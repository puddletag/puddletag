"""The FreeDB tag source (puddlestuff/tagsources/freedb.py): the disc id it
computes from the files, the albums it finds and the fields it returns, as
tagsources.txt describes them, against replies a local web server sends back.

Every reply is synthetic, shaped like gnudb's, the server freedb's data moved
to. Expected values come from tagsources.txt, from the CDDB protocol and the
xmcd database format as freedb documented them (CDDBPROTO and DBFORMAT, kept
by the Internet Archive at
web.archive.org/web/2019/http://ftp.freedb.org/pub/freedb/latest/), and, for
the disc id, from libdiscid's test data (github.com/metabrainz/libdiscid,
test/test_put.c).
"""
import struct

import pytest

from puddlestuff import audioinfo
from puddlestuff.tagsources import CDDB, RetrievalError, freedb

CGI = '/~cddb/cddb.cgi'
DISC_ID = '0c025603'
# Synthetic: three tracks starting 2, 202 and 402 seconds in, 600 seconds in
# all, under the id the CDDB algorithm gives them.
TRACK_INFO = [0x0c025603, 3, 150, 15150, 30150, 600]


class FakeClock:
    """The time module as freedb sees it: time moves only when the source
    waits, each wait kept in ``sleeps``, or when a test advances it."""

    def __init__(self):
        self.now = 1_000_000.0
        self.sleeps = []

    def advance(self, seconds):
        self.now += seconds

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    time = monotonic


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(freedb, 'time', fake)
    # When gnudb was last asked something: shared by every FreeDB source.
    monkeypatch.setattr(freedb, '_last_request', None)
    return fake


@pytest.fixture
def gnudb(monkeypatch, web_server, clock):
    """The local server in place of gnudb's CGI, at protocol level 6 (the
    level freedb sets when it's imported). The source's waits take no
    time: the clock stands still."""
    monkeypatch.setattr(CDDB, 'proto', 6)
    monkeypatch.setattr(CDDB, 'default_server', web_server.url + CGI)
    return web_server


def reply(*lines):
    """A reply's body, each line ending in CR LF as gnudb's do."""
    return ''.join(line + '\r\n' for line in lines)


def entry(*data, disc_id=DISC_ID):
    """A read reply for ``disc_id`` in gnudb's one category: the status line,
    an xmcd file's first comments, ``data`` (its KEYWORD=data lines) and the
    terminating marker."""
    return reply(f"210 data {disc_id} CD database entry follows (until terminating `.')",
                 '# xmcd', '#', f'DISCID={disc_id}', *data, '.')


def answer_queries(gnudb, body):
    """Answers every query with ``body``, whatever disc id it sends. Added
    before any read's answer: the last matching answer wins, and a read
    names its command."""
    gnudb.add(CGI, body, content_type='text/plain')


def answer_read(gnudb, body, disc_id=DISC_ID):
    gnudb.add(CGI, body, content_type='text/plain',
              query={'cmd': f'cddb read data {disc_id}'})


def flac(path, frames):
    """A FLAC file of exactly ``frames`` CD frames (588 samples each at
    44.1 kHz): only the STREAMINFO block, no audio, which is all mutagen
    reads for the length. Synthetic."""
    samples = frames * 588
    # Sample rate (20 bits), channels - 1 (3), bits per sample - 1 (5),
    # total samples (36).
    packed = (44100 << 44) | (1 << 41) | (15 << 36) | samples
    info = struct.pack('>HH', 4096, 4096) + bytes(6) + packed.to_bytes(8, 'big') + bytes(16)
    path.write_bytes(b'fLaC' + bytes([0x80]) + len(info).to_bytes(3, 'big') + info)
    return path


def one_second_files(make_audio, tmp_path, count=3):
    """Synthetic one-second FLAC files of one album, as the window passes
    them to the source: audioinfo tags."""
    return [audioinfo.Tag(str(make_audio(f'0{n}.flac', tmp_path, album='Old', track=str(n))))
            for n in range(1, count + 1)]


