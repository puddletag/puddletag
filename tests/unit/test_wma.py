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


# tags.txt's field table: each field and its WMA attribute (the MusicBrainz
# ids are in test_musicbrainz_ids.py).
TEXT_ATTRIBUTES = {
    'album': 'WM/AlbumTitle', 'albumartist': 'WM/AlbumArtist', 'albumartistsortorder': 'WM/AlbumArtistSortOrder',
    'albumsortorder': 'WM/AlbumSortOrder', 'arranger': 'WM/ModifiedBy', 'artist': 'Author',
    'author': 'WM/OriginalLyricist', 'bpm': 'WM/BeatsPerMinute', 'comment': 'Description',
    'composer': 'WM/Composer', 'conductor': 'WM/Conductor', 'copyright': 'WM/Copyright',
    'discnumber': 'WM/PartOfSet', 'encodedby': 'WM/EncodedBy', 'encodingsettings': 'WM/EncodingSettings',
    'encodingtime': 'WM/EncodingTime', 'filename': 'WM/OriginalFilename', 'genre': 'WM/Genre',
    'grouping': 'WM/ContentGroupDescription', 'initialkey': 'WM/InitialKey', 'isrc': 'WM/ISRC',
    'itunescomposersortorder': 'WM/ComposerSortOrder', 'language': 'WM/Language', 'lyricist': 'WM/Writer',
    'mbrainz_albumartist_id': 'MusicBrainz/Album Artist Id', 'mbrainz_discid': 'MusicBrainz/Disc Id',
    'mbrainz_trmid': 'MusicBrainz/TRM Id', 'mood': 'WM/Mood', 'musicip_puid': 'MusicIP/PUID',
    'organization': 'WM/Publisher', 'originalalbum': 'WM/OriginalAlbumTitle',
    'originalartist': 'WM/OriginalArtist', 'originalyear': 'WM/OriginalReleaseYear',
    'performersortorder': 'WM/ArtistSortOrder', 'producer': 'WM/Producer',
    'releasecountry': 'MusicBrainz/Album Release Country', 'releasestatus': 'MusicBrainz/Album Status',
    'releasetype': 'MusicBrainz/Album Type', 'setsubtitle': 'WM/SetSubTitle', 'title': 'Title',
    'titlesortorder': 'WM/TitleSortOrder', 'track': 'WM/TrackNumber', 'unsyncedlyrics': 'WM/Lyrics',
    'version': 'WM/SubTitle', 'wwwartist': 'WM/AuthorURL', 'wwwcommercialinfo': 'WM/PromotionURL',
    'wwwcopyright': 'CopyrightURL', 'wwwsource': 'WM/AudioSourceURL', 'year': 'WM/Year',
}


def test_text_attributes(make_audio):
    # Two values each, one not ASCII.
    fields = {field: [field + ' one', 'Ünïcode two'] for field in TEXT_ATTRIBUTES}
    attributes, tag = save(make_audio('song.wma'), fields)
    assert {field: stored(attributes)[name] for field, name in TEXT_ATTRIBUTES.items()} == fields
    assert {field: tag[field] for field in TEXT_ATTRIBUTES} == fields


@pytest.mark.parametrize('value, stored_value, shown', [
    # "WM/IsCompilation reads 1 or 0, as MP4's flags do, and 1 or Yes turns
    # it on."
    ('1', True, '1'),
    ('0', False, '0'),
    ('Yes', True, '1'),
    ('No', False, '0'),
])
def test_compilation_flag(make_audio, value, stored_value, shown):
    attributes, tag = save(make_audio('song.wma'), {'itunescompilationflag': [value]})
    assert ([v.value for v in attributes['WM/IsCompilation']], tag['itunescompilationflag']) == (
        [stored_value], [shown])


def test_compilation_flag_as_picard_writes_it(make_audio):
    # Picard's tag mapping: compilation is WM/IsCompilation; a true or false
    # attribute.
    path = make_audio('song.wma')
    audio = mutagen.asf.ASF(path)
    audio['WM/IsCompilation'] = [ASFBoolAttribute(True)]
    audio.save()
    assert audioinfo.Tag(str(path))['itunescompilationflag'] == ['1']


@pytest.mark.parametrize('old, new, name', [
    # "Some WMA fields used to have names of their own, and writing those
    # still sets them".
    ('album_subtitle', 'setsubtitle', 'WM/SetSubTitle'),
    ('encodersettings', 'encodingsettings', 'WM/EncodingSettings'),
    ('engineer', 'producer', 'WM/Producer'),
    ('label', 'organization', 'WM/Publisher'),
    ('originalfilename', 'filename', 'WM/OriginalFilename'),
    ('originallyricist', 'author', 'WM/OriginalLyricist'),
    ('remixer', 'arranger', 'WM/ModifiedBy'),
    ('subtitle', 'version', 'WM/SubTitle'),
    ('wwwaudiosource', 'wwwsource', 'WM/AudioSourceURL'),
])
def test_old_names_still_write(make_audio, old, new, name):
    attributes, tag = save(make_audio('song.wma'), {old: ['Value']})
    assert (stored(attributes), audioinfo.usertags(tag)) == ({name: ['Value']}, {new: ['Value']})


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
