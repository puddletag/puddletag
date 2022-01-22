import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from . import parse_html
from ..audioinfo import isempty, CaselessDict
from ..constants import CHECKBOX
from ..puddleobjects import ratio
from ..tagsources import (write_log, set_status, RetrievalError,
                          urlopen, parse_searchstring, retrieve_cover, get_encoding, iri_to_uri)


class OldURLError(RetrievalError):
    pass


ALBUM_ID = 'amg_album_id'

release_order = ('year', 'type', 'label', 'catalog')
search_adress = 'http://www.allmusic.com/search/albums/%s'
album_url = 'http://www.allmusic.com/album/'

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
    'duration': '__length',
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
    'tracknum': 'track',
    'AMG Classical ID': 'amg_classical_id',
    'catalog #': 'catalog',
    'release info': 'release_info',
    'primary': 'composer',
})

sqlre = re.compile('(r\d+)$')

first_white = lambda match: match.groups()[0][0]


def find_id(tracks, field=None):
    for track in tracks:
        if field in track:
            value = track[field]
            if isinstance(value, str):
                return value.replace(' ', '').lower()
            else:
                return value[0].replace(' ', '').lower()


white_replace = lambda match: match.group()[0]


def convert(value):
    text = value.strip()
    text = re.sub('\s{2,}', white_replace, text)
    if isinstance(text, str):
        return str(text)
    return text


def convert_year(info):
    if 'release date' not in info:
        return {}

    info['year'] = info['release date']
    del (info['release date'])

    if not isinstance(info['year'], str):
        info['year'] = info['year'][0]
    try:
        year = time.strptime(info['year'], '%B %d, %Y')
        return {'year': time.strftime('%Y-%m-%d', year)}
    except ValueError:
        try:
            year = time.strptime(info['year'], '%b %Y')
            return {'year': time.strftime('%Y-%m', year)}
        except ValueError:
            return {}
    return {}


def create_search(terms):
    terms = re.sub('[%]', '', terms.strip())
    return search_adress % urllib.parse.quote(re.sub('(\s+)', ' ',
                                                     terms))


def equal(audio1, audio2, play=False, tags=('artist', 'album')):
    for key in tags:
        if (key in audio1) and (key in audio2):
            if ratio(''.join(audio1[key]), ''.join(audio2[key])) < 0.5:
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
    dd.find('span', {'class': "hidden", 'itemprop': "rating"})
    return convert(dd.string)


def parse_review(content):
    reviewer = content.find('h4', {'class': 'review-author headline'})
    if not reviewer:
        return {}

    author = convert(reviewer.string)

    text = convert(content.find('div', {'class': 'text'}).p.string)

    return {'review': author + '\n\n' + text}


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

        url = '; http://www.allmusic.com' + div.a.element.attrib['href']
        ret.append(title.replace(' - ', '; ', 1) + url)

    if ret:
        return {'similar_albums': ret}
    return {}


def parse_albumpage(page, artist=None, album=None):
    info = {}

    album_soup = parse_html.SoupWrapper(parse_html.parse(page))

    artist = album_soup.find('div', {'class': 'album-artist'})
    album = album_soup.find('div', {'class': 'album-title'})

    release_title = album_soup.find('h3', 'release-title')

    if release_title:
        album = release_title
        details = album_soup.find('p', {'class': 'release-details'})
        if details:
            info['release'] = convert(details.string)

    if not artist:
        artist = album_soup.find('h3', 'release-artist')

    if album is None:
        info.update({'artist': convert(artist.string), 'album': ''})
    else:
        info.update({'artist': convert(artist.string), 'album': convert(album.string)})
    info['albumartist'] = info['artist']

    sidebar = album_soup.find('div', {'class': 'sidebar'})
    info.update(parse_sidebar(sidebar))
    info.update(convert_year(info))

    content = album_soup.find('section', {'class': 'review read-more'})
    if content:
        info.update(parse_review(content))

    # swipe = main.find('div', {'id':"similar-albums", 'class':"grid-gallery"})

    # info.update(parse_similar(swipe))

    info = dict((spanmap.get(k, k), v) for k, v in info.items() if not isempty(v))

    return [info, parse_tracks(album_soup, info)]


