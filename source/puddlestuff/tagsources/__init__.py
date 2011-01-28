# -*- coding: utf-8 -*-
from puddlestuff.constants import SAVEDIR
from puddlestuff.puddleobjects import PuddleConfig
from puddlestuff.util import translate
from os.path import join, exists
import os, re, pdb
from PyQt4.QtCore import QObject, SIGNAL
from collections import defaultdict
import urllib2, socket, urllib
from sgmllib import SGMLParser
import urlparse

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
user_agent = None

mapping = {}

def get_encoding(page, decode=False, default=None):
    encoding = None
    match = re.search('<\?xml(.+)\?>', page)
    if match:
        enc = re.search('''encoding(?:\s*)=(?:\s*)["'](.+)['"]''',
            match.group(), re.I)
        if enc:
            encoding = enc.groups()[0]

    if not encoding:
        parser = MetaProcessor()
        try:
            parser.feed(page)
        except FoundEncoding, e:
            encoding = e.encoding.strip()

    if not encoding and default:
        encoding = default

    if decode:
        return encoding, page.decode(encoding, 'replace') if encoding else page
    else:
        return encoding

#From http://stackoverflow.com/questions/4389572 by bobince
def iri_to_uri(iri):
    parts= urlparse.urlparse(iri)
    return urlparse.urlunparse(
        part.encode('idna') if parti==1 else url_encode_non_ascii(part.encode('utf-8'))
        for parti, part in enumerate(parts)
    )

def parse_searchstring(text):
    try:
        text = [z.split(u';') for z in text.split(u'|') if z]
        return [(z.strip(), v.strip()) for z, v in text]
    except ValueError:
        raise RetrievalError(translate('Tag Sources',
            '<b>Error parsing artist/album combinations.</b>'))
    return []

def retrieve_cover(url):
    write_log(translate("Tag Sources", 'Retrieving cover: %s') % url)
    cover = urlopen(url)
    return {'__image': [{'data': cover}]}

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

def set_mapping(m):
    global mapping

    mapping.clear()
    mapping.update(m)

def set_status(msg):
    status_obj.emit(SIGNAL('statusChanged'), msg)

def set_useragent(agent):
    global user_agent
    user_agent = agent

def to_file(data, name):
    if os.path.exists(name):
        return to_file(data, name + '_')

    f = open(name, 'w')
    f.write(data)
    f.close()

def url_encode_non_ascii(b):
    return re.sub('[\x80-\xFF]', lambda c: '%%%02x' % ord(c.group(0)), b)

def urlopen(url, mask=True):
    try:
        request = urllib2.Request(url)
        if user_agent:
            request.add_header('User-Agent', user_agent)
        page = urllib2.build_opener().open(request)
        if page.code == 403:
            raise RetrievalError(translate("Tag Sources", 'HTTPError 403: Forbidden'))
        elif page.code == 404:
            raise RetrievalError(translate("Tag Sources", "Page doesn't exist"))
        return page.read()
    except urllib2.URLError, e:
        try:
            msg = u'%s (%s)' % (e.reason.strerror, e.reason.errno)
        except AttributeError:
            msg = unicode(e)
        raise RetrievalError(msg)
    except socket.error:
        msg = u'%s (%s)' % (e.strerror, e.errno)
        raise RetrievalError(msg)
    except EnvironmentError, e:
        msg = u'%s (%s)' % (e.strerror, e.errno)
        raise RetrievalError(msg)

def write_log(text):
    status_obj.emit(SIGNAL('logappend'), text)

class MetaProcessor(SGMLParser):
    def reset(self):
        self.pieces = []
        self.encoding = None
        SGMLParser.reset(self)

    def start_meta(self, text):
        text = [tuple([x.lower() for x in z]) for z in text]
        if text[0] == ('http-equiv', 'content-type'):
            d = dict(text)
            if 'charset' in d:
                encoding = d['charset']
                error = FoundEncoding()
                error.encoding = encoding
                raise error
            if text[1][0] == 'content':
                encoding = re.search('charset.*=(.+)',
                    text[1][1]).group(1)
                error = FoundEncoding()
                error.encoding = encoding
                raise error

import amazon, freedb, discogs
tagsources = [z.info for z in (amazon, freedb, discogs)]

try:
    import musicbrainz
    tagsources.append(musicbrainz.info)
except ImportError:
    print translate("Tag Sources", "python-musicbrainz2 wasn't found.")


try:
    import amg
    tagsources.append(amg.info)
except ImportError:
    allmusic = None