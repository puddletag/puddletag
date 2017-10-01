# -*- coding: utf-8 -*-
import cStringIO
from copy import deepcopy
import gzip
import json
import re
import socket
import time
import urllib2

from puddlestuff.audioinfo import DATA, isempty
from puddlestuff.constants import CHECKBOX, COMBO, TEXT
from puddlestuff.tagsources import (
    find_id, write_log, RetrievalError, iri_to_uri, get_useragent)
from puddlestuff.util import translate

R_ID_DEFAULT = 'discogs_id'
R_ID = R_ID_DEFAULT
MASTER = 'master'
RELEASE = 'release'

SITE_MASTER_URL = 'http://www.discogs.com/master/'
SITE_RELEASE_URL = 'http://www.discogs.com/releases/'
API_RELEASE_URL = 'http://api.discogs.com/releases/'
API_MASTER_URL = 'http://api.discogs.com/masters/'
SITE_URL = 'http://www.discogs.com'

BASE_URL = 'http://api.discogs.com/%s'
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

INVALID_KEYS = [
    'status', 'resource_url', 'tracklist', 'thumb', 'formats', 'artists',
    'extraartists', 'images', 'videos', 'master_id', 'labels', 'companies',
    'series', 'released_formatted', 'identifiers', 'sub_tracks']


class LastTime(object):
    pass

__lasttime = LastTime()
__lasttime.time = time.time()


def convert_dict(d, keys=None):
    if keys is None:
        keys = TRACK_KEYS
    d = deepcopy(d)
    for key in keys:
        if key in d:
            d[keys[key]] = d[key]
            del(d[key])
    return d


def check_values(d):
    ret = {}
    for key, v in d.iteritems():
        if key in INVALID_KEYS or isempty(v):
            continue
        if hasattr(v, '__iter__') and hasattr(v, 'items'):
            continue
        elif not hasattr(v, '__iter__'):
            v = unicode(v)
        elif isinstance(v, str):
            v = v.decode('utf8')

        ret[key] = v

    return ret


def keyword_search(keywords):
    write_log(
        translate("Discogs",
                  'Retrieving search results for keywords: %s') % keywords)
    keywords = re.sub('(\s+)', u'+', keywords)
    url = SEARCH_URL % keywords
    text = urlopen(url)
    return parse_search_json(json.loads(text))


def parse_tracklist(tlist):
    tracks = []
    for t in tlist:
        if not t.get(u'duration') and not t.get('position'):
            continue
        title = t['title']
        people = []
        featuring = []
        for person in t.get('extraartists', {}):
            name = person['name']
            if person.get('join'):
                title = title + u' ' + person.get('join') + u' ' + name
            elif person.get('role', u'') == u'Featuring':
                featuring.append(name)
            else:
                people.append(u"%s:%s" % (person['name'], person['role']))

        if featuring:
            title = title + u' featuring ' + u', '.join(featuring)

        info = convert_dict(t)
        artist = []
        a_len = len(t.get('artists', []))
        for i, a in enumerate(t.get(u'artists', [])):
            if a_len > 1 and a.get(u'join'):
                artist.append(u'%s %s ' % (a[u'name'], a[u'join']))
            else:
                if i < a_len - 1:
                    artist.append(u'%s & ' % a[u'name'])
                else:
                    artist.append(a[u'name'])
        info['artist'] = u''.join(artist).strip()
        info['title'] = title

        if people:
            info['involvedpeople_track'] = u';'.join(people)
        tracks.append(check_values(info))
    return tracks


def parse_album_json(data):
    """Parses the retrieved json for an album and get's the track listing."""

    info = {}

    formats = []
    for fmt in data.get('formats', []):
        desc = fmt.get('descriptions', fmt.get('name', u''))
        if not desc:
            continue
        if isinstance(desc, basestring):
            formats.append(desc)
        else:
            formats.extend(desc)

    if formats:
        info['format'] = list(set(formats))
    info['artist'] = [z['name'] for z in data.get('artists', [])]
    info['artist'] = u" & ".join(filter(None, info['artist']))
    info['involvedpeople_album'] = \
        u':'.join(u'%s;%s' % (z['name'], z['role'])
                  for z in data.get('extraartists', []))
    info['label'] = [z['name'] for z in data.get('labels', [])]
    info['catno'] = filter(None,
                           (z.get('catno') for z in data.get('labels', [])))

    info['companies'] = u';'.join(
        u'%s %s' % (z['entity_type_name'], z['name'])
        for z in data.get('companies', []))
    info['album'] = data['title']
    cleaned_data = convert_dict(check_values(data), ALBUM_KEYS)
    cleaned_data.update(check_values(convert_dict(info, ALBUM_KEYS)))
    info = cleaned_data

    if 'images' in data:
        images = \
            [(z.get('uri', ''), z.get('uri150', ''))
             for z in data['images'] if 'uri' in z or 'uri150' in z]
        info['#cover-url'] = images

    return info, parse_tracklist(data['tracklist'])


