# latexmkrc
@default_files = ('main.tex');

$out_dir         = 'build';
$pdf_mode        = 4;
$postscript_mode = 0;
$dvi_mode        = 0;

$lualatex = 'lualatex -interaction=nonstopmode -synctex=1 -shell-escape %O %S';

$bibtex     = 'biber %O %B';
$biber      = 'biber %O %B';
$bibtex_use = 2;

$makeindex = 'makeindex %O -o %D %S';
$max_repeat = 6;

# Allow -C to remove everything, including custom-dep-generated files
$cleanup_includes_generated        = 1;
$cleanup_includes_cusdep_generated = 1;

# --- build subdirectories ---
sub ensure_build_subdirs {
    system("mkdir -p $out_dir/sections/frontmatter $out_dir/sections/chapters");
}
ensure_build_subdirs();
$init_hooks{'pre_processing'} = sub { ensure_build_subdirs(); };

# --- bib2gls as a proper custom dependency ---
push @generated_exts, 'glstex', 'glg', 'glsdefs';
$makeglossaries = '';

add_cus_dep('aux', 'glstex', 0, 'run_bib2gls');
sub run_bib2gls {
    my ($base) = @_;               # e.g. "build/main" or "main"
    $base =~ s/\.aux$//;
    $base =~ s|^\Q$out_dir\E/||;   # strip leading "build/"
    my $ret = system("bib2gls --dir=$out_dir $base");
    warn "bib2gls failed (exit $ret) for $base\n" if $ret;
}
