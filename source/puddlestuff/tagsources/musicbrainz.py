# -*- coding: utf-8 -*-
from collections import defaultdict
import socket

import musicbrainz2

import musicbrainz2.webservice as ws
import musicbrainz2.model as brainzmodel

from musicbrainz2.utils import extractUuid
from musicbrainz2.webservice import (ArtistFilter, Query, ReleaseFilter,
    WebServiceError)

import puddlestuff

from puddlestuff.constants import CHECKBOX
from puddlestuff.audioinfo import strlength
from puddlestuff.tagsources import (parse_searchstring, set_status,
    write_log, RetrievalError)
from puddlestuff.tagsources.discogs import find_id
from puddlestuff.util import escape_html, translate

old_version = False

Release = brainzmodel.Release
RELEASETYPES = (Release.TYPE_OFFICIAL)
ARTIST_ID = 'mbrainz_artist_id'
ALBUM_ID = 'mbrainz_album_id'
PUID = 'musicip_puid'
TRACK_ID = 'mbrainz_track_id'
COUNTRY = 'mbrainz_country'
SITE_ALBUM_URL = 'http://musicbrainz.org/release/'

escape = lambda e: escape_html(unicode(e))

try:
    RELEASEINCLUDES = ws.ReleaseIncludes(discs=True, tracks=True,
        artist=True, releaseEvents=True, labels=True, ratings=True,
        isrcs=True)
except (TypeError):
    RELEASEINCLUDES = ws.ReleaseIncludes(discs=True, tracks=True,
        artist=True, releaseEvents=True, labels=True)
    old_version = True

try:
    ARTIST_INCLUDES = ws.ArtistIncludes(ratings=True,
        releases=[Release.TYPE_OFFICIAL], releaseRelations=True,
        trackRelations=True, artistRelations=True)
except TypeError:
    ARTIST_INCLUDES = ws.ArtistIncludes(
        releases=[Release.TYPE_OFFICIAL], releaseRelations=True,
        trackRelations=True, artistRelations=True)
    old_version = True

if hasattr(musicbrainz2.model, 'Rating'):
    class Rating(musicbrainz2.model.Rating):

        def getValue(self):
            return self._value

        def setValue(self, value):
            try:
                value = float(value)
            except ValueError, e:
                value = None
            self._value = value

        value = property(getValue, setValue, doc='The value of the rating.')

    musicbrainz2.model.Rating = Rating

CONNECTIONERROR = translate('MusicBrainz',
    "Could not connect to MusicBrainz server. Check your net connection.")

q = Query(clientId = 'puddletag/' + puddlestuff.version_string)

def get_artist_id(artist, lucene=False):
    if lucene:
        results = q.getArtists(ArtistFilter(query=artist, limit = 1))
    else:
        results = q.getArtists(ArtistFilter(artist, limit = 1))
    if results:
        return (results[0].artist.name, results[0].artist.id)

def artist_releases(artistid):
    ret = q.getArtistById(artistid, ARTIST_INCLUDES).releases
    return ret

def artist_search(artist):
    try:
        set_status(translate("MusicBrainz",
            'Retrieving Artist Info for <b>%s</b>') % artist)
        write_log(translate("MusicBrainz",
            'Retrieving Artist Info for <b>%s</b>') % artist)
        artist, artistid = get_artist_id(artist)
        return artist, artistid
    except WebServiceError, e:
        msg = translate("MusicBrainz",
            '<b>Error:</b> While retrieving %1: %2').arg(artist)
        write_log(msg.arg(escape(e)))
        raise RetrievalError(unicode(e))
    except ValueError:
        return (None, None)

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
    if not old_version:
        includes = ws.TrackIncludes(puids=True, ratings=True)
    else:
        includes = ws.TrackIncludes(puids=True)
    track = q.getTrackById(track_id, includes)
    track_dict = {'musicip_puid': track.puids}
    if not old_version:
        track_dict['mbrainz_rating'] = unicode(track.rating.value) if \
            track.rating.value is not None else None
    return dict((k,v) for k,v in track_dict.iteritems() if v)

def find_releases(artists=None, album=None, limit=100, offset=None):
    if artists and album and len(artists) > 1:
        ret = VA_search(album)
        if ret:
            return ret

    if artists is not None:
        artist = artists[0]
    else:
        artist = None

    r_filter = ws.ReleaseFilter(artistName=artist, title=album,
        limit=limit, offset=offset,
        releaseTypes=(Release.TYPE_OFFICIAL,))
    releases = q.getReleases(filter=r_filter)

    return map(release_to_dict, releases)

