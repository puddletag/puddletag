"""Mp3tag web source scripts (.src files) as puddletag loads, searches
and runs them. tagsources.txt says where they go and how they're
listed; Mp3tag's reference (docs.mp3tag.de/tag-sources/development/)
defines their header keys and commands. Every script here is synthetic
except jonaaa20's iTunes script (tests/data/mp3tag/, Apache-2.0); every
page is synthetic, in the layout of the service its script was written for.
"""
import json
import logging
from pathlib import Path

import pytest

from puddlestuff.mainwin.tagsources import load_mp3tag_sources, tag_source_search
from puddlestuff.tagsources import DEFAULT_USERAGENT, RetrievalError, discogs
from puddlestuff.util import split_by_field

ALBUM_PARSER = 'outputto "album"\nsayrest\n'
HEADER = {'AlbumUrl': 'https://example.org/album?id=', 'Name': 'Synthetic', 'SearchBy': '%album%'}
INDEX_HEADER = {'IndexFormat': '%_url%|%album%', 'IndexUrl': 'https://example.org/search?q=%s'}
INDEX_PARSER = 'sayrest\n'


def script(header=HEADER, index=None, album=ALBUM_PARSER):
    """A script's text: a "[Key]=value" line per header key, then each
    parser after its "[ParserScriptIndex]=..." or
    "[ParserScriptAlbum]=..." line, as Mp3tag's reference lays them out."""
    lines = [f'[{key}]={value}' for key, value in header.items()]
    if index is not None:
        lines += ['[ParserScriptIndex]=...', index]
    if album is not None:
        lines += ['[ParserScriptAlbum]=...', album]
    return '\n'.join(lines) + '\n'


@pytest.fixture
def folder(tmp_path):
    """The user's mp3tag_sources folder."""
    path = tmp_path / 'mp3tag_sources'
    path.mkdir()
    return path


def write(folder, text, filename='Synthetic.src', encoding='utf-8'):
    path = folder / filename
    path.write_text(text, encoding=encoding)
    return path


def loaded(folder):
    """The sources puddletag builds from the folder when it starts."""
    return load_mp3tag_sources(str(folder))


def load_one(folder, text):
    write(folder, text)
    [source] = loaded(folder)
    return source


def errors(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]


def test_script_that_fails_to_load_is_logged_and_left_out(folder, caplog):
    # tagsources.txt: "place any tag sources in there. If everything went
    # okay, they'll be loaded when you start puddletag." Synthetic: an
    # empty script. The file names match their [Name] on purpose.
    write(folder, script({**HEADER, 'Name': 'Good'}), 'Good.src')
    broken = write(folder, '', 'Broken.src')

    assert [s.name for s in loaded(folder)] == ['Good [M]']

    [message] = errors(caplog)
    assert message.startswith(f"Couldn't load Mp3tag Tag Source {broken}")


# Mp3tag's reference (docs.mp3tag.de/tag-sources/development/):
# - AlbumUrl: "Result base URL (URL result from first search pass will be
#   appended)"
# - IndexFormat: "splits the first search pass output into fields"
# - IndexUrl: "%s is replaced by the user's search criteria"
# - SearchBy: "Field(s) which are offered as search criteria"
@pytest.mark.parametrize('key, value, attribute', [
    ('AlbumUrl', 'https://example.org/release/', 'album_url'),
    ('IndexFormat', '%_url%|%album%|%artist%', 'indexformat'),
    ('IndexUrl', 'https://example.org/find?q=%s', '_search_base'),
    ('SearchBy', '%artist%', 'searchby'),
])
def test_header_keys_are_read(folder, key, value, attribute):
    # _search_base is private, but it is what the search reads to build
    # its URL.
    source = load_one(folder, script({**HEADER, **INDEX_HEADER, key: value},
                                     index=INDEX_PARSER))

    assert getattr(source, attribute) == value


def test_script_without_an_index_parser_loads(folder):
    # Synthetic: Mp3tag's reference doesn't say whether the index parser
    # is required.
    source = load_one(folder, script())

    assert source.search_source is None
    assert source.name == 'Synthetic [M]'


def test_header_keys_puddletag_does_not_use_still_load(folder):
    # Keys from Mp3tag's reference that puddletag has no use for.
    header = {
        **HEADER,
        'BasedOn': 'https://example.org',
        'Encoding': 'url-utf-8',
        'MinAppVersionMac': '1.8.4',
        'MinAppVersionWin': '3.22',
        'Settings': 'Synthetic#Settings.settings',
        'UserAgent': '1',
    }

    assert load_one(folder, script(header)).name == 'Synthetic [M]'


