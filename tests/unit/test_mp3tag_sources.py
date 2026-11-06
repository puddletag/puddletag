"""Mp3tag web source scripts (.src files) as puddletag loads, searches
and runs them. tagsources.txt says where they go and how they're
listed; Mp3tag's reference (docs.mp3tag.de/tag-sources/development/)
defines their header keys and commands. Every script here is synthetic
except the iTunes script in tests/data/mp3tag/ (Apache-2.0); every
page is synthetic, in the layout of the service its script was written for.
"""
import json
import logging
from pathlib import Path

import pytest

from puddlestuff.mainwin.tagsources import load_mp3tag_sources, tag_source_search
from puddlestuff.tagsources import DEFAULT_USERAGENT, RetrievalError, discogs, mp3tag
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
    pytest.param(script({**HEADER, 'Name': 'Synthétique'}), 'latin-1', 'not UTF-8 text', id='not-utf-8'),
    pytest.param('# A comment\n', 'utf-8', 'no [Name] line', id='only-comments'),
    pytest.param(script({**HEADER, **INDEX_HEADER}, index='sayrest\nSkipChars " "\n'), 'utf-8',
                 "line 8 uses a command puddletag doesn't have: SkipChars",
                 id='unknown-command', marks=pytest.mark.xfail(
                     strict=True, raises=AssertionError,
                     reason="a command puddletag doesn't have is found only when the page is parsed, as a KeyError")),
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
    monkeypatch.setattr(discogs, '_wait', lambda: None)
    return web_server


def local_header(server, **keys):
    """HEADER and INDEX_HEADER with their addresses on the local server."""
    return {**HEADER, **INDEX_HEADER, 'AlbumUrl': f'{server.url}/album?id=',
            'IndexUrl': f'{server.url}/search?q=%s', **keys}


def install_itunes(folder, server):
    """The iTunes script as a user installs it, with its iTunes
    address replaced by the local server's."""
    text = ITUNES.read_bytes().replace(b'https://itunes.apple.com', server.url.encode())
    (folder / ITUNES.name).write_bytes(text)
    [source] = loaded(folder)
    return source


def itunes_page(*results):
    """An answer in the iTunes Search API's layout, one result per line, as
    the iTunes script reads it."""
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


def test_search_box_search_requests_index_url(folder, server):
    # Mp3tag's reference: [IndexUrl] "Search URL where %s is replaced by the
    # search criteria entered by the user"; [WordSeparator] "Character/string
    # used instead of blanks within the search criteria". The iTunes script
    # sets "+".
    server.add('/search', itunes_page(itunes_album(server)))

    install_itunes(folder, server).keyword_search('Daft Punk Discovery')

    assert requested(server) == [('/search', 'country=ES&entity=album&term=Daft+Punk+Discovery')]


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


def test_retrieve_requests_album_url_with_the_result_url_appended(folder, server):
    # Mp3tag's reference, [AlbumUrl]: "Result base URL (URL result from first
    # search pass will be appended)". The "&entity=song&limit=200" twice is
    # the script's own: its index parser says it and so does its [AlbumUrl].
    info, tracks = retrieve_itunes_album(folder, server)

    assert requested(server)[1:] == [
        ('/lookup', 'country=ES&entity=song&limit=200&id=101&entity=song&limit=200')]
    assert info['#url'] == f'{server.url}/lookup?country=ES&entity=song&limit=200&id=101&entity=song&limit=200'


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


def test_retrieve_downloads_the_cover(folder, server):
    # Docs-silent: the Retrieve Covers preference is puddletag's own, on by
    # default.
    server.add('/cover.jpg', b'synthetic cover', content_type='image/jpeg')

    info, tracks = retrieve_itunes_album(folder, server, covers=True)

    assert info['__image'] == [{'data': b'synthetic cover'}]
    assert requested(server)[-1] == ('/cover.jpg', '')


def test_script_without_index_parser_goes_to_the_album_page(folder, server):
    # Synthetic: Mp3tag's reference doesn't say whether the index parser is
    # required. Without one, the search words are appended to [AlbumUrl]
    # and the album page is the result.
    server.add('/album', 'Synthetic album page')
    source = load_one(folder, script({**HEADER, 'AlbumUrl': f'{server.url}/album?id='}))

    results = source.keyword_search('First Light')

    assert requested(server) == [('/album', 'id=First+Light')]
    assert [(info['album'], tracks) for info, tracks in results] == [('Synthetic album page', None)]


def test_page_declaring_another_encoding_is_read_in_it(folder, server):
    # Synthetic: a page whose XML declaration names ISO-8859-1.
    server.add('/search', '<?xml version="1.0" encoding="ISO-8859-1"?>\nu1|Café\n'.encode('latin-1'))
    source = load_one(folder, script(local_header(server), index='findline "|"\nsayrest\n'))

    assert source.keyword_search('Cafe') == [({'#url': 'u1', 'album': 'Café'}, [])]


def test_bytes_that_are_not_utf8_do_not_stop_the_search(folder, server):
    # Synthetic: Latin-1 bytes in a page that declares no encoding.
    server.add('/search', b'u1|Caf\xe9\n')
    source = load_one(folder, script(local_header(server), index=INDEX_PARSER))

    assert source.keyword_search('Cafe') == [({'#url': 'u1', 'album': 'Caf�'}, [])]


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
    # The window shows it as "An error occurred: <message>". Synthetic error
    # pages.
    server.add('/search', 'Synthetic error page', status=status)
    source = load_one(folder, script(local_header(server), index=INDEX_PARSER))

    with pytest.raises(RetrievalError) as error:
        source.keyword_search('First Light')

    assert str(error.value) == message


def test_album_page_error_is_reported(folder, server):
    # Synthetic: the album page answers 404.
    server.add('/album', 'Synthetic error page', status=404)
    source = load_one(folder, script(local_header(server)))

    with pytest.raises(RetrievalError, match='^HTTP Error 404: Not Found$'):
        source.retrieve({'#url': 'u1', 'album': 'First Light'})


# Synthetic selected files: two albums, the first on two files.
SELECTED_ALBUMS = [
    {'album': ['First Light'], 'artist': ['Synthetic Band']},
    {'album': ['Second Light'], 'artist': ['Other Band']},
    {'album': ['First Light'], 'artist': ['Synthetic Band']},
]

# Synthetic, modelled on the [SearchBy] of a script shared in an issue
# (that script has no license).
MP3TAG_FUNCTION_SEARCH_BY = r"%artist% $regexp(%album%,'[- ]+cd ?\d+$',,1)"


def test_selected_files_are_searched_once_per_album(folder, server):
    # tagsources.txt: "Selecting files and searching works too."; Mp3tag's
    # reference, SearchBy: "Field(s) which are offered as search criteria".
    server.add('/search', 'u1|First Light')
    source = load_one(folder, script(local_header(server), index=INDEX_PARSER))

    search_files(source, SELECTED_ALBUMS)

    assert [q for _, q in requested(server)] == ['q=First+Light', 'q=Second+Light']


