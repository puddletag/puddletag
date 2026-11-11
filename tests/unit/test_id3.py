"""ID3 tags (puddlestuff/audioinfo/id3.py), saved with the two calls an edit
in the main table ends in (update, then save: puddlestuff/util.py write)
and read back with mutagen."""
import mutagen
import mutagen.id3
import mutagen.mp4
import pytest
from mutagen.id3 import CHAP, CTOC, CTOCFlags, Encoding, GEOB, GRP1, MCDI, PRIV, PictureType, SYLT, TIT2

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


def test_id3v1_title_holds_30_characters(make_audio):
    # ID3v1.1 (preferences.txt) has 30 bytes for the title: a longer one is
    # cut there and kept whole in ID3v2. Synthetic title.
    title = 'A Title Longer Than Thirty Characters'
    path = make_audio('song.mp3', title='Song')
    tag = audioinfo.Tag(str(path))
    tag.update({'title': [title]})
    tag.save()
    assert (id3v1(path)[3:33], mutagen.id3.ID3(path)['TIT2'].text) == (title[:30].encode(), [title])


@pytest.mark.parametrize('option, had_id3v1, title', [
    # The Preferences dialog's choices for the ID3v1 tag on saving: "Remove
    # ID3v1 tag.", "Update the ID3v1 tag's values only if an ID3v1 tag is
    # present." and "Create an ID3v1 tag if it's not present. Otherwise
    # update it." (the default). Synthetic tags.
    (0, False, None),
    (0, True, None),
    (1, False, None),
    (1, True, b'Song 2'),
    (2, False, b'Song 2'),
    (2, True, b'Song 2'),
])
def test_id3v1_on_saving(make_audio, monkeypatch, option, had_id3v1, title):
    path = make_audio('song.mp3', title='Song')
    if had_id3v1:
        audioinfo.Tag(str(path)).save(v1=2)
    monkeypatch.setattr(audioinfo.id3, 'v1_option', option)
    tag = audioinfo.Tag(str(path))
    tag.update({'title': ['Song 2']})
    tag.save()
    v1 = id3v1(path)
    assert (v1[3:33].rstrip(b'\0') if v1[:3] == b'TAG' else None) == title


# id3.txt's frames, written with puddletag and read back with mutagen and
# with puddletag, in every format whose tag is ID3. Synthetic values.

ID3_FORMATS = ['aiff', 'dff', 'dsf', 'mp3']


@pytest.fixture(params=ID3_FORMATS)
def id3_file(request, make_audio):
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
    'itunescompilationflag': 'TCMP', 'itunescomposersortorder': 'TSOC', 'itunesgrouping': 'GRP1',
    'language': 'TLAN', 'lyricist': 'TEXT', 'mediatype': 'TMED', 'mood': 'TMOO', 'organization': 'TPUB',
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


@pytest.mark.parametrize('value, stored', [('0', '0'), ('1', '1'), ('No', '0'), ('Yes', '1')])
def test_compilation_flag(id3_file, value, stored):
    # tags.txt: "ID3's itunescompilationflag (TCMP) saves Yes and No as 1
    # and 0 too", as MP4's flags read.
    frames, tag = save(id3_file, {'itunescompilationflag': [value]})
    assert (frames['TCMP'].text, tag['itunescompilationflag']) == ([stored], [stored])


def test_time_frames(id3_file):
    # "YYYY-MM-DD HH:MM:SS Or some partial form".
    fields = {'encodingtime': ['2001-02-03 04:05:06'], 'originalreleasetime': ['1999'],
              'releasetime': ['2001-02'], 'taggingtime': ['2001-02-03 04'], 'year': ['2001']}
    frames, tag = save(id3_file, fields)
    time_frames = {'encodingtime': 'TDEN', 'originalreleasetime': 'TDOR', 'releasetime': 'TDRL',
                   'taggingtime': 'TDTG', 'year': 'TDRC'}
    assert {field: [str(t) for t in frames[frame].text] for field, frame in time_frames.items()} == fields
    assert {field: tag[field] for field in time_frames} == fields


ID3V23_ONLY = {'audiosize': ['1000'], 'date': ['0512'], 'originalyear': ['1999'],
               'recordingdates': ['December 5'], 'time': ['1230'], 'year': ['2001']}


