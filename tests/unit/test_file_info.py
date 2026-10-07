"""The file information fields (__length, __bitrate, __path...) that
audioinfo.Tag gives a real file: the table shows them and patterns use them.

Expected results come from docsrc/source/tags.txt. The files are synthetic:
one second of mono silence at 44.1 kHz, in Music/Artist/Album (the .ape
file only says so in its header).
"""
import os
import re

import pytest

from puddlestuff import audioinfo
from puddlestuff.audioinfo.util import strlength

# Each format and the tag puddletag reads and writes in it.
FORMATS = {'mp3': 'ID3v2.4', 'flac': 'VorbisComment', 'ogg': 'VorbisComment', 'm4a': 'MP4',
           'ape': 'APEv2', 'mpc': 'APEv2', 'wv': 'APEv2', 'wma': 'ASF'}
DATE = r'\d{4}-\d\d-\d\d'
DATETIME = DATE + r' \d\d:\d\d:\d\d'

# Where the code differs from tags.txt, by test and format.
DIFFERS = {
    ('test_sound', 'mpc'): 'Musepack files are read by the generic APEv2 class: '
                           'no length, frequency or channels',
    ('test_sound', 'wv'): "mutagen gives a mono WavPack file's channels as True",
    ('test_sound', 'wma'): 'mutagen gives the length as 0.9999999999999996 s, '
                           'which __length rounds down to 00:00',
    ('test_tags', 'wma'): '__num_images is missing when the file has no cover art',
}


@pytest.fixture(params=sorted(FORMATS))
def song(request, make_audio, tmp_path):
    reason = DIFFERS.get((request.node.originalname, request.param))
    if reason:
        request.node.add_marker(pytest.mark.xfail(strict=True, reason=reason))
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
    assert (song['__frequency'], song['__frequency_num']) == ('44.1 kHz', 44.1)
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


@pytest.mark.parametrize('ext', ['mp3', 'flac'])
def test_total(make_audio, tmp_path, ext):
    # "If the track field is of track/numtracks format, returns numtracks.
    # Can also be written to."
    path = make_audio('song.' + ext, tmp_path, tracknumber='3/12')
    tag = audioinfo.Tag(str(path))
    assert tag['__total'] == '12'
    tag.update({'__total': '15'})
    tag.save()
    assert audioinfo.Tag(str(path))['track'] == ['3/15']
