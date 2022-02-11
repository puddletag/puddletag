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

ALBUM_KEYS = {
    'title': 'album',
    'uri': 'discogs_uri',
    'summary': 'discogs_summary',
    'released': 'year',
    'notes': 'discogs_notes',
    'id': '#r_id',
    'thumb': '#cover_url',
    'resource_url': '#discogs_url',
    'type': '#release_type',
    'master_url': "discogs_master_url"}

TRACK_KEYS = {
    'position': 'track',
    'duration': '__length',
    'notes': 'discogs_notes'}

RELEASE_PROPERTIES_TO_IGNORE = [
    'status', 'resource_url', 'tracklist', 'thumb', 'formats', 'artists',
    'extraartists', 'images', 'videos', 'master_id', 'labels', 'companies',
    'series', 'released_formatted', 'identifiers', 'sub_tracks']

__minimum_request_separation = 1  # second - no more than one request sent to discogs in this time frame
__reference_time = 0  # A reference time. The initial value ensure first request goes ahead


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


def parse_tracklist(tlist):
    tracks = []
    for t in tlist:
        if not t.get('duration') and not t.get('position'):
            continue
        title = t['title']
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
                artist.append('%s %s ' % (a['name'], a['join']))
            else:
                if i < a_len - 1:
                    artist.append('%s & ' % a['name'])
                else:
                    artist.append(a['name'])
        info['artist'] = ''.join(artist).strip()
        info['title'] = title

        if people:
            info['involvedpeople_track'] = ';'.join(people)
        tracks.append(capture_dict_values(info))
    return tracks


def parse_album_json(data):
    """Parses the retrieved json for an album and get's the track listing."""

    info = {}

    formats = []
    for fmt in data.get('formats', []):
        desc = fmt.get('descriptions', fmt.get('name', ''))
        if not desc:
            continue
        if isinstance(desc, str):
            formats.append(desc)
        else:
            formats.extend(desc)

    if formats:
        info['format'] = list(set(formats))
    info['artist'] = [z['name'] for z in data.get('artists', [])]
    info['artist'] = " & ".join([_f for _f in info['artist'] if _f])
    info['involvedpeople_album'] = \
        ':'.join('%s;%s' % (z['name'], z['role'])
                 for z in data.get('extraartists', []))
    info['label'] = [z['name'] for z in data.get('labels', [])]
    info['catno'] = [_f for _f in (z.get('catno') for z in data.get('labels', [])) if _f]

    info['companies'] = ';'.join(
        '%s %s' % (z['entity_type_name'], z['name'])
        for z in data.get('companies', []))
    info['album'] = data['title']
    cleaned_data = convert_dict(capture_dict_values(data), ALBUM_KEYS)
    cleaned_data.update(capture_dict_values(convert_dict(info, ALBUM_KEYS)))
    info = cleaned_data

    if 'images' in data:
        images = \
            [(z.get('uri', ''), z.get('uri150', ''))
             for z in data['images'] if 'uri' in z or 'uri150' in z]
        info['#cover-url'] = images

    return info, parse_tracklist(data['tracklist'])

  
def retrieve_album(info, image=LARGEIMAGE, rls_type=None):
    """Retrieves album from the information in info.
    image must be either one of image_types or None.
    If None, no image is retrieved."""
    if isinstance(info, int):
        r_id = str(info)
        info = {}
        write_log(
            translate("Discogs", 'Retrieving using Release ID: %s') % r_id)
        rls_type = 'release'
    elif isinstance(info, str):
        r_id = info
        info = {}
        write_log(
            translate("Discogs", 'Retrieving using Release ID: %s') % r_id)
        rls_type = 'release'
    else:
        if rls_type is None and '#release_type' in info:
            rls_type = info['#release_type']
        r_id = info['#r_id']
        write_log(
            translate("Discogs", 'Retrieving album %s') % (info['album']))

    site_url = SITE_MASTER_URL if rls_type == MASTER else SITE_RELEASE_URL
    site_url += r_id

    url = MASTER_URL % r_id if rls_type == MASTER else RELEASE_URL % r_id

    x = urlopen(url)
    ret = parse_album_json(json.loads(x))

    info = deepcopy(info)
    info.update(ret[0])

    if image in IMAGE_TYPES and '#cover-url' in info:
        data = []
        for large, small in info['#cover-url']:
            if image == LARGEIMAGE and large:
                write_log(
                    translate("Discogs", 'Retrieving cover: %s') % large)
                try:
                    data.append({DATA: urlopen(large)})
                except RetrievalError as e:
                    write_log(translate(
                        'Discogs', 'Error retrieving image:') + str(e))
            else:
                write_log(
                    translate("Discogs", 'Retrieving cover: %s') % small)
                try:
                    data.append({DATA: urlopen(small)})
                except RetrievalError as e:
                    write_log(translate(
                        'Discogs', 'Error retrieving image:') + str(e))
        if data:
            info.update({'__image': data})

    try:
        info['#extrainfo'] = translate(
            'Discogs', '%s at Discogs.com') % info['album'], site_url
    except KeyError:
        pass
    return info, ret[1]


def urlopen(url):
    url = iri_to_uri(url)
    request = urllib.request.Request(url)
    request.add_header('Accept-Encoding', 'gzip')
    request.add_header('User-Agent', get_useragent())

    while (time.time() - __reference_time) < __minimum_request_separation:
        time.sleep(__minimum_request_separation)
    __reference_time = time.time()

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
        self.covertype = 1

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

        try:
            r_id = int(text.strip())
        except (TypeError, ValueError):
            raise RetrievalError(translate(
                "Discogs", 'Discogs release id should be an integer.'))

        try:
            return [self.retrieve(r_id)]
        except Exception as e:
            raise RetrievalError(str(e))

    def search(self, album, artists):

        if len(artists) > 1:
            artist = 'Various Artists'
        else:
            artist = [z for z in artists][0]

        if hasattr(artists, 'values'):
            write_log(
                translate("Discogs", 'Checking tracks for Discogs Album ID.'))
            tracks = []
            [tracks.extend(z) for z in artists.values()]
            album_id = find_id(tracks, R_ID)
            if not album_id:
                write_log(
                    translate("Discogs", 'No Discogs ID found in tracks.'))
            else:
                write_log(
                    translate("Discogs", 'Found Discogs ID: %s') % album_id)
                return [self.retrieve(album_id)]

        return []

    def retrieve(self, info):
        if False and self._getcover:  # retrieving images is broken by Discogs
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

if __name__ == '__main__':
    k = Discogs()
    print(k.keyword_search(":r 911637"))