def test_id3v23_frames_saved_as_id3v23(id3_file):
    # They're in the file, and read back as id3.txt says: "year, date and
    # time together as year (TDRC, eg. 2001-12-05 12:30:00), originalyear as
    # originalreleasetime (TDOR), and recordingdates and audiosize not at all".
    path = id3_file
    frames, tag = save(path, ID3V23_ONLY, v2=3)
    v23 = id3_frames(path, translate=False)
    assert {f: v23[f].text for f in ('TDAT', 'TIME', 'TORY', 'TRDA', 'TSIZ', 'TYER')} == {
        'TDAT': ['0512'], 'TIME': ['1230'], 'TORY': ['1999'], 'TRDA': ['December 5'], 'TSIZ': ['1000'],
        'TYER': ['2001']}
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


@pytest.mark.parametrize('year, v2', [(mutagen.id3.TDRC, 4), (mutagen.id3.TYER, 3)])
def test_user_defined_year_next_to_the_year_frame(make_audio, year, v2):
    # #989: editing files bought from Beatport closed puddletag, with
    # "AttributeError: 'str' object has no attribute 'text'" from saving a
    # date frame; their year showed two values, 1998\\1998, and removing one
    # made them save. Synthetic file: the year frame (TYER in ID3v2.3) and a
    # TXXX:YEAR frame. year keeps showing both values, and saving writes them
    # to TDRC, as dates.
    path = make_audio('song.mp3', title='Song')
    tags = mutagen.id3.ID3(path)
    tags.add(year(text=['1998']))
    tags.add(mutagen.id3.TXXX(desc='YEAR', text=['1998']))
    tags.save(v2_version=v2)
    frames, tag = save(path, {'title': ['New']})
    assert frames['TIT2'].text == ['New']
    assert [str(t) for t in frames['TDRC'].text] == ['1998', '1998']
    assert 'TXXX:YEAR' not in frames
    assert tag['year'] == ['1998', '1998']


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


@pytest.mark.parametrize('v2', [3, 4])
def test_saving_again_keeps_one_tag(make_audio, v2):
    # #477 reports each edit stacking another ID3v2 and ID3v1 tag in the
    # file. The docs are silent; synthetic file, titles and cover. Four
    # saves leave one ID3v2 tag at the start, the audio right after it and
    # one ID3v1 tag at the end.
    path = make_audio('song.mp3', title='Song')
    for count in range(4):
        tag = audioinfo.Tag(str(path))
        tag.update({'title': [f'Song {count}'], '__image': [{'data': JPEG, 'mime': 'image/jpeg', 'description': 'Front',
                                                              'imagetype': PictureType.COVER_FRONT}]})
        tag.save(v1=2, v2=v2)
    data = path.read_bytes()
    size = sum(b << shift for b, shift in zip(data[6:10], (21, 14, 7, 0)))  # synchsafe
    assert (data[:4], data.count(b'ID3'), data[10 + size:10 + size + 1], data.count(b'TAG'), data[-128:-125]) == (
        b'ID3' + bytes([v2]), 1, b'\xff', 1, b'TAG')


# Frames id3.txt doesn't list, as other programs write them: a chapter and
# its table of contents, an object, a CD identifier, a private frame and
# synced lyrics. Synthetic values.
UNLISTED = ['CHAP:c1', 'CTOC:toc', 'GEOB:d', 'MCDI', 'PRIV:example.org:private', 'SYLT::eng']


def add_unlisted_frames(path):
    audio = mutagen.File(path)
    audio.tags.add(CHAP(element_id='c1', start_time=0, end_time=500,
                        sub_frames=[TIT2(encoding=Encoding.UTF8, text=['Intro'])]))
    audio.tags.add(CTOC(element_id='toc', flags=CTOCFlags.TOP_LEVEL | CTOCFlags.ORDERED,
                        child_element_ids=['c1'], sub_frames=[]))
    audio.tags.add(GEOB(encoding=Encoding.UTF8, mime='application/octet-stream', filename='a.bin',
                        desc='d', data=b'xyz'))
    audio.tags.add(MCDI(data=b'\x00\x01'))
    audio.tags.add(PRIV(owner='example.org', data=b'private'))
    audio.tags.add(SYLT(encoding=Encoding.UTF8, lang='eng', format=2, type=1, desc='',
                        text=[('la', 0), ('la', 500)]))
    audio.save()


