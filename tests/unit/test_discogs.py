"""The Discogs tag source (puddlestuff/tagsources/discogs.py): the fields it
returns for a release and its tracks, as tagsources.txt lists them, how it
finds a release, its covers and the pause between its requests, from
responses Discogs served (tests/data/discogs/, recorded by
tests/data/record_discogs.py), sent back by a local web server. The
recordings keep only release data, which Discogs publishes under CC0: a test
that needs a marketplace field, a heading, a credit or an image no recording
has adds it, labelled synthetic.
"""
import gzip
import json
from pathlib import Path

import pytest

from puddlestuff.constants import COMBO
from puddlestuff.tagsources import RetrievalError, discogs
from puddlestuff.util import split_by_field

DATA = Path(__file__).parent.parent / 'data' / 'discogs'

BEATLES = 10102399  # two CDs: 1-1 to 2-13, then a Data track
DVORAK = 16106482  # the Legends: an index track of ten movements
EXISTENCE = 1257896  # a compilation: track artists and credits
NEVER_GONNA = 249504  # a 7" single: sides A and B
NEVER_GONNA_MASTER = 96559
THE_WALL = 367511  # two LPs: sides A1 to D7, no durations
RELEASES = [BEATLES, DVORAK, EXISTENCE, NEVER_GONNA, THE_WALL]


class FakeClock:
    """The time module as discogs sees it: time moves only when the source
    waits, each wait kept in ``sleeps``, or when a test advances it. A test
    can also set the wall clock (``time()``) back, as a clock change does,
    which leaves ``monotonic()`` alone."""

    def __init__(self):
        self.now = 1_000_000.0
        self.sleeps = []
        self.wall_offset = 0

    def advance(self, seconds):
        self.now += seconds

    def monotonic(self):
        return self.now

    def set_back(self, seconds):
        self.wall_offset -= seconds

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    def time(self):
        return self.now + self.wall_offset


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(discogs, 'time', fake)
    # When Discogs was last asked something: 0, as at import, so the first
    # request doesn't wait.
    monkeypatch.setattr(discogs, '__reference_time', 0)
    return fake


def recorded(name):
    """A recorded response as a dict, eg. recorded('release-249504')."""
    return json.loads((DATA / f'{name}.json').read_text(encoding='utf-8'))


@pytest.fixture
def source(web_server, monkeypatch, clock):
    """Discogs as the Tag Sources window sets it up with Retrieve Cover
    unchecked, sending its requests to the local server, which answers with
    the recorded responses. Its waits take no time: the clock stands
    still."""
    monkeypatch.setattr(discogs, 'RELEASE_URL', web_server.url + '/releases/%s')
    monkeypatch.setattr(discogs, 'MASTER_URL', web_server.url + '/masters/%s')
    monkeypatch.setattr(discogs, 'R_ID', discogs.R_ID_DEFAULT)
    monkeypatch.setattr(discogs, 'API_KEY', '', raising=False)
    for path in sorted(DATA.glob('*.json')):
        kind, discogs_id = path.stem.split('-')
        web_server.add(f'/{kind}s/{discogs_id}', path, content_type='application/json')
    source = discogs.Discogs()
    source.applyPrefs([False, 1, discogs.R_ID_DEFAULT, ''])
    return source


def serve(web_server, release_id, release):
    """Answers release ``release_id`` with ``release``, a recorded response
    a test changed. Added after the source fixture's answers, so it wins."""
    web_server.add(f'/releases/{release_id}', json.dumps(release),
                   content_type='application/json')


def retrieve(source, release_id):
    """The release's fields and its tracks' own, as the source returns
    them for a release id typed in the Tag Sources window."""
    return source.retrieve(release_id)


def retrieve_master(source, master_id, album):
    """A master's fields and tracks, retrieved as the source retrieves a
    search result that is one: by its id and type."""
    return source.retrieve({'#r_id': str(master_id), '#release_type': 'master',
                            'album': album})


def written(fields):
    """The fields the Tag Sources window writes: '#' keys are the source's
    own."""
    return {key for key in fields if not key.startswith('#')}


# The release's fields --------------------------------------------------------

@pytest.mark.parametrize(('release_id', 'expected'), sorted({
    BEATLES: ('The Beatles', 'The Beatles', 'Spain', ['Apple Records', 'Parlophone']),
    DVORAK: ('Symphonic Variations - Scherzo Capriccioso - Legends',
             'Antonín Dvořák & The Czech Philharmonic Orchestra & Sir Charles Mackerras',
             'Europe', ['Supraphon']),
    EXISTENCE: ('Existence Dance Festival', 'Fiuzz', 'Portugal', ['Spectral Records']),
    NEVER_GONNA: ('Never Gonna Give You Up', 'Rick Astley', 'UK', ['RCA']),
    THE_WALL: ('The Wall', 'Pink Floyd', 'UK', ['Harvest']),
}.items()))
def test_release_fields(source, release_id, expected):
    """tagsources.txt: "**album**: The release's (album's) name.",
    "**artist**: The track's artist, as Discogs names it: an artist sharing a
    name with another carries Discogs' number, eg. **Shift (2)**.",
    "**country**: The album's release country", "**label**: The record label
    responsible for releasing the album." """
    info, _ = retrieve(source, release_id)

    assert (info['album'], info['artist'], info['country'], info['label']) == expected


