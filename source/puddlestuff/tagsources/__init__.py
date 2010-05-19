# -*- coding: utf-8 -*-
from puddlestuff.constants import SAVEDIR
from puddlestuff.puddleobjects import PuddleConfig
from os.path import join, exists
import os
from PyQt4.QtCore import QObject, SIGNAL

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

status_obj = QObject()

def set_status(msg):
    status_obj.emit(SIGNAL('statusChanged'), msg)

def write_log(text):
    status_obj.emit(SIGNAL('logappend'), text)