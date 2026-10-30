import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from itertools import chain
from xml.sax.saxutils import escape

from xml.dom import minidom, Node

from puddlestuff.audioinfo import IMAGETYPES, get_mime, strlength
from puddlestuff.constants import CHECKBOX, COMBO
from puddlestuff.tagsources import (find_id, write_log, RetrievalError,
                          urlopen, parse_searchstring)
from puddlestuff.util import isempty, translate

SERVER = 'http://musicbrainz.org/ws/2/'
COVER_SERVER = 'http://coverartarchive.org/'

_last_request = None
_request_lock = threading.Lock()

TEXT_NODE = Node.TEXT_NODE

ARTISTID_FIELD = 'mbrainz_artist_id'
ALBUMID_FIELD = 'mbrainz_album_id'

ARTIST_KEYS = {
    'name': 'artist',
    'sort-name': 'sortname',
    'id': ARTISTID_FIELD,
    'ns2:score': '#score',
    'type': 'artist_type',
    'rating': 'mbrainz_rating',
}

ALBUM_KEYS = ARTIST_KEYS.copy()
ALBUM_KEYS.update({
    'name': 'album',
    'id': ALBUMID_FIELD,
    'type': 'album_type',
    'xml:ext': '#xml:ext',
    'title': 'album',
    'track-count': '__numtracks',
})

TRACK_KEYS = {
    'id': 'mbrainz_track_id',
    'position': 'track',
    'length': '__length',
    'rating': 'mbrainz_rating',
}

TO_REMOVE = ('recording', 'offset', 'count')

SMALL = 0
LARGE = 1
ORIG = 2

imagetypes = dict(reversed(i) for i in enumerate(IMAGETYPES))

mb_imagetypes = {
    "Front": "Cover (Front)",
    "Back": "Cover (Back)",
    "Other": "Other",
}


def children_to_text(node):
    if istext(node): return
    info = dict(list(node.attributes.items()))
    for ch in node.childNodes:
        if istext(ch): continue
        key = ch.tagName
        if key not in info:
            info[key] = node_to_text(ch)
        else:
            info[key] = to_list(info[key], node_to_text(ch))
    return info


def convert_dict(d, fm):
    return dict((fm.get(k, k), v) for k, v in d.items() if
                not isempty(v))


def istext(node):
    return getattr(node, 'nodeType', None) == TEXT_NODE


ESCAPE_CHARS_RE = re.compile(r'(?<!\\)(?P<char>[&|+\-!(){}[\]^"~*?:/])')


def solr_escape(value):
    r"""Escape un-escaped special characters and return escaped value.

    >>> solr_escape(r'foo+') == r'foo\+'
    True
    >>> solr_escape(r'foo\+') == r'foo\+'
    True
    >>> solr_escape(r'foo\\+') == r'foo\\+'
    True
    """
    #    value = value.replace('/', ' ')
    return ESCAPE_CHARS_RE.sub(r'\\\g<char>', value)


def node_to_text(node):
    if len(node.childNodes) > 1:
        return
    text_node = node.firstChild
    if istext(text_node):
        return text_node.data


def parse_album(xml):
    doc = minidom.parseString(xml)
    release_node = doc.getElementsByTagName('release')[0]

    return parse_release(release_node)


def parse_album_search(xml):
    doc = minidom.parseString(xml)
    nodes = doc.getElementsByTagName('release-list')[0].childNodes
    ret = []
    for i, node in enumerate(nodes):
        if istext(node):
            continue
        ret.append(parse_release(node))
    return ret


def parse_artist_credit(node):
    artists = parse_node(node, 'artist-credit', 'name-credit', 'artist')
    if not artists:
        return {}

    artist = ''.join(z['artist']['name'] + z.get('joinphrase', '')
                     for z in artists)
    if len(artists) == 1:
        artist_id = artists[0]['artist']['id']
        return {
            'artist': artist,
            'albumartist': artist,
            '#artist_id': artist_id,
            'mbrainz_artist_id': artist_id,
        }
    else:
        return {
            'artist': artist,
            'albumartist': artist,
            'mbrainz_artist_id': [z['artist']['id'] for z in artists],
        }


def parse_artist_relation(relations):
    ret = defaultdict(lambda: [])
    for r in to_list(relations['relation']):
        field = r['type']
        desc = ''

        if 'attribute-list' in r:
            desc = ', '.join(to_list(r['attribute-list']['attribute']))
        if 'artist' in r:
            if not desc:
                desc = r['artist']['name']
            else:
                if r['direction'] == 'backward':
                    field = '%s %s' % (desc, field)
                else:
                    field = '%s %s' % (field, desc)
                desc = r['artist']['name']
        if desc and desc not in ret[field]:
            ret[field].append(desc)
    return ret


