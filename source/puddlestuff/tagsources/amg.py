# -*- coding: utf-8 -*-
import sys, json
import re
import parse_html
import urllib, urllib2
import codecs
import sys, pdb, re, time, os
from functools import partial
from collections import defaultdict
from puddlestuff.util import split_by_tag
from puddlestuff.tagsources import (write_log, set_status, RetrievalError,
    urlopen, parse_searchstring, retrieve_cover, get_encoding, iri_to_uri)
from puddlestuff.constants import CHECKBOX, SAVEDIR, TEXT
from puddlestuff.puddleobjects import PuddleConfig
from puddlestuff.audioinfo import isempty, CaselessDict

ALBUM_ID = 'amg_album_id'

release_order = ('year', 'type', 'label', 'catalog')
search_adress = 'http://www.allmusic.com/-/search/albums/%s'
album_url = u'http://www.allmusic.com/album/'

spanmap = CaselessDict({
    'Genre': 'genre',
    'Styles': 'style',
    'Style': 'style',
    'Themes': 'theme',
    'Moods': 'mood',
    'Release Date': 'year',
    'Recording Date': 'recording_date',
    'Label': 'label',
    'Album': 'album',
    'Artist': 'artist',
    'Featured Artist': 'artist',
    'Performer': 'performer',
    'Title': 'title',
    'Composer': 'composer',
    'Time': '__length',
    'Type': 'type',
    'Year': 'year',
    'Performance': 'performance',
    'Sound': 'sound',
    'Rating': 'rating',
    'AMG Album ID': ALBUM_ID,
    'Performed By': 'performer',
    'sample': None,
    'stream': None,
    'title-artist': 'artist',
    'AMG Pop ID': 'amg_pop_id',
    'Rovi Music ID': 'amg_rovi_id',
    })

sqlre = re.compile('(r\d+)$')

first_white = lambda match: match.groups()[0][0]

def find_id(tracks, field=None):
    for track in tracks:
        if field in track:
            value = track[field]
            if isinstance(value, basestring):
                return value.replace(u' ', u'').lower()
            else:
                return value[0].replace(u' ', u'').lower()

white_replace = lambda match: match.group()[0]
def convert(value):
    text = value.strip()
    text = re.sub('\s{2,}', white_replace, text)
    if isinstance(text, str):
        return unicode(text)
    return text

def convert_year(info):
    if 'year' not in info:
        return {}

    try:
        year = time.strptime(info['year'], '%b %d, %Y')
        return {'year': time.strftime('%Y-%m-%d', year)}
    except ValueError:
        try:
            year = time.strptime(info['year'], '%b %Y')
            return {'year': time.strftime('%Y-%m', year)}
        except ValueError:
            return {}
    return {}

def create_search(terms):
    terms = re.sub(u'[%]', u'', terms.strip())
    return search_adress % urllib.quote(re.sub('(\s+)', u' ',
        terms).encode('utf8'))

def equal(audio1, audio2, play=False, tags=('artist', 'album')):
    for key in tags:
        if (key in audio1) and (key in audio2):
            if u''.join(audio1[key]).lower() != u''.join(audio2[key]).lower():
                return False
        else:
            return False
    if play and ('#play' not in audio2):
        return False
    return True

def parse_cover(soup):
    cover_html = soup.find('img', src=re.compile('http://image.allmusic.com/'))
    try:
        cover_url = cover_html.element.attrib['src']
    except AttributeError:
        return {}
    return {'#cover-url': cover_url}
    
def parse_rating(dd):
    dd.find('span', {'class':"hidden", 'itemprop':"rating"})
    return convert(dd.string)

def parse_review(content):

    review = content.find('div', {'id': 'review'})
    if not review:
        return {}

    review_text = content.find('div', {'class':"review-body"})
    review_text = review.find('div',
        {'class': "editorial-text collapsible-content"})
    text = convert(review_text.p.string)

    author = convert(review.find('span', {'class':"author"}).string)

    return {'review': author + '\n\n' + text}

def print_track(track):
    print '\n'.join([u'  %s - %s' % z for z in track.items()])
    print

def parse_sidebar_element(element):
    info = {}
    for e in element.find_all('dt|dd'):
        if e.tag == 'dt':
            field = convert(e.string)
        elif e.tag == 'dd':
            if field == 'editor rating':
                info['rating'] = parse_rating(e)
                continue
            elif field in ('genres', 'styles', 'genre', 'style'):
                try:
                    items = e.find('ul').find_all('li')
                    key = spanmap.get(field, field)
                    info[key] = [convert(i.string) for i in items]
                except AttributeError:
                    info[field[:-1]] = convert(e.string)
            elif e.element.attrib.get('class') == u'metaids':
                info.update(parse_sidebar_element(e.contents[0].contents[1]))
            else:
                if field:
                    info[spanmap.get(field, field)] = convert(e.string)
            field = None

    info.update(convert_year(info))
    if 'duration' in info:
        del(info['duration'])
    return info

