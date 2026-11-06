import os
import traceback
from itertools import chain, product, starmap

import acoustid

from puddlestuff import audioinfo, tagsources

from puddlestuff.audioinfo import stringtags
from puddlestuff.constants import SPINBOX, TEXT
from puddlestuff.tagsources import set_status, write_log, RetrievalError, SubmissionError
from puddlestuff.tagsources.musicbrainz import retrieve_album
from puddlestuff.translations import translate
from puddlestuff.util import escape_html, isempty, to_string

CALCULATE_MSG = translate('AcoustID', "Calculating ID")
RETRIEVE_MSG = translate('AcoustID', "Retrieving AcoustID data: {} of {}.")
RETRIEVE_MB_MSG = translate('AcoustID', "Retrieving MB album data: {}")
FP_ERROR_MSG = translate('AcoustID', "Error generating fingerprint: {}")
WEB_ERROR_MSG = translate('AcoustID', "Error retrieving data: {}")
SUBMIT_ERROR_MSG = translate('AcoustID', "Error submitting data: {}")
SUBMIT_MSG = translate('AcoustID', "Submitting data to AcoustID: {} to {} of {}.")
NOTHING_SENT_MSG = translate('AcoustID', "No files were submitted.")
FOUND_ID_MSG = translate('AcoustID', "Found AcoustID in file.")
FILE_MSG = translate('AcoustID', "File #{}: {}")

API_KEY = "gT8GJxhO"


def album_hash(d):
    h = ''
    if 'album' in d:
        h = d['album']

    if 'year' in d:
        h += d['year']

    return hash(h)


def best_match(albums, tracks):
    hashed = {}
    data = (product(a, [t]) for a, t in zip(albums, tracks))

    for album, track in chain(*data):
        key = album_hash(album)
        if key not in hashed:
            hashed[key] = [album, 1, [track]]
        else:
            hashed[key][1] += 1
            hashed[key][2].append(track)

    matched_tracks = []
    ret = []

    for key in sorted(hashed, key=lambda i: hashed[i][1], reverse=True):
        album, count, tracks = hashed[key]
        new_tracks = []

        for t in tracks:
            if t['#exact'] not in matched_tracks:
                new_tracks.append(t)
                matched_tracks.append(t['#exact'])
        if not new_tracks: continue
        ret.append([album, new_tracks])

    return ret


def convert_for_submit(tags):
    cipher = {
        'mbrainz_track_id': 'mbid',
        'title': 'track',
        'track': 'trackno',
        'discnumber': 'discno',
        '__bitrate': 'bitrate',
        'musicip_puid': 'puid',
    }

    valid_keys = set(['artist', 'album', 'title', 'track', 'discno',
                      'mbid', 'year', 'bitrate', 'puid', 'trackno'])

    ret = dict((cipher.get(k, k), v) for k, v in stringtags(tags).items()
               if cipher.get(k, k) in valid_keys and v)
    bitrate = ret['bitrate'].split(' ')[0]
    if bitrate == 0:
        del (ret['bitrate'])
    else:
        ret['bitrate'] = str(bitrate)

    return ret


def fingerprint_file(fn):
    duration, fingerprint = acoustid.fingerprint_file(fn, force_fpcalc=True)
    return duration, to_string(fingerprint)


def id_in_tag(tag):
    # Older versions wrote a fingerprint as one value a byte.
    if 'acoustid_fingerprint' in tag and len(tag['acoustid_fingerprint']) == 1:
        fp = to_string(tag['acoustid_fingerprint'])
    else:
        return

    if '__length' in tag:
        duration = audioinfo.lnglength(tag['__length'])
    else:
        return

    return (duration, fp)


def match(apikey, path, fp=None, dur=None, meta='releases recordings tracks'):
    """Look up the metadata for an audio file. If ``parse`` is true,
    then ``parse_lookup_result`` is used to return an iterator over
    small tuple of relevant information; otherwise, the full parsed JSON
    response is returned.
    """
    path = os.path.abspath(os.path.expanduser(path))
    if None in (fp, dur):
        dur, fp = fingerprint_file(path)
    response = acoustid.lookup(apikey, fp, dur, meta, timeout=tagsources.TIMEOUT)
    return response, fp


