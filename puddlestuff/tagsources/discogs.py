import gzip
import json
import re
import socket
import time
import numbers
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from io import StringIO

from puddlestuff.audioinfo import DATA, isempty
from puddlestuff.constants import CHECKBOX, COMBO, TEXT
from puddlestuff.tagsources import (
    find_id, write_log, RetrievalError, iri_to_uri, get_useragent)
from puddlestuff.util import translate

R_ID_DEFAULT = 'discogs_id'
R_ID = R_ID_DEFAULT
MASTER = 'master'
RELEASE = 'release'

SITE_MASTER_URL = 'https://www.discogs.com/master/'
SITE_RELEASE_URL = 'https://www.discogs.com/releases/'
API_RELEASE_URL = 'https://api.discogs.com/releases/'
API_MASTER_URL = 'https://api.discogs.com/masters/'
SITE_URL = 'https://www.discogs.com'

BASE_URL = 'https://api.discogs.com/%s'
SEARCH_URL = BASE_URL % 'database/search?type=release&q=%s&per_page=100'
RELEASE_URL = BASE_URL % 'releases/%s'
MASTER_URL = BASE_URL % 'masters/%s'

SMALLIMAGE = '#smallimage'
LARGEIMAGE = '#largeimage'
IMAGE_TYPES = [SMALLIMAGE, LARGEIMAGE]

IMAGEKEYS = {
    'SmallImage': SMALLIMAGE,
    'LargeImage': LARGEIMAGE}

# The release's own values that are kept, by the field each becomes.
ALBUM_KEYS = {
    'country': 'country',
    'genres': 'genre',
    'id': '#r_id',
    'master_url': 'discogs_master_url',
    'notes': 'discogs_notes',
    'released': 'year',
    'resource_url': '#discogs_url',
    'styles': 'style',
    'thumb': '#cover_url',
    'title': 'album',
    'type': '#release_type',
    'uri': 'discogs_uri',
    'year': 'year'}

TRACK_KEYS = {
    'position': 'track',
    'duration': '__length',
    'notes': 'discogs_notes'}

RELEASE_PROPERTIES_TO_IGNORE = [
    'status', 'resource_url', 'tracklist', 'thumb', 'formats', 'artists',
    'extraartists', 'images', 'videos', 'master_id', 'labels', 'companies',
    'series', 'released_formatted', 'identifiers', 'sub_tracks',
    'type_']

_last_request = None


def _wait():
    """Keeps the requests to Discogs a second apart."""
    global _last_request
    if _last_request is not None:
        wait = _last_request + 1 - time.monotonic()
        if wait > 0:
            time.sleep(wait)
    _last_request = time.monotonic()


def convert_dict(d, keys=None):
    if keys is None:
        keys = TRACK_KEYS
    d = deepcopy(d)
    for key in keys:
        if key in d:
            d[keys[key]] = d[key]
            del (d[key])
    return d


def capture_dict_values(d):
    ret = {}
    for key, v in d.items():
        if key in RELEASE_PROPERTIES_TO_IGNORE or isempty(v) or isinstance(v, dict):
            continue
        elif isinstance(v, bytes):
            ret[key] = v.decode('utf8')
        elif isinstance(v, numbers.Number):
            ret[key] = str(v)
        else:
            ret[key] = v

    return ret


def parse_track(t, title_prefix=''):
    """The fields of one track of Discogs' tracklist."""
    title = title_prefix + t['title']
    people = []
    featuring = []
    for person in t.get('extraartists', {}):
        name = person['name']
        if person.get('join'):
            title = title + ' ' + person.get('join') + ' ' + name
        elif person.get('role', '') == 'Featuring':
            featuring.append(name)
        else:
            people.append("%s:%s" % (person['name'], person['role']))

    if featuring:
        title = title + ' featuring ' + ', '.join(featuring)

    info = convert_dict(t)
    artist = []
    a_len = len(t.get('artists', []))
    for i, a in enumerate(t.get('artists', [])):
        if a_len > 1 and a.get('join'):
            space = '' if a['join'] == ',' else ' '
            artist.append('%s%s%s ' % (a['name'], space, a['join']))
        else:
            if i < a_len - 1:
                artist.append('%s & ' % a['name'])
            else:
                artist.append(a['name'])
    info['artist'] = ''.join(artist).strip()
    info['title'] = title

    if people:
        info['involvedpeople_track'] = ';'.join(people)

    match = re.fullmatch(r'(\d+)-(\d+)', info.get('track', ''))
    if match:
        info['discnumber'], info['track'] = match.groups()
    return capture_dict_values(info)


