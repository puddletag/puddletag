"""Field values in every format: several values in one field and non-ASCII
text, in a field every format names (artist) and in a field of the user's
own; saved with the two calls an edit in the main table ends in (update,
then save) and read back with mutagen, and read from files another program
wrote. Synthetic files and values.

A field holds several values (tut3.txt: "Multiple-valued fields are shown
like value1\\\\value2"; id3.txt: "Multiple values are allowed per field").
A field puddletag has no name for is kept under its own: "ID3 frames not
found will be written as TXXX frames", MP4 atoms as freeform ones, and
VorbisComment and APEv2 fields "show with the name they have in the file"
(tags.txt).
"""
import mutagen
import mutagen.apev2
import mutagen.id3
import mutagen.mp4
import pytest

from puddlestuff import audioinfo

VALUES = ['Ünïcödé', '藏經 two']

# Where each tag type keeps the artist and a field named myfield, as
# puddletag writes it. VorbisComment and APEv2 keys don't depend on case.
KEYS = {
    'APEv2': ('Artist', 'Myfield'),
    'ID3': ('TPE1', 'TXXX:myfield'),
    'MP4': ('\xa9ART', '----:com.apple.iTunes:myfield'),
    'VorbisComment': ('ARTIST', 'MYFIELD'),
    'WMA': ('Author', 'myfield'),
}
FORMATS = [('aiff', 'ID3'), ('ape', 'APEv2'), ('dff', 'ID3'), ('dsf', 'ID3'), ('flac', 'VorbisComment'),
           ('m4a', 'MP4'), ('mp3', 'ID3'), ('mpc', 'APEv2'), ('ogg', 'VorbisComment'),
           ('opus', 'VorbisComment'), ('wma', 'WMA'), ('wv', 'APEv2')]
WMA_DROPS_IT = pytest.mark.xfail(strict=True, reason="WMA saves only the fields in wma.py's own table "
                                                     "(Tag.__setitem__), though it reads any")


def stored(path, kind, key):
    """The values the file keeps under key, as mutagen reads them."""
    if kind == 'APEv2':
        return list(mutagen.apev2.APEv2(str(path)).get(key, []))
    tags = mutagen.File(str(path)).tags
    if kind == 'ID3':
        return tags[key].text if key in tags else []
    if key not in tags:
        return []
    if kind == 'MP4' and key.startswith('----'):
        return [bytes(value).decode() for value in tags[key]]
    return [str(value) for value in tags[key]]


def write(path, kind, key, values):
    """Save values under key as another program would, with mutagen."""
    if kind == 'APEv2':
        tag = mutagen.apev2.APEv2(str(path))
        tag[key] = values
        tag.save(str(path))
        return
    audio = mutagen.File(str(path))
    if kind == 'ID3' and key.startswith('TXXX:'):
        audio.tags.add(mutagen.id3.TXXX(encoding=3, desc=key[5:], text=values))
    elif kind == 'ID3':
        audio.tags.add(getattr(mutagen.id3, key)(encoding=3, text=values))
    elif key.startswith('----'):
        audio[key] = [mutagen.mp4.MP4FreeForm(value.encode()) for value in values]
    else:
        audio[key] = values
    audio.save()


def save(path, fields):
    tag = audioinfo.Tag(str(path))
    tag.update(fields)
    tag.save()
    return audioinfo.Tag(str(path))


@pytest.mark.parametrize('ext, kind', FORMATS)
def test_several_values_saved(make_audio, ext, kind):
    path = make_audio('song.' + ext, title='Song')
    tag = save(path, {'artist': VALUES})
    assert (stored(path, kind, KEYS[kind][0]), tag['artist']) == (VALUES, VALUES)


@pytest.mark.parametrize('ext, kind', FORMATS)
def test_several_values_read(make_audio, ext, kind):
    path = make_audio('song.' + ext, title='Song')
    write(path, kind, KEYS[kind][0], VALUES)
    assert audioinfo.Tag(str(path))['artist'] == VALUES


@pytest.mark.parametrize('ext, kind', [pytest.param(*format, marks=WMA_DROPS_IT) if format[0] == 'wma'
                                       else format for format in FORMATS])
def test_field_of_its_own_saved(make_audio, ext, kind):
    path = make_audio('song.' + ext, title='Song')
    tag = save(path, {'myfield': VALUES})
    assert (stored(path, kind, KEYS[kind][1]), tag['myfield']) == (VALUES, VALUES)


@pytest.mark.parametrize('ext, kind', FORMATS)
def test_field_of_its_own_read(make_audio, ext, kind):
    path = make_audio('song.' + ext, title='Song')
    write(path, kind, KEYS[kind][1], VALUES)
    assert audioinfo.Tag(str(path))['myfield'] == VALUES