@pytest.mark.parametrize('v2', [3, 4])
@pytest.mark.parametrize('ext', ID3_FORMATS)
def test_save_keeps_frames_puddletag_does_not_list(make_audio, ext, v2):
    # news.txt: "There was a pretty nasty bug where puddletag would remove
    # any unsupported tags. Sorry about that, hopefully you haven't lost any
    # priceless info because of it." The maintainer decided (2026-11-10)
    # that a save keeps the frames puddletag doesn't show. Synthetic frames.
    path = make_audio('song.' + ext, title='Before')
    add_unlisted_frames(path)
    save(path, {'title': ['After']}, v2=v2)
    frames = id3_frames(path, translate=False)
    assert (sorted(frames.keys()), frames['TIT2'].text, frames['CHAP:c1'].sub_frames['TIT2'].text,
            frames.version[:2]) == (sorted(UNLISTED + ['TIT2']), ['After'], ['Intro'], (2, v2))


@pytest.mark.parametrize('ext', ID3_FORMATS)
def test_emptied_field_still_removed(make_audio, ext):
    # tut1.txt: "To remove a field, change the text to <blank> and the field'll
    # be removed upon saving". The maintainer decided (2026-11-10) that only
    # the field goes: the frames puddletag doesn't show stay. Synthetic
    # frames.
    path = make_audio('song.' + ext, title='Before', artist='Artist')
    save(path, {'comment': ['Hi'], 'mine': ['x']})
    add_unlisted_frames(path)
    frames, tag = save(path, {'artist': [], 'comment': [], 'mine': []})
    assert (sorted(frames.keys()), audioinfo.usertags(tag)) == (sorted(UNLISTED + ['TIT2']), {'title': ['Before']})


@pytest.mark.parametrize('ext', ID3_FORMATS)
def test_remove_tag_removes_unlisted_frames(make_audio, ext):
    # menus.txt, Remove Tag: "Removes the tags of selected files." The
    # maintainer decided (2026-11-10) that it still removes everything, the
    # frames puddletag doesn't show included. Synthetic frames.
    path = make_audio('song.' + ext, title='Before')
    add_unlisted_frames(path)
    audioinfo.Tag(str(path)).delete()
    assert not id3_frames(path)


def add_frames(path, *frames):
    """Frames as other programs write them, added with mutagen."""
    audio = mutagen.File(path)
    for frame in frames:
        audio.tags.add(frame)
    audio.save()


def test_paired_frame_item_without_a_role(id3_file):
    # id3.txt, Paired Frames: "Items in a pair are separated with a colon (:),
    # with pairs separated by a semi-colon(;)". A name with no role keeps an
    # empty one. Synthetic names.
    frames, tag = save(id3_file, {'involvedpeople': ['Bob;Ann:Piano']})
    assert frames['TIPL'].people == [['Bob', ''], ['Ann', 'Piano']]
    assert tag['involvedpeople'] == ['Bob:;Ann:Piano']


@pytest.mark.parametrize('ext', ID3_FORMATS)
@pytest.mark.parametrize('field, value', [
    # id3.txt: PCNT "stores the number of times the file has been played".
    ('playcount', 'abc'),
    # POPM: "an email, rating and playcount separated by a colon".
    ('popularimeter', 'a@b:x:1'),
    # RVA2: "Values are of the forme channel:gain:peak". Synthetic values.
    ('rgain:track', 'x'),
])
def test_values_that_are_not_saved(make_audio, ext, field, value):
    path = make_audio('song.' + ext, title='Song')
    frames, tag = save(path, {field: [value]})
    assert sorted(frames.keys()) == ['TIT2']
    assert field not in tag


@pytest.mark.parametrize('ext', ID3_FORMATS)
def test_bad_value_keeps_the_frame(make_audio, ext):
    # id3.txt: POPM "an email, rating and playcount separated by a colon";
    # RVA2 "Values are of the forme channel:gain:peak". A value that isn't
    # in that form changes nothing. Synthetic frames and values.
    path = make_audio('song.' + ext, title='Song')
    add_frames(path, mutagen.id3.POPM(email='a@b', rating=5, count=2),
               mutagen.id3.RVA2(desc='track', channel=1, gain=-1.0, peak=0.5))
    frames, tag = save(path, {'popularimeter': ['zzz'], 'rgain:track': ['y']})
    assert [(p.email, p.rating, p.count) for p in frames.getall('POPM')] == [('a@b', 5, 2)]
    assert (frames['RVA2:track'].channel, frames['RVA2:track'].gain) == (1, -1.0)


