"""The file information fields (__length, __bitrate, __path...) that
audioinfo.Tag gives a real file: the table shows them and patterns use them.

Expected results come from docsrc/source/tags.txt. The files are synthetic:
one second of mono silence at 44.1 kHz (DSD at 2822.4 kHz), in
Music/Artist/Album (the .ape file only says so in its header).
"""
import os
import re

import mutagen
import pytest

from puddlestuff import audioinfo, findfunc
from puddlestuff.audioinfo.util import strlength

# Each format and the tag puddletag reads and writes in it.
FORMATS = {'aiff': 'ID3v2.4', 'ape': 'APEv2', 'dff': 'ID3v2.4', 'dsf': 'ID3v2.4',
           'flac': 'VorbisComment', 'm4a': 'MP4', 'mp3': 'ID3v2.4', 'mpc': 'APEv2',
           'ogg': 'VorbisComment', 'opus': 'VorbisComment', 'wma': 'ASF', 'wv': 'APEv2'}
# __frequency and __frequency_num, where not 44.1 kHz. Opus streams are
# timed at 48 kHz whatever the input's rate (RFC 7845), and libopus
# resamples ffmpeg's 44.1 kHz input to it.
RATES = {'dff': ('2822.4 kHz', 2822.4), 'dsf': ('2822.4 kHz', 2822.4), 'opus': ('48.0 kHz', 48.0)}
DATE = r'\d{4}-\d\d-\d\d'
DATETIME = DATE + r' \d\d:\d\d:\d\d'


@pytest.fixture(params=sorted(FORMATS))
def song(request, make_audio, tmp_path):
    path = make_audio('song.' + request.param, tmp_path / 'Music' / 'Artist' / 'Album', title='Song')
    return audioinfo.Tag(str(path))


def test_names(song):
    # The docs' examples: /media/Multimedia/Music/myfile.mp3 has __filename
    # myfile.mp3, __dirpath /media/Multimedia/Music, extension mp3...
    ext = song['__ext']
    folder = os.path.dirname(song['__path'])
    assert (song['__filename'], song['__filename_no_ext'], ext) == ('song.' + ext, 'song', ext)
    assert song['__path'] == os.path.join(folder, 'song.' + ext)
    assert (song['__dirpath'], song['__dirname'], song['__parent_dir']) == (folder, 'Album', 'Artist')


def test_sound(song):
    assert (song['__length'], song['__length_seconds']) == ('00:01', '1')
    assert (song['__frequency'], song['__frequency_num']) == RATES.get(song['__ext'], ('44.1 kHz', 44.1))
    assert (song['__mode'], song['__channels']) == ('Mono', '1')


def test_length_past_an_hour():
    # __length: "MM:SS format, or HH:MM:SS from an hour on, e.g. 03:25 or
    # 01:02:05"
    assert (strlength(205), strlength(3725)) == ('03:25', '01:02:05')


def test_bitrate(song):
    # "a string with kb/s appended as in '213 kb/s'"; __bitrate_num: "in
    # whole kb/s, as a number: 213 for '213 kb/s'"
    assert song['__bitrate'] == '{} kb/s'.format(song['__bitrate_num'])


def test_bitrate_num(song):
    assert re.fullmatch(r'\d+', str(song['__bitrate_num']))


def test_sizes(song):
    size = os.path.getsize(song['__path'])
    assert song['__size'] == song['__file_size_bytes'] == str(size)
    assert re.fullmatch(r'\d+ KB', song['__file_size_kb'])
    assert song['__file_size_mb'] == '{:.2f} MB'.format(size / 1024 ** 2)  # "to two decimal places"
    assert re.fullmatch(r'\d+(\.\d+)? (B|KB|MB|GB)', song['__file_size'])  # "human-readable"


@pytest.mark.parametrize('field, form', [
    ('__accessed', DATETIME), ('__created', DATETIME), ('__modified', DATETIME),
    ('__file_access_date', DATE), ('__file_access_datetime', DATETIME),
    ('__file_create_date', DATE), ('__file_create_datetime', DATETIME),
    ('__file_mod_date', DATE), ('__file_mod_datetime', DATETIME),
    ('__file_access_datetime_raw', r'\d+'), ('__file_create_datetime_raw', r'\d+'),
    ('__file_mod_datetime_raw', r'\d+'),
])
def test_dates(song, field, form):
    assert re.fullmatch(form, song[field])


def test_tags(song):
    tag = FORMATS[song['__ext']]
    assert (song['__tag'], song['__tag_read'], song['__num_images']) == (tag, tag, '0')
    assert re.fullmatch(r'puddletag v\d+\.\d+.*', song['__app'])  # "puddletag v0.10.4"


