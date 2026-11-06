"""The AcoustID tag source (tagsources.txt, "Using AcoustID"): a file's
fingerprint, what the web service replies, how a search turns replies
into albums, and what a submit sends. Replies come from a local web server.
acoustid/lookup-canon.json under tests/data is one AcoustID served (recorded by
record_acoustid.py); every other reply is synthetic, in its shape, and names a
recorded MusicBrainz release. fpcalc is a stub, but for the two real_fpcalc
tests.
"""
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

import acoustid
import mutagen.id3
import pytest

from puddlestuff import audioinfo, tagsources
from puddlestuff.tagsources import RetrievalError, SubmissionError, musicbrainz

DATA = Path(__file__).parent.parent / 'data'
REPO = Path(__file__).parent.parent.parent

ABBEY_ROAD = '6bb3793b-f991-378e-9bff-0bd3117f2298'
ABBEY_ROAD_PATH = '/ws/2/release/' + ABBEY_ROAD
ACOUSTID_ID = '11111111-2222-4333-8444-555555555555'  # synthetic
BEATLES = 'b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d'
# Recordings of the recorded Abbey Road.
COME_TOGETHER = '485bbe7f-d0f7-4ffe-8adb-0f1093dd2dbf'
SOMETHING = 'b849acd4-0638-49ea-8e40-7391613d4890'
LOOKUP = '/v2/lookup'
# Synthetic, in the shape of the service's errors.
LOOKUP_ERROR = '{"error": {"code": 4, "message": "invalid API key"}, "status": "error"}'
# The service docs' own example id.
MBID = '4e0d8649-1f89-44f3-91af-4c0dbee81f28'
REFUSAL = 'error 6: invalid user API key ("User with the API key does not exist")'
SUBMIT = '/v2/submit'
# Synthetic, in the shape of the service's errors.
SUBMIT_ERROR = ('{"error": {"code": 6, "message": "invalid user API key (\\"User with the API key '
                'does not exist\\")"}, "status": "error"}')
# Synthetic, in the shape of the service docs' example.
SUBMITTED = '{"status": "ok", "submissions": [{"id": 123456789, "status": "pending"}]}'
USER_KEY = 'synthetic-user-key'


def recorded_reply():
    return json.loads((DATA / 'acoustid' / 'lookup-canon.json').read_text(encoding='utf-8'))


def release(release_id=ABBEY_ROAD, title='Abbey Road'):
    """A release as a lookup gives it. Synthetic, in the recorded reply's shape."""
    return {'id': release_id, 'medium_count': 1, 'title': title, 'track_count': 17,
            'mediums': [{'position': 1, 'track_count': 17, 'tracks': [{'position': 1}]}]}


def recording(title='Come Together', recording_id=COME_TOGETHER, releases=None):
    """A recording as a lookup gives it, on Abbey Road unless releases says
    otherwise. Synthetic, in the recorded reply's shape."""
    return {'artists': [{'id': BEATLES, 'name': 'The Beatles'}], 'duration': 259.0,
            'id': recording_id, 'releases': [release()] if releases is None else releases,
            'title': title}


def reply(*recordings, score=0.9):
    """A lookup's answer: one result, holding these recordings."""
    result = {'id': ACOUSTID_ID, 'score': score}
    if recordings:
        result['recordings'] = list(recordings)
    return json.dumps({'results': [result], 'status': 'ok'})


def answer(service, body, **form):
    """Serves body to the lookups whose form fields are these."""
    service.add(LOOKUP, body, content_type='application/json', form=form)


def tags(*paths):
    return [audioinfo.Tag(str(path)) for path in paths]


def lookups(service):
    """The form fields of each lookup sent."""
    return [request.form for request in service.requests if request.path == LOOKUP]


def submissions(service):
    """The form fields of each submit request sent."""
    return [request.form for request in service.requests if request.path == SUBMIT]


def sending(lines):
    """The lines that announce a request."""
    return [line for line in lines if line.startswith('Submitting data')]


def exact(tracks):
    return [track for track in tracks if '#exact' in track]


def sources_listed(path):
    """The tag sources a freshly started puddletag lists with this PATH."""
    code = ('import puddlestuff.resource\n'
            'from puddlestuff import tagsources\n'
            'print(*(source.name for source in tagsources.tagsources), sep="\\n")\n')
    done = subprocess.run([sys.executable, '-c', code], capture_output=True, check=True, cwd=REPO,
                          env=dict(os.environ, PATH=str(path)), text=True)
    return done.stdout.splitlines()


@pytest.fixture
def source(acoust_id, acoustid_service):
    """AcoustID as the Tag Sources window builds it, on the local server,
    which serves the recorded Abbey Road."""
    acoustid_service.add(ABBEY_ROAD_PATH, DATA / 'musicbrainz' / f'release-{ABBEY_ROAD}.xml',
                         content_type='application/xml')
    return acoust_id.AcoustID()


@pytest.fixture
def log(acoust_id, monkeypatch):
    """The lines the source writes to the Tag Sources window's log."""
    lines = []
    monkeypatch.setattr(acoust_id, 'write_log', lines.append)
    return lines


@pytest.fixture
def statuses(acoust_id, monkeypatch):
    """The lines the source writes to the Tag Sources window's label."""
    lines = []
    monkeypatch.setattr(acoust_id, 'set_status', lines.append)
    return lines


@pytest.fixture
def submitter(source, acoustid_service):
    """AcoustID with a user key, on a local server that takes every submit."""
    source.applyPrefs([80, USER_KEY])
    acoustid_service.add(SUBMIT, SUBMITTED, content_type='application/json')
    return source


