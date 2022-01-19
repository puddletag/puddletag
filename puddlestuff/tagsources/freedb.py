from . import CDDB

CDDB.proto = 6  # utf8 instead of latin1
from ..util import to_string
from collections import defaultdict
from ..tagsources import RetrievalError
from .. import version_string
from .. import audioinfo
from ..util import translate
import time

CLIENTINFO = {'client_name': "puddletag",
              'client_version': version_string}


def sumdigits(n): return sum(map(int, str(n)))


def sort_func(key, default):
    def func(audio):
        track = to_string(audio.get(key, [default]))
        try:
            return int(track)
        except:
            return track

    return func


def calculate_discid(album):
    # from quodlibet's cddb plugin by Michael Urman
    album = sorted(album, key=sort_func('__filename', ''))
    album = sorted(album, key=sort_func('track', '1'))
    lengths = [audioinfo.lnglength(to_string(song['__length']))
               for song in album]
    total_time = 0
    offsets = []
    for length in lengths:
        offsets.append(total_time)
        total_time += length
    checksum = sum(map(sumdigits, offsets))
    discid = ((checksum % 0xff) << 24) | (total_time << 8) | len(album)
    return [discid, len(album)] + [75 * o for o in offsets] + [total_time]


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


def query(category, discid, xcode='utf8:utf8'):
    # from quodlibet's cddb plugin by Michael Urman
    discinfo = {}
    tracktitles = {}

    read, info = CDDB.read(category, discid, **CLIENTINFO)
    if read != 210: return None

    xf, xt = xcode.split(':')
    for key, value in info.items():
        try:
            value = value.decode('utf-8', 'replace').strip().encode(
                xf, 'replace').decode(xt, 'replace')
        except AttributeError:
            pass
        if key.startswith('TTITLE'):
            try:
                tracktitles[int(key[6:])] = value
            except ValueError:
                pass
        elif key == 'DGENRE':
            discinfo['genre'] = value
        elif key == 'DTITLE':
            dtitle = value.strip().split(' / ', 1)
            if len(dtitle) == 2:
                discinfo['artist'], discinfo['title'] = dtitle
            else:
                discinfo['title'] = dtitle[0].strip()
        elif key == 'DYEAR':
            discinfo['year'] = value

    return discinfo, tracktitles


def retrieve(category, discid):
    try:
        info, tracks = query(category, discid)
    except EnvironmentError as e:
        raise RetrievalError(e.strerror)
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
    except EnvironmentError as e:
        raise RetrievalError(e.strerror)
    if stat not in [200, 211]:
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


class FreeDB(object):
    name = 'FreeDB'
    tooltip = translate("FreeDB",
                        '<b>FreeDB does not support text-based searches.</b>')
    group_by = ['album', None]

    def __init__(self):
        object.__init__(self)
        self.__retrieved = {}
        self.__lasttime = time.time()

    def search(self, album, files):
        if time.time() - self.__lasttime < 1000:
            time.sleep(1)
        if files:
            results = search(files)
            self.__lasttime = time.time()
            if results:
                results[0] = self.retrieve(results[0][0])
            return results
        else:
            return []

    def retrieve(self, info):
        if time.time() - self.__lasttime < 1000:
            time.sleep(1)
        discid = info['#discid']
        if discid in self.__retrieved:
            return self.__retrieved[discid]
        else:
            info, tracks = retrieve_from_info(info)
            self.__retrieved[info['#discid']] = [info, tracks]
            return info, tracks

        return info


info = FreeDB

if __name__ == '__main__':
    # return [({'#discid': '0200d001', '#category': 'soundtrack', 'album': 'German'}, [])]
    from .. import audioinfo
    import glob

    files = list(map(audioinfo.Tag,
                     glob.glob("/mnt/multimedia/Music/Ratatat - Classics/*.mp3")))
    print(search(files))
