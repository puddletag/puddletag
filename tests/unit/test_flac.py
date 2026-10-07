"""FLAC tags (puddlestuff/audioinfo/vorbis.py), saved with the two calls an
edit in the main table ends in (update, then save: puddlestuff/util.py
write) and read back with mutagen."""
import mutagen.flac
from PyQt6.QtCore import QBuffer, QIODevice
from PyQt6.QtGui import QImage

from puddlestuff import audioinfo


def jpeg(width, height):
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(0)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, 'JPEG')
    return bytes(buffer.data())


def test_cover_dimensions_are_written(make_audio):
    # #1081: a 1024 x 1024 JPEG attached to a FLAC file got width and height
    # 0 in its PICTURE block (metaflac --list); expected its actual size.
    # Synthetic file and image, at the report's size.
    path = make_audio('song.flac', title='Song')
    tag = audioinfo.Tag(str(path))
    tag.update({'__image': [{'data': jpeg(1024, 1024), 'mime': 'image/jpeg', 'imagetype': 3}]})
    tag.save()

    [picture] = mutagen.flac.FLAC(path).pictures
    assert (picture.width, picture.height) == (1024, 1024)
