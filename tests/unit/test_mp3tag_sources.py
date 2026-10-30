"""Mp3tag web source scripts (.src files) as puddletag loads, searches
and runs them. tagsources.txt says where they go and how they're
listed; Mp3tag's reference (docs.mp3tag.de/tag-sources/development/)
defines their header keys and commands. Every script here is synthetic.
"""
import logging

import pytest

from puddlestuff.mainwin.tagsources import load_mp3tag_sources

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
