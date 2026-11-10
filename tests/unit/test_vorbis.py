"""VorbisComment tags (puddlestuff/audioinfo/vorbis.py) in FLAC, Ogg Vorbis
and Opus files, saved with the two calls an edit in the main table ends in
(update, then save) and read back with mutagen. Vorbis keys don't depend on
case, so only the key-case tests compare it. Synthetic files and values.
"""
import base64
import json
import os
import shutil
import subprocess

import mutagen
import mutagen.flac
import pytest

from puddlestuff import audioinfo

VORBIS_FORMATS = ['flac', 'ogg', 'opus']

# Synthetic values, after the comments #1072's reporter showed.
CHAPTERS = [('TITLE', 'Before'), ('CHAPTER001', '00:00:00.000'), ('CHAPTER001NAME', 'One'),
            ('CHAPTER002', '00:00:00.500'), ('CHAPTER002NAME', 'Two'), ('ARTIST', 'A1'), ('ARTIST', 'A2')]


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


def picture_comment():
    """A cover as a METADATA_BLOCK_PICTURE comment, as Ogg files keep one."""
    picture = mutagen.flac.Picture()
    picture.type, picture.mime, picture.data = 3, 'image/jpeg', b'\xff\xd8\xff\xd9'
    return ('METADATA_BLOCK_PICTURE', base64.b64encode(picture.write()).decode('ascii'))


@pytest.mark.xfail(strict=True, reason='a save writes the comments in another order')
def test_save_keeps_the_order_of_comments(vorbis_file):
    # No docs say what order the comments take. #611 ("Tags written out of
    # order") and #1072 (an Opus file's chapters, whose titles ffprobe no
    # longer read after an edit) show it matters; corubba on #611: nothing in
    # the spec mandates an order. Decided 2026-11-10: a save keeps the file's
    # order.
    write_comments(vorbis_file, CHAPTERS)
    save(vorbis_file, {'title': ['After']})
    assert comments(vorbis_file) == [('TITLE', 'After')] + CHAPTERS[1:]


@pytest.mark.xfail(strict=True, reason='a save writes the comments in another order')
def test_new_fields_go_after_the_file_s(vorbis_file):
    # Decided 2026-11-10: the fields an edit adds go after the file's
    # comments (no docs say where they go).
    write_comments(vorbis_file, CHAPTERS)
    save(vorbis_file, {'album': ['New'], 'title': ['After']})
    assert comments(vorbis_file) == [('TITLE', 'After')] + CHAPTERS[1:] + [('ALBUM', 'New')]


@pytest.mark.xfail(strict=True, reason='a save writes the comments in another order')
def test_removed_field_leaves_the_others_in_order(vorbis_file):
    # Decided 2026-11-10: a save keeps the file's order, so emptying a field
    # leaves the others where they were.
    write_comments(vorbis_file, CHAPTERS)
    save(vorbis_file, {'chapter001name': []})
    assert comments(vorbis_file) == [pair for pair in CHAPTERS if pair[0] != 'CHAPTER001NAME']


@pytest.mark.xfail(strict=True, reason='a save writes the comments in another order')
@pytest.mark.parametrize('ext', ['ogg', 'opus'])
def test_cover_keeps_its_place(make_audio, ext):
    # Decided 2026-11-10: a save keeps the file's order, the cover's comment
    # included. puddletag re-encodes the picture, so only the keys and the
    # image data are compared.
    path = make_audio('song.' + ext)
    write_comments(path, CHAPTERS[:3] + [picture_comment()] + CHAPTERS[3:])
    save(path, {'title': ['After']})
    assert [key for key, value in comments(path)] == [
        'TITLE', 'CHAPTER001', 'CHAPTER001NAME', 'METADATA_BLOCK_PICTURE', 'CHAPTER002', 'CHAPTER002NAME',
        'ARTIST', 'ARTIST']
    assert audioinfo.Tag(str(path))['__image'][0]['data'] == b'\xff\xd8\xff\xd9'


@pytest.mark.xfail(strict=True, reason="an edit deletes a FLAC file's picture comment")
def test_flac_keeps_a_picture_comment(make_audio):
    # news.txt:1056: "There was a pretty nasty bug where puddletag would
    # remove any unsupported tags. Sorry about that, hopefully you haven't
    # lost any priceless info because of it." A FLAC file's picture comment
    # isn't shown (the picture blocks are); decided 2026-11-10: an edit keeps
    # it as it is.
    path = make_audio('song.flac')
    write_comments(path, [('TITLE', 'Before'), picture_comment(), ('ARTIST', 'A')])
    save(path, {'title': ['After']})
    assert comments(path) == [('TITLE', 'After'), picture_comment(), ('ARTIST', 'A')]


def test_remove_tag_removes_a_flac_picture_comment(make_audio):
    # menus.txt:103, Remove Tag: "Removes the tags of selected files. Note
    # that although this operation can be undone, the tag is not restored as
    # it was before: a new one is created, and only supported fields are
    # restored." Decided 2026-11-10: Remove Tag removes the picture comment
    # too.
    path = make_audio('song.flac')
    write_comments(path, [('TITLE', 'Before'), picture_comment(), ('ARTIST', 'A')])
    audioinfo.Tag(str(path)).delete()
    audio = mutagen.File(str(path))
    assert not audio.tags
    assert audio.pictures == []


@pytest.mark.xfail(strict=True, reason='a save writes the comments in another order')
def test_chapter_titles_still_read_by_ffprobe(make_audio):
    # #1072: "chapter entries are destroyed" after an edit. ffmpeg reads a
    # chapter's NAME only after the chapter, so a save that moves them apart
    # leaves the chapters without titles. Decided 2026-11-10: ffprobe still
    # reads an Opus file's chapter titles after an edit.
    ffprobe = shutil.which('ffprobe')
    if ffprobe is None:
        if os.environ.get('CI'):
            pytest.fail('ffprobe is missing')
        pytest.skip('ffprobe is missing')
    path = make_audio('song.opus', seconds=3)
    write_comments(path, [('CHAPTER002', '00:00:01.000') if pair[0] == 'CHAPTER002' else pair for pair in CHAPTERS])
    save(path, {'title': ['After']})
    out = subprocess.run([ffprobe, '-v', 'error', '-show_chapters', '-of', 'json', str(path)],
                         capture_output=True, text=True, check=True).stdout
    assert [c.get('tags', {}).get('title') for c in json.loads(out)['chapters']] == ['One', 'Two']
