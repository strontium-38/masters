# latexmkrc
# Configuration for compiling main.tex with pdflatex + biber

# Main file
@default_files = ('main.tex');

# Build directory
$out_dir = 'build';

# PDF mode (generate PDF directly)
$pdf_mode = 4;
$postscript_mode = 0;
$dvi_mode = 0;

# LuaLaTeX command with synctex and nonstopmode
$lualatex = 'lualatex -interaction=nonstopmode -synctex=1 %O %S';

# Bibliography: use biber (for biblatex)
$bibtex = 'biber %O %B';
$biber = 'biber %O %B';
$bibtex_use = 2;       # 2 = run biber automatically

# Makeindex (if you use \makeindex)
$makeindex = 'makeindex %O -o %D %S';

# Maximum number of passes
$max_repeat = 5;

# Clean up auxiliary files
$clean_ext = 'bbl run.xml out blg lot lof toc aux log fls fdb_latexmk nav snm vrb synctex.gz acn acr alg glg glo gls ist';
$clean_full_ext = $clean_ext . ' pdf dvi ps';

# Prevent latexmk from deleting the final PDF on clean
$cleanup_includes_generated = 0;
$cleanup_includes_cusdep_generated = 0;

# Force a full recompile if source files change
$hash_calc_ignore_pattern{'pdf'} = '^';

# For large documents, increase memory (optional)
$pdflatex =~ s/pdflatex/pdflatex --shell-escape/;
