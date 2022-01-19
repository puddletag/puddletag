import contextlib
import http.client
import os
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from itertools import chain, product, starmap

try:
    import acoustid

    # Don't want it to use audioread as python-gst
    # lib causes lockups.
    acoustid.have_audioread = False
except ImportError:
    from . import _acoustid as acoustid

from .. import audioinfo

from ..audioinfo import stringtags
from ..constants import SPINBOX, TEXT
from ..tagsources import set_status, write_log, SubmissionError
from ..tagsources.musicbrainz import retrieve_album
from ..translations import translate
from ..util import escape_html, isempty, to_string

CALCULATE_MSG = translate('AcoustID', "Calculating ID")
RETRIEVE_MSG = translate('AcoustID', "Retrieving AcoustID data: %1 of %2.")
RETRIEVE_MB_MSG = translate('AcoustID', "Retrieving MB album data: %1")
FP_ERROR_MSG = translate('AcoustID', "Error generating fingerprint: %1")
WEB_ERROR_MSG = translate('AcoustID', "Error retrieving data: %1")
SUBMIT_ERROR_MSG = translate('AcoustID', "Error submitting data: %1")
SUBMIT_MSG = translate('AcoustID', "Submitting data to AcoustID: %1 to %2 of %3.")
FOUND_ID_MSG = translate('AcoustID', "Found AcoustID in file.")
FILE_MSG = translate('AcoustID', 'File #%1: %2')

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
    return acoustid._fingerprint_file_fpcalc(fn, 120)


def id_in_tag(tag):
    if 'acoustid_fingerprint' in tag:
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
    response = acoustid.lookup(apikey, fp, dur, meta)
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
        raise acoustid.WebServiceError("status: %s" % data['status'])
    if 'results' not in data:
        raise acoustid.WebServiceError("results not included")

    try:
        result = data['results'][0]
    except IndexError:
        return None
    info = {}
    info['#score'] = result['score']
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
        track['acoustid_id'] = data['id']
        return {}, track
    if 'duration' in data:
        track['__length'] = audioinfo.strlength(data['duration'])
    track['acoustid_id'] = data['id']

    track['artist'] = data.get('artists', [{'name': ""}])[0]['name']
    if track['artist']:
        track['mbrainz_artist_id'] = data['artists'][0]['id']

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


def retrieve_album_info(album, tracks):
    if not album:
        return album, tracks
    msg = '<b>%s - %s</b>' % tuple(map(escape_html,
                                       (album['artist'], album['album'])))
    msg = RETRIEVE_MB_MSG.arg(msg)
    write_log(msg)
    set_status(msg)

    info, new_tracks = retrieve_album(album['mbrainz_album_id'])
    for t in tracks:
        try:
            index = int(t['track'])
        except KeyError:
            for index, nt in enumerate(new_tracks):
                if nt['title'] == t['title']:
                    break
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
        self.__lasttime = time.time()
        acoustid._send_request = self._send_request
        self.__user_key = ""

    def _send_request(self, req):
        """Given a urllib2 Request object, make the request and return a
        tuple containing the response data and headers.
        """
        if time.time() - self.__lasttime < 0.4:
            time.sleep(time.time() - self.__lasttime + 0.1)
        try:
            with contextlib.closing(urllib.request.urlopen(req)) as f:
                return f.read(), f.info()
        except urllib.error.HTTPError as exc:
            raise acoustid.WebServiceError('HTTP status %i' % exc.code, exc.read())
        except http.client.BadStatusLine:
            raise acoustid.WebServiceError('bad HTTP status line')
        except IOError:
            raise acoustid.WebServiceError('connection failed')

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

                write_log(RETRIEVE_MSG.arg(i + 1).arg(fns_len))
                set_status(RETRIEVE_MSG.arg(i + 1).arg(fns_len))

                data, fp = match("gT8GJxhO", fn.filepath, fp, dur)
                write_log(translate('AcoustID', "Parsing Data"))

                info = parse_lookup_result(data, fp=fp)
            except acoustid.FingerprintGenerationError as e:
                write_log(FP_ERROR_MSG.arg(str(e)))
                continue
            except acoustid.WebServiceError as e:
                set_status(WEB_ERROR_MSG.arg(str(e)))
                write_log(WEB_ERROR_MSG.arg(str(e)))
                break

            if hasattr(info, 'items'):
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
        for i, fn in enumerate(fns):

            try:
                disp_fn = audioinfo.decode_fn(fn.filepath)
            except AttributeError:
                disp_fn = fn['__path']
            write_log(FILE_MSG.arg(i + 1).arg(disp_fn))

            try:
                fp = id_in_tag(fn)
                if fp:
                    write_log(FOUND_ID_MSG)
                    dur, fp = fp
                else:
                    write_log(CALCULATE_MSG)
                    dur, fp = fingerprint_file(fn.filepath)

                info = {
                    'duration': str(dur),
                    'fingerprint': str(fp),
                }

                info.update(convert_for_submit(fn))
                data.append(info)

                if len(data) > 9 or i == fns_len - 1:
                    msg = SUBMIT_MSG.arg(i - len(data) + 2)
                    msg = msg.arg(i + 1).arg(fns_len)
                    write_log(msg)
                    set_status(msg)
                    acoustid.submit(API_KEY, self.__user_key, data)
                    data = []

            except acoustid.FingerprintGenerationError as e:
                traceback.print_exc()
                write_log(FP_ERROR_MSG.arg(str(e)))
                continue
            except acoustid.WebServiceError as e:
                traceback.print_exc()
                set_status(SUBMIT_ERROR_MSG.arg(str(e)))
                write_log(SUBMIT_ERROR_MSG.arg(str(e)))
                break

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