def test_only_src_files_are_loaded(folder):
    # tagsources.txt: "place any tag sources in there" for the .src
    # files; Mp3tag's reference: [Include] "references another web source
    # description file", which is not a source by itself.
    write(folder, script())
    write(folder, script({**HEADER, 'Name': 'Included'}), 'Synthetic Web.inc')
    write(folder, script({**HEADER, 'Name': 'Notes'}), 'notes.txt')
    write(folder, script({**HEADER, 'Name': 'Upper'}), 'Upper.SRC')

    assert [s.name for s in loaded(folder)] == ['Synthetic [M]']


def test_missing_folder_loads_nothing(tmp_path, caplog):
    # tagsources.txt: "create the directory
    # ~/.config/puddletag/mp3tag_sources", so a user who hasn't has no
    # scripts and no error.
    assert loaded(tmp_path / 'mp3tag_sources') == []
    assert errors(caplog) == []


INCLUDE_HEADER = {'Include': 'Synthetic Web.inc', 'IndexUrl': 'https://example.org/search?q=%s',
                  'SearchBy': 'Search for||%album%||%s'}


@pytest.mark.parametrize('text, encoding, reason', [
    pytest.param('', 'utf-8', 'no [Name] line', id='empty'),
    pytest.param(script(INCLUDE_HEADER, album=None), 'utf-8',
                 '[Include] is not supported (Synthetic Web.inc)', id='include'),
    pytest.param(script({**HEADER, 'IndexUrl': INDEX_HEADER['IndexUrl']}, index=INDEX_PARSER), 'utf-8',
                 'no [IndexFormat] line, which [ParserScriptIndex] needs', id='index-without-format'),
    pytest.param(script({**HEADER, 'IndexFormat': INDEX_HEADER['IndexFormat']}, index=INDEX_PARSER), 'utf-8',
                 'no [IndexUrl] line, which [ParserScriptIndex] needs', id='index-without-url'),
    pytest.param('[Oops\n' + script(), 'utf-8', 'line 1 is not a [Key]=value line: [Oops', id='malformed'),
    pytest.param(script(album=None), 'utf-8', 'no [ParserScriptAlbum] section', id='no-album-parser'),
    pytest.param(script({k: v for k, v in HEADER.items() if k != 'Name'}), 'utf-8',
                 'no [Name] line', id='no-name'),
    pytest.param(script({k: v for k, v in HEADER.items() if k != 'SearchBy'}), 'utf-8',
                 'no [SearchBy] line', id='no-search-by'),
    pytest.param(script({**HEADER, 'Name': 'Synthétique'}), 'latin-1', 'not UTF-8 text', id='not-utf-8'),
    pytest.param('# A comment\n', 'utf-8', 'no [Name] line', id='only-comments'),
])
def test_script_that_cannot_load_logs_why(folder, caplog, text, encoding, reason):
    # Mp3tag's reference lists the header keys; a script without the ones it
    # needs, or with a line it can't read, isn't loaded. Synthetic scripts.
    path = write(folder, text, encoding=encoding)
    assert loaded(folder) == []
    assert errors(caplog) == [f"Couldn't load Mp3tag Tag Source {path}: {reason}"]
    assert caplog.records[-1].exc_info is None


def test_script_with_a_byte_order_mark_loads(folder):
    # Synthetic: editors such as Notepad save UTF-8 text with a byte order
    # mark; it isn't part of the first line, [Name].
    write(folder, script({'Name': 'Synthetic', 'SearchBy': '%album%'}), encoding='utf-8-sig')
    assert [s.name for s in loaded(folder)] == ['Synthetic [M]']


def test_scripts_load_in_file_name_order(folder):
    # Synthetic: the sources are listed in the same order whatever order the
    # files were created in.
    for name in ('Charlie', 'Bravo', 'Alpha'):
        write(folder, script({**HEADER, 'Name': name}), filename=f'{name}.src')
    assert [s.name for s in loaded(folder)] == ['Alpha [M]', 'Bravo [M]', 'Charlie [M]']


def test_script_with_include_and_its_own_keys_still_loads(folder):
    # Mp3tag's reference: [Include] "references another web source
    # description file which is included into this file". puddletag doesn't
    # read the included file, so a script that has every key it needs
    # itself loads. Synthetic.
    source = load_one(folder, script({**HEADER, 'Include': 'Synthetic Web.inc'}))
    assert source.name == 'Synthetic [M]'


