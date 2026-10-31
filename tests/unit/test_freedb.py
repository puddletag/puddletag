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
    monkeypatch.setattr(freedb, '_last_request', None, raising=False)
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
