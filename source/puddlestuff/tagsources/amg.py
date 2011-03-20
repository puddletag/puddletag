# -*- coding: utf-8 -*-
import sys
import re
import parse_html
import urllib2
import codecs
import sys, pdb, re, time, os
from functools import partial
from collections import defaultdict
from puddlestuff.util import split_by_tag
from puddlestuff.tagsources import (write_log, set_status, RetrievalError,
    urlopen, parse_searchstring, retrieve_cover, get_encoding, iri_to_uri)
from puddlestuff.constants import CHECKBOX, SAVEDIR, TEXT
from puddlestuff.puddleobjects import PuddleConfig

release_order = ('year', 'type', 'label', 'catalog')
search_adress = 'http://www.allmusic.com/search/album/%s'
album_url = u'http://www.allmusic.com/album/'

spanmap = {
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
    'Performer': 'artist',
    'Title': 'title',
    'Composer': 'composer',
    'Time': '__length',
    'Type': 'type',
    'Year': 'year',
    'Performance': 'performance',
    'Sound': 'sound',
    'Rating': 'rating',
    'AMG Album ID': 'amg_album_id',
    'Performed By': 'performer'}

sqlre = re.compile('(r\d+)$')

first_white = lambda match: match.groups()[0][0]

def find_id(tracks, field=None):
    for track in tracks:
        if field in track:
            value = track[field]
            if isinstance(value, basestring):
                return value
            else:
                return value[0]

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
    return search_adress % re.sub('(\s+)', u'%20', terms.strip())

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

def find_a(tag, regex):
    ret = tag.find('a', href=re.compile(regex))
    if ret:
        return ret.all_text()
    return False

def find_all(regex, group):
    return filter(None, [find_a(tag, regex) for tag in group])

def parse_album_element(element):
    ret =  dict([(k, text(z)) for k, z in
                    zip(release_order, element)])

def parse_cover(soup):
    cover_html = soup.find('img', src=re.compile('http://image.allmusic.com/'))
    try:
        cover_url = cover_html.element.attrib['src']
    except AttributeError:
        return {}
    return {'#cover-url': cover_url}

def parse_rating(soup, field='rating'):
    try:
        img = soup.find('img', {'alt': re.compile('star_rating\(\d+\)')})
        rating = re.search('star_rating\((\d+)\)', img.element.attrib['alt']).groups()[0]
    except (IndexError, AttributeError):
        return {}
    return {field: rating}

def parse_review(soup):
    try:
        review_td = soup.find_all('div', {'id': 'review'})[0]
        author = review_td.find('p', {'class':'author'}).string.strip()
        review = review_td.find('p', {'class':'text'}).string.strip()
        if not review.strip():
            raise IndexError
        ##There are double-spaces in links and italics. Have to clean up.
        review = re.sub('\s{2,}', ' ', review)
    except (IndexError, AttributeError):
        return {}
    
    return {'review': '%s\n\n%s' % (author, review)}

def print_track(track):
    print '\n'.join([u'  %s - %s' % z for z in track.items()])
    print

def parse_albumpage(page, artist=None, album=None):
    album_soup = parse_html.SoupWrapper(parse_html.parse(page))
    artist_group = album_soup.find('div', {'class': 'left-sidebar'})

    find = artist_group.find_all

    info = {}
    values = find('p')

    for field in find('h3'):
        if field.element.attrib:
            continue

        value = field.element.getnext()
        if value.tag != 'p':
            break
        value = convert(value.text_content())
        field = field.string.strip()
        info[field] = value

    #Get Genres/styles
    styles = artist_group.find_all('div', {'id': 'genre-style'})
    half_column = re.compile('half-column$')
    for style in styles:
        for g in style.find_all('div', half_column):
            try:
                field = g.find('h3').string.strip()
            except AttributeError:
                #Sometimes they leave an extra empty field
                continue
            try:
                values = [convert(z.string) for z
                    in g.find('ul').find_all('li')]
            except AttributeError:
                info.update(parse_rating(g, field))
                continue
            info[field] = values

    info.update(parse_rating(album_soup))
    info.update(parse_review(album_soup))
    info.update(convert_year(info))
    info.update(parse_cover(album_soup))

    info = dict((spanmap.get(k, k), v) for k, v in info.iteritems() if v)

    if artist and 'artist' not in info:
        info['artist'] = artist
    
    if album and 'album' not in info:
        info['album'] = album

    if ('#extrainfo' not in info) and ('#albumurl' in info) and ('album' in info):
        info['#extrainfo'] = [info['album'] + u' at AllMusic.com', info['#albumurl']]

    return info, parse_tracks(album_soup)

