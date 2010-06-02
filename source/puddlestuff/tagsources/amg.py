# -*- coding: utf-8 -*-
import re
import parse_html
import urllib2
import codecs
import sys, pdb, re, time
from functools import partial
from collections import defaultdict
from puddlestuff.util import split_by_tag
from puddlestuff.tagsources import write_log, set_status, RetrievalError
from puddlestuff.constants import CHECKBOX
from puddlestuff.puddleobjects import PuddleConfig

release_order = ('year', 'type', 'label', 'catalog')
search_adress = 'http://www.allmusic.com/cg/amg.dll?P=amg&sql=%s&opt1=2&samples=1&x=0&y=0'

search_order = (None, 'year', 'artist', None, 'album', None, 'label', 
                    None, 'genre')
album_url = 'http://www.allmusic.com/cg/amg.dll?p=amg&sql='

spanmap = {'Genre': 'genre',
           'Styles': 'style',
           'Themes': 'theme',
           'Moods': 'mood',
           'Release Date': 'year',
            'Label': 'label',
            'Album': 'album',
            'Artist': 'artist',
            'Featured Artist': 'artist',
            'Performer': 'artist',
            'Title': 'title',
            'Composer': 'composer',
            'Time': '__length',
            'Year': 'year'}

sqlre = re.compile('sql=(.*)')

first_white = lambda match: match.groups()[0][0]

def create_search(terms):
    return search_adress % re.sub('(\s+)', u'%20', terms)

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

def get_track(trackinfo, keys):
    tags =  trackinfo.find_all('td', {'class':'cell'})
    if not tags:
        return {}
    values = []
    for tag in tags:
        if text(tag):
            values.append(text(tag))
        else:
            if not tag.img:
                values.append('')
    try:
        track = int(values[0])
        return dict([(key, value) for key, value in zip(['track'] + keys, 
            values) if value])
    except ValueError:
        return dict([(key, value) for key, value in zip(keys, values)])

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

def parselist(item):
    d = {}
    titles = [text(z) for z in item.find_all('span')]
    for key, ul in zip(titles, item.find_all('ul')):
        if key in spanmap:
            key = spanmap[key]
            d[key] = [text(li) for li in ul.find_all('li')]
    return d

def parse_rating(soup):
    try:
        rating = soup.find_all('td', {'class': 'rating-stars'})[0][0]\
                .element.attrib['title'][0]
    except IndexError:
        return {}
    return {'rating': rating}

def parse_review(soup):
    try:
        review_td = [x for x in soup.find_all('td', valign="top", colspan="2")][0]
    except IndexError:
        return {}
    #review = text(review_td)
    ##There are double-spaces in links and italics. Have to clean up.
    #review = re.sub('(\s+)', first_white, review)
    return {'review': review_td.string.strip()}

def print_track(track):
    print '\n'.join([u'  %s - %s' % z for z in track.items()])
    print

keys = {'Release Date': 'year',
        'Label': 'label',
        'Album': 'album',
        'Artist': 'artist',
        'Featured Artist': 'artist',
        'Genre': parselist,
        'Moods': parselist,
        'Styles': parselist,
        'Themes': parselist,
        'Rating': parse_rating}

def parse_albumpage(page, artist=None, album=None):
    album_soup = parse_html.SoupWrapper(parse_html.parse(page))
    artist_group = album_soup.find_all('td', 'artist')
    info = {}
    for item in artist_group:
        key = item.find('span').all_text().strip()
        if key in keys:
            if callable(keys[key]):                
                info.update(keys[key](item))
            else:
                values = filter(None, map(text, item.find_all('td')))
                middle = len(values) / 2
                fields = [spanmap.get(key, key) for key in values[:middle]]
                info.update(zip(fields, values[middle:]))

    info.update(parse_rating(album_soup))
    info.update(parse_cover(album_soup))
    info.update(parse_review(album_soup))
    if 'year' in info:
        try:
            year = time.strptime(info['year'], '%b %d, %Y')
            info['year'] = time.strftime('%Y-%m-%d', year)
        except ValueError:
            try:
                year = time.strptime(info['year'], '%b %Y')
                info['year'] = time.strftime('%Y-%m', year)
            except ValueError:
                pass
    
    if artist and 'artist' not in info:
        info['artist'] = artist
    
    if album and 'album' not in info:
        info['album'] = album

    return info, parse_tracks(album_soup)

def parse_search_element(element):
    ret = {'#albumurl' : album_url + element.element.attrib['onclick'][3:-2]}
    try:
        ret.update({'#play': element[3].find('a',
                        {'rel': 'track'}).element.attrib['href']})
    except AttributeError:
        pass
    ret.update([(field, text(z)) for field, z
                    in zip(search_order, element) if field])
    ret['#extrainfo'] = [ret['album'] + u' at AllMusic.com', ret['#albumurl']]
    try:
        ret['amgsqlid'] = sqlre.search(ret['#albumurl']).groups()[0]
    except:
        print ret
        pass
    return ret

