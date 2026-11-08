"""Undo (menus.txt: "Undo's the last edit"), run as a user runs it: the
toolbar button, Edit→Undo or Ctrl+Z. Each undo is checked in the files and
in the table. Synthetic files.
"""
import os

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


# "Undo's the last edit", from each place it's offered. "When there's
# nothing left to undo, Undo is greyed out."

UNDO = {
    'toolbar': lambda user: user.click_toolbar('&Undo'),
    'Edit menu': lambda user: user.click_menu('&Undo'),
    'Ctrl+Z': lambda user: user.press(Key.Key_Z, Ctrl),
}


@pytest.mark.parametrize('undo', UNDO.values(), ids=UNDO.keys())
def test_undo(user, loaded, qtbot, undo):
    table, paths = loaded
    assert not user.action('&Undo').isEnabled()
    edit(user, qtbot, 0, 'New', paths[0])
    assert user.action('&Undo').isEnabled()
    undo(user)
    assert in_file(paths[0])['title'] == ['Title 1']
    assert titles(table)[str(paths[0])] == ['Title 1']
    assert not user.action('&Undo').isEnabled()


def test_edits_undone_in_reverse_order(user, loaded, qtbot):
    table, paths = loaded
    edit(user, qtbot, 0, 'First', paths[0])
    edit(user, qtbot, 0, 'Second', paths[0])
    edit(user, qtbot, 1, 'Other', paths[1])
    after_each = []
    for i in range(3):
        user.click_toolbar('&Undo')
        after_each.append([in_file(p)['title'] for p in paths[:2]])
    assert after_each == [[['Second'], ['Title 2']],
                          [['First'], ['Title 2']],
                          [['Title 1'], ['Title 2']]]
    assert not user.action('&Undo').isEnabled()


def select_all(user, paths):
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(len(paths) - 1, 'title'), Shift)


def set_pattern(user, pattern):
    """F8 goes to the Pattern Combo, its text selected, and back
    (tut3.txt: "Pressing F8 switches focus between it and the
    file-view")."""
    user.press(Key.Key_F8)
    user.type(pattern)
    user.press(Key.Key_F8)


# A command that writes several files is one edit: one Undo puts them all
# back.

def test_format_undone_in_one_step(user, loaded, qtbot):
    table, paths = loaded
    select_all(user, paths)
    set_pattern(user, '%artist% - %title%')
    user.click_toolbar('&Format')
    qtbot.waitUntil(lambda: in_file(paths[2])['title'] == ['Artist 3 - Title 3'])
    user.activate()
    user.click_toolbar('&Undo')
    assert [in_file(p)['title'] for p in paths] == [['Title 1'], ['Title 2'], ['Title 3']]
    assert not user.action('&Undo').isEnabled()


def test_tag_to_file_undone_in_one_step(user, loaded, qtbot):
    # The renames are undone too: the files get their names back.
    table, paths = loaded
    select_all(user, paths)
    set_pattern(user, '%artist% - %title%')
    user.press(Key.Key_F, Ctrl)
    qtbot.waitUntil(lambda: os.path.exists(paths[2].with_name('Artist 3 - Title 3.mp3')))
    user.activate()
    user.click_toolbar('&Undo')
    assert sorted(os.listdir(paths[0].parent)) == ['01.mp3', '02.mp3', '03.mp3']
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]
    assert not user.action('&Undo').isEnabled()


def test_action_undone_in_one_step(user, loaded, qtbot):
    # The default action Case Conversion, run from Actions → Actions.
    table, paths = loaded
    edit_all(user, qtbot, 'lower case', paths)
    user.click_menu('&Actions')
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is not None)
    window = QApplication.activeModalWidget()
    user.activate(window)
    [item] = window.listbox.findItems('Case Conversion', Qt.MatchFlag.MatchExactly)
    user.click(window.listbox.viewport(), window.listbox.visualItemRect(item).center())
    user.press(Key.Key_Space)
    assert item.checkState() == Qt.CheckState.Checked
    user.click(window.okcancel.okButton)
    qtbot.waitUntil(lambda: all(in_file(p)['title'] == ['Lower Case'] for p in paths))
    user.activate()
    user.click_toolbar('&Undo')
    assert [in_file(p)['title'] for p in paths] == [['lower case']] * 3
    assert user.action('&Undo').isEnabled()  # the edit before it