def test_word_separator_is_read(folder):
    # Mp3tag's reference: "[WordSeparator]: Character/string used instead
    # of blanks within the search criteria entered by the user", e.g. %20.
    source = load_one(folder, script({**HEADER, 'WordSeparator': '%20'}))
    assert source._separator == '%20'


def test_old_word_seperator_spelling_still_works(folder):
    # The reference spells the key [WordSeparator]. The maintainer's choice
    # (not a quote): puddletag keeps reading the old spelling too, for the
    # scripts written for it.
    source = load_one(folder, script({**HEADER, 'WordSeperator': '%20'}))
    assert source._separator == '%20'


def test_word_separator_wins_over_the_old_spelling(folder):
    # The reference only knows [WordSeparator]. The maintainer's choice
    # (not a quote): when a script has both spellings, [WordSeparator]
    # is the one used.
    header = {**HEADER, 'WordSeparator': '%20', 'WordSeperator': '-'}
    source = load_one(folder, script(header))
    assert source._separator == '%20'


def test_word_separator_defaults_to_plus(folder):
    # The reference gives no default for [WordSeparator]. The maintainer's
    # choice (not a quote): without the key, blanks become "+".
    source = load_one(folder, script())
    assert source._separator == '+'


# Searching and retrieving. The pages come from the local web server.

ITUNES = Path(__file__).parent.parent / 'data' / 'mp3tag' / 'iTunes#Spain.src'


@pytest.fixture
def server(web_server, monkeypatch):
    """The local web server, without the second Mp3tag scripts wait between
    requests: they download through Discogs' urlopen."""
    monkeypatch.setattr(discogs, '__minimum_request_separation', 0)
    return web_server


def local_header(server, **keys):
    """HEADER and INDEX_HEADER with their addresses on the local server."""
    return {**HEADER, **INDEX_HEADER, 'AlbumUrl': f'{server.url}/album?id=',
            'IndexUrl': f'{server.url}/search?q=%s', **keys}


def install_itunes(folder, server):
    """jonaaa20's iTunes script as a user installs it, with its iTunes
    address replaced by the local server's."""
    text = ITUNES.read_bytes().replace(b'https://itunes.apple.com', server.url.encode())
    (folder / ITUNES.name).write_bytes(text)
    [source] = loaded(folder)
    return source


def itunes_page(*results):
    """An answer in the iTunes Search API's layout, one result per line, as
    jonaaa20's script reads it."""
    lines = ', \n'.join(json.dumps(r, ensure_ascii=False, separators=(', ', ':')) for r in results)
    return f'\n\n\n{{\n "resultCount":{len(results)},\n "results": [\n{lines}]\n}}\n\n\n'


# Synthetic iTunes results. The keys keep iTunes' order: the script reads
# each value up to the next key.
def itunes_album(server, **changes):
    return {'wrapperType': 'collection', 'collectionType': 'Album', 'artistId': 11,
            'collectionId': 101, 'artistName': 'Synthétique Band', 'collectionName': 'First Light',
            'collectionCensoredName': 'First Light',
            'collectionViewUrl': 'https://music.example/album/101',
            'artworkUrl100': f'{server.url}/cover.jpg', 'collectionPrice': 9.99,
            'collectionExplicitness': 'notExplicit', 'trackCount': 2,
            'copyright': '℗ 2001 Synthetic Records', 'country': 'ESP', 'currency': 'EUR',
            'releaseDate': '2001-03-12T08:00:00Z', 'primaryGenreName': 'Electrónica', **changes}


def itunes_track(number, title):
    return {'wrapperType': 'track', 'kind': 'song', 'artistId': 11, 'collectionId': 101,
            'trackId': 1000 + number, 'artistName': 'Synthétique Band',
            'collectionName': 'First Light', 'trackName': title,
            'collectionCensoredName': 'First Light', 'trackCensoredName': title,
            'collectionViewUrl': 'https://music.example/album/101',
            'previewUrl': 'https://music.example/preview.m4a',
            'artworkUrl100': 'https://music.example/cover.jpg', 'collectionPrice': 9.99,
            'trackPrice': 0.99, 'releaseDate': '2001-03-12T08:00:00Z',
            'collectionExplicitness': 'notExplicit', 'trackExplicitness': 'notExplicit',
            'discCount': 1, 'discNumber': 1, 'trackCount': 2, 'trackNumber': number,
            'trackTimeMillis': 200000 + number, 'country': 'ESP', 'currency': 'EUR',
            'primaryGenreName': 'Electrónica', 'isStreamable': True}


