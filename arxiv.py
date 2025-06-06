#!env python3
"""Download arXiv source and build pdf"""

import argparse
import glob
import os
import platform
import re
import subprocess
import tarfile
import urllib.error
from pathlib import Path

import requests
from lxml import etree


def filetype(file):
    "File type detection for specific types"
    header = Path(file).read_bytes()[0:4]
    if header == b'%PDF':
        return 'pdf'
    if header[0:-1] == b'%PS':
        return 'ps'
    if header[0:2] == b'\x1f\x8b':
        return 'gz'
    if Path(file).read_bytes()[257:262] == b'ustar':
        return 'tar'
    raise NotImplementedError('Unknown header', header)


def dvi2pdf(dvi, verbose):
    "Convert DVI to PDF"
    command = ['dvips', dvi]
    if verbose:
        print(command)
    subprocess.run(command, capture_output=not verbose, check=False)
    ps = Path(dvi).with_suffix('.ps')
    print('ps2pdf')
    subprocess.run(['ps2pdf', ps], capture_output=not verbose, check=False)
    return Path(dvi).with_suffix('.pdf')


def extract(archive):
    "Extract"
    if tarfile.is_tarfile(archive):
        os.rename(archive, archive + '.tar')
        archive += '.tar'
        with tarfile.open(archive) as tar:
            tar.extractall(filter='data')
    else:
        os.rename(archive, archive + '.gz')
        archive += '.gz'
        subprocess.run(['gzip', '-dNf', archive], check=False)


def tex2pdf(tex, compiler, verbose):
    "Build PDF"
    try:
        subprocess.run(['tectonic', tex],
                       capture_output=not verbose,
                       check=True)
        return Path(tex).with_suffix('.pdf')
    except FileNotFoundError as err:
        print(err)
    except subprocess.CalledProcessError as err:
        print(err)
    command = ['texliveonfly', '-c', compiler]
    if verbose:
        print(command + [tex])
    subprocess.run(command + [tex], capture_output=not verbose, check=False)
    command = [
        compiler, '-interaction=batchmode', '-halt-on-error', '-shell-escape'
    ]
    log = Path(tex).with_suffix('.log')
    text = log.read_text(encoding='utf-8', errors='ignore')
    if 'Package inputenc Error:' in text or 'UseRawInputEncoding' in text:
        if verbose:
            print('inputenc error')
        command.append('\\UseRawInputEncoding \\input')
    if 'extension: .pstex' in text or 'PSTricks' in text:
        if verbose:
            print('Switch to PostScript')
        compiler = compiler.replace('pdf', '')
        compiler = compiler.replace('xe', '')
        command[0] = compiler
    if '! LaTeX Error: ' in text:
        if verbose:
            print('Switch to XeLaTeX')
        compiler = 'xelatex'
        command[0] = compiler
    if verbose:
        print(command + [tex])
    missfont = Path('missfont.log')
    if missfont.exists():
        missfont.unlink()  # 3.8 only: missing_ok=True)
    subprocess.run(command + [tex], capture_output=not verbose, check=False)
    while 'Rerun to' in log.read_text(encoding='utf-8', errors='ignore'):
        if verbose:
            print('Rerun', command)
        subprocess.run(command + [tex],
                       capture_output=not verbose,
                       check=False)
    if missfont.exists():
        print('Missing fonts!')
        subprocess.run(['cat', 'missfont.log'], check=False)
    if not (compiler.startswith('pdf') or compiler.startswith('xe')):
        return dvi2pdf(Path(tex).with_suffix('.dvi'), verbose)
    return Path(tex).with_suffix('.pdf')


def view_pdf(pdf):
    "View PDF"
    if platform.system() == 'Darwin':
        subprocess.run(['open', pdf], check=False)
    if platform.system() == 'Windows':
        subprocess.run([pdf], check=False)
    if platform.system() == 'Linux':
        subprocess.run(['open', pdf], check=False)


def parse_args():
    "Parse arguments"
    parser = argparse.ArgumentParser(
        description='Download and build arXiv papers.')
    parser.add_argument('tag', help='paper tag')
    parser.add_argument('--compiler',
                        default='pdflatex',
                        help='use pdflatex or xelatex')
    parser.add_argument('-f',
                        '--forcedownload',
                        action='store_true',
                        help='force download')
    parser.add_argument('-s',
                        '--skipextract',
                        action='store_true',
                        help='skip extraction')
    parser.add_argument('-v',
                        '--verbose',
                        action='store_true',
                        help='verbose output')

    return parser.parse_args()


