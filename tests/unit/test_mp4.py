"""MP4 tags (puddlestuff/audioinfo/mp4.py), saved with the two calls an edit
in the main table ends in (update, then save: puddlestuff/util.py write)
and read back with mutagen."""
import mutagen.mp4
import pytest

from puddlestuff import audioinfo
from puddlestuff.audioinfo.util import to_string


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


def test_save_keeps_the_narrator_of_an_audiobook(make_audio):
    # #1060: editing the composer of an .m4b audiobook raised "TypeError:
    # b'Stefan Kaminski' not str" and saved nothing; the reporter found that
    # name in the ©nrt atom, the narrator, which puddletag doesn't map. The
    # name is from the report; the file is synthetic, an .m4a renamed.
    path = make_audio('book.m4a', title='Book')
    audio = mutagen.mp4.MP4(path)
    audio['\xa9nrt'] = ['Stefan Kaminski']
    audio.save()
    path = path.rename(path.with_suffix('.m4b'))

    tag = audioinfo.Tag(str(path))
    tag.update({'composer': ['After']})
    tag.save()

    saved = mutagen.mp4.MP4(path).tags
    assert saved['\xa9wrt'] == ['After']
    assert saved['\xa9nrt'] == ['Stefan Kaminski']


def test_save_keeps_the_descriptions_yt_dlp_writes(make_audio):
    # #1086: saving an edit to an MP4 from yt-dlp raised "TypeError: b'...'
    # not str"; removing its Description and Long Description made it save.
    # yt-dlp writes the video's description to both, desc and ldes.
    # Synthetic file and text.
    path = make_audio('video.m4a', title='Before')
    audio = mutagen.mp4.MP4(path)
    audio['desc'] = audio['ldes'] = ['A video description']
    audio.save()

    tag = audioinfo.Tag(str(path))
    tag.update({'title': ['After']})
    tag.save()

    saved = mutagen.mp4.MP4(path).tags
    assert saved['\xa9nam'] == ['After']
    assert (saved['desc'], saved['ldes']) == (['A video description'], ['A video description'])


def test_save_keeps_number_atoms_puddletag_does_not_map(make_audio):
    # Atoms mutagen keeps as whole numbers that puddletag has no field for:
    # ffmpeg writes tvsn and tves from yt-dlp's season and episode numbers,
    # and hdvd for HD video; iTunes writes ©mvi, ©mvc and shwm for classical
    # works. Synthetic values.
    numbers = {'hdvd': [1], 'shwm': [1], 'tves': [7], 'tvsn': [2], '\xa9mvc': [4], '\xa9mvi': [3]}
    path = make_audio('song.m4a', title='Before')
    audio = mutagen.mp4.MP4(path)
    audio.update(numbers)
    audio.save()

    tag = audioinfo.Tag(str(path))
    tag.update({'title': ['After']})
    tag.save()

    saved = mutagen.mp4.MP4(path).tags
    assert saved['\xa9nam'] == ['After']
    assert {atom: saved[atom] for atom in numbers} == numbers


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


# tags.txt's field table: each field and its MP4 atom (the table leaves out
# the © some atom names start with). Synthetic values.

def save(path, fields):
    tag = audioinfo.Tag(str(path))
    tag.update(fields)
    tag.save()
    return mutagen.mp4.MP4(path).tags, audioinfo.Tag(str(path))


TEXT_ATOMS = {
    'album': '©alb', 'albumartist': 'aART', 'albumartistsortorder': 'soaa', 'albumsortorder': 'soal',
    'artist': '©ART', 'comment': '©cmt', 'composer': '©wrt', 'copyright': 'cprt', 'description': 'desc',
    'encodedby': '©too', 'genre': '©gen', 'grouping': '©grp', 'itunesaccount': 'apID',
    'itunescomposersortorder': 'soco', 'itunesproductid': 'prID', 'itunespublisher': '©pub',
    'itunesxid': 'xid ', 'performersortorder': 'soar', 'podcastcategory': 'catg', 'podcastdesc': 'ldes',
    'podcastepisodeguid': 'egid', 'podcastkeywords': 'keyw', 'podcasturl': 'purl', 'purchasedate': 'purd',
    'showname': 'tvsh', 'showsortorder': 'sosn', 'title': '©nam', 'titlesortorder': 'sonm',
    'unsyncedlyrics': '©lyr', 'year': '©day',
}
# "tmpo and the iTunes IDs ... take whole numbers."
NUMBER_ATOMS = {
    'bpm': 'tmpo', 'itunesaccounttype': 'akID', 'itunesadvisory': 'rtng', 'itunesalbumid': 'plID',
    'itunesartistid': 'atID', 'itunescatalogid': 'cnID', 'itunescomposerid': 'cmID', 'itunesgenreid': 'geID',
    'itunesmediatype': 'stik', 'itunesstorecountry': 'sfID',
}
FLAG_ATOMS = {'itunescompilationflag': 'cpil', 'partofgaplessalbum': 'pgap', 'podcast': 'pcst'}


def test_text_atoms(make_audio):
    # Two values each, one not ASCII.
    fields = {field: [field + ' one', 'Ünïcode two'] for field in TEXT_ATOMS}
    atoms, tag = save(make_audio('song.m4a'), fields)
    assert {field: atoms[atom] for field, atom in TEXT_ATOMS.items()} == fields
    assert {field: tag[field] for field in TEXT_ATOMS} == fields


def test_number_atoms(make_audio):
    atoms, tag = save(make_audio('song.m4a'), {field: ['7'] for field in NUMBER_ATOMS})
    assert {field: atoms[atom] for field, atom in NUMBER_ATOMS.items()} == {field: [7] for field in NUMBER_ATOMS}
    assert {field: tag[field] for field in NUMBER_ATOMS} == {field: ['7'] for field in NUMBER_ATOMS}


