"""Cover art in every format: saved with the two calls an edit in the main
table ends in (update, then save) and read back with mutagen, and read from
covers another program wrote. Synthetic files and images.

tags.txt, "Cover Art": "For ID3 tag cover art, writing multiple pictures
per file is supported, but a different description is required for each.
MP4 tags also support multiple pictures per file, but not setting
descriptions. APEv2 tags can store at most two pictures per file. Moreover,
these pictures need to have different cover types, limited to Cover (front)
and Cover (back). VorbisComment tags support multiple pictures per file with
no limit on the descriptions or cover types." The docs leave out WMA, whose
WM/Picture attribute holds a picture type, MIME type and description for
each picture (Picard's formats/asf.py, pack_image).

A cover is its data, MIME type, description and picture type (ID3's
numbering: 3 is Cover (Front), 4 Cover (Back), 8 Artist). An MP4 cover
holds only the image and its format, JPEG or PNG; an APEv2 one is the
description, a zero byte and the image, under a key naming its type, and
puddletag tells its MIME type from the image.
"""
import base64
import struct

import mutagen
import mutagen.apev2
import mutagen.flac
import mutagen.id3
import mutagen.mp4
import pytest
from mutagen.asf import ASFByteArrayAttribute
from PyQt6.QtCore import QBuffer, QIODevice
from PyQt6.QtGui import QImage

from puddlestuff import audioinfo


def image(form, width):
    """A real image, so that its MIME type can be told from its data; the
    width tells images apart."""
    picture = QImage(width, 1, QImage.Format.Format_RGB32)
    picture.fill(0)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert picture.save(buffer, form)
    return bytes(buffer.data())


FRONT = {'data': image('PNG', 10), 'description': 'Front', 'imagetype': 3, 'mime': 'image/png'}
BACK = {'data': image('JPEG', 20), 'description': 'Back', 'imagetype': 4, 'mime': 'image/jpeg'}
ARTIST = {'data': image('JPEG', 30), 'description': 'Café 封面', 'imagetype': 8, 'mime': 'image/jpeg'}

APEV2 = ['ape', 'mpc', 'wv']
ID3 = ['aiff', 'dff', 'dsf', 'mp3']
VORBIS = ['flac', 'ogg', 'opus']
FORMATS = sorted(APEV2 + ID3 + VORBIS + ['m4a', 'wma'])

APEV2_KEYS = {3: 'Cover Art (Front)', 4: 'Cover Art (Back)'}
MP4_FORMATS = {'image/jpeg': mutagen.mp4.MP4Cover.FORMAT_JPEG, 'image/png': mutagen.mp4.MP4Cover.FORMAT_PNG}


def only(cover, keys):
    return {key: cover[key] for key in keys}


def kept(ext, cover):
    """What the file keeps of a cover."""
    if ext == 'm4a':
        return only(cover, ['data', 'mime'])
    if ext in APEV2:
        return only(cover, ['data', 'description', 'imagetype'])
    return cover


def shown(ext, cover):
    """What puddletag shows of a cover the file keeps."""
    return only(cover, ['data', 'mime']) if ext == 'm4a' else cover


def pack(cover):
    """A WM/Picture value as Picard packs it: the picture type, the data's
    length, the MIME type and the description (UTF-16, each ending in two
    zero bytes), then the data."""
    return (struct.pack('<bi', cover['imagetype'], len(cover['data']))
            + cover['mime'].encode('utf-16-le') + b'\0\0'
            + cover['description'].encode('utf-16-le') + b'\0\0' + cover['data'])


def unpack(value):
    imagetype, size = struct.unpack_from('<bi', value)
    texts, start = [], 5
    for _ in range(2):  # the MIME type and the description, by UTF-16 code units
        end = start
        while value[end:end + 2] != b'\0\0':
            end += 2
        texts.append(value[start:end].decode('utf-16-le'))
        start = end + 2
    return {'data': value[start:start + size], 'description': texts[1], 'imagetype': imagetype,
            'mime': texts[0]}


def picture(cover):
    result = mutagen.flac.Picture()
    result.data, result.desc, result.mime, result.type = (
        cover['data'], cover['description'], cover['mime'], cover['imagetype'])
    return result


