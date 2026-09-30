#!/usr/bin/env python3
"""
scripts/preprocess.py <root> <in.tex> <out.tex>

Prepare a flattened LaTeX file for Pandoc conversion to DOCX/ODT.
Does what Pandoc cannot:

  * expand \\gls{...}, \\Glsentrylong{...}, etc. using glossaries/*.bib
  * resolve \\Cref{...}, \\cref{...}, \\ref{...} using build/*.aux
  * replace \\unit{...}, \\qty{...} with plain text (custom macros)
  * drop \\directlua{...} blocks
  * comment out \\includestandalone{...} (Pandoc cannot run TikZ)
  * unwrap landscape / ThreePartTable / xltabular / tablenotes
"""
import os
import re
import sys
import csv
import glob
import subprocess
import shutil
import tempfile

BIB_FILES = [
    'glossaries/abbreviations.bib',
    'glossaries/symbols.bib',
    'glossaries/units.bib',
]

AUX_FILES = [
    'build/main.aux',
    'build/sections/frontmatter/acknowledgements.aux',
    'build/sections/frontmatter/abstract.aux',
    'build/sections/frontmatter/resumo.aux',
    'build/sections/chapters/01_introduction.aux',
    'build/sections/chapters/02_literature_review.aux',
    'build/sections/chapters/03_materials_methods.aux',
    'build/sections/chapters/04_results.aux',
    'build/sections/chapters/06_conclusion.aux',
]


# --------------------------------------------------------------------------
# bib parsing
# --------------------------------------------------------------------------
def parse_bib(text):
    entries = {}
    for m in re.finditer(r'@(\w+)\s*\{\s*([^,\s]+)\s*,(.*?)\n\}',
                         text, re.DOTALL):
        key, body = m.group(2), m.group(3)
        fields = {}
        for fm in re.finditer(
                r'(\w+)\s*=\s*(\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}|'
                r'"[^"]*"|[^,\n]+)', body, re.DOTALL):
            fname = fm.group(1)
            fval = fm.group(2).strip()
            if fval[:1] == '{' and fval[-1:] == '}':
                fval = fval[1:-1]
            elif fval[:1] == '"' and fval[-1:] == '"':
                fval = fval[1:-1]
            fields[fname] = fval.strip()
        entries[key] = fields
    return entries


def load_glossaries(root):
    entries = {}
    for rel in BIB_FILES:
        p = os.path.join(root, rel)
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                entries.update(parse_bib(f.read()))
    return entries


def _clean(value):
    if not value:
        return ''
    value = re.sub(r'\\ce\{([^}]*)\}', r'\1', value)
    value = re.sub(r'\\unit\{([^}]*)\}', r'\1', value)
    value = re.sub(r'\\text(sub|super)script\{([^}]*)\}', r'\2', value)
    value = re.sub(r'\\[gG]ls(pl|first|firstplural)?\{([^}]*)\}', r'\2', value)
    return re.sub(r'\s+', ' ', value).strip()


def _long(entries, key, cap=False):
    e = entries.get(key, {})
    v = None
    for f in ('long', 'name', 'symbol', 'short'):
        if e.get(f):
            v = _clean(e[f])
            break
    if v is None:
        v = key
    return v[0].upper() + v[1:] if (cap and v) else v


def _short(entries, key, cap=False):
    e = entries.get(key, {})
    v = None
    for f in ('short', 'name', 'symbol', 'long'):
        if e.get(f):
            v = _clean(e[f])
            break
    if v is None:
        v = key
    return v[0].upper() + v[1:] if (cap and v) else v


# --------------------------------------------------------------------------
# aux parsing
# --------------------------------------------------------------------------
def _kind(label):
    if label.startswith(('graph:', 'fig:')):
        return 'figure'
    if label.startswith('tab:'):
        return 'table'
    if label.startswith('eq:'):
        return 'equation'
    if label.startswith('ch:'):
        return 'chapter'
    if label.startswith('subsec:'):
        return 'subsection'
    if label.startswith('sec:'):
        return 'section'
    return 'section'


PREFIX = {
    'figure': 'Fig.',
    'table': 'Table',
    'equation': 'Eq.',
    'chapter': 'Chapter',
    'section': 'Section',
    'subsection': 'Section',
}


def load_labels(root):
    refs = {}
    for rel in AUX_FILES:
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            continue
        with open(p, encoding='utf-8') as f:
            for line in f:
                m = re.match(
                    r'\\newlabel\{([^}]+)\}\{\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}',
                    line)
                if not m:
                    continue
                label = m.group(1)
                if label.endswith('@cref'):
                    continue
                refs[label] = {'num': m.group(2),
                               'page': m.group(3),
                               'title': m.group(4)}
    return refs