@pytest.mark.parametrize('ext', ID3_FORMATS)
def test_editing_existing_frames(make_audio, ext):
    # id3.txt: POPM "an email, rating and playcount separated by a colon";
    # UFID "Only values that can be decoded to UTF-8 will be editable"; RVA2
    # "Values are of the forme channel:gain:peak"; USLT
    # "Language|Description|Lyrics". Frames written by another program, then
    # edited. Synthetic values.
    path = make_audio('song.' + ext, title='Song')
    add_frames(path, mutagen.id3.POPM(email='a@b', rating=5, count=2),
               mutagen.id3.UFID(owner='x.org', data=b'old'),
               mutagen.id3.RVA2(desc='track', channel=1, gain=-1.0, peak=0.5),
               mutagen.id3.USLT(encoding=3, lang='eng', desc='d', text='old'))
    frames, tag = save(path, {'popularimeter': ['c@d:6:3', 'e@f:7:4'], 'rgain:track': ['2:-3:0.25'],
                              'ufid:x.org': ['new'], 'unsyncedlyrics': ['fra|x|neu']})
    assert sorted((p.email, p.rating, p.count) for p in frames.getall('POPM')) == [('c@d', 6, 3), ('e@f', 7, 4)]
    assert frames['UFID:x.org'].data == b'new'
    rva2 = frames['RVA2:track']
    assert (rva2.channel, rva2.gain) == (2, -3.0)
    assert rva2.peak == pytest.approx(0.25)
    assert [(u.lang, u.desc, u.text) for u in frames.getall('USLT')] == [('fra', 'x', 'neu')]
    assert tag['popularimeter'] == ['c@d:6:3', 'e@f:7:4']
    assert tag['ufid:x.org'] == ['new']
    assert tag['unsyncedlyrics'] == ['fra|x|neu']


def test_lyrics_without_text(id3_file):
    # id3.txt: USLT "Language|Description|Lyrics"; the lyrics may be empty.
    # Synthetic values.
    frames, tag = save(id3_file, {'unsyncedlyrics': ['eng|d|']})
    assert [(u.lang, u.desc, u.text) for u in frames.getall('USLT')] == [('eng', 'd', '')]
    assert tag['unsyncedlyrics'] == ['eng|d|']


def test_cover_without_a_mime_type(id3_file):
    # tags.txt, Cover Art: "Cover art can be accessed using the __image
    # field". Synthetic image data: a PNG's signature.
    png = b'\x89PNG\r\n\x1a\n' + b'\0' * 8
    frames, tag = save(id3_file, {'__image': [{'data': png}]})
    assert [(a.mime, a.type, a.desc) for a in frames.getall('APIC')] == [
        ('image/png', PictureType.COVER_FRONT, '')]


@pytest.mark.parametrize('ext', ID3_FORMATS)
def test_total_needs_a_track_total(make_audio, ext):
    # tags.txt, __total: "If the track field is of track/numtracks format,
    # returns numtracks." Synthetic tracks.
    with_total = audioinfo.Tag(str(make_audio('with.' + ext, title='Song', tracknumber='3/12')))
    without = audioinfo.Tag(str(make_audio('without.' + ext, title='Song')))
    assert ('__total' in with_total, with_total['__total'], '__total' in without) == (True, '12', False)


def test_lyrics_field_named_with_a_language(id3_file):
    # "Any unknown field is assumed to be a user-defined field. Therefore
    # writing to the field 'mytag' will write to the ID3 tag frame
    # TXXX:mytag." id3.txt names only the field unsyncedlyrics for USLT.
    # Synthetic value.
    frames, tag = save(id3_file, {'unsyncedlyrics:eng': ['eng|d|t']})
    assert (frames['TXXX:unsyncedlyrics:eng'].text, frames.getall('USLT'), tag['unsyncedlyrics:eng']) == (
        ['eng|d|t'], [], ['eng|d|t'])


@pytest.mark.parametrize('value, text', [('eng|d|a|b', 'a|b'), ('eng|d|a|b|c', 'a|b|c')])
def test_lyrics_keep_their_bars(id3_file, value, text):
    # "Values should take the form Language|Description|Lyrics": whatever
    # follows the second bar is the lyrics. Synthetic values.
    frames, tag = save(id3_file, {'unsyncedlyrics': [value]})
    assert ([(u.lang, u.desc, u.text) for u in frames.getall('USLT')], tag['unsyncedlyrics']) == (
        [('eng', 'd', text)], [f'eng|d|{text}'])


