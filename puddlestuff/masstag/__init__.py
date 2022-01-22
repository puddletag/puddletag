from collections import defaultdict
from copy import deepcopy
from operator import itemgetter

from ..audioinfo import FILENAME
from ..constants import VARIOUS
from ..findfunc import filenametotag
from ..puddleobjects import natsort_case_key, ratio
from ..tagsources import RetrievalError
from ..translations import translate
from ..util import sorted_split_by_field, split_by_field, to_string
from ..webdb import (strip as strip_fields, DEFAULT_REGEXP,
                     apply_regexps)


def set_status(v):
    print(v)


NO_MATCH_OPTIONS = [
    translate('Masstagging', 'Continue'),
    translate('Masstagging', 'Stop')]

SINGLE_MATCH_OPTIONS = [
    translate('Masstagging', 'Combine and continue'),
    translate('Masstagging', 'Replace and continue'),
    translate('Masstagging', 'Combine and stop'),
    translate('Masstagging', 'Replace and stop')]

AMBIGIOUS_MATCH_OPTIONS = [
    translate('Masstagging', 'Use best match'),
    translate('Masstagging', 'Do nothing and continue')]

COMBINE_CONTINUE = 0
REPLACE_CONTINUE = 1
COMBINE_STOP = 2
REPLACE_STOP = 3

CONTINUE = 0
STOP = 1

USE_BEST = 0
DO_NOTHING = 1
RETRY = 2

ALBUM_BOUND = 'album'
TRACK_BOUND = 'track'
PATTERN = 'pattern'
SOURCE_CONFIGS = 'source_configs'
FIELDS = 'fields'
JFDI = 'jfdi'
NAME = 'name'
DESC = 'description'
EXISTING_ONLY = 'field_exists'

DEFAULT_PATTERN = '%artist% - %album%/%track% - %title%'
DEFAULT_NAME = translate('Masstagging', 'Default Profile')

POLLING = translate("Masstagging", '<b>Polling: %s</b>')
MATCH_ARTIST_ALBUM = translate("Masstagging",
                               'Retrieving matching album. <b>%1 - %2</b>')
MATCH_ARTIST = translate("Masstagging",
                         'Retrieving matching album. Artist=<b>%1</b>')
MATCH_ALBUM = translate("Masstagging",
                        'Retrieving matching album. Album=<b>%1</b>')
MATCH_NO_INFO = translate("Masstagging", 'Retrieving matching album.')

SEARCHING_ARTIST_ALBUM = ':insert' + translate("Masstagging",
                                               'Starting search for: <br />artist=<b>%1</b> '
                                               '<br />album=<b>%2</b><br />')
SEARCHING_ARTIST = ':insert' + translate("Masstagging",
                                         'Starting search for: <br />artist=<b>%1</b>'
                                         '<br />album=No album name found.')
SEARCHING_ALBUM = ':insert' + translate("Masstagging",
                                        'Starting search for: <br />album=<b>%1</b>'
                                        '<br />artist=No artist found.')
SEARCHING_NO_INFO = ':insert' + translate("Masstagging",
                                          'No artist or album info found in files. Starting search.')

RESULTS_FOUND = translate("Masstagging", '<b>%d</b> results found.')
NO_RESULTS_FOUND = translate("Masstagging", '<b>No results were found.</b>')
ONE_RESULT_FOUND = translate("Masstagging", '<b>One</b> result found.')

MATCHING_ALBUMS_FOUND = translate("Masstagging",
                                  '<b>%d</b> possibly matching albums found.')
ONE_MATCHING_ALBUM_FOUND = translate("Masstagging",
                                     '<b>One</b> possibly matching album found.')
NO_MATCHES = translate("Masstagging",
                       'No matches found for tag source <b>%s</b>')

RETRIEVING_NEXT = translate("Masstagging",
                            'Previously retrieved result does not match. '
                            'Retrieving next matching album.')

RECHECKING = translate("Masstagging",
                       '<br />Rechecking with results from <b>%s</b>.<br />')

VALID_FOUND = translate("Masstagging",
                        '<br />Valid matches were found for the album.')

NO_VALID_FOUND = translate("Masstagging",
                           '<b>No valid matches were found for the album.</b>')


class MassTagFlag(object):
    def __init__(self):
        self.stop = False
        object.__init__(self)