def test_search_by_two_fields_searches_each_selected_album(folder, server):
    # Mp3tag's reference, SearchBy: "Field(s) which are offered as search
    # criteria".
    server.add('/search', 'u1|First Light')
    header = local_header(server, SearchBy='%artist% %album%')
    source = load_one(folder, script(header, index=INDEX_PARSER))

    search_files(source, SELECTED_ALBUMS)

    assert [q for _, q in requested(server)] == ['q=Synthetic+Band+First+Light', 'q=Other+Band+Second+Light']


def test_selected_files_without_the_field_are_skipped(folder, server):
    # Synthetic: the second file has no album. The files that do have one
    # are still searched.
    server.add('/search', 'u1|First Light')
    source = load_one(folder, script(local_header(server), index=INDEX_PARSER))
    files = [{'album': ['First Light']}, {'artist': ['Synthetic Band']}]

    assert search_files(source, files) == [({'#url': 'u1', 'album': 'First Light'}, [])]
    assert [q for _, q in requested(server)] == ['q=First+Light']


def test_no_request_when_no_selected_file_has_the_field(folder, server):
    # Synthetic: no selected file has an album.
    source = load_one(folder, script(local_header(server), index=INDEX_PARSER))

    assert search_files(source, [{'artist': ['Synthetic Band']}]) == []
    assert server.requests == []


def test_retry_without_the_brackets_searches_the_shorter_album(folder, server):
    # Synthetic: the Tag Sources window retries a search that finds nothing
    # with the album's bracketed part removed.
    server.add('/search', 'u1|First Light')
    server.add('/search', '', query={'q': 'First Light (Deluxe)'})
    source = load_one(folder, script(local_header(server), index=INDEX_PARSER))

    search_files(source, [{'album': ['First Light (Deluxe)']}])

    queries = [q for _, q in requested(server)]
    assert len(queries) == 2
    assert queries[1] == 'q=First+Light'


@pytest.mark.parametrize('search_by, expected', [
    ('%album%', '<b>%album%</b>'),
    ('%artist% %album%', '<b>%artist% %album%</b>'),
    ('Search for||%album%||%s', '<b>Search for||%album%||%s</b>'),
])
def test_tooltip_names_the_search_by_fields(folder, search_by, expected):
    # tagsources.txt: "See the tooltip for the fields used to search the
    # selected files."
    source = load_one(folder, script({**HEADER, 'SearchBy': search_by}))

    assert expected in source.tooltip


def test_tooltip_goes_through_translate(folder, monkeypatch):
    # Synthetic: the tooltip is user-visible text.
    monkeypatch.setattr('puddlestuff.tagsources.mp3tag.translate',
                        lambda context, text: f'<<{text}>>')

    assert load_one(folder, script()).tooltip.startswith('<<<p>Enter search keywords here.')


def test_search_by_with_mp3tag_functions_says_so(folder, server):
    # tagsources.txt: searching selected files works for a [SearchBy] of
    # plain fields, "not Mp3tag's functions". Synthetic [SearchBy].
    server.add('/search', 'u1|First Light')
    source = load_one(folder, script(local_header(server, SearchBy=MP3TAG_FUNCTION_SEARCH_BY),
                                     index=INDEX_PARSER))

    with pytest.raises(RetrievalError, match=r"^\[SearchBy\] uses a function puddletag doesn't have"):
        search_files(source, SELECTED_ALBUMS)


def test_search_box_works_with_mp3tag_functions_in_search_by(folder, server):
    # tagsources.txt: "You can search as you do using Mp3tag by using the
    # Search box."
    server.add('/search', 'u1|First Light')
    source = load_one(folder, script(local_header(server, SearchBy=MP3TAG_FUNCTION_SEARCH_BY),
                                     index=INDEX_PARSER))

    source.keyword_search('First Light')

    assert requested(server) == [('/search', 'q=First+Light')]


def test_script_without_search_by_can_search_with_the_search_box(folder, server):
    # Mp3tag's reference doesn't make [SearchBy] required. Synthetic script
    # without it.
    server.add('/search', 'u1|First Light')
    header = {k: v for k, v in local_header(server).items() if k != 'SearchBy'}
    source = load_one(folder, script(header, index=INDEX_PARSER))

    assert source.group_by == ['album', None]
    assert source.keyword_search('First Light') == [({'#url': 'u1', 'album': 'First Light'}, [])]


def test_script_without_search_by_says_so_for_selected_files(folder, server):
    server.add('/search', 'u1|First Light')
    header = {k: v for k, v in local_header(server).items() if k != 'SearchBy'}
    source = load_one(folder, script(header, index=INDEX_PARSER))

    with pytest.raises(RetrievalError, match=r'^This script has no \[SearchBy\] line\. '
                                             r'Type the search in the Search box\.$'):
        search_files(source, SELECTED_ALBUMS)


def test_search_by_with_several_search_fields_says_so(folder, server):
    # Synthetic: the [SearchBy] value of Mp3tag scripts that offer several
    # search fields, written "Name||%field%||%s".
    server.add('/search', 'u1|First Light')
    source = load_one(folder, script(local_header(server, SearchBy='Search for||%album%||%s'),
                                     index=INDEX_PARSER))

    with pytest.raises(RetrievalError, match=r'^\[SearchBy\] with several search fields \(\|\|\) '
                                             r"isn't supported\. Type the search in the Search box\.$"):
        search_files(source, SELECTED_ALBUMS)


# Mp3tag's reference:
# - Encoding: "Encoding used for all URLs. Can be utf-8, iso-8859-1, url,
#   url-utf-8, or ansi"
# puddletag always uses UTF-8 for the words it puts in the address.
@pytest.mark.parametrize('words, query', [
    ('Simon & Garfunkel #1', 'q=Simon+%26+Garfunkel+%231'),
    ('Sigur Rós', 'q=Sigur+R%C3%B3s'),
])
def test_search_words_are_percent_encoded(folder, server, words, query):
    # Synthetic: an [Encoding] of url-utf-8 and words with characters
    # that mean something in an address.
    server.add('/search', 'u1|First Light')
    source = load_one(folder, script(local_header(server, Encoding='url-utf-8'),
                                     index=INDEX_PARSER))

    source.keyword_search(words)

    assert requested(server) == [('/search', query)]


def test_word_separator_is_not_encoded(folder, server):
    # Mp3tag's reference: [WordSeparator] "Character/string used instead
    # of blanks within the search criteria, e.g., `%20` or `+`".
    server.add('/search', 'u1|First Light')
    source = load_one(folder, script(local_header(server, WordSeparator='%20'),
                                     index=INDEX_PARSER))

    source.keyword_search('Daft Punk')

    assert requested(server) == [('/search', 'q=Daft%20Punk')]