@pytest.fixture
def silent_server():
    """A local address that takes connections and never answers. Closing it
    at teardown frees any request still waiting."""
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen()
    yield f'http://127.0.0.1:{listener.getsockname()[1]}/v2'
    listener.close()


@pytest.fixture
def closed_server():
    """A local address nothing listens on."""
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    listener.close()
    return f'http://127.0.0.1:{port}/v2'


# Loading, preferences and parsers --------------------------------------------

def test_listed_with_fpcalc_installed(fpcalc):
    # "tag sources supporting lookups from Discogs, FreeDB, MusicBrainz and
    # AcoustID"; "you need to have chromaprint (specifically the fpcalc
    # binary) installed".
    assert sources_listed(fpcalc.directory) == ['AcoustID', 'Discogs.com', 'FreeDB', 'MusicBrainz']


def test_absent_without_fpcalc(tmp_path):
    # "tag sources supporting lookups from Discogs, FreeDB, MusicBrainz and
    # AcoustID"; "you need to have chromaprint (specifically the fpcalc
    # binary) installed". PATH holds an empty folder, so there's no fpcalc.
    assert sources_listed(tmp_path) == ['Discogs.com', 'FreeDB', 'MusicBrainz']


def test_preferences_offer_the_minimum_score_and_the_key(acoust_id):
    # The docs don't say; this is what puddletag does.
    from puddlestuff.constants import SPINBOX, TEXT
    assert acoust_id.AcoustID().preferences == [['Minimum Score', SPINBOX, [0, 100, 80]],
                                                ['AcoustID Key', TEXT, '']]


def test_minimum_score_is_a_percentage(acoust_id):
    # The docs don't say; this is what puddletag does.
    source = acoust_id.AcoustID()
    assert source.min_score == 0.8
    source.applyPrefs([85, 'Key'])
    assert source.min_score == 0.85


def test_recorded_reply_gives_the_recordings_track(acoust_id):
    # "acoustid_id: The AcoustID identifier for a track as returned by the
    # AcoustID webservice"; "acoustid_fingerprint: The calculated AcoustID
    # fingerprint". The reply is the recorded one, and the fingerprint is
    # synthetic.
    release_id = 'ab46c4ff-af73-4ed4-bbfb-665d6358b7ec'
    [(albums, track)] = acoust_id.parse_lookup_result(recorded_reply(), fp='AQABsynthetic')
    assert albums == [{'#album_id': release_id, '__numtracks': '108',
                       'album': 'The Complete Works of Frédéric Chopin', 'artist': 'Aya Higuchi',
                       'country': 'XW', 'discs': '1', 'mbrainz_album_id': release_id,
                       'track': '106'}]
    assert track == {'#score': 0.99827456, '__length': '00:43',
                     'acoustid_fingerprint': 'AQABsynthetic',
                     'acoustid_id': '93a95c37-79d9-435d-978a-2529991aec27',
                     'artist': 'Aya Higuchi',
                     'mbrainz_artist_id': '1c3f22d8-961c-46d0-bdf0-6c15a463697f',
                     'mbrainz_track_id': 'ba53f6d0-2686-43ba-a34a-b9af5c19405e',
                     'title': 'Miscellaneous no. 17 - Op. posth. Canon: F minor'}


@pytest.mark.parametrize('date, year', [
    ({'year': 1969, 'month': 9, 'day': 26}, '1969-09-26'),
    ({'year': 1969, 'month': 9}, '1969-09'),
    ({'year': 1969}, '1969'),
])
def test_release_date_becomes_the_year(acoust_id, date, year):
    # The docs don't say; this is what puddletag does. Synthetic dates.
    assert acoust_id.parse_release_data(dict(release(), date=date))['year'] == year


def test_result_without_recordings_keeps_acoustids_id(acoust_id):
    # "acoustid_id: The AcoustID identifier for a track as returned by the
    # AcoustID webservice". Synthetic reply.
    assert acoust_id.parse_lookup_result(json.loads(reply()), fp='AQABsynthetic') == {
        '#score': 0.9, 'acoustid_fingerprint': 'AQABsynthetic', 'acoustid_id': ACOUSTID_ID}


def test_no_results_is_no_match(acoust_id):
    # The docs don't say; this is what puddletag does. Synthetic reply.
    assert acoust_id.parse_lookup_result({'results': [], 'status': 'ok'}) is None


def test_reply_without_results_is_an_error(acoust_id):
    # The docs don't say; this is what puddletag does. Synthetic reply.
    with pytest.raises(acoustid.WebServiceError, match='^results not included$'):
        acoust_id.parse_lookup_result({'status': 'ok'})


def test_error_reply_is_an_error(acoust_id):
    # The docs don't say; this is what puddletag does. Synthetic, in the
    # shape of the service's errors.
    with pytest.raises(acoustid.WebServiceError, match='^invalid API key$'):
        acoust_id.parse_lookup_result(json.loads(LOOKUP_ERROR))


def test_recording_without_a_title_has_no_album(acoust_id):
    # "acoustid_id: The AcoustID identifier for a track as returned by the
    # AcoustID webservice". Synthetic recording.
    assert acoust_id.parse_recording_data({'id': COME_TOGETHER}, {'#score': 0.9}) == (
        {}, {'#score': 0.9, 'mbrainz_track_id': COME_TOGETHER})