def parse_release_data(rel):
    info = {}
    info['__numtracks'] = str(rel.get('track_count', ''))
    info['album'] = rel.get('title', '')

    if 'date' in rel:
        date = rel['date']
        info['year'] = '-'.join(str(z).zfill(2) for z in
                                map(date.get, ('year', 'month', 'day')) if z)
    info['country'] = rel.get('country', '')
    info['discs'] = str(rel.get('medium_count', ''))
    info['#album_id'] = rel['id']
    info['mbrainz_album_id'] = rel['id']
    if 'mediums' in rel:
        info['track'] = str(
            rel['mediums'][0]['tracks'][0].get('position', ""))
    return dict((k, v) for k, v in info.items() if not isempty(v))


def parse_lookup_result(data, albums=False, fp=None):
    if data['status'] != 'ok':
        message = data.get('error', {}).get('message', 'status: %s' % data['status'])
        raise acoustid.WebServiceError(message)
    if 'results' not in data:
        raise acoustid.WebServiceError("results not included")

    if not data['results']:
        return None
    result = next((r for r in data['results'] if r.get('recordings')), data['results'][0])
    info = {}
    info['#score'] = result['score']
    info['acoustid_id'] = result['id']
    if not result.get('recordings'):
        # No recording attached. This result is not very useful.
        return {
            'acoustid_id': result['id'],
            '#score': result['score'],
            'acoustid_fingerprint': fp, }

    if fp:
        info['acoustid_fingerprint'] = fp

    tracks = [parse_recording_data(r, info) for r in result['recordings']]

    return tracks


def parse_recording_data(data, info=None):
    track = {} if info is None else info.copy()

    try:
        track['title'] = data['title']
    except KeyError:
        track['mbrainz_track_id'] = data['id']
        return {}, track
    if 'duration' in data:
        track['__length'] = audioinfo.strlength(data['duration'])
    track['mbrainz_track_id'] = data['id']

    artists = data.get('artists') or [{'name': ""}]
    track['artist'] = artists[0]['name']
    if track['artist']:
        track['mbrainz_artist_id'] = artists[0]['id']

    if 'releases' in data:
        album_info = list(map(parse_release_data, data['releases']))
    else:
        album_info = []

    track = dict((k, v) for k, v in track.items() if not isempty(v))

    if 'artist' in track:
        for album in album_info:
            if 'artist' not in album:
                album['artist'] = track['artist']

    return album_info, track


def find_track(track, release_tracks):
    """The position of the release's track this match is: by recording id,
    which AcoustID and MusicBrainz share, or else by title. A track already
    given to a file isn't given to a second one. None if there's none."""
    free = [(index, t) for index, t in enumerate(release_tracks) if '#exact' not in t]
    recording_id = track.get('mbrainz_track_id')
    for index, t in free:
        if recording_id and t.get('mbrainz_track_id') == recording_id:
            return index
    for index, t in free:
        if t['title'] == track['title']:
            return index


def retrieve_album_info(album, tracks):
    if not album:
        return album, tracks
    msg = '<b>%s - %s</b>' % tuple(map(escape_html,
                                       (album.get('artist', ''), album['album'])))
    msg = RETRIEVE_MB_MSG.format(msg)
    write_log(msg)
    set_status(msg)

    info, new_tracks = retrieve_album(album['mbrainz_album_id'])
    for t in tracks:
        index = find_track(t, new_tracks)
        if index is None:
            new_tracks.append(t)
        else:
            t.update(new_tracks[index])
            new_tracks[index] = t

    return info, new_tracks


def which(program):

    # http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