@pytest.mark.parametrize('release_id', RELEASES)
def test_release_notes_and_address(source, release_id):
    """tagsources.txt: "**discogs_notes**: Notes associated with the album.",
    "**discogs_uri**: The album's discogs URI." """
    info, _ = retrieve(source, release_id)

    release = recorded(f'release-{release_id}')
    assert info['discogs_notes'] == release['notes']
    assert info['discogs_uri'] == release['uri']


def test_release_address_is_the_releases_page(source):
    """tagsources.txt: "**discogs_uri**: The album's discogs URI." """
    info, _ = retrieve(source, NEVER_GONNA)

    assert info['discogs_uri'] == (
        'https://www.discogs.com/release/249504-Rick-Astley-Never-Gonna-Give-You-Up')


def test_master_fields(source, web_server):
    """tagsources.txt: "**album**: The release's (album's) name.",
    "**artist**: The track's artist, as Discogs names it: an artist sharing a
    name with another carries Discogs' number, eg. **Shift (2)**.",
    "**year**: The album's release date." """
    info, tracks = retrieve_master(source, NEVER_GONNA_MASTER, 'Never Gonna Give You Up')

    assert (info['album'], info['artist'], info['year'], info['discogs_uri']) == (
        'Never Gonna Give You Up', 'Rick Astley', '1987',
        'https://www.discogs.com/master/96559-Rick-Astley-Never-Gonna-Give-You-Up')
    assert [(t['track'], t['title'], t['__length']) for t in tracks] == [
        ('A', 'Never Gonna Give You Up (Cake Mix)', '5:47'),
        ('B1', 'Never Gonna Give You Up (Instrumental)', '6:21'),
        ('B2', 'Never Gonna Give You Up', '3:32')]
    assert [r.path for r in web_server.requests] == ['/masters/96559']


@pytest.mark.parametrize(('release_id', 'expected'), [
    pytest.param(NEVER_GONNA, [('A', 'Never Gonna Give You Up', '3:32'),
                               ('B', 'Never Gonna Give You Up (Instrumental)', '3:30')],
                 id='single'),
    pytest.param(EXISTENCE, [('1', 'Other Reality', '8:24'), ('2', 'A-Team', '7:38'),
                             ('3', 'The Myth', '7:26'), ('4', 'Prestige', '7:55'),
                             ('5', 'Time Distortion', '6:33'), ('6', 'Aim', '7:32'),
                             ('7', 'Break The Floor', '6:27'), ('8', 'Organic Drugs', '6:37'),
                             ('9', 'Hinni Downmix', '5:30')],
                 id='compilation'),
])
def test_track_titles_and_lengths(source, release_id, expected):
    """tagsources.txt: "**track**: Track number, or Discogs' position for a
    vinyl side, eg. **A1**.", "**title**: The track's title.", "**__length**:
    The track's length, when Discogs has it." """
    _, tracks = retrieve(source, release_id)

    assert [(t['track'], t['title'], t.get('__length')) for t in tracks] == expected


def test_track_without_duration_has_no_length(source):
    """tagsources.txt: "**__length**: The track's length, when Discogs has
    it." Discogs gives no duration for The Wall's tracks (`duration: ''`)."""
    _, tracks = retrieve(source, THE_WALL)

    assert [t['title'] for t in tracks] == [
        'In The Flesh?', 'The Thin Ice', 'Another Brick In The Wall (Part 1)',
        'The Happiest Days Of Our Lives', 'Another Brick In The Wall (Part 2)',
        'Mother', 'Goodbye Blue Sky', 'Empty Spaces', 'Young Lust',
        'One Of My Turns', "Don't Leave Me Now", 'Another Brick In The Wall Part 3',
        'Goodbye Cruel World', 'Hey You', 'Is There Anybody Out There?',
        'Nobody Home', 'Vera', 'Bring The Boys Back Home', 'Comfortably Numb',
        'The Show Must Go On', 'In The Flesh', 'Run Like Hell',
        'Waiting For The Worms', 'Stop', 'The Trial', 'Outside The Wall']
    assert not any('__length' in track for track in tracks)