# --------------------------------------------------------------------------
# replacement passes
# --------------------------------------------------------------------------
def pass_glossaries(text, entries):
    # order matters: longer macro names first
    text = re.sub(r'\\glsentrylong\{([^}]+)\}',
                  lambda m: _long(entries, m.group(1)), text)
    text = re.sub(r'\\Glsentrylong\{([^}]+)\}',
                  lambda m: _long(entries, m.group(1), cap=True), text)
    text = re.sub(r'\\glsentryshort\{([^}]+)\}',
                  lambda m: _short(entries, m.group(1)), text)
    text = re.sub(r'\\Glsentryshort\{([^}]+)\}',
                  lambda m: _short(entries, m.group(1), cap=True), text)

    text = re.sub(r'\\glsfirst(plural)?\{([^}]+)\}',
                  lambda m: _long(entries, m.group(2)), text)
    text = re.sub(r'\\Glsfirst(plural)?\{([^}]+)\}',
                  lambda m: _long(entries, m.group(2), cap=True), text)

    text = re.sub(r'\\glstext\{([^}]+)\}',
                  lambda m: _short(entries, m.group(1)), text)
    text = re.sub(r'\\Glstext\{([^}]+)\}',
                  lambda m: _short(entries, m.group(1), cap=True), text)

    text = re.sub(r'\\glsdisp\{[^}]+\}\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\glslink\{([^}]+)\}\{([^}]*)\}',
                  lambda m: m.group(2) or _short(entries, m.group(1)), text)
    text = re.sub(r'\\glsadd\{[^}]*\}', '', text)

    def sub(m):
        cmd, pl, key = m.group(1), m.group(2), m.group(3)
        cap = cmd[0] == 'G'
        v = _short(entries, key, cap)
        if pl == 'pl' and not v.endswith('s'):
            v += 's'
        return v

    text = re.sub(r'\\(GLS|Gls|gls)(pl)?\{([^}]+)\}', sub, text)

    # last-resort: kill remaining glsxtr* macros
    text = re.sub(r'\\[gG]lsxtr\w*\*?\{[^}]*\}', '', text)
    return text

def pass_definitions(text, root):
    path = os.path.join(root, 'definitions.tex')
    if not os.path.exists(path):
        return text
    with open(path, encoding='utf-8') as f:
        src = f.read()
    defs = dict(re.findall(
        r'\\newcommand\s*\{\s*\\([A-Za-z]+)\s*\}\s*\{((?:[^{}]|\{[^{}]*\})*)\}',
        src))

    # \Keywords is defined as
    #     \StrSubstitute[0]{\keywords}{, }{; }
    # Expand it FIRST — before we turn \keywords into a plain string.
    # Otherwise the expansion of \Keywords re-introduces \keywords
    # *after* the loop has already passed it.
    def _expand_keywords():
        return defs.get('keywords', '').replace(', ', '; ')

    text = text.replace('\\Keywords',       _expand_keywords())
    text = text.replace('\\palavraschaves', defs.get('palavraschaves', ''))

    # Then everything else — but skip the two we already handled.
    for name, body in defs.items():
        if name in ('Keywords', 'palavraschaves'):
            continue
        text = text.replace('\\' + name, body)

    # Safety net for any \StrSubstitute[opts]{s}{a}{b} that survived.
    text = re.sub(
        r'\\StrSubstitute(?:\[[^\]]*\])?'
        r'\{([^{}]*)\}\{([^{}]*)\}\{([^{}]*)\}',
        lambda m: m.group(1).replace(m.group(2), m.group(3)),
        text)
    return text

def pass_refs(text, refs):
    def sub_cref(m):
        cmd = m.group(1)
        out = []
        for lbl in (s.strip() for s in m.group(2).split(',')):
            info = refs.get(lbl)
            if not info:
                out.append('??')
                continue
            prefix = PREFIX[_kind(lbl)]
            if cmd == 'cref':
                prefix = prefix.lower()
            out.append(prefix + '\u00a0' + info['num'])
        return ' and '.join(out)

    text = re.sub(r'\\(Cref|cref)\{([^}]+)\}', sub_cref, text)

    def sub_ref(m):
        info = refs.get(m.group(1))
        return info['num'] if info else '??'

    text = re.sub(r'\\(?:ref|pageref|autoref)\{([^}]+)\}', sub_ref, text)
    text = re.sub(r'\\label\{[^}]*\}', '', text)
    return text

