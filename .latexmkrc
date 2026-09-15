# latexmkrc
# Configuration for compiling main.tex with LuaLaTeX + biber + bib2gls

@default_files = ('main.tex');

$out_dir        = 'build';
$pdf_mode       = 4;
$postscript_mode = 0;
$dvi_mode       = 0;

$lualatex = 'lualatex -interaction=nonstopmode -synctex=1 %O %S';

# biblatex + biber
$bibtex       = 'biber %O %B';
$biber        = 'biber %O %B';
$bibtex_use   = 2;

# makeindex (unused, but harmless)
$makeindex    = 'makeindex %O -o %D %S';
$max_repeat   = 5;

# what -C removes
$clean_ext = 'bbl run.xml out blg lot lof toc aux log fls fdb_latexmk '
           . 'nav snm vrb synctex.gz acn acr alg glg glo gls glstex glsdefs '
           . 'slg sls slo';
$clean_full_ext = $clean_ext . ' pdf dvi ps';
$cleanup_includes_generated = 0;
$cleanup_includes_cusdep_generated = 0;
$hash_calc_ignore_pattern{'pdf'} = '^';

# --- ensure build subdirectories exist for \include aux files ------------
sub ensure_build_subdirs {
    system("mkdir -p $out_dir/sections/frontmatter $out_dir/sections/chapters");
}
ensure_build_subdirs();              # in case .latexmkrc is sourced after -C
$init_hooks{'pre_processing'} = sub { ensure_build_subdirs(); };

# --- bib2gls integration -------------------------------------------------
push @generated_exts, 'glstex', 'glg', 'glsdefs';
$makeglossaries = '';                # don't call makeglossaries

add_cus_dep('aux', 'glstex', 0, 'run_bib2gls');
add_cus_dep('bib', 'glstex', 0, 'run_bib2gls');

sub run_bib2gls {
    my ($base, $path) = @_;
    $base =~ s/\.(aux|bib)$//;
    $base =~ s|^\Q$out_dir\E/||;        # <-- strip leading "build/"
    system("bib2gls --dir=$out_dir $base");
}