def test_recording_keeps_its_first_artist(acoust_id):
    # The docs don't say; this is what puddletag does. Synthetic recording.
    artists = [{'id': BEATLES, 'joinphrase': ' feat. ', 'name': 'The Beatles'},
               {'id': 'b', 'name': 'Billy Preston'}]
    albums, track = acoust_id.parse_recording_data(dict(recording(releases=[]), artists=artists))
    assert track['artist'] == 'The Beatles'
    assert track['mbrainz_artist_id'] == BEATLES


# Fingerprints and the request ------------------------------------------------

def test_lookup_sends_the_files_fingerprint_and_length(source, fpcalc, acoustid_service, make_audio):
    # tagsources.txt: "calculating a unique fingerprint for your audio files".
    path = make_audio('a.flac')  # synthetic: no tags
    answer(acoustid_service, reply())
    list(source.search('', tags(path)))
    assert fpcalc.files == [str(path)]
    assert lookups(acoustid_service) == [{
        'client': ['gT8GJxhO'], 'duration': ['42'], 'fingerprint': ['AQABsynthetic'],
        'format': ['json'], 'meta': ['releases recordings tracks']}]


def test_fingerprint_in_the_file_skips_fpcalc(source, fpcalc, acoustid_service, log, make_audio):
    # The docs don't say; this is what puddletag does.
    path = make_audio('a.flac', acoustid_fingerprint='AQABstored')
    answer(acoustid_service, reply())
    list(source.search('', tags(path)))
    assert fpcalc.files == []
    (form,) = lookups(acoustid_service)
    assert form['fingerprint'] == ['AQABstored']
    assert form['duration'] == ['1']  # the file's length
    assert 'Found AcoustID in file.' in log


def test_file_fpcalc_cant_read_is_skipped(source, fpcalc, acoustid_service, log, make_audio):
    # The docs don't say; this is what puddletag does.
    fpcalc.fail()
    first = make_audio('a.flac')  # synthetic: no tags
    second = make_audio('b.flac', acoustid_fingerprint='AQABstored')
    answer(acoustid_service, reply())
    ((album, found),) = list(source.search('', tags(first, second)))
    assert album == {}
    assert found[0]['#exact'].filepath == str(second)
    assert len(lookups(acoustid_service)) == 1
    assert 'Error generating fingerprint: fpcalc exited with status 2' in log


def test_fingerprint_is_text(acoust_id, make_audio):
    # tagsources.txt: "acoustid_fingerprint: The calculated AcoustID fingerprint."
    assert acoust_id.fingerprint_file(str(make_audio('a.flac'))) == (42.0, 'AQABsynthetic')


def test_fingerprint_comes_from_pyacoustids_public_call(acoust_id, monkeypatch):
    # The docs don't say; this is what puddletag does. No behaviour differs
    # (the public call runs the private one, with the same 120 seconds), so
    # only a spy can show it.
    calls = []

    def fingerprint_file(path, **options):
        calls.append((path, options))
        return 42.0, b'AQABsynthetic'

    monkeypatch.setattr(acoustid, 'fingerprint_file', fingerprint_file)
    acoust_id.fingerprint_file('/music/song.flac')
    assert calls == [('/music/song.flac', {'force_fpcalc': True})]


@pytest.mark.timeout(10)
def test_lookup_gives_up_on_a_silent_server(source, silent_server, monkeypatch, make_audio):
    # The docs don't say; every other source's request has this timeout.
    monkeypatch.setattr(tagsources, 'TIMEOUT', 0.2)
    acoustid.set_base_url(silent_server)
    path = make_audio('a.flac')  # synthetic: no tags
    with pytest.raises(RetrievalError, match='timed out'):
        list(source.search('', tags(path)))


def test_lookups_wait_between_requests(source, acoustid_clock, acoustid_service, make_audio):
    # acoustid.org/webservice: "Do not make more than 3 requests per second."
    # pyacoustid's rate limit is what keeps this.
    paths = [make_audio(f'{name}.flac') for name in 'abc']  # synthetic: no tags
    answer(acoustid_service, reply())
    list(source.search('', tags(*paths)))
    assert len(acoustid_clock.waits) == 2
    assert min(acoustid_clock.waits) >= 0.33


def test_source_leaves_pyacoustid_alone(acoust_id, monkeypatch):
    # The docs don't say; this is what puddletag does. pyacoustid no longer
    # has the function the source used to replace.
    monkeypatch.delattr(acoustid, '_send_request', raising=False)
    acoust_id.AcoustID()
    assert not hasattr(acoustid, '_send_request')


# Search, Minimum Score and the merge -----------------------------------------

def test_each_file_goes_to_the_release_most_files_share(source, acoustid_service, make_audio):
    # The docs don't say. Synthetic replies: the first two recordings are on two releases,
    # the third on one.
    paths = [make_audio(f'{n}.flac', acoustid_fingerprint=f'AQAB{n}') for n in (1, 2, 3)]
    both = [release('other-release', 'Other'), release()]
    answer(acoustid_service, reply(recording('Come Together', releases=both)), fingerprint='AQAB1')
    answer(acoustid_service, reply(recording('Something', SOMETHING, both)), fingerprint='AQAB2')
    answer(acoustid_service, reply(recording('Oh! Darling', 'de896c41-463d-4eaa-8fe4-d826e2afa0f8')),
           fingerprint='AQAB3')
    [(album, tracks)] = list(source.search('', tags(*paths)))
    assert album['album'] == 'Abbey Road'
    assert [t['title'] for t in exact(tracks)] == ['Come Together', 'Something', 'Oh! Darling']
    assert [i for i, t in enumerate(tracks) if '#exact' in t] == [0, 1, 3]
    releases = [r.path for r in acoustid_service.requests if r.path.startswith('/ws/2/release/')]
    assert releases == [ABBEY_ROAD_PATH]


