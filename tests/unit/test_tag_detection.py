"""The tags tag_versions.tags_in_file finds in a file: ID3v1 and APEv2 at
its end, ID3v2 at its start or the ID3v2 version puddletag already read.
__tag lists them (tags.txt: "Comma-Separated list of tags found in file");
test_other_tags.py and test_file_info.py test __tag on whole files.

Synthetic files and tags.
"""
import pytest

from puddlestuff.audioinfo import tag_versions


@pytest.mark.parametrize("tail, tags", [(b"", []), (b"TAG" + b"A" * 125, ["ID3v1.1"])],
                         ids=["no tag", "ID3v1"])
def test_tags_in_file_small_file(tmp_path, tail, tags):
    # Shorter than the 160 bytes read from its end: its ID3v1 tag is still found
    fn = tmp_path / "short.mp3"
    fn.write_bytes(b"\x00" * 10 + tail)
    assert tag_versions.tags_in_file(str(fn)) == tags


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
