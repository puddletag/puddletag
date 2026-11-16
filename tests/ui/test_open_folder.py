"""Open Folder in File Manager (menus.txt: "Opens the selected file's folder
in the desktop's file manager"), run as a user runs it: the File menu and
the right-click menu. The file manager itself isn't started: the URL handed
to it is recorded. Synthetic files in two folders.
"""
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDesktopServices

pytestmark = pytest.mark.ui

Ctrl = Qt.KeyboardModifier.ControlModifier

NAME = 'Open Folder in File &Manager'


@pytest.fixture
def opened(monkeypatch):
    """The folders handed to the desktop's file manager."""
    urls = []
    monkeypatch.setattr(QDesktopServices, 'openUrl',
                        lambda url: urls.append(Path(url.toLocalFile())))
    return urls


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    """Two files in folder a, then one in folder b, added after them."""
    a, b = tmp_path / 'a', tmp_path / 'b'
    paths = [make_audio('01.mp3', a, title='Title 1'),
             make_audio('02.mp3', a, title='Title 2'),
             make_audio('03.mp3', b, title='Title 3')]
    mainwin.openDir(str(a), False)
    mainwin.openDir(str(b), True)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == 3)
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]
    user.activate()
    table.setFocus()
    return table, a, b


# Each way the window offers Open Folder in File Manager.
OPEN = {
    'File menu': lambda user, index: user.click_menu(NAME),
    'right-click menu': lambda user, index: user.right_click_cell(index, NAME),
}


@pytest.mark.parametrize('open_folder', OPEN.values(), ids=OPEN.keys())
def test_opens_the_selected_files_folder(mainwin, user, loaded, opened, open_folder):
    # "Opens the selected file's folder in the desktop's file manager."
    table, a, b = loaded
    index = user.cell(2, 'title')
    user.click_cell(index)
    open_folder(user, index)
    assert opened == [b]
    assert table.model().rowCount() == 3


def test_several_files_open_the_topmost_ones_folder(mainwin, user, loaded, opened):
    # "With several files selected, it opens the folder of the topmost one in
    # the list." One window, not one per file or per folder. Row 2 (folder b)
    # is clicked first, so the order of the clicks doesn't decide it.
    table, a, b = loaded
    user.click_cell(user.cell(2, 'title'))
    user.click_cell(user.cell(0, 'title'), Ctrl)
    assert table.selectedRows == [0, 2]
    user.click_menu(NAME)
    assert opened == [a]


def test_greyed_out_with_nothing_selected(mainwin, user, loaded, opened):
    # Synthetic (docs-silent): like the other commands on the selected files,
    # it's greyed out until a file is selected.
    table, a, b = loaded
    table.clearSelection()
    assert not table.selectedRows
    assert not user.action(NAME).isEnabled()
    user.click_cell(user.cell(0, 'title'))
    assert user.action(NAME).isEnabled()
    assert opened == []