def test_blanks_in_a_row_are_one_separator(folder, server):
    # Synthetic: three blanks between the words.
    server.add('/search', 'u1|First Light')
    source = load_one(folder, script(local_header(server), index=INDEX_PARSER))

    source.keyword_search('Daft   Punk')

    assert requested(server) == [('/search', 'q=Daft+Punk')]


@pytest.mark.parametrize('keys', [{}, {'UserAgent': '1'}])
def test_search_sends_puddletags_user_agent(folder, server, keys):
    # Mp3tag's reference: [UserAgent] "If set to `1`, Mp3tag uses its name
    # and version number as user agent". puddletag sends its own whatever
    # the script says.
    server.add('/search', 'u1|First Light')
    source = load_one(folder, script(local_header(server, **keys), index=INDEX_PARSER))

    source.keyword_search('First Light')

    assert server.requests[0].headers['User-Agent'] == DEFAULT_USERAGENT


def test_percent_sign_in_album_url_is_kept(folder, server):
    # Mp3tag's reference: [AlbumUrl] "will be appended" to the result's
    # address.
    server.add('/album', 'Synthetic album page')
    header = local_header(server, AlbumUrl=f'{server.url}/album?term=a%20b&id=')
    source = load_one(folder, script(header, index=INDEX_PARSER))

    source.retrieve({'#url': 'u1'})

    assert requested(server) == [('/album', 'term=a%20b&id=u1')]


def test_percent_s_in_album_url_is_replaced_by_the_result_url(folder, server):
    # Docs-silent: a %s in [AlbumUrl] is where the result's address goes,
    # as in [IndexUrl].
    server.add('/album/u1/tracks', 'Synthetic album page')
    header = local_header(server, AlbumUrl=f'{server.url}/album/%s/tracks')
    source = load_one(folder, script(header, index=INDEX_PARSER))

    source.retrieve({'#url': 'u1'})

    assert requested(server) == [('/album/u1/tracks', '')]


def test_cover_that_cannot_be_downloaded_leaves_the_album(folder, server, monkeypatch):
    # Docs-silent: the album still arrives, without its cover; the error
    # goes to the Tag Sources window's log.
    lines = []
    monkeypatch.setattr(mp3tag, 'write_log', lines.append)
    server.add('/cover.jpg', 'Synthetic error page', status=404)

    info, tracks = retrieve_itunes_album(folder, server, covers=True)

    assert info['album'] == 'First Light'
    assert '__image' not in info
    assert "Couldn't retrieve the cover: HTTP Error 404: Not Found" in lines


# The parser commands, each against Mp3tag's reference
# (docs.mp3tag.de/tag-sources/development/). Every page is synthetic.

PAGE = ('line one\n'
        '<b>Artist:</b> Foo Bar  Year: 1999 end\n'
        'line three <i>x</i> tail\n'
        'line four\n'
        'line five')


def parse_album(folder, parser, page=PAGE):
    """The album's fields and its tracks, as the script's album parser
    `parser` reads them from `page` for Retrieve."""
    source = load_one(folder, script(album=parser))
    return mp3tag.parse_album_page(page, source.album_source)


def album_fields(folder, parser, page=PAGE):
    return parse_album(folder, parser, page)[0]


def test_say_sends_its_text(folder):
    # Mp3tag's reference: "Send S to output"
    parser = 'outputto "album"\nsay "hi"\nsay "!"\n'

    assert album_fields(folder, parser) == {'album': 'hi!'}


def test_sayrest_says_the_rest_of_the_line(folder):
    # Mp3tag's reference: "Send everything to the end of the current line to output"
    parser = 'outputto "album"\nfindline "three"\nsayrest\n'

    assert album_fields(folder, parser) == {'album': 'line three <i>x</i> tail'}


@pytest.mark.xfail(strict=True, reason="SayRest leaves the pointer on the line's last character, so the next Say command says it again")
def test_second_sayrest_says_nothing_more(folder):
    # Docs-silent: the maintainer's choice (not a quote): after SayRest the
    # pointer is past the line's end, so the next Say command says nothing.
    parser = 'outputto "album"\nsayrest\nsayrest\n'

    assert album_fields(folder, parser) == {'album': 'line one'}


@pytest.mark.parametrize('parser, expected', [
    ('findline "Artist"\nfindinline "</b>"\nsayuntil "Year"\n',
     {'album': 'Foo Bar'}),
    ('findline "Artist"\nsayuntil "Foo"\noutputto "artist"\nsayrest\n',
     {'album': '<b>Artist:</b>', 'artist': 'Foo Bar  Year: 1999 end'}),
])
def test_sayuntil_says_up_to_the_text(folder, parser, expected):
    # Mp3tag's reference: "Send everything until S to output". Docs-silent
    # for the pointer, the maintainer's choice (not a quote): it stays on S.
    assert album_fields(folder, 'outputto "album"\n' + parser) == expected


@pytest.mark.xfail(strict=True, reason="SayUntil without the text leaves the pointer on the line's last character, so the next Say command says it again")
def test_sayuntil_without_the_text_says_the_rest(folder):
    # Docs-silent: the maintainer's choice (not a quote): the rest of the
    # line is said and the pointer is past its end.
    parser = 'outputto "album"\nsayuntil "zzz"\nsayrest\n'

    assert album_fields(folder, parser) == {'album': 'line one'}


@pytest.mark.xfail(strict=True, reason="SayNChars says one character fewer, leaving out the first")
@pytest.mark.parametrize('parser, expected', [
    ('findline "three"\nsaynchars 4\noutputto "artist"\nsayrest\n',
     {'album': 'line', 'artist': 'three <i>x</i> tail'}),
    ('findline "Artist"\ngotochar 4\nsaynchars 6\n',
     {'album': 'Artist'}),
])
def test_saynchars_says_n_characters(folder, parser, expected):
    # Mp3tag's reference: "Send next N characters to output"
    assert album_fields(folder, 'outputto "album"\n' + parser) == expected


@pytest.mark.parametrize('parser, expected', [
    ('findline "Year:"\nfindinline "Year:"\nsaynextnumber\n',
     {'album': '1999'}),
    ('findline "Artist"\nfindinline "</b>"\nsaynextword\n',
     {'album': 'Foo'}),
])
def test_saynext_says_the_next_number_or_word(folder, parser, expected):
    # Mp3tag's reference: "Outputs the next numeric value from the input."
    # and "Outputs the next word from the input."
    assert album_fields(folder, 'outputto "album"\n' + parser) == expected


@pytest.mark.xfail(strict=True, reason="SayNextNumber and SayNextWord move the pointer by the length of what they say, not past it")
@pytest.mark.parametrize('parser, expected', [
    ('findline "Year:"\nsaynextnumber\noutputto "artist"\nsayrest\n',
     {'album': '1999', 'artist': 'end'}),
    ('findline "Artist"\nfindinline "</b>"\nsaynextword\noutputto "artist"\nsayrest\n',
     {'album': 'Foo', 'artist': 'Bar  Year: 1999 end'}),
])
def test_saynext_moves_past_what_it_says(folder, parser, expected):
    # Docs-silent: the maintainer's choice (not a quote): the pointer is
    # left just past the number or word said.
    assert album_fields(folder, 'outputto "album"\n' + parser) == expected