# The disc id -------------------------------------------------------------------

LEADOUT = 303602
# libdiscid's test disc (test/test_put.c): 22 tracks, freedb id 370fce16.
OFFSETS = [150, 9700, 25887, 39297, 53795, 63735, 77517, 94877, 107270, 123552,
           135522, 148422, 161197, 174790, 192022, 205545, 218010, 228700,
           239590, 255470, 266932, 288750]


def known_disc(tmp_path, names=None, tracks=None):
    """libdiscid's disc as files: one header-only FLAC per track, of its
    exact length. ``names``/``tracks``: the files' names and track numbers,
    by default 01.flac.. and 1..; the tags come back in the order given."""
    count = len(OFFSETS)
    names = names or [f'{n:02d}.flac' for n in range(1, count + 1)]
    tracks = tracks or [str(n) for n in range(1, count + 1)]
    tmp_path.mkdir(exist_ok=True)
    ends = OFFSETS[1:] + [LEADOUT]
    files = []
    for name, track, start, end in zip(names, tracks, OFFSETS, ends):
        tag = audioinfo.Tag(str(flac(tmp_path / name, end - start)))
        if track is not None:
            tag['track'] = [track]
        files.append(tag)
    return files


def numbered_disc_id(tmp_path):
    return freedb.calculate_discid(known_disc(tmp_path / 'numbered'))


def test_disc_id_of_a_known_disc(tmp_path):
    # tagsources.txt:102: "FreeDB creates a (semi-)unique DiscID by using the
    # number of tracks, their order and lengths of a particular CD."
    # libdiscid's test disc gives freedb id 370fce16.
    assert freedb.calculate_discid(known_disc(tmp_path)) == [0x370fce16, 22, *OFFSETS, 4048]


def test_disc_id_follows_the_track_numbers(tmp_path):
    # tagsources.txt:102: "...by using the number of tracks, their order and
    # lengths of a particular CD." Track 1 is in 22.flac, so the filename
    # order is the reverse of the track order; the files are passed reversed.
    names = [f'{23 - n:02d}.flac' for n in range(1, 23)]
    files = known_disc(tmp_path / 'reversed', names=names)
    assert (freedb.calculate_discid(files[::-1])
            == freedb.calculate_discid(known_disc(tmp_path / 'ordered')))


@pytest.mark.parametrize('tracks', [
    pytest.param([f'{n}/22' for n in range(1, 23)], id='n-of-m'),
    pytest.param([str(n) if n % 2 else f'{n}/22' for n in range(1, 23)], id='mixed'),
])
def test_disc_id_reads_track_numbers_with_a_total(tmp_path, tracks):
    # tagsources.txt:102: "...by using the number of tracks, their order and
    # lengths of a particular CD." Synthetic: a track number may carry the
    # album's track total, "2/22"; the files are passed in reverse so only the
    # track numbers give the order.
    files = known_disc(tmp_path / 'totals', tracks=tracks)
    assert freedb.calculate_discid(files[::-1]) == numbered_disc_id(tmp_path)


def test_disc_id_without_track_numbers_keeps_filename_order(tmp_path):
    # tagsources.txt:102: "...by using the number of tracks, their order and
    # lengths of a particular CD." Synthetic: files with no track number stay
    # in filename order.
    files = known_disc(tmp_path / 'unnumbered', tracks=[None] * 22)
    assert freedb.calculate_discid(files) == numbered_disc_id(tmp_path)


# Albums, fields and errors ---------------------------------------------------

ALBUM = 'Some Artist / Some Album'


def hit(category, disc_id, artist='Some Artist', album='Some Album'):
    """What search_by_id returns for one album of a query's reply."""
    return ({'#category': category, '#discid': disc_id, 'album': album, 'artist': artist,
             'freedb_category': category, 'freedb_disc_id': disc_id}, [])


