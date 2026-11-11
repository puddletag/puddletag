"""The helpers every tag format shares (puddlestuff/audioinfo/util.py)
and the tag mapping (audioinfo.setmapping): what the tag classes, the
table and the clipboard get from them. Expected values come from
docsrc/source/tags.txt where it covers them, otherwise from the
maintainer's decisions. Synthetic values and files."""
import os
import time
from copy import deepcopy

import pytest

from puddlestuff import audioinfo
from puddlestuff.audioinfo import util


@pytest.fixture
def song(make_audio, tmp_path):
    """A synthetic MP3 in Artist/Album."""
    return make_audio('song.mp3', tmp_path / 'Artist' / 'Album', artist='Artist', title='Song')


@pytest.fixture
def new_york(monkeypatch):
    """A zone whose clocks are 4 or 5 hours behind UTC, given as a
    POSIX rule so no time-zone data is needed."""
    monkeypatch.setenv('TZ', 'EST5EDT,M3.2.0,M11.1.0')
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def test_unicode_list():
    assert util.unicode_list('x') == ['x']
    assert util.unicode_list(5) == ['5']
    assert util.unicode_list(['a', None, '', 3]) == ['a', '3']


@pytest.mark.parametrize('value, empty', [
    ('', True), ([], True), (['', None], True), ([0], False),
    (0, False), (['x'], False), (None, True), (['', 'x'], False)])
def test_isempty(value, empty):
    assert util.isempty(value) is empty


def test_common_values_of_plain_dicts():
    tags = [{'artist': ['A'], 'title': 'T'}, {'artist': ['A'], 'title': ['U']}]
    assert util.commontags(tags) == (
        {'__image': None, 'artist': ['A'], 'title': ['T', 'U']},
        {'artist': 2, 'title': 1}, set())


def test_common_images():
    assert util.commonimages([]) is None
    image = {'data': b'xx', 'mime': 'image/png'}
    assert util.commonimages([image, dict(image)]) == image
    assert util.commonimages([image, {'data': b'yy', 'mime': 'image/png'}]) == 0


def test_cover_of_an_unknown_type_counts_as_front():
    assert util.cover_info([{'data': b'xx', 'imagetype': 30, 'mime': 'image/png'}]) == {
        '__image_mimetype': 'image/png', '__image_size': '2',
        '__image_type': 'Cover (Front)', '__num_images': '1'}


def test_no_covers_drops_the_old_cover_fields():
    assert util.cover_info([]) == {'__image_mimetype': '', '__num_images': '0'}
    info = {'__image_mimetype': 'a', '__image_size': '3'}
    util.cover_info([], info)
    assert info == {'__num_images': '0'}


def test_mime_and_size_of_data_that_is_no_image():
    assert util.get_mime(b'\x00\x01\x02\x03') == ''
    assert util.get_image_dimensions(b'junk') == (0, 0)


def test_length_back_to_seconds():
    # "MM:SS format, or HH:MM:SS from an hour on, e.g. 03:25 or 01:02:05"
    assert util.lnglength('01:02:05') == 3725
    assert util.lnglength('03:25') == 205


def test_text_helpers():
    assert util.to_string(None) == ''
    assert util.to_string(5) == '5'
    assert util.to_string(['a', 'b']) == 'a'
    assert util.path_to_string('') == ''
    assert util.path_to_string(['/a', '/b']) == '/a'
    assert util.decode_fn(b'caf\xc3\xa9') == 'caf\xe9'


def test_string_values_for_patterns():
    tags = {1: 'x', '__path': '/p', 'a': '', 'b': ['x', 'y'], 'c': [''], 'd': 5}
    # the table's separator is two backslashes
    assert util.stringtags(tags) == {'__path': '/p', 'b': 'x\\\\y', 'd': '5'}
    assert util.stringtags({'a': '', 'c': [''], 'e': None}, leaveNone=True) == {
        'a': '', 'c': '', 'e': ''}