def parse_sidebar_element(element):
    try:
        title = convert(element.find('h4').string.lower())
    except AttributeError:
        return {}

    if element.find('span'):
        values = [convert(element.find('span').string)]
    elif element.find('div'):
        anchors = element.find('div').find_all('a')
        values = [convert(anchor.string) for anchor in anchors]
    elif element.find('ul'):
        values = [convert(z.string) for z in element.ul.find_all('li')]
    else:
        return {}
    return {title: values}


def parse_metadata_ids(element):
    data = {}
    key = None
    for child in element.contents:
        if child.element.attrib.get('class') == 'id-type':
            key = convert(child.string)
        elif key:
            data[key] = [convert(child.string)]
            key = None
    return data


def parse_sidebar(sidebar):
    info = {}

    container = sidebar.find('div', {'class': 'album-contain'})
    if container is None:
        container = sidebar.find('div', {'class': 'release-cover-contain'})
    cover = container.find('img')
    if cover is not None:
        try:
            cover_url = json.loads(cover.element.attrib['data-lightbox'])['url']
        except KeyError:
            try:
                cover_url = cover.element.attrib['src']
                if cover.element.attrib.get('class') == 'no-image':
                    cover_url = None
            except (AttributeError, KeyError):
                cover_url = None

        if cover_url:
            cover_url = cover_url.replace('?partner=allrovi.com', '')
            if cover_url.startswith('/'):
                cover_url = 'http://www.allmusic.com' + cover_url
            info['#cover-url'] = cover_url

    basic_info = sidebar.find('section', {'class': 'basic-info'})
    invalids = set(['affiliates', 'advertising medium-rectangle', 'partner-buttons'])
    for div in basic_info.find_all('div'):
        class_name = div.element.attrib.get('class')
        if class_name in invalids: continue
        if class_name == 'metadata-ids':
            info.update(parse_metadata_ids(div))
        elif class_name:
            info.update(parse_sidebar_element(div))

    moods = sidebar.find('section', {'class': 'moods'})
    if moods is not None:
        info['mood'] = [convert(z.string) for z in
                        moods.find_all('span', {'class': 'mood'})]

    themes = sidebar.find('section', {'class': 'themes'})
    if themes is not None:
        info['theme'] = [convert(z.string) for z in
                         themes.find_all('span', {'class': 'theme'})]

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
        try:
            return convert(e.a.string)
        except AttributeError:
            try:
                return convert(e.string)
            except AttributeError:
                return ''

    info = {}

    album = td.find('div', {'class': 'title'})

    info['album'] = to_string(album)
    info['#albumurl'] = convert(album.a.element.attrib['href'])
    info['amg_url'] = info['#albumurl']

    info['artist'] = to_string(td.find('div', {'class': 'artist'}))

    if not info['artist']:
        artist = to_string(td.find('div', {'class': 'title'}))
        if ':' in artist:
            artist = [z.strip() for z in artist.split(':', 1)]
            info['artist'], info['album'] = artist
        else:
            info['album'] = artist

    info['year'] = to_string(td.find('div', {'class': 'year'}))
    info['genre'] = to_string(td.find('div', {'class': 'genres'}))

    info['#extrainfo'] = [
        info['album'] + ' at AllMusic.com', info['#albumurl']]

    info[id_field] = re.search('-(mw\d+)$', info['#albumurl']).groups()[0]

    return dict((k, v) for k, v in info.items() if not isempty(v))


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
    soup = parse_html.SoupWrapper(parse_html.parse(page))
    result_table = soup.find('ul', {'class': 'search-results'})
    try:
        results = result_table.find_all('div',
                                        {'class': 'info'})
    except AttributeError:
        return []

    albums = [parse_search_element(result) for result in results]

    d = {}
    if artist and album:
        d = {'artist': artist, 'album': album}
        top = [album for album in albums if equal(d, album, True)]
    elif album:
        d = {'album': album}
        top = [album for album in albums if equal(d, album, True, ['album'])]
        if not top:
            top = [album for album in albums if
                   equal(d, album, False, ['album'])]
    elif artist:
        d = {'artist': artist}
        top = [album for album in albums if equal(d, album, True, ['artist'])]
        if not ret:
            top = [album for album in albums if
                   equal(d, album, False, ['artist'])]
    else:
        top = []

    return False, albums