def album_info(**fields):
    """What retrieve returns as the album's fields: those the tests share and
    ``fields``."""
    return {'#category': 'data', '#discid': DISC_ID, 'album': 'Some Album', 'artist': 'Some Artist',
            'freedb_category': 'data', 'freedb_disc_id': DISC_ID, **fields}


@pytest.mark.parametrize(('body', 'expected'), [
    pytest.param(reply(f'200 rock {DISC_ID} {ALBUM}'), [hit('rock', DISC_ID)], id='exact'),
    pytest.param(reply("210 Found exact matches, list follows (until terminating `.')",
                       f'data {DISC_ID} {ALBUM}', '.'),
                 [hit('data', DISC_ID)], id='exact-list-one'),
    pytest.param(reply("210 Found exact matches, list follows (until terminating `.')",
                       f'data {DISC_ID} {ALBUM}', f'data 0c025604 {ALBUM} (Remastered)', '.'),
                 [hit('data', DISC_ID), hit('data', '0c025604', album='Some Album (Remastered)')],
                 id='exact-list'),
    pytest.param(reply("211 Found inexact matches, list follows (until terminating `.')",
                       'misc 0c0256ff Other Artist / Other Album', f'rock {DISC_ID} {ALBUM}', '.'),
                 [hit('misc', '0c0256ff', artist='Other Artist', album='Other Album'),
                  hit('rock', DISC_ID)],
                 id='inexact'),
    pytest.param(reply(f'202 No match for disc ID {DISC_ID}.'), [], id='none'),
])
def test_query_statuses(gnudb, body, expected):
    # tagsources.txt: "The DiscID is then referenced to the FreeDB database
    # and any matching albums are returned." CDDBPROTO's status lines: "200
    # Found exact match", "210 Found exact matches, list follows (until
    # terminating marker)", "211 Found inexact matches, list follows (until
    # terminating marker)", "202 No match found".
    answer_queries(gnudb, body)

    assert freedb.search_by_id(TRACK_INFO) == expected


def test_retrieve_returns_the_docs_fields(gnudb):
    # tagsources.txt lists album, artist, freedb_disc_id, freedb_category,
    # genre, title, track and year. The # keys are the window's own and are
    # never written.
    answer_read(gnudb, entry(f'DTITLE={ALBUM}', 'DYEAR=1999', 'DGENRE=Synthpop', 'TTITLE0=One',
                             'TTITLE1=Two', 'TTITLE2=Three', 'EXTD=', 'PLAYORDER='))

    assert freedb.retrieve('data', DISC_ID) == (
        album_info(genre='Synthpop', year='1999'),
        [{'title': 'One', 'track': '1'}, {'title': 'Two', 'track': '2'},
         {'title': 'Three', 'track': '3'}])


def test_track_with_its_own_artist(gnudb):
    # tagsources.txt: "artist: The track's artist." DBFORMAT's TTITLEn
    # holds "artist / title" on a various-artists disc.
    answer_read(gnudb, entry(f'DTITLE={ALBUM}', 'TTITLE0=One', 'TTITLE1=Guest / Two', 'TTITLE2=Three'))

    _, tracks = freedb.retrieve('data', DISC_ID)

    assert tracks == [{'title': 'One', 'track': '1'},
                      {'artist': 'Guest', 'title': 'Two', 'track': '2'},
                      {'title': 'Three', 'track': '3'}]


@pytest.mark.parametrize(('dtitle', 'fields'), [
    pytest.param('Some Album', {'album': 'Some Album'}, id='album-only'),
    pytest.param(f'{ALBUM} / Part One', {'album': 'Some Album / Part One', 'artist': 'Some Artist'},
                 id='split-on-the-first'),
])
def test_title_without_an_artist(gnudb, dtitle, fields):
    # DBFORMAT: DTITLE is "artist / title" and says no more about a title
    # without the separator.
    answer_read(gnudb, entry(f'DTITLE={dtitle}', 'TTITLE0=One'))

    info, _ = freedb.retrieve('data', DISC_ID)

    assert {key: info[key] for key in ('album', 'artist') if key in info} == fields