def pass_graphics(text, root):
    import glob, shutil, os
    found = {}
    for d in ('assets', 'assets/figures', 'assets/graphs',
              'assets/logos', 'assets/photos',
              'assets/photos/ampts', 'assets/photos/reactor'):
        for p in glob.glob(os.path.join(root, d, '*')):
            found[os.path.basename(p)] = p
    def sub(m):
        opts, name = m.group(1), m.group(2)
        full = found.get(name, name)
        return r'\includegraphics%s{%s}' % (opts, full)
    return re.sub(r'\\includegraphics(\[[^\]]*\])?\{([^}]+)\}', sub, text)

def pass_units(text):
    UNIT_SUBS = [
        ('mega', 'M'), ('kilo', 'k'), ('milli', 'm'),
        ('gram', 'g'), ('litre', 'L'), ('liter', 'L'),
        ('meter', 'm'), ('metre', 'm'), ('second', 's'),
        ('minute', 'min'), ('hour', 'h'), ('day', 'd'),
        ('year', 'yr'), ('yr', 'yr'),
        ('mol', 'mol'), ('mole', 'mol'),
        ('celsius', '\u00b0C'), ('percent', '%'),
        ('molar', 'M'), ('gforce', 'G'), ('tonne', 't'),
        ('nml', 'NmL'), ('normality', 'N'), ('dil', 'X'),
        ('VSfed', 'VS_fed'), ('VS', 'VS'),
        ('reactorlitre', 'L_r'),
        ('CHCOOH', 'CH3COOH'), ('CaCO', 'CaCO3'),
        ('NaOH', 'NaOH'), ('CO', 'CO2'), ('CH', 'CH4')
    ]
    UNIT_MAP = dict(UNIT_SUBS)

    def expand_macro_string(s):
        out, i, n = [], 0, len(s)
        while i < n:
            c = s[i]
            if c == '\\':
                j = i + 1
                while j < n and s[j].isalpha():
                    j += 1
                name = s[i+1:j]
                if name == 'per':
                    out.append('/')
                elif name in ('cubic', 'squared'):
                    k = j
                    while k < n and s[k].isspace():
                        k += 1
                    if k < n and s[k] == '\\':
                        l = k + 1
                        while l < n and s[l].isalpha():
                            l += 1
                        base_name = s[k+1:l]
                        base = UNIT_MAP.get(base_name, base_name)
                        out.append(base + ('\u00b3' if name == 'cubic' else '\u00b2'))
                        j = l
                    else:
                        out.append('\\' + name)
                elif name in UNIT_MAP:
                    out.append(UNIT_MAP[name])
                else:
                    out.append('\\' + name)
                i = j
            elif c.isspace():
                out.append(' ')
                i += 1
            else:
                out.append(c)
                i += 1
        result = re.sub(r'\s+', ' ', ''.join(out)).strip()
        # "kgVS" -> "kg VS"
        result = re.sub(r'([a-z])([A-Z])', r'\1 \2', result)
        return result

    text = re.sub(
        r'\\unit\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}',
        lambda m: expand_macro_string(m.group(1)),
        text)
    text = re.sub(
        r'\\qty\{([^{}]*)\}\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}',
        lambda m: m.group(1) + ' ' + expand_macro_string(m.group(2)),
        text)
    text = re.sub(
        r'\\qtyrange\{([^{}]*)\}\{([^{}]*)\}'
        r'\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}',
        lambda m: (m.group(1) + '\u2013' + m.group(2) + ' '
                   + expand_macro_string(m.group(3))),
        text)
    text = re.sub(r'\\numrange\{([^{}]*)\}\{([^{}]*)\}',
              lambda m: m.group(1) + '\u2013' + m.group(2), text)
    text = re.sub(r'\\num\{([^{}]*)\}', r'\1', text)
    return text


def _balanced_drop(text, needle):
    """Remove every `needle{...}` with balanced braces."""
    out, i = [], 0
    while True:
        j = text.find(needle, i)
        if j < 0:
            out.append(text[i:])
            break
        out.append(text[i:j])
        k = j + len(needle)
        while k < len(text) and text[k] in ' \t\n':
            k += 1
        if k < len(text) and text[k] == '{':
            depth, k = 1, k + 1
            while k < len(text) and depth:
                c = text[k]
                depth += (c == '{') - (c == '}')
                k += 1
        i = k
    return ''.join(out)