def parse_tracklist(tlist):
    tracks = []
    for t in tlist:
        if t.get('type_') == 'heading' or (
                'type_' not in t and not t.get('duration') and not t.get('position')):
            continue
        if t.get('type_') == 'index' and t.get('sub_tracks'):
            # The index is a title over its movements, which are the tracks.
            tracks.extend(parse_track(sub, t['title'] + ': ') for sub in t['sub_tracks'])
        else:
            tracks.append(parse_track(t))
    return tracks


def parse_album_json(data):
    """Parses the retrieved json for an album and get's the track listing."""

    info = {}

    formats = []
    media = []
    for fmt in data.get('formats', []):
        if fmt.get('name'):
            media.append(fmt['name'])
        desc = fmt.get('descriptions', fmt.get('name', ''))
        if not desc:
            continue
        if isinstance(desc, str):
            formats.append(desc)
        else:
            formats.extend(desc)

    if formats:
        info['format'] = list(dict.fromkeys(formats))
    if media:
        info['discogs_format'] = list(dict.fromkeys(media))
    info['artist'] = [z['name'] for z in data.get('artists', [])]
    info['artist'] = " & ".join([_f for _f in info['artist'] if _f])
    info['involvedpeople_album'] = \
        ';'.join('%s:%s' % (z['name'], z['role'])
                 for z in data.get('extraartists', []))
    info['label'] = [z['name'] for z in data.get('labels', [])]
    info['catno'] = list(dict.fromkeys(
        _f for _f in (z.get('catno') for z in data.get('labels', [])) if _f))
    info['album'] = data['title']

    # Discogs writes what it doesn't know as 00, or 0 for a year.
    kept = capture_dict_values(data)
    if 'released' in kept:
        kept['released'] = re.sub(r'(-00)+$', '', kept['released'])
        kept.pop('year', None)
    elif kept.get('year') == '0':
        del kept['year']
    cleaned_data = {
        ALBUM_KEYS[key]: value for key, value in kept.items() if key in ALBUM_KEYS}
    cleaned_data.update(capture_dict_values(info))
    info = cleaned_data

    if 'images' in data:
        images = \
            [(z.get('uri', ''), z.get('uri150', ''))
             for z in data['images'] if 'uri' in z or 'uri150' in z]
        info['#cover-url'] = images

    tracks = parse_tracklist(data['tracklist'])
    discs = {t['discnumber'] for t in tracks if 'discnumber' in t}
    if discs:
        info['discs'] = str(len(discs))
    return info, tracks

  
def retrieve_album(info, image=LARGEIMAGE, rls_type=None):
    """Retrieves album from the information in info.
    image must be either one of image_types or None.
    If None, no image is retrieved."""
    if isinstance(info, int):
        r_id = str(info)
        info = {}
        write_log(
            translate('Discogs', "Retrieving using Release ID: {}").format(r_id))
        rls_type = 'release'
    elif isinstance(info, str):
        r_id = info
        info = {}
        write_log(
            translate('Discogs', "Retrieving using Release ID: {}").format(r_id))
        rls_type = 'release'
    else:
        if rls_type is None and '#release_type' in info:
            rls_type = info['#release_type']
        r_id = info['#r_id']
        write_log(
            translate('Discogs', "Retrieving album {}").format(info['album']))

    site_url = SITE_MASTER_URL if rls_type == MASTER else SITE_RELEASE_URL
    site_url += r_id

    url = MASTER_URL % r_id if rls_type == MASTER else RELEASE_URL % r_id

    x = urlopen(url)
    ret = parse_album_json(json.loads(x))

    info = deepcopy(info)
    info.update(ret[0])
    if rls_type != MASTER:
        info['discogs_r_id'] = str(r_id)

    if image in IMAGE_TYPES and '#cover-url' in info:
        data = []
        for large, small in info['#cover-url']:
            address = (large or small) if image == LARGEIMAGE else (small or large)
            if not address:
                continue
            write_log(
                translate('Discogs', "Retrieving cover: {}").format(address))
            try:
                data.append({DATA: urlopen(address)})
            except RetrievalError as e:
                write_log(translate(
                    'Discogs', 'Error retrieving image:') + str(e))
        if data:
            info.update({'__image': data})

    try:
        info['#extrainfo'] = translate(
            'Discogs', "{} at Discogs.com").format(info['album']), site_url
    except KeyError:
        pass
    return info, ret[1]