def brute_force_results(audios, retrieved):
    matched = {}

    audios = sorted(audios, natsort_case_key,
                    lambda f: to_string(f.get('track', f['__filename'])))

    retrieved = sorted(retrieved, natsort_case_key,
                       lambda t: to_string(t.get('track', t.get('title', ''))))

    for audio, result in zip(audios, retrieved):
        matched[audio] = result

    return matched


def check_result(result, audios):
    track_nums = [_f for _f in [to_string(audio.get('track', None)) for audio in audios] if _f]

    if result.tracks is None:
        return True

    if track_nums:
        max_num = 0
        for num in track_nums:
            try:
                num = int(num)
            except (TypeError, ValueError):
                continue
            max_num = num if num > max_num else max_num
        if max_num != 0 and max_num == len(result.tracks):
            return True

    if len(audios) == len(result.tracks):
        return True
    return False


def combine_tracks(track1, track2, repl=None):
    ret = defaultdict(lambda: [])

    for key, value in list(track2.items()) + list(track1.items()):
        if isinstance(value, str):
            if value not in ret[key]:
                ret[key].append(value)
        else:
            for v in value:
                if v not in ret[key]:
                    ret[key].append(v)
    if repl:
        for key in repl:
            if key in track2:
                ret[key] = track2[key]
    if '#exact' in track1:
        ret['#exact'] = track1['#exact']
    elif '#exact' in track2:
        ret['#exact'] = track2['#exact']
    return ret


def fields_from_text(text):
    if not text:
        return []
    return [_f for _f in map(str.strip, text.split(',')) if _f]


def dict_difference(dict1, dict2):
    """Returns a dictonary containing key/value pairs from dict2 where key
    isn't in dict1."""
    temp = {}
    for field in dict2:
        if field not in dict1:
            temp[field] = dict2[field]
    return temp


def find_best(matches, files, minimum=0.7):
    group = split_by_field(files, 'album', 'artist')
    album = list(group.keys())[0]
    artists = list(group[album].keys())
    if len(artists) == 1:
        artist = artists[0]
    else:
        artist = VARIOUS
    d = {'artist': artist, 'album': album}
    scores = {}

    for match in matches:
        if hasattr(match, 'info'):
            info = match.info
        else:
            info = match[0]

        score = min([ratio_compare(d, info, key) for key in d])

        if score in scores:
            score = score + 0.01  # For albums that have same name.
        scores[score] = match
        tracks = match.tracks if hasattr(match, 'tracks') else match[1]
        if tracks and score < minimum:
            if len(tracks) == len(files):
                scores[minimum + 0.01] = match

    if scores:
        return [scores[z] for z in
                sorted(scores, reverse=True) if z >= minimum]
    else:
        return []


def get_artist_album(files):
    tags = split_by_field(files, 'album', 'artist')
    album = list(tags.keys())[0]
    artists = tags[album]
    if len(artists) > 1:
        return VARIOUS, album
    else:
        return list(artists)[0], album


def get_match_str(info):
    artist = album = None
    if info.get('artist'):
        artist = to_string(info['artist'])

    if info.get('album'):
        album = to_string(info['album'])

    if artist and album:
        return MATCH_ARTIST_ALBUM.arg(artist).arg(album)
    elif artist:
        return MATCH_ARTIST.arg(artist)
    elif album:
        return MATCH_ALBUM.arg(album)
    else:
        return MATCH_NO_INFO


get_lower = lambda f, key, default='': to_string(f.get(key, default)).lower()


def ratio_compare(d1, d2, key):
    return ratio(get_lower(d1, key, 'a'), get_lower(d2, key, 'b'))


