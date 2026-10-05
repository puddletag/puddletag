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
