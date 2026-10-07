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


def jpeg(size):
    """Synthetic image data of a given size, to tell images apart."""
    return JPEG[:2] + b'\0' * (size - len(JPEG)) + JPEG[2:]


def test_covers_keep_their_order(make_audio):
    # tags.txt: __image_mimetype and __image_size describe "the first cover
    # image in the file". mutagen before 1.48 sorted covers by size when
    # saving (its bug 436). Synthetic images, the first one the larger.
    path = make_audio('song.mp3', title='Song')
    save_images(path, [
        {'data': jpeg(100), 'mime': 'image/jpeg', 'description': 'Front', 'imagetype': PictureType.COVER_FRONT},
        {'data': jpeg(10), 'mime': 'image/jpeg', 'description': 'Back', 'imagetype': PictureType.COVER_BACK}])
    assert [image['description'] for image in audioinfo.Tag(str(path)).images] == ['Front', 'Back']


def test_covers_with_the_same_description_are_all_saved(make_audio):
    # tags.txt: ID3 needs a different description for each cover; two left
    # without one must still both be saved. Synthetic images.
    path = make_audio('song.mp3', title='Song')
    data = [jpeg(10), jpeg(20)]
    save_images(path, [{'data': d, 'mime': 'image/jpeg', 'description': '',
                        'imagetype': PictureType.COVER_FRONT} for d in data])
    assert [image['data'] for image in audioinfo.Tag(str(path)).images] == data


def test_comments_are_saved_once(make_audio):
    # id3.txt: "comment" is the COMM frame without a description, and
    # "comment:numbertwo" the one with description numbertwo. mutagen 1.48.0
    # duplicated COMM frames on save (reverted in 1.48.1). Saved twice;
    # synthetic comments.
    path = make_audio('song.mp3', title='Song')
    for changes in ({'comment': ['Plain'], 'comment:numbertwo': ['Second']}, {'title': ['Song 2']}):
        tag = audioinfo.Tag(str(path))
        tag.update(changes)
        tag.save()
    comments = mutagen.id3.ID3(path).getall('COMM')
    assert sorted((frame.desc, frame.text) for frame in comments) == [('', ['Plain']), ('numbertwo', ['Second'])]


def id3v1(path):
    with open(path, 'rb') as f:
        f.seek(-128, 2)
        return f.read()


def test_id3v1_holds_the_track(make_audio):
    # puddletag writes an ID3v1.1 tag next to ID3v2 by default
    # (preferences.txt; "Create an ID3v1 tag if it's not present"): its
    # comment field ends with a zero byte and the track number. Synthetic
    # tags.
    path = make_audio('song.mp3', title='Song')
    tag = audioinfo.Tag(str(path))
    tag.update({'track': ['5']})
    tag.save()
    v1 = id3v1(path)
    assert (v1[:3], v1[3:33].rstrip(b'\0'), v1[125], v1[126]) == (b'TAG', b'Song', 0, 5)


def test_id3v1_comment_is_not_a_track(make_audio):
    # #1013: a file with an ID3v1.0 tag whose comment fills its 30
    # characters showed track 63: the comment's last character, "?", read as
    # an ID3v1.1 track number (mutagen bug 668, fixed in 1.48.0). The
    # reporter's tags; their ID3v2 tag had no track either.
    path = make_audio('On.mp3', artist='Aphex Twin', title='On', album='On', date='2024')
    fields = [('On', 30), ('Aphex Twin', 30), ('On', 30), ('2024', 4), ('https://www.youtube.com/watch?', 30)]
    with open(path, 'ab') as f:
        f.write(b'TAG' + b''.join(text.encode('latin1').ljust(size, b'\0') for text, size in fields) + b'\xff')
    tag = audioinfo.Tag(str(path))
    assert 'track' not in tag
    # id3.txt: a comment with a description shows as comment:<description>;
    # mutagen describes the ID3v1 comment as "ID3v1 Comment".
    assert tag['comment:ID3v1 Comment'] == ['https://www.youtube.com/watch?']