@pytest.mark.xfail(strict=True, raises=AttributeError, reason="SayNextWord raises when the rest of the line has no word")
def test_saynextword_without_a_word_says_nothing(folder):
    # Docs-silent: the maintainer's choice (not a quote): with nothing to
    # say, nothing is said and the script goes on.
    parser = ('outputto "album"\nfindline "line four"\nfindinline "four"\n'
              'saynextword\nsay "!"\n')

    assert album_fields(folder, parser) == {'album': '!'}


def test_saynewline_starts_a_new_line(folder):
    # Mp3tag's reference: "Outputs a carriage return, line feed (CR LF)
    # sequence." The maintainer's choice (not a quote): puddletag says "\n".
    parser = 'outputto "album"\nsay "a"\nsaynewline\nsay "b"\n'

    assert album_fields(folder, parser) == {'album': 'a\nb'}


def test_saynewline_separates_search_results(folder):
    # Mp3tag's reference, [IndexFormat]: "Format string for splitting the
    # output buffer from the first search pass into different fields".
    # The iTunes script's index parser ends each result with SayNewline.
    source = load_one(folder, script({**HEADER, **INDEX_HEADER}, index='say "u1|First"\nsaynewline\nsay "u2|Second"\n'))

    results = mp3tag.parse_search_page(source.indexformat, PAGE, source.search_source)

    assert results == [{'#url': 'u1', 'album': 'First'},
                       {'#url': 'u2', 'album': 'Second'}]


@pytest.mark.xfail(strict=True, reason="SayRegexp without a separator says only the first match")
def test_sayregexp_says_every_match_separated_by_a_space(folder):
    # Mp3tag's reference: "Outputs all matches of the regular expression in
    # the first parameter separated by the string in the second parameter,
    # which defaults to the space character."
    parser = 'outputto "album"\nfindline "Artist"\nsayregexp "[A-Z][a-z]+"\n'

    assert album_fields(folder, parser) == {'album': 'Artist Foo Bar Year'}


@pytest.mark.parametrize('arguments, expected', [
    ('", "', {'album': 'Artist, Foo, Bar, Year'}),
    ('"," "Year"', {'album': 'Artist,Foo,Bar'}),
    ('"," "zzz"', {}),
])
def test_sayregexp_with_separator_and_end(folder, arguments, expected):
    # Mp3tag's reference: "If the third parameter is provided, the match is
    # only performed till the third parameter content is reached. If the
    # third parameter content cannot be found, the line is ignored."
    parser = f'outputto "album"\nfindline "Artist"\nsayregexp "[A-Z][a-z]+" {arguments}\n'

    assert album_fields(folder, parser) == expected


@pytest.mark.xfail(strict=True, raises=AttributeError, reason="SayRegexp without a separator raises when nothing matches")
def test_sayregexp_without_a_match_says_nothing(folder):
    # Docs-silent: the maintainer's choice (not a quote): with no match,
    # nothing is said and the script goes on.
    parser = 'outputto "album"\nfindline "Artist"\nsayregexp "[0-9]{5}"\nsay "!"\n'

    assert album_fields(folder, parser) == {'album': '!'}


@pytest.mark.xfail(strict=True, reason="SayUntilML keeps the space puddletag adds at each line's end")
def test_sayuntilml_says_across_lines(folder):
    # Mp3tag's reference: "Send everything until S to output searching
    # across multiple lines". Docs-silent for the joins, the maintainer's
    # choice (not a quote): the lines are joined with "\n", each stripped.
    parser = 'outputto "album"\nfindline "three"\nsayuntilml "five"\n'

    assert album_fields(folder, parser) == {'album': 'line three <i>x</i> tail\nline four\nline'}


@pytest.mark.xfail(strict=True, reason="SayUntilML leaves the pointer one character past the text's position in the line")
def test_sayuntilml_leaves_the_pointer_on_the_text(folder):
    # Docs-silent: the maintainer's choice (not a quote): as SayUntil, the
    # pointer stays on S.
    parser = ('outputto "album"\nfindline "three"\nfindinline "three"\n'
              'sayuntilml "four"\noutputto "artist"\nsayrest\n')

    assert album_fields(folder, parser) == {'album': '<i>x</i> tail\nline', 'artist': 'four'}


@pytest.mark.parametrize('commands, expected', [
    # Mp3tag's reference, FindLine: "Find line with first or Nth occurrence
    # of S (starting from the current position)."
    ('findline "four"\nsayrest', {'album': 'line four'}),
    ('findline "line" 3\nsayrest', {'album': 'line four'}),
    # Docs-silent: the maintainer's choice (not a quote): the current line
    # counts as the first occurrence (the iTunes script's loop relies on it).
    ('findline "line four"\nfindline "line"\nsayrest', {'album': 'line four'}),
    # Docs-silent: the maintainer's choice (not a quote): a negative N
    # searches upwards from the line above.
    ('findline "line five"\nfindline "line" -2\nsayrest',
     {'album': 'line three <i>x</i> tail'}),
    # Mp3tag's reference, FindLineNoCase: the same "(ignoring case and
    # starting from the current position)".
    ('findlinenocase "LINE FOUR"\nsayrest', {'album': 'line four'}),
], ids=['first', 'nth', 'current-line', 'upwards', 'nocase'])
def test_findline_finds_the_line(folder, commands, expected):
    assert album_fields(folder, 'outputto "album"\n' + commands) == expected


@pytest.mark.xfail(strict=True, reason="a FindLine, FindLineNoCase or FindInLine that finds nothing doesn't stop the script")
@pytest.mark.parametrize('commands', [
    'say "before"\nfindline "zzz"\noutputto "artist"\nsay "after"',
    'say "before"\nfindlinenocase "ZZZ"\noutputto "artist"\nsay "after"',
    'say "before"\nfindline "Artist"\nfindinline "zzz"\noutputto "artist"\nsay "after"',
], ids=['findline', 'findlinenocase', 'findinline'])
def test_find_that_finds_nothing_stops_the_script(folder, commands):
    # Mp3tag's reference, FindLine: "If the 3rd parameter is set to 1, no
    # error is produced if S is not found", so without it, not finding S is
    # an error. Docs-silent: the maintainer's choice (not a quote): the
    # script stops there and keeps what it output so far.
    assert album_fields(folder, 'outputto "album"\n' + commands) == {'album': 'before'}


def test_findline_told_not_to_fail_goes_on(folder):
    # Mp3tag's reference, FindLine: "If the 3rd parameter is set to 1, no
    # error is produced if S is not found." Docs-silent: the maintainer's
    # choice (not a quote): the pointer goes to the page's end.
    commands = 'findline "zzz" 1 1\nsayrest\noutputto "artist"\nsay "after"'

    assert album_fields(folder, 'outputto "album"\n' + commands) == {'artist': 'after'}


