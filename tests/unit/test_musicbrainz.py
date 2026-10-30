"""The MusicBrainz tag source: what it returns for a release, from
responses MusicBrainz served (tests/data/musicbrainz/, recorded by
tests/data/record_musicbrainz.py), sent back by a local web server. Ratings
and search scores aren't in the recordings (they aren't CC0): a test that
needs one adds it, labelled synthetic. Cover Art Archive indexes and images
are synthetic.
"""
import json
import re
from pathlib import Path

import pytest

from puddlestuff import tagsources, version_string
from puddlestuff.tagsources import RetrievalError, musicbrainz

DATA = Path(__file__).parent.parent / 'data' / 'musicbrainz'

ABBEY_ROAD = '6bb3793b-f991-378e-9bff-0bd3117f2298'
ABBEYS_ROAD = '70516629-7715-41bf-97e1-b7bf11254cb8'  # two artists, " feat. "
COFFEE_LANDS = '33eff102-8312-4be2-b3d9-5bd9957f0158'  # Various Artists
NINE_SYMPHONIES = 'f0217095-5daf-4293-8f59-6ddec7187707'  # five discs

THE_BEATLES = 'b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d'
# The releases of the recorded Abbey Road search, in its order.
SEARCH_RESULTS = ['7a2075a2-ab80-4225-b20d-63b6b9c6a20d', '8c6a00d5-8673-4aad-8192-5fe8649b5efa']


def release_path(release_id):
    return '/ws/2/release/' + release_id


def recorded(release_id):
    return (DATA / f'release-{release_id}.xml').read_text(encoding='utf-8')


class FakeClock:
    """The time module as musicbrainz sees it: time moves only when the
    source waits, each wait kept in ``sleeps``, or when a test advances
    it."""

    def __init__(self):
        self.now = 1_000_000.0
        self.sleeps = []

    def advance(self, seconds):
        self.now += seconds

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    time = monotonic


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(musicbrainz, 'time', fake)
    # When MusicBrainz was last asked something: shared by every source.
    monkeypatch.setattr(musicbrainz, '_last_request', None, raising=False)
    return fake


@pytest.fixture
def source(web_server, monkeypatch, clock):
    """MusicBrainz as the Tag Sources window sets it up with Retrieve Cover
    unchecked, sending its requests to the local server, which answers with
    the recorded responses. Its waits take no time: the clock stands
    still."""
    monkeypatch.setattr(musicbrainz, 'SERVER', web_server.url + '/ws/2/')
    for path in sorted(DATA.glob('release-*.xml')):
        web_server.add(release_path(path.stem.removeprefix('release-')), path,
                       content_type='application/xml')
    web_server.add('/ws/2/release/', DATA / 'search-abbey-road-the-beatles.xml',
                   content_type='application/xml')
    mb = musicbrainz.MusicBrainz()
    mb.applyPrefs([False, 1, 0])
    return mb


@pytest.fixture
def log(monkeypatch):
    """The lines the source writes to the Tag Sources window's log."""
    lines = []
    monkeypatch.setattr(musicbrainz, 'write_log', lines.append)
    return lines


def cover_bytes(path):
    """Synthetic image data: a JPEG's first bytes, then the address it is
    served at, so a test can tell which image came back."""
    return b'\xff\xd8\xff\xe0 synthetic ' + path.encode()


def serve_covers(web_server, release_id=ABBEY_ROAD):
    """Synthetic: a Cover Art Archive index for the release, in the
    service's shape (as Abbey Road's real index has it: each image's types,
    comment, original and thumbnails), and its images, on the local server.
    The Cover Art Archive redirects /front, /front-250 and /front-500 to
    the front image; the local server answers them with it."""
    base = f'/release/{release_id}'
    images = []
    for image_id, types, comment in [(1, ['Front', 'Booklet'], ''),
                                     (2, ['Back', 'Spine'], ''),
                                     (3, ['Medium'], 'Synthetic disc photo')]:
        stem = f'{base}/{image_id}'
        for suffix in ['', '-1200', '-250', '-500']:
            path = f'{stem}{suffix}.jpg'
            web_server.add(path, cover_bytes(path), content_type='image/jpeg')
        url = web_server.url + stem
        images.append({
            'approved': True, 'back': 'Back' in types, 'comment': comment, 'edit': image_id,
            'front': 'Front' in types, 'id': image_id, 'image': url + '.jpg',
            'thumbnails': {'1200': url + '-1200.jpg', '250': url + '-250.jpg',
                           '500': url + '-500.jpg', 'large': url + '-500.jpg',
                           'small': url + '-250.jpg'},
            'types': types,
        })
    web_server.add(base, json.dumps({'images': images,
                                     'release': f'https://musicbrainz.org/release/{release_id}'}),
                   content_type='application/json')
    for name, suffix in [('front', ''), ('front-1200', '-1200'), ('front-250', '-250'),
                         ('front-500', '-500')]:
        web_server.add(f'{base}/{name}', cover_bytes(f'{base}/1{suffix}.jpg'),
                       content_type='image/jpeg')


@pytest.fixture
def covers(source, web_server, monkeypatch):
    """The source with the Cover Art Archive on the local server, serving
    serve_covers' synthetic index and images for Abbey Road."""
    monkeypatch.setattr(musicbrainz, 'COVER_SERVER', web_server.url + '/')
    serve_covers(web_server)
    return source


def retrieve(source, release_id):
    """The release's fields, and what the Tag Sources window writes to each
    track: the release's fields, then the track's own."""
    info, tracks = source.retrieve(release_id)
    return info, [{**info, **track} for track in tracks]


def values(fields, name):
    """A field as the list of strings puddletag saves."""
    value = fields[name]
    return [value] if isinstance(value, str) else value


# The release's fields --------------------------------------------------------

ALBUM_ARTISTS = {
    ABBEY_ROAD: 'The Beatles',
    ABBEYS_ROAD: 'Ada Montellanico feat. Giovanni Falzone',
    COFFEE_LANDS: 'Various Artists',
    NINE_SYMPHONIES: 'Ludwig van Beethoven; Herbert von Karajan, Berliner Philharmoniker',
}


