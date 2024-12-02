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

    given $filename.IO.extension {
        when 'pdf' { # 2312.10426
            run 'open', $filename;
            exit;
        }
        when 'gz' {
            run 'gunzip', '-f', $filename;
            unlink $filename;
            $filename = $filename.IO.extension: '';
            given $filename.IO.extension {
                when 'ps' { # cs/0003065
                    run 'open', $filename;
                    exit;
                }
                when 'html' {
                    run 'open', $filename;
                    exit;
                }
                when 'tar' {
                    run 'tar', 'xf', $filename;
                    unlink $filename;
                }
                when '' {
                    my $texfilename = $filename.IO.extension: 'tex';
                    rename $filename, $texfilename;
                }
                default { say "Unknown extension: $_" }
            }
        }
        default { say "Unknown extension: $_", }
    }

    for dir(test => /\.tex$/) -> $file {
       if $file.comb('\\documentclass', 1, :enc<utf8-c8>) { # cs/0301032
           my $proc = run 'texliveonfly', $file, :out, :err, :merge, :enc<utf8-c8>; # 2106.04826
           my @args = '-interaction=nonstopmode', $file;
           if $proc.out.comb('UnicodeDecodeError', 1) { # cs/0509027
               @args = '-interaction=nonstopmode', '\\UseRawInputEncoding', '\\input', $file;
           }
           $proc = run 'pdflatex', @args, :out, :enc<utf8-c8>; # cs/0509027
           while $proc.out.comb('Rerun', 1) {
               $proc.spawn(@args);
           }
           run 'open', $file.IO.extension: 'pdf';
           exit;
       };
    }
    say 'No TeX Found'; # TODO: cs/0003064
}
