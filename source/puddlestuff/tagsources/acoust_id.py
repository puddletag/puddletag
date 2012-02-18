import pdb

from collections import defaultdict

import acoustid
import audioread

import puddlestuff.audioinfo as audioinfo

from puddlestuff.constants import SPINBOX
from puddlestuff.tagsources import set_status, write_log
from puddlestuff.translations import translate
from puddlestuff.util import isempty

RETRIEVE_MSG = translate('AcoustID', "Retrieving data for file %1")
FP_ERROR_MSG = translate('AcoustID', "Error generating fingerprint: %1")
WEB_ERROR_MSG = translate('AcoustID', "Error retrieving data: %1")

def audio_open(path):
    """Open an audio file using a library that is available on this
    system.
    """
    # Standard-library WAV and AIFF readers.
    from audioread import rawread
    try:
        print 'raw'
        return rawread.RawAudioFile(path)
    except rawread.UnsupportedError:
        pass

    # Core Audio.
    if audioread._ca_available():
        from audioread import macca
        try:
            print 'ca'
            return macca.ExtAudioFile(path)
        except macca.MacError:
            pass

    # GStreamer.
    if audioread._gst_available():
        from audioread import gstdec
        try:
            print 'gst'
            return gstdec.GstAudioFile(path)
        except gstdec.GStreamerError:
            pass

    # MAD.
    if audioread._mad_available():
        from audioread import maddec
        try:
            print 'mad'
            return maddec.MadAudioFile(path)
        except maddec.UnsupportedError:
            pass

    # FFmpeg.
    from audioread import ffdec
    try:
        print 'ff'
        return ffdec.FFmpegAudioFile(path)
    except ffdec.FFmpegError:
        pass

    # All backends failed!
    raise DecodeError()

audioread.audio_open = audio_open
    
def best_album(albums):
    albums = albums[::]
    while albums:
        count = 0
        album = albums[0]
        best_match = [album, 1]
        while album in albums:
            albums.remove(album)
            count + 1
        if count > best_match[1]:
            best_match = (album, count)
    return best_match[0]
            
def parse_release_data(rel):
    info = {}
    info['__numtracks'] = unicode(rel.get('track_count', ''))
    info['album'] = rel.get('title', u'')

    if 'date' in rel:
        date = rel['date']
        info['year'] = u'-'.join(unicode(z).zfill(2) for z in
            map(date.get, ('year', 'month', 'day')) if z)
    info['country'] = rel.get('country', u'')
    info['discs'] = unicode(rel.get('medium_count', ''))
    info['#album_id'] = rel['id']
    info['mbrainz_album_id'] = rel['id']
    if 'mediums' in rel:
        info['track'] = unicode(
            rel['mediums'][0]['tracks'][0].get('position', ""))
    return dict((k,v) for k,v in info.iteritems() if not isempty(v))

def parse_lookup_result(data):
    if data['status'] != 'ok':
        raise acoustid.WebServiceError("status: %s" % data['status'])
    if 'results' not in data:
        raise acoustid.WebServiceError("results not included")

    try:
        result = data['results'][0]
    except IndexError:
        return {}, {}
    info = {}
    info['#score'] = result['score']
    if not result.get('recordings'):
        # No recording attached. This result is not very useful.
        return

    track = max(result['recordings'], key=lambda v: len(v))

    info['title'] = track['title']
    if 'duration' in track:
        info['__length'] = audioinfo.strlength(track['duration'])
    info['acoust_id'] = track['id']

    info['artist'] = track.get('artists', [{'name': u""}])[0]['name']
    if info['artist']:
        info['mbrainz_artist_id'] = track['artists'][0]['id']

    if 'releases' in track:
        album_info = parse_release_data(track['releases'][0])
    else:
        album_info = {}

    info = dict((k,v) for k,v in info.iteritems() if not isempty(v))

    if 'artist' in info and 'artist' not in album_info:
        album_info['artist'] = info['artist']

    if 'track' in album_info:
        info['track'] = album_info['track']
        del(album_info['track'])

    return album_info, info

class AcoustID(object):
    name = 'AcoustID'
    group_by = ['album', None]
    def __init__(self):
        object.__init__(self)
        self.min_score = 0.80
        self.preferences = [['Minimum Score', SPINBOX, [0, 100, 80]]]
        
    def search(self, artist, fns=None):

        tracks = []
        albums = []

        for fn in fns:
            disp_fn = audioinfo.decode_fn(fn.filepath)
            #write_log(RETRIEVE_MSG.arg(disp_fn))
            try:
                data = acoustid.match("gT8GJxhO", fn.filepath,
                    'releases recordings tracks', False)
                album, track = parse_lookup_result(data)
                track.update(album)
            except acoustid.FingerprintGenerationError, e:
                write_log(FP_ERROR_MSG.arg(unicode(e)))
                continue
            except acoustid.WebServiceError, e:
                set_status(WEB_ERROR_MSG.arg(unicode(e)))
                write_log(WEB_ERROR_MSG.arg(unicode(e)))
                break

            
            if track and track['#score'] >= self.min_score:
                track['#exact'] = fn
                tracks.append(track)
                if album:
                    albums.append(album)

        if albums:
            return [(best_album(albums), tracks)]
            
        elif (not albums) and tracks:
            try:
                info = {'artist': tracks[0]['artist']}
                return [(info, tracks)]
            except KeyError:
                pass
        return []

    def applyPrefs(self, args):
        self.min_score = args[0] / 100.0

info = AcoustID

if __name__ == '__main__':
    x = AcoustID()
    print parse_lookup_result({u'status': u'ok', u'results': [{u'recordings': [{u'id': u'32f5e92e-291b-4e2c-99b6-a0c0b2f1ab6d'}, {u'artists': [{u'id': u'ce55e49a-32f4-4757-9849-bf04d06d5fcc', u'name': u'T-Pain'}, {u'id': u'f5dfa020-ad69-41cd-b3d4-fd7af0414e94', u'name': u'Wiz Khalifa'}, {u'id': u'6e0c7c0e-cba5-4c2c-a652-38f71ef5785d', u'name': u'Lily Allen'}], u'id': u'b5d2720d-b40d-4400-b63b-19216452aab6', u'title': u"5 O'Clock"}, {u'duration': 280, u'artists': [{u'id': u'ce55e49a-32f4-4757-9849-bf04d06d5fcc', u'name': u'T-Pain'}], u'id': u'fb91dc84-dbed-43d0-ae6c-aecccc6a5cdc', u'title': u"5 O'Clock (feat. Wiz Khalifa & Lily Allen)"}], u'score': 0.936147, u'id': u'2f4ccef3-13b6-467a-bf2c-99cb1f83b696'}]})