def test_track_credits(source):
    """tagsources.txt: "**involvedpeople_track**: People involved with the
    relevant track. Taken from the track's extraartists node." """
    _, existence = retrieve(source, EXISTENCE)
    _, wall = retrieve(source, THE_WALL)

    existence = {t['track']: t for t in existence}
    wall = {t['track']: t for t in wall}
    assert existence['2']['involvedpeople_track'] == (
        'Roy Engel:Written-By, Producer;Yonatan Marcow:Written-By, Producer')
    assert 'involvedpeople_track' not in existence['1']
    assert wall['B3']['involvedpeople_track'] == 'David Gilmour:Written-By;Roger Waters:Written-By'


# The tracks ------------------------------------------------------------------

LEGENDS = 'Legends Op. 59 (B. 122, 1881)'


def test_tracks_have_no_type(source):
    """tagsources.txt lists the fields a track gets: "title", "artist",
    "track" and so on, with no ``type_``. The Tag Sources window writes
    every field that doesn't start with '#', so ``type_`` would land in each
    file."""
    for release_id in RELEASES:
        for track in retrieve(source, release_id)[1]:
            assert 'type_' not in track, release_id
    for track in retrieve_master(source, NEVER_GONNA_MASTER, 'Never Gonna Give You Up')[1]:
        assert 'type_' not in track


def test_index_track_movements(source):
    """#725: "This release has 12 tracks, 10 of which are under an Index
    track ... it only shows the two non-indexed tracks and the index track,
    without all the movements."
    """
    tracks = retrieve(source, DVORAK)[1]
    assert [(t.get('track'), t.get('__length')) for t in tracks] == [
        ('1', '21:58'), ('2', '14:01'), ('3', '3:23'), ('4', '4:18'),
        ('5', '4:06'), ('6', '5:44'), ('7', '4:23'), ('8', '5:11'),
        ('9', '2:47'), ('10', '3:45'), ('11', '2:33'), ('12', '4:02')]


def test_index_track_titles(source):
    """tagsources.txt: "**title**: The track's title. An index track's
    movements are tracks of their own, titled **work: movement**." (#725)"""
    tracks = retrieve(source, DVORAK)[1]
    assert [t['title'] for t in tracks[:2]] == [
        'Symphonic Variations Op. 78 (B. 70 1877)',
        'Scherzo Capriccioso Op. 66 (B. 131, 1883)']
    assert [t['title'] for t in tracks[2:]] == [
        f'{LEGENDS}: {movement}' for movement in [
            'I. Allegretto Non Troppo, Quasi Andantino', 'II. Molto Moderato',
            'III. Allegro Giusto', 'IV. Molto Maestoso', 'V. Allegro Giusto',
            'VI. Allegro Con Moto', 'VII. Allegretto Grazioso',
            'VIII. Un Poco Allegretto', 'IX. Andante Con Moto', 'X. Andante']]


def test_headings_are_dropped(source, web_server):
    """Synthetic headings: Discogs' headings are titles over a group of
    tracks ("Disc 1"), not tracks."""
    release = recorded('release-10102399')
    tracklist = release['tracklist']
    second_disc = next(i for i, t in enumerate(tracklist) if t['position'] == '2-1')
    tracklist.insert(second_disc, {'position': '', 'type_': 'heading', 'title': 'Disc 2', 'duration': ''})
    tracklist.insert(0, {'position': '', 'type_': 'heading', 'title': 'Disc 1', 'duration': ''})
    serve(web_server, BEATLES, release)
    tracks = retrieve(source, BEATLES)[1]
    assert len(tracks) == 31
    assert {'Disc 1', 'Disc 2'}.isdisjoint(t['title'] for t in tracks)


def test_track_without_position_or_duration_is_kept(source, web_server):
    """Synthetic: Discogs lists a hidden track with a title only; it is a
    track of the release, not a heading."""
    release = recorded('release-10102399')
    release['tracklist'].append(
        {'position': '', 'type_': 'track', 'title': 'Hidden Track', 'duration': ''})
    serve(web_server, BEATLES, release)
    tracks = retrieve(source, BEATLES)[1]
    assert len(tracks) == 32
    assert tracks[-1]['title'] == 'Hidden Track'
    assert 'track' not in tracks[-1]
    assert '__length' not in tracks[-1]


def test_track_artists(source):
    """tagsources.txt: "**artist**: The track's artist, as Discogs names it:
    an artist sharing a name with another carries Discogs' number, eg.
    **Shift (2)**." """
    tracks = retrieve(source, EXISTENCE)[1]
    assert [t['artist'] for t in tracks] == [
        'Menog', 'A-Team (17)', 'Painkiller (3) vs. Fiuzz', 'Abomination (2)',
        'Khopat', 'Shift (2)', 'Tickets', 'Jaws Underground', 'MIDI-Terranien']
    # The album's artist applies to a track with none of its own.
    assert all('artist' not in t for t in retrieve(source, NEVER_GONNA)[1])


