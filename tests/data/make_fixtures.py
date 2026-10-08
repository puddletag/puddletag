"""Rebuild the public-domain fixtures in this directory from their sources.

Each source is downloaded, checked against the hash its site publishes, and
cut down to its tags, byte for byte, plus the start of its audio. README.md
lists the sources and their licenses. Needs network access; the tests never
run it.

    venv/bin/python tests/data/make_fixtures.py
"""
import hashlib
import io
import struct
import sys
import urllib.request
from pathlib import Path

from mutagen.ogg import OggPage

HERE = Path(__file__).parent
AUDIO_BYTES = 4096  # of audio kept after the tags

CANON = 'https://archive.org/download/musopen-chopin/Canon%20in%20F%20minor.'
SOURCES = [
    # fixture, source, hash algorithm, published hash
    ('musopen-canon.m4a', CANON + 'm4a', 'md5', 'fadb5931ccf05e3bfb24d4cea337f7f9'),
    ('musopen-canon.mp3', CANON + 'mp3', 'md5', 'dc0da3cf414d8872f77952d6eaf0a41f'),
    ('musopen-canon.ogg', CANON + 'ogg', 'md5', '4b61554772b53d5f170f36865747337c'),
    ('musopen-goldberg-aria.flac',
     'https://archive.org/download/MusopenCollectionAsFlac/Bach_GoldbergVariations/'
     'JohannSebastianBach-01-GoldbergVariationsBwv.988-Aria.flac',
     'md5', '853f9f9396946c3842ccbbcecf55a73d'),
    ('marine-band-maple-leaf-rag.ogg',
     'https://upload.wikimedia.org/wikipedia/commons/3/3a/'
     '1906_-_Scott_Joplin%27s_Maple_Leaf_Rag_%281899%29_played_by_the_United_States_Marine_Band.ogg',
     'sha1', 'b76a36d2811a6aede6b3fe3c58c314ba501c4716'),
]


def trim_mp3(data):
    """The ID3v2 tag, the start of the audio, and the ID3v1 tag at the end."""
    if data[:3] != b'ID3':
        raise ValueError('no ID3v2 tag')
    size = 10 + (data[6] << 21 | data[7] << 14 | data[8] << 7 | data[9])
    if data[5] & 0x10:  # footer
        size += 10
    id3v1 = data[-128:] if data[-128:-125] == b'TAG' else b''
    return data[:size + AUDIO_BYTES] + id3v1


def trim_flac(data):
    """The fLaC marker and every metadata block, then the start of the audio."""
    if data[:4] != b'fLaC':
        raise ValueError('not a FLAC file')
    end = 4
    while True:
        flags = data[end]
        end += 4 + int.from_bytes(data[end + 1:end + 4], 'big')
        if flags & 0x80:  # the last metadata block
            return data[:end + AUDIO_BYTES]


def trim_ogg(data):
    """Whole pages: the header packets' pages, then the first page of audio."""
    fileobj = io.BytesIO(data)
    while True:
        if OggPage(fileobj).position > 0:
            return data[:fileobj.tell()]


def trim_m4a(data):
    """Every atom before mdat, unchanged, then mdat cut to the start of the
    audio, with its size field changed to match."""
    start = 0
    while True:
        size, kind = struct.unpack('>I4s', data[start:start + 8])
        if kind == b'mdat':
            audio = data[start + 8:start + 8 + AUDIO_BYTES]
            return data[:start] + struct.pack('>I4s', 8 + len(audio), b'mdat') + audio
        if size < 8:
            raise ValueError(f'unexpected atom size {size} at {start}')
        start += size


TRIM = {'.m4a': trim_m4a, '.mp3': trim_mp3, '.ogg': trim_ogg, '.flac': trim_flac}


def main():
    for name, url, algorithm, published in SOURCES:
        request = urllib.request.Request(
            url, headers={'User-Agent': 'puddletag-tests (https://github.com/puddletag/puddletag)'})
        with urllib.request.urlopen(request) as response:
            data = response.read()
        if hashlib.new(algorithm, data).hexdigest() != published:
            sys.exit(f'{url}: its {algorithm} differs from the published one')
        fixture = TRIM[Path(name).suffix](data)
        (HERE / name).write_bytes(fixture)
        print(f'{name}: {len(data)} -> {len(fixture)} bytes')


if __name__ == '__main__':
    main()
