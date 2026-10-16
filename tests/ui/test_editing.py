"""Editing tags in the File-View, the main window's table, as a user does:
double-click a cell (or press F2, or start typing), type, press Enter
(tut3.txt, "The File-View"). Each edit is checked in the table and in the
file. Synthetic files.
"""
import os

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QApplication, QMessageBox

from puddlestuff import audioinfo

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    """Three MP3s in the table, in this order, with the window active and
    the table focused, as after clicking into it."""
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


def open_editor(table, index):
    """The editor open on index, which has the keyboard focus."""
    editor = table.indexWidget(index)
    assert editor is not None and QApplication.focusWidget() is editor
    return editor


def edit(user, index, text):
    user.double_click_cell(index)
    open_editor(user.table, index).selectAll()
    user.type(text)


def in_file(path):
    return audioinfo.usertags(audioinfo.Tag(str(path)))


def in_table(table):
    return [audioinfo.usertags(audio) for audio in table.model().taginfo]


def written(qtbot, path, field, value):
    """Enter writes once Qt's event loop runs again (the delegate commits
    the edit through a queued call)."""
    qtbot.waitUntil(lambda: in_file(path).get(field) == value)


# "You can write to multiple files at once. Just select the files. Choose
# the field you want to write to and write as normal. All selected files
# will be updated." Writing to one cell is writing as normal, started in
# each way the table offers: a double-click, F2, or typing.

def start_with_double_click(user, index):
    user.double_click_cell(index)
    open_editor(user.table, index).selectAll()


def start_with_f2(user, index):
    user.click_cell(index)
    user.press(Key.Key_F2)
    assert open_editor(user.table, index).selectedText() == user.table.model().data(index)


def start_by_typing(user, index):
    user.click_cell(index)


@pytest.mark.parametrize('start', [start_with_double_click, start_with_f2, start_by_typing])
def test_edit_one_cell(user, loaded, qtbot, start):
    table, paths = loaded
    start(user, user.cell(0, 'title'))
    user.type('New')
    user.press(Key.Key_Return)
    written(qtbot, paths[0], 'title', ['New'])
    expected = [{'artist': ['Artist 1'], 'title': ['New']},
                {'artist': ['Artist 2'], 'title': ['Title 2']},
                {'artist': ['Artist 3'], 'title': ['Title 3']}]
    assert [in_file(p) for p in paths] == expected
    assert in_table(table) == expected
    assert table.model().data(user.cell(0, 'title')) == 'New'


# "With several files selected, the cell stays where it is instead",
# whichever key ends the edit, as since puddletag 1.0.0-RC2 (moving on
# opened the next cell with its value from before the write). The edited
# cell is in the middle row, with a cell to go to each way.

@pytest.mark.parametrize('key, modifier', [(Key.Key_Return, None), (Key.Key_Return, Shift),
                                           (Key.Key_Tab, None), (Key.Key_Backtab, Shift)],
                         ids=['Enter', 'Shift+Enter', 'Tab', 'Shift+Tab'])
def test_edit_several_files(user, loaded, qtbot, key, modifier):
    table, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(1, 'title'), Shift)
    user.press(Key.Key_F2)
    open_editor(table, user.cell(1, 'title')).selectAll()
    user.type('Same')
    user.press(key, modifier or Qt.KeyboardModifier.NoModifier)
    for path in paths[:2]:
        written(qtbot, path, 'title', ['Same'])
    expected = [{'artist': ['Artist 1'], 'title': ['Same']},
                {'artist': ['Artist 2'], 'title': ['Same']},
                {'artist': ['Artist 3'], 'title': ['Title 3']}]
    assert [in_file(p) for p in paths] == expected
    assert in_table(table) == expected
    user.activate()
    qtbot.wait(50)  # where the next cell would open
    assert table.state() == QAbstractItemView.State.NoState
    assert table.currentIndex() == user.cell(1, 'title')
    assert table.selectedRows == [0, 1]


def test_edit_several_files_undone_in_one_step(user, loaded, qtbot):
    # "All selected files will be updated, and Edit→Undo puts them all
    # back at once", here with its shortcut, Ctrl+Z.
    table, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(2, 'title'), Shift)
    assert table.selectedRows == [0, 1, 2]
    user.press(Key.Key_F2)
    user.type('Same')
    user.press(Key.Key_Return)
    for path in paths:
        written(qtbot, path, 'title', ['Same'])
    user.activate()
    user.press(Key.Key_Z, Ctrl)
    expected = [{'artist': ['Artist 1'], 'title': ['Title 1']},
                {'artist': ['Artist 2'], 'title': ['Title 2']},
                {'artist': ['Artist 3'], 'title': ['Title 3']}]
    assert [in_file(p) for p in paths] == expected
    assert in_table(table) == expected
    assert not user.action('&Undo').isEnabled()