@pytest.mark.parametrize('ext', sorted(set(FORMATS) - {'m4a'}))
def test_total(make_audio, tmp_path, ext):
    # "If the track field is of track/numtracks format, returns numtracks.
    # Can also be written to."
    path = make_audio('song.' + ext, tmp_path, tracknumber='3/12')
    tag = audioinfo.Tag(str(path))
    assert '__total' in tag
    assert tag['__total'] == '12'
    tag.update({'__total': '15'})
    tag.save()
    assert audioinfo.Tag(str(path))['track'] == ['3/15']


@pytest.mark.parametrize('ext', sorted(set(FORMATS) - {'m4a'}))
def test_total_without_a_track(make_audio, tmp_path, ext):
    # "If the track field is of track/numtracks format, returns numtracks.
    # Can also be written to." Synthetic: the file has no track, so there is
    # no total to write to.
    path = make_audio('song.' + ext, tmp_path, title='Song')
    tag = audioinfo.Tag(str(path))
    tag.update({'__total': '12'})
    tag.save()
    saved = audioinfo.Tag(str(path))
    assert 'track' not in saved
    assert '__total' not in saved
    assert saved['title'] == ['Song']


def test_opus_bitrate(make_audio, tmp_path):
    # #980: "the software can't show the bitrate of opus files".
    # tags.txt: __bitrate_num is the bitrate as a number.
    tag = audioinfo.Tag(str(make_audio('song.opus', tmp_path, title='Song')))
    assert int(tag['__bitrate_num']) > 0
    assert dict(tag.info[1][1])['Bitrate'] == tag['__bitrate']


def test_info_panel(song):
    # menus.txt: Properties "Shows the first selected file's format
    # information"; tags.txt: __frequency and __length. The panel shows what
    # the table shows.
    [(_, _), (_, rows)] = song.info
    rows = dict(rows)
    assert (rows['Frequency'], rows['Length']) == (song['__frequency'], song['__length'])


def test_link_file_info(make_audio, tmp_path):
    # Synthetic .apl: the fixture's link text and an APEv2 tag. Properties
    # "Shows the first selected file's format information".
    tag = audioinfo.Tag(str(make_audio('song.apl', tmp_path, title='Song')))
    [(title, rows), *_] = tag.info
    assert (title, dict(rows)['Filename']) == ('File', 'song.apl')


def test_info_without_length(make_audio, tmp_path):
    # Synthetic: a file whose header gives no length leaves Length out.
    tag = audioinfo.Tag(str(make_audio('song.mp3', tmp_path, title='Song')))
    del tag.length
    assert 'Length' not in dict(tag.info[1][1])


def test_file_name_fields_written(song):
    # The docs' examples: /media/Multimedia/Music/myfile.mp3 has __filename
    # myfile.mp3, __dirpath /media/Multimedia/Music, extension mp3...
    ext = song['__ext']
    folder = os.path.dirname(song['__path'])
    song.update({'__filename': 'other.' + ext})
    assert song['__path'] == os.path.join(folder, 'other.' + ext)
    assert song['__filename_no_ext'] == 'other'
    assert song['__ext'] == ext


def test_save_after_a_rename(song):
    # Synthetic: the table renames the file, then points the tag at the new
    # path and saves (rename_file in puddlestuff/util.py).
    ext = song['__ext']
    old = song['__path']
    new = os.path.join(os.path.dirname(old), 'renamed.' + ext)
    os.rename(old, new)
    song.update({'__path': new, 'album': ['A']})
    song.save()
    saved = audioinfo.Tag(new)
    assert (saved['album'], saved['title']) == (['A'], ['Song'])


@pytest.mark.parametrize('ext', sorted(FORMATS))
def test_save_with_no_tags(make_audio, tmp_path, ext):
    # Synthetic: a file whose tags were all removed by another program still
    # takes a title.
    path = make_audio('song.' + ext, tmp_path, title='Song')
    mutagen.File(path).delete()
    tag = audioinfo.Tag(str(path))
    assert audioinfo.usertags(tag) == {}
    tag.update({'title': ['New']})
    tag.save()
    assert audioinfo.Tag(str(path))['title'] == ['New']


@pytest.mark.parametrize('size, text', [
    (2, '2 B'),
    (1023, '1023 B'),
    (1025, '1 KB'),
    (5 * 1024 ** 2, '5.00 MB'),
    (3 * 1024 ** 3, '3.00 GB'),
])
def test_file_size_units(size, text):
    # __file_size: "The file's size in human-readable format." Synthetic sizes.
    assert audioinfo.str_filesize(size) == text


