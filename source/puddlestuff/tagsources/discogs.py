# -*- coding: utf-8 -*-
import cStringIO, gzip, json, re, socket, sys, time, urllib2

from copy import deepcopy

import puddlestuff.tagsources

from puddlestuff.audioinfo import DATA, isempty
from puddlestuff.constants import CHECKBOX, COMBO, TEXT
from puddlestuff.tagsources import (find_id, write_log, RetrievalError,
    parse_searchstring, iri_to_uri)
from puddlestuff.util import translate

R_ID_DEFAULT = 'discogs_id'
R_ID = R_ID_DEFAULT
MASTER = 'master'
RELEASE = 'release'

SITE_MASTER_URL = 'http://www.discogs.com/master/'
SITE_RELEASE_URL = 'http://www.discogs.com/release/'
API_RELEASE_URL = 'http://api.discogs.com/release/'
API_MASTER_URL = 'http://api.discogs.com/master/'
SITE_URL = 'http://www.discogs.com'

api_key = 'c6e33897b6'
base_url = 'http://api.discogs.com/%s'

def query_urls(key):
    search_url = base_url % 'database/search?type=release&q=%s&per_page=100'
    release_url = base_url % 'release/%s'
    master_url = base_url % 'master/%s'
    return (search_url, release_url, master_url)

search_url, release_url, master_url = query_urls(api_key)

SMALLIMAGE = '#smallimage'
LARGEIMAGE = '#largeimage'
image_types = [SMALLIMAGE, LARGEIMAGE]

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

INVALID_KEYS = ['status', 'resource_url', 'tracklist', 'thumb',
    'formats', 'artists', 'extraartists', 'images', 'videos',
    'master_id', 'labels', 'companies', 'series', 'released_formatted',
    'identifiers']

class LastTime(object): pass
    
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
    for key,v in d.iteritems():
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
    write_log(translate("Discogs",
        'Retrieving search results for keywords: %s') % keywords)
    keywords = re.sub('(\s+)', u'+', keywords)
    url = search_url % keywords
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
            if a.get(u'join'):
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
    info['involvedpeople_album'] = u':'.join(u'%s;%s' % (z['name'],z['role'])
        for z in data.get('extraartists', []))
    info['label'] = [z['name'] for z in data.get('labels', [])]
    info['catno'] = filter(None,
        [z.get('catno') for z in data.get('labels', [])])

    info['companies'] = u';'.join(
        u'%s %s' % (z['entity_type_name'], z['name'])
        for z in data.get('companies', []))
    info['album'] = data['title']
    cleaned_data = convert_dict(check_values(data), ALBUM_KEYS)
    cleaned_data.update(check_values(convert_dict(info, ALBUM_KEYS)))
    info = cleaned_data

    if 'images' in data:
        imgs = [(z.get('uri', ''), z.get('uri150', ''))
            for z in data['images'] if 'uri' in z or 'uri150' in z]
        info['#cover-url'] = imgs
        
    return (info, parse_tracklist(data['tracklist']))

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
            
    url = master_url % r_id if rls_type == MASTER else release_url % r_id
    x = urlopen(url)
    ret = parse_album_json(json.loads(x)['resp'][rls_type])

    info = deepcopy(info)
    info.update(ret[0])

    if image in image_types and '#cover-url' in info:
        data = []
        for large, small in info['#cover-url']:
            if image == LARGEIMAGE and large:
                write_log(
                    translate("Discogs", 'Retrieving cover: %s') % large)
                try:
                    data.append({DATA: urlopen(large)})
                except RetrievalError, e:
                    write_log(translate('Discogs',
                        u'Error retrieving image:') + unicode(e))
            else:
                write_log(
                    translate("Discogs", 'Retrieving cover: %s') % small)
                try:
                    data.append({DATA: urlopen(small)})
                except RetrievalError, e:
                    write_log(translate('Discogs',
                        u'Error retrieving image:') + unicode(e))
        if data:
            info.update({'__image': data})

    try:
        info['#extrainfo'] = (translate('Discogs', '%s at Discogs.com') % \
            info['album'], site_url)
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
    if puddlestuff.tagsources.user_agent:
        request.add_header('User-Agent', puddlestuff.tagsources.user_agent)

    if time.time() - __lasttime.time < 1:
        time.sleep(1)
    __lasttime.time = time.time()

    try:
        data = urllib2.urlopen(request).read()
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

    try: data = gzip.GzipFile(fileobj = cStringIO.StringIO(data)).read()
    except IOError: "Gzipped data not returned."

    return data

class Discogs(object):
    name = 'Discogs.com'
    group_by = [u'album', u'artist']
    tooltip = translate("Discogs", """<p>Enter search parameters here. If empty,
        the selected files are used.</p>
        <ul>
        <li><b>artist;album</b>
        searches for a specific album/artist combination.</li>
        <li>To list the albums by an artist leave off the album part,
        but keep the semicolon (eg. <b>Ratatat;</b>).
        For a album only leave the artist part as in
        <b>;Resurrection.</li>
        <li>Using <b>:r id</b> will retrieve the album with Discogs
        ID <b>id</b>.</li>
        <li>Entering keywords <b>without a semi-colon (;)</b> will
         do a Discogs album search using those keywords.</li>
        </ul>""")

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

        if text.startswith(':r'):
            r_id = text[len(':r'):].strip()
            try:
                r_id = int(r_id)
                return [self.retrieve(r_id)]
            except (TypeError, ValueError):
                raise RetrievalError(
                    translate("Discogs", 'Invalid Discogs Release ID'))
        try:
            params = parse_searchstring(text)
        except RetrievalError:
            return [(info, []) for info in keyword_search(text)]

        artists = [params[0][0]]
        album = params[0][1]
        return self.search(album, artists)

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

        retrieved_albums = search(artist, album)
        return [(info, []) for info in retrieved_albums]

    def retrieve(self, info):
        if self._getcover:
            return retrieve_album(info, self.covertype)
        else:
            return retrieve_album(info, None)

    def applyPrefs(self, args):
        self._getcover = args[0]
        self.covertype = image_types[args[1]]
        if not self._getcover:
            self.covertype = None
        global R_ID
        if args[2]:
            R_ID = args[2]
        else:
            R_ID = R_ID_DEFAULT

        global search_url, release_url, master_url
        key = args[3] if args[3] else api_key
        search_url, release_url, master_url = query_urls(key)
        

info = Discogs

if __name__ == '__main__':

    k = Discogs()
    print k.keyword_search(":r 911637")
    
    #import json
    #d = json.loads(open('a.json', 'r').read())
    #x = parse_album_json(d['resp']['release'])
    #print x