def stored(path):
    """The covers the file keeps, as mutagen reads them."""
    ext = path.suffix[1:]
    if ext in APEV2:
        tag = mutagen.apev2.APEv2(str(path))
        covers = []
        for imagetype, key in APEV2_KEYS.items():
            if key in tag:
                description, data = tag[key].value.split(b'\0', 1)
                covers.append({'data': data, 'description': description.decode(), 'imagetype': imagetype})
        return covers
    tags = mutagen.File(str(path)).tags
    if ext == 'm4a':
        mimes = {form: mime for mime, form in MP4_FORMATS.items()}
        return [{'data': bytes(cover), 'mime': mimes[cover.imageformat]} for cover in tags.get('covr', [])]
    if ext == 'wma':
        return [unpack(value.value) for value in tags.get('WM/Picture', [])]
    if ext in ID3:
        pictures = tags.getall('APIC')
    elif ext == 'flac':
        pictures = mutagen.flac.FLAC(str(path)).pictures
    else:
        pictures = [mutagen.flac.Picture(base64.b64decode(value))
                    for value in tags.get('metadata_block_picture', [])]
    return [{'data': p.data, 'description': p.desc, 'imagetype': p.type, 'mime': p.mime} for p in pictures]


def write(path, covers):
    """Save covers as another program would, with mutagen."""
    ext = path.suffix[1:]
    if ext in APEV2:
        tag = mutagen.apev2.APEv2(str(path))
        for cover in covers:
            tag[APEV2_KEYS[cover['imagetype']]] = mutagen.apev2.APEValue(
                cover['description'].encode() + b'\0' + cover['data'], mutagen.apev2.BINARY)
        tag.save(str(path))
        return
    audio = mutagen.File(str(path))
    if ext == 'm4a':
        audio['covr'] = [mutagen.mp4.MP4Cover(cover['data'], MP4_FORMATS[cover['mime']]) for cover in covers]
    elif ext == 'wma':
        audio['WM/Picture'] = [ASFByteArrayAttribute(pack(cover)) for cover in covers]
    elif ext in ID3:
        for cover in covers:
            audio.tags.add(mutagen.id3.APIC(encoding=3, mime=cover['mime'], type=cover['imagetype'],
                                            desc=cover['description'], data=cover['data']))
    elif ext == 'flac':
        for cover in covers:
            audio.add_picture(picture(cover))
    else:
        audio['METADATA_BLOCK_PICTURE'] = [base64.b64encode(picture(cover).write()).decode('ascii')
                                           for cover in covers]
    audio.save()


def save(path, fields):
    tag = audioinfo.Tag(str(path))
    tag.update(fields)
    tag.save()
    return audioinfo.Tag(str(path))


@pytest.mark.parametrize('ext', FORMATS)
def test_cover_saved(make_audio, ext):
    path = make_audio('song.' + ext, title='Song')
    tag = save(path, {'__image': [FRONT]})
    assert stored(path) == [kept(ext, FRONT)]
    assert (tag['__image'], tag['__num_images'], tag['__image_mimetype']) == ([shown(ext, FRONT)], '1', 'image/png')


@pytest.mark.parametrize('ext', FORMATS)
def test_cover_read(make_audio, ext):
    path = make_audio('song.' + ext, title='Song')
    write(path, [FRONT])
    tag = audioinfo.Tag(str(path))
    assert (tag['__image'], tag['__num_images'], tag['__image_mimetype']) == ([shown(ext, FRONT)], '1', 'image/png')


@pytest.mark.parametrize('ext', FORMATS)
def test_image_size(make_audio, ext):
    # tags.txt: "Size in bytes of the first cover image in the file." Read
    # from the file, then after edits, as __num_images follows them.
    path = make_audio('song.' + ext, title='Song')
    write(path, [FRONT])
    tag = audioinfo.Tag(str(path))
    sizes = [tag.get('__image_size')]
    tag.update({'__image': [BACK, FRONT]})
    sizes.append(tag.get('__image_size'))
    tag.update({'__image': []})
    sizes.append(tag.get('__image_size'))
    assert sizes == [str(len(FRONT['data'])), str(len(BACK['data'])), None]