def match_files(files, tracks, minimum=0.7, keys=None, jfdi=False,
                existing=False, as_index=False):
    if not keys:
        keys = ['artist', 'title']
    if 'track' in keys and len(keys) > 1:
        keys = keys[::]
        keys.remove('track')
    ret = {}
    replace_tracknumbers(files, tracks)
    assigned = {}
    matched = defaultdict(lambda: {})
    b = False

    for f_index, f in enumerate(files):
        scores = {}
        for t_index, track in enumerate(tracks):
            totals = [ratio_compare(f, track, key) for key in keys]
            if not totals:
                continue
            score = min(totals)
            if score > minimum and score not in scores:
                matched[f_index][t_index] = sum(totals)

    def get_best(f_index, t_indexes):
        if not t_indexes:
            return
        items = list(t_indexes.items())
        best_match = max(items, key=itemgetter(1))
        t_i = best_match[0]

        while t_i in assigned:
            try:
                old_match = matched[assigned[t_i]][t_i]
            except KeyError:
                break
            if best_match[1] > old_match:
                old_f_index = assigned[t_i]
                assigned[t_i] = f_index
                get_best(old_f_index, matched[old_f_index])
                return
            else:
                items.remove(best_match)
                if not items:
                    return
                best_match = max(items, key=itemgetter(1))
                t_i = best_match[0]

        assigned[t_i] = f_index

    for f_index, t_indexes in matched.items():
        best_match = max(list(t_indexes.items()), key=itemgetter(1))
        t_index = best_match[0]
        while t_index in assigned:
            prev_matched = assigned[t_index]
            if t_indexes[t_index] > matched[prev_matched][t_index]:
                get_best(prev_matched, matched[prev_matched])
                break
            else:
                del (t_indexes[t_index])
                if not t_indexes:
                    break
                best_match = max(list(t_indexes.items()), key=itemgetter(1))
                t_index = best_match[0]

        if t_indexes:
            assigned[t_index] = f_index

    ret_indexes = {}
    for t_index, f_index in assigned.items():
        try:
            ret[files[f_index].cls] = tracks[t_index]
            ret_indexes[t_index] = files[f_index].cls
        except AttributeError:
            ret[files[f_index]] = tracks[t_index]
            ret_indexes[t_index] = files[f_index]

    for t in tracks:
        if '#exact' in t:
            ret[t['#exact'].cls] = t
            del (t['#exact'])

    if jfdi:
        unmatched_tracks = [t for i, t in enumerate(tracks) if i
                            not in assigned]
        unmatched_files = [f.cls for f in files if f.cls not in ret]
        ret.update(brute_force_results(unmatched_files, unmatched_tracks))

    if existing:
        ret = dict((f, dict_difference(f, r)) for f, r in ret.items())

    if as_index:
        return ret, ret_indexes
    return ret


def merge_track(audio, info):
    track = {}

    for key in info.keys():
        if not key.startswith('#'):
            if isinstance(info[key], str):
                track[key] = info[key]
            else:
                if isinstance(info[key], list):
                    track[key] = info[key][::]
                elif isinstance(info[key], dict):
                    track[key] = info[key]

    for key in audio.keys():
        if not key.startswith('#'):
            if isinstance(audio[key], str):
                track[key] = audio[key]
            else:
                track[key] = audio[key][::]
    if '#exact' in audio:
        track['#exact'] = audio['#exact']
    return track


def merge_tsp_tracks(profiles, files=None):
    ret = []
    to_repl = []
    for tsp in profiles:
        if not tsp.matched:
            continue

        if tsp.result.tracks is None and files is not None:
            info = strip_fields(tsp.result.info, tsp.fields, leave_exact=True)
            tags = [deepcopy(info) for z in files]
        else:
            tags = [strip_fields(t, tsp.fields, leave_exact=True)
                    for t in tsp.result.merged]

        if len(tags) > len(ret):
            ret.extend(tags[len(ret):])
        if tsp.replace_fields:
            to_repl.append([tags, tsp.replace_fields])
        for i, t in enumerate(tags):
            ret[i] = combine_tracks(ret[i], t)

    for tracks, fields in to_repl:
        for repl, track in zip(tracks, ret):
            track.update(strip_fields(repl, fields, leave_exact=True))

    return ret