@pytest.mark.parametrize('release_id, expected', sorted({
    ABBEY_ROAD: ('Abbey Road', None, None, 'JP', '1983-05-21', '1', ABBEY_ROAD),
    ABBEYS_ROAD: ("Abbey's Road", None, '8058333571324', 'IT', '2016', '1', ABBEYS_ROAD),
    COFFEE_LANDS: ('A Putumayo Blend: Music From the Coffee Lands', 'B000003EKA',
                   '790248013527', 'US', '1997-09-22', '1',
                   'b8621ea1-acaf-46b5-b292-3a7c9eba9773'),
    NINE_SYMPHONIES: ('9 Symphonien', None, '028942903623', 'CA', None, '5', NINE_SYMPHONIES),
}.items()))
def test_release_fields(source, release_id, expected):
    """tagsources.txt: "**album**: The release's (album's) name.", "**asin**:
    Amazon identifier.", "**barcode**: The album's barcode.", "**country**:
    Album's release country.", "**date**: The release's date. Not available for
    every album.", "**discs**: Number of discs in the album.",
    "**mbrainz_album_id**: MusicBrainz's unique identifier for the album." The
    values are the recorded release's own; the album is the release's title,
    not a track's."""
    info, _ = retrieve(source, release_id)
    names = ['album', 'asin', 'barcode', 'country', 'date', 'discs', 'mbrainz_album_id']
    assert tuple(info.get(name) for name in names) == expected


def test_release_request_asks_for_labels(source, web_server):
    """tagsources.txt: "**label**: Labels responsible for the album's release."
    The recorded response has the labels whatever the request asks, so the
    request is what shows the bug."""
    retrieve(source, ABBEY_ROAD)
    [request] = web_server.requests
    assert 'labels' in request.query['inc'][0].split()


@pytest.mark.parametrize('release_id, expected', [
    (ABBEY_ROAD, (['EMI‐Odeon'], ['CP35‐3016'], ['3b6781a7-7733-4f04-8f0b-a41dfb8d6401'])),
    (ABBEYS_ROAD, (['Incipit Records'], ['INC225'], ['1a649f65-61c3-4e7d-8214-ff7e73837661'])),
    (COFFEE_LANDS, (['Putumayo World Music'], ['M 135-2', 'PUTU 135-2'],
                    ['98049da0-a5be-49b9-8d95-770e2d7906d2'])),
    (NINE_SYMPHONIES, (['Deutsche Grammophon'], ['429 036-2'], ['5a584032-dcef-41bb-9f8b-19540116fb1c'])),
])
def test_release_labels(source, release_id, expected):
    """tagsources.txt: "**label**: Labels responsible for the album's
    release.", "**mbrainz_label_id**: MusicBrainz's unique identifiers for the
    labels.", "**catalognumber**: Catalog numbers of the album." The values are
    the recorded release's label list (the hyphens of EMI‐Odeon and CP35‐3016
    are U+2010)."""
    info, _ = retrieve(source, release_id)
    assert (values(info, 'label'), values(info, 'catalognumber'),
            values(info, 'mbrainz_label_id')) == expected


@pytest.mark.parametrize('release_id', [
    ABBEY_ROAD,
    ABBEYS_ROAD,
    COFFEE_LANDS,
    NINE_SYMPHONIES,
])
def test_release_artist_keeps_the_join_phrases(source, release_id):
    """tagsources.txt: "**albumartist**: The release's artists, joined as the
    release joins them (eg. **Ada Montellanico feat. Giovanni Falzone**)." The
    value is the name and join phrase of each credit in the recorded release's
    artist credit."""
    info, _ = retrieve(source, release_id)
    assert info['artist'] == ALBUM_ARTISTS[release_id]


@pytest.mark.parametrize('release_id', sorted(ALBUM_ARTISTS))
def test_albumartist(source, release_id):
    """tagsources.txt: "**albumartist**: The release's artists, joined as the
    release joins them (eg. **Ada Montellanico feat. Giovanni Falzone**)."
    Issue 836: "The album artist tag remains empty despite the tag source
    (Musicbrainz) having one"."""
    info, _ = retrieve(source, release_id)
    assert info['albumartist'] == ALBUM_ARTISTS[release_id]


@pytest.mark.parametrize('release_id, expected', [
    (ABBEY_ROAD, ['b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d']),
    (ABBEYS_ROAD, ['1aa00b34-ccfc-468d-aa4c-425e1b8eb7f8',
                   'e3fe8224-eb5f-4411-a922-26da0ebdc912']),
    (COFFEE_LANDS, ['89ad4ac3-39f7-470e-963a-56509c546377']),
    (NINE_SYMPHONIES, ['1f9df192-a621-4f54-8850-2c5373b7eac9',
                       'd2ced2f1-6b58-47cf-ae87-5943e2ab6d99',
                       'dea28aa9-1086-4ffa-8739-0ccc759de1ce']),
])
def test_release_artist_ids(source, release_id, expected):
    """tagsources.txt: "**mbrainz_artist_id**: MusicBrainz's unique identifiers
    for the track's artists." The values are the ids in the recorded release's
    artist credit."""
    info, _ = retrieve(source, release_id)
    assert values(info, 'mbrainz_artist_id') == expected


# A track's fields ------------------------------------------------------------

COME_TOGETHER = '485bbe7f-d0f7-4ffe-8adb-0f1093dd2dbf'  # Abbey Road's first recording


@pytest.mark.parametrize('release_id, expected', [
    (ABBEY_ROAD, [str(n) for n in range(1, 18)]),
    (ABBEYS_ROAD, [str(n) for n in range(1, 12)]),
    (COFFEE_LANDS, [str(n) for n in range(1, 14)]),
    (NINE_SYMPHONIES, [str(n) for n in [*range(1, 9), *range(1, 9), *range(1, 10), *range(1, 9),
                                         *range(1, 6)]]),
])
def test_track_numbers(source, release_id, expected):
    """tagsources.txt: "**track**: The track's number on its disc." Values:
    each <track>'s <position> in the recorded response."""
    _, tracks = retrieve(source, release_id)
    assert [t['track'] for t in tracks] == expected