def test_files_without_a_release_share_an_empty_album(source, acoustid_service, make_audio):
    # The docs don't say.
    paths = [make_audio('a.flac'), make_audio('b.flac')]
    answer(acoustid_service, reply(recording(releases=[])))
    files = tags(*paths)
    [(album, tracks)] = list(source.search('', files))
    assert album == {}
    assert [t['#exact'] for t in tracks] == files
    assert not [r for r in acoustid_service.requests if r.path.startswith('/ws/2/')]


@pytest.mark.parametrize(('score', 'percent', 'kept'), [
    (0.79, 80, False), (0.8, 80, True), (0.6, 50, True), (0.49, 50, False)])
def test_minimum_score_filters(source, acoustid_service, make_audio, score, percent, kept):
    # The docs don't say; the preference's name, "Minimum Score".
    path = make_audio('a.flac')
    source.applyPrefs([percent, ''])
    answer(acoustid_service, reply(recording(), score=score))
    albums = list(source.search('', tags(path)))
    assert len(albums) == (1 if kept else 0)


def test_minimum_score_filters_a_result_without_recordings(source, acoustid_service, make_audio):
    # The docs don't say; the preference's name, "Minimum Score".
    path = make_audio('a.flac')
    answer(acoustid_service, reply(score=0.1))
    assert list(source.search('', tags(path))) == []


def test_result_without_recordings_is_kept_above_the_minimum(source, acoustid_service, make_audio):
    # The docs don't say.
    path = make_audio('a.flac')
    answer(acoustid_service, reply(score=0.9))
    [(album, tracks)] = list(source.search('', tags(path)))
    assert album == {}
    assert tracks[0]['acoustid_id'] == ACOUSTID_ID


def test_an_error_stops_the_search(source, acoustid_service, log, make_audio):
    # The docs don't say.
    paths = [make_audio(f'{n}.flac', acoustid_fingerprint=f'AQAB{n}') for n in (1, 2, 3)]
    answer(acoustid_service, reply(recording()), fingerprint='AQAB1')
    answer(acoustid_service, LOOKUP_ERROR, fingerprint='AQAB2')
    [(album, tracks)] = list(source.search('', tags(*paths)))
    assert len(lookups(acoustid_service)) == 2
    assert album['album'] == 'Abbey Road'
    assert len(exact(tracks)) == 1
    assert any(line.startswith('Error retrieving data: ') for line in log)


def test_a_first_error_is_raised(source, acoustid_service, make_audio):
    # The docs don't say.
    paths = [make_audio('a.flac'), make_audio('b.flac')]
    answer(acoustid_service, LOOKUP_ERROR)
    with pytest.raises(RetrievalError, match='^Error retrieving data: '):
        list(source.search('', tags(*paths)))
    assert len(lookups(acoustid_service)) == 1


def test_unreadable_reply_stops_the_search(source, acoustid_service, log, make_audio):
    # The docs don't say.
    path = make_audio('a.flac')
    acoustid_service.add(LOOKUP, 'not json', status=500, content_type='text/plain')
    with pytest.raises(RetrievalError, match='^Error retrieving data: '):
        list(source.search('', tags(path)))
    assert 'Error retrieving data: response is not valid JSON' in log


def test_match_joins_the_musicbrainz_release(source, acoustid_service, make_audio):
    # tagsources.txt: "AcoustID returns the same data as the MusicBrainz tag source".
    path = make_audio('a.flac')
    answer(acoustid_service, reply(recording()))
    [(album, tracks)] = list(source.search('', tags(path)))
    info, rows = musicbrainz.retrieve_album(ABBEY_ROAD)
    assert album == info
    assert len(tracks) == 17
    assert tracks[1:] == rows[1:]
    assert {key: tracks[0][key] for key in rows[0]} == rows[0]
    assert tracks[0]['#exact'].filepath == str(path)
    assert tracks[0]['#score'] == 0.9
    assert tracks[0]['acoustid_fingerprint'] == 'AQABsynthetic'
    assert tracks[0]['acoustid_id'] == ACOUSTID_ID


def test_no_title_matching_leaves_the_release_alone(source, acoustid_service, make_audio):
    # The docs don't say. Synthetic: a recording the release doesn't hold.
    path = make_audio('a.flac')
    answer(acoustid_service, reply(recording('Not On This Release', 'unknown-recording')))
    [(album, tracks)] = list(source.search('', tags(path)))
    assert len(tracks) == 18
    assert tracks[16]['title'] == 'Her Majesty'
    assert '#exact' not in tracks[16]
    assert tracks[17]['title'] == 'Not On This Release'
    assert '#exact' in tracks[17]


def test_two_files_of_one_recording_each_get_a_row(source, acoustid_service, make_audio):
    # The docs don't say.
    paths = [make_audio('a.flac'), make_audio('b.flac')]
    answer(acoustid_service, reply(recording()))
    files = tags(*paths)
    [(album, tracks)] = list(source.search('', files))
    assert sorted(t['#exact'].filepath for t in exact(tracks)) == sorted(str(p) for p in paths)
    assert len(tracks) == 18