def test_non_ascii_text(gnudb):
    # DBFORMAT allows UTF-8 text at protocol level 6. The text is synthetic.
    answer_read(gnudb, entry('DTITLE=Sÿnth Ärtist / Ålbum', 'TTITLE0=Öne', 'TTITLE1=Thrée'))

    info, tracks = freedb.retrieve('data', DISC_ID)

    assert (info['artist'], info['album']) == ('Sÿnth Ärtist', 'Ålbum')
    assert [track['title'] for track in tracks] == ['Öne', 'Thrée']


def test_tracks_in_number_order(gnudb):
    # DBFORMAT: "TTITLEn" is the title of track n + 1, wherever it stands in
    # the entry.
    answer_read(gnudb, entry(f'DTITLE={ALBUM}', 'TTITLE0=One', 'TTITLE2=Three', 'TTITLE1=Two'))

    _, tracks = freedb.retrieve('data', DISC_ID)

    assert tracks == [{'title': 'One', 'track': '1'}, {'title': 'Two', 'track': '2'},
                      {'title': 'Three', 'track': '3'}]


def test_album_without_year_or_genre(gnudb):
    # tagsources.txt: year is "Not available for every album." DBFORMAT
    # leaves DYEAR and DGENRE empty when the submitter gave none.
    answer_read(gnudb, entry(f'DTITLE={ALBUM}', 'DYEAR=', 'DGENRE=', 'TTITLE0=One'))

    assert freedb.retrieve('data', DISC_ID) == (album_info(), [{'title': 'One', 'track': '1'}])


def test_values_are_stripped(gnudb):
    # Synthetic: spaces around a title carry no meaning in a tag.
    answer_read(gnudb, entry(f'DTITLE={ALBUM}', 'TTITLE0=  One  '))

    _, tracks = freedb.retrieve('data', DISC_ID)

    assert tracks == [{'title': 'One', 'track': '1'}]


@pytest.mark.parametrize(('body', 'message'), [
    # CDDBPROTO: "401 Specified CDDB entry not found."
    pytest.param(reply(f'401 data {DISC_ID} No such CD entry in database.'),
                 f"Couldn't read data {DISC_ID}: the server answered 401.", id='not-found'),
    # 417 isn't one of read's codes: its explanation runs up to the ".".
    pytest.param(reply("417 Access limit exceeded, explanation follows (until terminating `.')",
                       'Too many requests from this address today.',
                       'Please try again tomorrow.', '.'),
                 f"Couldn't read data {DISC_ID}: the server answered 417. Too many requests "
                 'from this address today. Please try again tomorrow.',
                 id='refused'),
])
def test_failed_read(gnudb, body, message):
    # A read the server refuses ends in an error that says why, not in a
    # crash.
    answer_read(gnudb, body)

    with pytest.raises(RetrievalError) as excinfo:
        freedb.retrieve('data', DISC_ID)

    assert str(excinfo.value) == message
    assert excinfo.value.code == int(body[:3])


def test_http_error(gnudb):
    gnudb.add(CGI, '', status=500, content_type='text/plain')

    with pytest.raises(RetrievalError) as excinfo:
        freedb.search_by_id(TRACK_INFO)

    assert str(excinfo.value) == 'HTTP Error 500: Internal Server Error'


@pytest.mark.parametrize('call', [
    pytest.param(lambda: freedb.search_by_id(TRACK_INFO), id='search'),
    pytest.param(lambda: freedb.retrieve('data', DISC_ID), id='retrieve'),
])
@pytest.mark.parametrize('body', ['', 'garbage\r\n'])
def test_unreadable_reply(gnudb, call, body):
    # A reply that isn't CDDB's (no status line) is reported, not a crash.
    answer_queries(gnudb, body)

    with pytest.raises(RetrievalError) as excinfo:
        call()

    assert str(excinfo.value) == "The server's reply isn't a CDDB reply."


