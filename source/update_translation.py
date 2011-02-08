# -*- coding: utf-8 -*-
from subprocess import call
import sys

usage = '''Usage: python update_translation.py [-h] [-q] language

Options:
    language: Locale of the language to be created eg. en_ZA, rus, fr_BE.
    -q Quiet mode (only error messages will be shown).
    -h Show this message.'''

verbose = True

try:
    lang = sys.argv[1]
    if lang.strip() == '-q':
        verbose = False
        lang = sys.argv[2]
except IndexError:
    print 'Error: No language specified\n'
    print usage
    sys.exit(1)

if lang in ('--help', '-h'):
    print usage
    sys.exit(0)

f = open('puddletag.pro', 'r+')
for line in f.readlines():
    if line.startswith('TRANSLATIONS'):
        f.seek(-len(line), 1)
        tr = ' translations/puddletag_%s.ts\n' % lang
        if tr.strip() not in line:
            line = line.strip() + tr
        f.write(line)
        break
f.close()

if verbose:
    print 'Updating translations...\n'

try:
    if verbose:
        call(['pylupdate4',  '-verbose', 'puddletag.pro'])
    else:
        call(['pylupdate4', 'puddletag.pro'])
except OSError:
    print 'Error: pylupdate4 is not installed.'
    sys.exit(2)

if verbose:
    print '\nOpen %s in Qt Linguist in order to edit the translation.' % tr.strip()