def urlopen(url):
    url = iri_to_uri(url)
    request = urllib.request.Request(url)
    request.add_header('Accept-Encoding', 'gzip')
    request.add_header('User-Agent', get_useragent())

    _wait()

    try:
        data = urllib.request.urlopen(request).read()
    except urllib.error.URLError as e:
        try:
            msg = '%s (%s)' % (e.reason.strerror, e.reason.errno)
        except AttributeError:
            msg = str(e)
        raise RetrievalError(msg)
    except socket.error as e:
        msg = '%s (%s)' % (e.strerror, e.errno)
        raise RetrievalError(msg)
    except EnvironmentError as e:
        msg = '%s (%s)' % (e.strerror, e.errno)
        raise RetrievalError(msg)

    try:
        data = gzip.decompress(data)
    except IOError:
        "Gzipped data not returned."

    return data


class Discogs(object):
    name = 'Discogs.com'
    group_by = ['album', 'artist']
    tooltip = translate("Discogs", """<p><b>Discogs only support searching by release id</b></p>
        <p>Enter the release id Eg. "1257896" to search.</p>""")

    def __init__(self):
        super(Discogs, self).__init__()
        self._getcover = True
        self.covertype = LARGEIMAGE

        self.preferences = [
            [translate('Discogs', 'Retrieve Cover'), CHECKBOX, True],
            [translate("Discogs", 'Cover size to retrieve'), COMBO,
             [[translate("Discogs", 'Small'),
               translate("Discogs", 'Large')], 1]],
            [translate("Discogs", 'Field to use for discogs_id'), TEXT, R_ID],
            [translate("Discogs", 'API Key (Stored as plain-text.'
                                  'Leave empty to use default.)'), TEXT, ''],
        ]

    def keyword_search(self, text):

        text = text.strip()
        if text.startswith(':r'):
            text = text[len(':r'):].strip()

        try:
            r_id = int(text)
        except (TypeError, ValueError):
            raise RetrievalError(translate(
                "Discogs", 'Discogs release id should be an integer.'))

        try:
            return [self.retrieve(r_id)]
        except Exception as e:
            raise RetrievalError(str(e))

    def search(self, album, artists):

        if hasattr(artists, 'values'):
            write_log(
                translate("Discogs", 'Checking tracks for Discogs Album ID.'))
            tracks = []
            [tracks.extend(z) for z in artists.values()]
            album_id = find_id(tracks, R_ID) or find_id(tracks, 'discogs_r_id')
            if not album_id:
                write_log(
                    translate("Discogs", 'No Discogs ID found in tracks.'))
            else:
                write_log(
                    translate('Discogs', "Found Discogs ID: {}").format(album_id))
                return [self.retrieve(album_id)]

        return []

    def retrieve(self, info):
        if self._getcover:
            return retrieve_album(info, self.covertype)
        else:
            return retrieve_album(info, None)

    def applyPrefs(self, args):
        self._getcover = args[0]
        self.covertype = IMAGE_TYPES[args[1]]
        if not self._getcover:
            self.covertype = None
        global R_ID
        if args[2]:
            R_ID = args[2]
        else:
            R_ID = R_ID_DEFAULT


info = Discogs
