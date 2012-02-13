from collections import defaultdict

import acoustid

import puddlestuff.audioinfo as audioinfo
from puddlestuff.tagsources import set_status, write_log
from puddlestuff.translations import translate

RETRIEVE_MSG = translate('AcoustID', "Retrieving data for file %1")

def parse_lookup_result(data):
    """Given a parsed JSON response, generate tuples containing the match
    score, the MusicBrainz recording ID, the title of the recording, and
    the name of the recording's first artist. (If an artist is not
    available, the last item is None.) If the response is incomplete,
    raises a WebServiceError.
    """
    if data['status'] != 'ok':
        raise acoustid.WebServiceError("status: %s" % data['status'])
    if 'results' not in data:
        raise acoustid.WebServiceError("results not included")

    result = data['results'][0]
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

    if 'releases' in 'track':
        rel = track['releases'][0]
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

    return info

class AcoustID(object):
    name = 'AcoustID'
    group_by = ['album', None]
    def search(self, artist, fns=None):

        tracks = []

        for fn in fns:
            
            write_log(RETRIEVE_MSG.arg(audioinfo.decode_fn(fn.filepath)))
            data = acoustid.match("gT8GJxhO", fn.filepath,
                'release recordings', False)

            print data
            track = parse_lookup_result(data)
            if track:
                track['#exact'] = fn
                tracks.append(track)

        albums = defaultdict(lambda: [])
        for t in tracks:
            if t and t.get('album'):
                albums[t['album']].append(t)

        print tracks

        if albums:
            info = albums[max(albums, lambda key: len(info[key]))]

            return [(info, tracks)]
        elif (not albums) and tracks:
            try:
                info = {'artist': tracks[0]['artist']}
                return [(info, tracks)]
            except KeyError:
                pass
        return []


info = AcoustID

if __name__ == '__main__':
    x = AcoustID()
    print parse_lookup_result({u'status': u'ok', u'results': [{u'recordings': [{u'id': u'32f5e92e-291b-4e2c-99b6-a0c0b2f1ab6d'}, {u'artists': [{u'id': u'ce55e49a-32f4-4757-9849-bf04d06d5fcc', u'name': u'T-Pain'}, {u'id': u'f5dfa020-ad69-41cd-b3d4-fd7af0414e94', u'name': u'Wiz Khalifa'}, {u'id': u'6e0c7c0e-cba5-4c2c-a652-38f71ef5785d', u'name': u'Lily Allen'}], u'id': u'b5d2720d-b40d-4400-b63b-19216452aab6', u'title': u"5 O'Clock"}, {u'duration': 280, u'artists': [{u'id': u'ce55e49a-32f4-4757-9849-bf04d06d5fcc', u'name': u'T-Pain'}], u'id': u'fb91dc84-dbed-43d0-ae6c-aecccc6a5cdc', u'title': u"5 O'Clock (feat. Wiz Khalifa & Lily Allen)"}], u'score': 0.936147, u'id': u'2f4ccef3-13b6-467a-bf2c-99cb1f83b696'}]})