@pytest.mark.xfail(strict=True, reason="a FindInLine that finds nothing leaves the pointer on the line's last character")
def test_findinline_told_not_to_fail_goes_to_the_line_end(folder):
    # Mp3tag's reference, FindInLine: "If the 3rd parameter is set to 1, no
    # error is produced if S is not found." Docs-silent: the maintainer's
    # choice (not a quote): the pointer goes to the line's end, so SayRest
    # says nothing.
    commands = ('findline "Artist"\nfindinline "zzz" 1 1\nsayrest\n'
                'outputto "artist"\nsay "after"')

    assert album_fields(folder, 'outputto "album"\n' + commands) == {'artist': 'after'}


@pytest.mark.xfail(strict=True, reason="FindLineNoCase reads the lines as they were before JoinUntil joined them")
def test_findlinenocase_sees_joined_lines(folder):
    # Mp3tag's reference, FindLineNoCase: "(ignoring case and starting from
    # the current position)", and JoinUntil: "Joins the current line to the
    # next occurrence of S." So "line four" is read after the join.
    commands = ('findline "line one"\njoinuntil "three"\n'
                'findlinenocase "LINE FOUR"\nsayrest')

    assert album_fields(folder, 'outputto "album"\n' + commands) == {'album': 'line four'}


@pytest.mark.parametrize('commands, expected', [
    # Mp3tag's reference: "FindInLine ... looks within the current line
    # where the pointer is and positions it after the found text".
    ('findline "Artist"\nfindinline "</b>"\nsayrest', {'album': 'Foo Bar  Year: 1999 end'}),
    # Mp3tag's reference, FindInLine: "Find the next/Nth occurrence of S
    # within the current line."
    ('findline "Artist"\nfindinline "a" 2\nsayrest', {'album': 'r: 1999 end'}),
], ids=['first', 'nth'])
def test_findinline_goes_past_the_text(folder, commands, expected):
    assert album_fields(folder, 'outputto "album"\n' + commands) == expected


@pytest.mark.xfail(strict=True, reason="GotoLine N also moves to character N")
def test_gotoline_goes_to_the_lines_first_character(folder):
    # Mp3tag's reference, GotoLine: "Go to Nth line (counting from top)",
    # and: "In all cases the pointer would be moved to the first character
    # of the target line."
    assert album_fields(folder, 'outputto "album"\ngotoline 4\nsayrest') == {'album': 'line four'}


@pytest.mark.parametrize('commands, expected', [
    # Mp3tag's reference, MoveLine: "Move down/up N lines (starting from
    # current position)."
    ('moveline 2\nsayrest', {'album': 'line three <i>x</i> tail'}),
    ('findline "four"\nmoveline -1\nsayrest', {'album': 'line three <i>x</i> tail'}),
    # Mp3tag's reference, GotoChar: "Skip to the Nth character in the
    # current line". MoveChar: "Move right/left N characters".
    ('findline "Artist"\ngotochar 4\nsayrest', {'album': 'Artist:</b> Foo Bar  Year: 1999 end'}),
    ('findline "Artist"\nmovechar 3\nsayrest', {'album': 'Artist:</b> Foo Bar  Year: 1999 end'}),
    ('findline "Artist"\nfindinline "Foo"\nmovechar -3\nsayrest', {'album': 'Foo Bar  Year: 1999 end'}),
], ids=['moveline-down', 'moveline-up', 'gotochar', 'movechar', 'movechar-left'])
def test_pointer_moves(folder, commands, expected):
    assert album_fields(folder, 'outputto "album"\n' + commands) == expected


@pytest.mark.parametrize('commands', [
    'say "before"\nmoveline 10\noutputto "artist"\nsay "after"',
    pytest.param('say "before"\nmoveline -1\noutputto "artist"\nsay "after"',
                 marks=pytest.mark.xfail(strict=True, reason="a MoveLine above the first line wraps round to the page's end")),
], ids=['past-the-end', 'above-the-first'])
def test_moveline_out_of_the_page_stops_the_script(folder, commands):
    # Docs-silent: the maintainer's choice (not a quote): a MoveLine that
    # leaves the page stops the script and keeps what it output so far.
    assert album_fields(folder, 'outputto "album"\n' + commands) == {'album': 'before'}


@pytest.mark.xfail(strict=True, reason="MoveLine's second parameter doesn't keep the script going")
def test_moveline_told_to_ignore_errors_goes_on(folder):
    # Mp3tag's reference, MoveLine: "If the second parameter is set to 1,
    # possible errors are ignored."
    commands = 'say "before"\nmoveline 10 1\noutputto "artist"\nsay "after"'

    assert album_fields(folder, 'outputto "album"\n' + commands) == {'album': 'before', 'artist': 'after'}


TAGS = '<p class="c">A</p> <b>B</b> <B>C</B>\n   padded line   '


def test_replace_replaces_every_occurrence(folder):
    # Mp3tag's reference, Replace: "Replaces all occurrences of the first
    # parameter by the second parameter."
    parser = 'outputto "album"\nfindline "Artist"\nreplace "r" "R"\nsayrest'

    assert album_fields(folder, parser) == {'album': '<b>ARtist:</b> Foo BaR  YeaR: 1999 end'}


@pytest.mark.xfail(strict=True, reason='Replace only changes the line from the pointer on')
def test_replace_covers_the_whole_line(folder):
    # Mp3tag's reference, Replace: "Replaces all occurrences of the first
    # parameter by the second parameter." Docs-silent on the reach: the
    # maintainer's choice (not a quote): the whole current line, as
    # RegexpReplace.
    parser = ('findline "Artist"\nfindinline "Bar"\nreplace "r" "R"\ngotochar 1\n'
              'outputto "album"\nsayrest')

    assert album_fields(folder, parser) == {'album': '<b>ARtist:</b> Foo BaR  YeaR: 1999 end'}


@pytest.mark.parametrize('parser, page, expected', [
    pytest.param('findline "Artist"\nreplace "Foo" "Baz"\nfindline "Artist"\nsayrest', PAGE,
                 '<b>Artist:</b> Baz Bar  Year: 1999 end', id='replace'),
    pytest.param('findline "Artist"\nregexpreplace "<[^>]+>" ""\nfindline "Artist"\nsayrest', PAGE,
                 'Artist: Foo Bar  Year: 1999 end', id='regexpreplace'),
    pytest.param('killtag "*" ""\nfindline "B"\nsayrest', TAGS, 'A B C', id='killtag'),
])
@pytest.mark.xfail(strict=True, reason='a change to the line is undone when FindLine moves to a line')
def test_changes_last_past_the_next_findline(folder, parser, page, expected):
    # Mp3tag's reference, Replace: "Replaces all occurrences of the first
    # parameter by the second parameter." RegexpReplace: "Replaces everything
    # that is matched by the regular expression in the first parameter by
    # the string in the second parameter." KillTag: "Replaces tag S with s
    # in current line (or blank if omitted)." A replaced line stays replaced
    # when the script looks at it again.
    assert album_fields(folder, 'outputto "album"\n' + parser, page) == {'album': expected}


