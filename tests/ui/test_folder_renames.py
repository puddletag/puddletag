"""Renaming a folder from the File-View, as a user does: typing into a
Dirname cell (tut3.txt: "Editing a Dirname cell renames the file's folder,
and every file in it moves along") or Convert > Rename Directories
(menus.txt: "Renames the selected files' directories based on the pattern
in Pattern Combo"). Each rename is checked in the table and on disk.
Synthetic files.
"""
import os

import pytest
from PyQt6.QtCore import Qt

from puddlestuff.mainwin.filterwin import FilterView

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier


def load(mainwin, qtbot, user, folder, count, append=False):
    """Opens the folder (or adds it, as Add Folder does) and waits for its
    files; the window is active and the table focused."""
    mainwin.openDir(str(folder), append)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == count)
    user.activate()
    table.setFocus()
    return table


def show_dirname(table):
    table.setHeaderTags(table.model().headerdata + [('__dirname', '__dirname')])


def row_of(table, path):
    return [audio.filepath for audio in table.model().taginfo].index(str(path))


def type_dirname(user, row, text):
    index = user.cell(row, '__dirname')
    user.double_click_cell(index)
    user.table.indexWidget(index).selectAll()
    user.type(text)
    user.press(Key.Key_Return)


def set_pattern(user, pattern):
    """F8 goes to the Pattern Combo, its text selected, and back (tut3.txt:
    "Pressing F8 switches focus between it and the file-view"). Delete drops
    the rest of a saved pattern that the combo completes the typed text to."""
    user.press(Key.Key_F8)
    user.type(pattern)
    user.press(Key.Key_Delete)
    user.press(Key.Key_F8)


def enter_filter(user, mainwin, text):
    """Clicks into the Filter box, types over its text and presses Enter."""
    [view] = mainwin.findChildren(FilterView)
    user.click(view.combo.combo.lineEdit())
    user.press(Key.Key_A, Ctrl)
    if text:
        user.type(text)
    else:
        user.press(Key.Key_Delete)
    user.press(Key.Key_Return)


def in_table(table):
    return sorted(audio.filepath for audio in table.model().taginfo)


@pytest.mark.xfail(strict=True, reason='renaming Album also renamed the loaded folder Album 2 to New 2 '
                                       'in the list Refresh re-reads')
def test_refresh_rereads_a_folder_named_like_the_renamed_one(mainwin, make_audio, tmp_path, qtbot, user):
    # menus.txt: Rename Directories "Renames the selected files' directories
    # based on the pattern in Pattern Combo"; Refresh (F5) "If any
    # directories are loaded, they'll be re-read and checked for new files."
    # Album 2 isn't Album's subfolder, so renaming Album leaves it alone.
    m = tmp_path / 'm'
    make_audio('01.mp3', m / 'Album', album='New', title='One')
    make_audio('02.mp3', m / 'Album 2', album='Other', title='Two')
    table = load(mainwin, qtbot, user, m / 'Album', 1)
    load(mainwin, qtbot, user, m / 'Album 2', 2, append=True)
    user.click_cell(user.cell(row_of(table, m / 'Album' / '01.mp3'), 'title'))
    set_pattern(user, '%album%')
    user.click_menu('&Rename Directories')
    qtbot.waitUntil((m / 'New' / '01.mp3').exists)
    make_audio('03.mp3', m / 'Album 2', title='Three')
    user.activate()
    table.setFocus()
    user.press(Key.Key_F5)
    qtbot.waitUntil(lambda: table.model().rowCount() == 3)
    assert in_table(table) == [str(m / 'Album 2' / '02.mp3'), str(m / 'Album 2' / '03.mp3'),
                               str(m / 'New' / '01.mp3')]
    assert sorted(os.listdir(m)) == ['Album 2', 'New']


@pytest.mark.xfail(strict=True, reason='a file two folders down keeps its old path in the File-View')
def test_files_deeper_down_move_along(mainwin, make_audio, tmp_path, qtbot, user):
    # tut3.txt: "Editing a Dirname cell renames the file's folder, and every
    # file in it moves along".
    m = tmp_path / 'm'
    make_audio('01.mp3', m / 'Album', title='One')
    make_audio('02.mp3', m / 'Album' / 'CD1', title='Two')
    make_audio('03.mp3', m / 'Album' / 'CD1' / 'Disc', title='Three')
    table = load(mainwin, qtbot, user, m, 3)
    show_dirname(table)
    type_dirname(user, row_of(table, m / 'Album' / '01.mp3'), 'New')
    qtbot.waitUntil((m / 'New' / '01.mp3').exists)
    expected = [str(m / 'New' / '01.mp3'), str(m / 'New' / 'CD1' / '02.mp3'),
                str(m / 'New' / 'CD1' / 'Disc' / '03.mp3')]
    assert in_table(table) == expected
    assert all(os.path.exists(path) for path in expected)


@pytest.mark.xfail(strict=True, reason='a file the Filter hides keeps its old path after its folder is renamed')
def test_a_hidden_file_moves_along(mainwin, make_audio, tmp_path, qtbot, user):
    # tut3.txt: "Editing a Dirname cell renames the file's folder, and every
    # file in it moves along"; filter.txt: "Otherwise, puddletag will hide
    # it". A file the Filter hides is still in the folder.
    music = tmp_path / 'music'
    make_audio('01.mp3', music / 'unsorted', artist='Bongo Maffin', title='Monster')
    make_audio('02.mp3', music / 'unsorted', artist='Jon Smith', title='Angel')
    table = load(mainwin, qtbot, user, music, 2)
    show_dirname(table)
    enter_filter(user, mainwin, 'Maffin')
    qtbot.waitUntil(lambda: table.model().rowCount() == 1)
    table.setFocus()
    type_dirname(user, 0, 'New')
    qtbot.waitUntil((music / 'New' / '01.mp3').exists)
    enter_filter(user, mainwin, '')
    qtbot.waitUntil(lambda: table.model().rowCount() == 2)
    expected = [str(music / 'New' / '01.mp3'), str(music / 'New' / '02.mp3')]
    assert in_table(table) == expected
    assert all(os.path.exists(path) for path in expected)
