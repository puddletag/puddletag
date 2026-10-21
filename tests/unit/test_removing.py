"""Removing fields and tags in every format: fields saved with the two calls
an edit in the main table ends in (update, then save), and Remove Tag,
which the table runs as the tag's delete on each selected file
(TagModel.deleteTag). Synthetic files and tags.

A field is removed three ways the docs describe: <blank> in the Tag Panel
("To remove a field, change the text to <blank> and the field'll be removed
upon saving", tut1.txt), saved as an empty list, as an emptied cell in the
table is; Cut ("Works like Copy Selection, but removes the selected
fields", menus.txt), saved as empty text; and the Remove Fields function
(function.txt). Remove Tag (menus.txt): "Removes the tags of selected
files."
"""
import mutagen
import pytest

from puddlestuff import audioinfo
from test_covers import BACK, FORMATS, FRONT, apply_function, save, write

FIELDS = {'artist': ['Artist'], 'comment': ['Comment'], 'custom': ['Custom'], 'genre': ['Genre']}
REMOVED = ['comment', 'custom', 'genre']


def native(path):
    """The keys of the file's tag, as mutagen reads them."""
    tags = mutagen.File(str(path)).tags
    return [] if tags is None else sorted(str(key) for key in tags.keys())


@pytest.mark.parametrize('how', ['blank', 'cut', 'remove_fields'])
@pytest.mark.parametrize('ext', FORMATS)
def test_fields_removed(make_audio, ext, how):
    # The file ends up as one that never had them: the same keys as a file
    # saved with only the fields left. comment is a frame of its own in
    # ID3, MP4 and WMA; custom is a field of the user's own.
    path = make_audio('song.' + ext, title='Song')
    save(path, FIELDS)
    if how == 'remove_fields':
        changes = apply_function('remove_fields', path, fields=REMOVED)
    else:
        changes = {field: [] if how == 'blank' else '' for field in REMOVED}
    tag = save(path, changes)
    reference = make_audio('reference.' + ext, title='Song')
    save(reference, {'artist': ['Artist']})
    assert (audioinfo.usertags(tag), native(path)) == ({'artist': ['Artist'], 'title': ['Song']}, native(reference))


@pytest.mark.parametrize('ext', FORMATS)
def test_tag_removed(make_audio, ext):
    # Every field and the covers go, in the table (the tag it removed from)
    # and in the file, where __num_images is "Number of cover images found
    # in the file" (tags.txt); the audio stays. Before, a FLAC file kept its
    # pictures, and a file without an ID3 tag had no __num_images.
    path = make_audio('song.' + ext, title='Song', artist='Artist')
    write(path, [FRONT, BACK])
    tag = audioinfo.Tag(str(path))
    length = tag['__length']
    tag.delete()
    again = audioinfo.Tag(str(path))
    assert [(audioinfo.usertags(t), t['__image'], t.get('__num_images')) for t in (tag, again)] == [({}, [], '0')] * 2
    assert (native(path), again['__length']) == ([], length)


def test_remove_tag_leaves_no_padding(make_audio):
    # menus.txt: "Remove Tag (Ctrl+R): Removes the tags of selected files."
    # #469 reports space left in an MP3 after removing the fields; the tag
    # goes whole, padding included: the file starts with the audio and has
    # no ID3v1 tag. Synthetic file and tags.
    path = make_audio('song.mp3', title='Song', artist='Artist', album='Album')
    save(path, {'genre': ['Genre']})
    audioinfo.Tag(str(path)).delete()
    data = path.read_bytes()
    assert (data[:3] != b'ID3', data[-128:-125] != b'TAG', data[:1]) == (True, True, b'\xff')


def test_remove_all_fields_except_nothing_leaves_padding(make_audio):
    # #469: after "Remove all fields except" with nothing kept, the MP3
    # starts with an ID3v2 header and zero bytes. By design: mutagen keeps
    # the tag's padding so the next save needn't rewrite the file; Remove
    # Tag removes it. Synthetic file and tags.
    path = make_audio('song.mp3', title='Song', artist='Artist', album='Album')
    save(path, apply_function('remove_except', path, ''))
    data = path.read_bytes()
    size = sum(b << shift for b, shift in zip(data[6:10], (21, 14, 7, 0)))  # synchsafe
    assert (data[:3], size > 0, set(data[10:10 + size]), native(path)) == (b'ID3', True, {0}, [])