@pytest.mark.parametrize('ext', ID3_FORMATS)
def test_undecodable_ufid_is_kept(make_audio, ext):
    # "Only values that can be decoded to UTF-8 will be editable". The
    # maintainer decided (2026-11-10) that a save keeps the frames
    # puddletag doesn't show. Synthetic frame.
    path = make_audio('song.' + ext, title='Song')
    add_frames(path, mutagen.id3.UFID(owner='example.org', data=b'\xff\xfe\x00'))
    frames, tag = save(path, {'title': ['After']})
    assert (frames['UFID:example.org'].data, 'ufid:example.org' in tag) == (b'\xff\xfe\x00', False)


@pytest.mark.parametrize('ext', ID3_FORMATS)
def test_comments_in_two_languages_are_kept(make_audio, ext):
    # "storing different comment frames requires a different description for
    # each frame". The maintainer decided (2026-11-10) that a save keeps the
    # frames puddletag doesn't show. Synthetic frames.
    path = make_audio('song.' + ext, title='Song')
    add_frames(path, mutagen.id3.COMM(encoding=3, lang='eng', desc='x', text='English'),
               mutagen.id3.COMM(encoding=3, lang='fra', desc='x', text='French'))
    frames, tag = save(path, {'title': ['After']})
    assert sorted((c.lang, c.text) for c in frames.getall('COMM:x')) == [('eng', ['English']), ('fra', ['French'])]


def test_replaygain_value_is_a_list(id3_file):
    # A field maps to a list of strings (audioinfo's contract). Synthetic
    # value.
    frames, tag = save(id3_file, {'rgain:track': ['1:-6.5:0.5']})
    assert isinstance(tag['rgain:track'], list)


@pytest.mark.parametrize('ext', ID3_FORMATS)
def test_id3v23_keeps_the_sort_frames(make_audio, ext):
    # id3.txt lists albumsortorder (TSOA), performersortorder (TSOP),
    # setsubtitle (TSST) and titlesortorder (TSOT) and is silent on ID3v2.3;
    # puddletag's MP3 code keeps them there because "most applications use
    # them also in ID3v2.3", so the other formats do the same. Synthetic
    # values.
    path = make_audio('song.' + ext)
    save(path, {'albumsortorder': ['a'], 'performersortorder': ['p'], 'setsubtitle': ['s'],
                'titlesortorder': ['t']}, v2=3)
    frames = id3_frames(path, translate=False)
    assert ({name: frames[name].text for name in ('TSOA', 'TSOP', 'TSOT', 'TSST')}, frames.version[:2]) == (
        {'TSOA': ['a'], 'TSOP': ['p'], 'TSOT': ['t'], 'TSST': ['s']}, (2, 3))


def test_id3v23_leaves_out_frames_only_id3v24_has(id3_file):
    # id3.txt: saving as ID3v2.3 leaves out mood (TMOO), producednotice
    # (TPRO), encodingtime (TDEN), releasetime (TDRL) and taggingtime (TDTG),
    # which only ID3v2.4 has, and writes involvedpeople and musiciancredits
    # together as involvedpeople (IPLS). Synthetic values.
    save(id3_file, {'encodingtime': ['2001'], 'involvedpeople': ['Bob:Piano'], 'mood': ['m'], 'producednotice': ['n'],
                    'releasetime': ['2002'], 'taggingtime': ['2003'], 'title': ['T']}, v2=3)
    frames = id3_frames(id3_file, translate=False)
    assert (sorted(frames.keys()), frames['IPLS'].people) == (['IPLS', 'TIT2'], [['Bob', 'Piano']])


@pytest.mark.parametrize('ext', ID3_FORMATS)
def test_id3v23_writes_the_credits_together(make_audio, ext):
    # id3.txt: saving as ID3v2.3 "writes involvedpeople and musiciancredits
    # together as involvedpeople (IPLS)". Synthetic values.
    path = make_audio('song.' + ext)
    save(path, {'involvedpeople': ['Bob:Piano'], 'musiciancredits': ['Ann:Drums'], 'title': ['T']}, v2=3)
    frames = id3_frames(path, translate=False)
    assert (sorted(frames.keys()), frames['IPLS'].people, audioinfo.Tag(str(path))['involvedpeople']) == (
        ['IPLS', 'TIT2'], [['Bob', 'Piano'], ['Ann', 'Drums']], ['Bob:Piano;Ann:Drums'])


