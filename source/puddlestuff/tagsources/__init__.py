# -*- coding: utf-8 -*-
from puddlestuff.constants import SAVEDIR
from puddlestuff.puddleobjects import PuddleConfig
from os.path import join, exists
import os

all = ['musicbrainz', 'amazon']
class RetrievalError(Exception):
    pass

COVERDIR = join(SAVEDIR, 'covers')
cparser = PuddleConfig()
COVERDIR = cparser.get('tagsources', 'coverdir', COVERDIR)
if not exists(COVERDIR):
    os.mkdir(COVERDIR)

def set_coverdir(dirpath):
    global COVERDIR
    COVERDIR = dirpath