@pytest.mark.parametrize('release_id, expected', [
    (ABBEY_ROAD, ['Come Together', 'Something', 'Maxwell’s Silver Hammer', 'Oh! Darling',
                  'Octopus’s Garden', 'I Want You (She’s So Heavy)', 'Here Comes the Sun',
                  'Because', 'You Never Give Me Your Money', 'Sun King', 'Mean Mr. Mustard',
                  'Polythene Pam', 'She Came In Through the Bathroom Window',
                  'Golden Slumbers', 'Carry That Weight', 'The End', 'Her Majesty']),
    (COFFEE_LANDS, [
        'Guajira Bonita (Peru)', 'Soltarlo (Colombia)', 'Wasuze Otya? (Uganda)',
        'Maria Lando (Peru)', 'Below the Bassline (Jamaica)', 'M’Ban Samba (Brazil)',
        'Hanzvadzi (Zimbabwe)', 'Dilema (Cuba)', 'Esa noche (Mexico)', 'Gabby Kai (Hawai)',
        'Kothbiro (Kenya)', 'Este son (Costa Rica)',
        'La milonga de Ricardo en cha‐cha‐chá (Congo)']),
])
def test_track_titles(source, release_id, expected):
    """tagsources.txt: "**title**: The track's title, as the release gives it."
    Values: each <track>'s <title> in the recorded response, or its recording's
    when MusicBrainz leaves it out because they are the same."""
    _, tracks = retrieve(source, release_id)
    assert [t['title'] for t in tracks] == expected


# Disc 1 in full, then the first track of discs 2 to 5.
NINE_SYMPHONIES_TITLES = {
    0: 'Symphonie Nr. 1 C-dur op. 21: 1. Adagio molto - Allegro con brio',
    1: 'Symphonie Nr. 1 C-dur op. 21: 2. Andante cantabile con moto',
    2: 'Symphonie Nr. 1 C-dur op. 21: 3. Menuetto. Allegro molto e vivace',
    3: 'Symphonie Nr. 1 C-dur op. 21: 4. Adagio - Allegro molto e vivace',
    4: 'Symphonie Nr. 3 in Es-dur op. 55 »Eroica«: 1. Allegro con brio',
    5: 'Symphonie Nr. 3 in Es-dur op. 55 »Eroica«: 2. Marcia funebre. Adagio assai',
    6: 'Symphonie Nr. 3 in Es-dur op. 55 »Eroica«: 3. Scherzo. Allegro vivace',
    7: 'Symphonie Nr. 3 in Es-dur op. 55 »Eroica«: 4. Finale. Allegro molto',
    8: 'Symphonie Nr. 2 D-dur op. 36: 1. Adagio - Allegro con brio',
    16: 'Symphonie Nr. 5 c-moll op. 67: 1. Allegro con brio',
    25: 'Symphonie Nr. 7 A-dur op. 92: 1. Poco sostenuto - Vivace',
    33: 'Symphonie Nr. 9 d-moll op. 125: 1. Allegro ma non troppo, un poco maestoso',
}


def test_track_titles_of_a_release_with_several_discs(source):
    """tagsources.txt: "**title**: The track's title, as the release gives it."
    Values: each <track>'s <title> in the recorded response."""
    _, tracks = retrieve(source, NINE_SYMPHONIES)
    assert {i: tracks[i]['title'] for i in NINE_SYMPHONIES_TITLES} == NINE_SYMPHONIES_TITLES


@pytest.mark.parametrize('release_id, expected', [
    (ABBEY_ROAD, ['04:20', '03:02', '03:27', '03:27', '02:50', '07:46', '03:05', '02:46',
                  '03:57', '02:31', '01:06', '01:18', '01:52', '01:31', '01:36', '02:20', '00:25']),
    (ABBEYS_ROAD, [None] * 11),
])
def test_track_lengths(source, release_id, expected):
    """The release's track lengths, in puddletag's MM:SS (the docs give no
    format). Values: each <track>'s <length> in the recorded response (Abbey
    Road's: 260066, 182493, 207573, 207066, 170626, 466173, 185133, 166133,
    237000, 151333, 66200, 78360, 112906, 91226, 96306, 140866, 25200 ms);
    Abbey's Road has none."""
    _, tracks = retrieve(source, release_id)
    assert [t.get('__length') for t in tracks] == expected


@pytest.mark.parametrize('release_id, expected', [
    (ABBEY_ROAD, ['The Beatles'] * 17),
    (ABBEYS_ROAD, ['Ada Montellanico feat. Giovanni Falzone'] * 11),
    (COFFEE_LANDS, [
        'Julian Avalos', 'Claudia Gómez', 'Samite', 'Susana Baca', 'Ernest Ranglin',
        'Raimundo Sodré', 'Thomas Mapfumo', 'Carlos Puebla', 'Café Tacvba',
        'James “Bla” Pahinui', 'Ayub Ogada', 'Juan Carlos Ureña', 'Ricardo Lemvo & Makina Loca']),
    (NINE_SYMPHONIES, ['Ludwig van Beethoven'] * 38),
])
def test_track_artists(source, release_id, expected):
    """tagsources.txt: "**artist**: The track's artists on the release, joined
    as the release joins them." Values: the <track>'s own <artist-credit> in
    the recorded response, else its recording's."""
    _, tracks = retrieve(source, release_id)
    assert [t['artist'] for t in tracks] == expected


COFFEE_LANDS_ARTIST_IDS = [
    ['a96369f4-5bc6-4b69-80cb-04c9de0716e4'], ['1df027fe-014f-4db8-9e8c-fccda788cb84'],
    ['c4fe63ab-3ecc-4611-96d7-c84503e54f3f'], ['176af481-a5db-4902-84e0-393e7811b8c4'],
    ['924203bb-da5f-4bd0-9630-c753c7cb9774'], ['afe6dc3e-b13c-4ff4-a4d3-bf90f7b2cc19'],
    ['c17caac7-7667-4c8c-b54e-0aac360b37b6'], ['5bc8a04e-e68e-4775-bd1e-6a5f1d761f80'],
    ['c2b37a39-c66a-44b2-b190-a69485ae5d95'], ['3c9ec03c-919e-448e-9bca-fd97b40c8cd8'],
    ['2e9c624b-f2d6-456d-9778-8d0b004b8ffa'], ['bef6b08a-017d-471e-8852-00577b25921b'],
    ['96f6ba7b-3bc2-4eb2-bd1c-a599f57aac47', 'e7570816-243d-4788-b16d-b1c24c503b01'],
]


