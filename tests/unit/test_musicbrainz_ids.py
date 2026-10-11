"""The MusicBrainz ids the tag sources return, in every format, under the
default field mapping: saved where tags.txt says (MusicBrainz Picard's tag
mapping), and read from there, as Picard writes them. Synthetic files and
ids.
"""
import mutagen
import mutagen.apev2
import mutagen.id3
import mutagen.mp4
import pytest

from puddlestuff import audioinfo

FIELDS = {'mbrainz_album_id': ['album-id'], 'mbrainz_artist_id': ['artist-id'], 'mbrainz_track_id': ['track-id']}

# tags.txt's table, as Picard writes the keys. VorbisComment and APEv2 keys
# don't depend on case: Picard writes MUSICBRAINZ_ALBUMID and
# Musicbrainz_Albumid.
KEYS = {
    'APEv2': {'Musicbrainz_Albumid': 'album-id', 'Musicbrainz_Artistid': 'artist-id',
              'musicbrainz_trackid': 'track-id'},
    'ID3': {'TXXX:MusicBrainz Album Id': 'album-id', 'TXXX:MusicBrainz Artist Id': 'artist-id',
            'UFID:http://musicbrainz.org': 'track-id'},
    'MP4': {'----:com.apple.iTunes:MusicBrainz Album Id': 'album-id',
            '----:com.apple.iTunes:MusicBrainz Artist Id': 'artist-id',
            '----:com.apple.iTunes:MusicBrainz Track Id': 'track-id'},
    'VorbisComment': {'MUSICBRAINZ_ALBUMID': 'album-id', 'MUSICBRAINZ_ARTISTID': 'artist-id',
                      'MUSICBRAINZ_TRACKID': 'track-id'},
    'WMA': {'MusicBrainz/Album Id': 'album-id', 'MusicBrainz/Artist Id': 'artist-id',
            'MusicBrainz/Track Id': 'track-id'},
}
FORMATS = [
    ('aiff', 'ID3'),
    ('ape', 'APEv2'),
    ('dff', 'ID3'),
    ('dsf', 'ID3'),
    ('flac', 'VorbisComment'),
    ('m4a', 'MP4'),
    ('mp3', 'ID3'),
    ('mpc', 'APEv2'),
    ('ogg', 'VorbisComment'),
    ('opus', 'VorbisComment'),
    ('wma', 'WMA'),
    ('wv', 'APEv2'),
]


def stored(path, kind):
    """The file's keys and values but the title, the keys in upper case
    where the tag ignores case."""
    if kind == 'APEv2':
        tags = {key.upper(): str(value) for key, value in mutagen.apev2.APEv2(str(path)).items()}
    elif kind == 'VorbisComment':
        tags = {key.upper(): value for key, value in mutagen.File(str(path)).tags}
    elif kind == 'ID3':
        tags = {key: frame.data.decode() if key.startswith('UFID') else frame.text[0]
                for key, frame in mutagen.File(str(path)).tags.items() if key.startswith(('TXXX', 'UFID'))}
    elif kind == 'MP4':
        tags = {key: bytes(value[0]).decode() for key, value in mutagen.File(str(path)).tags.items()
                if key.startswith('----')}
    else:
        tags = {key: str(value[0]) for key, value in mutagen.File(str(path)).tags.items()}
    return {key: value for key, value in tags.items() if key.upper() != 'TITLE'}


def expected(kind):
    if kind in ('APEv2', 'VorbisComment'):
        return {key.upper(): value for key, value in KEYS[kind].items()}
    return KEYS[kind]


def write_as_picard(path, kind):
    if kind == 'APEv2':
        tag = mutagen.apev2.APEv2(str(path))
        tag.update(KEYS[kind])
        tag.save(str(path))
        return
    audio = mutagen.File(str(path))
    for key, value in KEYS[kind].items():
        if key.startswith('TXXX:'):
            audio.tags.add(mutagen.id3.TXXX(encoding=3, desc=key[5:], text=[value]))
        elif key.startswith('UFID:'):
            audio.tags.add(mutagen.id3.UFID(owner=key[5:], data=value.encode()))
        elif key.startswith('----'):
            audio[key] = [mutagen.mp4.MP4FreeForm(value.encode())]
        else:
            audio[key] = [value]
    audio.save()


@pytest.mark.parametrize('ext, kind', FORMATS)
def test_saved_where_picard_saves_them(make_audio, ext, kind):
    path = make_audio('song.' + ext, title='Song')
    tag = audioinfo.Tag(str(path))
    tag.update(FIELDS)
    tag.save()
    assert stored(path, kind) == expected(kind)


@pytest.mark.parametrize('ext, kind', FORMATS)
def test_read_where_picard_saves_them(make_audio, ext, kind):
    # tags.txt: "files tagged by Picard show them under these names".
    path = make_audio('song.' + ext, title='Song')
    write_as_picard(path, kind)
    assert audioinfo.usertags(audioinfo.Tag(str(path))) == dict(FIELDS, title=['Song'])
