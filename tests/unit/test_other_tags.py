"""A second tag in a file, besides the one puddletag reads and writes: an
APEv2 or ID3v1 tag in an MP3, an ID3 tag in a FLAC file. What __tag lists
(tags.txt), what the Stored Tags window reads (menus.txt: "the Tags of the
currently selected files as stored on disk", through
tag_versions.tag_values), and the Update From Tag function (function.txt).

Synthetic files and tags.
"""
import mutagen.apev2
import mutagen.id3
import pytest

from puddlestuff import audioinfo
from puddlestuff.audioinfo import tag_versions
from puddlestuff.findfunc import Function, apply_actions

# Where the code differs from the docs, by test and case.
DIFFERS = {
    ('test_tag_lists_every_tag', 'mp3'): "ID3 tags aren't detected: bytes compared with str",
    ('test_tag_lists_every_tag', 'flac'): "ID3 tags aren't detected: bytes compared with str",
    ('test_stored_tags', 'mp3-ID3v1.1'): "ID3 values can't be read: the frames aren't unpacked as pairs",
    ('test_stored_tags', 'flac-ID3v2.4'): "ID3 values can't be read: the frames aren't unpacked as pairs",
    ('test_update_from_tag', 'flac-ID3-title;artist'): 'the ID3 tag is read as an MP3, which a FLAC file is not',
    ('test_update_from_tag', 'mp3-APEv2-~title;artist'): "the first field keeps its ~, so it isn't left out",
}


@pytest.fixture(autouse=True)
def _differs(request):
    callspec = getattr(request.node, 'callspec', None)
    reason = DIFFERS.get((request.node.originalname, callspec.id if callspec else None))
    if reason:
        request.applymarker(pytest.mark.xfail(strict=True, reason=reason))


def mp3_with_apev2(make_audio):
    """An MP3 with ID3v2.4 and ID3v1 tags, as puddletag saves it, and an
    APEv2 tag before the ID3v1 one, which ends the file."""
    path = make_audio('song.mp3', title='ID3 title', artist='ID3 artist')
    apev2 = mutagen.apev2.APEv2()
    apev2.update({'Title': 'APE title', 'Artist': 'APE artist', 'Album': 'APE album'})
    apev2.save(str(path))
    audioinfo.Tag(str(path)).save()  # adds ID3v1, "Create an ID3v1 tag" (preferences.txt)
    return path


def flac_with_id3(make_audio):
    """A FLAC file with an ID3v2.4 tag before its VorbisComment."""
    path = make_audio('song.flac', title='Vorbis title')
    id3 = mutagen.id3.ID3()
    id3.add(mutagen.id3.TIT2(encoding=3, text=['ID3 title']))
    id3.add(mutagen.id3.TPE1(encoding=3, text=['ID3 artist', 'ID3 other']))
    id3.add(mutagen.id3.TALB(encoding=3, text=['ID3 album']))
    id3.save(str(path))
    return path


FILES = {'mp3': mp3_with_apev2, 'flac': flac_with_id3}


@pytest.mark.parametrize('kind, tags', [('mp3', ['ID3v2.4', 'ID3v1.1', 'APEv2']),
                                        ('flac', ['VorbisComment', 'ID3v2.4'])], ids=['mp3', 'flac'])
def test_tag_lists_every_tag(make_audio, kind, tags):
    # tags.txt: "Comma-Separated list of tags found in file. Eg.
    # VorbisComment, ID3v2.4, ID3v1.1": the tag puddletag reads first.
    listed = audioinfo.Tag(str(FILES[kind](make_audio)))['__tag'].split(', ')
    assert (listed[0], sorted(listed)) == (tags[0], sorted(tags))


@pytest.mark.parametrize('kind, tag, values', [
    ('mp3', 'APEv2', {'title': ['APE title'], 'artist': ['APE artist'], 'album': ['APE album']}),
    ('mp3', 'ID3v1.1', {'title': ['ID3 title'], 'artist': ['ID3 artist']}),
    ('flac', 'ID3v2.4', {'title': ['ID3 title'], 'artist': ['ID3 artist', 'ID3 other'], 'album': ['ID3 album']}),
], ids=['mp3-APEv2', 'mp3-ID3v1.1', 'flac-ID3v2.4'])
def test_stored_tags(make_audio, kind, tag, values):
    # tags.txt and id3.txt name the fields: TIT2 is title, and so on.
    assert dict(tag_versions.tag_values(str(FILES[kind](make_audio)), tag)) == values


def update_from_tag(path, fields, tag_type):
    action = Function('update_from_tag')
    action.setTag(['__all'])
    action.setArgs([fields, tag_type])
    return apply_actions([action], audioinfo.Tag(str(path)))


@pytest.mark.parametrize('kind, tag_type, fields, expected', [
    # "Updates the fields specified with the values found in Tag type."
    ('mp3', 'APEv2', 'title;artist', {'title': ['APE title'], 'artist': ['APE artist']}),
    # function.txt's own case: "If your FLAC file has an ID3 tag ... update
    # the FLAC tag with the ID3 tag's contents".
    ('flac', 'ID3', 'title;artist', {'title': ['ID3 title'], 'artist': ['ID3 artist', 'ID3 other']}),
    # "Start the list with the tilde (~) character to update all the fields
    # except the ones in the list."
    ('mp3', 'APEv2', '~title;artist', {'album': ['APE album']}),
], ids=['mp3-APEv2-title;artist', 'flac-ID3-title;artist', 'mp3-APEv2-~title;artist'])
def test_update_from_tag(make_audio, kind, tag_type, fields, expected):
    assert update_from_tag(FILES[kind](make_audio), fields, tag_type) == expected


@pytest.mark.parametrize('kind, tag_type, read', [('mp3', 'APEv2', mutagen.apev2.APEv2),
                                                  ('flac', 'ID3', mutagen.id3.ID3)], ids=['mp3', 'flac'])
def test_update_from_tag_keeps_that_tag(make_audio, kind, tag_type, read):
    # "The tag will be not be changed in any manner": the APEv2 or ID3 tag
    # is as it was after the update is saved.
    path = FILES[kind](make_audio)
    before = dict(read(str(path)))
    tag = audioinfo.Tag(str(path))
    tag.update(update_from_tag(path, '', tag_type))
    tag.save()
    assert {k: str(v) for k, v in read(str(path)).items()} == {k: str(v) for k, v in before.items()}
