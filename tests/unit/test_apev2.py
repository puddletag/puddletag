"""APEv2 tags (puddlestuff/audioinfo/apev2.py) in Monkey's Audio, Musepack
and WavPack files, saved with the two calls an edit in the main table ends
in (update, then save) and read back with mutagen.

The disc number and the album artist are discnumber and albumartist in
every other format, the tag sources and the docs (tags.txt). APEv2 files
keep them as Disc and Album Artist (foobar2000, Winamp), or AlbumArtist
(Mp3tag). Keys are compared with their case, which a save keeps (#419).
Synthetic files and values.
"""
import copy

import mutagen.apev2
import mutagen.id3
import pytest

from puddlestuff import audioinfo
from test_covers import FRONT, write

APE_FORMATS = ['ape', 'mpc', 'wv']


@pytest.fixture(params=['default', 'no APEv2 entries'])
def mapping(request):
    """The default field mapping, and one without APEv2 entries, as a saved
    mappings file can have: the names don't depend on the mapping."""
    original = audioinfo.mapping
    if request.param == 'no APEv2 entries':
        audioinfo.setmapping(dict(original, APEv2={}))
    yield request.param
    audioinfo.setmapping(original)


def ape_file(make_audio, ext, **keys):
    """A file with only an APEv2 tag holding these keys, as written."""
    path = make_audio('song.' + ext)
    tag = mutagen.apev2.APEv2()
    tag.update(keys)
    tag.save(str(path))
    return path


def stored(path):
    return {key: str(value) for key, value in mutagen.apev2.APEv2(str(path)).items()}


@pytest.mark.parametrize('ext', APE_FORMATS)
def test_names(make_audio, ext):
    # tags.txt: APEv2 fields "show with the name they have in the file, in
    # lower case (TITLE shows as title)".
    path = ape_file(make_audio, ext, ARTIST='Band', MyField='x', Title='Song', Track='3', Year='2001')
    assert audioinfo.usertags(audioinfo.Tag(str(path))) == {
        'artist': ['Band'], 'myfield': ['x'], 'title': ['Song'], 'track': ['3'], 'year': ['2001']}


@pytest.mark.parametrize('ext', APE_FORMATS)
@pytest.mark.parametrize('keys', [{'Disc': '1/2', 'Album Artist': 'Band'},
                                  {'Disc': '1/2', 'AlbumArtist': 'Band'}], ids=['foobar2000', 'Mp3tag'])
def test_disc_and_album_artist_names(make_audio, mapping, ext, keys):
    # tags.txt: "APEv2: disc shows as discnumber, and album artist as
    # albumartist".
    tag = audioinfo.Tag(str(ape_file(make_audio, ext, Title='Song', **keys)))
    assert audioinfo.usertags(tag) == {'title': ['Song'], 'discnumber': ['1/2'], 'albumartist': ['Band']}


@pytest.mark.parametrize('ext', APE_FORMATS)
@pytest.mark.parametrize('keys, expected', [
    ({'Title': 'Song'}, {'Title': 'Song', 'Disc': '2/2', 'Album Artist': 'Other'}),
    ({'Disc': '1/2', 'Album Artist': 'Band'}, {'Disc': '2/2', 'Album Artist': 'Other'}),
    ({'Disc': '1/2', 'AlbumArtist': 'Band'}, {'Disc': '2/2', 'AlbumArtist': 'Other'}),
], ids=['new', 'foobar2000', 'Mp3tag'])
def test_saved_under_the_files_key(make_audio, mapping, ext, keys, expected):
    # tags.txt: "they're saved under the file's own key, or as Disc and Album
    # Artist".
    path = ape_file(make_audio, ext, **keys)
    tag = audioinfo.Tag(str(path))
    tag.update({'discnumber': ['2/2'], 'albumartist': ['Other']})
    tag.save()
    assert stored(path) == expected


@pytest.mark.parametrize('ext', APE_FORMATS)
def test_saving_keeps_the_case_of_keys(make_audio, ext):
    # #419: "When saving tags puddletag force changes the case of tag names
    # to lower case ... even when the tag values for the specific fields were
    # not changed".
    path = ape_file(make_audio, ext, Album='Record', REPLAYGAIN_TRACK_GAIN='-6.00 dB', TITLE='Song')
    tag = audioinfo.Tag(str(path))
    tag.update({'title': ['New']})
    tag.save()
    assert stored(path) == {'Album': 'Record', 'REPLAYGAIN_TRACK_GAIN': '-6.00 dB', 'TITLE': 'New'}


@pytest.mark.parametrize('ext', APE_FORMATS)
def test_new_keys_with_each_word_capitalised(make_audio, ext):
    # tags.txt: "A new key is saved ... with each word capitalised in APEv2
    # (Title, Record Date), except the APEv2 keys Debut album, EAN/UPC, ISBN,
    # ISRC and LC".
    path = ape_file(make_audio, ext)
    tag = audioinfo.Tag(str(path))
    tag.update({'debut album': ['First'], 'isrc': ['XX0000000000'], 'myfield': ['x'],
                'record date': ['2001'], 'title': ['Song']})
    tag.save()
    assert stored(path) == {'Debut album': 'First', 'ISRC': 'XX0000000000', 'Myfield': 'x',
                            'Record Date': '2001', 'Title': 'Song'}