def parse_artist_search(xml):
    doc = minidom.parseString(xml)
    nodes = doc.getElementsByTagName('artist-list')[0].childNodes
    ret = []
    for node in nodes:
        if istext(node):
            continue
        info = dict(list(node.attributes.items()))
        for ch in node.childNodes:
            if istext(node):
                continue
            info[ch.tagName] = node_to_text(ch)
        info = convert_dict(info, ARTIST_KEYS)
        info['#artist_id'] = info['mbrainz_artist_id']
        ret.append(info)
    return ret


def parse_label_list(release_node):
    labels = parse_node(release_node, 'label-info-list', 'label-info',
                        'label')

    catalogs = [z['catalog-number'] for z in labels if 'catalog-number' in z]
    label_names = [z['label']['name'] for z in labels
                   if 'label' in z and 'name' in z['label']]
    label_ids = [z['label']['id'] for z in labels
                 if 'label' in z and 'id' in z['label']]
    return {
        'label': list(dict.fromkeys(label_names)),
        'mbrainz_label_id': list(dict.fromkeys(label_ids)),
        'catalognumber': catalogs
    }


def parse_medium_list(r_node):
    lists = [z for z in r_node.childNodes
             if getattr(z, 'tagName', '') == 'medium-list']
    count = sum(1 for l in lists for z in l.childNodes
                if getattr(z, 'tagName', '') == 'medium')
    if not count:
        return {}

    info = {'discs': str(count)}
    formats = parse_node(r_node, 'medium-list', 'medium', 'format')
    if formats:
        info['format'] = formats[0]['format']
    return info


def parse_node(node, header_tag, sub_tag, check_tag):
    ret = []
    nodes = [z for z in node.childNodes if
             getattr(z, "tagName", '') == header_tag]
    for node in nodes:
        header = children_to_text(node)
        for ch in node.getElementsByTagName(sub_tag):
            if ch not in node.childNodes:
                continue
            info = header.copy()
            info.update(rec_children_to_text(ch))
            if check_tag not in info:
                continue
            ret.append(info)
    return ret


def parse_recording_relation(relations):
    info = defaultdict(lambda: [])

    for relation in to_list(relations['relation']):
        recording = relation['recording']
        desc = None

        if 'artist-credit' in recording:
            desc = ''.join(
                cr['artist']['name'] + cr.get('joinphrase', '')
                for cr in to_list(recording['artist-credit']['name-credit']))

        if 'title' in recording:
            if desc:
                desc = recording['title'] + ' by ' + desc
            else:
                desc = recording['title']
        if desc is not None:
            info[relation['type']].append(desc)
    return info


def parse_release(node):
    info = children_to_text(node)
    info.update(parse_artist_credit(node))

    info.update(parse_label_list(node))
    info.update(parse_medium_list(node))
    info = convert_dict(info, ALBUM_KEYS)
    info['#album_id'] = info['mbrainz_album_id']

    for k in ['count', 'track-list']:
        if k in info:
            del info[k]

    if 'disambiguation' in info:
        info['album'] = "%s (%s)" % (info['album'], info['disambiguation'])
        del (info['disambiguation'])

    tracks = []
    for medium in node.getElementsByTagName('medium'):
        disc = children_to_text(medium)
        disc = convert_dict({'discnumber': disc.get('position'),
                             'format': disc.get('format'),
                             'mbrainz_medium_id': disc.get('id')}, {})
        for track in parse_track_list(medium):
            track.update(disc)
            tracks.append(track)
    return info, tracks


def parse_track_list(node):
    tracks = []
    for i, t in enumerate(parse_node(node, 'track-list', 'track', 'position')):
        track = t['recording']
        track.update((k, v) for k, v in t.items() if k not in TO_REMOVE + ('id',))

        if 'isrc-list' in track:
            track['isrc'] = to_list(track.pop('isrc-list')['id'])

        if 'puid-list' in track:
            track['musicip_puid'] = track['puid-list']['id']
            del (track['puid-list'])

        if not isempty(track.get('relation-list')):
            for r in to_list(track['relation-list']):
                track.update(parse_track_relation(r))

        feat = to_list(track['artist-credit']['name-credit']) if 'artist-credit' in track else []
        if feat:
            names = [(z['artist']['name'], z.get('joinphrase', ''))
                     for z in feat]

            track['artist'] = ''.join('%s%s' % a for a in names)
            track['mbrainz_artist_id'] = [z['artist']['id'] for z in feat]

        for k, v in list(track.items()):
            if not isinstance(track[k], (str, list)):
                del (track[k])
            elif isinstance(v, list) and not isinstance(v[0], str):
                del (track[k])

        if 'length' in track:
            track['length'] = strlength(int(track['length']) / 1000)

        tracks.append(convert_dict(track, TRACK_KEYS))
    return tracks