def pass_directlua(text):
    return _balanced_drop(text, r'\directlua')

def pass_lua_tables(text, root):
    def sub(m):
        csv_rel, ncols = m.group(1), int(m.group(2))
        rows = list(csv.reader(open(os.path.join(root, csv_rel))))
        rows = [r for r in rows if any(c.strip() for c in r)]
        out = []
        for r in rows:
            r = (r + [''] * ncols)[:ncols]
            out.append(' & '.join('\\mbox{%s}' % c for c in r) + r' \\')
        return '\n'.join(out)
    text = re.sub(r'\\mbox\{([^{}]*)\}', r'\1', text)
    text = re.sub(r'\\makecell\{([^{}]*)\}', r'\1', text)
    return re.sub(
        r'\\directlua\{emit_grouped_table\("([^"]+)",\s*(\d+)\)\}',
        sub, text)

def _read_braced(text, i):
    """text[i] must be '{'. Return (content, index_after_closing_brace)."""
    depth, j = 1, i + 1
    while j < len(text) and depth > 0:
        c = text[j]
        if c == '{': depth += 1
        elif c == '}': depth -= 1
        j += 1
    return text[i+1:j-1], j


def pass_csvreader(text, root):
    import csv as _csv
    out, i = [], 0
    while True:
        j = text.find(r'\csvreader', i)
        if j < 0:
            out.append(text[i:]); break
        out.append(text[i:j])
        k = j + len(r'\csvreader')
        # skip optional [...] key list
        while k < len(text) and text[k] in ' \t\n': k += 1
        if k < len(text) and text[k] == '[':
            depth = 1; k += 1
            while k < len(text) and depth:
                if text[k] == '[': depth += 1
                elif text[k] == ']': depth -= 1
                k += 1
        # skip three mandatory { ... } groups
        for _ in range(3):
            while k < len(text) and text[k] in ' \t\n': k += 1
            if k < len(text) and text[k] == '{':
                _, k = _read_braced(text, k)
        # the second group holds the CSV path
        # (we re-read it from the original text)
        m = re.search(r'\\csvreader\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}',
                      text[j:])
        if m:
            rel = m.group(1)
            rows = list(_csv.reader(open(os.path.join(root, rel))))
            out.append('\n'.join(' & '.join(r) + r' \\' for r in rows))
        i = k
    return ''.join(out)