@pytest.mark.parametrize('ext', FORMATS)
def test_covers_kept_when_another_field_is_saved(make_audio, ext):
    path = make_audio('song.' + ext, title='Song')
    write(path, [FRONT, BACK])
    covers = stored(path)
    tag = save(path, {'title': ['Song 2']})
    assert (stored(path), tag['title']) == (covers, ['Song 2'])


@pytest.mark.parametrize('ext', FORMATS)
def test_covers_removed(make_audio, ext):
    # tut3.txt: with <blank> as the picture "artwork will be removed upon
    # saving"; for APEv2, #430: "upon restarting Puddletag the covers are
    # still there".
    path = make_audio('song.' + ext, title='Song')
    write(path, [FRONT, BACK])
    tag = save(path, {'__image': []})
    assert (stored(path), tag['__num_images'], tag['title']) == ([], '0', ['Song'])


@pytest.mark.parametrize('ext', sorted(ID3 + VORBIS + ['wma']))
def test_several_covers(make_audio, ext):
    # Each with its own description, non-ASCII too, and picture type, kept
    # in order: __image_mimetype is the first one's.
    path = make_audio('song.' + ext, title='Song')
    covers = [FRONT, BACK, ARTIST]
    tag = save(path, {'__image': covers})
    assert stored(path) == covers
    assert (tag['__image'], tag['__num_images'], tag['__image_mimetype']) == (covers, '3', 'image/png')


@pytest.mark.parametrize('ext', VORBIS)
def test_covers_with_the_same_description_and_type(make_audio, ext):
    # "no limit on the descriptions or cover types"
    path = make_audio('song.' + ext, title='Song')
    covers = [FRONT, dict(BACK, description=FRONT['description'], imagetype=FRONT['imagetype'])]
    tag = save(path, {'__image': covers})
    assert (stored(path), tag['__image']) == (covers, covers)


def test_mp4_covers_without_descriptions(make_audio):
    path = make_audio('song.m4a', title='Song')
    tag = save(path, {'__image': [FRONT, BACK, ARTIST]})
    covers = [kept('m4a', cover) for cover in (FRONT, BACK, ARTIST)]
    assert (stored(path), tag['__image'], tag['__num_images']) == (covers, covers, '3')


@pytest.mark.parametrize('ext', APEV2)
def test_apev2_front_and_back_covers(make_audio, ext):
    path = make_audio('song.' + ext, title='Song')
    tag = save(path, {'__image': [FRONT, BACK]})
    assert stored(path) == [kept(ext, FRONT), kept(ext, BACK)]
    assert (sorted(tag['__image'], key=lambda cover: cover['imagetype']), tag['__num_images']) == ([FRONT, BACK], '2')


@pytest.mark.parametrize('ext', APEV2)
def test_apev2_pictures_puddletag_does_not_show_are_kept(make_audio, ext):
    # Pictures of other types, as foobar2000 (Artist Picture, Cover Art
    # (Disc)) and Mp3tag from 3.10a (Cover Art (Artist)) write them, per
    # Mp3tag's developer: https://community.mp3tag.de/t/54604
    path = make_audio('song.' + ext, title='Song')
    tag = mutagen.apev2.APEv2(str(path))
    for key in ('Artist Picture', 'Cover Art (Artist)', 'Cover Art (Disc)'):
        tag[key] = mutagen.apev2.APEValue(key.encode() + b'.jpg\0' + ARTIST['data'], mutagen.apev2.BINARY)
    tag.save(str(path))
    save(path, {'title': ['Song 2']})
    binary = {key: value.value for key, value in mutagen.apev2.APEv2(str(path)).items()
              if value.kind == mutagen.apev2.BINARY}
    assert binary == {key: key.encode() + b'.jpg\0' + ARTIST['data']
                      for key in ('Artist Picture', 'Cover Art (Artist)', 'Cover Art (Disc)')}


@pytest.mark.parametrize('ext', ['ogg', 'opus'])
def test_cover_dimensions_are_written(make_audio, ext):
    # #1081 (test_flac.py) asks a FLAC picture block for the image's own
    # width and height; Ogg and Opus keep the same block in a field.
    path = make_audio('song.' + ext, title='Song')
    save(path, {'__image': [FRONT]})
    [value] = mutagen.File(str(path)).tags['metadata_block_picture']
    block = mutagen.flac.Picture(base64.b64decode(value))
    assert (block.width, block.height) == (10, 1)
