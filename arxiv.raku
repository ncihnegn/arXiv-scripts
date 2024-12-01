#!env raku

use HTTP::Tiny;

sub MAIN($tag) {
    mkdir $tag;
    chdir $tag;

    # Source
    my $response = HTTP::Tiny.new.get: 'https://arxiv.org/e-print/' ~$tag;
    die "Failed to download source!\n" unless $response<success>;

    my $filename = ($response<headers><content-disposition> ~~ /\".*\"/) .Str;
    $filename ~~ tr/"//;
    $filename.IO.spurt($response<content>, :bin);
    if $filename.ends-with: '.tar.gz' { # 2411.00037
        run 'tar', 'zxf', $filename;
    } elsif $filename.ends-with: '.gz' { # 2410.07918
        run 'gunzip', $filename;
        my $tmpfilename = $filename.IO.extension: '';
        my $texfilename = $filename.IO.extension: 'tex';
        rename $tmpfilename, $texfilename;
    }

    for dir(test => /\.tex$/) -> $file {
       if $file.comb('\\documentclass', 1).Capture() {
           run 'texliveonfly', $file, :out;
           my $proc = run 'pdflatex', $file, :out;
           while $proc.out.comb('Rerun', 1).Capture() {
               $proc.spawn($file);
           }
           run 'open', $file.IO.extension: 'pdf';
           exit;
       };
    }
}