def pass_standalone(text, root):
    """Compile \\includestandalone{rel} to <root>/<rel>.pdf, cached by mtime.

    latexmk names its output after the *source file's* basename, so we
    compile a throwaway wrapper in a temp directory whose basename matches
    the target PDF. That way latexmk emits `foo.pdf`, which we then copy
    next to the original `foo.tex`.
    """
    def sub(m):
        rel = m.group(1)
        tex = os.path.join(root, rel + '.tex')
        pdf = os.path.join(root, rel + '.pdf')
        out_dir = os.path.dirname(pdf)
        os.makedirs(out_dir, exist_ok=True)

        # ---- cache hit ------------------------------------------------
        if (os.path.exists(pdf)
                and os.path.getmtime(pdf) >= os.path.getmtime(tex)):
            return r'\includegraphics{%s}' % pdf

        # ---- build in a tempdir --------------------------------------
        basename = os.path.basename(rel)          # e.g. "garlapati2016-flow-gl"
        with tempfile.TemporaryDirectory(prefix='tikz-') as tmp:
            wrapper = os.path.join(tmp, basename + '.tex')
            with open(wrapper, 'w', encoding='utf-8') as w:
                w.write(r'\documentclass[tikz,border=2pt]{standalone}' '\n'
                        r'\usepackage{preamble}' '\n'
                        r'\usepackage{graphs}' '\n'
                        r'\usepackage{alone}' '\n'
                        r'\begin{document}' '\n')
                with open(tex, encoding='utf-8') as t:
                    w.write(t.read())
                w.write('\n' r'\end{document}' '\n')

            rc = subprocess.run(
            ['latexmk', '-lualatex',
            '-interaction=nonstopmode', '-halt-on-error', '-g', '-c',
            '-outdir=' + out_dir,      # PDF lands next to the .tex
            tex],
            cwd=root, check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode

        built = os.path.join(out_dir, basename + '.pdf')
        if rc == 0 and os.path.exists(built):
            return r'\includegraphics{%s}' % built
        return r'% TIKZ-FAILED: ' + rel

    return re.sub(
        r'\\includestandalone(?:\[[^\]]*\])?\{([^}]+)\}',
        sub, text)


def pass_environments(text):
    for env in ('landscape', 'ThreePartTable'):
        text = text.replace(r'\begin{%s}' % env, '')
        text = text.replace(r'\end{%s}' % env, '')
    text = re.sub(r'\\begin\{tablenotes\}.*?\\end\{tablenotes\}',
                  '', text, flags=re.DOTALL)
    def sub_xlt(m):
        spec = m.group(1)
        ncols = max(2, len(re.findall(r'[cClrR]', spec)))
        return r'\begin{tabular}{' + 'l' * ncols + '}'
    text = re.sub(
        r'\\begin\{xltabular\}\{[^}]*\}\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
        sub_xlt, text)
    text = text.replace(r'\end{xltabular}', r'\end{tabular}')
    text = re.sub(r'\\tnote\{([^}]+)\}', r'(\1)', text)
    text = text.replace(r'\addlinespace', '')
    text = re.sub(r'\\(tableofcontents|listoffigures|listoftables)\b', '', text)
    text = text.replace(r'\begin{xltabular}', r'\begin{longtable}')
    text = text.replace(r'\end{xltabular}',   r'\end{longtable}')
    return text

def pass_cleanup(text):
    # Strip blank lines immediately inside math display environments.
    # Pandoc breaks the math if it sees an empty line before \end{equation}.
    for env in ('equation', 'equation*', 'align', 'align*',
                'gather', 'gather*', 'multline', 'multline*'):
        pat_begin = r'(\\begin\{' + env + r'\}(?:\[[^\]]*\])?)\n\s*\n'
        text = re.sub(pat_begin, r'\1\n', text)
        pat_end = r'\n\s*\n(\s*\\end\{' + env + r'\})'
        text = re.sub(pat_end, r'\n\1', text)
    # Collapse runs of blank lines anywhere else to a single blank line.
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text

def pass_strip_newcommands(text):
    """Remove leftover \\newcommand{\\name}{...} (or \\newcommand{<value>}{...})
    declarations. latexpand has already replaced all usages, and it can
    mangle \\newcommand when its argument was itself expanded."""
    out, i = [], 0
    needle = r'\newcommand'
    while True:
        j = text.find(needle, i)
        if j < 0:
            out.append(text[i:]); break
        out.append(text[i:j])
        k = j + len(needle)
        if k < len(text) and text[k] == '*':
            k += 1
        # first mandatory { ... }
        while k < len(text) and text[k] in ' \t\n': k += 1
        if k < len(text) and text[k] == '{':
            _, k = _read_braced(text, k)
        # second mandatory { ... }
        while k < len(text) and text[k] in ' \t\n': k += 1
        if k < len(text) and text[k] == '{':
            _, k = _read_braced(text, k)
        # eat to end of line
        while k < len(text) and text[k] != '\n': k += 1
        i = k
    return ''.join(out)

def pass_equation_to_display(text):
    # Pandoc occasionally mis-renders consecutive \begin{equation}
    # environments. \[ ... \] is handled more predictably.
    text = re.sub(r'\\begin\{equation\*?\}', r'\\[', text)
    text = re.sub(r'\\end\{equation\*?\}',  r'\\]', text)
    return text

# --------------------------------------------------------------------------
def main():
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    root, in_path, out_path = sys.argv[1:4]

    entries = load_glossaries(root)
    refs    = load_labels(root)

    with open(in_path, encoding='utf-8') as f:
        text = f.read()

    # LaTeX cleanup first, so patterns below see simpler input
    text = pass_lua_tables(text, root)       # 1. expand emit_grouped_table
    text = pass_csvreader(text, root)        # 2. expand \csvreader
    text = pass_directlua(text)              # 3. drop leftover \directlua
    text = pass_environments(text)           # 4. unwrap landscape/xltabular
    text = pass_strip_newcommands(text)      # 5. drop all \newcommand decls  <-- moved
    text = pass_glossaries(text, entries)    # 6. \gls, \Glsentrylong, ...
    text = pass_definitions(text, root)      # 7. \Keywords, \palavraschaves
    text = pass_refs(text, refs)             # 8. \Cref, \ref
    text = pass_graphics(text, root)         # 9. absolute image paths
    text = pass_units(text)                  # 10. \qty, \unit, \num
    text = pass_standalone(text, root)       # 11. build TikZ PDFs
    text = pass_cleanup(text)
    text = pass_equation_to_display(text)

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(text)


if __name__ == '__main__':
    main()
