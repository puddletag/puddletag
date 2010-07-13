# -*- coding: utf-8 -*-
import sys, pdb, os
from musicbrainz2.webservice import Query, ArtistFilter, WebServiceError, ConnectionError, ReleaseFilter
import musicbrainz2.webservice as ws
import musicbrainz2.model as brainzmodel
from musicbrainz2.utils import extractUuid
from collections import defaultdict
import cPickle as pickle
from puddlestuff.tagsources import RetrievalError, write_log, set_status, parse_searchstring
from puddlestuff.util import split_by_tag
from puddlestuff.constants import TEXT, SAVEDIR
from puddlestuff.puddleobjects import PuddleConfig

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

def get_tracks(r_id, track_field=None):
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
    if artist:
        extra['artist'] = artist
    extra['album'] = release.title

    if release.tracks:
        year = release.getEarliestReleaseDate()
        if year:
            extra.update({'year': year})
        if not track_field:
            return [[{
                'title': track.title,
                'album': release.title,
                'track': unicode(i+1),
                'artist': track.artist.name if track.artist else artist}
                    for i, track in enumerate(release.tracks)], extra]
        else:
            return [[{
                track_field: extractUuid(track.id),
                'title': track.title,
                'album': release.title,
                'track': unicode(i+1),
                'artist': track.artist.name if track.artist else artist}
                    for i, track in enumerate(release.tracks)], extra]
    else:
        return [], extra

def get_releases(artistid, return_name=False):
    artist = q.getArtistById(artistid, ARTIST_INCLUDES)
    if return_name:
        return [(z.title, z.id) for z in artist.releases], artist.name
    else:
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

def find_id(tracks, field=None):
    if not field:
        return
    for track in tracks:
        if field in track:
            value = track[field]
            if isinstance(value, basestring):
                return value
            else:
                return value[0]

def artist_search(artist):
    try:
        set_status(u'Retrieving Artist Info for <b>%s</b>' % artist)
        write_log(u'Retrieving Artist Info for <b>%s</b>' % artist)
        artist, artistid = artist_id(artist)
        return artist, artistid
    except WebServiceError, e:
        write_log('<b>Error:</b> While retrieving %s: %s' % (
                    artist, unicode(e)))
        raise RetrievalError(unicode(e))
    except ValueError:
        return (None, None)