SECOND_ALBUM = {'artistName': 'Other Band', 'collectionCensoredName': 'Second Light',
                'collectionId': 202, 'collectionName': 'Second Light',
                'collectionViewUrl': 'https://music.example/album/202',
                'releaseDate': '1999-01-01T08:00:00Z'}


def requested(server):
    return [(r.path, r.raw_query) for r in server.requests]


def search_files(source, files):
    """What the Tag Sources window does when files are selected and the
    Search box is empty."""
    return tag_source_search(source, split_by_field(files, *source.group_by), files)[0]


DECODE = pytest.mark.xfail(strict=True, raises=TypeError,
                           reason='the downloaded page is passed on as bytes, not text')


def serve_itunes_album(server):
    """One album in the search answer, and it with two tracks in the album
    page's."""
    server.add('/search', itunes_page(itunes_album(server)))
    server.add('/lookup', itunes_page(itunes_album(server), itunes_track(1, 'Dawn'),
                                      itunes_track(2, 'Dusk')))


def retrieve_itunes_album(folder, server, covers=False):
    serve_itunes_album(server)
    source = install_itunes(folder, server)
    source.applyPrefs([covers])
    [(result, _)] = source.keyword_search('First Light')
    return source.retrieve(result)


@DECODE
def test_search_box_search_requests_index_url(folder, server):
    # Mp3tag's reference: [IndexUrl] "Search URL where %s is replaced by the
    # search criteria entered by the user"; [WordSeparator] "Character/string
    # used instead of blanks within the search criteria". jonaaa20's script
    # sets "+".
    server.add('/search', itunes_page(itunes_album(server)))

    install_itunes(folder, server).keyword_search('Daft Punk Discovery')

    assert requested(server) == [('/search', 'country=ES&entity=album&term=Daft+Punk+Discovery')]


@DECODE
def test_search_lists_each_album_by_index_format(folder, server):
    # tagsources.txt: "You can search as you do using Mp3tag by using the
    # Search box"; Mp3tag's reference, [IndexFormat]: "Format string for
    # splitting the output buffer from the first search pass into different
    # fields ... %_url% is mandatory". The explicitness is left out: the
    # script's replace lines shape it, and the commands' tests cover them.
    server.add('/search', itunes_page(itunes_album(server), itunes_album(server, **SECOND_ALBUM)))

    results = install_itunes(folder, server).keyword_search('Light')

    assert [({k: v for k, v in info.items() if k != 'explicitness'}, tracks)
            for info, tracks in results] == [
        ({'#url': '101&entity=song&limit=200', '_preview': 'https://music.example/album/101',
          'album': 'First Light', 'artist': 'Synthétique Band',
          'copyright': '℗ 2001 Synthetic Records', 'tracks': '2', 'year': '2001'}, []),
        ({'#url': '202&entity=song&limit=200', '_preview': 'https://music.example/album/202',
          'album': 'Second Light', 'artist': 'Other Band',
          'copyright': '℗ 2001 Synthetic Records', 'tracks': '2', 'year': '1999'}, []),
    ]


@DECODE
def test_retrieve_requests_album_url_with_the_result_url_appended(folder, server):
    # Mp3tag's reference, [AlbumUrl]: "Result base URL (URL result from first
    # search pass will be appended)". The "&entity=song&limit=200" twice is
    # the script's own: its index parser says it and so does its [AlbumUrl].
    info, tracks = retrieve_itunes_album(folder, server)

    assert requested(server)[1:] == [
        ('/lookup', 'country=ES&entity=song&limit=200&id=101&entity=song&limit=200')]
    assert info['#url'] == f'{server.url}/lookup?country=ES&entity=song&limit=200&id=101&entity=song&limit=200'


@DECODE
def test_retrieve_gives_the_album_page_fields(folder, server):
    # The result list's fields stay and the album page's are added. The
    # explicitness, label and currenturl are left out (the commands' tests
    # cover them). The year is the script's: it reads releaseDate up to the
    # next key.
    info, tracks = retrieve_itunes_album(folder, server)

    assert {'#cover-url': f'{server.url}/cover.jpg', 'album': 'First Light',
            'albumartist': 'Synthétique Band', 'albumsort': 'First Light',
            'artist': 'Synthétique Band', 'artistsort': 'Synthétique Band',
            'copyright': '℗ 2001 Synthetic Records', 'tracks': '2',
            'year': '2001-03-12T08:00:00Z'}.items() <= info.items()