@pytest.mark.xfail(strict=True, reason='an exact 1024 bytes shows as 1024 B, 1 GiB as 1024.00 MB')
@pytest.mark.parametrize('size, text', [
    (1024, '1 KB'),
    (1024 ** 2, '1.00 MB'),
    (1024 ** 3, '1.00 GB'),
])
def test_file_size_at_each_unit(size, text):
    # __file_size: "The file's size in human-readable format." Synthetic sizes.
    assert audioinfo.str_filesize(size) == text


@pytest.mark.xfail(strict=True, reason='a file under 2 bytes raises ValueError')
@pytest.mark.parametrize('size, text', [(0, '0 B'), (1, '1 B')])
def test_size_of_an_empty_file(size, text):
    # __file_size: "The file's size in human-readable format." Synthetic sizes.
    assert audioinfo.str_filesize(size) == text


@pytest.mark.xfail(strict=True, reason='a file under 2 bytes raises ValueError')
def test_empty_wavpack_file(tmp_path):
    # __size: "The size of the file in bytes." __file_size: "The file's size
    # in human-readable format." Synthetic empty file.
    path = tmp_path / 'empty.wv'
    path.write_bytes(b'')
    tag = audioinfo.Tag(str(path))
    assert (tag['__size'], tag['__file_size']) == ('0', '0 B')


@pytest.mark.xfail(strict=True, reason='patterns read only the fields keys() lists, which hold no __total')
@pytest.mark.parametrize('ext', sorted(set(FORMATS) - {'m4a'}))
def test_total_in_a_pattern(make_audio, tmp_path, ext):
    # "If the track field is of track/numtracks format, returns numtracks."
    path = make_audio('song.' + ext, tmp_path, tracknumber='3/12')
    assert findfunc.parsefunc('%__total%', audioinfo.Tag(str(path))) == '12'


@pytest.mark.xfail(strict=True, reason='patterns read only the fields keys() lists, which hold no __total')
def test_total_in_a_pattern_mp4(make_audio, tmp_path):
    # MP4: "writing track as 3/12 ... sets both" (make_audio can't set an MP4
    # track, so it is written through the tag).
    path = make_audio('song.m4a', tmp_path, title='Song')
    tag = audioinfo.Tag(str(path))
    tag.update({'track': ['3/12']})
    tag.save()
    assert findfunc.parsefunc('%__total%', audioinfo.Tag(str(path))) == '12'


def test_no_total_without_one_in_the_track(make_audio, tmp_path):
    # Synthetic: "If the track field is of track/numtracks format, returns
    # numtracks." A track of 3 has no numtracks, so there is no __total.
    path = make_audio('song.flac', tmp_path, tracknumber='3')
    tag = audioinfo.Tag(str(path))
    assert '__total' not in tag
    with pytest.raises(KeyError):
        tag['__total']


def test_empty_total_removes_it(make_audio, tmp_path):
    # Synthetic: "Can also be written to." Writing an empty total leaves the
    # track alone.
    path = make_audio('song.flac', tmp_path, tracknumber='3/12')
    tag = audioinfo.Tag(str(path))
    tag.update({'__total': ''})
    tag.save()
    assert audioinfo.Tag(str(path))['track'] == ['3']


@pytest.mark.xfail(strict=True, reason="writing __parent_dir renames the file's folder")
def test_parent_dir_cannot_be_written(song):
    # __parent_dir: "Cannot be written to."
    path = song['__path']
    song.update({'__parent_dir': 'X'})
    assert song['__path'] == path
    assert song['__parent_dir'] == 'Artist'


def test_file_name_fields_written_one_by_one(song):
    # The docs don't say whether __ext, __dirname, __filename_no_ext and
    # __filename can be written to; the maintainer's call is that writing
    # each renames the file. Each on a fresh tag of the same file. Synthetic
    # values.
    path = song['__path']
    folder, name = os.path.split(path)
    ext = song['__ext']

    tag = audioinfo.Tag(path)
    tag.update({'__ext': ''})
    assert tag['__path'] == os.path.join(folder, 'song')
    assert tag.filename_no_ext == 'song'

    tag = audioinfo.Tag(path)
    tag.update({'__dirname': 'Other'})
    assert tag['__path'] == os.path.join(os.path.dirname(folder), 'Other', name)
    assert (tag.dirname, tag.parent_dir) == ('Other', 'Artist')

    tag = audioinfo.Tag(path)
    tag.update({'__filename_no_ext': 'other'})
    assert tag['__path'] == os.path.join(folder, 'other.' + ext)
    assert tag.filename_no_ext == 'other'

    tag = audioinfo.Tag(path)
    tag.update({'__filename': ['list.' + ext]})
    assert tag['__path'] == os.path.join(folder, 'list.' + ext)
