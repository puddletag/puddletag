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
from puddlestuff.constants import CHECKBOX, SAVEDIR
from puddlestuff.puddleobjects import PuddleConfig

Release = brainzmodel.Release
RELEASETYPES = (Release.TYPE_OFFICIAL)
try:
    RELEASEINCLUDES = ws.ReleaseIncludes(discs=True, tracks=True, artist=True,
        releaseEvents=True, labels=True, ratings=True, isrcs=True)
except (TypeError, ValueError):
    RELEASEINCLUDES = ws.ReleaseIncludes(discs=True, tracks=True, artist=True,
        releaseEvents=True, labels=True, ratings=True)

ARTIST_INCLUDES = ws.ArtistIncludes(ratings=True,
    releases=[Release.TYPE_OFFICIAL], releaseRelations=True,
    trackRelations=True, artistRelations=True)

ARTIST_ID = 'mbrainz_artist_id'
ALBUM_ID = 'mbrainz_album_id'
PUID = 'musicip_puid'
TRACK_ID = 'mbrainz_track_id'
COUNTRY = 'mbrainz_country'

CONNECTIONERROR = "Could not connect to Musicbrainz server." \
    "(Check your net connection)"
q = Query()

def artist_id(artist, lucene=False):
    if lucene:
        results = q.getArtists(ArtistFilter(query=artist, limit = 1))
    else:
        results = q.getArtists(ArtistFilter(artist, limit = 1))
    if results:
        return (results[0].artist.name, results[0].artist.id)

def retrieve_tracks(release_id, puids=False, track_id=TRACK_ID):
    #f = open('/tmp/mbrainz/release1', 'rb')
    #release = pickle.load(f)
    #f.close()
    release = q.getReleaseById(release_id, RELEASEINCLUDES)
    info = release_to_dict(release)
    #f = open('/tmp/mbrainz/release1', 'wb')
    #pickle.dump(release, f)
    #f.close()

    if release.tracks:
        tracks = []
        for num, track in enumerate(release.tracks):
            track = {
                track_id: extractUuid(track.id),
                'title': track.title,
                'track': unicode(num + 1),
                'artist': track.artist.name if track.artist else None,
                'mbrainz_rating': unicode(track.rating.value) if track.rating.value is not None else None,
                'mbrainz_isrcs': track.isrcs}
            tracks.append(dict((k,v) for k,v in track.items() if v))

        if puids:
            for track in tracks:
                track.update(get_puid(track[TRACK_ID]))
        return info, tracks
    return info, []

def artist_releases(artistid):
    ret = q.getArtistById(artistid, ARTIST_INCLUDES).releases
    #f = open('/tmp/mbrainz/artist', 'wb')
    #pickle.dump(ret, f)
    #f.close()
    #ret = pickle.load(open('/tmp/mbrainz/artist', 'rb'))
    #pdb.set_trace()
    return ret

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

def get_puid(track_id):
    includes = ws.TrackIncludes(puids=True, ratings=True)
    track = q.getTrackById(track_id, includes)
    #track = pickle.load(open('/tmp/mbrainz/' + track_id, 'rb'))
    #f = open('/tmp/mbrainz/' + track_id, 'wb')
    #pickle.dump(track, f)
    #f.close()
    track = {
        'musicip_puid': track.puids,
        'mbrainz_rating': unicode(track.rating.value) if track.rating.value is not None else None}
    return dict((k,v) for k,v in track.items() if v)

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

def find_releases(artists=None, album=None):
    if artists and album and len(artists) > 1:
        ret = VA_search(album)
        if ret:
            return ret

    if artists is not None:
        artist = artists[0]
    else:
        artist = None

    q = Query()
    r_filter = ws.ReleaseFilter(artistName=artist, title=album,
        releaseTypes=(Release.TYPE_OFFICIAL,))

    releases = q.getReleases(filter=r_filter)

    return map(release_to_dict, releases)

def release_to_dict(release):
    if hasattr(release, 'release'):
        r = release.release
    else:
        r = release
    
    album = {
        'artist': r.artist.name if r.artist else None,
        ARTIST_ID: extractUuid(r.artist.id) if r.artist else None,
        'album': r.title,
        ALBUM_ID: extractUuid(r.id),
        '#artist_id': r.artist.id if r.artist else None,
        '#album_id': r.id,
        'asin': r.asin}

    if r.releaseEvents:
        e = r.releaseEvents[0]
        album.update({
            'year': e.date if hasattr(e, 'date') else None,
            COUNTRY: e.country if hasattr(e, 'country') else None,
            'barcode': e.barcode if hasattr(e, 'barcode') else None,
            'label': e.label.name if e.label else None})

    return dict((k,v) for k,v in album.iteritems() if v)

