"""Properties (menus.txt: "Shows the first selected file's format
information like filetype, version, etc."), run as a user runs it: the Edit
menu and the File-View's right-click menu. Synthetic files.
"""
import re

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextDocumentFragment
from PyQt6.QtWidgets import QGroupBox, QPushButton

from puddlestuff import audioinfo
from puddlestuff.tagmodel import Properties

pytestmark = pytest.mark.ui

Ctrl = Qt.KeyboardModifier.ControlModifier
DATETIME = r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d'


def load(mainwin, qtbot, user, folder, count):
    mainwin.openDir(str(folder), False)
    qtbot.waitUntil(lambda: mainwin._table.model().rowCount() == count)
    user.activate()


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    """Synthetic: three MP3 files, one second of mono silence at 44.1 kHz."""
    music = tmp_path / 'music'
    paths = [make_audio(f'0{i}.mp3', music, title=f'Title {i}') for i in (1, 2, 3)]
    load(mainwin, qtbot, user, music, 3)
    assert [audio.filepath for audio in mainwin._table.model().taginfo] == [str(p) for p in paths]
    return paths


def shown(label):
    """A label's text as the window shows it."""
    if label.textFormat() == Qt.TextFormat.PlainText:
        return label.text()
    return QTextDocumentFragment.fromHtml(label.text()).toPlainText()


def open_windows(mainwin):
    return [w for w in mainwin.findChildren(Properties) if w.isVisible()]


def open_properties(mainwin, qtbot, run):
    """Runs the command and returns the one window it opened."""
    run()
    qtbot.waitUntil(lambda: len(open_windows(mainwin)) == 1)
    [window] = open_windows(mainwin)
    return window


def panel(window):
    """Each group's title and its rows, label to value, as shown."""
    groups = {}
    for box in window.findChildren(QGroupBox):
        grid = box.layout()
        rows = [[shown(grid.itemAtPosition(row, column).widget()) for column in (0, 1)]
                for row in range(grid.rowCount())]
        groups[box.title()] = {name.removesuffix(':'): value for name, value in rows}
    return groups


# Each way the window offers Properties.
OPEN = {
    'Edit menu': lambda user, index: user.click_menu('&Properties'),
    'right-click menu': lambda user, index: user.right_click_cell(index, '&Properties'),
}


@pytest.mark.parametrize('open_', OPEN.values(), ids=OPEN.keys())
def test_properties(mainwin, qtbot, user, loaded, open_):
    # "Shows the first selected file's format information"
    paths = loaded
    index = user.cell(1, 'title')
    user.click_cell(index)
    window = open_properties(mainwin, qtbot, lambda: open_(user, index))
    file = panel(window)['File']
    assert file['Path'] == str(paths[1])
    assert file['Filename'] == '02.mp3'
    [close] = [b for b in window.findChildren(QPushButton) if b.text() == 'Close']
    user.click(close)
    assert not window.isVisible()


def test_format_information(mainwin, qtbot, user, loaded):
    # "Shows the first selected file's format information like filetype,
    # version, etc." tags.txt: __bitrate "a string with kb/s appended as in
    # '213 kb/s'", __frequency "'44.1 kHz'", __mode "One of, Mono, Stereo,
    # Joint-Stereo or Dual Channel", __length "MM:SS format", __modified
    # "YYYY-MM-DD HH:MM:SS format", __file_size "human-readable".
    paths = loaded
    user.click_cell(user.cell(0, 'title'))
    window = open_properties(mainwin, qtbot, lambda: user.click_menu('&Properties'))
    groups = panel(window)
    on_disk = audioinfo.Tag(str(paths[0]))
    assert groups['File']['Path'] == str(paths[0])
    assert groups['File']['Filename'] == '01.mp3'
    assert re.fullmatch(DATETIME, groups['File']['Modified'])
    assert re.fullmatch(r'\d+(\.\d+)? (B|KB|MB|GB)', groups['File']['Size'])
    # MPEG 1 Layer 3 is what a 44.1 kHz MP3 is (synthetic file).
    assert groups['Version'] == {'Bitrate': on_disk['__bitrate'], 'Frequency': '44.1 kHz',
                                 'Length': '00:01', 'Mode': 'Mono', 'Version': 'MPEG 1 Layer 3'}
    assert re.fullmatch(r'\d+ kb/s', groups['Version']['Bitrate'])


def test_first_selected_file(mainwin, qtbot, user, loaded):
    # "the first selected file's": the first is the topmost selected row,
    # whatever the click order.
    user.click_cell(user.cell(2, 'title'))
    user.click_cell(user.cell(0, 'title'), Ctrl)
    window = open_properties(mainwin, qtbot, lambda: user.click_menu('&Properties'))
    assert panel(window)['File']['Filename'] == '01.mp3'


def test_greyed_out_without_selection(user, loaded):
    # "the first selected file's": with none selected there is nothing to show.
    action = user.action('&Properties')
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(0, 'title'), Ctrl)
    assert not action.isEnabled()
    user.click_cell(user.cell(1, 'title'))
    assert action.isEnabled()
    user.click_cell(user.cell(2, 'title'), Ctrl)
    assert action.isEnabled()


def test_greyed_out_with_no_files(mainwin, user):
    assert not user.action('&Properties').isEnabled()


def test_no_key(mainwin, user):
    # The entry's title in menus.txt, "Properties", names no key.
    assert user.action('&Properties').shortcut().isEmpty()


def test_id3_version(mainwin, qtbot, user, loaded):
    # "format information like filetype, version, etc.", and the row's own
    # label, ID3 Version.
    paths = loaded
    user.click_cell(user.cell(0, 'title'))
    window = open_properties(mainwin, qtbot, lambda: user.click_menu('&Properties'))
    assert audioinfo.Tag(str(paths[0]))['__tag_read'] == 'ID3v2.4'
    assert panel(window)['File']['ID3 Version'] == 'ID3v2.4'


def test_file_name_with_angle_brackets(mainwin, make_audio, tmp_path, qtbot, user):
    # "Shows the first selected file's format information": the file's name
    # and path as they are (synthetic name).
    path = make_audio('Rock <Live> & Roll.mp3', tmp_path / 'music', title='Song')
    load(mainwin, qtbot, user, tmp_path / 'music', 1)
    user.click_cell(user.cell(0, 'title'))
    window = open_properties(mainwin, qtbot, lambda: user.click_menu('&Properties'))
    file = panel(window)['File']
    assert file['Filename'] == 'Rock <Live> & Roll.mp3'
    assert file['Path'] == str(path)