def masstag(mtp, files=None, flag=None, mtp_error_func=None,
            tsp_error_func=None, print_status=True):
    not_found = []
    found = []

    if files is None:
        files = mtp.files

    if flag is None:
        flag = MassTagFlag()
    elif flag.stop:
        return []

    assert files

    artist, album = get_artist_album(files)

    if artist and album:
        set_status(SEARCHING_ARTIST_ALBUM.arg(artist).arg(album))
    elif artist:
        set_status(SEARCHING_ARTIST.arg(artist))
    elif album:
        set_status(SEARCHING_ALBUM.arg(album))
    else:
        set_status(SEARCHING_NO_INFO)

    mtp.regexps = DEFAULT_REGEXP if not mtp.regexps else mtp.regexps

    for matches, results, tsp in mtp.search(files, errors=mtp_error_func):
        if flag.stop:
            break
        if len(results) > 1:
            set_status(RESULTS_FOUND % len(results))
        elif not results:
            set_status(NO_RESULTS_FOUND)
        else:
            set_status(ONE_RESULT_FOUND)

        if not matches:
            not_found.append(tsp)
            continue

        if len(matches) > 1:
            set_status(MATCHING_ALBUMS_FOUND % len(matches))
        else:
            set_status(ONE_MATCHING_ALBUM_FOUND)

        set_status(get_match_str(matches[0].info))
        result = tsp.retrieve(matches[0], errors=tsp_error_func)

        while not check_result(result, files):
            del (matches[0])
            if matches:
                set_status(RETRIEVING_NEXT)
                set_status(get_match_str(matches[0].info))
                result = tsp.retrieve(matches[0], errors=tsp_error_func)
            else:
                result = None
                break

        if result is None:
            set_status(NO_MATCHES % tsp.tag_source.name)
            not_found.append(tsp)
        else:
            found.append(tsp)

    ret = []

    if not_found and found:
        set_status(RECHECKING % found[0].tag_source.name)
        audios_copy = []
        for t, m in zip(list(map(deepcopy, files)), found[0].result.merged):
            audios_copy.append(combine_tracks(t, m))

        new_mtp = MassTagProfile(translate("Masstagging", 'Rechecking'),
                                 files=audios_copy, profiles=not_found,
                                 album_bound=mtp.album_bound, track_bound=mtp.track_bound,
                                 regexps=mtp.regexps)

        ret = masstag(new_mtp, audios_copy, flag,
                      mtp_error_func, tsp_error_func, False)

    if found:
        if not ret and print_status:
            set_status(VALID_FOUND)
        return [tsp.result for tsp in found] + ret
    else:
        if print_status:
            set_status(NO_VALID_FOUND)
        return []


def replace_tracknumbers(files, tracks):
    if len(files) != len(tracks):
        return

    files = sorted(files, key=lambda f: to_string(f.get('track', f[FILENAME])))
    try:
        tracks = sorted(tracks, key=itemgetter('track'))
        tracks = sorted(tracks, key=itemgetter('discnumber'))
    except KeyError:
        return

    if len(files) == len(tracks):
        discnum = 1
        track_count = 0
        offset = 0
        for f, t in zip(files, tracks):
            track_count += 1
            try:
                new_discnum = to_int(t['discnumber'])
            except (ValueError, TypeError):
                continue
            if new_discnum > discnum:
                offset = track_count - 1
                discnum = new_discnum
            try:
                f_tracknum = to_int(f['track'])
                t_tracknum = to_int(t['track'])
            except (ValueError, TypeError, KeyError):
                continue
            if f_tracknum > t_tracknum:
                f['track'] = [str(f_tracknum - offset)]


def split_files(audios, pattern):
    def copy_audio(f):
        tags = filenametotag(pattern, f['__path'], True)
        audio_copy = deepcopy(f)
        audio_copy.update(dict_difference(audio_copy, tags))
        audio_copy.cls = f
        return audio_copy

    tag_groups = []

    for dirpath, files in sorted_split_by_field(audios, '__dirpath'):
        album_groups = sorted_split_by_field(files, 'album')
        for album, album_files in album_groups:
            tag_groups.append(list(map(copy_audio, album_files)))

    return tag_groups


def to_int(v):
    return int(to_string(v))