@pytest.mark.parametrize('parser, expected', [
    pytest.param('findline "Artist"\nregexpreplace "<[^>]+>" ""\nsayrest',
                 'Artist: Foo Bar  Year: 1999 end', id='tags'),
    pytest.param('findline "Year"\nregexpreplace "(\\d+)" "[$1]"\nsayrest',
                 '<b>Artist:</b> Foo Bar  Year: [1999] end', id='group'),
])
def test_regexpreplace_replaces_matches(folder, parser, expected):
    # Mp3tag's reference, RegexpReplace: "Replaces everything that is
    # matched by the regular expression in the first parameter by the string
    # in the second parameter." The group reference `$1` is the one the
    # Apple Music script in #795 uses (`RegexpReplace "...(.*)..." "$1"`).
    assert album_fields(folder, 'outputto "album"\n' + parser) == {'album': expected}


@pytest.mark.parametrize('parser, expected', [
    pytest.param('killtag "b" ""\nsayrest', '<p class="c">A</p> B C', id='b'),
    pytest.param('killtag "p"\nsayrest', 'A  <b>B</b> <B>C</B>', id='p'),
])
@pytest.mark.xfail(strict=True, reason='KillTag replaces only the lowercase opening tag without attributes')
def test_killtag_replaces_the_tag(folder, parser, expected):
    # Mp3tag's reference, KillTag: "Replaces tag S with s in current line
    # (or blank if omitted)." Docs-silent on the details: the maintainer's
    # choice (not a quote): opening tags with any attributes and closing
    # tags, in any case, on the whole line; a blank is a space.
    assert album_fields(folder, 'outputto "album"\n' + parser, TAGS) == {'album': expected}


def test_killtag_star_kills_every_tag(folder):
    # Mp3tag's reference, KillTag: "Replaces tag S with s in current line
    # (or blank if omitted)." Docs-silent on "*": the maintainer's choice
    # (not a quote): it kills every tag.
    assert album_fields(folder, 'outputto "album"\nkilltag "*" ""\nsayrest', TAGS) == {'album': 'A B C'}


@pytest.mark.parametrize('parser', [
    pytest.param('findline "padded"\nunspace\nsayrest', id='at-the-start'),
    pytest.param('findline "padded"\nfindinline "padded"\nunspace\nsayrest', id='after-the-pointer'),
])
def test_unspace_strips_the_line(folder, parser):
    # Mp3tag's reference, Unspace: "Removes leading and trailing spaces
    # from the current line." Docs-silent on the pointer: the maintainer's
    # choice (not a quote): it goes back to the line's start.
    assert album_fields(folder, 'outputto "album"\n' + parser, TAGS) == {'album': 'padded line'}


@pytest.mark.xfail(strict=True, reason='JoinLines N joins N-1 lines and drops the joined line')
def test_joinlines_joins_the_next_n_lines(folder):
    # Mp3tag's reference, JoinLines: "Joins the current line with the next
    # N lines."
    parser = ('outputto "album"\nfindline "line three"\njoinlines 1\nsayrest\n'
              'outputto "artist"\nmoveline 1\nsayrest')

    assert album_fields(folder, parser) == {'album': 'line three <i>x</i> tailline four',
                                            'artist': 'line five'}


@pytest.mark.parametrize('parser', [
    pytest.param('findline "line four"\njoinlines -1\nsayrest', id='minus-one'),
    pytest.param('findline "line four"\njoinlines 10\nsayrest', id='too-many'),
])
@pytest.mark.xfail(strict=True, reason='JoinLines puts a space between the lines and, past the page, drops every line')
def test_joinlines_minus_one_or_too_many_joins_every_line(folder, parser):
    # Mp3tag's reference, JoinLines: "If N is -1 or exceeds input range,
    # all available lines are joined." Docs-silent on the separator: the
    # maintainer's choice (not a quote): nothing between the lines, as
    # JoinUntil.
    assert album_fields(folder, 'outputto "album"\n' + parser) == {'album': 'line fourline five'}


def test_joinuntil_joins_up_to_the_text(folder):
    # Mp3tag's reference, JoinUntil: "Joins the current line to the next
    # occurrence of S." Docs-silent on the separator: nothing between the
    # lines.
    parser = ('outputto "album"\nfindline "line three"\njoinuntil "four"\nsayrest\n'
              'outputto "artist"\nmoveline 1\nsayrest')

    assert album_fields(folder, parser) == {'album': 'line three <i>x</i> tailline four',
                                            'artist': 'line five'}


def retrieve_page(folder, server, parser):
    """What Retrieve gives for the page the server serves at /album, read by
    the album parser `parser`."""
    source = load_one(folder, script(local_header(server), index=INDEX_PARSER, album=parser))
    return source.retrieve('x')


@pytest.mark.xfail(strict=True, reason="named and hexadecimal entities aren't converted")
def test_entities_in_outputs_are_converted(folder):
    # Docs-silent: the maintainer's choice (not a quote): every HTML entity
    # in an output is converted. The iTunes script turns `\"` into `&quot;`
    # and expects a quote back.
    parser = 'outputto "album"\nsay "Caf&eacute; &amp; &quot;x&quot; &#233; &#xe9;"'

    assert album_fields(folder, parser) == {'album': 'Café & "x" é é'}


def test_decimal_entities_are_converted(folder):
    # Docs-silent: the maintainer's choice (not a quote): every HTML entity
    # in an output is converted, the decimal ones too.
    assert album_fields(folder, 'outputto "album"\nsay "Caf&#233;"') == {'album': 'Café'}


@pytest.mark.xfail(strict=True, raises=ValueError,
                   reason="several cover addresses fail the retrieval")
def test_several_cover_addresses_give_every_cover(folder, server):
    # Docs-silent: the maintainer's choice (not a quote): each address of
    # COVERURL is downloaded and they all are the album's images.
    server.add('/album', 'Synthetic album page')
    server.add('/a.jpg', b'cover a', content_type='image/jpeg')
    server.add('/b.jpg', b'cover b', content_type='image/jpeg')
    parser = f'outputto "coverurl"\nsay "{server.url}/a.jpg|{server.url}/b.jpg|"'

    info, tracks = retrieve_page(folder, server, parser)

    assert info['__image'] == [{'data': b'cover a'}, {'data': b'cover b'}]


@pytest.mark.xfail(strict=True, reason="a charset named only in the page's HTML is ignored")
@pytest.mark.parametrize('meta', ['<meta charset="iso-8859-1">',
                                  '<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">'],
                         ids=['charset', 'http-equiv'])
