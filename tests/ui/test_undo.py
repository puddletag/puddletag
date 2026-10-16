"""Undo (menus.txt: "Undo's the last edit"), run as a user runs it: the
toolbar button, Edit→Undo or Ctrl+Z. Each undo is checked in the files and
in the table. Synthetic files.
"""
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

from puddlestuff import audioinfo
from puddlestuff.mainwin.filterwin import FilterView

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    music = tmp_path / 'music'
    paths = [make_audio(f'0{i}.mp3', music, artist=f'Artist {i}', title=f'Title {i}')
             for i in (1, 2, 3)]
    mainwin.openDir(str(music), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == 3)
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]
    user.activate()
    table.setFocus()
    return table, paths


def in_file(path):
    return audioinfo.usertags(audioinfo.Tag(str(path)))


def titles(table):
    return {audio.filepath: audio['title'] for audio in table.model().taginfo}


def edit(user, qtbot, row, text, path):
    """Types text into the row's Title cell."""
    user.double_click_cell(user.cell(row, 'title'))
    QApplication.focusWidget().selectAll()
    user.type(text)
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: in_file(path)['title'] == [text])
    user.press(Key.Key_Escape)  # the next row's cell, which Enter opened


def edit_all(user, qtbot, text, paths):
    """Types text into the Title cell with every file selected."""
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(len(paths) - 1, 'title'), Shift)
    user.press(Key.Key_F2)
    user.type(text)
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: all(in_file(p)['title'] == [text] for p in paths))
    user.activate()


def filter_table(user, mainwin, text):
    [view] = mainwin.findChildren(FilterView)
    user.click(view.combo.combo.lineEdit())
    user.press(Key.Key_A, Ctrl)
    user.type(text)
    if not text:
        user.press(Key.Key_Delete)
    user.press(Key.Key_Return)


# The last edit's files may have left the table since: before, Undo then
# closed puddletag (an uncaught ValueError, since 2010).

def test_file_hidden_by_the_filter(mainwin, user, loaded, qtbot):
    # The hidden file is restored too, and shows so once the Filter is
    # cleared.
    table, paths = loaded
    edit(user, qtbot, 0, 'New', paths[0])
    filter_table(user, mainwin, 'Title 2')
    qtbot.waitUntil(lambda: str(paths[0]) not in titles(table))
    user.click_toolbar('&Undo')
    assert in_file(paths[0])['title'] == ['Title 1']
    assert not user.action('&Undo').isEnabled()
    filter_table(user, mainwin, '')
    qtbot.waitUntil(lambda: table.model().rowCount() == 3)
    assert titles(table)[str(paths[0])] == ['Title 1']


def test_file_reloaded_by_refresh_selected(user, loaded, qtbot):
    table, paths = loaded
    edit(user, qtbot, 0, 'New', paths[0])
    user.click_cell(user.cell(0, 'title'))
    old = table.model().taginfo[0]
    user.click_menu('Refresh &Selected')
    qtbot.waitUntil(lambda: table.model().rowCount() == 3 and old not in table.model().taginfo)
    user.click_toolbar('&Undo')
    assert in_file(paths[0])['title'] == ['Title 1']
    assert titles(table)[str(paths[0])] == ['Title 1']


def test_deleted_file(user, loaded, qtbot, dialogs):
    # The edit's other files are restored.
    table, paths = loaded
    edit_all(user, qtbot, 'Same', paths)
    user.click_cell(user.cell(1, 'title'))
    dialogs.answer('QMessageBox.question', QMessageBox.StandardButton.Yes)
    user.press(Key.Key_Delete)
    qtbot.waitUntil(lambda: not paths[1].exists())
    user.click_toolbar('&Undo')
    assert [in_file(p)['title'] for p in (paths[0], paths[2])] == [['Title 1'], ['Title 3']]
    assert titles(table) == {str(paths[0]): ['Title 1'], str(paths[2]): ['Title 3']}
    assert not user.action('&Undo').isEnabled()


def test_unload_everything_clears_the_history(user, loaded, qtbot):
    # "the undo history is cleared when a new folder is imported using Open
    # Folder, by Refresh and by Unload Everything" (menus.txt)
    table, paths = loaded
    edit(user, qtbot, 0, 'New', paths[0])
    assert user.action('&Undo').isEnabled()
    user.click_menu('&Unload Everything')
    assert table.model().rowCount() == 0
    assert not user.action('&Undo').isEnabled()
    assert in_file(paths[0])['title'] == ['New']
