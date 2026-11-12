"""util.write, the table's per-file write, called directly: a file's staged
preview, which no window passes to it. Synthetic files.
"""
import os

import mutagen
import pytest

from puddlestuff import audioinfo, util


@pytest.mark.skipif(os.geteuid() == 0, reason='root can write a read-only file')
def test_failed_write_keeps_the_preview(make_audio, tmp_path):
    path = make_audio('01.flac', tmp_path, title='One')
    tag = audioinfo.Tag(str(path))
    tag.library = None
    tag.preview = {'title': ['Staged']}
    os.chmod(path, 0o444)
    with pytest.raises(PermissionError):
        util.write(tag, {'title': ['New']})
    assert tag.preview == {'title': ['Staged']}
    assert tag['title'] == ['One']
    assert mutagen.File(str(path))['title'] == ['One']


def test_write_over_a_preview(make_audio, tmp_path):
    path = make_audio('01.flac', tmp_path, title='One')
    tag = audioinfo.Tag(str(path))
    tag.library = None
    tag.preview = {'title': ['Staged']}
    util.write(tag, {'title': ['New']})
    assert tag.preview == {}
    assert mutagen.File(str(path))['title'] == ['New']