# "the undo history is cleared when a new folder is imported using Open
# Folder, by Refresh and by Unload Everything (but not by Add Folder)"
# (menus.txt)

def test_open_folder_clears_the_history(user, loaded, qtbot, dialogs):
    table, paths = loaded
    edit(user, qtbot, 0, 'New', paths[0])
    dialogs.answer('QFileDialog.getExistingDirectory', str(paths[0].parent))
    user.press(Key.Key_O, Ctrl)
    qtbot.waitUntil(lambda: not user.action('&Undo').isEnabled())
    qtbot.waitUntil(lambda: table.model().rowCount() == 3)
    assert in_file(paths[0])['title'] == ['New']


def test_refresh_clears_the_history(user, loaded, qtbot):
    table, paths = loaded
    edit(user, qtbot, 0, 'New', paths[0])
    user.press(Key.Key_F5)
    qtbot.waitUntil(lambda: not user.action('&Undo').isEnabled())
    assert in_file(paths[0])['title'] == ['New']


def test_add_folder_keeps_the_history(user, loaded, qtbot, dialogs, make_audio, tmp_path):
    table, paths = loaded
    other = make_audio('04.mp3', tmp_path / 'other', title='Title 4')
    edit(user, qtbot, 0, 'New', paths[0])
    dialogs.answer('QFileDialog.getExistingDirectory', str(other.parent))
    user.click_menu('&Add Folder')
    qtbot.waitUntil(lambda: table.model().rowCount() == 4)
    user.click_toolbar('&Undo')
    assert in_file(paths[0])['title'] == ['Title 1']
    assert titles(table)[str(paths[0])] == ['Title 1']


# menus.txt: "If a file can't be written, puddletag says so as it does for
# any write and goes on with the other files; the files it couldn't restore
# stay in the undo history, so Undo stays available: fix the file (its
# permissions, say) and undo again." Here the file is read-only (synthetic:
# 0444). Before, the error closed puddletag.

def read_only(*paths):
    for path in paths:
        os.chmod(path, 0o444)


def writable(*paths):
    for path in paths:
        os.chmod(path, 0o644)


def asked(dialogs):
    """The write-error messages shown, as (kind, text)."""
    return [(name, args[2] if name == 'QMessageBox.warning' else args[0].text())
            for name, args, kwargs in dialogs.calls]


@pytest.mark.skipif(os.geteuid() == 0, reason='root can write a read-only file')
@pytest.mark.xfail(strict=True, reason='an Undo whose write fails raises out of the command instead of reporting it')
def test_undo_of_a_read_only_file_says_why_and_stays_on(user, loaded, qtbot, dialogs):
    # "puddletag says so as it does for any write" and "Undo stays available".
    table, paths = loaded
    edit(user, qtbot, 0, 'New', paths[0])
    read_only(paths[0])
    dialogs.answer('QMessageBox.warning', QMessageBox.StandardButton.Ok)
    user.press(Key.Key_Z, Ctrl)
    [(kind, text)] = asked(dialogs)
    assert kind == 'QMessageBox.warning'
    assert str(paths[0]) in text
    assert 'Permission denied' in text
    assert in_file(paths[0])['title'] == ['New']
    assert titles(table)[str(paths[0])] == ['New']
    assert user.action('&Undo').isEnabled()
    writable(paths[0])
    user.press(Key.Key_Z, Ctrl)
    assert in_file(paths[0])['title'] == ['Title 1']
    assert titles(table)[str(paths[0])] == ['Title 1']
    assert not user.action('&Undo').isEnabled()


@pytest.mark.skipif(os.geteuid() == 0, reason='root can write a read-only file')
@pytest.mark.xfail(strict=True, reason='an Undo whose write fails raises out of the command instead of reporting it')
def test_undo_goes_on_after_a_file_it_cant_write(user, loaded, qtbot, dialogs):
    # "goes on with the other files; the files it couldn't restore stay in
    # the undo history".
    table, paths = loaded
    edit_all(user, qtbot, 'Same', paths)
    read_only(paths[0])
    dialogs.answer('QMessageBox.exec', QMessageBox.StandardButton.Yes)
    user.press(Key.Key_Z, Ctrl)
    [(kind, text)] = asked(dialogs)
    assert kind == 'QMessageBox.exec'
    assert str(paths[0]) in text
    assert 'Do you want to continue?' in text
    assert [in_file(p)['title'] for p in paths] == [['Same'], ['Title 2'], ['Title 3']]
    assert [titles(table)[str(p)] for p in paths] == [['Same'], ['Title 2'], ['Title 3']]
    assert user.action('&Undo').isEnabled()
    writable(paths[0])
    user.press(Key.Key_Z, Ctrl)
    assert [in_file(p)['title'] for p in paths] == [['Title 1'], ['Title 2'], ['Title 3']]
    assert [titles(table)[str(p)] for p in paths] == [['Title 1'], ['Title 2'], ['Title 3']]
    assert not user.action('&Undo').isEnabled()


