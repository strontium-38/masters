#!/usr/bin/env bash
# scripts/build-docx.sh
#
# Regenerate build/main.docx from main.tex.
#
#   1. latexpand      — flatten \include/\input into a single .tex
#   2. preprocess.py  — expand glossaries, refs, units; compile TikZ figures
#   3. pandoc         — convert to DOCX, extract media into build/media
#
# Usage:
#   scripts/build-docx.sh            # incremental
#   scripts/build-docx.sh --clean    # wipe build/ first
#
# Everything lands under build/. The only artefacts that still touch the
# source tree are assets/graphs/*.pdf (TikZ figures), which preprocess.py
# caches and re-generates only when a .tex source is newer.

set -euo pipefail

# --- Resolve repo root (works regardless of cwd) -------------------------
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
ROOT="$( dirname -- "$SCRIPT_DIR" )"
cd "$ROOT"

BUILD="$ROOT/build"
FLAT="$BUILD/main-flat.tex"
PANDOC_TEX="$BUILD/main-pandoc.tex"
DOCX="$BUILD/main.docx"
MEDIA_DIR="$BUILD/media"

# --- Args ----------------------------------------------------------------
CLEAN=0
for arg in "$@"; do
    case "$arg" in
        --clean) CLEAN=1 ;;
        -h|--help)
            cat <<'EOF'
Usage: scripts/build-docx.sh [--clean]

  --clean   remove build/ before running
  -h        show this help
EOF
            exit 0
            ;;
        *)
            echo "unknown option: $arg" >&2
            exit 2
            ;;
    esac
done

# --- Sanity --------------------------------------------------------------
for tool in latexpand pandoc python3; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "error: missing tool: $tool" >&2
        exit 1
    }
done
[[ -f main.tex              ]] || { echo "error: main.tex not found" >&2; exit 1; }
[[ -f scripts/preprocess.py ]] || { echo "error: scripts/preprocess.py not found" >&2; exit 1; }

# --- Clean ---------------------------------------------------------------
if (( CLEAN )); then
    echo "[build-docx] cleaning $BUILD"
    rm -rf "$BUILD"
fi
mkdir -p "$BUILD"

# --- 1. Flatten ----------------------------------------------------------
echo "[build-docx] latexpand  main.tex -> $FLAT"
latexpand main.tex > "$FLAT"

# --- 1.5 One LaTeX pass, just to populate build/*.aux --------------------
# \ref / \Cref need real numbers; preprocess.py reads them from .aux.
# We tolerate failures (missing fonts, tikz problems, etc.) because the
# aux files are written before the compile dies anyway.
echo "[build-docx] latexmk (aux)       -> $BUILD/main.aux"
mkdir -p "$BUILD/sections/frontmatter" "$BUILD/sections/chapters"
latexmk -lualatex -interaction=nonstopmode \
        -outdir="$BUILD" \
        main.tex >/dev/null 2>&1 || true

# --- 2. Preprocess for Pandoc -------------------------------------------
echo "[build-docx] preprocess         -> $PANDOC_TEX"
python3 scripts/preprocess.py . "$FLAT" "$PANDOC_TEX"

find assets/graphs -maxdepth 1 \( -name '*.aux' -o -name '*.log' \
    -o -name '*.out' -o -name '*.fls' -o -name '*.fdb_latexmk' \) -delete

# Warn (but don't abort) if some TikZ figure failed to build.
if grep -q 'TIKZ-FAILED' "$PANDOC_TEX"; then
    echo "[build-docx] WARNING: some TikZ figures failed to compile." >&2
    echo "             They will be missing from $DOCX." >&2
    grep -n 'TIKZ-FAILED' "$PANDOC_TEX" | sed 's/^/             /' >&2
fi

for pat in '\\glsauto' '\\Glsauto' '\\glsentrylongauto' '??'; do
    n=$(grep -c "$pat" "$PANDOC_TEX" || true)
    echo "[build-docx] occurrences of $pat: $n"
done

# --- 3. Pandoc -> DOCX ---------------------------------------------------
# Wipe the extracted-media dir each time so stale images don't pile up.
rm -rf "$MEDIA_DIR"

echo "[build-docx] pandoc             -> $DOCX"
pandoc "$PANDOC_TEX" \
    -o "$DOCX" \
    --citeproc \
    --lua-filter=scripts/fix-siunitx.lua \
    --lua-filter=scripts/fix-bookmarks.lua \
    --bibliography=references/references.bib \
    --csl=https://raw.githubusercontent.com/citation-style-language/styles/master/apa.csl \
    --toc --number-sections \
    --extract-media="$MEDIA_DIR" \
    --resource-path="$ROOT"

echo "[build-docx] done"
echo "             docx : $DOCX"
echo "             media: $MEDIA_DIR"
