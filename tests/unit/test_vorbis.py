"""VorbisComment tags (puddlestuff/audioinfo/vorbis.py) in FLAC, Ogg Vorbis
and Opus files, saved with the two calls an edit in the main table ends in
(update, then save) and read back with mutagen. Vorbis keys don't depend on
case, so only the key-case tests compare it. Synthetic files and values.
"""
import mutagen
import pytest

from puddlestuff import audioinfo

VORBIS_FORMATS = ['flac', 'ogg', 'opus']


@pytest.fixture(params=VORBIS_FORMATS)
def vorbis_file(request, make_audio):
    return make_audio('song.' + request.param)


def write_comments(path, comments):
    """Replace the file's comments with these (key, value) pairs, as written."""
    audio = mutagen.File(str(path))
    audio.tags.clear()
    audio.tags.extend(comments)
    audio.save()


def comments(path):
    """The file's comments as (key, value) pairs."""
    return list(mutagen.File(str(path)).tags)


def upper(pairs):
    return sorted((key.upper(), value) for key, value in pairs)


def save(path, fields):
    tag = audioinfo.Tag(str(path))
    tag.update(fields)
    tag.save()


def test_names(vorbis_file):
    # tags.txt: VorbisComment fields "show with the name they have in the
    # file, in lower case (TITLE shows as title)", except "tracknumber shows
    # as track, and date as year".
    write_comments(vorbis_file, [('DATE', '2001'), ('MyField', 'x'), ('TITLE', 'Song'), ('TRACKNUMBER', '3')])
    assert audioinfo.usertags(audioinfo.Tag(str(vorbis_file))) == {
        'myfield': ['x'], 'title': ['Song'], 'track': ['3'], 'year': ['2001']}


def test_names_saved(vorbis_file):
    save(vorbis_file, {'myfield': ['x'], 'title': ['Song'], 'track': ['3'], 'year': ['2001']})
    assert upper(comments(vorbis_file)) == [
        ('DATE', '2001'), ('MYFIELD', 'x'), ('TITLE', 'Song'), ('TRACKNUMBER', '3')]


def test_several_values_and_non_ascii_text(vorbis_file):
    # tut3.txt: a field can hold several values; VorbisComment keeps each in
    # a comment of its own, as UTF-8.
    write_comments(vorbis_file, [('ARTIST', 'Ünïcödé'), ('ARTIST', '藏經')])
    assert audioinfo.Tag(str(vorbis_file))['artist'] == ['Ünïcödé', '藏經']
    save(vorbis_file, {'artist': ['Ćafé', '☕ two']})
    assert upper(comments(vorbis_file)) == [('ARTIST', 'Ćafé'), ('ARTIST', '☕ two')]


def test_saving_keeps_the_case_of_keys(vorbis_file):
    # #419: "When saving tags puddletag force changes the case of tag names
    # to lower case ... even when the tag values for the specific fields were
    # not changed": R128_TRACK_GAIN became r128_track_gain, which MPD missed.
    write_comments(vorbis_file, [('Album', 'Record'), ('R128_TRACK_GAIN', '-512'), ('TITLE', 'Song')])
    save(vorbis_file, {'title': ['New']})
    assert sorted(comments(vorbis_file)) == [('Album', 'Record'), ('R128_TRACK_GAIN', '-512'), ('TITLE', 'New')]


@pytest.mark.parametrize('name', ['a=b', 'a~b', 'título', '藏經'])
def test_name_it_cant_store(vorbis_file, name):
    # tags.txt: VorbisComment's field names "are ASCII from space to } and
    # can't contain ="; a field whose name the format can't take "isn't
    # saved: puddletag reports it as it does a file it can't write, and the
    # file keeps its tags".
    write_comments(vorbis_file, [('TITLE', 'Song')])
    tag = audioinfo.Tag(str(vorbis_file))
    tag.update({name: ['x'], 'title': ['New']})
    with pytest.raises(EnvironmentError) as error:
        tag.save()
    assert name in error.value.strerror and 'VorbisComment' in error.value.strerror
    assert comments(vorbis_file) == [('TITLE', 'Song')]


def test_new_keys_in_upper_case(vorbis_file):
    # tags.txt: "A new key is saved ... in upper case in VorbisComment".
    save(vorbis_file, {'myfield': ['x'], 'title': ['Song'], 'track': ['3']})
    assert sorted(comments(vorbis_file)) == [('MYFIELD', 'x'), ('TITLE', 'Song'), ('TRACKNUMBER', '3')]