@pytest.mark.parametrize('value, stored, shown', [
    # "The flags (cpil, pgap, pcst) read 1 or 0 ...; 1 or Yes turns one on,
    # anything else off."
    ('1', True, '1'),
    ('0', False, '0'),
    ('Yes', True, '1'),
    ('No', False, '0'),
])
def test_flag_atoms(make_audio, value, stored, shown):
    atoms, tag = save(make_audio('song.m4a'), {field: [value] for field in FLAG_ATOMS})
    assert {field: atoms[atom] for field, atom in FLAG_ATOMS.items()} == {field: stored for field in FLAG_ATOMS}
    assert {field: tag[field] for field in FLAG_ATOMS} == {field: [shown] for field in FLAG_ATOMS}


def test_flag_off_in_the_file(make_audio):
    # A flag another program wrote off reads 0, and an edit keeps it.
    # Synthetic file.
    path = make_audio('song.m4a', title='Before')
    audio = mutagen.mp4.MP4(path)
    audio['cpil'] = False
    audio.save()
    atoms, tag = save(path, {'title': ['After']})
    assert (atoms['cpil'], tag['itunescompilationflag']) == (False, ['0'])


@pytest.mark.parametrize('value, stored', [
    # "MP4 keeps lyrics as plain text, so a language and description in
    # front, as ID3 takes them (eng||Lyrics, eng|Description|Lyrics), aren't
    # saved." id3.txt: one '|' is the language and the lyrics.
    ('eng||Some lyrics', 'Some lyrics'),
    ('eng|Description|Some lyrics', 'Some lyrics'),
    ('eng|Some lyrics', 'Some lyrics'),
    ('Verse 1 | Chorus', 'Verse 1 | Chorus'),
])
def test_lyrics_as_plain_text(make_audio, value, stored):
    atoms, tag = save(make_audio('song.m4a'), {'unsyncedlyrics': [value]})
    assert (atoms['\xa9lyr'], tag['unsyncedlyrics']) == ([stored], [stored])


def test_track_and_its_total(make_audio):
    # "track and totaltracks share the trkn atom ... each a whole number"
    atoms, tag = save(make_audio('song.m4a'), {'track': ['3'], 'totaltracks': ['12']})
    assert atoms['trkn'] == [(3, 12)]
    assert (tag['track'], tag['totaltracks']) == (['3'], ['12'])
    # tags.txt, __total: the total (a list here, a string for MP3 and FLAC).
    assert to_string(tag['__total']) == '12'


# The disc number is discnumber in ID3, APEv2 and WMA, in the tag sources,
# and in the docs' Tag->File and Autonumbering examples.

def test_disc_and_its_total(make_audio):
    atoms, tag = save(make_audio('song.m4a'), {'discnumber': ['1'], 'totaldiscs': ['2']})
    assert atoms['disk'] == [(1, 2)]
    assert (tag['discnumber'], tag['totaldiscs']) == (['1'], ['2'])


@pytest.mark.parametrize('old, new, value, atom, stored', [
    ('artistsortorder', 'performersortorder', 'Sort', 'soar', ['Sort']),
    ('composersortorder', 'itunescomposersortorder', 'Sort', 'soco', ['Sort']),
    ('disc', 'discnumber', '1', 'disk', [(1, 0)]),
    ('lyrics', 'unsyncedlyrics', 'Words', '\xa9lyr', ['Words']),
    ('partofcompilation', 'itunescompilationflag', '1', 'cpil', True),
])
def test_old_names_still_write(make_audio, old, new, value, atom, stored):
    # tags.txt: "Some MP4 fields used to have names of their own, and writing
    # those still sets them", as actions saved for MP4 files may.
    atoms, tag = save(make_audio('song.m4a'), {old: [value]})
    assert (atoms[atom], tag[new]) == (stored, [value])


@pytest.mark.parametrize('field, value, atom, stored, total_field', [
    # "writing track as 3/12, or disc as 1/2, sets both"
    ('track', '3/12', 'trkn', (3, 12), 'totaltracks'),
    ('discnumber', '1/2', 'disk', (1, 2), 'totaldiscs'),
])
def test_number_with_its_total(make_audio, field, value, atom, stored, total_field):
    atoms, tag = save(make_audio('song.m4a'), {field: [value]})
    assert atoms[atom] == [stored]
    assert (tag[field], tag[total_field]) == ([str(stored[0])], [str(stored[1])])


def test_freeform_atom(make_audio):
    # "Any MP4 atoms not in this list will be assumed to be freeform frames,
    # written using ':com.apple.iTunes:fieldname' as the atom."
    atoms, tag = save(make_audio('song.m4a'), {'mytag': ['one', 'Ünïcode two']})
    assert atoms['----:com.apple.iTunes:mytag'] == [b'one', 'Ünïcode two'.encode()]
    assert tag['mytag'] == ['one', 'Ünïcode two']


def test_freeform_name_beyond_latin1(make_audio):
    # tags.txt: "MP4's freeform ones are Latin-1"; a field whose name the
    # format can't take "isn't saved: puddletag reports it as it does a file
    # it can't write, and the file keeps its tags".
    path = make_audio('song.m4a', title='Song')
    tag = audioinfo.Tag(str(path))
    tag.update({'título': ['Latin-1'], '藏經': ['x']})
    with pytest.raises(EnvironmentError) as error:
        tag.save()
    assert '藏經' in error.value.strerror and 'MP4' in error.value.strerror
    assert dict(mutagen.mp4.MP4(path).tags) == {'\xa9nam': ['Song']}
    atoms, tag = save(path, {'título': ['Latin-1']})
    assert atoms['----:com.apple.iTunes:título'] == [b'Latin-1']