@pytest.mark.parametrize('release_id, expected', [
    (ABBEY_ROAD, [['b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d']] * 17),
    (COFFEE_LANDS, COFFEE_LANDS_ARTIST_IDS),
])
def test_track_artist_ids(source, release_id, expected):
    """tagsources.txt: "**mbrainz_artist_id**: MusicBrainz's unique identifiers
    for the track's artists." Values: the ids of each track's artist credit in
    the recorded response (issue 874: "mbrainz_artist_id should reflect the
    track artist, not the album artist")."""
    _, tracks = retrieve(source, release_id)
    assert [values(t, 'mbrainz_artist_id') for t in tracks] == expected


@pytest.mark.parametrize('release_id, index, expected', [
    (ABBEY_ROAD, 0, ['GBAYE0000944', 'GBAYE0601690']),
    (ABBEY_ROAD, 1, ['GBAYE0000943', 'GBAYE0601691']),
    (ABBEY_ROAD, 16, ['GBAYE0601706']),
    (NINE_SYMPHONIES, 0, ['DEF056101961']),
])
def test_isrcs(source, release_id, index, expected):
    """tagsources.txt: "**isrc**: ISRCs of the track's recording." Values: the
    recording's <isrc id> elements in the recorded response."""
    _, tracks = retrieve(source, release_id)
    assert values(tracks[index], 'isrc') == expected


def test_no_isrc_when_the_release_has_none(source):
    """Abbey's Road's recorded response has no <isrc-list>, so no track gets
    an isrc field."""
    _, tracks = retrieve(source, ABBEYS_ROAD)
    assert not any('isrc' in t for t in tracks)


@pytest.mark.parametrize('release_id, expected', [
    (ABBEY_ROAD, COME_TOGETHER),
    (COFFEE_LANDS, 'dc3f11e7-ad0c-4031-ab35-c2d9a012a05c'),
    (NINE_SYMPHONIES, '865dee8e-1962-4f38-9e10-98ba8d459079'),
])
def test_track_id_is_the_recording_id(source, release_id, expected):
    """tagsources.txt: "**mbrainz_track_id**: MusicBrainz's unique identifier
    for the track's recording (what Picard calls the MusicBrainz Recording
    Id)." Value: the first <recording id> in the recorded response, not the
    <track id>."""
    _, tracks = retrieve(source, release_id)
    assert tracks[0]['mbrainz_track_id'] == expected


def test_rating_is_the_recordings(source, web_server):
    """tagsources.txt: "**mbrainz_rating**: The track's rating according to
    MusicBrainz, from its recording." Synthetic: a rating added to Come
    Together's recording (the recordings have none: ratings aren't CC0)."""
    start = f'<recording id="{COME_TOGETHER}">'
    text = recorded(ABBEY_ROAD)
    assert start in text
    web_server.add(release_path(ABBEY_ROAD),
                   text.replace(start, start + '<rating votes-count="25">4.1</rating>', 1),
                   content_type='application/xml')
    info, tracks = retrieve(source, ABBEY_ROAD)
    assert tracks[0]['mbrainz_rating'] == '4.1'
    assert 'mbrainz_rating' not in info
    assert 'mbrainz_rating' not in tracks[1]


def test_a_recording_without_an_artist_credit(source, web_server):
    """Synthetic: Come Together's recording without its <artist-credit>. The
    track still comes back, with the album's artist as the window applies
    it."""
    text = recorded(ABBEY_ROAD)
    edited = re.sub(rf'(<recording id="{COME_TOGETHER}">.*?)<artist-credit>.*?</artist-credit>',
                    r'\1', text, count=1, flags=re.S)
    assert edited != text
    web_server.add(release_path(ABBEY_ROAD), edited, content_type='application/xml')
    _, tracks = retrieve(source, ABBEY_ROAD)
    assert tracks[0]['artist'] == 'The Beatles'


# Discs -----------------------------------------------------------------------

@pytest.mark.parametrize('release_id, expected', [
    (ABBEY_ROAD, ['1'] * 17),
    (NINE_SYMPHONIES, ['1'] * 8 + ['2'] * 8 + ['3'] * 9 + ['4'] * 8 + ['5'] * 5),
])
def test_discnumber(source, release_id, expected):
    """tagsources.txt: "**discnumber**: The number of the disc the track is
    on." The recorded response gives each <medium> its <position>."""
    info, tracks = retrieve(source, release_id)
    assert [t.get('discnumber') for t in tracks] == expected


def test_each_track_has_its_own_discs_id(source):
    """tagsources.txt: "**mbrainz_medium_id**: MusicBrainz's unique identifier
    for the disc the track is on." The ids are the recorded <medium id>s."""
    info, tracks = retrieve(source, NINE_SYMPHONIES)
    assert [t['mbrainz_medium_id'] for t in tracks] == (
        ['230882e3-7b60-370b-afc7-861ea5080930'] * 8
        + ['42a5c283-f31f-3301-b6a5-4adeb94ac36b'] * 8
        + ['fa43730e-9f27-3c9a-993d-71183fd6490e'] * 9
        + ['5d563fda-1e6e-377b-af9b-ca0209b83ff8'] * 8
        + ['25895bbc-2237-3942-9eac-366078cb3cea'] * 5)


def test_no_position_field(source):
    """tagsources.txt's field list has no **position**: the disc's number is
    **discnumber**."""
    info, tracks = retrieve(source, NINE_SYMPHONIES)
    assert 'position' not in info
    assert not any('position' in t for t in tracks)


