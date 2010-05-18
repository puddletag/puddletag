# -*- coding: utf-8 -*-
import re
import parse_html
import urllib2
import codecs
import sys, pdb
from functools import partial
from collections import defaultdict
try:
    from puddlestuff.util import split_by_tag
except ImportError:
    pass

release_order = ('year', 'type', 'label', 'catalog')
search_adress = 'http://www.allmusic.com/cg/amg.dll?P=amg&sql=%s&opt1=2&samples=1&x=0&y=0'

search_order = (None, 'year', 'artist', None, 'album', None, 'label', None, 'genre')
album_url = 'http://www.allmusic.com/cg/amg.dll?p=amg&sql='

def create_search(terms):
    return search_adress % terms.replace(' ', '+')

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

def get_track(trackinfo):
    try:
        return {'track': trackinfo[2].all_recursive_text().strip(),
                'title': trackinfo[4].all_recursive_text().strip(),
                'composer': trackinfo[5].all_recursive_text().strip(),
                '__length': trackinfo[6].all_recursive_text().strip()}
    except IndexError:
        return None

def find_a(tag, regex):
    ret = tag.find('a', href=re.compile(regex))
    if ret:
        return ret.all_text()
    return False

def find_all(regex, group):
    return filter(None, [find_a(tag, regex) for tag in group])

def parse_album_element(element):
    return dict([(k, z.all_recursive_text()) for k, z in
                    zip(release_order, element)])

def print_track(track):
    print '\n'.join([u'  %s - %s' % z for z in track.items()])
    print

def parse_cover(soup):
    cover_html = soup.find('img', src=re.compile('http://image.allmusic.com/'))
    try:
        cover_url = cover_html.element.attrib['src']
    except AttributeError:
        return {}
    return {'#cover-url': cover_url}

def parselist(item):
    d = {}
    titles = [z.all_recursive_text().strip() for z in item.find_all('span')]
    for key, ul in zip(titles, item.find_all('ul')):
        if key in listkeys:
            key = listkeys[key]
            d[key] = [li.all_recursive_text().strip() for 
                            li in ul.find_all('li')]
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
    review = review_td.all_recursive_text().strip()
    #There are double-spaces in links and italics. Have to clean up.
    review = review.replace(' . ', '. ')
    review = review.replace('  ', ' ')
    return {'review': review}

def parse_tracks(soup):
    return filter(None, [get_track(trackinfo) for trackinfo in
                    soup.find_all('tr', {'id':"trlink"})])
    
listkeys = {'Genre': 'genre',
            'Styles': 'style',
            'Themes': 'theme',
            'Moods': 'mood'}

keys = {'Release Date': 'date',
        'Label': 'label',
        'Album': 'album',
        'Artist': 'artist',
        'Genre': parselist,
        'Moods': parselist,
        'Styles': parselist,
        'Themes': parselist,
        'Rating': parse_rating}

def text(z):
    return z.all_recursive_text().strip()

def parse_albumpage(page):
    album_soup = parse_html.SoupWrapper(parse_html.parse(page))
    artist_group = album_soup.find_all('td', 'artist')
    info = {}
    for item in artist_group:
        key = item.find('span').all_text().strip()
        if key in keys:
            if callable(keys[key]):                
                info.update(keys[key](item))
            else:
                key, val = filter(None, map(text, item.find_all('td')))
                info[keys[key]] = val
    info.update(parse_rating(album_soup))
    info.update(parse_cover(album_soup))
    info.update(parse_review(album_soup))

    releasetype = [parse_album_element(t) for t in album_soup.find_all('table', width="342", cellpadding="0", cellspacing="0")[0][1:]]
    return info, parse_tracks(album_soup)

def parse_search_element(element):
    ret = {'#albumurl' : album_url + element.element.attrib['onclick'][3:-1]}
    try:
        ret.update({'#play': element[3].find('a',
                        {'rel': 'track'}).element.attrib['href']})
    except AttributeError:
        pass
    ret.update([(field, z.all_recursive_text().strip()) for field, z
                    in zip(search_order , element) if field])
    return ret

def parse_searchpage(page, artist, album):
    soup = parse_html.SoupWrapper(parse_html.parse(page))
    albums = [parse_search_element(z) for z in soup.find_all('td', {'class':'visible', 'id': 'trlink'})]
    d = {'artist': artist, 'album': album}
    ret = [album for album in albums if equal(d, album, True)]
    if ret:
        return True, ret
    else:
        return False, albums

def search(album):
    search_url = create_search(album)
    return urllib2.urlopen(search_url).read()

def retrieve_cover(url):
    cover = urllib2.urlopen(url).read()
    f = open('cover.jpg', 'w')
    f.write(cover)
    f.close()
    return {'__image': [{'data': cover}]}

def to_file(data, name):
    f = open(name, 'w')
    f.write(data)
    f.close()

def retrieve_album(url, coverurl=None):
    print 'Opening Album Page', url
    album_page = urllib2.urlopen(url).read()
    info, tracks = parse_albumpage(album_page)
    if coverurl:
        try:
            print 'Retrieving Cover', info['#cover-url']
            cover = retrieve_cover(info['#cover-url'])
        except KeyError:
            print 'No cover found.'
            cover = None
    else:
        cover = None
    return info, tracks, cover

class AllMusic(object):
    def __init__(self, retrievecover=True):
        self._getcover = retrievecover

    def search(self, audios=None, params=None):
        ret = []
        check_matches = False
        if not params:
            params = split_by_tag(audios)
            check_matches = True
        for artist, albums in params.items():
            for album in albums:
                print 'Searching...', artist, album
                searchpage = search(album)
                print 'Retrieved search results.'
                searchpage = open('name', 'r').read()
                matched, matches = parse_searchpage(searchpage, artist, album)
                #matched, matches = True, [{'#albumurl': 'file:///mnt/documents/flux/allmusic/corrinne.htm',
                        #'artist' : 'Corinne Bailey Rae',
                        #'album' : 'The Sea'}]
                #matched, matches = True, [{'#albumurl': 'file:///mnt/documents/flux/allmusic/ratatat-classsics.htm',
                        #'artist' : 'Ratatat',
                        #'album' : 'Classics'}]
                if matched and len(matches) == 1:
                    info, tracks = self.retrieve(matches[0])
                    if check_matches:
                        for audio in albums[album]:
                            for track in tracks:
                                if equal(audio, track,  tags=['title']):
                                    track['#exact'] = audio
                                    continue
                    ret.append([info, tracks])
                else:
                    ret.extend([(z, []) for z in matches])
        return ret

    def retrieve(self, albuminfo):
        url = albuminfo['#albumurl']
        info, tracks, cover = retrieve_album(url, self._getcover)
        if cover:
            info.update(cover)
        return info, tracks


info = [AllMusic, None]
name = 'AllMusic.com'

if __name__ == '__main__':
    x = AllMusic()
    info, tracks = x.search(params = {'cb': ['aoeu']})[0]
    print info['mood']