def parse_similar(swipe):
    ret = []
    try:
        similar = swipe.find('ul', {'class': "swipe-gallery-pages"})
    except AttributeError:
        return {}
    for div in similar.find_all('div', {'class': "thumbnail lg album"}):
        try:
            title = div.a.element.attrib['title']
        except KeyError:
            title = div.a.element.attrib['oldtitle']
        #artist = convert(div.find('div', {'class': 'artist'}).string)
        #album = convert(div.find('div', {'class': 'album'}).string)
        ret.append(title.replace(u' - ', u'; ', 1))

    if ret:
        return {'similar_albums': ret}
    return {}
            
def parse_albumpage(page, artist=None, album=None):
    album_soup = parse_html.SoupWrapper(parse_html.parse(page))

    heading = album_soup.find('div', {'class': 'page-heading'})
    artist = heading.find('div', {'class': 'album-artist'})
    album = heading.find('div', {'class': 'album-title'})
    info = {'artist': convert(artist.string), 'album': convert(album.string)}
    
    main = album_soup.find('div', {'id': 'main'})
    sidebar = main.find('div', {'class': 'left', 'id': 'sidebar'})
    info.update(parse_sidebar(sidebar))

    content = main.find('div', {'class': 'right', 'id': 'content'})
    info.update(parse_review(content))

    swipe = main.find('div', {'id':"similar-albums", 'class':"grid-gallery"})
    
    info.update(parse_similar(swipe))
    
    info = dict((k,v) for k, v in info.iteritems() if not isempty(v))
        
    return [info, parse_tracks(content)]

def parse_sidebar(sidebar):
    
    info = {}

    cover = sidebar.find('div', {'class': 'album-art'})
    cover = cover.find('div', {'class': 'image-container'})
    try:
        
        info['#cover-url'] = json.loads(
            cover.element.attrib['data-large'])['url']
    except KeyError:
        "Doesn't have artwork."

    details = sidebar.find('dl', {'class': 'details'})
    info.update(parse_sidebar_element(details))

    moods = sidebar.find('div', {'class': 'sidebar-module moods'})
    if moods is not None:
        info['mood'] = [convert(z.string) for z in
            moods.find('ul').find_all('li')]

    themes = sidebar.find('div', {'class': 'sidebar-module themes'})
    if themes is not None:
        info['theme'] = [convert(z.string) for z in
            themes.find('ul').find_all('li')]

    return info

def parse_search_element(td, id_field=ALBUM_ID):
    """Parse search element td and returns dictionary with album info.

    Search pages contain all album info in a td element. This routine
    parses the element and returns all info in dictionary with
    the field as keys and value being the value.

    Returns a dictionary with at least the following keys:
    artist -- artist name found
    album -- album name found
    #albumurl -- link to album.
    #extrainfo -- tuple with first item description text and second item
                  a link to the album.
    year -- album release year."""

    
    def to_string(e):
        try: return convert(e.a.string)
        except AttributeError:
            try: return convert(e.string)
            except AttributeError: return u''
    
    info = {}

    album = td.find('div', {'class': 'title'})
    
    info['album'] = to_string(album)
    info['#albumurl'] = convert(album.a.element.attrib['href'])
    info['amg_url'] = info['#albumurl']

    info['artist'] = to_string(td.find('div', {'class': 'artist'}))

    if not info['artist']:
        artist = to_string(td.find('div', {'class': 'title'}))
        if u':' in artist:
            artist = [z.strip() for z in artist.split(u':', 1)]
            info['artist'], info['album'] = artist
        else:
            info['album'] = artist
    
    info['year'] = to_string(td.find('div', {'class': 'year'}))
    info['genre'] = to_string(td.find('div', {'class': 'genre'}))

    info['#extrainfo'] = [
        info['album'] + u' at AllMusic.com', info['#albumurl']]

    info[id_field] = re.search('-(mw\d+)$', info['#albumurl']).groups()[0]
    
    return dict((k,v) for k, v in info.iteritems() if not isempty(v))

