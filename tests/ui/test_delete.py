"""Delete (menus.txt: "Deletes the selected files permanently"), run as a
user runs it: File→Delete, the right-click menu and Del. Each delete is
checked in the table and on disk. Synthetic files.
"""
import json
import os

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QCheckBox, QMessageBox

from puddlestuff import audioinfo, confirmations
from puddlestuff.puddlesettings import SettingsDialog

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier
Yes = QMessageBox.StandardButton.Yes
No = QMessageBox.StandardButton.No
YesToAll = QMessageBox.StandardButton.YesToAll
QUESTION = ('puddletag', 'Are you sure you want to delete the selected files?')


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


def questions(dialogs):
    """The Delete question's title and text, each time it was asked."""
    return [args[1:] for name, args, kwargs in dialogs.calls if name == 'QMessageBox.question']


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


# Each way the window offers Delete; its other cases press Del.
DELETE = {
    'Del': lambda user, index: user.press(Key.Key_Delete),
    'File menu': lambda user, index: user.click_menu('&Delete'),
    'right-click menu': lambda user, index: user.right_click_cell(index, '&Delete'),
}


@pytest.mark.parametrize('delete', DELETE.values(), ids=DELETE.keys())
def test_delete_answered_yes(mainwin, user, loaded, qtbot, dialogs, delete):
    # Deletes the selected files permanently.
    table, paths = loaded
    index = user.cell(1, 'title')
    user.click_cell(index)
    dialogs.answer('QMessageBox.question', Yes)
    delete(user, index)
    qtbot.waitUntil(lambda: not paths[1].exists())
    assert questions(dialogs) == [QUESTION]
    assert loaded_paths(table) == [str(paths[0]), str(paths[2])]
    assert paths[0].exists() and paths[2].exists()


def test_delete_answered_no(mainwin, user, loaded, qtbot, dialogs):
    # preferences.txt: Confirmations "let you know that you're about to do
    # something that can't be reversed": answered No, nothing is deleted.
    table, paths = loaded
    user.click_cell(user.cell(1, 'title'))
    dialogs.answer('QMessageBox.question', No)
    user.press(Key.Key_Delete)
    assert questions(dialogs) == [QUESTION]
    assert all(p.exists() for p in paths)
    assert loaded_paths(table) == [str(p) for p in paths]


def test_delete_several_files(mainwin, user, loaded, qtbot, dialogs):
    # Deletes the selected files permanently.
    table, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(2, 'title'), Shift)
    dialogs.answer('QMessageBox.question', Yes)
    user.press(Key.Key_Delete)
    qtbot.waitUntil(lambda: not any(p.exists() for p in paths) and table.model().rowCount() == 0)
    user.activate()  # the progress window took the activation when it closed
    assert questions(dialogs) == [QUESTION]
    assert table.model().taginfo == []
    assert not user.action('&Delete').isEnabled()


def test_delete_files_selected_apart(mainwin, user, loaded, qtbot, dialogs):
    # Deletes the selected files permanently; the one between them stays.
    table, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(2, 'title'), Ctrl)
    dialogs.answer('QMessageBox.question', Yes)
    user.press(Key.Key_Delete)
    qtbot.waitUntil(lambda: not paths[0].exists() and not paths[2].exists()
                    and table.model().rowCount() == 1)
    user.activate()
    assert loaded_paths(table) == [str(paths[1])]
    assert paths[1].exists()
    assert in_file(paths[1])['title'] == ['Title 2']


def test_shift_del_asks_too(loaded, user, dialogs):
    # "Deletes the selected files permanently. puddletag asks first, unless
    # that confirmation is turned off in Edit->Preferences->Confirmations."
    # Shift+Del is the same command as Del: the separate Delete Without
    # Confirmation command was removed (issue #399).
    table, paths = loaded
    user.click_cell(user.cell(1, 'title'))
    dialogs.answer('QMessageBox.question', No)
    user.press(Key.Key_Delete, Shift)
    assert questions(dialogs) == [QUESTION]
    assert all(path.exists() for path in paths)
    assert loaded_paths(table) == [str(path) for path in paths]


@pytest.fixture
def restore_confirmations(monkeypatch):
    """The choice is kept in a module-level dict that outlives the window
    and this test's empty profile."""
    monkeypatch.setitem(confirmations._confirmations, 'delete_files',
                        list(confirmations._confirmations['delete_files']))


def confirmations_page(user, mainwin, qtbot):
    """Opens Preferences on its Confirmations page."""
    user.click_menu('&Preferences')
    qtbot.waitUntil(lambda: any(w.isVisible() for w in mainwin.findChildren(SettingsDialog)))
    [window] = [w for w in mainwin.findChildren(SettingsDialog) if w.isVisible()]
    user.activate(window)
    pages = window.listbox.model()
    [row] = [i for i in range(pages.rowCount()) if pages.data(pages.index(i, 0)) == 'Confirmations']
    user.click(window.listbox.viewport(), window.listbox.visualRect(pages.index(row, 0)).center())
    return window


