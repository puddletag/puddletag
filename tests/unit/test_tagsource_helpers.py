"""The helpers every tag source shares (puddlestuff/tagsources/__init__.py):
downloading a page, the errors a download ends in, and reading the search
box, the files' ids and a page's encoding.

The docs' example tag source plugin (docsrc/source/tagsource.tar.gz) asks
plugins to "use puddlestuff.tagsources.urlopen instead of the generic urllib
functions ... Pass it your url and it'll return your data", and to "Raise
puddlestuff.tagsources.RetrievalError if an error occurs". Pages come from
the local web server (tests/conftest.py); every page and address here is
synthetic.
"""

import errno
import socket
import threading

import pytest

from puddlestuff import tagsources, version_string
from puddlestuff.audioinfo import DATA
from puddlestuff.tagsources import (RetrievalError, discogs, find_id, get_encoding,
                                    iri_to_uri, parse_searchstring)

# preferences.txt: "The default names puddletag, its version and its
# address, as MusicBrainz asks of every program" ("Application
# name/<version> ( contact-url )").
DEFAULT_USERAGENT = f'puddletag/{version_string} ( https://github.com/puddletag/puddletag )'


@pytest.fixture
def no_wait(monkeypatch):
    """Discogs' urlopen (Mp3tag scripts download through it too) without its
    second between requests."""
    monkeypatch.setattr(discogs, '_wait', lambda: None)


@pytest.fixture
def closed_port():
    """A local address nothing listens on. The port stays bound, so no other
    program takes it during the test."""
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    yield f'http://127.0.0.1:{sock.getsockname()[1]}/'
    sock.close()


@pytest.fixture
def unknown_host(monkeypatch):
    """An address whose host no name server knows (.invalid, RFC 2606). Its
    lookup fails as the system's resolver fails it (glibc's message), before
    the network guard sees it; other hosts go to the guard as before."""
    guarded = socket.getaddrinfo

    def getaddrinfo(host, *args, **kwargs):
        if host == 'unknown.invalid':
            raise socket.gaierror(socket.EAI_NONAME, 'Name or service not known')
        return guarded(host, *args, **kwargs)

    monkeypatch.setattr(socket, 'getaddrinfo', getaddrinfo)
    return 'http://unknown.invalid/'


@pytest.fixture
def silent_server():
    """A local address that takes connections and never answers. Closing it
    at teardown frees any request still waiting."""
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen()
    yield f'http://127.0.0.1:{listener.getsockname()[1]}/'
    listener.close()