def test_recording_is_found_by_its_id(source, acoustid_service, make_audio):
    # The docs don't say. Synthetic: the recording's title differs from the release's.
    path = make_audio('a.flac')
    answer(acoustid_service, reply(recording('Come Together (Remastered)')))
    [(album, tracks)] = list(source.search('', tags(path)))
    assert len(tracks) == 17
    assert tracks[0]['title'] == 'Come Together'
    assert '#exact' in tracks[0]


def without_artists(recording_):
    del recording_['artists']
    return recording_


def empty_artists(recording_):
    recording_['artists'] = []
    return recording_


@pytest.mark.parametrize('damage', [without_artists, empty_artists], ids=['no key', 'empty list'])
def test_recording_without_artists_joins_the_release(source, acoustid_service, make_audio, damage):
    # The docs don't say. Synthetic: pyacoustid's own parser accepts both.
    path = make_audio('a.flac')
    answer(acoustid_service, reply(damage(recording())))
    [(album, tracks)] = list(source.search('', tags(path)))
    assert album['album'] == 'Abbey Road'
    assert len(exact(tracks)) == 1


def test_first_result_with_recordings_is_used(source, acoustid_service, make_audio):
    # The docs don't say. Synthetic: the first result has no recordings.
    path = make_audio('a.flac')
    body = {'results': [{'id': ACOUSTID_ID, 'score': 0.95},
                        {'id': 'b', 'recordings': [recording()], 'score': 0.9}],
            'status': 'ok'}
    answer(acoustid_service, json.dumps(body))
    [(album, tracks)] = list(source.search('', tags(path)))
    assert album['album'] == 'Abbey Road'
    assert len(exact(tracks)) == 1


def test_fingerprint_of_many_values_is_calculated_again(source, fpcalc, acoustid_service, make_audio):
    # The docs don't say. Synthetic: what older versions wrote for 'AQA'.
    path = make_audio('a.flac', acoustid_fingerprint=['65', '81', '65'])
    answer(acoustid_service, reply(recording()))
    list(source.search('', tags(path)))
    assert fpcalc.files == [str(path)]
    assert lookups(acoustid_service)[0]['fingerprint'] == ['AQABsynthetic']


# Submitting ------------------------------------------------------------------

def test_submit_needs_the_users_key(source, acoustid_service, make_audio):
    # acoustid.org/webservice, Submit: "user": required, "users's API key". The
    # message itself: the docs don't say; this is what puddletag does.
    path = make_audio('a.flac', acoustid_fingerprint='AQABstored')
    with pytest.raises(SubmissionError, match=r'^Please enter AcoustID user key in settings\.$'):
        source.submit(tags(path))
    assert submissions(acoustid_service) == []


def test_ten_files_go_in_one_request(submitter, acoustid_service, log, statuses, make_audio):
    # acoustid.org/webservice, Submit: "Multiple fingerprints can be submitted
    # in one call." The number ten: the docs don't say; this is what puddletag
    # does.
    paths = [make_audio(f'{n}.flac', acoustid_fingerprint=f'AQAB{n}') for n in range(10)]
    submitter.submit(tags(*paths))
    (form,) = submissions(acoustid_service)
    assert [form[f'fingerprint.{n}'] for n in range(10)] == [[f'AQAB{n}'] for n in range(10)]
    assert form['client'] == ['gT8GJxhO']
    assert form['format'] == ['json']
    assert form['user'] == [USER_KEY]
    assert sending(log) == statuses == ['Submitting data to AcoustID: 1 to 10 of 10.']


def test_eleventh_file_goes_in_a_second_request(submitter, acoustid_service, log, statuses,
                                                make_audio):
    # acoustid.org/webservice, Submit: "Multiple fingerprints can be submitted
    # in one call." The number ten: the docs don't say; this is what puddletag
    # does.
    paths = [make_audio(f'{n}.flac', acoustid_fingerprint=f'AQAB{n}') for n in range(11)]
    submitter.submit(tags(*paths))
    first, second = submissions(acoustid_service)
    assert 'fingerprint.9' in first
    assert 'fingerprint.10' not in first
    assert second['fingerprint.0'] == ['AQAB10']
    assert 'fingerprint.1' not in second
    assert statuses == ['Submitting data to AcoustID: 1 to 10 of 11.',
                        'Submitting data to AcoustID: 11 to 11 of 11.']
    assert sending(log) == statuses


def test_submits_wait_between_requests(submitter, acoustid_clock, make_audio):
    # acoustid.org/webservice: "Do not make more than 3 requests per second."
    paths = [make_audio(f'{n}.flac', acoustid_fingerprint=f'AQAB{n}') for n in range(11)]
    submitter.submit(tags(*paths))
    assert len(acoustid_clock.waits) == 1
    assert min(acoustid_clock.waits) >= 0.33


@pytest.mark.parametrize(('duration', 'sent'), [(42, '42'), (42.9, '42')])
def test_computed_fingerprint_is_submitted(submitter, fpcalc, acoustid_service, log, make_audio,
                                           duration, sent):
    # acoustid.org/webservice, Submit: "duration": "duration of the whole audio
    # file in seconds"; "fingerprint": "audio fingerprint data". The second
    # length is synthetic: fpcalc prints whole seconds, and pyacoustid cuts
    # with int().
    fpcalc.answer(duration=duration)
    path = make_audio('a.flac')  # synthetic: no tags
    submitter.submit(tags(path))
    assert fpcalc.files == [str(path)]
    (form,) = submissions(acoustid_service)
    assert form['duration.0'] == [sent]
    assert form['fingerprint.0'] == ['AQABsynthetic']
    assert 'Calculating ID' in log


