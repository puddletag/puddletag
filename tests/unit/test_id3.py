"""ID3 tags (puddlestuff/audioinfo/id3.py), saved with the two calls an edit
in the main table ends in (update, then save: puddlestuff/util.py write)
and read back with mutagen."""
import mutagen.id3
import mutagen.mp4
import pytest
from mutagen.id3 import Encoding, PictureType

from puddlestuff import audioinfo

# Synthetic image data: a JPEG's start and end markers.
JPEG = b'\xff\xd8\xff\xd9'


def save_images(path, images):
    # The reporter of #1057 writes ID3v2.3.
    tag = audioinfo.Tag(str(path))
    tag.update({'__image': images})
    tag.save(v2=3)
    return mutagen.id3.ID3(path).getall('APIC')


@pytest.mark.parametrize('description', ['', 'Front', 'Café'])
def test_cover_description_is_latin1_when_it_can_be(make_audio, description):
    # #1057: car stereos and Windows didn't show covers puddletag wrote to
    # ID3v2.3; Mp3tag's, readable there, use Latin-1 (encoding 0) for empty
    # and non-empty descriptions alike. Synthetic descriptions.
    path = make_audio('song.mp3', title='Song')
    [apic] = save_images(path, [{'data': JPEG, 'mime': 'image/jpeg', 'description': description,
                                 'imagetype': PictureType.COVER_FRONT}])
    assert (apic.encoding, apic.desc) == (Encoding.LATIN1, description)


def test_cover_description_beyond_latin1_is_unicode(make_audio):
    # ID3v2.3 allows only Latin-1 or Unicode (UTF-16), as quoted in #1057.
    # Synthetic description.
    path = make_audio('song.mp3', title='Song')
    [apic] = save_images(path, [{'data': JPEG, 'mime': 'image/jpeg', 'description': '封面',
                                 'imagetype': PictureType.COVER_FRONT}])
    assert (apic.encoding, apic.desc) == (Encoding.UTF16, '封面')


def test_m4a_cover_becomes_the_front_cover(make_audio):
    # An M4A cover has no picture type; copied to an MP3 it's the front
    # cover. Synthetic files.
    m4a = make_audio('song.m4a', title='Song')
    audio = mutagen.mp4.MP4(m4a)
    audio['covr'] = [mutagen.mp4.MP4Cover(JPEG, imageformat=mutagen.mp4.MP4Cover.FORMAT_JPEG)]
    audio.save()
    images = audioinfo.Tag(str(m4a)).images

    [apic] = save_images(make_audio('song.mp3', title='Song'), images)
    assert apic.type == PictureType.COVER_FRONT