def test_album_is_not_a_discs_title(source, web_server):
    """tagsources.txt: "**album**: The release's (album's) name." Synthetic:
    Abbey Road's disc is given a title."""
    start = '<medium id="c690a1e8-1fae-3d45-bed8-2800d4136f72">'
    text = recorded(ABBEY_ROAD)
    assert start in text
    web_server.add(release_path(ABBEY_ROAD),
                   text.replace(start, start + '<title>Synthetic disc title</title>', 1),
                   content_type='application/xml')
    info, tracks = retrieve(source, ABBEY_ROAD)
    assert info['album'] == 'Abbey Road'


# Relationships and search results --------------------------------------------

@pytest.mark.parametrize('release_id, field, expected', [
    (ABBEY_ROAD, 'drums (drum set) instrument', ['Ringo Starr']),
    (ABBEY_ROAD, 'electric bass guitar instrument', ['Paul McCartney']),
    (ABBEY_ROAD, 'engineer', ['Geoff Emerick', 'Phil McDonald']),
    (ABBEY_ROAD, 'producer', ['George Martin']),
    (ABBEYS_ROAD, 'arranger', ['Giovanni Falzone']),
    (ABBEYS_ROAD, 'engineer', ['Stefano Amerio']),
    (ABBEYS_ROAD, 'trumpet instrument', ['Giovanni Falzone']),
    (ABBEYS_ROAD, 'vocal', ['Ada Montellanico']),
    (NINE_SYMPHONIES, 'balance', ['Günter Hermanns']),
    (NINE_SYMPHONIES, 'conductor', ['Herbert von Karajan']),
    (NINE_SYMPHONIES, 'executive producer', ['Elsa Schiller']),
    (NINE_SYMPHONIES, 'performing orchestra', ['Berliner Philharmoniker']),
    (NINE_SYMPHONIES, 'producer', ['Otto Gerdes']),
])
def test_artist_relationships_are_fields(source, release_id, field, expected):
    """tagsources.txt: "The artists in a role, as in engineer, producer,
    conductor or arranger: producer: George Martin" and "The performers of an
    instrument or a voice, as in electric bass guitar instrument: Paul
    McCartney". The value is in the recording's artist relationships of the
    recorded response."""
    info, tracks = retrieve(source, release_id)
    assert values(tracks[0], field) == expected


@pytest.mark.parametrize('field, expected', [
    ('electric guitar instrument', ['George Harrison', 'John Lennon']),
    ('lead vocals vocal', ['John Lennon']),
])
def test_an_artist_credited_twice_is_listed_once(source, field, expected):
    """tagsources.txt: "The performers of an instrument or a voice, as in
    electric bass guitar instrument: Paul McCartney and lead vocals vocal: John
    Lennon". Come Together's recorded recording lists the same artist in
    several relationships of one type."""
    info, tracks = retrieve(source, ABBEY_ROAD)
    assert values(tracks[0], field) == expected


def test_a_recording_relationship_is_a_field(source):
    """tagsources.txt: "Other recordings, by title and artist, as in music
    video: Come Together by The Beatles"."""
    info, tracks = retrieve(source, ABBEY_ROAD)
    assert values(tracks[0], 'music video') == ['Come Together by The Beatles']


def test_a_related_recordings_credits_keep_their_join_phrases(source):
    """tagsources.txt: "Other recordings, by title and artist, as in ... remix
    and compilation". The recorded response credits the related recording's
    artists with "joinphrase" ", " between them."""
    info, tracks = retrieve(source, NINE_SYMPHONIES)
    assert values(tracks[37], 'compilation') == [
        'Symphonie Nr. 9. in d-Moll op. 125: 4. „O Freunde, nicht diese Töne!“ – Allegro assai – Allegro assai vivace. Alla marcia – Andante maestoso – Allegro energico, sempre ben marcato'
        ' by Reinhold Schmidt, Walter Berry, Gundula Janowitz, Waldemar Kmentt, Hilde Rössel‐Majdan, Wiener Singverein, Berliner Philharmoniker, Herbert von Karajan']


def test_search_results_have_no_score_field(source, web_server):
    """Synthetic: a score added to each release of the recorded search
    response, since the recordings have none (scores aren't CC0). It isn't a
    tag of the release."""
    text = (DATA / 'search-abbey-road-the-beatles.xml').read_text(encoding='utf-8')
    edited = text.replace('<release id=', '<release ns2:score="100" id=')
    assert edited.count('ns2:score="100"') == 2
    web_server.add('/ws/2/release/', edited, content_type='application/xml')
    results = source.search('Abbey Road', ['The Beatles'])
    assert len(results) == 2
    assert not any('ns2:score' in info for info, tracks in results)


# Searches --------------------------------------------------------------------

@pytest.mark.parametrize('text, query', [
    (';Abbey Road', 'release:Abbey Road'),
    ('Abbey Road', 'release:Abbey Road'),
    ('The Beatles;', 'artistname:The Beatles'),
    ('The Beatles;Abbey Road', 'release:Abbey Road AND artistname:The Beatles'),
])
def test_text_searches(source, web_server, text, query):
    """tagsources.txt: "To search for a specific artist, album pair enter the
    search string as **artist;album**", "Searching for the albums of a
    specific artist is done by leaving off the album part as in **artist;**",
    "For an album only leave off the artist part, as in **;album**",
    "Anything else is searched as an album title." The results are the
    recorded Abbey Road search's, without tracks."""
    results = source.keyword_search(text)
    [request] = web_server.requests
    assert request.path == '/ws/2/release/'
    assert request.query['query'] == [query]
    assert [info['mbrainz_album_id'] for info, tracks in results] == SEARCH_RESULTS
    assert all(tracks == [] for info, tracks in results)


def test_search_by_artist_id(source, web_server):
    """tagsources.txt: "**:a f59c5520-5f46-4d2c-b2c4-822eabf53419**"
    (Retrieving the albums of an artist by MusicBrainz Artist ID). The route
    answers only the unescaped query, with the recorded search by The
    Beatles' artist id."""
    web_server.add('/ws/2/release/', DATA / 'search-arid-the-beatles.xml',
                   content_type='application/xml', query={'query': 'arid:' + THE_BEATLES})
    results = source.keyword_search(':a ' + THE_BEATLES)
    [request] = web_server.requests
    assert request.query['query'] == ['arid:' + THE_BEATLES]
    assert len(results) == 2
    for info, tracks in results:
        assert THE_BEATLES in values(info, 'mbrainz_artist_id')