def test_fingerprint_in_the_file_is_submitted_without_fpcalc(submitter, fpcalc, acoustid_service,
                                                             log, make_audio):
    # The docs don't say; this is what puddletag does.
    path = make_audio('a.flac', acoustid_fingerprint='AQABstored')
    submitter.submit(tags(path))
    assert fpcalc.files == []
    (form,) = submissions(acoustid_service)
    assert form['duration.0'] == ['1']  # the file's length
    assert form['fingerprint.0'] == ['AQABstored']
    assert 'Found AcoustID in file.' in log


def test_fingerprint_goes_as_plain_text(submitter, fpcalc, acoustid_service, make_audio):
    # acoustid.org/webservice, Submit: "fingerprint": "audio fingerprint data",
    # as in AQABz0qUkZ...
    fpcalc.answer(fingerprint='AQAB-_synthetic')
    path = make_audio('a.flac')  # synthetic: no tags
    submitter.submit(tags(path))
    (form,) = submissions(acoustid_service)
    assert form['fingerprint.0'] == ['AQAB-_synthetic']


def test_files_before_a_failed_last_file_are_sent(submitter, fpcalc, acoustid_service, log,
                                                  make_audio):
    # The docs don't say.
    fpcalc.fail()
    first = make_audio('a.flac', acoustid_fingerprint='AQABa')
    second = make_audio('b.flac', acoustid_fingerprint='AQABb')
    third = make_audio('c.flac')  # synthetic: no tags
    submitter.submit(tags(first, second, third))
    (form,) = submissions(acoustid_service)
    assert form['fingerprint.0'] == ['AQABa']
    assert form['fingerprint.1'] == ['AQABb']
    assert 'fingerprint.2' not in form
    assert 'Error generating fingerprint: fpcalc exited with status 2' in log


def test_file_fpcalc_cant_read_leaves_the_others(submitter, fpcalc, acoustid_service, log,
                                                 make_audio):
    # The docs don't say.
    fpcalc.fail()
    first = make_audio('a.flac', acoustid_fingerprint='AQABa')
    second = make_audio('b.flac')  # synthetic: no tags
    third = make_audio('c.flac', acoustid_fingerprint='AQABc')
    submitter.submit(tags(first, second, third))
    (form,) = submissions(acoustid_service)
    assert form['fingerprint.0'] == ['AQABa']
    assert form['fingerprint.1'] == ['AQABc']
    assert sending(log) == ['Submitting data to AcoustID: 1 to 3 of 3.']


@pytest.mark.parametrize(('body', 'status', 'message'), [
    (SUBMIT_ERROR, 400, REFUSAL), ('not json', 500, 'response is not valid JSON')],
    ids=['refused', 'unreadable'])
def test_refusal_stops_the_submit(submitter, acoustid_service, log, make_audio, body, status,
                                  message):
    # The docs don't say. Like the search's first error, which is raised.
    paths = [make_audio(f'{n}.flac', acoustid_fingerprint=f'AQAB{n}') for n in range(11)]
    acoustid_service.add(SUBMIT, body, status=status, content_type='application/json')
    with pytest.raises(SubmissionError) as error:
        submitter.submit(tags(*paths))
    assert str(error.value) == f'Error submitting data: {message}'
    assert len(submissions(acoustid_service)) == 1
    assert str(error.value) in log


def test_refusal_of_a_later_request_keeps_the_first(submitter, acoustid_service, log, make_audio):
    # The docs don't say.
    paths = [make_audio(f'{n}.flac', acoustid_fingerprint=f'AQAB{n}') for n in range(11)]
    acoustid_service.add(SUBMIT, SUBMIT_ERROR, status=400, content_type='application/json',
                         form={'fingerprint.0': 'AQAB10'})
    with pytest.raises(SubmissionError):
        submitter.submit(tags(*paths))
    assert len(submissions(acoustid_service)) == 2


def test_dropped_connection_stops_the_submit(submitter, closed_server, log, make_audio):
    # The docs don't say. A refused connection takes the same branch as a
    # dropped one.
    path = make_audio('a.flac', acoustid_fingerprint='AQABstored')
    acoustid.set_base_url(closed_server)
    with pytest.raises(SubmissionError, match='^Error submitting data: HTTP request failed: '):
        submitter.submit(tags(path))


@pytest.mark.timeout(10)
def test_submit_gives_up_on_a_silent_server(submitter, silent_server, monkeypatch, make_audio):
    # The docs don't say; every other source's request has this timeout.
    path = make_audio('a.flac', acoustid_fingerprint='AQABstored')
    monkeypatch.setattr(tagsources, 'TIMEOUT', 0.2)
    acoustid.set_base_url(silent_server)
    with pytest.raises(SubmissionError, match='timed out'):
        submitter.submit(tags(path))


def test_nothing_to_send_says_so(submitter, fpcalc, acoustid_service, make_audio):
    # The docs don't say; the maintainer's call. Nothing selected, then a file
    # fpcalc can't read.
    fpcalc.fail()
    path = make_audio('a.flac')  # synthetic: no tags
    assert submitter.submit([]) == 'No files were submitted.'
    assert submitter.submit(tags(path)) == 'No files were submitted.'
    assert submissions(acoustid_service) == []


# What a submit sends ---------------------------------------------------------