class MusicBrainz(object):
    name = 'MusicBrainz'
    tooltip = "Enter search parameters here. If empty, the selected files are used. <ul><li><b>artist;album</b> searches for a specific album/artist combination.</li> <li>For multiple artist/album combinations separate them with the '|' character. eg. <b>Amy Winehouse;Back To Black|Outkast;Atliens</b>.</li> <li>To list the albums by an artist leave off the album part, but keep the semicolon (eg. <b>Ratatat;</b>). For a album only leave the artist part as in <b>;Resurrection.</li><li>Retrieving all albums by an artist using their MusicBrainz Artist ID is possible by prefacing your search with <b>:a</b> as in <b>:a f59c5520-5f46-4d2c-b2c4-822eabf53419</b> (extraneous spaces around the ID are discarded.)</li><li>In the same way an album can be retrieved using it's MusicBrainz ID by prefacing the search text with <b>:b</b> eg. <b>:b 34bb630-8061-454c-b35d-8f7131f4ff08</b></li></ul>"
    def __init__(self):
        cparser = PuddleConfig()
        cparser.filename = os.path.join(SAVEDIR, 'tagsources.conf')
        self._artist_field = cparser.get('musicbrainz', 'artistfield', '')
        self._album_field = cparser.get('musicbrainz', 'albumfield', '')
        self._track_field = cparser.get('musicbrainz', 'trackfield', '')
        self.preferences = [
            [u'Field to write MusicBrainz Artist ID to (leave empty'
                u' to disable.):', TEXT, self._artist_field],
            [u'Field to write MusicBrainz Album ID to (leave empty'
                u' to disable.):', TEXT, self._album_field],
            [u'Field to write MusicBrainz Track ID to (leave empty'
                u' to disable.):', TEXT, self._track_field]]


    def keyword_search(self, s):
        if s.startswith(u':a'):
            artistid = 'http://musicbrainz.org/artist/' + s[len(':a'):].strip()
            try:
                releases, artist = get_releases(artistid, True)
            except WebServiceError, e:
                write_log('<b>Error:</b> While retrieving %s: %s' % (
                                artistid, unicode(e)))
                raise RetrievalError(unicode(e))
            return [(info, tracks)]
            if releases:
                releases = [{'artist': artist,
                            'album': z[0],
                            '#albumid': z[1],
                            '#artistid': artistid} for z in releases]
                return [(info, []) for info in releases]

        elif s.startswith(':b'):
            r_id = 'http://musicbrainz.org/release/' + s[len(':a'):].strip()
            try:
                tracks, info = get_tracks(r_id)
            except WebServiceError, e:
                write_log('<b>Error:</b> While retrieving %s: %s' % (
                                artistid, unicode(e)))
                raise RetrievalError(unicode(e))
            return [(info, tracks)]
        else:
            return self.search(None, parse_searchstring(s))

    def search(self, audios=None, params=None):
        ret = []
        check_matches = False
        if not params:
            params = split_by_tag(audios)
            check_matches = True
        for artist, albums in params.items():
            all_tracks = None
            if check_matches:
                all_tracks = []
                [all_tracks.extend(z) for z in albums.values()]

            if check_matches and self._artist_field:
                write_log(u'Checking tracks for Artist ID.')
                artist_id = find_id(all_tracks, self._artist_field)
                if not artist_id:
                    write_log(u'No Artist ID found in tracks.')
                else:
                    artist_id = u'http://musicbrainz.org/artist/%s' % artist_id
            else:
                artist_id = None
            if not artist_id:
                artist, artist_id = artist_search(artist)
            if not artist_id:
                write_log(u'No Artist ID found.' % artist)
                set_status(u'No Artist ID found.' % artist)
                continue
            write_log(u'Found Artist ID for %s = "%s"' % (artist, artist_id))
            try:
                set_status(u'Retrieving releases for %s' % artist)
                write_log(u'Retrieving releases for %s' % artist)
                releases = get_releases(artist_id)
                if self._artist_field:
                    releases = [{'artist': artist,
                                'album': z[0],
                                '#albumid': z[1],
                                '#artistid': artist_id} for z in releases]
                    if self._artist_field:
                        v = extractUuid(artist_id)
                        [z.update({self._artist_field: v})
                            for z in releases]
                    if self._album_field:
                        [z.update({self._album_field: extractUuid(z['#albumid'])})
                            for z in releases]
            except WebServiceError, e:
                write_log('<b>Error:</b> While retrieving %s: %s' % (
                            artist_id, unicode(e)))
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
                    tracks, tempinfo = get_tracks(info['#albumid'], 
                        self._track_field)
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
    
    def applyPrefs(self, values):

        self._artist_field = values[0]
        self._album_field = values[1]
        self._track_field = values[2]
        
        self.preferences[0][2] = values[0]
        self.preferences[1][2] = values[1]
        self.preferences[2][2] = values[2]

        cparser = PuddleConfig()
        cparser.filename = os.path.join(SAVEDIR, 'tagsources.conf')
        cparser.set('musicbrainz', 'artistfield', values[0])
        cparser.set('musicbrainz', 'albumfield', values[1])
        cparser.set('musicbrainz', 'trackfield', values[2])

info = [MusicBrainz, None]
name = 'MusicBrainz'

if __name__ == '__main__':
    from exampletags import tags
    x = MusicBrainz(params = dict([('Linkin Park', 'Minutes To Midnight'), (u"Beyonc\xe9" ,"B'day")]))
    print x.search(tags)
    #pickle.dump(x, open('mbrainz', 'wb'))
    print sorted(retrieve([('Linkin Park', 'Minutes To Midnight'), (u"Beyonc\xe9" ,"B'day")]).items())