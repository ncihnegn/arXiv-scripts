#!env raku

use HTTP::Tiny;

sub MAIN($tag) {
    mkdir $tag;
    chdir $tag;

    # Source
    my $archive = $tag ~'.tar.gz';
    my $response = HTTP::Tiny.new().mirror( 'https://arxiv.org/e-print/' ~$tag,
        $archive);
    die "Failed to download source!\n" unless $response<success>;
    run 'tar', 'zxf', $archive;

    for dir(test => /\.tex$/) -> $file {
       if $file.comb('\\documentclass', 1).Capture() {
           #run 'texliveonfly', $file;
           my $proc = run 'pdflatex', $file, :out;
           while $proc.out.comb('Rerun', 1).Capture() {
               $proc.spawn($file);
           }
           run 'open', $file.IO.extension: 'pdf';
       };
    }
}