FIELDS = {'album': 'The Division Bell', 'artist': 'Pink Floyd', 'date': '1994', 'discnumber': '1',
          'genre': 'Rock', 'title': 'High Hopes', 'tracknumber': '11'}


def flac_with_fields(make_audio):
    return make_audio('a.flac', acoustid_fingerprint='AQABstored', musicbrainz_trackid=MBID, **FIELDS)


def mp3_with_fields(make_audio):
    path = make_audio('a.mp3', **FIELDS)
    id3 = mutagen.id3.ID3(str(path))
    id3.add(mutagen.id3.TXXX(encoding=3, desc='acoustid_fingerprint', text=['AQABstored']))
    id3.add(mutagen.id3.UFID(owner='http://musicbrainz.org', data=MBID.encode()))
    id3.save()
    return path


@pytest.mark.parametrize('file_with_fields', [flac_with_fields, mp3_with_fields], ids=['flac', 'mp3'])
def test_fields_go_under_the_services_names(submitter, acoustid_service, make_audio, file_with_fields):
    # webservice, Submit: "track title", "track artist", "album title",
    # "album release year", "track number", "disc number", "corresponding
    # MusicBrainz recording ID"; and "If the file has embedded MusicBrainz
    # tags, please send the MusicBrainz recording ID."
    path = file_with_fields(make_audio)
    submitter.submit(tags(path))
    (form,) = submissions(acoustid_service)
    # The bitrate depends on the encoder: the next tests look at it.
    assert {key: value for key, value in form.items() if key != 'bitrate.0'} == {
        'album.0': ['The Division Bell'], 'artist.0': ['Pink Floyd'], 'client': ['gT8GJxhO'],
        'discno.0': ['1'], 'duration.0': ['1'], 'fingerprint.0': ['AQABstored'], 'format': ['json'],
        'mbid.0': [MBID], 'track.0': ['High Hopes'], 'trackno.0': ['11'], 'user': [USER_KEY],
        'year.0': ['1994']}


def test_puid_is_sent(submitter, acoustid_service, make_audio):
    # The docs don't say: the page no longer lists it; Picard still sends it.
    path = make_audio('a.flac', acoustid_fingerprint='AQABstored', musicip_puid=MBID)
    submitter.submit(tags(path))
    (form,) = submissions(acoustid_service)
    assert form['puid.0'] == [MBID]


def test_zero_bitrate_is_not_sent(submitter, acoustid_service, make_audio):
    # webservice, Submit: "bitrate of the audio file", 192: none isn't a bitrate of 0.
    path = make_audio('a.flac', acoustid_fingerprint='AQABstored')
    assert tags(path)[0]['__bitrate'] == '0 kb/s'
    submitter.submit(tags(path))
    (form,) = submissions(acoustid_service)
    assert 'bitrate.0' not in form


def test_bitrate_goes_as_a_number(submitter, acoustid_service, make_audio):
    # webservice, Submit: "bitrate of the audio file", 192.
    submitter.submit(tags(mp3_with_fields(make_audio)))
    (form,) = submissions(acoustid_service)
    assert re.fullmatch('[1-9][0-9]*', form['bitrate.0'][0])


def test_file_without_a_bitrate_is_sent(submitter, acoustid_service, make_audio):
    # webservice, Submit: bitrate.# is optional. Synthetic: every format
    # audioinfo reads has a bitrate, so this tag is a plain dict.
    tag = {'__length': '00:42', '__path': '/music/a.flac', 'acoustid_fingerprint': ['AQABdict']}
    path = make_audio('a.flac', acoustid_fingerprint='AQABfile')
    submitter.submit([tag, *tags(path)])
    (form,) = submissions(acoustid_service)
    assert form['fingerprint.0'] == ['AQABdict']
    assert form['fingerprint.1'] == ['AQABfile']
    assert 'bitrate.0' not in form


# Values a submit changes -----------------------------------------------------

def test_track_disc_and_year_go_as_the_service_reads_them(submitter, acoustid_service, make_audio):
    # webservice, Submit: "track number", 11; "disc number", 1; "album
    # release year", 1994.
    path = make_audio('a.flac', acoustid_fingerprint='AQABstored', date='2001-05-06', discnumber='1/2',
                      tracknumber='3/12')
    submitter.submit(tags(path))
    (form,) = submissions(acoustid_service)
    assert form['discno.0'] == ['1']
    assert form['trackno.0'] == ['3']
    assert form['year.0'] == ['2001']


def test_values_that_arent_numbers_are_left_out(submitter, acoustid_service, make_audio):
    # webservice, Submit: "track number", 11; "album release year", 1994.
    path = make_audio('a.flac', acoustid_fingerprint='AQABstored', date='unknown', tracknumber='A1')
    submitter.submit(tags(path))
    (form,) = submissions(acoustid_service)
    assert 'trackno.0' not in form
    assert 'year.0' not in form


def test_several_values_are_joined_for_the_service(submitter, acoustid_service, make_audio):
    # webservice, Submit: "track artist". Picard joins several with "; ".
    path = make_audio('a.flac', acoustid_fingerprint='AQABstored', artist=['A1', 'A2'])
    submitter.submit(tags(path))
    (form,) = submissions(acoustid_service)
    assert form['artist.0'] == ['A1; A2']