def test_selected_files_get_the_edited_field(user, loaded, qtbot):
    # "Just select the files. Choose the field you want to write to": the
    # value goes to the field of the cell being edited, in every file with
    # a cell selected, whichever column that cell is in.
    table, paths = loaded
    user.click_cell(user.cell(0, 'artist'))
    user.click_cell(user.cell(2, 'title'), Ctrl)
    user.type('New')
    user.press(Key.Key_Return)
    written(qtbot, paths[2], 'title', ['New'])
    expected = [{'artist': ['Artist 1'], 'title': ['New']},
                {'artist': ['Artist 2'], 'title': ['Title 2']},
                {'artist': ['Artist 3'], 'title': ['New']}]
    assert [in_file(p) for p in paths] == expected
    assert in_table(table) == expected


def test_multiple_values(user, loaded, qtbot):
    # "Multiple-valued fields are shown like value1\\value2. Enter a value
    # like that and puddletag will assume you want some multiple values."
    table, paths = loaded
    edit(user, user.cell(0, 'artist'), 'One\\\\Two')
    user.press(Key.Key_Return)
    written(qtbot, paths[0], 'artist', ['One', 'Two'])
    assert table.model().taginfo[0]['artist'] == ['One', 'Two']
    assert table.model().data(user.cell(0, 'artist')) == 'One\\\\Two'


# "When you press Enter after editing a cell, puddletag opens the one just
# be below it for editing. Shift+Enter will open the one directly above,
# Tab the one to the right and Shift+Tab the one on the left." A keyboard
# sends Shift+Tab as Backtab. In a fresh profile's columns, Artist is left
# of Title and Album right of it.

@pytest.mark.parametrize('key, modifier, row, field', [
    (Key.Key_Return, None, 2, 'title'),
    (Key.Key_Return, Shift, 0, 'title'),
    (Key.Key_Tab, None, 1, 'album'),
    (Key.Key_Backtab, Shift, 1, 'artist'),
], ids=['Enter', 'Shift+Enter', 'Tab', 'Shift+Tab'])
def test_next_cell_opens(user, loaded, qtbot, key, modifier, row, field):
    table, paths = loaded
    edit(user, user.cell(1, 'title'), 'New')
    user.press(key, modifier or Qt.KeyboardModifier.NoModifier)
    written(qtbot, paths[1], 'title', ['New'])
    qtbot.waitUntil(lambda: table.indexWidget(user.cell(row, field)) is not None)
    editor = open_editor(table, user.cell(row, field))
    assert editor.text() == (table.model().data(user.cell(row, field)) or '')
    assert table.model().taginfo[1]['title'] == ['New']


# What happens at the ends of the table: the docs don't say; this is what
# puddletag does. Enter on the last row and Shift+Enter on the first write
# and close the editor; Tab on the last column opens the next row's first
# cell, as anywhere in Qt.

@pytest.mark.parametrize('key, modifier, row', [(Key.Key_Return, None, 2), (Key.Key_Return, Shift, 0)],
                         ids=['Enter on the last row', 'Shift+Enter on the first row'])
def test_no_cell_past_the_end(user, loaded, qtbot, key, modifier, row):
    table, paths = loaded
    edit(user, user.cell(row, 'title'), 'New')
    user.press(key, modifier or Qt.KeyboardModifier.NoModifier)
    written(qtbot, paths[row], 'title', ['New'])
    qtbot.waitUntil(lambda: table.state() == QAbstractItemView.State.NoState)
    assert table.currentIndex() == user.cell(row, 'title')


def test_tab_on_the_last_column(user, loaded, qtbot):
    table, paths = loaded
    model = table.model()
    user.double_click_cell(model.index(0, model.columnCount() - 1))
    user.press(Key.Key_Tab)
    qtbot.waitUntil(lambda: table.indexWidget(model.index(1, 0)) is not None)
    open_editor(table, model.index(1, 0))


def test_escape_writes_nothing(user, loaded, qtbot):
    # The docs don't say; this is what puddletag does.
    table, paths = loaded
    edit(user, user.cell(0, 'title'), 'New')
    user.press(Key.Key_Escape)
    qtbot.waitUntil(lambda: table.state() == QAbstractItemView.State.NoState)
    qtbot.wait(50)  # where a commit would come, as with Enter
    assert in_file(paths[0]) == {'artist': ['Artist 1'], 'title': ['Title 1']}
    assert in_table(table)[0] == {'artist': ['Artist 1'], 'title': ['Title 1']}
    assert not user.action('&Undo').isEnabled()


