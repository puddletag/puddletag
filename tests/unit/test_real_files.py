"""Real files whose tags other programs wrote: public-domain recordings cut
down to their tags (tests/data/README.md has their sources and licenses).

Expected values are each file's own tags, named as docsrc/source/tags.txt
and id3.txt say puddletag shows them.
"""
import shutil
from pathlib import Path

import mutagen
import pytest

from puddlestuff import audioinfo

DATA = Path(__file__).parent.parent / 'data'
CHOPIN = 'Musopen: The Complete Works of Frédéric Chopin'

# Every field each file shows, unless noted.
SHOWN = {
    # X Lossless Decoder: tags.txt's MP4 atoms.
    'musopen-canon.m4a': {
        'artist': ['Aya Higuchi'], 'album': [CHOPIN], 'composer': ['Frédéric Chopin'],
        'encodedby': ['X Lossless Decoder 20140504, QuickTime 7.7.3'], 'genre': ['Classical'],
        'year': ['2015'], 'partofcompilation': ['Yes'],
    },
    # archive.org's copy of the same: ID3v2.3 and ID3v1. id3.txt: "The first
    # COMM frame encountered without a description will be used as the
    # comment field", and text after "comment:" is a frame's description;
    # mutagen describes the ID3v1 comment as "ID3v1 Comment". Not every
    # field: id3.txt doesn't say how a second COMM frame without a
    # description shows (this file has one in another language).
    'musopen-canon.mp3': {
        'title': ['tmp'], 'audiolength': ['42.98'],
        'encodingsettings': ['LAME 64bits version 3.99.5 (http://lame.sf.net)'],
        'comment': ['https://archive.org/details/musopen-chopin'],
        'comment:ID3v1 Comment': ['https://archive.org/details/'],
    },
    # archive.org's copy of the same, with its own fields.
    'musopen-canon.ogg': {
        'artist': ['Aya Higuchi'], 'album': [CHOPIN], 'genre': ['Classical'], 'year': ['2015'],
        'comment': ['http://archive.org/details/musopen-chopin'], 'encoder': ['Lavc55.68.101 libvorbis'],
        'crc32': ['a69965a3'], 'format': ['Apple Lossless Audio'],
        'md5': ['fadb5931ccf05e3bfb24d4cea337f7f9'], 'mtime': ['1422569158'],
        'sha1': ['f7c36328f629d52e63d3d384531a902d7f8df237'], 'size': ['6807260'],
        'source': ['original'],
    },
    # Two TITLE values, upper-case names but a lower-case "website".
    'musopen-goldberg-aria.flac': {
        'title': ['Goldberg Variations, BWV. 988', 'Aria'], 'artist': ['Shelley Katz'],
        'albumartist': ['Shelley Katz'], 'album': ['Musopen Kickstarter Project'], 'year': ['2012'],
        'track': ['01'], 'genre': ['Classical'], 'composer': ['Johann Sebastian Bach'],
        'website': ['http://musopen.org/'],
    },
    # Not every field: it also has a comment without "=", which mutagen names
    # unknown0.
    'marine-band-maple-leaf-rag.ogg': {
        'title': ['Maple Leaf Rag (1906)'], 'artist': ['United States Marine Band'], 'year': ['1906'],
        'album': ['Victor-4911'], 'comment': ['None'], 'genre': ['Acoustic Era'],
    },
}
EVERY_FIELD = {'musopen-canon.m4a', 'musopen-canon.ogg', 'musopen-goldberg-aria.flac'}


@pytest.mark.parametrize('name', sorted(SHOWN))
def test_reads_the_tags_as_written(name):
    tag = audioinfo.Tag(str(DATA / name))
    if name in EVERY_FIELD:
        assert audioinfo.usertags(tag) == SHOWN[name]
    else:
        assert {field: tag.get(field) for field in SHOWN[name]} == SHOWN[name]


def test_reads_the_cover():
    # The M4A's one cover, a 120417-byte JPEG.
    tag = audioinfo.Tag(str(DATA / 'musopen-canon.m4a'))
    assert (tag['__num_images'], tag['__image_mimetype']) == ('1', 'image/jpeg')
    assert len(tag['__image'][0]['data']) == 120417


def stored(path):
    """The file's tags as mutagen reads them, each value a list of text or
    bytes."""
    tags = mutagen.File(path).tags
    items = tags.as_dict().items() if hasattr(tags, 'as_dict') else tags.items()
    stored = {}
    for key, value in items:
        value = getattr(value, 'text', value)
        stored[key] = [v if isinstance(v, bytes) else str(v)
                       for v in (value if isinstance(value, list) else [value])]
    return stored


GENRE = {'.m4a': '©gen', '.mp3': 'TCON'}


@pytest.mark.parametrize('name', sorted(SHOWN))
def test_editing_a_field_keeps_the_others(name, tmp_path):
    path = tmp_path / name
    shutil.copy(DATA / name, path)
    before = stored(path)
    tag = audioinfo.Tag(str(path))
    tag.update({'genre': ['Test']})
    tag.save()
    after = stored(path)
    genre = GENRE.get(path.suffix, 'genre')
    before.pop(genre, None)
    assert after.pop(genre) == ['Test']
    assert after == before