@pytest.mark.skipif(os.geteuid() == 0, reason='root can write a read-only file')
@pytest.mark.xfail(strict=True, reason='an Undo whose write fails raises out of the command instead of reporting it')
def test_no_stops_the_undo(user, loaded, qtbot, dialogs):
    # "says so as it does for any write": No stops, and the files not
    # reached stay in the undo history.
    table, paths = loaded
    edit_all(user, qtbot, 'Same', paths)
    read_only(paths[0])
    dialogs.answer('QMessageBox.exec', QMessageBox.StandardButton.No)
    user.press(Key.Key_Z, Ctrl)
    assert [in_file(p)['title'] for p in paths] == [['Same']] * 3
    assert [titles(table)[str(p)] for p in paths] == [['Same']] * 3
    assert user.action('&Undo').isEnabled()
    writable(paths[0])
    user.press(Key.Key_Z, Ctrl)
    assert [in_file(p)['title'] for p in paths] == [['Title 1'], ['Title 2'], ['Title 3']]
    assert [titles(table)[str(p)] for p in paths] == [['Title 1'], ['Title 2'], ['Title 3']]
    assert not user.action('&Undo').isEnabled()


@pytest.mark.skipif(os.geteuid() == 0, reason='root can write a read-only file')
@pytest.mark.xfail(strict=True, reason='an Undo whose write fails raises out of the command instead of reporting it')
def test_yes_to_all_stops_asking(user, loaded, qtbot, dialogs):
    # "says so as it does for any write": Yes to All doesn't ask again.
    table, paths = loaded
    edit_all(user, qtbot, 'Same', paths)
    read_only(paths[0], paths[1])
    dialogs.answer('QMessageBox.exec', QMessageBox.StandardButton.YesToAll)
    user.press(Key.Key_Z, Ctrl)
    [(kind, text)] = asked(dialogs)
    assert str(paths[0]) in text
    assert [in_file(p)['title'] for p in paths] == [['Same'], ['Same'], ['Title 3']]
    assert [titles(table)[str(p)] for p in paths] == [['Same'], ['Same'], ['Title 3']]
    assert user.action('&Undo').isEnabled()
    writable(paths[0], paths[1])
    user.press(Key.Key_Z, Ctrl)
    assert [in_file(p)['title'] for p in paths] == [['Title 1'], ['Title 2'], ['Title 3']]
    assert [titles(table)[str(p)] for p in paths] == [['Title 1'], ['Title 2'], ['Title 3']]
    assert not user.action('&Undo').isEnabled()


@pytest.mark.skipif(os.geteuid() == 0, reason='root can write a read-only file')
@pytest.mark.xfail(strict=True, reason='an Undo whose write fails raises out of the command instead of reporting it')
def test_last_file_failing_is_a_warning(user, loaded, qtbot, dialogs):
    # "says so as it does for any write": the last file gets a warning, not
    # a question.
    table, paths = loaded
    edit_all(user, qtbot, 'Same', paths)
    read_only(paths[2])
    dialogs.answer('QMessageBox.warning', QMessageBox.StandardButton.Ok)
    user.press(Key.Key_Z, Ctrl)
    [(kind, text)] = asked(dialogs)
    assert kind == 'QMessageBox.warning'
    assert str(paths[2]) in text
    assert [in_file(p)['title'] for p in paths] == [['Title 1'], ['Title 2'], ['Same']]
    assert [titles(table)[str(p)] for p in paths] == [['Title 1'], ['Title 2'], ['Same']]
    assert user.action('&Undo').isEnabled()
    writable(paths[2])
    user.press(Key.Key_Z, Ctrl)
    assert [in_file(p)['title'] for p in paths] == [['Title 1'], ['Title 2'], ['Title 3']]
    assert [titles(table)[str(p)] for p in paths] == [['Title 1'], ['Title 2'], ['Title 3']]
    assert not user.action('&Undo').isEnabled()
