"""Remove from List (menus.txt: "Removes the selected files from the list
without asking, and leaves them as they are on disk"), run as a user runs it:
File→Remove from List and the right-click menu. Each removal is checked in
the table and on disk. Synthetic files.
"""
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from puddlestuff import audioinfo

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


def loaded_paths(table):
    return [audio.filepath for audio in table.model().taginfo]


def shown(user, row, field):
    """A cell's text and how it's shown: bold, italic or plain."""
    model = user.table.model()
    index = user.cell(row, field)
    font = model.data(index, Qt.ItemDataRole.FontRole)
    return model.data(index), 'bold' if font.bold() else 'italic' if font.italic() else 'plain'


def edit(user, qtbot, row, field, text):
    """Types text into the row's cell."""
    user.double_click_cell(user.cell(row, field))
    QApplication.focusWidget().selectAll()
    user.type(text)
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: shown(user, row, field)[0] == text)
    user.press(Key.Key_Escape)  # the next row's cell, which Enter opened


# Each way the window offers Remove from List.
REMOVE = {
    'File menu': lambda user, index: user.click_menu('Remove from &List'),
    'right-click menu': lambda user, index: user.right_click_cell(index, 'Remove from &List'),
}


@pytest.mark.parametrize('remove', REMOVE.values(), ids=REMOVE.keys())
def test_remove_from_list(mainwin, user, loaded, remove):
    # "Removes the selected files from the list without asking, and leaves
    # them as they are on disk."
    table, paths = loaded
    index = user.cell(1, 'title')
    user.click_cell(index)
    remove(user, index)
    assert loaded_paths(table) == [str(paths[0]), str(paths[2])]
    assert paths[1].exists()
    assert in_file(paths[1])['title'] == ['Title 2']


def test_remove_several_files(mainwin, user, loaded):
    # "Removes the selected files from the list without asking, and leaves
    # them as they are on disk."
    table, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(2, 'title'), Shift)
    user.click_menu('Remove from &List')
    assert table.model().taginfo == []
    assert all(p.exists() for p in paths)
    assert not user.action('Remove from &List').isEnabled()


def test_remove_files_selected_apart(mainwin, user, loaded):
    # "Removes the selected files from the list without asking, and leaves
    # them as they are on disk."
    table, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(2, 'title'), Ctrl)
    user.click_menu('Remove from &List')
    assert loaded_paths(table) == [str(paths[1])]
    assert all(p.exists() for p in paths)


def test_no_key(mainwin, user):
    # The entry's title in menus.txt, "Remove from List", names no key.
    assert user.action('Remove from &List').shortcut().isEmpty()


def test_undo_greyed_out_after_removing_an_edited_file(user, loaded, qtbot):
    # "Their edits drop out of the undo history."
    table, paths = loaded
    edit(user, qtbot, 1, 'title', 'New')
    qtbot.waitUntil(lambda: in_file(paths[1])['title'] == ['New'])
    user.click_cell(user.cell(1, 'title'))
    user.click_menu('Remove from &List')
    assert loaded_paths(table) == [str(paths[0]), str(paths[2])]
    assert not user.action('&Undo').isEnabled()
    assert in_file(paths[1])['title'] == ['New']


def test_undo_after_editing_two_files_and_removing_one(user, loaded, qtbot):
    # "Their edits drop out of the undo history.": what is left to undo is
    # the edit of the file that is still in the list.
    table, paths = loaded
    edit(user, qtbot, 0, 'title', 'New 1')
    qtbot.waitUntil(lambda: in_file(paths[0])['title'] == ['New 1'])
    edit(user, qtbot, 1, 'title', 'New 2')
    qtbot.waitUntil(lambda: in_file(paths[1])['title'] == ['New 2'])
    user.click_cell(user.cell(1, 'title'))
    user.click_menu('Remove from &List')
    assert user.action('&Undo').isEnabled()
    user.press(Key.Key_Z, Ctrl)
    assert shown(user, 0, 'title')[0] == 'Title 1'
    qtbot.waitUntil(lambda: in_file(paths[0])['title'] == ['Title 1'])
    assert in_file(paths[1])['title'] == ['New 2']
    assert not user.action('&Undo').isEnabled()


def test_remove_in_preview_mode(user, loaded, qtbot):
    # "in preview mode their unsaved edits are dropped with them."
    table, paths = loaded
    user.press(Key.Key_P, Ctrl | Shift)
    edit(user, qtbot, 1, 'title', 'New 2')
    user.click_cell(user.cell(1, 'title'))
    user.click_menu('Remove from &List')
    assert loaded_paths(table) == [str(paths[0]), str(paths[2])]
    assert in_file(paths[1])['title'] == ['Title 2']
    assert not user.action('&Undo').isEnabled()

    edit(user, qtbot, 0, 'title', 'New 1')
    user.activate()  # the File menu took the activation
    user.press(Key.Key_W, Ctrl)  # Write Previews
    qtbot.waitUntil(lambda: in_file(paths[0])['title'] == ['New 1'])
    assert in_file(paths[1])['title'] == ['Title 2']