def test_page_naming_its_charset_in_html_is_read_in_it(folder, server, meta):
    # Docs-silent: the maintainer's choice (not a quote): a page that names
    # its charset in a meta tag is read in it. Synthetic: a Latin-1 page.
    server.add('/album', f'<html><head>{meta}</head>\nCafé\n'.encode('latin-1'))

    info, tracks = retrieve_page(folder, server, 'outputto "album"\nfindline "Caf"\nsayrest')

    assert info['album'] == 'Café'


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="a command puddletag doesn't have is found only when the page is parsed, as a KeyError")
@pytest.mark.parametrize('command', sorted([
    'DebugWriteInput', 'IfGreater', 'IfLess', 'IfNotOutput', 'IfNotVar', 'IfOutput', 'IfVar', 'Insert',
    'SayDate', 'SayDuration', 'SayFormat', 'SayVar', 'SkipChars', 'Trim', 'Use', 'UseFormat', 'json',
    'json_foreach', 'json_foreach_counter', 'json_foreach_end', 'json_foreach_reverse', 'json_select',
    'json_select_array', 'json_select_many', 'json_select_many_count', 'json_select_object',
    'json_unselect_object']))
def test_script_with_a_command_puddletag_lacks_says_which(folder, caplog, command):
    # tagsources.txt: "A tag source that can't be loaded is left out, and
    # the reason is shown in the Tag Sources window and written to
    # puddletag's log". The command names are Mp3tag's reference's.
    path = write(folder, script(album=f'outputto "album"\n{command} "x"\nsayrest\n'))
    assert loaded(folder) == []
    assert errors(caplog) == [f"Couldn't load Mp3tag Tag Source {path}: "
                              f"line 6 uses a command puddletag doesn't have: {command}"]


def test_commands_are_read_in_any_case(folder):
    # Mp3tag's reference writes OutputTo, FindLine and SayRest; the scripts
    # also write outputto, findline and sayrest.
    assert album_fields(folder, 'OutputTo "album"\nFindLine "four"\nSayRest') == {'album': 'line four'}


@pytest.mark.parametrize('commands, expected', [
    pytest.param('if "line"\nsay "yes"\nelse\nsay "no"\nendif', 'yes', id='if-found'),
    pytest.param('if "xx"\nsay "yes"\nelse\nsay "no"\nendif', 'no', id='if-missing'),
    pytest.param('if "four"\nsay "yes"\nelse\nsay "no"\nendif', 'no', id='if-after-the-pointer'),
    pytest.param('ifnot "xx"\nsay "yes"\nendif\nsay "!"', 'yes!', id='ifnot-missing'),
    pytest.param('ifnot "line"\nsay "yes"\nelse\nsay "no"\nendif', 'no', id='ifnot-found'),
    pytest.param('if "line"\nif "zz"\nsay "a"\nelse\nsay "b"\nendif\nsay "c"\nendif', 'bc', id='nested'),
])
def test_if_checks_the_text_at_the_pointer(folder, commands, expected):
    # Mp3tag's reference: If "Check for occurrence of S on current
    # position."; IfNot "Check for absence of S on current position."; Else
    # "Alternative branch of an If operation."; Endif "End of an
    # If/IfNot/IfOutput/IfNotOutput/IfVar/IfNotVar operation."
    assert album_fields(folder, f'outputto "album"\nfindline "line four"\n{commands}') == {'album': expected}


def test_debug_on_writes_the_named_file(folder, tmp_path, monkeypatch):
    # Mp3tag's reference: Debug "Debug output, S= "on" or "off", s is an
    # optional file name." tagsources.txt: "Be sure to set 'debug off' or
    # remove it alltogether unless you're in the mood for having your
    # filesystem being littered with junk files."
    monkeypatch.chdir(tmp_path)

    fields = album_fields(folder, 'debug "on" "debug.out"\noutputto "album"\nsay "ok"')

    assert fields == {'album': 'ok'}
    assert (tmp_path / 'debug.out').read_text() != ''


def test_debug_off_writes_nothing(folder, tmp_path, monkeypatch):
    # Mp3tag's reference: Debug "Debug output, S= "on" or "off", s is an
    # optional file name."
    monkeypatch.chdir(tmp_path)

    fields = album_fields(folder, 'debug "off"\noutputto "album"\nsay "ok"')

    assert fields == {'album': 'ok'}
    assert list(tmp_path.iterdir()) == [folder]


ITEMS = 'item 1\nitem 2\nitem 3\nitem 4\nitem 5'


def retrieve(folder, server, parser, page=PAGE):
    """Retrieve's result for the album page `page`, served at the script's
    [AlbumUrl] with the result address u1."""
    server.add('/album', page)
    source = load_one(folder, script({**HEADER, 'AlbumUrl': f'{server.url}/album?id='},
                                     album=parser))
    return source.retrieve({'#url': 'u1'})


def test_outputto_names_the_field_say_writes_to(folder):
    # Mp3tag's reference, OutputTo: "Sets the name of the output buffer of
    # the Say commands to S."
    parser = 'outputto "album"\nsay "A"\noutputto "artist"\nsay "B"\noutputto "album"\nsay "C"'

    assert album_fields(folder, parser) == {'album': 'AC', 'artist': 'B'}


def test_tracks_output_gives_the_track_titles(folder):
    # Mp3tag's reference: "For fields that have varying contents for
    # tracks, e.g., TITLE, TRACK, or ISRC, Mp3tag expects the output buffer
    # to contain the individual values separated and finalized by the pipe
    # character |, e.g., Title 1|Title 2|Title 3|." That TRACKS holds the
    # titles comes from scripts (the iTunes one), not the reference.
    parser = 'outputto "tracks"\nsay "Song 1|Song 2|"'

    assert parse_album(folder, parser) == ({}, [{'title': 'Song 1'}, {'title': 'Song 2'}])


def test_album_fields_before_the_tracks_stay_the_albums(folder):
    # Mp3tag's reference: "For fields that have varying contents for
    # tracks ... the individual values separated and finalized by the pipe
    # character |". An output with one value is the album's.
    parser = 'outputto "album"\nsay "A"\noutputto "tracks"\nsay "Song 1|Song 2|"'

    assert parse_album(folder, parser) == (
        {'album': 'A'}, [{'title': 'Song 1'}, {'title': 'Song 2'}])


@pytest.mark.xfail(strict=True, reason='outputs after an OutputTo "tracks" outside a loop go to '
                                       'the album, as several values')
def test_outputs_after_the_titles_are_per_track(folder):
    # Mp3tag's reference: "For fields that have varying contents for
    # tracks, e.g., TITLE, TRACK, or ISRC, Mp3tag expects the output buffer
    # to contain the individual values separated and finalized by the pipe
    # character |, e.g., Title 1|Title 2|Title 3|."
    parser = ('outputto "tracks"\nsay "Song 1|Song 2|"\n'
              'outputto "artist"\nsay "Artist 1|Artist 2|"')

    assert parse_album(folder, parser) == ({}, [
        {'artist': 'Artist 1', 'title': 'Song 1'}, {'artist': 'Artist 2', 'title': 'Song 2'}])