def test_confirmation_turned_off(mainwin, user, loaded, qtbot, dialogs, restore_confirmations):
    # preferences.txt: "Confirmations let you know that you're about to do
    # something that can't be reversed. Turn off the ones that you find grating."
    table, paths = loaded
    window = confirmations_page(user, mainwin, qtbot)
    [box] = [c for c in window.findChildren(QCheckBox) if c.text() == 'Confirm when deleting files.']
    assert box.isChecked()
    user.click(box)
    assert not box.isChecked()
    user.click(window.okbuttons.okButton)
    qtbot.waitUntil(lambda: not window.isVisible())
    user.activate()

    user.click_cell(user.cell(1, 'title'))
    user.press(Key.Key_Delete)
    qtbot.waitUntil(lambda: not paths[1].exists())

    assert dialogs.calls == []
    assert loaded_paths(table) == [str(paths[0]), str(paths[2])]
    with open(confirmations._filename) as f:
        saved = {c['name']: c['value'] for c in json.load(f).values()}
    assert saved == {'delete_files': False, 'preview_mode': True}


def test_undo_greyed_out_after_delete(user, loaded, qtbot, dialogs):
    # "some things like deleting files cannot be undone. When there's nothing
    # left to undo, Undo is greyed out." (menus.txt)
    table, paths = loaded
    user.click_cell(user.cell(1, 'title'))
    dialogs.answer('QMessageBox.question', Yes)
    user.press(Key.Key_Delete)
    qtbot.waitUntil(lambda: not paths[1].exists())
    assert not user.action('&Undo').isEnabled()
    user.click_cell(user.cell(0, 'title'))
    user.press(Key.Key_Z, Ctrl)
    assert not paths[1].exists()
    assert loaded_paths(table) == [str(paths[0]), str(paths[2])]


def test_undo_after_editing_the_deleted_file(user, loaded, qtbot, dialogs):
    # "some things like deleting files cannot be undone. When there's nothing
    # left to undo, Undo is greyed out." (menus.txt)
    table, paths = loaded
    edit(user, qtbot, 1, 'title', 'New')
    qtbot.waitUntil(lambda: in_file(paths[1])['title'] == ['New'])
    user.click_cell(user.cell(1, 'title'))
    dialogs.answer('QMessageBox.question', Yes)
    user.press(Key.Key_Delete)
    qtbot.waitUntil(lambda: not paths[1].exists())
    assert not user.action('&Undo').isEnabled()
    user.press(Key.Key_Z, Ctrl)
    assert not paths[1].exists()
    assert loaded_paths(table) == [str(paths[0]), str(paths[2])]
    assert [in_file(p)['title'] for p in (paths[0], paths[2])] == [['Title 1'], ['Title 3']]
    assert not user.action('&Undo').isEnabled()


def test_undo_after_editing_two_files_and_deleting_one(user, loaded, qtbot, dialogs):
    # "some things like deleting files cannot be undone. When there's nothing
    # left to undo, Undo is greyed out." (menus.txt): what is left to undo is
    # the edit of the file that is still there.
    table, paths = loaded
    edit(user, qtbot, 0, 'title', 'New 1')
    qtbot.waitUntil(lambda: in_file(paths[0])['title'] == ['New 1'])
    edit(user, qtbot, 1, 'title', 'New 2')
    qtbot.waitUntil(lambda: in_file(paths[1])['title'] == ['New 2'])
    user.click_cell(user.cell(1, 'title'))
    dialogs.answer('QMessageBox.question', Yes)
    user.press(Key.Key_Delete)
    qtbot.waitUntil(lambda: not paths[1].exists())
    assert user.action('&Undo').isEnabled()
    user.press(Key.Key_Z, Ctrl)
    assert shown(user, 0, 'title')[0] == 'Title 1'
    qtbot.waitUntil(lambda: in_file(paths[0])['title'] == ['Title 1'])
    assert not user.action('&Undo').isEnabled()


def test_undo_greyed_out_after_deleting_a_previewed_file(user, loaded, qtbot, dialogs):
    # "some things like deleting files cannot be undone. When there's nothing
    # left to undo, Undo is greyed out." (menus.txt)
    table, paths = loaded
    user.press(Key.Key_P, Ctrl | Shift)
    edit(user, qtbot, 1, 'title', 'New')
    assert in_file(paths[1])['title'] == ['Title 2']
    user.click_cell(user.cell(1, 'title'))
    dialogs.answer('QMessageBox.question', Yes)
    user.press(Key.Key_Delete)
    qtbot.waitUntil(lambda: not paths[1].exists())
    assert not user.action('&Undo').isEnabled()
    assert loaded_paths(table) == [str(paths[0]), str(paths[2])]