def parse_search_element(element, fields, id_field = None):
    ret = {}
    for td, field in zip(element.find_all('td'), fields):
        if field == 'title':
            ret['#albumurl'] = td.find('a').element.attrib['href']
        elif not field:
            try:
                ret.update({'#play': td.find(
                    'a', {'rel': 'sample'}).element.attrib['href']})
            except AttributeError:
                pass
            continue
        ret[field] = td.string.strip()

    ret['#extrainfo'] = [ret['title'] + u' at AllMusic.com', ret['#albumurl']]
    try:
        if id_field:
            ret[id_field] = sqlre.search(ret['#albumurl']).groups()[0]
    except AttributeError:
        pass
    if 'relevance' in ret:
        del(ret['relevance'])

    if 'title' in ret:
        ret['album'] = ret['title']
        del(ret['title'])
    return ret

def parse_searchpage(page, artist, album, id_field):
    page = get_encoding(page, True, 'utf8')[1]
    soup = parse_html.SoupWrapper(parse_html.parse(page))
    results = soup.find('table', {'class': 'search-results'})
    try:
        fields = [z.string.strip().lower() for z in results.find('tr').find_all('th')]
    except AttributeError:
        return []
    albums = [parse_search_element(z, fields, id_field) for z in
        results.find_all('tr')[1:]]

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
    try:
        headers = [th.string.strip() for th in table.tr.find_all('th')]
    except AttributeError:
        return None

    keys = [spanmap.get(key, key) for key in headers]

    tracks = []

    for tr in table.find_all('tr', {'id': 'trlink'}):
        track = {}
        if discnum:
            track['discnumber'] = discnum
        extra = tr.find('div', {'class': 'expand'})
        if extra:
            value = convert(extra.string)
            try:
                field, value = [z.strip() for z in value.split(u':')]
                tracks[-1][spanmap.get(field, field)] = value
            except (ValueError, TypeError):
                tracks[-1][extra] = value
            continue
                
        for field, td in zip(headers, tr.find_all('td')):
            if not field:
                try:
                    value = unicode(int(td.string.strip()))
                    field = 'track'
                except (TypeError, ValueError):
                    continue
            else:
                value = convert(td.string)
            track[spanmap.get(field, field)] = value
        if not track:
            continue
        else:
            tracks.append(dict((k,v) for k,v in track.items() if v))
    if not tracks:
        return None
    return tracks

def parse_tracks(soup):
    track_div = soup.find('div', {'id': 'tracks'})
    if track_div is None:
        track_div = track_div = soup.find('div', {'id': 'performances'})

    if track_div is None:
        return None
    discs = [re.search('\d+$', z.string.strip()).group()
        for z in track_div.find_all('p', {'id': 'discnum'})]
    track_tables = soup.find_all('table', {'id': 'ExpansionTable'})
    if discs:
        tracks = []
        [tracks.extend(parse_track_table(t, d)) for t,d in
            zip(track_tables, discs)]
        if tracks:
            return tracks
        else:
            return None
    else:
        return parse_track_table(track_tables[0])

def retrieve_album(url, coverurl=None, id_field=None):
    review = False
    try:
        write_log('Opening Review Page - %s' % (url + '/review', ))
        album_page = urlopen(url + '/review', False)
    except (EnvironmentError, RetrievalError):
        write_log('Opening Album Page - %s' % url)
        album_page = urlopen(url)
        review = False
    album_page = get_encoding(album_page, True, 'utf8')[1]
    
    
    info, tracks = parse_albumpage(album_page)
    if not tracks and review:
        write_log('Re-Opening Album Page - %s' % url)
        album_page = urlopen(url)
        album_page = get_encoding(album_page, True, 'utf8')[1]
        new_info, tracks = parse_albumpage(album_page)
        info.update(new_info)
        
    info['#albumurl'] = url
    try:
        if id_field:
            info[id_field] = sqlre.search(url).groups()[0]
    except AttributeError:
        pass
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
        return to_file(name + '_')
        
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
        self._id_field = 'amgalbumid'
        self.preferences = [
            ['Retrieve Covers', CHECKBOX, True],
            ['Use AllMusic Album ID to retrieve albums:', CHECKBOX, self._useid],
            ['Field to use for SQL ID:', TEXT, self._id_field]
            ]
    
    def keyword_search(self, text):
        if text.startswith(u':id'):
            url = album_url + text[len(':id'):].strip()
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
            if album_id and (album_id.startswith('r') or album_id.startswith('w')):
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
        
        matched, matches = parse_searchpage(searchpage, artist, album,
            self._id_field)
        if matched and len(matches) == 1:
            ret = [(matches[0], [])]
        elif matched:
            write_log(u'Ambiguous matches found for: %s - %s' % 
                (artist, album))
            ret.extend([(z, []) for z in matches])
        else:
            write_log(u'No matches found for: %s - %s' % 
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
            spanmap['AMG Album ID'] = 'amg_album_id'

info = AllMusic

if __name__ == '__main__':
    f = get_encoding(open(sys.argv[1], 'r').read(), True)[1]
    x = parse_albumpage(f)
    #pdb.set_trace()
    print x
    