def parse_track_table(table, discnum=None):

    def to_string(e):
        try:
            return convert(e.a.string)
        except AttributeError:
            return convert(e.string)

    header_items = table.thead.find('tr').find_all('th')
    headers = [th.element.attrib.get('class', convert(th.string))
               for th in header_items]

    fields = [spanmap.get(key, key) for key in headers]

    tracks = []
    performance_title = None
    for item in table.tbody.find_all('tr'):
        if item.element.attrib.get('class') == 'performance-title':
            performance_title = convert(item.string.strip())
            continue
        t = parse_track(item, fields, performance_title)
        tracks.append(t)
    return tracks


def parse_track(tr, fields, performance_title=None):
    track = {}
    ignore = set(['pick-prefix', 'sample', 'stream', 'pick-suffix'])

    if tr.element.attrib.get('class') == 'perfomance-title':
        return convert(tr.string)

    for td, field in zip(tr.find_all('td'), fields):
        if field in ignore:
            continue
        elif field is None:
            field = td.element.attrib.get('class')
            if not field:
                continue

        sub_fields = td.find_all('div')
        if (sub_fields):
            for div in sub_fields:
                sub_field = div.element.attrib['class']
                if field == 'performer' and sub_field == 'primary':
                    sub_field = field
                elif field == 'performer' and sub_field != 'primary':
                    if sub_field == 'featuring':
                        track[field] = '%s %s' % (track.get(field, ''), convert(div.string))
                    else:
                        sub_field = 'composer'

                value = convert(div.string)
                track[sub_field] = value
        else:
            track[field] = convert(td.string)
    if performance_title and 'title' in track:
        track['title'] = performance_title + ': ' + track['title']
    if 'artist' not in track and 'performer' in track:
        track['artist'] = track['performer']
    return dict((spanmap.get(k, k), v) for k, v in track.items() if spanmap.get(k, k) and not isempty(v))


def replace_feat(album_info, track_info):
    artist = None
    for key in ['albumartist', 'artist', 'performer', 'composer']:
        value = album_info.get(key, '').strip();
        if not value.startswith('feat:'):
            artist = album_info[key]
            break

    if artist is None:
        return

    for k, v in track_info.items():
        if isinstance(v, str) and v.strip().startswith('feat:'):
            track_info[k] = artist + ' ' + v.strip()

    if 'featuring' in track_info:
        del (track_info['featuring'])


def parse_tracks(content, album_info):
    discs = content.find_all('div', 'disc')
    if not discs:
        return None
    tracks = []
    for i, disc in enumerate(discs):
        disc_info = {'discnumber': str(i + 1)}
        disc_tracks = parse_track_table(disc.table)
        for track in disc_tracks:
            if len(discs) > 1:
                track.update(disc_info)
            replace_feat(album_info, track)

        tracks.extend(disc_tracks)
    return tracks


