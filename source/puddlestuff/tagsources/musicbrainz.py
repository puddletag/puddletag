import json, pdb, re, sys, time, urllib, urllib2

from collections import defaultdict
from itertools import chain
from sgmllib import SGMLParser
from xml.dom import minidom, Node
from xml.sax.saxutils import escape, quoteattr

from puddlestuff.audioinfo import IMAGETYPES, get_mime, strlength
from puddlestuff.constants import CHECKBOX, COMBO
from puddlestuff.tagsources import (find_id, write_log, RetrievalError,
    urlopen, parse_searchstring)
from puddlestuff.util import isempty, translate

SERVER = 'http://musicbrainz.org/ws/2/'

TEXT_NODE = Node.TEXT_NODE

ARTISTID = '#artistid'
ALBUMID = '#albumid'
LABELID = '#labelid'
INCLUDES = ''

ARTISTID_FIELD = 'mbrainz_artist_id'
ALBUMID_FIELD = 'mbrainz_album_id'

ARTIST_KEYS = {
    'name': 'artist',
    'sort-name': 'sortname',
    'id': 'mbrainz_artist_id',
    'ext:score': '#score',
    'type': 'artist_type',
    'rating': 'mbrainz_rating',
    }

ALBUM_KEYS = ARTIST_KEYS.copy()
ALBUM_KEYS.update({
    'name': 'album',
    'id': 'mbrainz_album_id',
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
    info = dict(node.attributes.items())
    for ch in node.childNodes:
        if istext(ch): continue
        key = ch.tagName
        if key not in info:
            info[key] = node_to_text(ch)
        else:
            info[key] = to_list(info[key], node_to_text(ch))
    return info

def convert_dict(d, fm):
    return dict((fm.get(k, k), v) for k, v in d.iteritems() if
        not isempty(v))

def fix_xml(xml):
    c = XMLEscaper()
    c.feed(album_xml)
    return c.xml

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
#    value = value.replace(u'/', u' ')
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
    artists = parse_node(node, u'artist-credit', u'name-credit', u'artist')
    if not artists:
        return {}

    artist = u', '.join(z[u'artist'][u'name'] for z in artists)
    if len(artists) == 1:
        artist_id = artists[0]['artist']['id']
        return {
            'artist': artist,
            '#artist_id': artist_id,
            'mbrainz_artist_id': artist_id,
            }
    else:
        return {'artist': artist}

def parse_artist_relation(relations):
    ret = defaultdict(lambda: [])
    for r in to_list(relations[u'relation']):
        field = r['type']
        desc = u''

        if u'attribute-list' in r:
            desc = u', '.join(to_list(r[u'attribute-list']['attribute']))
        if u'artist' in r:
            if not desc:
                desc = r[u'artist'][u'name']
            else:
                if r[u'direction'] == u'backward':
                    field = '%s %s' % (desc, field)
                else:
                    field = '%s %s' % (field, desc)
                desc = r[u'artist'][u'name']
        if desc:
            ret[field].append(desc)
    return ret
        
def parse_artist_search(xml):
    doc = minidom.parseString(xml)
    nodes = doc.getElementsByTagName('artist-list')[0].childNodes
    ret = []
    for node in nodes:
        if istext(node):
            continue
        info = dict(node.attributes.items())
        for ch in node.childNodes:
            if istext(node):
                continue
            info[ch.tagName] = node_to_text(ch)
        info = convert_dict(info, ARTIST_KEYS)
        info['#artist_id'] = info['mbrainz_artist_id']
        ret.append(info)
    return ret

def parse_label_list(release_node):
    labels = parse_node(release_node, u'label-info-list', u'label-info',
        u'label')


    catalogs = [z[u'catalog-number'] for z in labels if u'catalog-number' in z]
    label_names = [z[u'label'][u'name'] for z in labels
        if u'label' in z and u'name' in z[u'label']]
    label_ids = [z[u'label'][u'id'] for z in labels
        if u'label' in z and u'id' in z[u'label']]
    return {
        'label': label_names,
        'mbrainz_label_id': label_ids,
        'catalognumber': catalogs
        }
    
def parse_medium_list(r_node):
    mediums = parse_node(r_node, u'medium-list', u'medium', u'format')
    if not mediums:
        return {}

    mediums = [convert_dict(m, ALBUM_KEYS) for m in mediums]
    info = mediums[0]
    info.update({'discs': unicode(len(mediums))})
    return info

def parse_node(node, header_tag, sub_tag, check_tag):
    ret = []
    nodes = [z for z in node.childNodes if
        getattr(z, "tagName", u'') == header_tag]
    for node in nodes:
        info = children_to_text(node)
        for ch in node.getElementsByTagName(sub_tag):
            if ch not in node.childNodes:
                continue
            info = info.copy()
            info.update(rec_children_to_text(ch))
            if check_tag not in info:
                continue
            ret.append(info)
    return ret

def parse_recording_relation(relations):
    info = defaultdict(lambda: [])

    for relation in to_list(relations[u'relation']):
        recording = relation['recording']
        desc = None

        if u'artist-credit' in recording:
            artists = []
            for cr in to_list(recording[u'artist-credit']['name-credit']):
                if u'join-phrase' in cr:
                    artists.append(cr[u'join-phrase'])
                artists.append(cr[u'artist'][u'name'])

            unique_artists = []
            for z in artists:
                if z not in unique_artists:
                    unique_artists.append(z)
                
            desc = u' '.join(unique_artists)

        if u'title' in recording:
            if desc:
                desc = recording[u'title'] + u' by ' + desc
            else:
                desc = recording[u'title']
        if desc is not None:
            info[relation['type']].append(desc)
    return info

def parse_release(node):
    info = children_to_text(node)
    info.update(parse_artist_credit(node))

    info.update(parse_label_list(node))
    info.update(parse_medium_list(node))
    info = convert_dict(info, ALBUM_KEYS)
    info['#album_id'] = info[u'mbrainz_album_id']

    if u'count' in info:
        del(info['count'])

    if 'disambiguation' in info:
        info['album'] = u"%s (%s)" % (info['album'], info['disambiguation'])
        del(info['disambiguation'])
    
    tracks = []
    for medium in node.getElementsByTagName('medium'):
        tracks.extend(parse_track_list(medium))
    return info, tracks
    
def parse_track_list(node):
    tracks = []
    for i, t in enumerate(parse_node(node, 'track-list', 'track', 'position')):
        track = t['recording']
        rem_keys = set(track).union(TO_REMOVE)
        track.update((k,v) for k,v in t.iteritems() if k not in rem_keys)

        if u'puid-list' in track:
            track['musicip_puid'] = track['puid-list']['id']
            del(track['puid-list'])
    
        if not isempty(track.get(u'relation-list')):
            for r in to_list(track['relation-list']):
                track.update(parse_track_relation(r))

        feat = to_list(track.get('artist-credit', {}).get('name-credit'))
        if feat:
            names = [(z['artist']['name'], z.get('joinphrase', u''))
                for z in feat]

            track['artist'] = u''.join('%s%s' % a for a in names)

        for k, v in track.items():
            if not isinstance(track[k], (basestring, list)):
                del(track[k])
            elif isinstance(v, list) and not isinstance(v[0], basestring):
                del(track[k])

        if u'length' in track:
            track['length'] = strlength(int(track[u'length']) / 1000)

        tracks.append(convert_dict(track, TRACK_KEYS))
    return tracks

def parse_track_relation(relation):
    if relation[u'target-type'] == u'recording':
        return parse_recording_relation(relation)
    elif relation[u'target-type'] == u'artist':
        return parse_artist_relation(relation)
    return {}

def rec_children_to_text(node):
    if istext(node): return
    info = dict(node.attributes.items())
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

def retrieve_album(album_id):
    url = SERVER + 'release/' + album_id + \
        '?inc=recordings+artist-credits+puids+isrcs+tags+ratings' \
        '+artist-rels+recording-rels+release-rels+release-group-rels' \
        '+url-rels+work-rels+recording-level-rels+work-level-rels'

    data = urlopen(url)
    return parse_album(data)

def retrieve_cover_links(album_id, extra=None):
    if extra is None:
        url = "http://coverartarchive.org/release/" + album_id
    else:
        url = "http://coverartarchive.org/release/%s/%s" % (album_id, extra)
    write_log(translate("MusicBrainz", "Retrieving cover: %s") % url)
    try:
        data, code = urlopen(url, code=True)
    except RetrievalError, e:
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
        desc = cover.get('comment', u"")
        cover_type = cover['types'][0]
        if cover_type in mb_imagetypes:
            cover_type = imagetypes[mb_imagetypes[cover_type]]
        else:
            cover_type = imagetypes[u"Other"]
        if cover == SMALL:
            image_url = cover['thumbnails']['small']
        elif cover == LARGE:
            image_url = cover['thumbnails']['large']
        else:
            image_url = cover['image']

        write_log(translate("MusicBrainz", "Retrieving image %s") % image_url)
        image_data = urlopen(image_url)

        ret.append({'desc': desc, 'mime': get_mime(image_data),
            "imagetype": cover_type, "data": image_data})

    return ret

def retrieve_front_cover(album_id):
    data = retrieve_cover_links(album_id, "front")
    return {'data': data, 'mime': get_mime(data)}
    
def search_album(album=None, artist=None, limit=25, offset=0, own=False):
    if own:
        if isinstance(album, unicode):
            album = solr_escape(album.encode('utf8'))

        return SERVER + 'release/?query=' + urllib.quote_plus(album) + \
            '&limit=%d&offset=%d' % (limit, offset)

    if artist:
        if isinstance(artist, unicode):
            artist = artist.encode('utf8')
        query = 'artistname:' + urllib.quote_plus(solr_escape(artist))

    if album:
        if isinstance(album, unicode):
            album = solr_escape(album.encode('utf8'))
        if artist:
            query = 'release:' + urllib.quote_plus(album) + \
                '%20AND%20' + query
        else:
            query = 'release:' + urllib.quote_plus(album)

    return SERVER + 'release/?query=' + query.replace('%3A', '') + \
        '&limit=%d&offset=%d' % (limit, offset)

def search_artist(artist, limit=25, offset=0):
    if isinstance(artist, unicode):
        artist = artist.encode('utf8')
    query = urllib.urlencode({
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

class XMLEscaper(SGMLParser):
    def reset(self):
        SGMLParser.reset(self)
        self._xml = []

    def handle_data(self, data):
        self._xml.append(escape(data))

    def unknown_starttag(self, tag, attributes):
        attrib_str = ' '.join('%s=%s' % (k, quoteattr(v))
            for k, v in attributes)
        self._xml.append('<%s %s>' % (tag, attrib_str))

    def unknown_endtag(self, tag):
        self._xml.append('</%s>' % tag)

    def _get_xml(self):
        return ''.join(self._xml)

    xml = property(_get_xml)


class MusicBrainz(object):
    name = u'MusicBrainz'

    group_by = [u'album', 'artist']
    def __init__(self):
        super(MusicBrainz, self).__init__()
        self.__lasttime = time.time()
        self.__image_size = LARGE
        self.__num_images = 0
        self.__get_images = True

        self.preferences = [
            [translate('MusicBrainz', 'Retrieve Cover'), CHECKBOX, True],
            [translate('MusicBrainz', 'Cover size to retrieve:'), COMBO,
                [[translate('Amazon', 'Small'),
                    translate('Amazon', 'Large'),
                    translate('Amazon', 'Original Size')], 1]],
            [translate('MusicBrainz', 'Amount of images to retrieve:'), COMBO,
                [[translate('MusicBrainz', 'Just the front cover'),
                    translate('MusicBrainz', 'All (can take a while)')], 0]],
            ]

    def keyword_search(self, s):
        if s.startswith(u':a'):
            artist_id = s[len(':a'):].strip()
            try:
                url = search_album('arid:' +
                    solr_escape(artist_id.encode('utf8')), limit=100, own=True)
                return parse_album_search(urlopen(url))
            except RetrievalError, e:
                msg = translate("MusicBrainz",
                    '<b>Error:</b> While retrieving %1: %2')
                write_log(msg.arg(artist_id).arg(escape(e)))
                raise
        elif s.startswith(u':b'):
            r_id = s[len(u':b'):].strip()
            try:
                return [self.retrieve(r_id)]
            except RetrievalError, e:
                msg = translate("MusicBrainz",
                    "<b>Error:</b> While retrieving Album ID %1 (%2)")
                write_log(msg.arg(r_id).arg(escape(e)))
                raise 
        else:
            try:
                params = parse_searchstring(s)
            except RetrievalError, e:
                return parse_album_search(urlopen(search_album(s, limit=100)))
            if not params:
                return
            artist = params[0][0]
            album = params[0][1]
            return self.search(album, [artist], 100)

    def search(self, album, artists=u'', limit=40):
        if time.time() - self.__lasttime < 1000:
            time.sleep(1)

        ret = []
        check_matches = False
        if isempty(artists):
            artist = None
        if len(artists) > 1:
            artist = u'Various Artists'
        elif artists:
            if hasattr(artists, 'items'):
                artist = artists.keys()[0]
            else:
                artist = artists[0]

        if not album and not artist:
            raise RetrievalError('Album or Artist required.')

        write_log(u'Searching for %s' % album)

        if hasattr(artists, "items"):
            album_id = find_id(chain(*artists.values()), "mbrainz_album_id")
            if album_id:
                try:
                    write_log(translate("MusicBrainz",
                        "Found album id %s in tracks. Retrieving") % album_id)
                    return [retrieve_album(album_id)]
                except RetrievalError, e:
                    msg = translate("MusicBrainz",
                        "<b>Error:</b> While retrieving Album ID %1 (%2)")
                    write_log(msg.arg(album_id).arg(escape(e)))

        try:
            xml = urlopen(search_album(album, artist, limit))
        except urllib2.URLError, e:
            write_log(u'Error: While retrieving search page %s' %
                        unicode(e))
            raise RetrievalError(unicode(e))
        write_log(u'Retrieved search results.')
        self.__lasttime = time.time()
        return parse_album_search(xml)

    def retrieve(self, albuminfo):
        try:
            album_id = albuminfo['#album_id']
        except TypeError:
            album_id = albuminfo
        if time.time() - self.__lasttime < 1000:
            time.sleep(1)
        ret = retrieve_album(album_id)
        self.__lasttime = time.time()
        image = self.retrieve_covers(album_id)
        if image:
            ret[0]['__image'] = image
        return ret

    def retrieve_covers(self, album_id):
        if not self.__get_images:
            return []
        if self.__num_images == 0:
            try:
                image = retrieve_front_cover(album_id)
                if image:
                    return [image]
            except RetrievalError, e:
                import traceback
                traceback.print_exc()
                print
                write_log(translate("MusicBrainz",
                    "Error retrieving image: %s") % unicode(e))
                return []
        else:
            return retrieve_covers(album_id, self.__image_size)

    def applyPrefs(self, args):
        self.__get_images = args[0]
        self.__image_size = args[1]
        self.__num_images = args[2]

info = MusicBrainz

if __name__ == '__main__':
    #retrieve_album(u'f504ebe7-8fb4-40e5-aa55-b6384bdf863e')
    #c = MusicBrainz()
    xml = open('/home/keith/Desktop/mb.xml', 'r').read()
    #x = c.search('New Again', 'Taking Back Sunday')
    tracks = parse_album(xml)[1]
    for z in tracks:
        print z['title'], z['track']