@pytest.fixture
def hanging_up_server():
    """A local address that reads one request and hangs up without an
    answer."""
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen()

    def hang_up():
        try:
            connection, _ = listener.accept()
        except OSError:
            return
        with connection:
            request = b''
            while b'\r\n\r\n' not in request:
                chunk = connection.recv(1024)
                if not chunk:
                    break
                request += chunk

    thread = threading.Thread(target=hang_up, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{listener.getsockname()[1]}/'
    listener.close()
    thread.join(1)


# Downloading a page ----------------------------------------------------------

def test_urlopen_returns_the_page(web_server):
    # Example plugin: "Pass it your url and it'll return your data."
    web_server.add('/page', b'Synthetic page')
    assert tagsources.urlopen(web_server.url + '/page') == b'Synthetic page'


@pytest.mark.parametrize(('setting', 'sent'), [
    pytest.param('', DEFAULT_USERAGENT, id='empty'),
    pytest.param('Synthetic/1.0 ( https://example.org )',
                 'Synthetic/1.0 ( https://example.org )', id='set'),
])
def test_urlopen_sends_the_user_agent(web_server, monkeypatch, setting, sent):
    # preferences.txt: "The User-Agent puddletag sends to the web sites its
    # tag sources read (MusicBrainz, Discogs, Mp3tag's tag sources). The
    # default names puddletag, its version and its address, as MusicBrainz
    # asks of every program; leave it empty for the default."
    monkeypatch.setattr(tagsources, 'useragent', tagsources.useragent)
    tagsources.set_useragent(setting)
    web_server.add('/page', b'Synthetic page')
    tagsources.urlopen(web_server.url + '/page')
    assert web_server.requests[-1].headers['User-Agent'] == sent


@pytest.mark.parametrize(('status', 'message'), [
    pytest.param(403, 'HTTP Error 403: Forbidden', id='forbidden'),
    pytest.param(404, 'HTTP Error 404: Not Found', id='not-found'),
    pytest.param(500, 'HTTP Error 500: Internal Server Error', id='server-error'),
])
def test_http_error_becomes_a_retrieval_error(web_server, status, message):
    # Example plugin: "Raise puddlestuff.tagsources.RetrievalError if an error
    # occurs." The docs are silent on the message and the code.
    web_server.add('/page', b'Synthetic error page', status=status, content_type='text/html')
    with pytest.raises(RetrievalError) as error:
        tagsources.urlopen(web_server.url + '/page')
    assert str(error.value) == message
    assert error.value.code == status


def test_refused_connection_becomes_a_retrieval_error(closed_port):
    # Example plugin: "Raise puddlestuff.tagsources.RetrievalError if an error
    # occurs." The docs are silent on the message and the code.
    with pytest.raises(RetrievalError) as error:
        tagsources.urlopen(closed_port)
    assert str(error.value) == f'Connection Error: [Errno {errno.ECONNREFUSED}] Connection refused'
    assert error.value.code == 0


def test_unknown_host_becomes_a_retrieval_error(unknown_host):
    # Example plugin: "Raise puddlestuff.tagsources.RetrievalError if an error
    # occurs." The docs are silent on the message and the code.
    with pytest.raises(RetrievalError) as error:
        tagsources.urlopen(unknown_host)
    assert str(error.value) == f'Connection Error: [Errno {socket.EAI_NONAME}] Name or service not known'
    assert error.value.code == 0


def test_retrieve_cover_returns_the_image(web_server):
    # Example plugin: "Images must be a list of dictonaries with the following
    # keys (all from puddlestuff.audioinfo): DATA: Required. The images string
    # data."
    web_server.add('/cover.jpg', b'synthetic image', content_type='image/jpeg')
    assert tagsources.retrieve_cover(web_server.url + '/cover.jpg') == {'__image': [{DATA: b'synthetic image'}]}


# Reading the search box, the files' ids and a page's encoding ----------------

@pytest.mark.parametrize(('text', 'pairs'), [
    pytest.param('Synthetic Band;Synthetic Album',
                 [('Synthetic Band', 'Synthetic Album')], id='artist-and-album'),
    pytest.param('Synthetic Band;', [('Synthetic Band', '')], id='artist-only'),
    pytest.param(';Synthetic Album', [('', 'Synthetic Album')], id='album-only'),
    pytest.param('Band 1;Album 1|Band 2;Album 2',
                 [('Band 1', 'Album 1'), ('Band 2', 'Album 2')], id='two-pairs'),
])
def test_search_text_gives_artist_and_album_pairs(text, pairs):
    """tagsources.txt: "enter the search string as **artist;album**",
    "**artist;**", "**;album**". The example plugin: "The format
    artist1;album1|artist2;album2 should be accepted. Use the
    parse_searchstring method to separate text into a list of artist album
    pairs as in: [(artist1, album1), (artist2, album2)]"."""
    assert parse_searchstring(text) == pairs


def test_find_id_returns_the_id_the_files_carry():
    """tagsources.txt: "each album among the selected files is retrieved by
    the release id its files carry: in the field the tag source's **Field to
    use for discogs_id** preference names (**discogs_id** unless changed), or
    else in **discogs_r_id**". The example plugin: "values are usually lists
    and "builtin" values are strings"."""
    tracks = [{'title': ['One']}, {'discogs_id': ['249504'], 'title': ['Two']}]
    assert find_id(tracks, 'discogs_id') == '249504'
    # No file carries it, so Discogs tries the other field.
    assert find_id(tracks, 'discogs_r_id') is None
    # Synthetic field name: any field holding a string.
    assert find_id([{'__id': '7'}], '__id') == '7'


@pytest.mark.parametrize(('page', 'encoding'), [
    pytest.param('<?xml version="1.0" encoding="ISO-8859-1"?><a/>', 'ISO-8859-1',
                 id='double-quotes'),
    pytest.param("<?xml version='1.0' encoding='windows-1252'?><a/>", 'windows-1252',
                 id='single-quotes'),
    pytest.param('<?xml version="1.0" encoding = "UTF-16" ?><a/>', 'UTF-16',
                 id='spaces-around-equals'),
    pytest.param('<?xml version="1.0"?><a/>', None, id='no-encoding'),
    pytest.param('<html><body>Synthetic</body></html>', None, id='no-declaration'),
])
def test_encoding_named_by_the_xml_declaration(page, encoding):
    """XML 1.0, sections 2.8 and 4.3.3: `EncodingDecl ::= S 'encoding' Eq
    ('"' EncName '"' | "'" EncName "'")` and `Eq ::= S? '=' S?`. A page
    without the declaration, or whose declaration names no encoding, has none
    (synthetic pages)."""
    assert get_encoding(page) == encoding


@pytest.mark.parametrize(('text', 'pairs'), [
    pytest.param(' Band ; Album ', [('Band', 'Album')], id='spaces-around'),
    pytest.param('', [], id='empty'),
    pytest.param('Band;Album|', [('Band', 'Album')], id='trailing-bar'),
])
def test_search_text_edge_cases(text, pairs):
    """tagsources.txt: "enter the search string as **artist;album**". Edge
    cases of the box's text are synthetic."""
    assert parse_searchstring(text) == pairs


@pytest.mark.parametrize('text', [
    pytest.param('Synthetic Album', id='album-only-without-semicolon'),
    pytest.param('A;B;C', id='three-parts'),
])
def test_search_text_without_a_pair_is_an_error(text):
    """tagsources.txt: "Anything else is searched as an album title."
    MusicBrainz catches this error to do so (synthetic texts)."""
    with pytest.raises(RetrievalError,
                       match='^<b>Error parsing artist/album combinations\\.</b>$'):
        parse_searchstring(text)


@pytest.mark.parametrize('value', [
    pytest.param([''], id='empty-string'),
    pytest.param([], id='empty-list'),
])
def test_find_id_skips_a_file_without_a_value(value):
    """tagsources.txt: "each album among the selected files is retrieved by
    the release id its files carry". A file with an empty field carries none
    (synthetic)."""
    tracks = [{'discogs_id': value}, {'discogs_id': ['249504']}]
    assert find_id(tracks, 'discogs_id') == '249504'


def test_find_id_without_a_field_is_none():
    """An emptied Field to use for discogs_id preference names no field
    (synthetic)."""
    assert find_id([{'discogs_id': ['249504']}], '') is None


def test_encoding_declared_over_two_lines():
    """XML 1.0, section 2.3: `S` includes line feeds (#xA), so a line break
    may separate the declaration's parts (synthetic page)."""
    page = '<?xml version="1.0"\nencoding="ISO-8859-1"?><a/>'
    assert get_encoding(page) == 'ISO-8859-1'


def test_encoding_of_a_page_without_one_is_the_default():
    """A page naming no encoding gets the caller's default (synthetic)."""
    assert get_encoding('<a/>', default='utf-8') == 'utf-8'


# Addresses with characters outside ASCII -------------------------------------

# RFC 3987, 3.1: "For each character in 'ucschar' or 'iprivate', apply steps
# 2.1 through 2.3 below." "Convert the character to a sequence of one or more
# octets using UTF-8", "Convert each octet to %HH". The query case is
# synthetic, the same rule.
@pytest.mark.parametrize(('iri', 'uri'), [
    pytest.param('http://www.example.org/Dürst', 'http://www.example.org/D%C3%BCrst',
                 id='path'),
    pytest.param('http://www.example.org/red%09rosé#red',
                 'http://www.example.org/red%09ros%C3%A9#red', id='keeps-percent-escapes'),
    pytest.param('http://example.org/search?q=Björk', 'http://example.org/search?q=Bj%C3%B6rk',
                 id='query'),
    # WHATWG URL standard: the path percent-encode set is "the query
    # percent-encode set and U+003F (?), U+005E (^), U+0060 (`), U+007B ({),
    # and U+007D (})", and the query percent-encode set "the C0 control
    # percent-encode set and U+0020 SPACE, ...": a space and the controls
    # become %XX. Synthetic address.
    pytest.param('http://example.org/a b', 'http://example.org/a%20b', id='space'),
])
def test_non_ascii_characters_are_percent_encoded_as_utf8(iri, uri):
    assert iri_to_uri(iri) == uri


# RFC 3987, 3.1: "Systems accepting IRIs MAY convert the ireg-name component
# of an IRI as follows (before step 2 above)": "Replace the ireg-name part of
# the IRI by the part converted using the ToASCII operation."
def test_non_ascii_host_is_encoded_in_idna():
    assert iri_to_uri('http://résumé.example.org') == 'http://xn--rsum-bpad.example.org'


# Synthetic: an address with nothing outside ASCII has nothing to encode.
def test_ascii_address_is_unchanged():
    assert (iri_to_uri('https://api.discogs.com/releases/249504?a=1&b=2')
            == 'https://api.discogs.com/releases/249504?a=1&b=2')


# tagsources.txt: "puddletag supports using Mp3tag's tag sources". Their search and
# album pages download through Discogs' urlopen, and a result's address may
# hold any character (synthetic).
def test_discogs_downloads_a_non_ascii_address(web_server, no_wait):
    web_server.add('/Björk/cover.jpg', b'synthetic image')
    assert discogs.urlopen(web_server.url + '/Björk/cover.jpg') == b'synthetic image'
    assert web_server.requests[-1].path == '/Björk/cover.jpg'