def parse_search_json(data):
    """Parses the xml retrieved after entering a search query. Returns a
    list of the albums found.
    """

    results = data.get('results', []) + data.get('exactresults', [])

    if not results:
        return []

    albums = []

    for result in results:
        info = result.copy()
        try:
            artist, album = result['title'].split(u' - ')
        except ValueError:
            album = result['title']
            artist = u''

        info = convert_dict(info, ALBUM_KEYS)

        info['artist'] = artist
        info['album'] = album

        info['discogs_id'] = info['#r_id']

        info['#extrainfo'] = (
            translate('Discogs', '%s at Discogs.com') % info['album'],
            SITE_URL + info['discogs_uri'])

        albums.append(check_values(info))

    return albums


def retrieve_album(info, image=LARGEIMAGE, rls_type=None):
    """Retrieves album from the information in info.
    image must be either one of image_types or None.
    If None, no image is retrieved."""
    if isinstance(info, (int, long)):
        r_id = unicode(info)
        info = {}
        write_log(
            translate("Discogs", 'Retrieving using Release ID: %s') % r_id)
        rls_type = u'release'
    elif isinstance(info, basestring):
        r_id = info
        info = {}
        write_log(
            translate("Discogs", 'Retrieving using Release ID: %s') % r_id)
        rls_type = u'release'
    else:
        if rls_type is None and '#release_type' in info:
            rls_type = info['#release_type']
        r_id = info['#r_id']
        write_log(
            translate("Discogs", 'Retrieving album %s') % (info['album']))

    site_url = SITE_MASTER_URL if rls_type == MASTER else SITE_RELEASE_URL
    site_url += r_id.encode('utf8')

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
                        'Discogs', u'Error retrieving image:') + unicode(e))
            else:
                write_log(
                    translate("Discogs", 'Retrieving cover: %s') % small)
                try:
                    data.append({DATA: urlopen(small)})
                except RetrievalError as e:
                    write_log(translate(
                        'Discogs', u'Error retrieving image:') + unicode(e))
        if data:
            info.update({'__image': data})

    try:
        info['#extrainfo'] = translate(
            'Discogs', '%s at Discogs.com') % info['album'], site_url
    except KeyError:
        pass
    return info, ret[1]


def search(artist=None, album=None):
    if artist and album:
        keywords = u' '.join([artist, album])
    elif artist:
        keywords = artist
    else:
        keywords = album
    return keyword_search(keywords)


def urlopen(url):
    url = iri_to_uri(url)
    request = urllib2.Request(url)
    request.add_header('Accept-Encoding', 'gzip')
    request.add_header('User-Agent', get_useragent())

    if time.time() - __lasttime.time < 1:
        time.sleep(1)
    __lasttime.time = time.time()

    try:
        data = urllib2.urlopen(request).read()
    except urllib2.URLError as e:
        try:
            msg = u'%s (%s)' % (e.reason.strerror, e.reason.errno)
        except AttributeError:
            msg = unicode(e)
        raise RetrievalError(msg)
    except socket.error as e:
        msg = u'%s (%s)' % (e.strerror, e.errno)
        raise RetrievalError(msg)
    except EnvironmentError, e:
        msg = u'%s (%s)' % (e.strerror, e.errno)
        raise RetrievalError(msg)

    try:
        data = gzip.GzipFile(fileobj=cStringIO.StringIO(data)).read()
    except IOError:
        "Gzipped data not returned."

    return data


class Discogs(object):
    name = 'Discogs.com'
    group_by = [u'album', u'artist']
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
        except Exception, e:
            raise RetrievalError(unicode(e))

    def search(self, album, artists):

        if len(artists) > 1:
            artist = u'Various Artists'
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
    print k.keyword_search(":r 911637")