def test_caseless_dict():
    caseless = util.CaselessDict({'Artist': 1})
    assert 'artist' in caseless
    assert caseless['ARTIST'] == 1
    assert caseless.get('x', 9) == 9
    caseless['ARTIST'] = 2
    assert dict(caseless) == {'ARTIST': 2}
    del caseless['artist']
    assert not caseless


def test_caseless_dict_copy():
    copied = deepcopy(util.CaselessDict([('A', [1])]))
    assert isinstance(copied, util.CaselessDict)
    assert dict(copied) == {'A': [1]}
    assert 'a' in copied


def test_tag_to_json_of_a_path(song):
    tag = util.tag_to_json(str(song))
    assert tag['artist'] == ['Artist']
    assert tag['title'] == ['Song']
    assert '__path' in tag


def test_tag_to_json_of_some_fields(song):
    assert util.tag_to_json(str(song), ['__image', 'nope', 'title']) == {'title': ['Song']}


def test_tag_to_json_of_a_file_it_cannot_read(tmp_path, caplog):
    notes = tmp_path / 'notes.txt'
    notes.write_text('hi')
    assert util.tag_to_json(str(notes)) is None
    assert util.tag_to_json(str(tmp_path / 'gone.mp3')) is None
    assert any(record.levelname == 'ERROR' and record.getMessage().startswith('Invalid File:')
               for record in caplog.records)


def test_tag_update_clear_and_save(song):
    tag = audioinfo.Tag(str(song))
    tag.update([('album', ['Al'])])
    assert tag['album'] == ['Al']
    before = dict(tag)
    tag.update(None)
    assert dict(tag) == before
    assert len(tag.values()) == len(list(tag))
    assert tag.stringtags()['album'] == 'Al'
    tag.clear()
    assert tag.usertags == {}
    tag.save()
    assert audioinfo.usertags(audioinfo.Tag(str(song))) == {}


def test_save_of_a_removed_file(song):
    tag = audioinfo.Tag(str(song))
    os.remove(song)
    tag.update({'title': ['New']})
    with pytest.raises(FileNotFoundError) as error:
        tag.save()
    assert error.value.filename == str(song)


def test_file_times_are_utc(song, new_york):
    # "The last time the file was modified in YYYY-MM-DD HH:MM:SS format.
    # The time is in UTC."
    tag = audioinfo.Tag(str(song))
    utc = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(os.path.getmtime(song)))
    assert tag['__modified'] == utc
    assert tag['__file_mod_datetime'] == utc


@pytest.fixture
def restored_mappings(monkeypatch):
    """setmapping merges a global mapping into each tag class's own and
    replaces only the tag types its mapping names: every class gets its
    mapping back after the test."""
    monkeypatch.setattr(audioinfo, 'mapping', audioinfo.mapping)
    monkeypatch.setattr(audioinfo, 'revmapping', deepcopy(audioinfo.revmapping))
    for cls in {kind[1] for kind in audioinfo.extensions.values()}:
        monkeypatch.setattr(cls, 'mapping', deepcopy(cls.mapping))
        monkeypatch.setattr(cls, 'revmapping', deepcopy(cls.revmapping))


@pytest.mark.xfail(strict=True, reason='a global mapping is listed and saved again under each tag type')
def test_global_mapping_leaves_the_tag_types_own(restored_mappings, make_audio, tmp_path):
    # preferences.txt: "A mapping whose Tag is global applies to every tag
    # type." Synthetic mapping and file.
    m = {'VorbisComment': {'tracknumber': 'track'}, 'global': {'comment': 'notes'}}

    audioinfo.setmapping(m)

    assert m['VorbisComment'] == {'tracknumber': 'track'}
    tag = audioinfo.Tag(str(make_audio('song.flac', tmp_path, comment='C', tracknumber='3')))
    assert tag['notes'] == ['C']
    assert tag['track'] == ['3']