def test_retrieve_by_album_id(source, web_server):
    """tagsources.txt: "retrieving a specific album using its **MusicBrainz
    Album ID** can be done by starting your search string with **:b**";
    tut4.txt: "the Musicbrainz Tag Source supports searching via Musicbrainz
    Album Id". The album is retrieved at once, with its tracks."""
    [(info, tracks)] = source.keyword_search(':b ' + ABBEY_ROAD)
    assert [r.path for r in web_server.requests] == [release_path(ABBEY_ROAD)]
    assert info['album'] == 'Abbey Road'
    assert len(tracks) == 17


@pytest.mark.parametrize('text', [
    ':a ' + THE_BEATLES,
    ':b ' + ABBEY_ROAD,
    'Abbey Road',
    'The Beatles;Abbey Road',
])
def test_a_busy_musicbrainz_is_an_error(source, web_server, text):
    """The docs are silent on errors. A busy MusicBrainz (HTTP 503) is a
    RetrievalError with urllib's text and the code, for every kind of
    search."""
    web_server.add('/ws/2/release/', b'busy', status=503, content_type='text/plain')
    web_server.add(release_path(ABBEY_ROAD), b'busy', status=503, content_type='text/plain')
    with pytest.raises(RetrievalError) as error:
        source.keyword_search(text)
    assert error.value.code == 503
    assert str(error.value) == 'HTTP Error 503: Service Unavailable'


def test_file_search_with_an_album_id_retrieves_it(source, web_server):
    """tagsources.txt (How to Search): "Select all the files in an album you
    want to tag. Click on Search. The album's tag's will then be used to poll
    the tag sources." Files that carry the album's MusicBrainz id are
    retrieved by it, with no text search."""
    [(info, tracks)] = source.search('Abbey Road', {'The Beatles': [{
        'album': ['Abbey Road'], 'artist': ['The Beatles'], 'mbrainz_album_id': [ABBEY_ROAD]}]})
    assert [r.path for r in web_server.requests] == [release_path(ABBEY_ROAD)]
    assert info['mbrainz_album_id'] == ABBEY_ROAD
    assert len(tracks) == 17


def test_file_search_without_an_album_id(source, web_server):
    """tagsources.txt (How to Search): "Select all the files in an album you
    want to tag. Click on Search. The album's tag's will then be used to poll
    the tag sources." Without an album id the album and artist are searched
    for."""
    results = source.search('Abbey Road', {'The Beatles': [{
        'album': ['Abbey Road'], 'artist': ['The Beatles']}]})
    [request] = web_server.requests
    assert request.query['query'] == ['release:Abbey Road AND artistname:The Beatles']
    assert [info['mbrainz_album_id'] for info, tracks in results] == SEARCH_RESULTS


def test_file_search_of_several_artists_is_various_artists(source, web_server):
    """The docs are silent on files by several artists. Synthetic: two
    artists."""
    source.search('Abbey Road', {'Synthetic One': [{}], 'Synthetic Two': [{}]})
    [request] = web_server.requests
    assert request.query['query'] == ['release:Abbey Road AND artistname:Various Artists']


@pytest.mark.parametrize('status, reason', [
    (404, 'Not Found'),
    (503, 'Service Unavailable'),
])
def test_an_album_id_that_fails_falls_back_to_the_text_search(source, web_server, log, status,
                                                              reason):
    """The docs are silent on a file whose album id fails to retrieve. The
    search logs the error and goes on with the text search instead of
    crashing."""
    web_server.add(release_path(ABBEY_ROAD), b'', status=status, content_type='text/plain')
    results = source.search('Abbey Road', {'The Beatles': [{'mbrainz_album_id': [ABBEY_ROAD]}]})
    assert [r.path for r in web_server.requests] == [release_path(ABBEY_ROAD), '/ws/2/release/']
    assert [info['mbrainz_album_id'] for info, tracks in results] == SEARCH_RESULTS
    assert (f'<b>Error:</b> While retrieving Album ID {ABBEY_ROAD} '
            f'(HTTP Error {status}: {reason})') in log


def test_a_search_needs_an_artist_or_an_album(source, web_server):
    """The docs are silent on an empty search. A lone ";" is a RetrievalError
    and sends no request."""
    with pytest.raises(RetrievalError, match='Album or Artist required.'):
        source.keyword_search(';')
    assert web_server.requests == []


# Covers ----------------------------------------------------------------------

COVERS = f'/release/{ABBEY_ROAD}/'  # where serve_covers puts the images


def all_images(suffix):
    """What "All" returns for serve_covers' index: each image, with the
    puddletag image type of its first type (Front, Back, else Other)."""
    return [{'data': cover_bytes(f'{COVERS}{number}{suffix}.jpg'), 'desc': desc,
             'imagetype': imagetype, 'mime': 'image/jpeg'}
            for number, desc, imagetype in [(1, '', 3), (2, '', 4),
                                            (3, 'Synthetic disc photo', 0)]]


@pytest.mark.parametrize('size, suffix', [
    (0, '-250'),
    (1, '-500'),
    (2, ''),
])
def test_all_images(covers, web_server, size, suffix):
    """tagsources.txt: "**Cover size to retrieve:** is Small (250 px), Large
    (500 px) or Original Size (the default), for the front cover and for all
    images alike. **Amount of images to retrieve:** is Just the front cover
    (the default) or All (can take a while)." Every image of the Cover Art
    Archive's index comes back, in its order, at the size chosen, with the
    type of its first type: Front is Cover (Front), Back is Cover (Back),
    anything else Other. Issue 622: "An unhandled error occured: string
    indices must be integers"."""
    covers.applyPrefs([True, size, 1])
    info, tracks = covers.retrieve(ABBEY_ROAD)
    assert info['__image'] == all_images(suffix)
    assert [r.path for r in web_server.requests] == [
        release_path(ABBEY_ROAD), f'/release/{ABBEY_ROAD}',
        *[f'{COVERS}{number}{suffix}.jpg' for number in (1, 2, 3)]]