def test_disc_numbers(source):
    """tagsources.txt: "**discnumber**: Disc number, from a track position
    like **2-5**.", "**discs**: Number of discs in the album.", "**track**:
    Track number, or Discogs' position for a vinyl side, eg. **A1**." A
    two-disc release's positions are 1-1 to 2-13."""
    info, tracks = retrieve(source, BEATLES)
    assert info['discs'] == '2'
    assert [(t['discnumber'], t['track']) for t in tracks[:30]] == (
        [('1', str(n)) for n in range(1, 18)] + [('2', str(n)) for n in range(1, 14)])
    assert tracks[30]['track'] == 'Data'
    assert 'discnumber' not in tracks[30]
    for release_id in [NEVER_GONNA, THE_WALL]:
        info, tracks = retrieve(source, release_id)
        assert 'discs' not in info
        assert all('discnumber' not in t for t in tracks)


def test_lp_positions_are_kept(source):
    """tagsources.txt: "**track**: Track number, or Discogs' position for a
    vinyl side, eg. **A1**." """
    tracks = retrieve(source, THE_WALL)[1]
    assert [t['track'] for t in tracks] == [
        'A1', 'A2', 'A3', 'A4', 'A5', 'A6',
        'B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7',
        'C1', 'C2', 'C3', 'C4', 'C5', 'C6',
        'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7']


def synthetic_credits(web_server):
    """Synthetic: the second track of the compilation with a comma join
    between its artists and a featured artist."""
    release = recorded('release-1257896')
    track = release['tracklist'][1]
    track['artists'] = [{'join': ',', 'name': 'Roy Engel'}, {'join': '', 'name': 'Yonatan Marcow'}]
    track['extraartists'].append({'join': '', 'name': 'Fiuzz', 'role': 'Featuring'})
    serve(web_server, EXISTENCE, release)


def test_featuring_credit_goes_to_title(source, web_server):
    """Synthetic: a featured artist is added to the title, as " featuring
    X", not to the credits."""
    synthetic_credits(web_server)
    track = retrieve(source, EXISTENCE)[1][1]
    assert track['title'] == 'A-Team featuring Fiuzz'
    assert 'Fiuzz' not in track['involvedpeople_track']


def test_comma_join_has_no_space_before_it(source, web_server):
    """Synthetic: artists Discogs joins with a ',' are written "A, B"."""
    synthetic_credits(web_server)
    assert retrieve(source, EXISTENCE)[1][1]['artist'] == 'Roy Engel, Yonatan Marcow'


# The release's fields as the docs name them ----------------------------------

ALBUM_FIELDS = {
    'album', 'artist', 'catno', 'country', 'discogs_format',
    'discogs_master_url', 'discogs_notes', 'discogs_r_id', 'discogs_uri',
    'discs', 'format', 'genre', 'involvedpeople_album', 'label', 'style',
    'year',
}


@pytest.mark.parametrize('release_id, expected', [
    (BEATLES, (['Rock'], ['Art Rock', 'Pop Rock'])),
    (DVORAK, (['Classical'], ['Romantic'])),
    (EXISTENCE, (['Electronic'], ['Psy-Trance'])),
    (NEVER_GONNA, (['Electronic', 'Pop'], ['Euro-Disco'])),
    (THE_WALL, (['Rock'], ['Prog Rock', 'Art Rock'])),
])
def test_genre_and_style(source, release_id, expected):
    """tagsources.txt: "**genre**: Genres associated with the album.",
    "**style**: Discogs styles."; tut5.txt: "Discogs gave **artist=TKZee,
    title=Felakai, genre=Kwaito\\\\Rap**." The fields are named genre and
    style, not as Discogs' own genres and styles."""
    info, _ = retrieve(source, release_id)
    assert (info.get('genre'), info.get('style')) == expected
    assert 'genres' not in info
    assert 'styles' not in info


def test_master_genre_and_style(source):
    """tagsources.txt: "**genre**: Genres associated with the album.",
    "**style**: Discogs styles." A master has them too."""
    info, _ = retrieve_master(source, NEVER_GONNA_MASTER, 'Never Gonna Give You Up')
    assert (info.get('genre'), info.get('style')) == (['Electronic', 'Pop'], ['Synth-pop'])
    assert 'genres' not in info
    assert 'styles' not in info


@pytest.mark.parametrize('release_id, expected', [
    (BEATLES, ['05099962829724']),
    (DVORAK, ['SU 3533-2 031']),
    (EXISTENCE, ['SPLCD005']),
    (NEVER_GONNA, ['PB 41447']),
    (THE_WALL, ['SHDW 411']),
])
def test_catalog_numbers(source, release_id, expected):
    """tagsources.txt: "**catno**: Discogs catalog number." A number the
    labels share is given once."""
    info, _ = retrieve(source, release_id)
    assert info['catno'] == expected