def parse_searchpage(page, artist, album):
    soup = parse_html.SoupWrapper(parse_html.parse(page))
    albums = [parse_search_element(z) for z in soup.find_all('td', {'class':'visible', 'id': 'trlink'})]
    d = {'artist': artist, 'album': album}
    ret = [album for album in albums if equal(d, album, True)]
    if ret:
        return True, ret
    else:
        ret = [album for album in albums if equal(d, album, False)]
        if ret:
            return True, ret
        else:
            return False, albums

def parse_tracks(soup):
    try:
        headers = [text(z) for z in soup.find('table', {'id': 'ExpansionTable1'}
                    ).find_all('td', {'class': 'passive'})]
    except AttributeError:
        return []
    keys = [spanmap.get(key, key) for key in headers]
    tracks = filter(None, [get_track(trackinfo, keys) for trackinfo in
                    soup.find_all('tr', {'id':"trlink"})])
    return tracks

def retrieve_album(url, coverurl=None):
    write_log('Opening Album Page - %s' % url)
    album_page = urllib2.urlopen(url).read()
    #to_file(album_page, 'album1.htm')
    info, tracks = parse_albumpage(album_page)
    try:
        info['amgsqlid'] = sqlre.search(url).groups()[0]
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

def retrieve_cover(url):
    cover = urllib2.urlopen(url).read()
    f = open('cover.jpg', 'w')
    f.write(cover)
    f.close()
    return {'__image': [{'data': cover}]}

def search(album):
    search_url = create_search(album)
    write_log(u'Search URL - %s' % search_url)
    return urllib2.urlopen(search_url.encode('utf8')).read()

def text(z):
    text = z.all_recursive_text().strip()
    return re.sub('(\s+)', first_white, text)

def to_file(data, name):
    f = open(name, 'w')
    f.write(data)
    f.close()


class AllMusic(object):
    name = 'AllMusic.com'
    def __init__(self):
        cparser = PuddleConfig()
        self._getcover = cparser.get('amg', 'retrievecovers', True)
        self.preferences = [['Retrieve Covers', CHECKBOX, self._getcover]]

    def search(self, audios=None, params=None):
        ret = []
        check_matches = False
        if not params:
            params = split_by_tag(audios, 'album', 'artist')
            check_matches = True
        else:
            d = defaultdict(lambda:[])
            for artist, albums in params.items():
                [d[album].append(artist) for album in albums]
            params = d
        for album, artists in params.items():
            if len(artists) > 1:
                set_status(u'More than one artist found. Assuming artist=' \
                            u'Various Artists.')
                artist = u'Various Artists'
            else:
                if check_matches:
                    artist = artists.keys()[0]
                else:
                    artist = artists[0]
            set_status(u'Searching for %s' % album)
            write_log(u'Searching for %s' % album)
            try:
                searchpage = search(album)
                #to_file(searchpage, 'search1.htm')
                #searchpage = open('spainsearch.htm').read()
            except urllib2.URLError, e:
                write_log(u'Error: While retrieving search page %s' % 
                            unicode(e))
                set_status(u'Error: While retrieving search page %s' % 
                            unicode(e))
                raise RetrievalError(unicode(e))
            write_log(u'Retrieved search results.')           
            matched, matches = parse_searchpage(searchpage, artist, album)
            if matched and len(matches) == 1:
                info, tracks = self.retrieve(matches[0])
                set_status(u'Found match for: %s - %s' % 
                                (artist, album))
                write_log(u'Found match for: %s - %s' % 
                                (artist, album))
                if check_matches:
                    if artist == u'Various Artists':
                        tags = ('artist', 'title')
                        audios = []
                        [audios.extend(z) for z in artists.values()]
                    else:
                        tags = ('title',)
                        audios = artists[artist]
                    for audio in audios:
                        for track in tracks:
                            if equal(audio, track, tags=tags):
                                track['#exact'] = audio
                                continue
                ret.append([info, tracks])
            elif matched:
                set_status(u'Ambiguous matches found for: %s - %s' % 
                                (artist, album))
                write_log(u'Ambiguous matches found for: %s - %s' % 
                                (artist, album))
                ret.extend([(z, []) for z in matches])
            else:
                set_status(u'No matches found for: %s - %s' % 
                                (artist, album))
                write_log(u'No matches found for: %s - %s' % 
                                (artist, album))
                ret.extend([(z, []) for z in matches])
        return ret

    def retrieve(self, albuminfo):
        set_status('Retrieving %s - %s' % (albuminfo['artist'], albuminfo['album']))
        write_log('Retrieving %s - %s' % (albuminfo['artist'], albuminfo['album']))
        write_log('Album URL - %s' % albuminfo['#albumurl'])
        url = albuminfo['#albumurl']
        try:
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
        self.preferences[0][2] = self._getcover
        cparser = PuddleConfig()
        cparser.set('amg', 'retrievecovers', self._getcover)

info = [AllMusic, None]
name = 'AllMusic.com'

if __name__ == '__main__':
    page = urllib2.urlopen(filename).read()
    [print_track(t) for t in parse_albumpage(page)[1]]
    