@pytest.mark.parametrize('size, name, suffix', [
    pytest.param(0, 'front-250', '-250', marks=pytest.mark.xfail(
        strict=True, reason='the front cover is always the original, whatever the size')),
    pytest.param(1, 'front-500', '-500', marks=pytest.mark.xfail(
        strict=True, reason='the front cover is always the original, whatever the size')),
    (2, 'front', ''),
])
def test_front_cover(covers, web_server, size, name, suffix):
    """tagsources.txt: "**Cover size to retrieve:** is Small (250 px), Large
    (500 px) or Original Size (the default), for the front cover and for all
    images alike." The Cover Art Archive serves the front cover as /front,
    /front-250 and /front-500. It has no image type: puddletag saves a
    missing one as Cover (Front)."""
    covers.applyPrefs([True, size, 0])
    info, tracks = covers.retrieve(ABBEY_ROAD)
    assert [r.path for r in web_server.requests] == [
        release_path(ABBEY_ROAD), f'/release/{ABBEY_ROAD}/{name}']
    assert [image['data'] for image in info['__image']] == [cover_bytes(f'{COVERS}1{suffix}.jpg')]
    assert info['__image'][0]['mime'] == 'image/jpeg'
    assert info['__image'][0].get('imagetype', 3) == 3


@pytest.mark.parametrize('count', [0, 1])
def test_no_images(covers, web_server, log, count):
    """The docs are silent on an album with no cover. The Cover Art Archive
    answers 404: the album comes back without a cover, and the log says why,
    for the front cover and for All."""
    web_server.add(f'/release/{ABBEY_ROAD}', b'', status=404, content_type='text/plain')
    web_server.add(f'/release/{ABBEY_ROAD}/front', b'', status=404, content_type='text/plain')
    covers.applyPrefs([True, 2, count])
    info, tracks = covers.retrieve(ABBEY_ROAD)
    assert '__image' not in info
    assert len(tracks) == 17
    assert 'Error retrieving image: No images exist for this album.' in log


@pytest.mark.parametrize('count', [0, 1])
def test_retrieve_cover_unchecked(covers, web_server, count):
    """tagsources.txt: "If **Retrieve Cover** is checked in the tag source's
    preferences, an album comes with its covers, from the Cover Art
    Archive." Unchecked, the Cover Art Archive isn't asked, for the front
    cover or for All."""
    covers.applyPrefs([False, 2, count])
    info, _ = covers.retrieve(ABBEY_ROAD)
    assert [r.path for r in web_server.requests] == [release_path(ABBEY_ROAD)]
    assert '__image' not in info


def test_an_image_that_fails_leaves_the_others(covers, web_server, log):
    """The docs are silent on an image that fails. Synthetic: the second image
    is gone (404). "All" logs the error and keeps the other two."""
    web_server.add(f'{COVERS}2.jpg', b'', status=404, content_type='text/plain')
    covers.applyPrefs([True, 2, 1])
    info, _ = covers.retrieve(ABBEY_ROAD)
    assert [i['data'] for i in info['__image']] == [cover_bytes(f'{COVERS}1.jpg'),
                                                    cover_bytes(f'{COVERS}3.jpg')]
    assert 'Error retrieving image: HTTP Error 404: Not Found' in log


@pytest.mark.xfail(strict=True, reason='a file search that finds an album id in the files '
                                       'retrieves the album without its cover')
def test_cover_with_an_album_id_in_the_files(covers, web_server):
    """tagsources.txt (How to Search): "Select all the files in an album you
    want to tag. Click on Search. The album's tag's will then be used to poll
    the tag sources." Files that carry the album's MusicBrainz id get the
    album as the **:b** search retrieves it, with its cover."""
    covers.applyPrefs([True, 2, 0])
    [(info, tracks)] = covers.search('Abbey Road', {'The Beatles': [{
        'mbrainz_album_id': [ABBEY_ROAD]}]})
    assert [i['data'] for i in info['__image']] == [cover_bytes(f'{COVERS}1.jpg')]


# Pacing ----------------------------------------------------------------------

# Every kind of request to MusicBrainz's web service, each sent by a source.
PACED_REQUESTS = {
    'album id search': lambda mb: mb.keyword_search(':b ' + ABBEY_ROAD),
    'artist and album search': lambda mb: mb.keyword_search('The Beatles;Abbey Road'),
    'artist id search': lambda mb: mb.keyword_search(':a ' + THE_BEATLES),
    'file search': lambda mb: mb.search('Abbey Road', {'The Beatles': [{'album': ['Abbey Road']}]}),
    'file search with an album id':
        lambda mb: mb.search('Abbey Road', {'The Beatles': [{'mbrainz_album_id': [ABBEY_ROAD]}]}),
    'release': lambda mb: mb.retrieve(ABBEY_ROAD),
    'release for AcoustID': lambda mb: musicbrainz.retrieve_album(ABBEY_ROAD),
    'text search': lambda mb: mb.keyword_search('Abbey Road'),
}


@pytest.mark.xfail(strict=True, reason='every search and retrieve waits a full second')
def test_the_first_request_does_not_wait(source, clock):
    """MusicBrainz's rate limiting page: "Your per-IP average must stay at
    about one request per second." Nothing was asked before, so there is
    nothing to wait for."""
    source.search('Abbey Road', ['The Beatles'])
    assert clock.sleeps == []


@pytest.mark.xfail(strict=True, reason='every search and retrieve waits a full second')
def test_a_request_within_a_second_waits_the_rest(source, clock):
    """MusicBrainz's rate limiting page: "Your per-IP average must stay at
    about one request per second." A request a quarter second after the last
    waits the other three quarters."""
    source.search('Abbey Road', ['The Beatles'])
    clock.advance(0.25)
    source.retrieve(ABBEY_ROAD)
    assert clock.sleeps == [pytest.approx(0.75)]


@pytest.mark.xfail(strict=True, reason='every search and retrieve waits a full second')
def test_a_request_more_than_a_second_later_does_not_wait(source, clock):
    """MusicBrainz's rate limiting page: "Your per-IP average must stay at
    about one request per second." A request over a second after the last has
    nothing to wait for."""
    source.search('Abbey Road', ['The Beatles'])
    clock.advance(1.5)
    source.search('Abbey Road', ['The Beatles'])
    assert clock.sleeps == []


