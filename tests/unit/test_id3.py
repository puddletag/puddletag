"""ID3 tags (puddlestuff/audioinfo/id3.py), saved with the two calls an edit
in the main table ends in (update, then save: puddlestuff/util.py write)
and read back with mutagen."""
import mutagen.id3
import mutagen.mp4
import pytest
from mutagen.id3 import Encoding, PictureType

from puddlestuff import audioinfo
from puddlestuff.audioinfo.util import to_string

# Synthetic image data: a JPEG's start and end markers.
JPEG = b'\xff\xd8\xff\xd9'


def save_images(path, images, v2=3):
    # The reporter of #1057 writes ID3v2.3.
    tag = audioinfo.Tag(str(path))
    tag.update({'__image': images})
    tag.save(v2=v2)
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


def test_cover_description_is_latin1_in_id3v24_too(make_audio):
    # id3.txt: "a cover's description is Latin-1 when it fits". Synthetic
    # description.
    path = make_audio('song.mp3', title='Song')
    [apic] = save_images(path, [{'data': JPEG, 'mime': 'image/jpeg', 'description': 'Café',
                                 'imagetype': PictureType.COVER_FRONT}], v2=4)
    assert (apic.encoding, apic.desc) == (Encoding.LATIN1, 'Café')


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


# id3.txt's frames, written with puddletag and read back with mutagen and
# with puddletag, in every format whose tag is ID3. Synthetic values.

ID3_FORMATS = ['mp3', 'dff']
# Where a format differs from id3.txt, by test.
DIFFERS = {('test_id3v23_frames_saved_as_id3v23', 'dff'):
           'an ID3v2.3 save keeps the ID3v2.4 frame TDRC instead of writing TYER'}


@pytest.fixture(params=ID3_FORMATS)
def id3_file(request, make_audio):
    reason = DIFFERS.get((request.node.originalname, request.param))
    if reason:
        request.node.add_marker(pytest.mark.xfail(strict=True, reason=reason))
    return make_audio('song.' + request.param)


def id3_frames(path, translate=True):
    """The file's ID3 frames as mutagen reads them, wherever its format keeps
    them; translate=False leaves an ID3v2.3 tag as it is in the file."""
    return type(mutagen.File(path))(path, translate=translate).tags


def save(path, fields, v2=4):
    tag = audioinfo.Tag(str(path))
    tag.update(fields)
    tag.save(v2=v2)
    return id3_frames(path), audioinfo.Tag(str(path))


# The text frames that ID3v2.4 has; the ID3v2.3 ones are further down.
TEXT_FRAMES = {
    'album': 'TALB', 'albumartist': 'TPE2', 'albumartistsortorder': 'TSO2', 'albumsortorder': 'TSOA',
    'arranger': 'TPE4', 'artist': 'TPE1', 'audiodelay': 'TDLY', 'audiolength': 'TLEN', 'author': 'TOLY',
    'bpm': 'TBPM', 'composer': 'TCOM', 'conductor': 'TPE3', 'copyright': 'TCOP', 'discnumber': 'TPOS',
    'encodedby': 'TENC', 'encodingsettings': 'TSSE', 'filename': 'TOFN', 'fileowner': 'TOWN',
    'filetype': 'TFLT', 'genre': 'TCON', 'grouping': 'TIT1', 'initialkey': 'TKEY', 'isrc': 'TSRC',
    'itunescompilationflag': 'TCMP', 'itunescomposersortorder': 'TSOC', 'language': 'TLAN',
    'lyricist': 'TEXT', 'mediatype': 'TMED', 'mood': 'TMOO', 'organization': 'TPUB',
    'originalalbum': 'TOAL', 'originalartist': 'TOPE', 'performersortorder': 'TSOP',
    'producednotice': 'TPRO', 'radioowner': 'TRSO', 'radiostationname': 'TRSN', 'setsubtitle': 'TSST',
    'title': 'TIT2', 'titlesortorder': 'TSOT', 'track': 'TRCK', 'version': 'TIT3',
}
# Frames that hold numbers; the others get two values, as "Multiple values
# per field are allowed".
NUMBERS = {'audiodelay': ['5'], 'audiolength': ['205000'], 'bpm': ['120'], 'discnumber': ['1/2'],
           'itunescompilationflag': ['1'], 'track': ['3/12']}


