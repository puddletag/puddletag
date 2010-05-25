# -*- coding: utf-8 -*-
import sys, pdb
from musicbrainz2.webservice import Query, ArtistFilter, WebServiceError, ConnectionError, ReleaseFilter
import musicbrainz2.webservice as ws
import musicbrainz2.model as brainzmodel
from collections import defaultdict
import cPickle as pickle
from puddlestuff.tagsources import RetrievalError, write_log, set_status
from puddlestuff.util import split_by_tag

RELEASETYPES = (brainzmodel.Release.TYPE_OFFICIAL)
RELEASEINCLUDES = ws.ReleaseIncludes(discs=True, tracks=True, artist=True,
                                        releaseEvents=True)
ARTIST_INCLUDES = ws.ArtistIncludes(releases=[brainzmodel.Release.TYPE_OFFICIAL])

CONNECTIONERROR = "Could not connect to Musicbrainz server." \
                  "(Check your net connection)"
q = Query()

def artist_id(artist):
    results = q.getArtists(ArtistFilter(artist, limit = 1))
    if results:
        return (results[0].artist.name, results[0].artist.id)

def equal(audio1, audio2, play=False, tags=('artist', 'album')):
    for key in tags:
        if (key in audio1) and (key in audio2):
            if u''.join(audio1[key]).lower() != u''.join(audio2[key]).lower():
                return False
        else:
            return False
    return True

def get_tracks(r_id):
    release = q.getReleaseById(r_id, RELEASEINCLUDES)
    if release:
        artist = release.artist.name
    else:
        artist = ''
    if release.getReleaseEventsAsDict():
        extra = {'date': min(release.getReleaseEventsAsDict().values())}
        if not extra['date']:
            del(extra['date'])
    else:
        extra = {}
    if release.tracks:
        year = release.getEarliestReleaseDate()
        if year:
            return [[{#'mbrainz_track_id': track.id,
                'title': track.title,
                'album': release.title,
                'year': year,
                #'mbrainz_album_id': r_id,
                #'mbrainz_artist_id': release.artist.id,
                'track': unicode(i+1),
                'artist': track.artist.name if track.artist else artist}
                    for i, track in enumerate(release.tracks)], extra]
        else:
            return [[{#'mbrainz_track_id': track.id,
                    'title': track.title,
                    'album': release.title,
                    #'mbrainz_album_id': r_id,
                    #'mbrainz_artist_id': release.artist.id,
                    'track': unicode(i+1),
                    'artist': track.artist.name if track.artist else artist}
                        for i, track in enumerate(release.tracks)], extra]
    else:
        return [], extra

def get_releases(artistid):
    artist = q.getArtistById(artistid, ARTIST_INCLUDES)
    return [(z.title, z.id) for z in artist.releases]

def get_all_releases(title):
    tmp = ReleaseFilter(releaseTypes=RELEASETYPES,title=title)
    releases = q.getReleases(filter=tmp)
    artists = defaultdict(lambda: {})
    albums = defaultdict(lambda:{})
    albumlist = defaultdict(lambda:[])
    for release in releases:
        r = release.release
        artists[r.artist.name] = (r.artist.name, r.artist.id)
        albums[r.artist.id][r.title] = r.id
        albumlist[r.artist.name].append((r.title, []))
    return artists, albums, albumlist

class MusicBrainz(object):
    name = 'Musicbrainz'
    def search(self, audios=None, params=None):
        ret = []
        check_matches = False
        if not params:
            params = split_by_tag(audios)
            check_matches = True
        for artist, albums in params.items():
            try:
                set_status(u'Retrieving Artist Info for <b>%s</b>' % artist)
                write_log(u'Retrieving Artist Info for <b>%s</b>' % artist)
                artist, artistid = artist_id(artist)
                #pickle.dump([artist, artistid], open('artistid', 'wb'))
                #artist, artistid = pickle.load(open('artistid', 'rb'))
                write_log(u'ArtistID for %s = "%s"' % (artist, artistid))
            except WebServiceError, e:
                write_log('<b>Error:</b> While retrieving %s: %s' % (
                            artist, unicode(e)))
                raise RetrievalError(unicode(e))
            except ValueError:
                set_status(u'Artist %s not found.' % artist)
                write_log(u'Artist %s not found.' % artist)
                continue
            try:
                set_status(u'Retrieving releases for %s' % artist)
                write_log(u'Retrieving releases for %s' % artist)
                releases = get_releases(artistid)
                #releases = pickle.load(open('releases', 'rb'))
                #pickle.dump(releases, open('releases', 'wb'))
                releases = [{'artist': artist,
                            'album': z[0],
                            '#albumid': z[1],
                            '#artistid': artistid} for z in releases]
            except WebServiceError, e:
                write_log('<b>Error:</b> While retrieving %s: %s' % (
                            artistid, unicode(e)))
                raise RetrievalError(unicode(e))
            if not releases:
                set_status(u'No albums found for %s.' % artist)
                write_log(u'No releases found for %s.' % artist)
                continue
            else:
                write_log(u"MusicBrainz ID's for %s releases \n%s" % (artist,
                    u'\n'.join([u'%s - %s' % (z['album'], z['#albumid']) 
                    for z in releases])))
                set_status(u'Releases found for %s' % artist)
            lowered = [z['album'].lower() for z in releases]
            matched = []
            allmatched = True
            for album in albums:
                if album.lower() in lowered:
                    index = lowered.index(album.lower())
                    info = releases[index]
                    set_status('Retrieving tracks for %s - %s' % (artist, album))
                    write_log('Retrieving %s - %s: %s' % (artist, album, info['#albumid']))
                    tracks, tempinfo = get_tracks(info['#albumid'])
                    #pickle.dump([tracks, tempinfo], open('tracks', 'wb'))
                    #tracks, tempinfo = pickle.load(open('tracks', 'rb'))
                    info.update(tempinfo)
                    if check_matches:
                        for audio in albums[album]:
                            for track in tracks:
                                if equal(audio, track,  tags=['title']):
                                    track['#exact'] = audio
                                    continue
                    ret.append([info, tracks])
                    matched.append(index)                    
                else:
                    allmatched = False
            if not allmatched:
                [ret.append([info, []]) for i, info in enumerate(releases)
                    if i not in matched]
        return ret

    def retrieve(self, info):
        a_id = info['#artistid']
        r_id = info['#albumid']
        return info, get_tracks(r_id)[0]

info = [MusicBrainz, None]
name = 'Musicbrainz'

if __name__ == '__main__':
    from exampletags import tags
    x = MusicBrainz(params = dict([('Linkin Park', 'Minutes To Midnight'), (u"Beyonc\xe9" ,"B'day")]))
    print x.search(tags)
    #pickle.dump(x, open('mbrainz', 'wb'))
    print sorted(retrieve([('Linkin Park', 'Minutes To Midnight'), (u"Beyonc\xe9" ,"B'day")]).items())