class AcoustID(object):
    name = 'AcoustID'
    group_by = ['album', None]

    def __init__(self):
        object.__init__(self)
        self.min_score = 0.80
        self.preferences = [
            [translate("AcoustID", 'Minimum Score'), SPINBOX, [0, 100, 80]],
            [translate("AcoustID", "AcoustID Key"), TEXT, ""]
        ]
        self.__user_key = ""

    def search(self, artist, fns=None):

        tracks = []
        albums = []

        fns_len = len(fns)
        for i, fn in enumerate(fns):
            try:
                disp_fn = audioinfo.decode_fn(fn.filepath)
            except AttributeError:
                disp_fn = fn['__path']
            write_log(disp_fn)
            try:

                fp = id_in_tag(fn)
                if fp:
                    write_log(FOUND_ID_MSG)
                    dur, fp = fp
                else:
                    write_log(CALCULATE_MSG)
                    dur, fp = (None, None)

                write_log(RETRIEVE_MSG.format(i + 1, fns_len))
                set_status(RETRIEVE_MSG.format(i + 1, fns_len))

                data, fp = match("gT8GJxhO", fn.filepath, fp, dur)
                write_log(translate('AcoustID', "Parsing Data"))

                info = parse_lookup_result(data, fp=fp)
            except acoustid.FingerprintGenerationError as e:
                write_log(FP_ERROR_MSG.format(str(e)))
                continue
            except acoustid.WebServiceError as e:
                set_status(WEB_ERROR_MSG.format(str(e)))
                write_log(WEB_ERROR_MSG.format(str(e)))
                if not tracks:
                    raise RetrievalError(WEB_ERROR_MSG.format(str(e)))
                break

            if hasattr(info, 'items'):
                if info['#score'] >= self.min_score:
                    albums.append([{}])
                    info['#exact'] = fn
                    tracks.append(info)
            elif info is not None:
                for album, track in info:
                    if track and track['#score'] >= self.min_score:
                        track['#exact'] = fn
                        tracks.append(track)
                        albums.append(album if album else [{}])

        return starmap(retrieve_album_info, best_match(albums, tracks))

    def submit(self, fns):
        if not self.__user_key:
            raise SubmissionError(translate("AcoustID",
                                            "Please enter AcoustID user key in settings."))

        fns_len = len(fns)
        data = []
        numbers = []
        sent = False
        for i, fn in enumerate(fns):

            try:
                disp_fn = audioinfo.decode_fn(fn.filepath)
            except AttributeError:
                disp_fn = fn['__path']
            write_log(FILE_MSG.format(i + 1, disp_fn))

            try:
                fp = id_in_tag(fn)
                if fp:
                    write_log(FOUND_ID_MSG)
                    dur, fp = fp
                else:
                    write_log(CALCULATE_MSG)
                    dur, fp = fingerprint_file(fn.filepath)
            except acoustid.FingerprintGenerationError as e:
                traceback.print_exc()
                write_log(FP_ERROR_MSG.format(str(e)))
                continue

            info = {
                'duration': str(int(dur)),
                'fingerprint': str(fp),
            }

            info.update(convert_for_submit(fn))
            data.append(info)
            numbers.append(i + 1)

            if len(data) > 9:
                self.__send(data, numbers, fns_len)
                sent = True
                data, numbers = [], []

        if data:
            self.__send(data, numbers, fns_len)
            sent = True

        if not sent:
            return NOTHING_SENT_MSG

    def __send(self, data, numbers, total):
        msg = SUBMIT_MSG.format(numbers[0], numbers[-1], total)
        write_log(msg)
        set_status(msg)
        try:
            acoustid.submit(API_KEY, self.__user_key, data, timeout=tagsources.TIMEOUT)
        except acoustid.WebServiceError as e:
            traceback.print_exc()
            message = SUBMIT_ERROR_MSG.format(str(e))
            write_log(message)
            raise SubmissionError(message)

    def retrieve(self, info):
        return None

    def applyPrefs(self, args):
        self.min_score = args[0] / 100.0
        self.__user_key = args[1]


if not which('fpcalc'):
    raise ImportError("fpcalc not found on system")

info = AcoustID

if __name__ == '__main__':
    x = AcoustID()
    x.applyPrefs([85, "KEIY0X4P"])
    file_dir = ''
    files = []
    for z in os.listdir(file_dir):
        fn = os.path.join(file_dir, z)
        try:
            tag = audioinfo.Tag(fn)
            if tag is not None:
                files.append(tag)
        except:
            pass
    x.submit(files)