@pytest.mark.parametrize('release_id, expected', [
    (BEATLES, ['CD']),
    (DVORAK, ['CD']),
    (EXISTENCE, ['CD']),
    (NEVER_GONNA, ['Vinyl']),
    (THE_WALL, ['Vinyl']),
])
def test_format_media(source, release_id, expected):
    """tagsources.txt: "**discogs_format**: The album's release media (eg.
    Vinyl, CD, etc.)" """
    info, _ = retrieve(source, release_id)
    assert info.get('discogs_format') == expected


def test_format_descriptions_keep_discogs_order(source):
    """tagsources.txt: "**format**: The format description (eg. Album, Single,
    etc.)" The descriptions come in the order Discogs lists them. All five
    releases are checked at once: one release alone can come out in order by
    chance."""
    expected = {
        BEATLES: ['Album', 'Enhanced', 'Reissue', 'Remastered'],
        DVORAK: ['Album', 'Stereo'],
        EXISTENCE: ['Compilation'],
        NEVER_GONNA: ['7"', '45 RPM', 'Single', 'Stereo'],
        THE_WALL: ['LP', 'Album', 'Repress', 'Stereo'],
    }
    assert {release_id: retrieve(source, release_id)[0]['format']
            for release_id in RELEASES} == expected


@pytest.mark.parametrize('release_id, expected', [
    (EXISTENCE, 'Fiuzz:Compiled By;Painkiller (3):Mastered By;Roy Engel:Mastered By'),
    (NEVER_GONNA, 'Me Company:Design;Mark McGuire:Engineer;Mike Duffy:Engineer;'
                  'Miles Showell:Lacquer Cut By;Pete Hammond:Mixed By;'
                  'Stock, Aitken & Waterman:Producer, Written-By'),
])
def test_album_credits(source, release_id, expected):
    """tagsources.txt: "**involvedpeople_album**: People involved with the
    album's creation. Taken from the extraartists node for the album."; id3.txt:
    "**Billy Taylor:Piano;Chester Bennington:Vocals;Ratatat:Instruments** ...
    Items in a pair are separated with a colon (:), with pairs separated by a
    semi-colon(;)" """
    info, _ = retrieve(source, release_id)
    assert info['involvedpeople_album'] == expected


@pytest.mark.parametrize('release_id', RELEASES)
def test_release_id(source, release_id):
    """tagsources.txt: "**discogs_r_id**: Discogs Release ID." """
    info, _ = retrieve(source, release_id)
    assert info.get('discogs_r_id') == str(release_id)


def test_master_has_no_release_id(source):
    """tagsources.txt: "**discogs_r_id**: Discogs Release ID." A master's id
    isn't a release's."""
    info, _ = retrieve_master(source, NEVER_GONNA_MASTER, 'Never Gonna Give You Up')
    assert 'discogs_r_id' not in info


@pytest.mark.parametrize('release_id, expected', [
    (BEATLES, '2013-10-27'),
    (DVORAK, '2002'),
    (EXISTENCE, '2007-12'),
    (NEVER_GONNA, '1987-07'),
    (THE_WALL, None),
])
def test_release_date(source, release_id, expected):
    """tagsources.txt: "**year**: The album's release date." Discogs writes
    what it doesn't know as 00 (or 0 for a year): the date has only what is
    known."""
    info, _ = retrieve(source, release_id)
    assert info.get('year') == expected


def test_only_documented_fields(source, web_server):
    """tagsources.txt lists the fields the source returns, and no marketplace
    ones (#522). The marketplace fields are synthetic: the recording has none
    (Restricted Data)."""
    release = recorded(f'release-{NEVER_GONNA}')
    release['lowest_price'] = 0.67
    release['num_for_sale'] = 122
    release['blocked_from_sale'] = False
    serve(web_server, NEVER_GONNA, release)
    for release_id in RELEASES:
        info, _ = retrieve(source, release_id)
        assert written(info) <= ALBUM_FIELDS, release_id
    info, _ = retrieve_master(source, NEVER_GONNA_MASTER, 'Never Gonna Give You Up')
    assert written(info) <= ALBUM_FIELDS


# Looking up a release --------------------------------------------------------

def lookup(source, *files):
    """What the source finds when Search is clicked with the search box
    empty: one search per album among the files, grouped as the Tag
    Sources window groups them. Each file is a dict of field: values, as
    a tag reads them (synthetic)."""
    group = split_by_field(files, *source.group_by)
    return [found for album in group for found in source.search(album, group[album])]


def albums(found):
    return [info['album'] for info, tracks in found]


