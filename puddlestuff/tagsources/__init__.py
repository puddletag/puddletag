import http.client
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from importlib import import_module

from PyQt6.QtCore import QObject, pyqtSignal

from .. import version_string
from ..util import translate


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


status_obj = _SignalObject()
# MusicBrainz asks for "Application name/<version> ( contact-url )".
DEFAULT_USERAGENT = ('puddletag/' + version_string +
                     ' ( https://github.com/puddletag/puddletag )')
useragent = DEFAULT_USERAGENT
# Seconds a request waits for the server before it gives up.
TIMEOUT = 30


def get_encoding(page, decode=False, default=None):
    encoding = None
    match = re.search(r'<\?xml(.+?)\?>', page, re.S)
    if match:
        enc = re.search(r'''encoding(?:\s*)=(?:\s*)["'](.+?)['"]''',
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
        value = track.get(field)
        if isinstance(value, str):
            value = [value]
        if value and value[0]:
            return value[0]


def iri_to_uri(iri):
    """The address as a URI (RFC 3987, 3.1): the host in IDNA; elsewhere
    spaces, control characters and every non-ASCII character as their UTF-8
    bytes, percent-encoded."""
    parts = urllib.parse.urlsplit(iri)
    netloc = parts.netloc.encode('idna').decode('ascii')
    path, query, fragment = (
        re.sub('[^\x21-\x7e]+', lambda m: urllib.parse.quote(m.group()), part)
        for part in (parts.path, parts.query, parts.fragment))
    return urllib.parse.urlunsplit((parts.scheme, netloc, path, query, fragment))


def parse_searchstring(text):
    try:
        text = [z.split(';') for z in text.split('|') if z]
        return [(z.strip(), v.strip()) for z, v in text]
    except ValueError:
        raise RetrievalError(
            translate('Tag Sources',
                      '<b>Error parsing artist/album combinations.</b>'))


def retrieve_cover(url):
    write_log(translate('Tag Sources', "Retrieving cover: {}").format(url))
    cover = urlopen(url)
    return {'__image': [{'data': cover}]}


def set_status(msg):
    status_obj.statusChanged.emit(msg)


def get_useragent():
    return useragent or DEFAULT_USERAGENT


def set_useragent(agent):
    global useragent
    # Preferences saves the default of the day, so an older version's is the default too.
    if re.fullmatch(r'puddletag/\S+( \( \S+ \))?', agent):
        agent = DEFAULT_USERAGENT
    useragent = agent


def urlopen(url, mask=True, code=False, headers=None):
    request = urllib.request.Request(iri_to_uri(url))
    request.add_header('User-Agent', get_useragent())
    for name, value in (headers or {}).items():
        request.add_header(name, value)
    try:
        page = urllib.request.build_opener().open(request, timeout=TIMEOUT)
        data = page.read()
    except urllib.error.HTTPError as e:
        raise RetrievalError(str(e), e.code)
    except urllib.error.URLError as e:
        raise RetrievalError(
            translate('Defaults', "Connection Error: {}").format(e.reason))
    except (OSError, http.client.HTTPException) as e:
        raise RetrievalError(
            translate('Defaults', "Connection Error: {}").format(e))
    return (data, page.code) if code else data


def write_log(text):
    status_obj.logappend.emit(text)


tagsources = []
for source in ('acoust_id', 'discogs', 'freedb', 'musicbrainz'):
    try:
        tagsources.append(getattr(
            import_module('puddlestuff.tagsources.' + source),
            'info'))
    except ImportError as ie:
        logging.debug(f"error loading source '{source}: error={ie}")
