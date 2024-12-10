#!env raku

use HTTP::Tiny;

sub MAIN($tag) {
    mkdir $tag;
    chdir $tag;

    # Source
    my $response = HTTP::Tiny.new.get: 'https://arxiv.org/src/' ~$tag;
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
            my $gzip = run 'gzip', '-Nl', $filename, :out;
            # my $tail = run 'tail', '-n1', :in($gzip.out), :out;
            # my $cut = run 'cut', '-w', '-f5', :in($tail.out), :out;
            # my $original = $cut.out;
            my $original = split(' ', $gzip.out.lines()[1], :skip-empty).[3];
            run 'gunzip', '-Nf', $filename;
            given $original.IO.extension {
                when 'ps' { # cs/0003065
                    run 'open', $original;
                    exit;
                }
                when 'html' { # cs/0001003
                    run 'open', $original;
                    exit;
                }
                when 'tar' {
                    run 'tar', 'xf', $original;
                    unlink $original;
                    succeed;
                }
                when 'tex' {
                    succeed;
                }
                default { say "Unknown 2nd extension: $_" }
            }
        }
        default { say "Unknown 1st extension: $_", }
    }

    for dir(test => /\.tex$/) -> $file { # LaTeX
       if $file.comb('\\documentclass', 1, :enc<utf8-c8>) { # cs/0301032
           my $proc = run 'texliveonfly', $file, :out, :err, :merge, :enc<utf8-c8>; # 2106.04826
           my @args = '-interaction=nonstopmode', $file;
           if $proc.out.comb('UnicodeDecodeError', 1) { # cs/0509027
               @args = '-interaction=nonstopmode', '\\UseRawInputEncoding',
                       '\\input', $file;
           }
           $proc = run 'pdflatex', @args, :out, :enc<utf8-c8>; # cs/0509027
           while $proc.out.comb('Rerun', 1) {
               $proc.spawn(@args);
           }
           run 'open', $file.IO.extension: 'pdf';
           exit;
       };
    }
    for dir(test => /\.tex$/) -> $file { # Plain TeX
           my @args = '-interaction=nonstopmode', $file;
           my $proc = run 'pdftex', @args, :out, :enc<utf8-c8>; # math/9201303
           next if $proc.out.comb('Fatal', 1);
           run 'open', $file.IO.extension: 'pdf';
           exit;
    }
    say 'No TeX Found'; # TODO: cs/0003064, cs/0408036
}