def parse_track_relation(relation):
    if relation['target-type'] == 'recording':
        return parse_recording_relation(relation)
    elif relation['target-type'] == 'artist':
        return parse_artist_relation(relation)
    return {}


def rec_children_to_text(node):
    if istext(node): return
    info = dict(list(node.attributes.items()))
    for ch in node.childNodes:
        if istext(ch):
            continue
        text = node_to_text(ch)
        tag = ch.tagName
        if text is not None:
            info[tag] = to_list(info[tag], text) if tag in info else text
        elif ch.childNodes:
            v = rec_children_to_text(ch)
            info[tag] = to_list(info[tag], v) if tag in info else v
        elif ch.attributes:
            for k, v in ch.attributes.items():
                info[k] = to_list(info[k], v) if k in info else v
    return info


def mb_urlopen(url):
    """urlopen for MusicBrainz's web service, at most one request a
    second, as MusicBrainz asks of every program."""
    global _last_request
    with _request_lock:
        if _last_request is not None:
            wait = _last_request + 1 - time.monotonic()
            if wait > 0:
                time.sleep(wait)
        try:
            return urlopen(url)
        finally:
            _last_request = time.monotonic()


def retrieve_album(album_id):
    url = SERVER + 'release/' + album_id + \
          '?inc=recordings+artist-credits+labels+puids+isrcs+tags+ratings' \
          '+artist-rels+recording-rels+release-rels+release-group-rels' \
          '+url-rels+work-rels+recording-level-rels+work-level-rels'

    data = mb_urlopen(url)
    return parse_album(data)


def retrieve_cover_links(album_id, extra=None):
    if extra is None:
        url = COVER_SERVER + 'release/' + album_id
    else:
        url = '%srelease/%s/%s' % (COVER_SERVER, album_id, extra)
    write_log(translate('MusicBrainz', "Retrieving cover: {}").format(url))
    try:
        data, code = urlopen(url, code=True)
    except RetrievalError as e:
        if e.code == 404:
            raise RetrievalError(translate("MusicBrainz",
                                           "No images exist for this album."), 404)
        raise e

    if code == 200:
        if extra is None:
            return json.loads(data)
        else:
            return data
    elif code == 400:
        raise RetrievalError(translate("MusicBrainz", "Invalid UUID"))
    elif code in (405, 406):
        raise RetrievalError(translate("MusicBrainz", "Invalid query sent."))
    elif code == 503:
        raise RetrievalError(translate("MusicBrainz",
                                       "You have exceeded your rate limit."))
    elif code == 404:
        raise RetrievalError(translate("MusicBrainz",
                                       "Image does not exist."))


def retrieve_covers(cover_links, size=LARGE):
    ret = []
    for cover in cover_links['images']:
        desc = cover.get('comment', "")
        cover_type = cover['types'][0]
        if cover_type in mb_imagetypes:
            cover_type = imagetypes[mb_imagetypes[cover_type]]
        else:
            cover_type = imagetypes["Other"]
        thumbnails = cover['thumbnails']
        if size == SMALL:
            image_url = thumbnails.get('250') or thumbnails['small']
        elif size == LARGE:
            image_url = thumbnails.get('500') or thumbnails['large']
        else:
            image_url = cover['image']

        write_log(translate('MusicBrainz', "Retrieving image {}").format(image_url))
        try:
            image_data = urlopen(image_url)
        except RetrievalError as e:
            write_log(translate('MusicBrainz',
                                "Error retrieving image: {}").format(str(e)))
            continue

        ret.append({'desc': desc, 'mime': get_mime(image_data),
                    "imagetype": cover_type, "data": image_data})

    return ret


def retrieve_front_cover(album_id, size=ORIG):
    if size == SMALL:
        extra = 'front-250'
    elif size == LARGE:
        extra = 'front-500'
    else:
        extra = 'front'
    data = retrieve_cover_links(album_id, extra)
    return {'data': data, 'mime': get_mime(data)}


def search_album(album=None, artist=None, limit=25, offset=0, own=False):
    if own:
        return SERVER + 'release/?query=' + urllib.parse.quote_plus(album) + \
               '&limit=%d&offset=%d' % (limit, offset)

    if artist:
        query = 'artistname:' + urllib.parse.quote_plus(solr_escape(artist))

    if album:
        if isinstance(album, str):
            album = solr_escape(album)
        if artist:
            query = 'release:' + urllib.parse.quote_plus(album) + \
                    '%20AND%20' + query
        else:
            query = 'release:' + urllib.parse.quote_plus(album)

    return SERVER + 'release/?query=' + query.replace('%3A', '') + \
           '&limit=%d&offset=%d' % (limit, offset)


