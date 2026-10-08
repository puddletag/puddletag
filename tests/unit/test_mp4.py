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
    'artist': '©ART', 'artistsortorder': 'soar', 'comment': '©cmt', 'composer': '©wrt',
    'composersortorder': 'soco', 'copyright': 'cprt', 'description': 'desc', 'encodedby': '©too',
    'genre': '©gen', 'grouping': '©grp', 'itunesaccount': 'apID', 'itunesproductid': 'prID',
    'itunespublisher': '©pub', 'itunesxid': 'xid ', 'lyrics': '©lyr', 'podcastcategory': 'catg',
    'podcastdesc': 'ldes', 'podcastepisodeguid': 'egid', 'podcastkeywords': 'keyw', 'podcasturl': 'purl',
    'purchasedate': 'purd', 'showname': 'tvsh', 'showsortorder': 'sosn', 'title': '©nam',
    'titlesortorder': 'sonm', 'year': '©day',
}
# "tmpo and the iTunes IDs ... take whole numbers."
NUMBER_ATOMS = {
    'bpm': 'tmpo', 'itunesaccounttype': 'akID', 'itunesadvisory': 'rtng', 'itunesalbumid': 'plID',
    'itunesartistid': 'atID', 'itunescatalogid': 'cnID', 'itunescomposerid': 'cmID', 'itunesgenreid': 'geID',
    'itunesmediatype': 'stik', 'itunesstorecountry': 'sfID',
}
FLAG_ATOMS = {'partofcompilation': 'cpil', 'partofgaplessalbum': 'pgap', 'podcast': 'pcst'}


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


@pytest.mark.parametrize('value, stored', [
    # "The flags (cpil, pgap, pcst) read Yes or No and take either."
    ('Yes', True),
    ('No', False),
])
def test_flag_atoms(make_audio, value, stored):
    atoms, tag = save(make_audio('song.m4a'), {field: [value] for field in FLAG_ATOMS})
    assert {field: atoms[atom] for field, atom in FLAG_ATOMS.items()} == {field: stored for field in FLAG_ATOMS}
    assert {field: tag[field] for field in FLAG_ATOMS} == {field: [value] for field in FLAG_ATOMS}


def test_flag_off_in_the_file(make_audio):
    # A flag another program wrote off reads No, and an edit keeps it.
    # Synthetic file.
    path = make_audio('song.m4a', title='Before')
    audio = mutagen.mp4.MP4(path)
    audio['cpil'] = False
    audio.save()
    atoms, tag = save(path, {'title': ['After']})
    assert (atoms['cpil'], tag['partofcompilation']) == (False, ['No'])


def test_track_and_disc(make_audio):
    # "track and totaltracks share the trkn atom, disc and totaldiscs the
    # disk atom, each a whole number"
    atoms, tag = save(make_audio('song.m4a'),
                      {'track': ['3'], 'totaltracks': ['12'], 'disc': ['1'], 'totaldiscs': ['2']})
    assert (atoms['trkn'], atoms['disk']) == ([(3, 12)], [(1, 2)])
    assert [tag[f] for f in ('track', 'totaltracks', 'disc', 'totaldiscs')] == [['3'], ['12'], ['1'], ['2']]
    # tags.txt, __total: the total (a list here, a string for MP3 and FLAC).
    assert to_string(tag['__total']) == '12'


@pytest.mark.parametrize('field, value, atom, stored, total_field', [
    # "writing track as 3/12, or disc as 1/2, sets both"
    ('track', '3/12', 'trkn', (3, 12), 'totaltracks'),
    ('disc', '1/2', 'disk', (1, 2), 'totaldiscs'),
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
