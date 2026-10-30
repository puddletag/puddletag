import io
import os
import mutagen.apev2
import mutagen.id3
import pytest

from puddlestuff import audioinfo
from puddlestuff.audioinfo import tag_versions


def test_tags_in_file_small_file():
    # File smaller than 160 bytes should not raise OSError / IOError
    bio = io.BytesIO(b"short file")
    tags = tag_versions.tags_in_file(bio)
    assert tags == []


def test_tags_in_file_id3v1_only(tmp_path):
    fn = str(tmp_path / "v1.mp3")
    with open(fn, "wb") as f:
        f.write(b"\x00" * 200)
        # 128 bytes ID3v1 tag
        f.write(b"TAG" + b"A" * 125)

    tags = tag_versions.tags_in_file(fn)
    assert tags == ["ID3v1.1"]


def test_tags_in_file_known_v2_used(tmp_path):
    fn = str(tmp_path / "test.mp3")
    with open(fn, "wb") as f:
        f.write(b"\x00" * 200)
        f.write(b"TAG" + b"A" * 125)

    # When known_v2 is provided, it should appear in tags without reading header
    tags = tag_versions.tags_in_file(fn, known_v2="ID3v2.4")
    assert "ID3v2.4" in tags
    assert "ID3v1.1" in tags


def test_tags_in_file_known_v2_ignored_if_invalid(tmp_path):
    fn = str(tmp_path / "test_invalid_known.mp3")
    with open(fn, "wb") as f:
        f.write(b"\x00" * 200)
        f.write(b"TAG" + b"A" * 125)

    # known_v2="ID3v1.1" should not be treated as known v2 tag
    tags = tag_versions.tags_in_file(fn, known_v2="ID3v1.1")
    assert tags == ["ID3v1.1"]
    assert tags.count("ID3v1.1") == 1


def test_tag_reporting_mp3_multiple_tags(make_audio):
    path = make_audio('test.mp3', title='Title', artist='Artist')
    apev2 = mutagen.apev2.APEv2()
    apev2.update({'Title': 'APE title'})
    apev2.save(str(path))
    audioinfo.Tag(str(path)).save()  # adds ID3v1

    tag_obj = audioinfo.Tag(str(path))
    tags = tag_obj['__tag'].split(', ')
    assert tags[0] == 'ID3v2.4'
    assert 'ID3v1.1' in tags
    assert 'APEv2' in tags


def test_tag_reporting_flac_secondary_id3(make_audio):
    path = make_audio('test.flac', title='Flac title')
    id3_tag = mutagen.id3.ID3()
    id3_tag.add(mutagen.id3.TIT2(encoding=3, text=['ID3 title']))
    id3_tag.save(str(path))

    tag_obj = audioinfo.Tag(str(path))
    tags = tag_obj['__tag'].split(', ')
    assert tags[0] == 'VorbisComment'
    assert 'ID3v2.4' in tags


def test_tag_reporting_formats(make_audio):
    flac_path = make_audio('track.flac', title='Flac title')
    assert audioinfo.Tag(str(flac_path))['__tag'] == 'VorbisComment'

    ogg_path = make_audio('track.ogg', title='Ogg title')
    assert audioinfo.Tag(str(ogg_path))['__tag'] == 'VorbisComment'

    mp4_path = make_audio('track.m4a', title='MP4 title')
    assert audioinfo.Tag(str(mp4_path))['__tag'] == 'MP4'

    wma_path = make_audio('track.wma', title='WMA title')
    assert audioinfo.Tag(str(wma_path))['__tag'] == 'ASF'