def test_search_reads_the_first_album_only(gnudb, make_audio, tmp_path):
    answer_queries(gnudb, reply("211 Found inexact matches, list follows (until terminating `.')",
                                f'data {DISC_ID} {ALBUM}', 'data 0c025699 Other / Second', '.'))
    answer_read(gnudb, entry(f'DTITLE={ALBUM}', 'DYEAR=1999', 'DGENRE=Synthpop', 'TTITLE0=One'))

    result = freedb.FreeDB().search('Old', one_second_files(make_audio, tmp_path))

    assert result == [(album_info(genre='Synthpop', year='1999'), [{'title': 'One', 'track': '1'}]),
                      hit('data', '0c025699', artist='Other', album='Second')]
    commands = [request.query['cmd'][0] for request in gnudb.requests]
    assert len(commands) == 2
    assert commands[0].startswith('cddb query ')
    assert commands[1] == f'cddb read data {DISC_ID}'


def test_search_without_files(gnudb):
    assert freedb.FreeDB().search('Old', []) == []
    assert gnudb.requests == []


# The pause -------------------------------------------------------------------
# No docs describe it; the changelog gives the intent: "Rate limiting for FreeDB
# as too many requests at once causes errors." The gap is one second between
# requests to gnudb.

TWO_HITS = reply("211 Found inexact matches, list follows (until terminating `.')",
                 f'data {DISC_ID} Some Artist / Some Album', 'data 0c025699 Other / Second', '.')
NO_MATCH = reply(f'202 No match for disc ID {DISC_ID}.')


def searched_two_hits(gnudb, make_audio, tmp_path):
    """A source that searched files and read the first of two hits, with the
    second hit's read answered: the source and the second hit's info."""
    answer_queries(gnudb, TWO_HITS)
    answer_read(gnudb, entry('DTITLE=Some Artist / Some Album', 'TTITLE0=One'))
    answer_read(gnudb, entry('DTITLE=Other / Second', 'TTITLE0=Two', disc_id='0c025699'),
                '0c025699')
    source = freedb.FreeDB()
    results = source.search('Old', one_second_files(make_audio, tmp_path))
    return source, results


def test_first_request_does_not_wait(gnudb, clock, make_audio, tmp_path):
    answer_queries(gnudb, NO_MATCH)
    freedb.FreeDB().search('Old', one_second_files(make_audio, tmp_path))
    assert clock.sleeps == []


def test_requests_are_a_second_apart(gnudb, clock, make_audio, tmp_path):
    searched_two_hits(gnudb, make_audio, tmp_path)
    assert clock.sleeps == [1]


def test_a_request_after_a_second_does_not_wait(gnudb, clock, make_audio, tmp_path):
    source, results = searched_two_hits(gnudb, make_audio, tmp_path)
    clock.advance(1)
    source.retrieve(results[1][0])
    assert clock.sleeps == [1]


def test_a_request_waits_only_the_rest_of_the_second(gnudb, clock, make_audio, tmp_path):
    source, results = searched_two_hits(gnudb, make_audio, tmp_path)
    clock.advance(0.25)
    source.retrieve(results[1][0])
    assert clock.sleeps[-1] == pytest.approx(0.75)


def test_a_cached_album_is_not_asked_again(gnudb, clock, make_audio, tmp_path):
    source, results = searched_two_hits(gnudb, make_audio, tmp_path)
    requests, sleeps = len(gnudb.requests), list(clock.sleeps)
    source.retrieve(results[0][0])
    assert len(gnudb.requests) == requests
    assert clock.sleeps == sleeps


def test_sources_share_the_gap(gnudb, clock, make_audio, tmp_path):
    answer_queries(gnudb, NO_MATCH)
    files = one_second_files(make_audio, tmp_path)
    freedb.FreeDB().search('Old', files)
    freedb.FreeDB().search('Old', files)
    assert clock.sleeps == [1]
