"""WMA tags (puddlestuff/audioinfo/wma.py), saved with the two calls an edit
in the main table ends in (update, then save: puddlestuff/util.py write)
and read back with mutagen. Synthetic files and values."""
import mutagen.asf
import pytest
from mutagen.asf import ASFBoolAttribute, ASFDWordAttribute

from puddlestuff import audioinfo


def save(path, fields):
    tag = audioinfo.Tag(str(path))
    tag.update(fields)
    tag.save()
    return mutagen.asf.ASF(path).tags, audioinfo.Tag(str(path))


def test_save_keeps_attributes_puddletag_does_not_show(make_audio):
    # An edit leaves alone what it doesn't touch, here attributes of kinds
    # puddletag doesn't show: text with a / in its name, a number, true or
    # false. Before, every save deleted them.
    path = make_audio('song.wma', title='Before')
    audio = mutagen.asf.ASF(path)
    audio['IsVBR'] = [ASFBoolAttribute(True)]
    audio['WM/Provider'] = ['A store']
    audio['WM/SharedUserRating'] = [ASFDWordAttribute(99)]
    audio.save()
    attributes, tag = save(path, {'title': ['After']})
    assert {key: [value.value for value in values] for key, values in attributes.items()} == {
        'IsVBR': [True], 'Title': ['After'], 'WM/Provider': ['A store'], 'WM/SharedUserRating': [99]}


def stored(attributes):
    return {key: [str(value) for value in values] for key, values in attributes.items()}


@pytest.mark.parametrize('field', ['comment', 'comment:'])
def test_comment(make_audio, field):
    # tags.txt: "comment is the Description attribute"; it "used to show as
    # comment:", and "writing those still sets them".
    attributes, tag = save(make_audio('song.wma'), {field: ['A comment']})
    assert (stored(attributes), audioinfo.usertags(tag)) == (
        {'Description': ['A comment']}, {'comment': ['A comment']})


@pytest.mark.parametrize('field, value, lyrics', [
    # "unsyncedlyrics is WM/Lyrics, plain text as in MP4: a language and
    # description in front aren't saved", and lyrics, its old name, still
    # writes it.
    ('unsyncedlyrics', 'Some lyrics', 'Some lyrics'),
    ('unsyncedlyrics', 'eng||Some lyrics', 'Some lyrics'),
    ('unsyncedlyrics', 'eng|Description|Some lyrics', 'Some lyrics'),
    ('unsyncedlyrics', 'Verse 1 | Chorus', 'Verse 1 | Chorus'),
    ('lyrics', 'Some lyrics', 'Some lyrics'),
])
def test_lyrics(make_audio, field, value, lyrics):
    attributes, tag = save(make_audio('song.wma'), {field: [value]})
    assert (stored(attributes), audioinfo.usertags(tag)) == ({'WM/Lyrics': [lyrics]}, {'unsyncedlyrics': [lyrics]})


def test_name_it_cant_store(make_audio):
    # tags.txt: WMA's field names "can't contain /"; such a field "isn't
    # saved: puddletag reports it as it does a file it can't write, and the
    # file keeps its tags".
    path = make_audio('song.wma', title='Song')
    tag = audioinfo.Tag(str(path))
    tag.update({'my/field': ['x'], 'title': ['New']})
    with pytest.raises(EnvironmentError) as error:
        tag.save()
    assert 'my/field' in error.value.strerror and 'WMA' in error.value.strerror
    assert stored(mutagen.asf.ASF(path).tags) == {'Title': ['Song']}


def test_clearing_a_field_the_file_lacks(make_audio):
    # Clearing a field leaves the file without it, whether it had it or not;
    # before, a field the file lacked raised KeyError.
    attributes, tag = save(make_audio('song.wma', title='Song'), {'myfield': [], 'title': []})
    assert stored(attributes) == {}
