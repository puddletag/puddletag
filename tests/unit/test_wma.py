"""WMA tags (puddlestuff/audioinfo/wma.py), saved with the two calls an edit
in the main table ends in (update, then save: puddlestuff/util.py write)
and read back with mutagen. Synthetic files and values."""
import mutagen.asf
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