@pytest.mark.xfail(strict=True, reason='a TITLE output with pipes becomes several album titles')
def test_title_with_pipes_gives_each_tracks_title(folder):
    # Mp3tag's reference: "For fields that have varying contents for
    # tracks, e.g., TITLE, TRACK, or ISRC, Mp3tag expects the output buffer
    # to contain the individual values separated and finalized by the pipe
    # character |, e.g., Title 1|Title 2|Title 3|."
    parser = 'outputto "title"\nsay "T1|T2|"\noutputto "album"\nsay "Alb"'

    assert parse_album(folder, parser) == (
        {'album': 'Alb'}, [{'title': 'T1'}, {'title': 'T2'}])


@pytest.mark.xfail(strict=True, reason="in a loop, the album's last field goes into the first "
                                       "track, each track's last field into the next, and the "
                                       "last track comes out twice")
def test_loop_gives_one_track_per_pass(folder):
    # Mp3tag's reference, Do ... While: "Execute the command surrounded by
    # the two commands while S occurs on current position."; and the
    # pipe quote: "Mp3tag expects the output buffer to contain the
    # individual values separated and finalized by the pipe character |".
    parser = ('outputto "album"\nsay "Alb"\ndo\noutputto "tracks"\nsayrest\nsay "|"\n'
              'outputto "artist"\nsay "Ar|"\nmoveline 1\nwhile "item"')

    assert parse_album(folder, parser, page=ITEMS) == (
        {'album': 'Alb'}, [{'artist': 'Ar', 'title': f'item {n}'} for n in range(1, 6)])


@pytest.mark.parametrize('condition, expected', [
    ('"item"', 'item 1 item 2 item 3 item 4 item 5'),
    ('"zzz"', 'item 1'),
    pytest.param('"item" 2', 'item 1 item 2', marks=pytest.mark.xfail(
        strict=True, reason="Do/While's limit never limits")),
])
def test_while_repeats_while_the_text_is_there(folder, condition, expected):
    # Mp3tag's reference, Do ... While: "Execute the command surrounded by
    # the two commands while S occurs on current position. The optional
    # second parameter limits the execution of the loop to maximal n times."
    # The check comes after the body, so a false condition still runs it once.
    parser = f'outputto "album"\ndo\nsayrest\nsay " "\nmoveline 1\nwhile {condition}'

    assert album_fields(folder, parser, page=ITEMS) == {'album': expected}


@pytest.mark.parametrize('parser, expected', [
    ('set "album" "xx"', {'album': 'xx'}),
    ('outputto "album"\nsay "abc"\nset "album"', {}),
    ('outputto "artist"\nsay "B"\noutputto "album"\nsay "A"\nset "artist"', {'album': 'A'}),
])
def test_set_sets_or_resets_a_field(folder, parser, expected):
    # Mp3tag's reference, Set: "Sets the content of output S to the value
    # s. Resets the content if s is omitted."
    assert album_fields(folder, parser) == expected


@pytest.mark.xfail(strict=True, reason='Set on the field being output to is overwritten by '
                                       'what was said before it')
def test_set_replaces_the_field_being_written(folder):
    # Mp3tag's reference, Set: "Sets the content of output S to the value s."
    parser = 'outputto "album"\nsay "abc"\nset "album" "xx"'

    assert album_fields(folder, parser) == {'album': 'xx'}


def test_sayoutput_says_another_field(folder):
    # Mp3tag's reference, SayOutput: "Send the content of output S to the
    # current output."
    parser = 'outputto "artist"\nsay "AA"\noutputto "album"\nsayoutput "artist"'

    assert album_fields(folder, parser) == {'album': 'AA', 'artist': 'AA'}


def test_sayoutput_currenturl_says_the_page_address(folder, server):
    # Mp3tag's reference, SayOutput: "The output CurrentUrl is always
    # generated at runtime."
    info, tracks = retrieve(folder, server, 'outputto "album"\nsayoutput "CurrentUrl"')

    assert info['album'] == f'{server.url}/album?id=u1'


@pytest.mark.xfail(strict=True, reason='CurrentUrl comes out as a field')
def test_currenturl_is_not_a_field(folder, server):
    # Mp3tag's reference, SayOutput: "The output CurrentUrl is always
    # generated at runtime." It isn't something the script outputs.
    assert retrieve(folder, server, 'outputto "album"\nsay "A"') == (
        {'#url': f'{server.url}/album?id=u1', 'album': 'A'}, None)


@pytest.mark.xfail(strict=True, reason='what a script says before any OutputTo comes out as a '
                                       'track holding CurrentUrl, or as a field with no name')
def test_say_before_any_outputto_makes_no_track(folder, server):
    # Docs-silent: the maintainer's choice (not a quote): text said before
    # any OutputTo has no field to go to and is dropped.
    assert retrieve(folder, server, 'say "x"') == ({'#url': f'{server.url}/album?id=u1'}, None)


@pytest.mark.xfail(strict=True, reason='the index parser knows CurrentUrl only in that exact case')
def test_index_parser_reads_currenturl_in_any_case(folder, server):
    # Mp3tag's reference, SayOutput: "The output CurrentUrl is always
    # generated at runtime." Output names are read in any case.
    server.add('/search', 'any page')
    source = load_one(folder, script(local_header(server),
                                     index='say "u1|"\nsayoutput "currenturl"\n'))

    assert source.keyword_search('First Light') == [
        ({'#url': 'u1', 'album': f'{server.url}/search?q=First+Light'}, [])]


@pytest.mark.xfail(strict=True, reason="the album's last field goes into the first track")
def test_itunes_album_keeps_its_label(folder, server):
    # The iTunes script outputs PUBLISHER (which puddletag calls label) as
    # the album's last field before the track loop.
    info, tracks = retrieve_itunes_album(folder, server)

    assert info['label'] == '℗ 2001 Synthetic Records'
    assert [t for t in tracks if 'label' in t] == []


@pytest.mark.xfail(strict=True, reason='Set turns a number to nothing')
def test_set_takes_a_number(folder):
    # Mp3tag's reference, Set: "Sets the content of output S to the value
    # s. Resets the content if s is omitted." The number is synthetic.
    parser = 'set "track" 0\noutputto "album"\nsay "x"'

    assert album_fields(folder, parser) == {'album': 'x', 'track': '0'}


@pytest.mark.parametrize('n', [-1, 10])
@pytest.mark.xfail(strict=True, reason='JoinLines also joins the page end line')
def test_joinlines_keeps_the_page_end(folder, n):
    # Mp3tag's reference, JoinLines: "If N is -1 or exceeds input range, all
    # available lines are joined."; FindLine: "If the 3rd parameter is set to 1,
    # no error is produced if S is not found." Docs-silent: the maintainer's
    # choice (not a quote): with the 1, the pointer goes to the page's end.
    parser = (f'outputto "album"\nfindline "line four"\njoinlines {n}\n'
              'findline "zz" 1 1\nsayrest\noutputto "artist"\nsay "after"')

    assert album_fields(folder, parser) == {'artist': 'after'}