@pytest.mark.parametrize('text', ['249504', ' 249504 '])
def test_search_by_release_id(source, text):
    """tagsources.txt: "To retrieve a release, type its Discogs release id, the
    number in its address on discogs.com, in the search box, eg. **1257896**
    or **:r 1257896**." """
    assert albums(source.keyword_search(text)) == ['Never Gonna Give You Up']


@pytest.mark.parametrize('text', [
    ':r 249504',
    pytest.param(':r249504', id='no-space'),  # synthetic: the docs show a space
])
def test_r_release_id(source, text):
    """tagsources.txt: "To retrieve a release, type its Discogs release id, the
    number in its address on discogs.com, in the search box, eg. **1257896**
    or **:r 1257896**." The text without a space is synthetic."""
    assert albums(source.keyword_search(text)) == ['Never Gonna Give You Up']


def test_r_without_id(source, web_server):
    """Synthetic: ":r" alone has no release id to retrieve."""
    with pytest.raises(RetrievalError, match='^Discogs release id should be an integer.$'):
        source.keyword_search(':r')

    assert web_server.requests == []


@pytest.mark.parametrize('text', [
    'Rick Astley;Never Gonna Give You Up',
    'Rick Astley;',
    ';Never Gonna Give You Up',
    'never gonna give you up',
])
def test_text_is_not_searched(source, web_server, text):
    """tagsources.txt: "puddletag doesn't search Discogs by artist or album."
    The texts are synthetic."""
    with pytest.raises(RetrievalError, match='^Discogs release id should be an integer.$'):
        source.keyword_search(text)

    assert web_server.requests == []


def test_files_with_release_id(source):
    """tagsources.txt: "With the search box empty, each album among the
    selected files is retrieved by the release id its files carry: in the field
    the tag source's **Field to use for discogs_id** preference names
    (**discogs_id** unless changed), or else in **discogs_r_id**, which a
    retrieved release writes." The files are synthetic."""
    found = lookup(source, {'album': ['Never Gonna Give You Up'],
                            'artist': ['Rick Astley'], 'discogs_id': ['249504']})

    assert albums(found) == ['Never Gonna Give You Up']


def test_files_without_artist(source):
    """tagsources.txt: "With the search box empty, each album among the
    selected files is retrieved by the release id its files carry". The file,
    with an album and no artist, is synthetic."""
    found = lookup(source, {'album': ['Never Gonna Give You Up'],
                            'discogs_id': ['249504']})

    assert albums(found) == ['Never Gonna Give You Up']


def test_release_id_field_preference(source):
    """tagsources.txt: "in the field the tag source's **Field to use for
    discogs_id** preference names (**discogs_id** unless changed)". The field
    name and the files are synthetic."""
    source.applyPrefs([False, 1, 'my_discogs', ''])

    assert albums(lookup(source, {'album': ['x'], 'my_discogs': ['249504']})) == [
        'Never Gonna Give You Up']
    assert lookup(source, {'album': ['x'], 'discogs_id': ['249504']}) == []


def test_files_without_release_id_find_nothing(source, web_server):
    """Synthetic: files without a release id aren't searched for by their
    album or artist."""
    found = lookup(source, {'album': ['Never Gonna Give You Up'],
                            'artist': ['Rick Astley']})

    assert found == []
    assert web_server.requests == []


def test_files_with_a_retrieved_release_id(source):
    """tagsources.txt: "or else in **discogs_r_id**, which a retrieved release
    writes." The file, carrying the fields a retrieval returned, is
    synthetic."""
    info, _ = retrieve(source, NEVER_GONNA)

    found = lookup(source, {'album': [info['album']],
                            'discogs_r_id': [info['discogs_r_id']]})

    assert albums(found) == ['Never Gonna Give You Up']


def test_search_without_artists(source):
    """Synthetic: a script or plugin calling search() with no files for the
    album gets no result, not a crash."""
    assert source.search('Never Gonna Give You Up', {}) == []


def test_unknown_release_id(source, web_server):
    """Synthetic: Discogs answers an id it doesn't know with 404 (its body is
    in Discogs' shape)."""
    web_server.add('/releases/999999999', '{"message": "Release not found."}',
                   status=404, content_type='application/json')

    with pytest.raises(RetrievalError, match='^HTTP Error 404: Not Found$'):
        source.keyword_search('999999999')


def test_server_error(source, web_server):
    """Synthetic: Discogs answering with a server error."""
    web_server.add('/releases/1', b'error', status=500)

    with pytest.raises(RetrievalError, match='^HTTP Error 500: Internal Server Error$'):
        retrieve(source, 1)


def test_gzipped_answer(source, web_server):
    """Synthetic: the requests ask for gzip, and a gzipped answer is read as
    the release."""
    web_server.add('/releases/249504',
                   gzip.compress((DATA / 'release-249504.json').read_bytes()),
                   content_type='application/json')

    assert retrieve(source, NEVER_GONNA)[0]['album'] == 'Never Gonna Give You Up'