def test_text_frames(id3_file):
    fields = {field: NUMBERS.get(field, [field + ' one', 'Ünïcode two']) for field in TEXT_FRAMES}
    frames, tag = save(id3_file, fields)
    assert {field: frames[frame].text for field, frame in TEXT_FRAMES.items()} == fields
    assert {field: tag[field] for field in TEXT_FRAMES} == fields


def test_time_frames(id3_file):
    # "YYYY-MM-DD HH:MM:SS Or some partial form".
    fields = {'encodingtime': ['2001-02-03 04:05:06'], 'originalreleasetime': ['1999'],
              'releasetime': ['2001-02'], 'taggingtime': ['2001-02-03 04'], 'year': ['2001']}
    frames, tag = save(id3_file, fields)
    time_frames = {'encodingtime': 'TDEN', 'originalreleasetime': 'TDOR', 'releasetime': 'TDRL',
                   'taggingtime': 'TDTG', 'year': 'TDRC'}
    assert {field: [str(t) for t in frames[frame].text] for field, frame in time_frames.items()} == fields
    assert {field: tag[field] for field in time_frames} == fields


ID3V23_ONLY = {'year': ['2001'], 'date': ['0512'], 'time': ['1230'], 'originalyear': ['1999'],
               'recordingdates': ['December 5'], 'audiosize': ['1000']}


def test_id3v23_frames_saved_as_id3v23(id3_file):
    # They're in the file, and read back as id3.txt says: "year, date and
    # time together as year (TDRC, eg. 2001-12-05 12:30:00), originalyear as
    # originalreleasetime (TDOR), and recordingdates and audiosize not at all".
    path = id3_file
    frames, tag = save(path, ID3V23_ONLY, v2=3)
    v23 = id3_frames(path, translate=False)
    assert {f: v23[f].text for f in ('TYER', 'TDAT', 'TIME', 'TORY', 'TRDA', 'TSIZ')} == {
        'TYER': ['2001'], 'TDAT': ['0512'], 'TIME': ['1230'], 'TORY': ['1999'], 'TRDA': ['December 5'],
        'TSIZ': ['1000']}
    assert audioinfo.usertags(tag) == {'year': ['2001-12-05 12:30:00'], 'originalreleasetime': ['1999']}


def test_id3v23_frames_saved_as_id3v24(id3_file):
    # "Saving as ID3v2.4 writes year to TDRC and originalyear to TDOR, and
    # leaves out date, time, recordingdates and audiosize."
    frames, tag = save(id3_file, ID3V23_ONLY)
    assert {f: [str(t) for t in frames[f].text] for f in frames} == {'TDRC': ['2001'], 'TDOR': ['1999']}


@pytest.mark.parametrize('v2, encoding', [(4, Encoding.UTF8), (3, Encoding.UTF16)])
def test_text_encoding(id3_file, v2, encoding):
    # "Text is written as UTF-8 in ID3v2.4 and as UTF-16 in ID3v2.3".
    path = id3_file
    save(path, {'title': ['Ünïcode'], 'comment': ['Ünïcode'], 'mytag': ['Ünïcode']}, v2=v2)
    frames = id3_frames(path, translate=False)
    assert {frame.encoding for frame in (frames['TIT2'], frames.getall('COMM')[0], frames['TXXX:mytag'])} == {
        encoding}


def test_user_defined_text(id3_file):
    # "writing to the field 'mytag' will write to the ID3 tag frame TXXX:mytag".
    frames, tag = save(id3_file, {'mytag': ['one', 'two']})
    assert (frames['TXXX:mytag'].text, tag['mytag']) == (['one', 'two'], ['one', 'two'])


URL_FRAMES = {'wwwartist': 'WOAR', 'wwwcommercialinfo': 'WCOM', 'wwwcopyright': 'WCOP', 'wwwfileinfo': 'WOAF',
              'wwwpayment': 'WPAY', 'wwwpublisher': 'WPUB', 'wwwradio': 'WORS', 'wwwsource': 'WOAS'}