@pytest.mark.parametrize('ext', APE_FORMATS)
@pytest.mark.parametrize('name', ['TAG', 'x', 'título', '藏經'])
def test_name_it_cant_store(make_audio, ext, name):
    # tags.txt: APEv2's field names "are 2 to 255 ASCII characters from space
    # to ~, other than ID3, TAG, OggS and MP+"; a field whose name the format
    # can't take "isn't saved: puddletag reports it as it does a file it
    # can't write, and the file keeps its tags".
    path = ape_file(make_audio, ext, Title='Song')
    tag = audioinfo.Tag(str(path))
    tag.update({name: ['x'], 'title': ['New']})
    with pytest.raises(EnvironmentError) as error:
        tag.save()
    assert name in error.value.strerror and 'APEv2' in error.value.strerror
    assert stored(path) == {'Title': 'Song'}


@pytest.mark.parametrize('ext', APE_FORMATS)
def test_old_names_still_write(make_audio, mapping, ext):
    # tags.txt: "writing disc or album artist still sets them".
    path = ape_file(make_audio, ext, Title='Song')
    tag = audioinfo.Tag(str(path))
    tag.update({'disc': ['1/2'], 'album artist': ['Band']})
    tag.save()
    assert audioinfo.usertags(audioinfo.Tag(str(path))) == {
        'title': ['Song'], 'discnumber': ['1/2'], 'albumartist': ['Band']}


@pytest.mark.parametrize('ext', APE_FORMATS)
def test_save_keeps_an_external_item(make_audio, ext):
    # news.txt: "There was a pretty nasty bug where puddletag would remove any
    # unsupported tags." An external (link) item isn't shown as a field, and an
    # edit keeps it. Synthetic values.
    path = make_audio('song.' + ext, title='Before')
    ape = mutagen.apev2.APEv2(str(path))
    ape['Link'] = mutagen.apev2.APEValue('http://example.org/', mutagen.apev2.EXTERNAL)
    ape.save()
    tag = audioinfo.Tag(str(path))
    tag.update({'title': ['After']})
    tag.save()
    saved = mutagen.apev2.APEv2(str(path))
    assert (saved['Link'].kind, str(saved['Link']), 'link' in audioinfo.usertags(audioinfo.Tag(str(path)))) == (
        mutagen.apev2.EXTERNAL, 'http://example.org/', False)


def test_id3_edit_keeps_an_mp3_s_apev2_tag(make_audio):
    # news.txt: "There was a pretty nasty bug where puddletag would remove any
    # unsupported tags." An MP3 can carry an APEv2 tag besides its ID3 one, and
    # puddletag edits only the ID3 tag: the APEv2 one stays as it was.
    # Synthetic values.
    path = make_audio('song.mp3', title='T')
    ape = mutagen.apev2.APEv2()
    ape['Title'] = 'Ape'
    ape['Custom'] = 'x'
    ape.save(str(path))
    tag = audioinfo.Tag(str(path))
    tag.update({'title': ['B']})
    tag.save()
    assert stored(path) == {'Custom': 'x', 'Title': 'Ape'}
    assert mutagen.id3.ID3(str(path))['TIT2'].text == ['B']


# A file with no APEv2 tag, the cover and file information lines.

def test_ape_file_without_an_apev2_tag(make_audio):
    # tags.txt: "__tag_read: The tag that'll get written to in the file." and
    # new keys are saved "with each word capitalised in APEv2 (Title, ...)".
    # A Monkey's Audio file with a header and no tag. Synthetic.
    path = make_audio('song.ape')
    tag = audioinfo.Tag(str(path))
    assert (audioinfo.usertags(tag), tag['__tag_read']) == ({}, 'APEv2')
    tag.update({'title': ['New']})
    tag.save()
    assert stored(path) == {'Title': 'New'}


@pytest.mark.parametrize('ext', APE_FORMATS)
def test_delete_cover_and_file_info(make_audio, ext):
    # tags.txt: "__image: Refers to the album art present in the file." Plugins
    # get the Tag object and delete these keys (the export_tags plugin restores
    # a tag dict the same way); the file information isn't saved. Synthetic.
    path = make_audio('song.' + ext, title='Song')
    write(path, [FRONT])
    tag = audioinfo.Tag(str(path))
    del tag['__image']
    del tag['__length']
    assert (tag.images, tag['__length']) == ([], '00:01')
    tag.save()
    assert 'Cover Art (Front)' not in stored(path)


@pytest.mark.parametrize('ext', APE_FORMATS)
def test_cover_without_data_is_not_saved(make_audio, ext):
    # tags.txt: "__image: Refers to the album art present in the file." A cover
    # with no bytes has nothing to store, so it isn't saved. Synthetic.
    path = make_audio('song.' + ext, title='Song')
    tag = audioinfo.Tag(str(path))
    tag.update({'__image': [{'data': b'', 'description': '', 'imagetype': 3, 'mime': 'image/png'}]})
    tag.save()
    assert stored(path) == {'Title': 'Song'}


def test_tta_file_info(make_audio):
    # menus.txt: Properties "Shows the first selected file's format
    # information". A TrueAudio file is the generic APEv2 class. Synthetic.
    tag = audioinfo.Tag(str(make_audio('song.tta', title='Song')))
    [(file_title, rows), (title, info)] = tag.info
    assert title == 'APEv2 Info'
    assert dict(info)['Length'] == tag['__length']


@pytest.mark.parametrize('ext', APE_FORMATS + ['tta'])
def test_copy_of_a_tag(make_audio, ext):
    # A copy keeps its kind and its file information (the maintainer's
    # decision): actions and tag sources edit a copy of the tag. Synthetic.
    tag = audioinfo.Tag(str(make_audio('song.' + ext, title='Before')))
    twin = copy.deepcopy(tag)
    twin.update({'title': ['Copy']})
    assert (tag['title'], twin['title']) == (['Before'], ['Copy'])
    assert (type(twin) is type(tag), twin.filetype) == (True, tag.filetype)
    assert twin.info == tag.info
