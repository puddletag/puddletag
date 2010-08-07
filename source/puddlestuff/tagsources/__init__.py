# -*- coding: utf-8 -*-
from puddlestuff.constants import SAVEDIR
from puddlestuff.puddleobjects import PuddleConfig
from os.path import join, exists
import os
from PyQt4.QtCore import QObject, SIGNAL
from collections import defaultdict
import urllib2, socket

all = ['musicbrainz']

class RetrievalError(Exception):
    pass

cover_pattern = u'%artist% - %album%'

COVERDIR = join(SAVEDIR, 'covers')
cparser = PuddleConfig()
COVERDIR = cparser.get('tagsources', 'coverdir', COVERDIR)
SAVECOVERS = False
status_obj = QObject()

mapping = {}

def set_mapping(m):
    global mapping

    mapping.clear()
    mapping.update(m)

if not exists(COVERDIR):
    try:
        os.mkdir(COVERDIR)
    except EnvironmentError:
        pass

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
    
def parse_searchstring(text):
    try:
        text = [z.split(';') for z in text.split(u'|') if z]
        return [(z.strip(), v.strip()) for z, v in text]
    except ValueError:
        raise RetrievalError('<b>Error parsing artist/album combinations.</b>')
    return []

def urlopen(url):
    try:
        return urllib2.urlopen(url).read()
    except urllib2.URLError, e:
        msg = u'%s (%s)' % (e.reason.strerror, e.reason.errno)
        raise RetrievalError(msg)
    except socket.error:
        msg = u'%s (%s)' % (e.strerror, e.errno)
        raise RetrievalError(msg)

import musicbrainz, amazon, freedb
try:
    import amg
    tagsources = [z.info for z in [musicbrainz, amazon, freedb, amg]]
except ImportError:
    allmusic = None
    tagsources = [z.info for z in [musicbrainz, amazon, freedb]]