def test_url_frames(id3_file):
    # "only one value per field is allowed (So even if you try to write
    # multiple values, only the first one will get written)", except
    # wwwartist and wwwcommercialinfo: "Each will be written to a different
    # frame".
    fields = {field: [f'http://example.com/{field}/1', f'http://example.com/{field}/2'] for field in URL_FRAMES}
    frames, tag = save(id3_file, fields)
    expected = {field: urls if field in ('wwwartist', 'wwwcommercialinfo') else urls[:1]
                for field, urls in fields.items()}
    assert {field: [f.url for f in frames.getall(frame)] for field, frame in URL_FRAMES.items()} == expected
    assert {field: tag[field] for field in URL_FRAMES} == expected


def test_user_defined_url(id3_file):
    # "from www:homepage homepage will be the description written to the
    # WXXX frame".
    frames, tag = save(id3_file, {'www:homepage': ['http://example.com/']})
    assert (frames['WXXX:homepage'].url, tag['www:homepage']) == ('http://example.com/', ['http://example.com/'])


def test_paired_frames(id3_file):
    # id3.txt's example: items in a pair separated with a colon, pairs with a
    # semicolon.
    people = 'Billy Taylor:Piano;Chester Bennington:Vocals;Ratatat:Instruments'
    frames, tag = save(id3_file, {'involvedpeople': [people], 'musiciancredits': [people]})
    pairs = [['Billy Taylor', 'Piano'], ['Chester Bennington', 'Vocals'], ['Ratatat', 'Instruments']]
    assert (frames['TIPL'].people, frames['TMCL'].people) == (pairs, pairs)
    assert (tag['involvedpeople'], tag['musiciancredits']) == ([people], [people])


def test_playcount(id3_file):
    frames, tag = save(id3_file, {'playcount': ['7']})
    assert (frames['PCNT'].count, tag['playcount']) == (7, ['7'])


@pytest.mark.parametrize('value, count', [
    # id3.txt's example: "an email, rating and playcount separated by a colon"
    ('cpuddle@unregistered.com:12:3', 3),
    # "If playcount isn't found in an existing field it'll be added."
    ('cpuddle@unregistered.com:12', 0),
])
def test_popularimeter(id3_file, value, count):
    frames, tag = save(id3_file, {'popularimeter': [value]})
    [popm] = frames.getall('POPM')
    assert (popm.email, popm.rating, popm.count) == ('cpuddle@unregistered.com', 12, count)
    assert tag['popularimeter'] == [f'cpuddle@unregistered.com:12:{count}']


def test_ufid(id3_file):
    # "shown in puddletag as ufid:owner eg. ufid:musicbrainz.org".
    track_id = '8f3471b5-7e6a-48da-86a9-c1c07a0f47ae'
    frames, tag = save(id3_file, {'ufid:musicbrainz.org': [track_id]})
    assert (frames['UFID:musicbrainz.org'].data, tag['ufid:musicbrainz.org']) == (track_id.encode(), [track_id])


def test_replaygain(id3_file):
    # "rgain:description", values "channel:gain:peak". RVA2 stores the peak
    # in fixed point, so it comes back close to what was written.
    frames, tag = save(id3_file, {'rgain:track': ['1:-6.5:0.5']})
    rva2 = frames['RVA2:track']
    channel, gain, peak = to_string(tag['rgain:track']).split(':')
    assert (rva2.channel, rva2.gain, channel, gain) == (1, -6.5, '1', '-6.5')
    assert rva2.peak == float(peak) == pytest.approx(0.5)


@pytest.mark.parametrize('value, lang, desc, text', [
    ('eng|Description|Some lyrics', 'eng', 'Description', 'Some lyrics'),
    # "If only one '|' is found ... the Language and Lyrics were entered."
    ('eng|Some lyrics', 'eng', '', 'Some lyrics'),
    # "If only text is entered, or the language isn't three letters, the
    # language und (undetermined) will be used."
    ('Some lyrics', 'und', '', 'Some lyrics'),
    ('english|Description|Some lyrics', 'und', 'Description', 'Some lyrics'),
])
def test_unsynced_lyrics(id3_file, value, lang, desc, text):
    frames, tag = save(id3_file, {'unsyncedlyrics': [value]})
    [uslt] = frames.getall('USLT')
    assert (uslt.lang, uslt.desc, uslt.text) == (lang, desc, text)
    assert tag['unsyncedlyrics'] == [f'{lang}|{desc}|{text}']
