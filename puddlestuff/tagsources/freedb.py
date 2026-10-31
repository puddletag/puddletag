from . import CDDB

CDDB.proto = 6  # utf8 instead of latin1
from collections import defaultdict

from puddlestuff import version_string
from puddlestuff import audioinfo
from puddlestuff.util import to_string
from puddlestuff.tagsources import RetrievalError
from puddlestuff.util import translate
import time

CLIENTINFO = {'client_name': "puddletag",
              'client_version': version_string}


def sumdigits(n): return sum(map(int, str(n)))


def sort_func(key, default):

    def func(audio):
        # "2/12" is track 2; what isn't a number sorts after the numbers.
        track = to_string(audio.get(key, [default])).split('/')[0]
        try:
            return 0, int(track), ''
        except ValueError:
            return 1, 0, track

    return func


def frame_count(audio):
    """The track's length in CD frames (75 a second)."""
    mut_obj = getattr(audio, 'mut_obj', None)
    if mut_obj is not None:
        return round(mut_obj.info.length * 75)
    return audioinfo.lnglength(to_string(audio['__length'])) * 75


def calculate_discid(album):
    # from quodlibet's cddb plugin by Michael Urman
    # The CDDB algorithm: the first track starts 150 frames in.
    album = sorted(album, key=sort_func('__filename', ''))
    album = sorted(album, key=sort_func('track', '1'))
    offsets = []
    leadout = 150
    for song in album:
        offsets.append(leadout)
        leadout += frame_count(song)
    checksum = sum(sumdigits(o // 75) for o in offsets)
    total_time = leadout // 75 - offsets[0] // 75
    discid = ((checksum % 0xff) << 24) | (total_time << 8) | len(album)
    return [discid, len(album)] + offsets + [leadout // 75]


def convert_info(info):
    keys = {'category': '#category',
            'disc_id': '#discid',
            'title': 'album'}

    for key in list(info.keys()):
        if key not in ['disc_id', 'category'] and isinstance(info[key], str):
            info[key] = decode_str(info[key])
        if key in keys:
            info[keys[key]] = info[key]
            del (info[key])
    if 'artist' not in info and 'album' in info:
        try:
            info['artist'], info['album'] = [z.strip() for z in
                                             info['album'].split(' / ', 1)]
        except (TypeError, ValueError):
            pass
    if '#discid' in info:
        info['freedb_disc_id'] = decode_str(info['#discid'])
    if '#category' in info:
        info['freedb_category'] = decode_str(info['#category'])

    return info


def convert_tracks(disc):
    tracks = []
    for tracknum, title in sorted(disc.items()):
        track = {'track': str(tracknum + 1)}
        if ' / ' in title:
            track['artist'], track['title'] = [z.strip() for z in
                                               decode_str(title).split(' / ', 1)]
        else:
            track['title'] = title
        tracks.append(track)
    return tracks


def decode_str(s):
    return s if isinstance(s, str) else s.decode('utf8', 'replace')


def query(category, discid):
    # from quodlibet's cddb plugin by Michael Urman
    discinfo = {}
    tracktitles = {}

    read, info = CDDB.read(category, discid, **CLIENTINFO)
    if read != 210:
        message = translate(
            "FreeDB", "Couldn't read {} {}: the server answered {}.").format(
            category, discid, read)
        if isinstance(info, list):
            message = ' '.join([message] + info)
        raise RetrievalError(message, read)

    for key, value in info.items():
        if isinstance(value, str):
            value = value.strip()
        if key.startswith('TTITLE'):
            try:
                tracktitles[int(key[6:])] = value
            except ValueError:
                pass
        elif key == 'DGENRE':
            if value:
                discinfo['genre'] = value
        elif key == 'DTITLE':
            dtitle = value.strip().split(' / ', 1)
            if len(dtitle) == 2:
                discinfo['artist'], discinfo['title'] = dtitle
            else:
                discinfo['title'] = dtitle[0].strip()
        elif key == 'DYEAR':
            if value:
                discinfo['year'] = value

    return discinfo, tracktitles


def retrieve(category, discid):
    try:
        info, tracks = query(category, discid)
    except RetrievalError:
        raise
    except EnvironmentError as e:
        raise RetrievalError(str(e))
    except ValueError:
        raise RetrievalError(translate(
            "FreeDB", "The server's reply isn't a CDDB reply."))
    if 'disc_id' not in info:
        info['disc_id'] = discid
    if 'category' not in info:
        info['category'] = category

    return convert_info(info), convert_tracks(tracks)


def retrieve_from_info(info):
    category = info['#category']
    discid = info['#discid']
    return retrieve(category, discid)


def search(tracklist):
    ret = []
    for tracks in split_by_tag(tracklist, 'album', None).values():
        discid = calculate_discid(tracks)
        ret.extend(search_by_id(discid))
    return ret


def search_by_id(discid):
    try:
        stat, discs = CDDB.query(discid, **CLIENTINFO)
    except RetrievalError:
        raise
    except EnvironmentError as e:
        raise RetrievalError(str(e))
    except ValueError:
        raise RetrievalError(translate(
            "FreeDB", "The server's reply isn't a CDDB reply."))
    if stat not in [200, 210, 211]:
        return []
    if discs:
        if hasattr(discs, 'items'):
            discs = [discs]
        return [(convert_info(info), []) for info in discs]
    return []


def split_by_tag(tracks, main='artist', secondary='album'):
    if secondary:
        ret = defaultdict(lambda: defaultdict(lambda: []))
        [ret[to_string(track.get(main))]
         [to_string(track.get(secondary))].append(track) for track in tracks]
    else:
        ret = defaultdict(lambda: [])
        [ret[to_string(track.get(main))].append(track) for track in tracks]
    return ret


_last_request = None


def _wait():
    """Keeps the requests to the server a second apart: it refuses too many
    at once."""
    global _last_request
    if _last_request is not None:
        wait = _last_request + 1 - time.monotonic()
        if wait > 0:
            time.sleep(wait)
    _last_request = time.monotonic()


class FreeDB(object):
    name = 'FreeDB'
    tooltip = translate("FreeDB",
                        '<b>FreeDB does not support text-based searches.</b>')
    group_by = ['album', None]

    def __init__(self):
        object.__init__(self)
        self.__retrieved = {}

    def search(self, album, files):
        if files:
            _wait()
            results = search(files)
            if results:
                results[0] = self.retrieve(results[0][0])
            return results
        else:
            return []

    def retrieve(self, info):
        discid = info['#discid']
        if discid in self.__retrieved:
            return self.__retrieved[discid]
        else:
            _wait()
            info, tracks = retrieve_from_info(info)
            self.__retrieved[info['#discid']] = [info, tracks]
            return info, tracks


info = FreeDB