@pytest.fixture
def two_folders(mainwin, make_audio, tmp_path, qtbot, user):
    """a1 and a2 in a read-only folder, b1 and b2 in another."""
    a = [make_audio(f'a{i}.mp3', tmp_path / 'a', title=f'A{i}') for i in (1, 2)]
    b = [make_audio(f'b{i}.mp3', tmp_path / 'b', title=f'B{i}') for i in (1, 2)]
    table = mainwin._table
    mainwin.openDir(str(tmp_path / 'a'), False)
    qtbot.waitUntil(lambda: table.model().rowCount() == 2)
    mainwin.openDir(str(tmp_path / 'b'), True)  # Add Folder
    qtbot.waitUntil(lambda: table.model().rowCount() == 4)
    assert loaded_paths(table) == [str(p) for p in a + b]
    user.activate()
    table.setFocus()
    os.chmod(tmp_path / 'a', 0o555)
    yield table, a, b
    os.chmod(tmp_path / 'a', 0o755)


def couldnt_delete(path):
    return f"I couldn't delete <b>{path}</b> (Permission denied)"


@pytest.mark.skipif(os.geteuid() == 0, reason='root can delete from a read-only folder')
def test_file_that_cannot_be_deleted(user, loaded, dialogs):
    # Delete: "Deletes the selected files permanently." A file the folder's
    # permissions keep, as the program behaves (the docs are silent): the
    # user is told why, and the row and the file stay.
    table, paths = loaded
    os.chmod(paths[1].parent, 0o555)
    try:
        user.click_cell(user.cell(1, 'title'))
        dialogs.answer('QMessageBox.question', Yes)
        dialogs.answer('QMessageBox.warning', QMessageBox.StandardButton.Ok)
        user.press(Key.Key_Delete)
        [args] = [args for name, args, kwargs in dialogs.calls if name == 'QMessageBox.warning']
    finally:
        os.chmod(paths[1].parent, 0o755)
    assert args[1:] == ('Error', couldnt_delete(paths[1]))
    assert all(p.exists() for p in paths)
    assert loaded_paths(table) == [str(p) for p in paths]


@pytest.mark.skipif(os.geteuid() == 0, reason='root can delete from a read-only folder')
@pytest.mark.parametrize('answers, asked_about, deleted, rows', [
    ((No,), ['a1'], [], ['a1', 'a2', 'b1', 'b2']),
    ((Yes, Yes), ['a1', 'a2'], ['b1', 'b2'], ['a1', 'a2']),
    ((YesToAll,), ['a1'], ['b1', 'b2'], ['a1', 'a2']),
], ids=['No', 'Yes', 'Yes to All'])
def test_error_with_several_files(user, two_folders, dialogs, qtbot, answers, asked_about, deleted, rows):
    # Delete: "Deletes the selected files permanently." With several files
    # selected and one that can't be deleted, as the program behaves (the
    # docs are silent): it asks whether to go on. Yes goes on and asks
    # again at the next failing file, No stops, Yes to All asks no more.
    table, a, b = two_folders
    named = {'a1': a[0], 'a2': a[1], 'b1': b[0], 'b2': b[1]}
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(3, 'title'), Shift)
    dialogs.answer('QMessageBox.question', Yes)
    dialogs.answer('QMessageBox.exec', *answers)
    user.press(Key.Key_Delete)
    if deleted:
        qtbot.waitUntil(lambda: not b[1].exists() and table.model().rowCount() == 2)
    user.activate()
    assert [args[0].text() for name, args, kwargs in dialogs.calls if name == 'QMessageBox.exec'] \
        == [couldnt_delete(named[name]) + '<br /> Do you want to continue?' for name in asked_about]
    assert [name for name, path in named.items() if not path.exists()] == deleted
    assert loaded_paths(table) == [str(named[name]) for name in rows]


def test_delete_in_preview_mode(loaded, user, qtbot, dialogs):
    # menus.txt: "Deletes the selected files permanently." In Preview Mode the
    # delete isn't staged as a preview: the file goes from disk at once, and
    # the other files' unwritten previews stay.
    table, paths = loaded
    user.press(Key.Key_P, Ctrl | Shift)
    edit(user, qtbot, 0, 'title', 'New 1')
    edit(user, qtbot, 1, 'title', 'New 2')
    user.click_cell(user.cell(1, 'title'))
    dialogs.answer('QMessageBox.question', Yes)
    user.press(Key.Key_Delete)
    qtbot.waitUntil(lambda: not paths[1].exists())
    assert loaded_paths(table) == [str(paths[0]), str(paths[2])]
    assert shown(user, 0, 'title') == ('New 1', 'bold')
    assert in_file(paths[0])['title'] == ['Title 1']