def test_emptying_a_cell_removes_the_field(user, loaded, qtbot):
    # "Empty a cell to remove that field from the file."
    table, paths = loaded
    user.double_click_cell(user.cell(0, 'artist'))
    open_editor(table, user.cell(0, 'artist')).selectAll()
    user.press(Key.Key_Delete)
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: 'artist' not in in_file(paths[0]))
    assert in_file(paths[0]) == {'title': ['Title 1']}
    assert in_table(table)[0] == {'title': ['Title 1']}


def test_same_value_writes_nothing(user, loaded, qtbot):
    # The docs don't say; this is what puddletag does: the file isn't
    # saved again, and there's nothing to undo.
    table, paths = loaded
    os.utime(paths[0], (1000000000, 1000000000))
    user.double_click_cell(user.cell(0, 'title'))
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: table.indexWidget(user.cell(1, 'title')) is not None)
    assert os.stat(paths[0]).st_mtime == 1000000000
    assert not user.action('&Undo').isEnabled()


@pytest.mark.parametrize('field, text', [('__bitrate', '1 kb/s'), ('__dirpath', '/elsewhere'),
                                         ('__length', '09:59')])
def test_file_information_cells_drop_the_text(user, loaded, qtbot, field, text):
    # "Some cells show file information that can't be changed, such as
    # Length, Bitrate and Dirpath: what you type in them is dropped." The
    # cell still opens for editing, and Enter moves on as usual.
    table, paths = loaded
    before = table.model().taginfo[0][field]
    edit(user, user.cell(0, field), text)
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: table.indexWidget(user.cell(1, field)) is not None)
    assert table.model().taginfo[0][field] == before
    assert audioinfo.Tag(str(paths[0]))[field] == before
    assert sorted(os.listdir(paths[0].parent)) == ['01.mp3', '02.mp3', '03.mp3']


# "Editing the Filename cell renames the file. The name includes the
# extension: leave it out and the file is renamed without one."

def test_filename_renames_the_file(user, loaded, qtbot):
    table, paths = loaded
    edit(user, user.cell(0, '__filename'), 'Renamed.mp3')
    user.press(Key.Key_Return)
    renamed = paths[0].with_name('Renamed.mp3')
    qtbot.waitUntil(renamed.exists)
    assert sorted(os.listdir(paths[0].parent)) == ['02.mp3', '03.mp3', 'Renamed.mp3']
    assert in_file(renamed) == {'artist': ['Artist 1'], 'title': ['Title 1']}
    assert table.model().taginfo[0].filepath == str(renamed)
    assert table.model().data(user.cell(0, '__filename')) == 'Renamed.mp3'


def test_filename_without_extension(user, loaded, qtbot):
    table, paths = loaded
    edit(user, user.cell(0, '__filename'), 'Bare')
    user.press(Key.Key_Return)
    qtbot.waitUntil(paths[0].with_name('Bare').exists)
    assert sorted(os.listdir(paths[0].parent)) == ['02.mp3', '03.mp3', 'Bare']
    assert table.model().taginfo[0].filepath == str(paths[0].with_name('Bare'))


def test_several_files_one_name(user, loaded, qtbot, dialogs):
    # The docs don't say; this is what puddletag does: the first file is
    # renamed, the second can't be (the name is taken), and nothing is
    # overwritten.
    table, paths = loaded
    user.click_cell(user.cell(0, '__filename'))
    user.click_cell(user.cell(1, '__filename'), Shift)
    dialogs.answer('QMessageBox.exec', QMessageBox.StandardButton.Yes)
    user.press(Key.Key_F2)
    user.type('Same.mp3')
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: len(dialogs.calls) == 1)
    [(name, (box,), kwargs)] = dialogs.calls
    assert 'File exists' in box.text() and '02.mp3' in box.text()
    assert sorted(os.listdir(paths[0].parent)) == ['02.mp3', '03.mp3', 'Same.mp3']
    assert in_file(paths[0].with_name('Same.mp3')) == {'artist': ['Artist 1'], 'title': ['Title 1']}
    assert in_file(paths[1]) == {'artist': ['Artist 2'], 'title': ['Title 2']}
    assert [os.path.basename(a.filepath) for a in table.model().taginfo] == ['Same.mp3', '02.mp3', '03.mp3']
