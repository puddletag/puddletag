# -*- coding: utf-8 -*-
from puddlestuff.constants import SAVEDIR
from puddlestuff.puddleobjects import PuddleConfig
from os.path import join, exists
import os
from PyQt4.QtCore import QObject, SIGNAL

all = ['musicbrainz']
class RetrievalError(Exception):
    pass

cover_pattern = u'%artist% - %album%'

COVERDIR = join(SAVEDIR, 'covers')
cparser = PuddleConfig()
COVERDIR = cparser.get('tagsources', 'coverdir', COVERDIR)
SAVECOVERS = False
status_obj = QObject()

if not exists(COVERDIR):
    os.mkdir(COVERDIR)

def save_cover(info, data, filetype):
    filename = findfunc.tagtofilename(pattern, info, True, filetype)
    save_file(filename, data)

def save_file(filename, data):
    path = join(filename, COVERDIR)
    if exists(path):
        save_file(u'%s0' % filename)
        return
    f = open(filename, 'wb')
    f.write(data)
    f.close()

def set_coverdir(dirpath):
    global COVERDIR
    COVERDIR = dirpath

def set_savecovers(value):
    global SAVECOVERS
    SAVECOVERS = value

def set_status(msg):
    status_obj.emit(SIGNAL('statusChanged'), msg)

def write_log(text):
    status_obj.emit(SIGNAL('logappend'), text)