def test_where_the_service_takes_one_value_the_first_goes(submitter, acoustid_service, make_audio):
    # webservice, Submit: "track number", 11; "disc number", 1; "album
    # release year", 1994; "corresponding MusicBrainz recording ID".
    path = make_audio('a.flac', acoustid_fingerprint='AQABstored', date=['2001', '2002'],
                      discnumber=['1', '2'], musicbrainz_trackid=[MBID, 'other'], tracknumber=['3', '4'])
    submitter.submit(tags(path))
    (form,) = submissions(acoustid_service)
    assert form['discno.0'] == ['1']
    assert form['mbid.0'] == [MBID]
    assert form['trackno.0'] == ['3']
    assert form['year.0'] == ['2001']


def test_fields_named_like_the_services_are_not_sent(submitter, acoustid_service, make_audio):
    # The docs don't say; the maintainer's call: only the file's real values go.
    # Synthetic: fields named like the service's parameters.
    path = make_audio('a.flac', acoustid_fingerprint='AQABstored', bitrate='999', discno='2',
                      mbid='other', trackno='7')
    submitter.submit(tags(path))
    (form,) = submissions(acoustid_service)
    for name in ('bitrate.0', 'discno.0', 'mbid.0', 'trackno.0'):
        assert name not in form


def test_field_named_like_the_services_leaves_the_real_value(submitter, acoustid_service):
    # The docs don't say; the maintainer's call. Synthetic: a plain dict, not a
    # file, because a file's fields come in a different order on each run, and
    # here the field named like the service's must come after the real one.
    tag = {'__length': '00:42', '__path': '/music/a.flac', 'acoustid_fingerprint': ['AQABdict'],
           'discnumber': ['1'], 'discno': ['2'], 'mbrainz_track_id': [MBID], 'mbid': ['other'],
           'track': ['3'], 'trackno': ['7']}
    submitter.submit([tag])
    (form,) = submissions(acoustid_service)
    assert form['discno.0'] == ['1']
    assert form['mbid.0'] == [MBID]
    assert form['trackno.0'] == ['3']


# Fingerprints in the file ----------------------------------------------------

def mp3_with_picards_fingerprint(make_audio):
    path = make_audio('a.mp3')
    id3 = mutagen.id3.ID3(str(path))
    id3.add(mutagen.id3.TXXX(encoding=3, desc='Acoustid Fingerprint', text=['AQABpicard']))
    id3.save()
    return path


def test_picards_fingerprint_is_read(submitter, fpcalc, acoustid_service, make_audio):
    # Picard's tag mapping: AcoustID Fingerprint, ID3v2 TXXX:Acoustid Fingerprint.
    path = mp3_with_picards_fingerprint(make_audio)
    submitter.submit(tags(path))
    assert fpcalc.files == []
    (form,) = submissions(acoustid_service)
    assert form['fingerprint.0'] == ['AQABpicard']


def test_picards_fingerprint_is_read_by_a_search(source, fpcalc, acoustid_service, make_audio):
    # Picard's tag mapping: AcoustID Fingerprint, ID3v2 TXXX:Acoustid Fingerprint.
    path = mp3_with_picards_fingerprint(make_audio)
    answer(acoustid_service, reply())
    list(source.search('', tags(path)))
    assert lookups(acoustid_service)[0]['fingerprint'] == ['AQABpicard']


@pytest.mark.parametrize('name', ['a.apl', 'a.tta'])
def test_fingerprint_without_a_length_is_calculated_again(submitter, fpcalc, acoustid_service,
                                                          make_audio, name):
    # acoustid.org/webservice, Submit: "duration of the whole audio file in
    # seconds", 641. puddletag reads only the APEv2 tag in these files, so it
    # has no length for them.
    path = make_audio(name, acoustid_fingerprint='AQABstored')
    assert tags(path)[0]['__length'] == '00:00'
    submitter.submit(tags(path))
    assert fpcalc.files == [str(path)]
    (form,) = submissions(acoustid_service)
    assert form['duration.0'] == ['42']
    assert form['fingerprint.0'] == ['AQABsynthetic']


def test_search_calculates_a_fingerprint_without_a_length(source, fpcalc, acoustid_service,
                                                          make_audio):
    # acoustid.org/webservice, Submit: "duration of the whole audio file in
    # seconds", 641. puddletag reads only the APEv2 tag in these files, so it
    # has no length for them.
    path = make_audio('a.tta', acoustid_fingerprint='AQABstored')
    answer(acoustid_service, reply(recording()))
    list(source.search('', tags(path)))
    assert fpcalc.files == [str(path)]
    assert lookups(acoustid_service)[0]['duration'] == ['42']


# The service's address -------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="pyacoustid's default address is plain http")
def test_requests_go_to_the_services_https_address(acoust_id):
    # acoustid.org/webservice, Submit: https://api.acoustid.org/v2/submit
    assert acoustid.API_BASE_URL == 'https://api.acoustid.org/v2/'


# The real fpcalc -------------------------------------------------------------

def test_real_fpcalc_fingerprints_a_file(real_fpcalc, make_audio):
    # tagsources.txt: "calculating a unique fingerprint for your audio files".
    path = make_audio('a.flac', seconds=4)
    duration, fingerprint = real_fpcalc.fingerprint_file(str(path))
    assert duration == 4
    assert re.fullmatch('[A-Za-z0-9_-]+', fingerprint)


def test_real_fpcalc_refuses_a_second_of_silence(real_fpcalc, make_audio):
    # The docs don't say. Synthetic: a second of silence is too short for
    # fpcalc to fingerprint.
    path = make_audio('a.flac')
    with pytest.raises(acoustid.FingerprintGenerationError, match='^fpcalc exited with status 2$'):
        real_fpcalc.fingerprint_file(str(path))