def VA_search(album):
    q = Query()
    r_filter = ws.ReleaseFilter(artistName=artist, title=album,
        releaseTypes=(Release.TYPE_COMPILATION, Release.TYPE_OFFICIAL))

    return map(release_to_dict, q.getReleases(filter=r_filter))

class MusicBrainz(object):
    name = 'MusicBrainz'
    group_by = ['album', 'artist']
    tooltip = """<p>Enter search parameters here. If empty, the selected
        files are used.</p>
        <ul>
        <li>Enter any text to search for an album. Eg. <b>Southernplayalisticadillacmuzik</b></li>
        <li><b>artist;album</b> searches for a
        specific album/artist combination.</li>
        <li>For multiple artist/album combinations separate them with the
        '|' character. eg. <b>Amy Winehouse;Back To Black|Outkast;Atliens</b>.
        </li> <li>To list the albums by an artist leave off the album part,
        but keep the semicolon (eg. <b>Ratatat;</b>).
        For an album only leave the artist part as in <b>;Resurrection.</li>
        <li>Retrieving all albums by an artist using their MusicBrainz
        Artist ID is possible by prefacing your search with
        <b>:a</b> as in <b>:a f59c5520-5f46-4d2c-b2c4-822eabf53419</b>
        (extra spaces around the ID are discarded.)</li>
        <li>In the same way an album can be retrieved using it's
        MusicBrainz ID by prefacing the search text with
        <b>:b</b> eg. <b>:b 34bb630-8061-454c-b35d-8f7131f4ff08</b></li></ul>"""
    def __init__(self):
        super(MusicBrainz, self).__init__()
        self._puids = False

        self.preferences = [
                ['Retrieve PUID (Requires a lookup for each track)',
                    CHECKBOX, self._puids]]

    def keyword_search(self, s):
        if s.startswith(u':a'):
            artist_id = s[len(':a'):].strip()
            try:
                return [(release_to_dict(r), []) for r in artist_releases(artist_id)]
            except WebServiceError, e:
                write_log('<b>Error:</b> While retrieving %s: %s' % (
                    artistid, unicode(e)))
                raise RetrievalError(unicode(e))

        elif s.startswith(u':b'):
            r_id = s[len(u':b'):].strip()
            try:
                return [retrieve_tracks(r_id)]
            except WebServiceError, e:
                write_log("<b>Error:</b> While retrieving Album ID %s (%s)" % (
                    r_id, unicode(e)))
                raise RetrievalError(unicode(e))
        else:
            try:
                params = parse_searchstring(s)
            except RetrievalError:
                return [(info, []) for info in find_releases(None, s)]
            if not params: 
                return
            artist = params[0][0]
            album = params[0][1]
            return self.search(album, [artist])

    def search(self, album, artists):
        ret = []
        if hasattr(artists, 'values'):
            write_log(u'Checking tracks for MusicBrainz Album ID.')
            tracks = []
            [tracks.extend(z) for z in artists.values()]
            album_id = find_id(tracks, ALBUM_ID)
            if not album_id:
                write_log(u'No Album ID found in tracks.')
            else:
                write_log(u'Found Album ID: %s' % album_id)
                try:
                    return [retrieve_tracks(album_id)]
                except WebServiceError, e:
                    write_log('<b>Error:</b> While retrieving %s: %s' % (
                        artist_id, unicode(e)))
                    raise RetrievalError(unicode(e))

        write_log(u'Searching for album: %s ' % album)
        try:
            return [(info, []) for info in find_releases(artists, album)]
        except WebServiceError, e:
            write_log('<b>Error:</b> While retrieving %s: %s' % (
                artist_id, unicode(e)))
            raise RetrievalError(unicode(e))

    def retrieve(self, info):
        return retrieve_tracks(info['#album_id'], self._puids)

    def applyPrefs(self, value):
        self._puids = value[0]

info = MusicBrainz

if __name__ == '__main__':
    #import pickle
    #releases = pickle.load(open('/tmp/mbrainz/releases', 'rb'))
    #print map(release_to_dict, releases)
    x = find_releases(['Ratatat'], 'Classics')
    print retrieve_tracks(x[0][ALBUM_ID], True)