
# -*- coding: utf-8 -*-
from subprocess import call
import subprocess
import sys, os, pdb, re
import puddlestuff
import shutil

dirname = 'puddletag-' + puddlestuff.version_string.lower()

try:
    shutil.rmtree('deb_build')
except EnvironmentError:
    pass

os.mkdir('deb_build')
os.mkdir('deb_build/control')
os.mkdir('deb_build/data')

source_files = [z.strip() for z in open('MANIFEST', 'r').readlines()
    if z.strip().endswith('.py') and z.startswith('puddlestuff')]

BASE_LIB = 'deb_build/data/usr/lib/python2.6/dist-packages/'

for f in source_files:
    f_dir = os.path.dirname(f)
    new_dir = os.path.join(BASE_LIB, f_dir)
    if not os.path.exists(new_dir):
        os.makedirs(new_dir)
    shutil.copy(f, os.path.join(new_dir, os.path.basename(f)))

os.makedirs('deb_build/data/usr/share/applications')
shutil.copy('puddletag.desktop', 'deb_build/data/usr/share/applications')
os.makedirs('deb_build/data/usr/share/doc')
for z in ['HACKING', 'NEWS', 'README', 'THANKS', 'TODO', 'copyright',
    'changelog']:
    shutil.copy(z, 'deb_build/data/usr/share/doc')

os.makedirs('deb_build/data/usr/share/man/man1')
shutil.copy('puddletag.1', 'deb_build/data/usr/share/man/man1')
call(['gzip', 'deb_build/data/usr/share/man/man1/puddletag.1'])

os.makedirs('deb_build/data/usr/share/menu')
shutil.copy('menu', 'deb_build/data/usr/share/puddletag')

os.makedirs('deb_build/data/usr/share/pixmaps')
shutil.copy('puddletag.png', 'deb_build/data/usr/share/pixmaps')

os.makedirs('deb_build/data/usr/share/pyshared')
shutil.copytree('deb_build/data/usr/lib/python2.6/dist-packages/puddlestuff',
    'deb_build/data/usr/share/pyshared/puddlestuff')

os.makedirs('deb_build/data/usr/share/python-support')
shutil.copy('puddletag.public', 'deb_build/data/usr/share/python-support')

call(['python2', 'setup.py', '--quiet', 'egg_info'])
shutil.copy('puddletag.egg-info/PKG-INFO',
    'deb_build/data/usr/share/pyshared/puddletag.egg-info')
shutil.copy('puddletag.egg-info/PKG-INFO',
    'deb_build/data/usr/lib/python2.6/dist-packages/puddletag.egg-info')
shutil.rmtree('puddletag.egg-info')

os.makedirs('deb_build/data/usr/lib/python2.7/')
shutil.copytree('deb_build/data/usr/lib/python2.6/dist-packages/',
    'deb_build/data/usr/lib/python2.7/dist-packages/')

os.makedirs('deb_build/data/usr/bin')
shutil.copy2('puddletag',
    'deb_build/data/usr/bin/puddletag')

CONTROL_DIR = 'deb_build/control'
shutil.copy('preinst', CONTROL_DIR)
shutil.copy('prerm', CONTROL_DIR)
shutil.copy('postinst', CONTROL_DIR)

info = subprocess.Popen(['find', 'deb_build/data/usr',
        '-type', 'f' ,'-exec', 'md5sum', '{}', ';'],
    stdout=subprocess.PIPE,stderr=subprocess.PIPE)

md5sums = info.stdout.read().replace('deb_build/data/', '')
f = open(os.path.join(CONTROL_DIR, 'md5sums'), 'w')
f.write(md5sums)
f.close()

control = '''Package: puddletag
Version: %s
Architecture: all
Maintainer: concentricpuddle <concentricpuddle@gmail.com>
Installed-Size: %d
Depends: python (>= 2.6), python-support, python-mutagen (>= 1.14), python-qt4 (>= 4.5), python-pyparsing (>= 1.5.1), python-configobj (>= 4.5)
Recommends: libchromaprint-tools (>= 0.4)
Homepage: http://puddletag.sourceforge.net
Section: sound
Priority: optional
Description:Simple, powerful audio tag editor.
 puddletag is an audio tag editor (primarily created) for GNU/Linux similar
 to the Windows program, Mp3tag. Unlike most taggers for GNU/Linux,
 it uses a spreadsheet-like layout so that all the tags you
 want to edit by hand are visible and easily editable.
 .
 The usual tag editor features are supported like extracting tag
 information from filenames, renaming files based on
 their tags by using patterns and basic tag editing.
 .
 Then there're Functions, which can do things like replace
 text, trim it, do case conversions, etc. Actions can
 automate repetitive tasks. You can import your QuodLibet
 library, lookup tags using Amazon (including cover art),
 Discogs (does cover art too!), FreeDB and MusicBrainz.
 There's quite a bit more, but I've reached my comma quota.
 .
 Supported formats: ID3v1, ID3v2 (mp3), MP4 (mp4, m4a, etc.),
 VorbisComments (ogg, flac), Musepack (mpc),
 Monkey's Audio (ape) and WavPack (wv).
''' 

dir_info = subprocess.Popen(['du', '-s', 'deb_build/data/'],
    stdout=subprocess.PIPE,stderr=subprocess.PIPE)

dir_size = int(re.search('\d+', dir_info.stdout.readlines()[0]).group())

control = control % (puddlestuff.version_string, dir_size)

f = open('deb_build/control/control', 'w')
f.write(control)
f.close()

call(['tar', 'cz', '-C', 'deb_build/control', '-f', 'deb_build/control.tar.gz', '.'])
call(['chmod', '744', '-R', 'deb_build/data'])
call(['chmod', '755', '-R', 'deb_build/data/usr/bin/puddletag'])
call(['tar', 'cz', '-C', 'deb_build/data', '-f', 'deb_build/data.tar.gz', '.'])
f = open('deb_build/debian-binary', 'w')
f.write('2.0\n')
f.close()


deb_name = 'puddletag_' + puddlestuff.version_string + '-1_all.deb'

call(['ar', 'rcu', 'dist/' + deb_name, 'deb_build/debian-binary',
    'deb_build/control.tar.gz', 'deb_build/data.tar.gz'])

outputdir = sys.argv[1] if len(sys.argv) > 1 else None
if outputdir:
    shutil.move(os.path.join('dist', deb_name), outputdir)