class MassTagProfile(object):
    def __init__(self, name=DEFAULT_NAME, desc='', fields=None, files=None,
                 file_pattern=DEFAULT_PATTERN, profiles=None, album_bound=0.50,
                 track_bound=0.80, jfdi=True, leave_existing=False, regexps=''):

        object.__init__(self)

        self.album_bound = album_bound
        self.desc = desc
        self.fields = ['artist', 'title'] if fields is None else fields
        self.file_pattern = file_pattern
        self.files = [] if files is None else files
        self.jfdi = jfdi
        self.leave_existing = leave_existing
        self.name = name
        self.profiles = profiles if profiles is not None else []
        self.regexps = regexps
        self.track_bound = track_bound

    def clear(self):
        for profile in self.profiles:
            profile.clear_results()

    def search(self, files=None, profiles=None, regexps=None, errors=None):
        files = self.files if files is None else files
        profiles = self.profiles if profiles is None else profiles
        regexps = self.regexps if regexps is None else regexps

        assert files
        assert profiles

        self.files = files

        if regexps:
            changed_files = \
                [apply_regexps(f, regexps) for f in files]
            rxp_album = changed_files[0][0]
            changed_files = [z[1] for z in changed_files]

        for profile in profiles:
            profile.clear_results()
            set_status(POLLING % profile.tag_source.name)
            try:
                results = profile.search(files)
                if regexps and rxp_album:
                    profile.clear_results()
                    set_status(translate('Masstagging',
                                         'Retrying search with album name: <b>%s</b>') %
                               rxp_album)
                    rxp_results = profile.search(changed_files)
                    results.extend(rxp_results)
                    profile.clear_results()
                profile.results = results
            except RetrievalError as e:
                if errors is None:
                    raise e
                if errors(e, profile):
                    raise e
                yield [], [], profile
                continue

            if results:
                profile.find_matches(self.album_bound, files)
            profile.files = files
            yield profile.matched, profile.results, profile


class Result(object):
    def __init__(self, info=None, tracks=None, tag_source=None):
        object.__init__(self)

        self.__info = {}
        self.__tracks = []
        self.merged = []
        self.tag_source = tag_source

        self.tracks = tracks if tracks is not None else []
        self.info = {} if info is None else info
        self.track_matched = {}

    def _get_info(self):
        return self.__info

    def _set_info(self, value):
        self.__info = value

        if self.__tracks:
            self.merged = [merge_track(a, value) for a in self.__tracks]
        else:
            self.merged = []

    info = property(_get_info, _set_info)

    def _get_tracks(self):
        return self.__tracks

    def _set_tracks(self, value):
        self.__tracks = value
        self._set_info(self.__info)

    tracks = property(_get_tracks, _set_tracks)

    def retrieve(self, errors=None):
        if self.tag_source:
            try:
                self.info, self.tracks = self.tag_source.retrieve(self.info)
            except RetrievalError as e:
                if errors is None:
                    raise
                if errors(e):
                    raise e
                else:
                    return {}, []
            return self.info, self.tracks
        return {}, []


class TagSourceProfile(object):
    def __init__(self, files=None, tag_source=None, fields=None,
                 if_no_result=CONTINUE, replace_fields=None):

        object.__init__(self)

        self.if_no_result = if_no_result
        self.fields = [] if fields is None else fields
        self.files = [] if files is None else files
        self.group_by = tag_source.group_by if tag_source else None
        self.matched = []
        self.replace_fields = [] if replace_fields is None else replace_fields
        self.result = None
        self.results = []
        self.tag_source = tag_source

    def clear_results(self):
        self.result = None
        self.results = []
        self.matched = []

    def find_matches(self, album_bound, files=None, results=None):
        files = self.files if files is None else files
        results = self.results if results is None else results

        assert files
        assert results

        self.matched = find_best(results, files, album_bound)
        return self.matched

    def retrieve(self, result, errors=None):
        info = result.info if hasattr(result, 'info') else result

        try:
            index = self.results.index(result)
        except ValueError:
            index = None

        try:
            results = self.tag_source.retrieve(info)
            if results is not None:
                self.result = Result(*results)
            else:
                self.result = result
                return self.result
        except RetrievalError as e:
            if errors is None:
                raise
            if errors(e, self):
                raise e
            else:
                self.result = Result({}, [])
        self.result.tag_source = self.tag_source
        if index is not None:
            self.results[index] = self.result
        return self.result

    def search(self, files=None, tag_source=None):
        tag_source = self.tag_source if tag_source is None else tag_source
        files = self.files if files is None else files

        assert hasattr(tag_source, 'search')
        assert files

        files = split_by_field(files, *tag_source.group_by)
        search_value = list(files.keys())[0]
        self.results = [Result(*x) for x in tag_source.search(search_value, files[search_value])]
        for r in self.results:
            r.tag_source = self.tag_source
        return self.results


if __name__ == '__main__':
    from .. import puddletag

    puddletag.load_plugins()
    from ..tagsources import tagsources

    sources = dict((t.name, t) for t in tagsources)
    source = sources['Local TSource Plugin']()
    source.applyPrefs(['/mnt/multimedia/testlib'])
    print(source._dirs)
