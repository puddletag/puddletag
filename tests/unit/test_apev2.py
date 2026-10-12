"""APEv2 tags (puddlestuff/audioinfo/apev2.py) in Monkey's Audio, Musepack
and WavPack files, saved with the two calls an edit in the main table ends
in (update, then save) and read back with mutagen.

The disc number and the album artist are discnumber and albumartist in
every other format, the tag sources and the docs (tags.txt). APEv2 files
keep them as Disc and Album Artist (foobar2000, Winamp), or AlbumArtist
(Mp3tag). Keys are compared with their case, which a save keeps (#419).
Synthetic files and values.
"""
import mutagen.apev2
import pytest

from puddlestuff import audioinfo

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