@pytest.mark.xfail(strict=True, reason='the last track comes out twice')
def test_retrieve_gives_one_entry_per_track(folder, server):
    # Mp3tag's reference: "Mp3tag expects the output buffer to contain the
    # individual values separated and finalized by the pipe character".
    info, tracks = retrieve_itunes_album(folder, server)

    assert [(t['title'], t['__length'], t['itunescatalogid']) for t in tracks] == [
        ('Dawn', '200001', '1001'), ('Dusk', '200002', '1002')]


@DECODE
def test_retrieve_downloads_the_cover(folder, server):
    # Docs-silent: the Retrieve Covers preference is puddletag's own, on by
    # default.
    server.add('/cover.jpg', b'synthetic cover', content_type='image/jpeg')

    info, tracks = retrieve_itunes_album(folder, server, covers=True)

    assert info['__image'] == [{'data': b'synthetic cover'}]
    assert requested(server)[-1] == ('/cover.jpg', '')


@pytest.mark.xfail(strict=True, reason='the downloaded page is passed on as bytes, not text')
def test_script_without_index_parser_goes_to_the_album_page(folder, server):
    # Synthetic: Mp3tag's reference doesn't say whether the index parser is
    # required. Without one, the search words are appended to [AlbumUrl]
    # and the album page is the result. The xfail has no raises=: retrieve
    # swallows the TypeError.
    server.add('/album', 'Synthetic album page')
    source = load_one(folder, script({**HEADER, 'AlbumUrl': f'{server.url}/album?id='}))

    results = source.keyword_search('First Light')

    assert requested(server) == [('/album', 'id=First+Light')]
    assert [(info['album'], tracks) for info, tracks in results] == [('Synthetic album page', None)]


@DECODE
def test_page_declaring_another_encoding_is_read_in_it(folder, server):
    # Synthetic: a page whose XML declaration names ISO-8859-1.
    server.add('/search', '<?xml version="1.0" encoding="ISO-8859-1"?>\nu1|Café\n'.encode('latin-1'))
    source = load_one(folder, script(local_header(server), index='findline "|"\nsayrest\n'))

    assert source.keyword_search('Cafe') == [({'#url': 'u1', 'album': 'Café'}, [])]


@DECODE
def test_bytes_that_are_not_utf8_do_not_stop_the_search(folder, server):
    # Synthetic: Latin-1 bytes in a page that declares no encoding.
    server.add('/search', b'u1|Caf\xe9\n')
    source = load_one(folder, script(local_header(server), index=INDEX_PARSER))

    assert source.keyword_search('Cafe') == [({'#url': 'u1', 'album': 'Caf�'}, [])]


@DECODE
def test_search_without_results_finds_nothing(folder, server):
    # Synthetic: an empty page. The window then says "No matching albums
    # were found."
    server.add('/search', '')
    source = load_one(folder, script(local_header(server), index=INDEX_PARSER))

    assert source.keyword_search('Nothing') == []


@pytest.mark.xfail(strict=True, reason="a findline that finds nothing doesn't stop the script")
def test_itunes_answer_without_results_finds_nothing(folder, server):
    # Mp3tag's reference, FindLine: "An optional third parameter set to 1
    # suppresses the error when S is not found", so a line that isn't found
    # is an error that ends the script.
    server.add('/search', itunes_page())

    assert install_itunes(folder, server).keyword_search('Nothing') == []


@pytest.mark.parametrize('status, message', [
    (404, 'HTTP Error 404: Not Found'),
    (500, 'HTTP Error 500: Internal Server Error'),
])
def test_search_page_error_is_reported(folder, server, status, message):
    # The window shows it as "An error occured: <message>". Synthetic error
    # pages.
    server.add('/search', 'Synthetic error page', status=status)
    source = load_one(folder, script(local_header(server), index=INDEX_PARSER))

    with pytest.raises(RetrievalError) as error:
        source.keyword_search('First Light')

    assert str(error.value) == message


@pytest.mark.xfail(strict=True, reason="retrieve swallows the album page's download error")
def test_album_page_error_is_reported(folder, server):
    # Synthetic: the album page answers 404.
    server.add('/album', 'Synthetic error page', status=404)
    source = load_one(folder, script(local_header(server)))

    with pytest.raises(RetrievalError, match='^HTTP Error 404: Not Found$'):
        source.retrieve({'#url': 'u1', 'album': 'First Light'})
