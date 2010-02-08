#! /usr/bin/env python
#webdb.py

#Copyright (C) 2008-2009 concentricpuddle

#This file is part of puddletag, a semi-good music tag editor.

#This program is free software; you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation; either version 2 of the License, or
#(at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program; if not, write to the Free Software
#Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
import sys, pdb
from musicbrainz2.webservice import Query, ArtistFilter, WebServiceError, ConnectionError, ReleaseFilter
import musicbrainz2.webservice as ws
import musicbrainz2.model as brainzmodel
from collections import defaultdict
import cPickle as pickle
from puddlestuff.tagsources import RetrievalError

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

def get_tracks(r_id):
    release = q.getReleaseById(r_id, RELEASEINCLUDES)
    if release.isSingleArtistRelease():
        artist = release.artist.name
    else:
        artist = None
    if release.getReleaseEventsAsDict():
        extra = {'date': min(release.getReleaseEventsAsDict().values())}
    else:
        extra = {}
    return [[{#'mbrainz_track_id': track.id,
            'title': track.title,
            'album': release.title,
            'year': release.getEarliestReleaseDate(),
            'mbrainz_album_id': r_id,
            'mbrainz_artist_id': release.artist.id,
            'track': unicode(i+1),
            'artist': artist if artist else track.artist.name}
                for i, track in enumerate(release.tracks)], extra]

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

def separate(tags):
    #artist = tags.real('artist')
    #album = tags.real('album')
    artist = 'artist'
    album = 'album'
    ret = defaultdict(lambda:set())
    [ret[tag[artist][0] if artist in tag else ''].add(
            tag[album][0] if album in tag else '') for tag in tags]
    return ret

class MusicBrainz(object):
    def search(self, audios=None, params=None):
        self._artistids = {}
        self._releases = {}
        ret = defaultdict(lambda:{})
        if not params:
            params = separate(audios)
        for artist, albums in params.items():
            if artist:
                try:
                    a_id = artist_id(artist)
                except WebServiceError, e:
                    raise RetrievalError(unicode(e))
                self._artistids[artist] = a_id
                if not a_id:
                    print u'%s not found.' % artist
                    continue
                try:
                    releases = get_releases(a_id[1])
                except WebServiceError, e:
                    raise RetrievalError(unicode(e))
                self._releases[a_id[1]] = dict(releases)
                if not releases:
                    print u'No albums found for %s.' % artist
                    continue
                releasenames = [z[0].lower() for z in releases]
                for album in albums:
                    if album.lower() in releasenames:
                        i = releasenames.index(album.lower())
                        ret[artist][album] = get_tracks(releases[i][1])
                    else:
                        ret[artist][album] = []
                        ret[artist]['__albumlist'] = dict([(z[0],[]) for z in releases])
                        break
            elif albums:
                for album in albums:
                    if album:
                        try:
                            artists, albums, albumlist = get_all_releases(album)
                        except WebServiceError, e:
                            raise RetrievalError(unicode(e))
                        self._artistids.update(artists)
                        self._releases.update(albums)
                        for artist in albumlist:
                            ret[artist]['__albumlist'] = dict(albumlist[artist])
        return ret

    def retrieve(self, artist, album):
        a_id = self._artistids[artist]
        r_id = self._releases[a_id[1]][album]
        return get_tracks(r_id)

if __name__ == '__main__':
    from exampletags import tags
    x = MusicBrainz(params = dict([('Linkin Park', 'Minutes To Midnight'), (u"Beyonc\xe9" ,"B'day")]))
    print x.search(tags)
    #pickle.dump(x, open('mbrainz', 'wb'))
    print sorted(retrieve([('Linkin Park', 'Minutes To Midnight'), (u"Beyonc\xe9" ,"B'day")]).items())