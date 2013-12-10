# -*- coding: utf-8 -*-
import os, shutil
import puddlestuff

version = puddlestuff.version_string

from glob import glob
from subprocess import call

RST_BASE='puddletag-docs-rst-' + version
HTML_BASE = 'puddletag-docs-html-' + version

def rst_docs(base = RST_BASE):

    images = glob('_build/puddletag-docs-html-' + version + '/_images/*.png')

    basenames = set(map(os.path.basename, images))

    out_dir = os.path.join('/tmp/', base)

    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    for fn in ['docs.txt', 'about.txt', 'subs.txt',
        'conf.py', 'Makefile', 'INSTALL', 'changelog']:
        shutil.copy(fn, out_dir)

    source_dir = os.path.join(out_dir, 'source')

    if not os.path.exists(source_dir):
        os.makedirs(source_dir)

    template_dir = os.path.join(out_dir, '_templates')

    if not os.path.exists(template_dir):
        os.makedirs(template_dir)

    shutil.copytree('_templates/offline', os.path.join(template_dir, 'offline'))

    for f in glob('source/*.txt') + glob('source/*.tar.gz'):
        shutil.copy(f, source_dir)

    for f in glob('source/*/*.png'):
        if os.path.basename(f) not in basenames:
            continue
        dirname = os.path.join(out_dir, os.path.dirname(f))
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        shutil.copy(f, os.path.join(dirname, os.path.basename(f)))

    curdir = os.path.abspath('.')
    os.chdir(os.path.dirname(out_dir))

    call(['tar', '--bzip2', '-c', '-f',
        os.path.join(curdir, base + '.tar.bz2'),
        os.path.basename(out_dir)])
    os.chdir(curdir)

def html_docs(base=HTML_BASE):
    if os.path.exists('_build'):
        shutil.rmtree('_build')
    call(['make', 'documentation'])
    shutil.rmtree('_build/documentation/_sources')
    os.remove('_build/documentation/.buildinfo')
    out_dir = '_build/' + base
    os.rename('_build/documentation', out_dir)
    curdir = os.path.abspath('.')
    os.chdir('_build')
    call(['tar', '--bzip2', '-c', '-f',
        os.path.join(curdir, base + '.tar.bz2'),
        os.path.basename(out_dir)])
    os.chdir(curdir)


if __name__ == '__main__':
    html_docs()
    rst_docs()