def download(tag, archive):
    "Download source"
    url = 'https://arxiv.org/e-print/' + tag
    try:
        req = requests.get(url, timeout=10)
        with open(archive, 'wb') as file:
            file.write(req.content)
            try:
                return filetype(archive)
            except IOError as err:
                print(err, url)
                return download_alternative_format(tag, archive)
        return 'latex'
    except urllib.error.HTTPError as err:
        print(err, url)
        return download_alternative_format(tag, archive)
    except urllib.error.URLError as err:
        print(err, url)
        return download_alternative_format(tag, archive)


def download_alternative_format(tag, archive):
    "Download alternative format"
    try:
        req = requests.get('https://arxiv.org/format/' + tag, timeout=10)
        html = etree.HTML(bytes(bytearray(req.text, encoding='utf-8')))
        forms = html.xpath('body/div/dl/dd/form')
        paths = list(map(lambda f: f.get('action'), forms))
        formats = {}
        for path in paths:
            fmt = path.split('/')[1]
            formats[fmt] = path
        if 'dvi' in formats:
            urllib.request.urlretrieve('https://arxiv.org' + formats['dvi'],
                                       archive)
            return 'dvi'
        if 'ps' in formats:
            urllib.request.urlretrieve('https://arxiv.org' + formats['ps'],
                                       archive)
            return 'ps'
        if 'pdf' in formats:
            urllib.request.urlretrieve('https://arxiv.org' + formats['pdf'],
                                       archive)
            return 'pdf'
        return 'error'
    except urllib.error.URLError as err:
        print(err)
        return 'error'


def find_main_latex():
    "Find the main LaTeX file"
    results = []
    for file in glob.glob('*.*t*x'):  # .tex or .ltx
        text = Path(file).read_text(encoding='utf-8', errors='ignore')
        if (not re.search("document.*subfiles", text)) and (
                re.search('^\\s*\\\\documentclass', text, re.MULTILINE)
                or re.search('^\\s*\\\\documentstyle', text, re.MULTILINE)):
            results.append(file)
    return results


def main():
    "Main script"
    args = parse_args()
    tag = args.tag
    compiler = args.compiler
    skipextract = args.skipextract
    forcedownload = args.forcedownload
    verbose = args.verbose
    print("arxiv:", tag)
    print("compiler:", compiler)
    print("skipextract:", skipextract)
    print("forcedownload:", forcedownload)
    print("verbose:", verbose)

    source = 'latex'
    if not compiler.endswith('latex'):
        source = 'tex'
        if verbose:
            print("Source: TeX")

    os.makedirs(tag, exist_ok=True)
    os.chdir(tag)

    archive = tag.split('/')[-1]

    # Download sources
    if not os.path.exists(archive) or forcedownload:
        if download(tag, archive) == 'dvi':
            source = 'dvi'
            if verbose:
                print("Source: DVI")

    pdf = archive + '.pdf'
    file_type = filetype(archive)
    if file_type == 'pdf':
        os.rename(archive, pdf)
        source = 'pdf'
        if verbose:
            print("Source: PDF")

    # Extract
    if not skipextract and (source.endswith('tex') or source.endswith('dvi')):
        if file_type == 'gz' or file_type == 'tar':
            extract(archive)

    if source == 'dvi':
        results = glob.glob('*.dvi')
        if not results:
            raise FileNotFoundError("Can't find a DVI file in", glob.glob('*'))
        dvi = results[0]
        pdf = dvi2pdf(dvi, verbose)

    if source.endswith('tex'):
        if source == 'latex':
            # Find the main file
            results = find_main_latex()
            if not results:
                if verbose:
                    print("Can't find the main LaTeX file in",
                          glob.glob('*.*t*x'))
                    print('Switch to plain TeX')
                source = 'tex'
                compiler = 'pdftex'
        if source == 'tex':
            results = glob.glob('*.tex')

        if not results:
            results = glob.glob('*')
            if results == ['withdrawn']:
                print("Paper withdrawn")
                return
            raise FileNotFoundError("Can't find a TeX file in", results)

        main_tex = results[0]

        # Build
        pdf = tex2pdf(main_tex, compiler, verbose)

    view_pdf(pdf)


if __name__ == '__main__':
    main()