def search_artist(artist, limit=25, offset=0):
    query = urllib.parse.urlencode({
        'query': solr_escape(artist),
        'limit': limit,
        'offset': offset,
    })
    return SERVER + 'artist?' + query.replace('%3A', '')


def to_list(v, arg=None):
    if isinstance(v, list):
        if arg is not None:
            v.append(arg)
        return v
    else:
        return [v, arg] if arg is not None else [v]


class MusicBrainz(object):
    name = 'MusicBrainz'

    group_by = ['album', 'artist']

    def __init__(self):
        super(MusicBrainz, self).__init__()
        self.__image_size = ORIG
        self.__num_images = 0
        self.__get_images = True

        self.preferences = [
            [translate('MusicBrainz', 'Retrieve Cover'), CHECKBOX, True],
            [translate('MusicBrainz', 'Cover size to retrieve:'), COMBO,
             [[translate('MusicBrainz', 'Small'),
               translate('MusicBrainz', 'Large'),
               translate('MusicBrainz', 'Original Size')], 2]],
            [translate('MusicBrainz', 'Amount of images to retrieve:'), COMBO,
             [[translate('MusicBrainz', 'Just the front cover'),
               translate('MusicBrainz', 'All (can take a while)')], 0]],
        ]

    def keyword_search(self, s):
        if s.startswith(':a'):
            artist_id = s[len(':a'):].strip()
            try:
                url = search_album('arid:' + artist_id, limit=100, own=True)
                return parse_album_search(mb_urlopen(url))
            except RetrievalError as e:
                msg = translate('MusicBrainz',
                                "<b>Error:</b> While retrieving {}: {}"
                                ).format(artist_id, escape(str(e)))
                write_log(msg)
                raise
        elif s.startswith(':b'):
            r_id = s[len(':b'):].strip()
            try:
                return [self.retrieve(r_id)]
            except RetrievalError as e:
                msg = translate('MusicBrainz',
                                "<b>Error:</b> While retrieving Album ID {} ({})"
                                ).format(r_id, escape(str(e)))
                write_log(msg)
                raise
        else:
            try:
                params = parse_searchstring(s)
            except RetrievalError as e:
                return parse_album_search(mb_urlopen(search_album(s, limit=100)))
            if not params:
                return
            artist = params[0][0]
            album = params[0][1]
            return self.search(album, [artist], 100)

    def search(self, album, artists='', limit=40):
        ret = []
        check_matches = False
        if isempty(artists):
            artist = None
        if len(artists) > 1:
            artist = 'Various Artists'
        elif artists:
            if hasattr(artists, 'items'):
                artist = list(artists.keys())[0]
            else:
                artist = artists[0]

        if not album and not artist:
            raise RetrievalError('Album or Artist required.')

        write_log('Searching for %s' % album)

        if hasattr(artists, "items"):
            album_id = find_id(chain(*list(artists.values())), "mbrainz_album_id")
            if album_id:
                try:
                    write_log(translate('MusicBrainz',
                                        "Found album id {} in tracks. Retrieving").format(album_id))
                    return [self.retrieve(album_id)]
                except RetrievalError as e:
                    msg = translate('MusicBrainz',
                                    "<b>Error:</b> While retrieving Album ID {} ({})"
                                    ).format(album_id, escape(str(e)))
                    write_log(msg)

        try:
            xml = mb_urlopen(search_album(album, artist, limit))
        except urllib.error.URLError as e:
            write_log('Error: While retrieving search page %s' %
                      str(e))
            raise RetrievalError(str(e))
        write_log('Retrieved search results.')
        return parse_album_search(xml)

    def retrieve(self, albuminfo):
        try:
            album_id = albuminfo['#album_id']
        except TypeError:
            album_id = albuminfo
        ret = retrieve_album(album_id)
        image = self.retrieve_covers(album_id)
        if image:
            ret[0]['__image'] = image
        return ret

    def retrieve_covers(self, album_id):
        if not self.__get_images:
            return []
        try:
            if self.__num_images == 0:
                image = retrieve_front_cover(album_id, self.__image_size)
                if image:
                    return [image]
            else:
                return retrieve_covers(retrieve_cover_links(album_id),
                                       self.__image_size)
        except RetrievalError as e:
            write_log(translate('MusicBrainz',
                                "Error retrieving image: {}").format(str(e)))
            return []

    def applyPrefs(self, args):
        self.__get_images = args[0]
        self.__image_size = args[1]
        self.__num_images = args[2]


info = MusicBrainz
