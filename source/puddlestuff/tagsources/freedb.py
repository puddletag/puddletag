# -*- coding: utf-8 -*-

import CDDB
CDDB.proto = 6 # utf8 instead of latin1
import os, pdb
from os import path
from gettext import ngettext
from puddlestuff.util import to_string
from collections import defaultdict
from puddlestuff.constants import TAGSOURCE
import puddlestuff.audioinfo as audioinfo
from puddlestuff.tagsources import RetrievalError

CLIENTINFO = {'client_name': "puddletag", 'client_version': '0.9.2' }
#properties = {'type': TAGSOURCE}


def sumdigits(n): return sum(map(long, str(n)))

def calculate_discid(album):
    #from quodlibet's cddb plugin by Michael Urman
    lengths = [audioinfo.lnglength(song.length) for song in album]
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
    for key in info.keys():
        if key in keys:
            info[keys[key]] = info[key]
            del(info[key])
    return info

def convert_tracks(disc):
    return [{'track': unicode(track + 1), 'title': title} for track, title 
        in sorted(disc.items())]

def query(category, discid, xcode='utf8:utf8'):
    #from quodlibet's cddb plugin by Michael Urman
    discinfo = {}
    tracktitles = {}

    read, info = CDDB.read(category, discid, **CLIENTINFO)
    if read != 210: return None

    xf, xt = xcode.split(':')
    for key, value in info.iteritems():
        try: value = value.decode('utf-8', 'replace').strip().encode(
            xf, 'replace').decode(xt, 'replace')
        except AttributeError: pass
        if key.startswith('TTITLE'):
            try: tracktitles[int(key[6:])] = value
            except ValueError: pass
        elif key == 'DGENRE': discinfo['genre'] = value
        elif key == 'DTITLE':
            dtitle = value.strip().split(' / ', 1)
            if len(dtitle) == 2:
                discinfo['artist'], discinfo['title'] = dtitle
            else: discinfo['title'] = dtitle[0].strip()
        elif key == 'DYEAR': discinfo['year'] = value

    return discinfo, tracktitles

def retrieve(category, discid):
    try:
        info, tracks = query(category, discid)
    except EnvironmentError, e:
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
    except EnvironmentError, e:
        raise RetrievalError(e.strerror)
    if stat not in [200, 211]:
        return []
    if stat == 200 or len(discs) == 1:
        info, tracks = retrieve(discs[0]['category'], discs[0]['disc_id'])
        return [(info, tracks)]
    elif discs:
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
    def search(self, audios=None, params=None):
        if audios:
            return search(audios)
        else:
            return []

    def retrieve(self, info):
        return retrieve_from_info(info)

info = [FreeDB, None]
name = 'FreeDB'

if __name__ == '__main__':
    import puddlestuff.audioinfo as audioinfo
    import glob
    import pdb
    files = map(audioinfo.Tag, 
        glob.glob("/mnt/multimedia/Music/Ratatat - Classics/*.mp3"))
    print search(files)