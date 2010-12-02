# -*- coding: utf-8 -*-
from puddlestuff.constants import SAVEDIR
from puddlestuff.puddleobjects import PuddleConfig
from os.path import join, exists
import os, re
from PyQt4.QtCore import QObject, SIGNAL
from collections import defaultdict
import urllib2, socket, urllib
from sgmllib import SGMLParser

all = ['musicbrainz', 'discogs', 'amazon']

class FoundEncoding(Exception): pass

class RetrievalError(Exception):
    pass

cover_pattern = u'%artist% - %album%'

COVERDIR = join(SAVEDIR, 'covers')
cparser = PuddleConfig()
COVERDIR = cparser.get('tagsources', 'coverdir', COVERDIR)
SAVECOVERS = False
status_obj = QObject()

mapping = {}

def get_encoding(page, decode=False):
    parser = MetaProcessor()
    encoding = None
    try:
        parser.feed(page)
    except FoundEncoding, e:
        encoding = e.encoding.strip()

    if decode:
        return encoding, page.decode(encoding) if encoding else None
    else:
        return encoding

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
        text = [z.split(u';') for z in text.split(u'|') if z]
        return [(z.strip(), v.strip()) for z, v in text]
    except ValueError:
        raise RetrievalError('<b>Error parsing artist/album combinations.</b>')
    return []

def set_useragent(agent):
    class MyOpener(urllib.FancyURLopener):
        version = agent
    global _urlopen
    _urlopen = MyOpener().open

_urlopen = urllib2.urlopen
def urlopen(url, mask=True):
    if not mask:
        return _urlopen(url).read()
    try:
        return _urlopen(url).read()
    except urllib2.URLError, e:
        msg = u'%s (%s)' % (e.reason.strerror, e.reason.errno)
        raise RetrievalError(msg)
    except socket.error:
        msg = u'%s (%s)' % (e.strerror, e.errno)
        raise RetrievalError(msg)
    except EnvironmentError, e:
        msg = u'%s (%s)' % (e.strerror, e.errno)
        raise RetrievalError(msg)


class MetaProcessor(SGMLParser):
    def reset(self):
        self.pieces = []
        self.encoding = None
        SGMLParser.reset(self)

    def start_meta(self, text):
        if text[0] == ('http-equiv', 'content-type'):
            if text[1][0] == 'content':
                encoding = re.search('charset.*=(.+)',
                    text[1][1]).group(1)
                error = FoundEncoding()
                error.encoding = encoding
                raise error

import musicbrainz, amazon, freedb, discogs
try:
    import amg
    tagsources = [z.info for z in [musicbrainz, amazon, freedb, amg, discogs]]
except ImportError:
    allmusic = None
    tagsources = [z.info for z in [musicbrainz, amazon, freedb, discogs]]