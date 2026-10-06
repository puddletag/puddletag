"""Checks that the shared test setup in conftest.py does its job."""
import os
import urllib.error
import urllib.request

import pytest
from PyQt6.QtWidgets import QMessageBox

from puddlestuff import constants


def test_config_and_data_dirs_are_in_the_sandbox(sandbox_root):
    for path in (constants.CONFIGDIR, constants.SAVEDIR, constants.HOMEDIR):
        assert path.startswith(sandbox_root + os.sep)


def test_network_access_is_blocked_and_recorded(no_network):
    with pytest.raises(urllib.error.URLError):
        urllib.request.urlopen('http://musicbrainz.org/', timeout=5)
    assert no_network == [('getaddrinfo', 'musicbrainz.org')]
    no_network.clear()


def test_queued_dialog_answer_is_returned(dialogs):
    dialogs.answer('QMessageBox.question', QMessageBox.StandardButton.No)
    assert QMessageBox.question(None, 'puddletag', 'Sure?') == QMessageBox.StandardButton.No
    assert dialogs.calls == [('QMessageBox.question', (None, 'puddletag', 'Sure?'), {})]


def test_unexpected_dialog_raises_and_is_recorded(dialogs):
    with pytest.raises(AssertionError, match='unexpected modal dialog QMessageBox.warning'):
        QMessageBox.warning(None, 'puddletag', 'Oops')
    assert dialogs.unexpected == [('QMessageBox.warning', (None, 'puddletag', 'Oops'))]
    dialogs.unexpected.clear()


@pytest.mark.parametrize('name', ['a.mp3', 'a.m4a', 'a.ogg', 'a.flac', 'a.wv', 'a.wma'])
def test_make_audio_writes_tags_puddletag_can_read(make_audio, name):
    from puddlestuff import audioinfo
    path = make_audio(name, artist='Synthetic Artist', title='Synthetic Title')
    tag = audioinfo.Tag(str(path))
    fields = {key: tag[key] for key in tag if not key.startswith('__')}
    assert fields == {'artist': ['Synthetic Artist'], 'title': ['Synthetic Title']}


# Synthetic: an ffmpeg built without libvorbis, as in PR #1100's report
# ("Unknown encoder 'libvorbis'"). Its listing is ffmpeg 6.1's, cut down.
_FFMPEG_WITHOUT_LIBVORBIS = """#!/bin/sh
cat <<'EOF'
Encoders:
 A..... = Audio
 ------
 A....D flac                 FLAC (Free Lossless Audio Codec)
EOF
"""


@pytest.mark.parametrize('ci, outcome', [
    (None, pytest.skip.Exception),    # a contributor's machine: skip
    ('true', pytest.fail.Exception),  # CI must not skip
])
def test_make_audio_without_the_encoder(make_audio, monkeypatch, tmp_path, ci, outcome):
    ffmpeg = tmp_path / 'bin' / 'ffmpeg'
    ffmpeg.parent.mkdir()
    ffmpeg.write_text(_FFMPEG_WITHOUT_LIBVORBIS)
    ffmpeg.chmod(0o755)
    monkeypatch.setenv('PATH', str(ffmpeg.parent), prepend=os.pathsep)
    if ci:
        monkeypatch.setenv('CI', ci)
    else:
        monkeypatch.delenv('CI', raising=False)
    with pytest.raises(outcome, match='ffmpeg has no libvorbis encoder'):
        make_audio('a.ogg')