@pytest.mark.xfail(strict=True, reason='the text, artist id and AcoustID requests never wait, '
                                       'the others wait twice')
@pytest.mark.parametrize('kind', sorted(PACED_REQUESTS))
def test_every_musicbrainz_request_is_paced(source, clock, kind):
    """MusicBrainz's rate limiting page: "Your per-IP average must stay at
    about one request per second. If it doesn't, all your requests are
    declined with 503 errors until your rate drops." Two requests of any
    kind in a row are a second apart."""
    PACED_REQUESTS[kind](source)
    PACED_REQUESTS[kind](source)
    assert clock.sleeps == [pytest.approx(1)]


@pytest.mark.xfail(strict=True, reason='every retrieve waits a second first')
def test_cover_art_archive_requests_are_not_paced(covers, web_server, clock):
    """The Cover Art Archive's rate limiting page: "There are currently no
    rate limiting rules in place". The front cover is asked right after the
    release, with no wait."""
    covers.applyPrefs([True, 2, 0])
    covers.retrieve(ABBEY_ROAD)
    assert [r.path for r in web_server.requests] == [release_path(ABBEY_ROAD),
                                                     f'/release/{ABBEY_ROAD}/front']
    assert clock.sleeps == []


@pytest.mark.xfail(strict=True, reason='every search and retrieve waits a full second')
def test_every_source_shares_the_pace(source, clock):
    """MusicBrainz's rate limiting page: "Your per-IP average must stay at
    about one request per second." The limit is per IP, not per source: the
    Tag Sources window and Mass Tagging each make a source of their own."""
    source.search('Abbey Road', ['The Beatles'])
    musicbrainz.MusicBrainz().search('Abbey Road', ['The Beatles'])
    assert clock.sleeps == [pytest.approx(1)]


@pytest.mark.xfail(strict=True, reason='every search and retrieve waits a full second')
def test_a_failed_request_counts(source, web_server, clock):
    """MusicBrainz's rate limiting page: "Your per-IP average must stay at
    about one request per second." A request that is declined was still
    sent, so the next waits for it."""
    web_server.add('/ws/2/release/', b'busy', status=503, content_type='text/plain')
    with pytest.raises(RetrievalError):
        source.search('Abbey Road', ['The Beatles'])
    web_server.add('/ws/2/release/', DATA / 'search-abbey-road-the-beatles.xml',
                   content_type='application/xml')
    source.search('Abbey Road', ['The Beatles'])
    assert clock.sleeps == [pytest.approx(1)]


# User agent ------------------------------------------------------------------

# What MusicBrainz asks of every program: "Application name/<version> ( contact-url )".
DEFAULT_USERAGENT = f'puddletag/{version_string} ( https://github.com/puddletag/puddletag )'


@pytest.mark.xfail(strict=True, reason='the user agent has no contact address')
def test_musicbrainz_is_told_who_to_contact(source, web_server, monkeypatch):
    """MusicBrainz's rate limiting page: "Each request sent to MusicBrainz
    needs to include a User-Agent header, with enough information in the
    User-Agent for us (MusicBrainz) to contact the application maintainers",
    as "Application name/<version> ( contact-url )"."""
    monkeypatch.setattr(tagsources, 'useragent', tagsources.useragent)
    source.search('Abbey Road', ['The Beatles'])
    [request] = web_server.requests
    assert request.headers['User-Agent'] == DEFAULT_USERAGENT


def test_the_preferences_user_agent_is_sent(source, web_server, monkeypatch):
    """preferences.txt: "The User-Agent puddletag sends to the web sites its
    tag sources read (MusicBrainz, Discogs, Mp3tag's tag sources)." What the
    user entered is what is sent."""
    monkeypatch.setattr(tagsources, 'useragent', tagsources.useragent)
    tagsources.set_useragent('Synthetic/1.0 ( https://example.org )')
    source.search('Abbey Road', ['The Beatles'])
    [request] = web_server.requests
    assert request.headers['User-Agent'] == 'Synthetic/1.0 ( https://example.org )'


@pytest.mark.xfail(strict=True, reason='a user agent saved by an older version is sent as it '
                                       'was saved')
@pytest.mark.parametrize('saved', [
    'puddletag/2.4.0',
    f'puddletag/{version_string}',
    'puddletag/2.4.0 ( https://github.com/puddletag/puddletag )',
])
def test_an_old_default_user_agent_becomes_the_new_one(source, web_server, monkeypatch, saved):
    """preferences.txt: "The default names puddletag, its version and its
    address, as MusicBrainz asks of every program; leave it empty for the
    default." Pressing OK in Preferences saves the default of the day, so a
    saved puddletag/<version> is the default, not a choice."""
    monkeypatch.setattr(tagsources, 'useragent', tagsources.useragent)
    tagsources.set_useragent(saved)
    source.search('Abbey Road', ['The Beatles'])
    [request] = web_server.requests
    assert request.headers['User-Agent'] == DEFAULT_USERAGENT


@pytest.mark.xfail(strict=True, reason="an empty user agent sends urllib's own")
def test_an_empty_user_agent_sends_the_default(source, web_server, monkeypatch):
    """preferences.txt: "The default names puddletag, its version and its
    address, as MusicBrainz asks of every program; leave it empty for the
    default." """
    monkeypatch.setattr(tagsources, 'useragent', tagsources.useragent)
    tagsources.set_useragent('')
    source.search('Abbey Road', ['The Beatles'])
    [request] = web_server.requests
    assert request.headers['User-Agent'] == DEFAULT_USERAGENT


@pytest.mark.xfail(strict=True, reason='an empty user agent is read as "puddetag/<version>"')
def test_an_empty_user_agent_is_read_as_the_default(monkeypatch):
    """preferences.txt: "The default names puddletag, its version and its
    address, as MusicBrainz asks of every program; leave it empty for the
    default." """
    monkeypatch.setattr(tagsources, 'useragent', tagsources.useragent)
    tagsources.set_useragent('')
    assert tagsources.get_useragent() == DEFAULT_USERAGENT