# Covers ----------------------------------------------------------------------

# Two images, front and back, each in Discogs' two sizes.
COVERS = [('front.jpg', 'front-150.jpg'), ('back.jpg', 'back-150.jpg')]
NEVER_RETRIEVED = 'covers are never retrieved: retrieve() has "if False and self._getcover"'


def covers(web_server, release_id, sizes):
    """Serves release ``release_id`` with images (synthetic: the recordings
    have none), one per (large, small) pair of file names in ``sizes``,
    '' for a size Discogs doesn't give. Each image answers with a JPEG's
    first bytes and its name. Returns each image's bytes by file name."""
    release = recorded(f'release-{release_id}')
    release['images'] = [
        {'type': 'secondary' if i else 'primary',
         'uri': large and f'{web_server.url}/{large}',
         'uri150': small and f'{web_server.url}/{small}'}
        for i, (large, small) in enumerate(sizes)]
    serve(web_server, release_id, release)
    data = {}
    for name in sorted(n for pair in sizes for n in pair if n):
        data[name] = b'\xff\xd8\xff' + name.encode()
        web_server.add(f'/{name}', data[name], content_type='image/jpeg')
    return data


def default_prefs(source):
    """The preferences of a user who never changed them: each one's
    default, as the Tag Sources window reads them from an empty config."""
    return [option[2][1] if option[1] == COMBO else option[2]
            for option in source.preferences]


@pytest.mark.xfail(strict=True, reason=NEVER_RETRIEVED)
def test_large_covers(source, web_server):
    """tagsources.txt: "**__image**: Cover art. Usually more than one image."
    "With **Retrieve Cover** checked (the default), the release's images
    become its cover art, at the size the tag source's **Cover size to
    retrieve** preference picks: **Large** (the default) or **Small**."
    Synthetic images, front and back."""
    data = covers(web_server, NEVER_GONNA, COVERS)
    source.applyPrefs([True, 1, discogs.R_ID_DEFAULT, ''])

    info = retrieve(source, NEVER_GONNA)[0]

    assert info['__image'] == [{'data': data['front.jpg']}, {'data': data['back.jpg']}]


@pytest.mark.xfail(strict=True, reason=NEVER_RETRIEVED)
def test_small_covers(source, web_server):
    """tagsources.txt: "**__image**: Cover art. Usually more than one image."
    "...at the size the tag source's **Cover size to retrieve** preference
    picks: **Large** (the default) or **Small**." Synthetic images, front
    and back."""
    data = covers(web_server, NEVER_GONNA, COVERS)
    source.applyPrefs([True, 0, discogs.R_ID_DEFAULT, ''])

    info = retrieve(source, NEVER_GONNA)[0]

    assert info['__image'] == [{'data': data['front-150.jpg']}, {'data': data['back-150.jpg']}]


@pytest.mark.xfail(strict=True, reason=NEVER_RETRIEVED)
def test_covers_default_to_large(source, web_server):
    """tagsources.txt: "With **Retrieve Cover** checked (the default), ...
    **Large** (the default) or **Small**." A user who never changed the
    preferences gets the large images. Synthetic images."""
    data = covers(web_server, NEVER_GONNA, COVERS)
    source.applyPrefs(default_prefs(source))

    info = retrieve(source, NEVER_GONNA)[0]

    assert info['__image'] == [{'data': data['front.jpg']}, {'data': data['back.jpg']}]


@pytest.mark.xfail(strict=True, reason='covers are never retrieved, and a new '
                                       "source's cover size is 1, which names no size")
def test_new_source_gets_large_covers(source, web_server):
    """tagsources.txt: "**Large** (the default) or **Small**." A source
    nobody set the preferences of (a plugin's, a script's) gets the large
    images. Synthetic images."""
    data = covers(web_server, NEVER_GONNA, COVERS)

    info = discogs.Discogs().retrieve(NEVER_GONNA)[0]

    assert info['__image'] == [{'data': data['front.jpg']}, {'data': data['back.jpg']}]


def test_no_covers_when_unchecked(source, web_server):
    """tagsources.txt: "**__image**: Cover art. Usually more than one
    image." With Retrieve Cover unchecked there is none, and the images
    aren't downloaded. Synthetic images."""
    covers(web_server, NEVER_GONNA, COVERS)

    info = retrieve(source, NEVER_GONNA)[0]

    assert '__image' not in info
    assert [r.path for r in web_server.requests] == ['/releases/249504']


@pytest.mark.xfail(strict=True, reason=NEVER_RETRIEVED)
def test_large_falls_back_to_small(source, web_server):
    """Synthetic: an image Discogs gives only in its small size. tagsources.txt:
    "**__image**: Cover art. Usually more than one image." Large takes what
    there is."""
    data = covers(web_server, NEVER_GONNA, [('', 'front-150.jpg')])
    source.applyPrefs([True, 1, discogs.R_ID_DEFAULT, ''])

    info = retrieve(source, NEVER_GONNA)[0]

    assert info['__image'] == [{'data': data['front-150.jpg']}]