def retrieve_album(url, coverurl=None, id_field=ALBUM_ID):
    write_log('Opening Album Page - %s' % url)
    album_page, code = urlopen(url, False, True)
    if album_page.find("featured new releases") >= 0:
        raise OldURLError("Old AMG URL used.")
    album_page = get_encoding(album_page, True, 'utf8')[1]

    info, tracks = parse_albumpage(album_page)
    info['#albumurl'] = url
    info['amg_url'] = url

    if 'album' in info:
        info['#extrainfo'] = [
            info['album'] + ' at AllMusic.com', info['#albumurl']]

    if coverurl:
        try:
            write_log('Retrieving Cover - %s' % info['#cover-url'])
            cover = retrieve_cover(info['#cover-url'])
        except KeyError:
            write_log('No cover found.')
            cover = None
        except urllib.error.URLError as e:
            write_log('Error: While retrieving cover %s - %s' %
                      (info['#cover-url'], str(e)))
            cover = None
    else:
        cover = None
    return info, tracks, cover


def search(album):
    search_url = create_search(album.replace('/', ' '))
    write_log('Search URL - %s' % search_url)
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
    group_by = ['album', 'artist']

    def __init__(self):
        super(AllMusic, self).__init__()
        self._getcover = True
        self._useid = True
        self.preferences = [
            ['Retrieve Covers', CHECKBOX, True],
            ['Use AllMusic Album ID to retrieve albums:', CHECKBOX, self._useid],
        ]

    def keyword_search(self, text):
        if text.startswith(':id'):
            sql = text[len(':id'):].strip().replace(' ', '').lower()
            if sql.startswith('mr'):
                url = album_url + 'release/' + sql
            else:
                url = album_url + sql
            info, tracks, cover = retrieve_album(url, self._getcover)
            if cover:
                info.update(cover)
            return [(info, tracks)]
        else:
            try:
                params = parse_searchstring(text)
            except RetrievalError:
                return self.search(text, [''])
            artists = [params[0][0]]
            album = params[0][1]
            return self.search(album, artists)

    def search(self, album, artists):
        ret = []
        if len(artists) > 1:
            artist = 'Various Artists'
        else:
            if hasattr(artists, 'items'):
                artist = list(artists.keys())[0]
            else:
                artist = artists[0]

        if self._useid and hasattr(artists, 'values'):
            tracks = []
            [tracks.extend(z) for z in artists.values()]
            for field in ('amg_rovi_id', 'amg_pop_id', 'amgsqlid', 'amg_album_id',):
                album_id = find_id(tracks, field)
                if album_id:
                    break

            if not isempty(album_id):
                write_log('Found Album ID %s' % album_id)
                try:
                    return self.keyword_search(':id %s' % album_id)
                except OldURLError:
                    write_log("Invalid URL used. Doing normal search.")

        if not album:
            raise RetrievalError('Album name required.')

        write_log('Searching for %s' % album)
        try:
            searchpage = search(album)
        except urllib.error.URLError as e:
            write_log('Error: While retrieving search page %s' %
                      str(e))
            raise RetrievalError(str(e))
        write_log('Retrieved search results.')

        search_results = parse_searchpage(searchpage, artist, album)
        if search_results:
            matched, matches = search_results
        else:
            return []

        if matched and len(matches) == 1:
            ret = [(matches[0], [])]
        elif matched:
            write_log('Ambiguous matches found for: %s - %s' %
                      (artist, album))
            ret.extend([(z, []) for z in matches])
        else:
            write_log('No exact matches found for: %s - %s' %
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
            write_log('Retrieving album.')
        write_log('Album URL - %s' % albuminfo['#albumurl'])
        url = albuminfo['#albumurl']
        try:
            if self._useid:
                info, tracks, cover = retrieve_album(url, self._getcover)
            else:
                info, tracks, cover = retrieve_album(url, self._getcover)
        except urllib.error.URLError as e:
            write_log('Error: While retrieving album URL %s - %s' %
                      (url, str(e)))
            raise RetrievalError(str(e))
        if cover:
            info.update(cover)
        albuminfo = albuminfo.copy()
        albuminfo.update(info)
        return albuminfo, tracks

    def applyPrefs(self, args):
        self._getcover = args[0]
        self._useid = args[1]


info = AllMusic

if __name__ == '__main__':
    f = get_encoding(open(sys.argv[1], 'r').read(), True)[1]
    x = parse_albumpage(f)
    print(x)
