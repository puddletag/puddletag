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
from test_covers import BACK, FORMATS, FRONT, ID3, apply_function, save, write

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


def removed_tag(ext):
    if ext in ID3:
        # tags.txt, __num_images: "Number of cover images found in the file."
        return pytest.param(ext, marks=pytest.mark.xfail(
            strict=True, reason='code differs from the docs: a file without an ID3 tag has no __num_images'))
    return ext


@pytest.mark.parametrize('ext', [removed_tag(ext) for ext in FORMATS])
def test_tag_removed(make_audio, ext):
    # Every field and the covers go, in the table (the tag it removed from)
    # and in the file; the audio stays. Before, a FLAC file kept its
    # pictures.
    path = make_audio('song.' + ext, title='Song', artist='Artist')
    write(path, [FRONT, BACK])
    tag = audioinfo.Tag(str(path))
    length = tag['__length']
    tag.delete()
    again = audioinfo.Tag(str(path))
    assert [(audioinfo.usertags(t), t['__image'], t.get('__num_images')) for t in (tag, again)] == [({}, [], '0')] * 2
    assert (native(path), again['__length']) == ([], length)