def parse_searchpage(page, artist=None, album=None, id_field=ALBUM_ID):
    """Parses a search page and gets relevant info.


    Arguments:
    page -- html string with search page's html.
    artist -- artist to to check for in results. If found only results
              with that artist are returned.
    album -- album to check for in results. If found only results with
             with the album are returned.
    id_field -- key to use for the album id found.

    Return a tuple with the first element being == True if the list
    was truncated with only matching artist/albums.
    
    """
    page = get_encoding(page, True, 'utf8')[1]
    soup = parse_html.SoupWrapper(parse_html.parse(page))
    result_table = soup.find('table', {'class': 'search-results'})
    try:
        results = result_table.find_all('tr',
            {'class': 'search-result album'})
    except AttributeError:
        return []

    albums = [parse_search_element(result.find("td")) for result in results]

    d = {}
    if artist and album:
        d = {'artist': artist, 'album': album}
        ret = [album for album in albums if equal(d, album, True)]
    elif album:
        d = {'album': album}
        ret = [album for album in albums if equal(d, album, True, ['album'])]
        if not ret:
            ret = [album for album in albums if 
                equal(d, album, False, ['album'])]
    elif artist:
        d = {'artist': artist}
        ret = [album for album in albums if equal(d, album, True, ['artist'])]
        if not ret:
            ret = [album for album in albums if
                equal(d, album, False, ['artist'])]
    else:
        ret = []

    if ret:
        return True, ret
    else:
        ret = [album for album in albums if equal(d, album, False)]
        if ret:
            return True, ret
        else:
            return False, albums

def parse_track_table(table, discnum=None):

    def to_string(e):
        try: return convert(e.a.string)
        except AttributeError: return convert(e.string)
    
    header_items = table.table.thead.find('tr').find_all('th')
    headers = [th.element.attrib.get('class', convert(th.string))
        for th in header_items]
    fields = [spanmap.get(key, key) for key in headers]

    tracks = []
    performance = u''
    for item in table.tbody.find_all('tr'):
        t = parse_track(item, fields)
        if isinstance(t, basestring):
            performance = t + u': '
        else:
            t['title'] = performance + t['title']
            if discnum:
                t['discnumber'] = discnum
            tracks.append(t)
    return tracks

def parse_track(tr, fields):

    track = {}

    if tr.element.attrib.get('class') == 'perfomance-title':
        return convert(tr.string)
    
    for th, field in zip(tr.find_all('td'), fields):
        if field is None:
            continue

        divs = th.find_all('div')
        if not divs:
            track[field] = convert(th.string)
            continue
        if field == 'artist':
            track['title'] = th.find('div', {'class':'title'})
            if track['title'] is None:
                track['title'] = th.find('div', {'class':'title primary_link'})

            track['title']= convert(track['title'].string)
                
            composer_div = th.find('div', {'class': "artist secondary_link"})
            composer = map(convert, composer_div.string.split(u' / '))
            track['composer'] = composer
        elif field == 'performer':
            track['performer'] =  map(convert, th.string.split(u' / '))

    return track

def parse_tracks(content):
    track_div = content.find('div', {'id': 'tracks'})
    if track_div is None:
        track_div = content.find('div', {'id': 'performances'})

    if track_div is None:
        track_div = content.find('div', {'id': 'results-table'})

    if track_div is None:
        return None

    discs = [re.search('\d+$', z.string.strip()).group()
        for z in track_div.find_all('span', {'class': 'disc-num'})]
    track_tables = content.find_all('div', {'class': 'table-container'})
    if not track_tables:
        return None
        
    if discs:
        tracks = []
        for tb, discnum in zip(track_tables, discs):
            tracks.extend(parse_track_table(tb, discnum))
        if tracks:
            return tracks
        else:
            return None
    else:
        return parse_track_table(track_tables[0])

def retrieve_album(url, coverurl=None, id_field=None):
    review = False
    write_log('Opening Album Page - %s' % url)
    album_page = urlopen(url, False)
    album_page = get_encoding(album_page, True, 'utf8')[1]
    
    info, tracks = parse_albumpage(album_page)
    info['#albumurl'] = url
    info['amg_url'] = url

    if coverurl:
        try:
            write_log('Retrieving Cover - %s'  % info['#cover-url'])
            cover = retrieve_cover(info['#cover-url'])
        except KeyError:
            write_log('No cover found.')
            cover = None
        except urllib2.URLError, e:
            write_log(u'Error: While retrieving cover %s - %s' % 
                (info['#cover-url'], unicode(e)))
            cover = None
    else:
        cover = None
    return info, tracks, cover

def search(album):
    search_url = create_search(album.replace(u'/', u' '))
    write_log(u'Search URL - %s' % search_url)
    return urlopen(iri_to_uri(search_url))

def text(z):
    text = z.all_recursive_text().strip()
    return re.sub('(\s+)', first_white, text)

def to_file(data, name):
    if os.path.exists(name):
        return to_file(data, name + '_')
        
    f = open(name, 'w')
    f.write(data)
    f.close()