def retrieve_tracks(release_id, puids=False, track_id=TRACK_ID):
    release = q.getReleaseById(release_id, RELEASEINCLUDES)
    info = release_to_dict(release)

    if not release.tracks:
        return info, []

    tracks = []
    for num, track in enumerate(release.tracks):
        track_dict = {
            track_id: extractUuid(track.id),
            'title': track.title,
            'track': unicode(num + 1),
            'artist': track.artist.name if track.artist else None,
            '__length': strlength(track.duration) if track.duration else None}

        if not old_version:
            track_dict.update({
                'mbrainz_rating': unicode(track.rating.value) if \
                    track.rating.value is not None else None,
                'isrc': track.isrcs if track.isrcs else None})

        tracks.append(dict((k,v) for k,v in track_dict.items() if v))

    if puids:
        for track in tracks:
            track.update(get_puid(track[TRACK_ID]))

    return info, tracks

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

    album['#extrainfo'] = (translate('MusicBrainz',
        '%s at MusicBrainz.org') % album['album'], r.id)

    return dict((k,v) for k,v in album.iteritems() if v)

def VA_search(album):
    r_filter = ws.ReleaseFilter(title=album,
        releaseTypes=(Release.TYPE_COMPILATION, Release.TYPE_OFFICIAL))

    return map(release_to_dict, q.getReleases(filter=r_filter))

class MusicBrainz(object):
    name = 'MusicBrainz'
    group_by = ['album', 'artist']
    tooltip = translate("MusicBrainz", """<p>Enter search parameters here.
        If empty, the selected files are used.</p>
        
        <ul>
        <li>Enter any text to search for an album. Eg.
            <b>Southernplayalisticadillacmuzik</b></li>
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
        <b>:b</b> eg. <b>:b 34bb630-8061-454c-b35d-8f7131f4ff08</b>
        </li></ul>""")
    def __init__(self):
        super(MusicBrainz, self).__init__()
        self._puids = False

        self.preferences = [
            [translate("MusicBrainz",
                'Retrieve PUIDS (Requires a separate lookup for each track.)'),
                CHECKBOX, self._puids]]

    def keyword_search(self, s):
        if s.startswith(u':a'):
            artist_id = s[len(':a'):].strip()
            try:
                return [(release_to_dict(r), []) for r
                    in artist_releases(artist_id)]
            except WebServiceError, e:
                msg = translate("MusicBrainz",
                    '<b>Error:</b> While retrieving %1: %2')

                write_log(msg.arg(artist_id).arg(escape(e)))
                raise RetrievalError(unicode(e))

        elif s.startswith(u':b'):
            r_id = s[len(u':b'):].strip()
            try:
                return [retrieve_tracks(r_id)]
            except WebServiceError, e:
                msg = translate("MusicBrainz",
                    "<b>Error:</b> While retrieving Album ID %1 (%2)")
                write_log(msg.arg(r_id).arg(escape(e)))
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
        if hasattr(artists, 'values'):
            write_log(translate("MusicBrainz",
                'Checking tracks for MusicBrainz Album ID.'))
            tracks = []
            [tracks.extend(z) for z in artists.values()]
            album_id = find_id(tracks, ALBUM_ID)
            if not album_id:
                write_log(translate("MusicBrainz",
                    'No Album ID found in tracks.'))
            else:
                write_log(translate("MusicBrainz",
                    'Found Album ID: %s') % album_id)
                try:
                    return [retrieve_tracks(album_id, self._puids)]
                except WebServiceError, e:
                    msg = translate("MusicBrainz",
                        '<b>Error:</b> While retrieving %1: %2')
                    msg = msg.arg(album_id).arg(escape(e))
                    write_log(msg)
                    raise RetrievalError(unicode(e))

        write_log(translate("MusicBrainz", 'Searching for album: %s') % album)
        try:
            return [(info, []) for info in find_releases(artists, album)]
        except WebServiceError, e:
            msg = translate("MusicBrainz",
                '<b>Error:</b> While retrieving %1: %2')
            write_log(msg.arg(album).arg(escape(e)))
            raise RetrievalError(unicode(e))
        except socket.error, e:
            msg = u'%s (%s)' % (e.strerror, e.errno)
            raise RetrievalError(msg)

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