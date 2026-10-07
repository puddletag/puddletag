"""MP4 tags (puddlestuff/audioinfo/mp4.py), saved with the two calls an edit
in the main table ends in (update, then save: puddlestuff/util.py write)
and read back with mutagen."""
import mutagen.mp4

from puddlestuff import audioinfo


def test_save_keeps_atoms_puddletag_does_not_map(make_audio):
    # #1071: saving a file with atoms puddletag doesn't map raised
    # "TypeError: b'100' not str" and saved nothing; corubba found the ldes
    # and rate atoms in the reporter's file. rate's "100" is from that
    # traceback; the other values are synthetic.
    path = make_audio('song.m4a', title='Before')
    audio = mutagen.mp4.MP4(path)
    audio['ldes'] = ['A long description']
    audio['rate'] = ['100']
    audio['----:com.apple.iTunes:MOOD'] = [b'Calm']
    audio.save()

    tag = audioinfo.Tag(str(path))
    tag.update({'title': ['After']})
    tag.save()

    saved = mutagen.mp4.MP4(path).tags
    assert saved['\xa9nam'] == ['After']
    assert saved['ldes'] == ['A long description']
    assert saved['rate'] == ['100']
    assert saved['----:com.apple.iTunes:MOOD'] == [b'Calm']


def test_save_keeps_itunes_composer_id(make_audio):
    # #850: saving an edit to a file with iTunes IDs crashed; naul06
    # (2026-05-03) narrowed it to itunescomposerid (the cmID atom, an
    # integer for mutagen), with "'<=' not supported between instances of
    # 'int' and 'str'". Synthetic file and ID.
    path = make_audio('song.m4a', title='Before')
    audio = mutagen.mp4.MP4(path)
    audio['cmID'] = [1234567]
    audio.save()

    tag = audioinfo.Tag(str(path))
    tag.update({'title': ['After']})
    tag.save()

    saved = mutagen.mp4.MP4(path).tags
    assert saved['\xa9nam'] == ['After']
    assert saved['cmID'] == [1234567]