class AllMusic(object):
    name = 'AllMusic.com'
    tooltip = "Enter search parameters here. If empty, the selected files are used. <ul><li><b>artist;album</b> searches for a specific album/artist combination.</li> <li>To list the albums by an artist leave off the album part, but keep the semicolon (eg. <b>Ratatat;</b>). For a album only leave the artist part as in <b>;Resurrection.</li><li>By prefacing the search text with <b>:id</b> you can search for an albums using it's AllMusic sql id eg. <b>:id 10:nstlgr7nth</b> (extraneous spaces are discarded.)<li></ul>"
    group_by = [u'album', 'artist']
    def __init__(self):
        super(AllMusic, self).__init__()
        self._getcover = True
        self._useid = True
        self._id_field = ALBUM_ID
        self.preferences = [
            ['Retrieve Covers', CHECKBOX, True],
            ['Use AllMusic Album ID to retrieve albums:', CHECKBOX, self._useid],
            ['Field to use for SQL ID:', TEXT, self._id_field]
            ]
    
    def keyword_search(self, text):
        if text.startswith(u':id'):
            sql = text[len(':id'):].strip().replace(u' ', u'').lower()
            if sql.startswith('mr'):
                url = album_url + 'release/' + sql
            else:
                url = album_url + sql
            if self._useid:
                info, tracks, cover = retrieve_album(url, self._getcover, 
                    self._id_field)
            else:
                info, tracks, cover = retrieve_album(url, self._getcover)
            if cover:
                info.update(cover)
            return [(info, tracks)]
        else:
            try:
                params = parse_searchstring(text)
            except RetrievalError:
                return self.search(text, [u''])
            artists = [params[0][0]]
            album = params[0][1]
            return self.search(album, artists)

    def search(self, album, artists):
        ret = []
        check_matches = False
        if len(artists) > 1:
            artist = u'Various Artists'
        else:
            if hasattr(artists, 'items'):
                artist = artists.keys()[0]
            else:
                artist = artists[0]
            
        if self._useid and hasattr(artists, 'values'):
            tracks = []
            [tracks.extend(z) for z in artists.values()]
            album_id = find_id(tracks, self._id_field)
            if album_id and (album_id.startswith('r') or \
                album_id.startswith('w')):

                write_log(u'Found Album ID %s' % album_id)
                return self.keyword_search(u':id %s' % album_id)

        if not album:
            raise RetrievalError('Album name required.')

        write_log(u'Searching for %s' % album)
        try:
            searchpage = search(album)
        except urllib2.URLError, e:
            write_log(u'Error: While retrieving search page %s' % 
                        unicode(e))
            raise RetrievalError(unicode(e))
        write_log(u'Retrieved search results.')
        
        search_results = parse_searchpage(searchpage, artist, album,
            self._id_field)
        if search_results:
            matched, matches = search_results
        else:
            return []

        if matched and len(matches) == 1:
            ret = [(matches[0], [])]
        elif matched:
            write_log(u'Ambiguous matches found for: %s - %s' % 
                (artist, album))
            ret.extend([(z, []) for z in matches])
        else:
            write_log(u'No exact matches found for: %s - %s' % 
                (artist, album))
            ret.extend([(z, []) for z in matches])
        return ret

    def retrieve(self, albuminfo):
        try:
            artist = albuminfo['artist']
            album = albuminfo['album']
            set_status('Retrieving %s - %s' % (artist, album))
            write_log('Retrieving %s - %s' % (artist, album))
        except KeyError:
            set_status('Retrieving album.')
            write_log('Retrieving album')
        write_log('Album URL - %s' % albuminfo['#albumurl'])
        url = albuminfo['#albumurl']
        try:
            if self._useid:
                info, tracks, cover = retrieve_album(url, self._getcover,
                    self._id_field)
            else:
                info, tracks, cover = retrieve_album(url, self._getcover)
        except urllib2.URLError, e:
            write_log(u'Error: While retrieving album URL %s - %s' % 
                (url, unicode(e)))
            raise RetrievalError(unicode(e))
        if cover:
            info.update(cover)
        albuminfo = albuminfo.copy()
        albuminfo.update(info)
        return albuminfo, tracks

    def applyPrefs(self, args):
        self._getcover = args[0]
        self._useid = args[1]
        self._id_field = args[2]
        if args[2]:
            spanmap['AMG Album ID'] = self._id_field
        else:
            spanmap['AMG Album ID'] = ALBUM_ID

info = AllMusic

if __name__ == '__main__':
    f = get_encoding(open(sys.argv[1], 'r').read(), True)[1]
    x = parse_albumpage(f)
    #pdb.set_trace()
    print x
    