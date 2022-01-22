import logging
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from importlib import import_module
from os.path import join, exists

from PyQt5.QtCore import QObject, pyqtSignal

from .. import version_string
from ..constants import CONFIGDIR
from ..findfunc import tagtofilename
from ..puddleobjects import PuddleConfig
from ..util import translate


class FoundEncoding(Exception):
    pass


class WebServiceError(EnvironmentError):
    pass


class RetrievalError(WebServiceError):

    def __init__(self, msg, code=0):
        WebServiceError.__init__(self, msg)
        self.code = code


class SubmissionError(WebServiceError):

    def __init__(self, msg, code=0):
        WebServiceError.__init__(self, msg)
        self.code = code


class _SignalObject(QObject):
    statusChanged = pyqtSignal(str, name='statusChanged')
    logappend = pyqtSignal(str, name='logappend')


cparser = PuddleConfig()

COVERDIR = cparser.get('tagsources', 'coverdir', join(CONFIGDIR, 'covers'))
COVER_PATTERN = '%artist% - %album%'
SAVECOVERS = False

mapping = {}
status_obj = _SignalObject()
useragent = "puddletag/" + version_string


def get_encoding(page, decode=False, default=None):
    encoding = None
    match = re.search(b'<\?xml(.+)\?>', page)
    if match:
        enc = re.search('''encoding(?:\s*)=(?:\s*)["'](.+?)['"]''',
                        match.group(), re.I)
        if enc:
            encoding = enc.groups()[0]

    if not encoding and default:
        encoding = default

    return encoding


def find_id(tracks, field):
    if not field:
        return
    for track in tracks:
        if field in track:
            value = track[field]
            if isinstance(value, str):
                return value
            else:
                return value[0]


# From http://stackoverflow.com/questions/4389572 by bobince
def iri_to_uri(iri):
    parts = urllib.parse.urlparse(iri)
    return urllib.parse.urlunparse(
        part.encode('idna') if i == 1
        else part.encode('utf-8')
        for i, part in enumerate(parts)
    ).decode()


def parse_searchstring(text):
    try:
        text = [z.split(';') for z in text.split('|') if z]
        return [(z.strip(), v.strip()) for z, v in text]
    except ValueError:
        raise RetrievalError(
            translate('Tag Sources',
                      '<b>Error parsing artist/album combinations.</b>'))
    return []


def retrieve_cover(url):
    write_log(translate("Tag Sources", 'Retrieving cover: %s') % url)
    cover = urlopen(url)
    return {'__image': [{'data': cover}]}


def save_cover(info, data, filetype):
    filename = tagtofilename(COVER_PATTERN, info, True, filetype)
    save_file(filename, data)


def save_file(filename, data):
    path = join(filename, COVERDIR)
    if exists(path):
        save_file('%s0' % filename)
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
    status_obj.statusChanged.emit(msg)


def get_useragent():
    if useragent:
        return useragent
    else:
        return 'puddetag/' + version_string


def set_useragent(agent):
    global useragent
    useragent = agent


def to_file(data, name):
    if os.path.exists(name):
        return to_file(data, name + '_')

    f = open(name, 'w')
    f.write(data)
    f.close()


def url_encode_non_ascii(b):
    return re.sub('[\x80-\xFF]', lambda c: '%%%02x' % ord(c.group(0)), b)


def urlopen(url, mask=True, code=False):
    try:
        request = urllib.request.Request(url)
        if useragent:
            request.add_header('User-Agent', useragent)
        page = urllib.request.build_opener().open(request)
        if page.code == 403:
            raise RetrievalError(
                translate("Tag Sources", 'HTTPError 403: Forbidden'))
        elif page.code == 404:
            raise RetrievalError(
                translate("Tag Sources", "Page doesn't exist"))
        if code:
            return page.read(), page.code
        else:
            return page.read()
    except urllib.error.URLError as e:
        try:
            msg = '%s (%s)' % (e.reason.strerror, e.reason.errno)
        except AttributeError:
            msg = str(e)

        try:
            raise RetrievalError(msg, e.code)
        except AttributeError:
            msg = e.args[1] if len(e.args) > 1 else e.args[0]
            raise RetrievalError(
                translate("Defaults", "Connection Error: %s ") % msg)
    except socket.error as e:
        msg = '%s (%s)' % (e.strerror, e.code)
        raise RetrievalError(msg)
    except EnvironmentError as e:
        msg = '%s (%s)' % (e.strerror, e.code)
        raise RetrievalError(msg)


def write_log(text):
    status_obj.logappend.emit(text)


class MetaProcessor(HTMLParser):

    def reset(self):
        self.pieces = []
        self.encoding = None
        HTMLParser.reset(self)

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
                encoding = re.search('charset.*=(.+)', text[1][1]).group(1)
                error = FoundEncoding()
                error.encoding = encoding
                raise error


tagsources = []
for source in ('acoust_id', 'amazon', 'amg', 'discogs', 'freedb',
               'musicbrainz'):
    try:
        tagsources.append(getattr(
            import_module('puddlestuff.tagsources.' + source),
            'info'))
    except ImportError as ie:
        logging.debug(f"error loading source '{source}: error={ie}")