@pytest.mark.xfail(strict=True, reason='covers are never retrieved, and Small '
                                       'with no small image opens the address ""')
def test_small_falls_back_to_large(source, web_server):
    """Synthetic: an image Discogs gives only in its large size. tagsources.txt:
    "**__image**: Cover art. Usually more than one image." Small takes what
    there is."""
    data = covers(web_server, NEVER_GONNA, [('front.jpg', '')])
    source.applyPrefs([True, 0, discogs.R_ID_DEFAULT, ''])

    info = retrieve(source, NEVER_GONNA)[0]

    assert info['__image'] == [{'data': data['front.jpg']}]


@pytest.mark.xfail(strict=True, reason=NEVER_RETRIEVED)
def test_failed_cover_is_skipped(source, web_server):
    """Synthetic: the front image is gone (404). tagsources.txt: "**__image**:
    Cover art. Usually more than one image." The release is still retrieved,
    with the images that came."""
    data = covers(web_server, NEVER_GONNA, COVERS)
    web_server.add('/front.jpg', b'', status=404)
    source.applyPrefs([True, 1, discogs.R_ID_DEFAULT, ''])

    info = retrieve(source, NEVER_GONNA)[0]

    assert info['__image'] == [{'data': data['back.jpg']}]


# The pause between requests, and the API key ---------------------------------

def test_first_request_does_not_wait(source, clock):
    """Synthetic: the docs don't mention the pause. The first request goes
    straight out."""
    retrieve(source, NEVER_GONNA)

    assert clock.sleeps == []


def test_requests_are_a_second_apart(source, clock):
    """Synthetic: the docs don't mention the pause. A request right after
    another waits a second."""
    retrieve(source, NEVER_GONNA)
    retrieve(source, NEVER_GONNA)

    assert clock.sleeps == [1]


def test_a_request_after_a_second_does_not_wait(source, clock):
    """Synthetic: the docs don't mention the pause."""
    retrieve(source, NEVER_GONNA)
    clock.advance(1)
    retrieve(source, NEVER_GONNA)

    assert clock.sleeps == []


@pytest.mark.xfail(strict=True, reason='the source waits a whole second before '
                   'a request, whatever part of it has gone')
def test_a_request_waits_only_the_rest_of_the_second(source, clock):
    """Synthetic: the docs don't mention the pause."""
    retrieve(source, NEVER_GONNA)
    clock.advance(0.25)
    retrieve(source, NEVER_GONNA)

    assert clock.sleeps == [pytest.approx(0.75)]


@pytest.mark.xfail(strict=True, reason='the source times its waits by the wall '
                   'clock: set back an hour, it waits an hour')
def test_setting_the_clock_back_does_not_hold_requests(source, clock):
    """Synthetic: the docs don't mention the pause. A clock change doesn't
    stop the requests for as long as it moved the clock."""
    retrieve(source, NEVER_GONNA)
    clock.set_back(3600)
    retrieve(source, NEVER_GONNA)

    assert clock.sleeps == [1]


@pytest.mark.xfail(strict=True, reason='the API Key preference is read nowhere')
@pytest.mark.parametrize('kind', ['master', 'release'])
def test_api_key_is_sent(source, web_server, kind):
    """tagsources.txt: "puddletag sends it with each request to Discogs'
    API." (the paragraph on the **API Key** preference)."""
    source.applyPrefs([False, 1, discogs.R_ID_DEFAULT, 'synthetic-token'])
    if kind == 'release':
        retrieve(source, NEVER_GONNA)
    else:
        retrieve_master(source, NEVER_GONNA_MASTER, 'Never Gonna Give You Up')

    assert web_server.requests[-1].headers['Authorization'] == 'Discogs token=synthetic-token'


def test_no_api_key_sends_no_authorization(source, web_server):
    """tagsources.txt: "If you have a Discogs account, you can paste a
    personal access token from its developer settings into the tag source's
    **API Key** preference". Synthetic: with no key pasted, nothing is
    sent."""
    retrieve(source, NEVER_GONNA)

    assert 'Authorization' not in web_server.requests[-1].headers


def test_api_key_is_not_sent_elsewhere(source, web_server):
    """Synthetic: Mp3tag scripts download other sites' pages through
    discogs.urlopen, and the key is Discogs' own."""
    source.applyPrefs([False, 1, discogs.R_ID_DEFAULT, 'synthetic-token'])
    web_server.add('/page', b'page')

    assert discogs.urlopen(web_server.url + '/page') == b'page'
    assert 'Authorization' not in web_server.requests[-1].headers
