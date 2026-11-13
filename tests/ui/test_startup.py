"""What puddletag does at startup with an unusual profile or system: a
shortcuts file it can't read or that names what it lacks, and a filesystem
whose encoding is ASCII. The docs don't describe these; the tests show what
puddletag does, as the maintainer decided. Synthetic files.
"""
import json
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QMessageBox

import puddlestuff
from puddlestuff import audioinfo, constants
from puddlestuff import loadshortcuts as ls

pytestmark = pytest.mark.ui

Ok = QMessageBox.StandardButton.Ok
SHIPPED = Path(puddlestuff.__file__).parent / 'data' / 'shortcuts'


def shortcuts_with(name, **values):
    """The shipped shortcuts file with these values changed in the action
    called name, as a hand edit leaves it. Synthetic."""
    data = json.loads(SHIPPED.read_text())
    [entry] = [entry for entry in data.values() if entry.get('name') == name]
    entry.update(values)
    with open(ls.shortcut_path, 'w') as f:
        json.dump(data, f)


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    music = tmp_path / 'music'
    paths = [make_audio(f'0{i}.mp3', music, title=f'Title {i}') for i in (1, 2)]
    mainwin.openDir(str(music), False)
    qtbot.waitUntil(lambda: mainwin._table.model().rowCount() == 2)
    user.activate()
    mainwin._table.setFocus()
    return paths


@pytest.fixture
def unreadable_shortcuts(clean_profile):
    """A shortcuts file cut off in the middle, written before mainwin
    builds the window. Synthetic."""
    with open(ls.shortcut_path, 'w') as f:
        f.write('{"info": {"version": "34"}, "shortcut1": {')


@pytest.fixture
def unknown_enable_signal(clean_profile):
    shortcuts_with('Refresh &Selected', enabled='nosuchsignal')


@pytest.fixture
def unknown_command(clean_profile):
    shortcuts_with('Refresh &Selected', command='nosuchcommand')


@pytest.fixture
def ascii_filesystem(monkeypatch, dialogs):
    monkeypatch.setattr(constants, 'FS_ENC', 'ascii')
    dialogs.answer('QMessageBox.warning', Ok)


def test_unreadable_shortcuts_file_is_replaced(unreadable_shortcuts, mainwin, user):
    # The docs are silent: puddletag replaces a shortcuts file it can't read
    # with the shipped one and starts, with the menus in place.
    with open(ls.shortcut_path) as f:
        assert json.load(f) == json.loads(SHIPPED.read_text())
    assert user.action('Refresh &Selected')


def test_action_whose_enable_signal_is_unknown_stays_greyed_out(unknown_enable_signal, mainwin, user, loaded):
    # The docs are silent: a hand-edited shortcuts entry whose enable signal
    # nothing emits is disabled for good, even with a file selected.
    user.click_cell(user.cell(0, 'title'))

    assert not user.action('Refresh &Selected').isEnabled()


def test_action_whose_command_is_unknown_does_nothing(unknown_command, mainwin, user, loaded):
    # The docs are silent: a hand-edited shortcuts entry whose command its
    # control lacks does nothing when clicked.
    user.click_cell(user.cell(0, 'title'))
    user.click_menu('Refresh &Selected')

    assert [audioinfo.Tag(str(p))['title'] for p in loaded] == [['Title 1'], ['Title 2']]
    assert mainwin._table.model().rowCount() == 2


def test_ascii_filesystem_warns_at_startup(ascii_filesystem, mainwin, dialogs):
    # The docs are silent: when the filesystem's encoding is ASCII, puddletag
    # warns at startup that non-ASCII names can't be handled.
    [(name, args, kwargs)] = dialogs.calls

    assert name == 'QMessageBox.warning'
    assert args[0] is mainwin
    assert args[1] == 'puddletag'
    assert '<b>ASCII</b>' in args[2]