@pytest.mark.parametrize('ext', ID3_FORMATS)
def test_id3v23_saved_twice_writes_the_credits_once(make_audio, ext):
    # id3.txt: saving as ID3v2.3 "writes involvedpeople and musiciancredits
    # together as involvedpeople (IPLS)"; the save changes the file, not the
    # fields the table shows. Synthetic values.
    path = make_audio('song.' + ext)
    tag = audioinfo.Tag(str(path))
    tag.update({'involvedpeople': ['Bob:Piano'], 'musiciancredits': ['Ann:Drums']})
    tag.save(v2=3)
    tag.save(v2=3)
    assert (id3_frames(path, translate=False)['IPLS'].people, tag['involvedpeople']) == (
        [['Bob', 'Piano'], ['Ann', 'Drums']], ['Bob:Piano'])


@pytest.mark.parametrize('ext', ID3_FORMATS)
def test_convert_to_utf8(make_audio, ext):
    # id3.txt: "Text is written as UTF-8 in ID3v2.4 and as UTF-16 in ID3v2.3,
    # which has no UTF-8". The Tag Tools > Convert to UTF-8 command turns an
    # ID3v2.3 file into ID3v2.4 with every frame in UTF-8. Synthetic values.
    path = make_audio('song.' + ext)
    save(path, {'artist': ['Ünï'], 'comment': ['Ç'], 'mine': ['ü'], 'unsyncedlyrics': ['eng|d|ä', 'fra|e|ö']}, v2=3)
    audioinfo.Tag(str(path)).to_encoding(3)
    frames = id3_frames(path, translate=False)
    assert ({key: frame.encoding for key, frame in frames.items()}, frames.version[:2],
            audioinfo.Tag(str(path))['__tag_read']) == (
        {key: Encoding.UTF8 for key in ('COMM::XXX', 'TPE1', 'TXXX:mine', 'USLT:d:eng', 'USLT:e:fra')},
        (2, 4), 'ID3v2.4')


def test_failed_conversion_keeps_the_encodings(make_audio, monkeypatch):
    # Convert to UTF-8 (see above) that fails to save leaves every frame's
    # encoding as it was: a later save shows it. Synthetic values.
    path = make_audio('song.mp3')
    save(path, {'artist': ['Ünï']}, v2=3)
    tag = audioinfo.Tag(str(path))

    def fail(**kwargs):
        raise OSError('disk full')

    with monkeypatch.context() as patch:
        patch.setattr(tag, 'save', fail)
        with pytest.raises(OSError):
            tag.to_encoding(3)
    tag.save(v2=4)
    assert id3_frames(path, translate=False)['TPE1'].encoding == Encoding.UTF16


@pytest.mark.parametrize('ext', ID3_FORMATS)
def test_save_after_a_rename(make_audio, ext):
    # The docs are silent: the table renames a file (Tag to Filename) and
    # its next edit must be saved under the new name. Synthetic title.
    path = make_audio('song.' + ext, title='Song')
    tag = audioinfo.Tag(str(path))
    new = path.with_name('renamed.' + ext)
    path.rename(new)
    tag.filepath = str(new)
    tag.update({'title': ['After']})
    tag.save(v2=4)
    assert (audioinfo.Tag(str(new))['title'], path.exists()) == (['After'], False)


@pytest.mark.parametrize('ext', ID3_FORMATS)
def test_itunes_grouping_is_shown_and_kept(make_audio, ext):
    # id3.txt's table: "itunesgrouping  GRP1". iTunes writes its grouping to
    # GRP1 (#1056). Synthetic value.
    path = make_audio('song.' + ext, title='Song')
    add_frames(path, GRP1(encoding=Encoding.UTF8, text=['Group']))
    assert audioinfo.Tag(str(path))['itunesgrouping'] == ['Group']
    frames, tag = save(path, {'title': ['After']})
    assert (frames['GRP1'].text, tag['itunesgrouping'], tag['title']) == (['Group'], ['Group'], ['After'])


@pytest.mark.parametrize('ext', ID3_FORMATS)
def test_itunes_grouping_writes_grp1_only(make_audio, ext):
    # id3.txt's table: "grouping  TIT1" and "itunesgrouping  GRP1": each field
    # has its own frame (#1056). Synthetic values.
    path = make_audio('song.' + ext, title='Song')
    frames, tag = save(path, {'itunesgrouping': ['Group']})
    assert (frames['GRP1'].text, 'TIT1' in frames, tag['itunesgrouping']) == (['Group'], False, ['Group'])
    frames, tag = save(path, {'grouping': ['Other']})
    assert (frames['TIT1'].text, frames['GRP1'].text, tag['grouping']) == (['Other'], ['Group'], ['Other'])
