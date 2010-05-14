# -*- coding: utf-8 -*-
import sys, pdb
from musicbrainz2.webservice import Query, ArtistFilter, WebServiceError, ConnectionError, ReleaseFilter
import musicbrainz2.webservice as ws
import musicbrainz2.model as brainzmodel
from collections import defaultdict
import cPickle as pickle
from puddlestuff.tagsources import RetrievalError
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

def get_tracks(r_id):
    release = q.getReleaseById(r_id, RELEASEINCLUDES)
    if release:
        artist = release.artist.name
    else:
        artist = ''
    if release.getReleaseEventsAsDict():
        extra = {'date': min(release.getReleaseEventsAsDict().values())}
    else:
        extra = {}
    if release.tracks:
        return [[{#'mbrainz_track_id': track.id,
                'title': track.title,
                'album': release.title,
                'year': release.getEarliestReleaseDate(),
                'mbrainz_album_id': r_id,
                'mbrainz_artist_id': release.artist.id,
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

import cPickle as pickle

class MusicBrainz(object):
    def search(self, audios=None, params=None):
        ret = []
        if not params:
            params = split_by_tag(audios)
        for artist, albums in params.items():
            try:
                print u'Retrieving Artist Info', artist
                artist, artistid = artist_id(artist)
                #artist, artistid = 'Alicia Keys', 'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e'
                print artist, artistid
            except WebServiceError, e:
                raise RetrievalError(unicode(e))
            except ValueError:
                print u'%s not found.' % artist
                continue
            try:
                print u'Getting Releases', artist
                #releases = [{'album': u"You Don't Know My Name", '#albumid': u'http://musicbrainz.org/release/3a92f107-4f90-419e-bfe9-0425398b26d1', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'Songs in A minor', '#albumid': u'http://musicbrainz.org/release/45b24460-0a35-415e-971d-9f6dd6b93d40', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u"Fallin'", '#albumid': u'http://musicbrainz.org/release/102ae81b-5ddb-454e-8fab-215d6e7c6b9f', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'Songs in A minor', '#albumid': u'http://musicbrainz.org/release/878c19e5-5af4-4be8-84b6-cf08eaa20dd2', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'Songs in A minor', '#albumid': u'http://musicbrainz.org/release/d86ba551-9dc6-421a-a2ab-d27cf1312996', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'Girlfriend', '#albumid': u'http://musicbrainz.org/release/45b88f92-75f3-4035-918e-c618c360cb7c', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'Songs in A minor', '#albumid': u'http://musicbrainz.org/release/da9113f7-3f5a-4b22-ab7b-6c4446dd6da8', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'Remixed & Unplugged', '#albumid': u'http://musicbrainz.org/release/35dd0211-d4df-4b27-9607-39f74af14a12', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u"A Woman's Worth", '#albumid': u'http://musicbrainz.org/release/b661a8c8-8d5c-4ec9-8941-c3b450c527ee', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'Songs in A minor', '#albumid': u'http://musicbrainz.org/release/28ceced0-0d25-4e48-b01d-10ea90eb415f', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u"How Come You Don't Call Me", '#albumid': u'http://musicbrainz.org/release/d940981b-bd47-4f67-b4b6-9cee83fa73fb', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'Maximum Alicia Keys', '#albumid': u'http://musicbrainz.org/release/00eeda39-d787-4228-ac8f-99fa144eaad6', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u"You Don't Know My Name", '#albumid': u'http://musicbrainz.org/release/0a96edb3-dd27-4b73-96e1-69516cf604a5', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'The Diary of Alicia Keys', '#albumid': u'http://musicbrainz.org/release/bd7d51ea-e13f-4be0-bc8b-3cbb266ce62e', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'The Diary of Alicia Keys', '#albumid': u'http://musicbrainz.org/release/f29e08b9-ace8-48da-a0ef-cb84883d63f6', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'The Diary of Alicia Keys (bonus disc)', '#albumid': u'http://musicbrainz.org/release/96c54061-71c6-4229-a8d2-06048a862a19', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u"If I Ain't Got You", '#albumid': u'http://musicbrainz.org/release/d7b02e44-1533-4cc5-830b-3e8c96d528c3', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'The Diary of Alicia Keys (bonus disc)', '#albumid': u'http://musicbrainz.org/release/287a913d-41d8-4e44-bed8-6bc5278bd997', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'Karma', '#albumid': u'http://musicbrainz.org/release/c223d1f7-ea9a-4452-a5c1-1bc13d0358ce', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'Unplugged', '#albumid': u'http://musicbrainz.org/release/905f63c8-fac6-4b82-ad99-e3163cffcfda', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'No One', '#albumid': u'http://musicbrainz.org/release/e114eea8-c679-44ce-a271-a29fbe362f8d', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'No One (Curtis Lynch Reggae remix)', '#albumid': u'http://musicbrainz.org/release/e26747fa-0182-4fc6-a8c2-8326241adb25', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'No One', '#albumid': u'http://musicbrainz.org/release/be952bce-141d-4eb7-8f32-e75a4df3f4f4', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'As I Am', '#albumid': u'http://musicbrainz.org/release/7be7a27d-6be7-47c7-a5f4-fcc6d58dc9b0', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'As I Am (disc 1)', '#albumid': u'http://musicbrainz.org/release/f6699616-9abc-42c9-a629-3a33fa39be45', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'As I Am (disc 2)', '#albumid': u'http://musicbrainz.org/release/51425e52-2e2f-4a62-9f9f-790e33b8eb89', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'As I Am', '#albumid': u'http://musicbrainz.org/release/823b4f5b-2329-4dca-aee7-fefbc1c49095', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'As I Am', '#albumid': u'http://musicbrainz.org/release/4021e476-038e-4442-b28e-abade23e8b3a', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u"Like You'll Never See Me Again", '#albumid': u'http://musicbrainz.org/release/d5750d50-edbb-445f-a12b-15e045cf36a9', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'Teenage Love Affair', '#albumid': u'http://musicbrainz.org/release/8a138be4-49b4-41db-9259-2b8140db23a2', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'Remixed', '#albumid': u'http://musicbrainz.org/release/d436d8c2-3f5b-41a6-845b-8fc28862d63b', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'As I Am: The Super Edition', '#albumid': u'http://musicbrainz.org/release/8f611175-c7e8-424d-b53b-6946bfd75ae3', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u"Doesn't Mean Anything", '#albumid': u'http://musicbrainz.org/release/560ec37b-e1cd-41eb-bcd7-1b02d33fd631', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'Try Sleeping With a Broken Heart', '#albumid': u'http://musicbrainz.org/release/c491171d-0dc4-417c-8e95-5503263cf17e', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u"Doesn't Mean Anything", '#albumid': u'http://musicbrainz.org/release/4d1ea3c0-07c1-4098-9dc8-7bee4347d463', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'The Element of Freedom', '#albumid': u'http://musicbrainz.org/release/ab07f018-23ea-4285-b4fe-283cc11ee1b2', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'The Element of Freedom', '#albumid': u'http://musicbrainz.org/release/958c5982-7117-481e-9738-8341444962cb', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'The Element of Freedom', '#albumid': u'http://musicbrainz.org/release/7dc181dd-6584-49bf-81c5-4fca8bdd9144', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'The Element of Freedom (bonus disc: Empire EP)', '#albumid': u'http://musicbrainz.org/release/2abe051e-6e5a-4116-8527-bf0fb62a7693', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'The Element of Freedom', '#albumid': u'http://musicbrainz.org/release/314f71ae-8b6c-4d79-becb-2d35142c8cc3', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'The Element of Freedom: Deluxe Edition', '#albumid': u'http://musicbrainz.org/release/0a59a633-e99b-4fc0-b257-cc85d7f5d111', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}, {'album': u'Empire State of Mind, Part II: Broken Down', '#albumid': u'http://musicbrainz.org/release/9e31b4ed-b59e-471c-9bdf-b58560f9fa79', '#artistid': u'http://musicbrainz.org/artist/8ef1df30-ae4f-4dbd-9351-1a32b208a01e', 'artist': u'Alicia Keys'}]
                releases = get_releases(artistid)
                releases = [{'artist': artist,
                            'album': z[0],
                            '#albumid': z[1],
                            '#artistid': artistid} for z in releases]
                print releases
            except WebServiceError, e:
                raise RetrievalError(unicode(e))
            if not releases:
                print u'No albums found for %s.' % artist
                continue
            lowered = [z['album'].lower() for z in releases]
            matched = []
            allmatched = True
            for album in albums:
                if album.lower() in lowered:
                    print 'Getting tracks', artist, album
                    index = lowered.index(album.lower())
                    tracks = get_tracks(releases[index]['#albumid'])
                    ret.append([releases[index], tracks])
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
        return info, get_tracks(r_id)

info = [MusicBrainz, None]
name = 'Musicbrainz'

if __name__ == '__main__':
    from exampletags import tags
    x = MusicBrainz(params = dict([('Linkin Park', 'Minutes To Midnight'), (u"Beyonc\xe9" ,"B'day")]))
    print x.search(tags)
    #pickle.dump(x, open('mbrainz', 'wb'))
    print sorted(retrieve([('Linkin Park', 'Minutes To Midnight'), (u"Beyonc\xe9" ,"B'day")]).items())