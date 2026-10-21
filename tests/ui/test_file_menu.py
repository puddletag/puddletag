"""The File menu (menus.txt), run as a user runs it: from the menu, the
toolbar, the shortcuts and the right-click menu, with each file dialog
answered. Each command is checked in the table and on disk. Synthetic
files.
"""
import os

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QCheckBox, QLabel, QMessageBox, QStyle, QStyleOptionButton

from puddlestuff import audioinfo
from puddlestuff.puddleobjects import PuddleConfig
from puddlestuff.puddlesettings import SettingsDialog

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier
No = QMessageBox.StandardButton.No
Yes = QMessageBox.StandardButton.Yes


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    """music/01.mp3 and music/02.mp3, opened."""
    music = tmp_path / 'music'
    paths = [make_audio(f'0{i}.mp3', music, artist=f'Artist {i}', title=f'Title {i}')
             for i in (1, 2)]
    mainwin.openDir(str(music), False)
    table = mainwin._table
    wait_for_rows(qtbot, table, paths)
    user.activate()
    table.setFocus()
    return table, paths


def in_file(path):
    return audioinfo.usertags(audioinfo.Tag(str(path)))


def loaded_paths(table):
    return [audio.filepath for audio in table.model().taginfo]


def wait_for_rows(qtbot, table, paths):
    """Files load through a progress window: wait for the rows."""
    expected = [str(p) for p in paths]
    qtbot.waitUntil(lambda: loaded_paths(table) == expected)


def edit(user, qtbot, row, field, text):
    """Types text into the row's cell."""
    user.double_click_cell(user.cell(row, field))
    QApplication.focusWidget().selectAll()
    user.type(text)
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: user.table.model().data(user.cell(row, field)) == text)
    user.press(Key.Key_Escape)  # the next row's cell, which Enter opened


def select_rows(user, first, last):
    user.click_cell(user.cell(first, 'title'))
    user.click_cell(user.cell(last, 'title'), Shift)


def open_preferences(mainwin, qtbot, user, page='General'):
    """Edit→Preferences, on the page clicked in its list."""
    user.click_menu('&Preferences')
    qtbot.waitUntil(lambda: any(w.isVisible() for w in mainwin.findChildren(SettingsDialog)))
    [window] = [w for w in mainwin.findChildren(SettingsDialog) if w.isVisible()]
    user.activate(window)
    [row] = [r for r, (title, *_) in window._widgets.items() if title == page]
    index = window.model.index(row, 0)
    user.click(window.listbox.viewport(), window.listbox.visualRect(index).center())
    qtbot.waitUntil(lambda: window.stack.currentWidget() is window._widgets[row][1])
    return window


def close_preferences(window, qtbot, user):
    user.click(window.okbuttons.okButton)
    qtbot.waitUntil(lambda: not window.isVisible())
    user.activate()


def set_check_box(user, window, text, checked):
    """Clicks the box's indicator if it isn't as wanted: the box stretches
    across the page, and a click at its center misses the label."""
    [box] = [c for c in window.findChildren(QCheckBox) if c.text() == text]
    if box.isChecked() != checked:
        option = QStyleOptionButton()
        box.initStyleOption(option)
        rect = box.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, box)
        user.click(box, rect.center())
    assert box.isChecked() == checked


def set_text(user, field, text):
    user.click(field)
    field.selectAll()
    user.type(text)


def labelled(window, text):
    """The field a label names."""
    [label] = [w for w in window.findChildren(QLabel) if w.text() == text]
    return label.buddy()


def set_subfolders(mainwin, qtbot, user, checked):
    window = open_preferences(mainwin, qtbot, user)
    set_check_box(user, window, 'Su&bfolders', checked)
    close_preferences(window, qtbot, user)


def player(tmp_path):
    """A program that writes the arguments it gets, one per line, to
    player.txt beside it, whole or not at all."""
    path = tmp_path / 'player'
    path.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$0.tmp" && mv "$0.tmp" "$0.txt"\n')
    path.chmod(0o755)
    return path


# Each way the window offers Open Folder and Add Folder.
OPEN = {
    'File menu': lambda user: user.click_menu('&Open Folder'),
    'shortcut': lambda user: user.press(Key.Key_O, Ctrl),
    'toolbar': lambda user: user.click_toolbar('&Open Folder'),
}
ADD = {
    'File menu': lambda user: user.click_menu('&Add Folder'),
    'toolbar': lambda user: user.click_toolbar('&Add Folder'),
}

GET_DIRECTORY = 'QFileDialog.getExistingDirectory'


@pytest.mark.parametrize('open_folder', OPEN.values(), ids=OPEN.keys())
def test_open_folder(mainwin, make_audio, tmp_path, qtbot, user, dialogs, open_folder):
    # "Imports a folder into puddletag. All files with supported/valid tags
    # are read."
    music = tmp_path / 'music'
    p1 = make_audio('01.mp3', music, artist='Artist 1', title='Title 1')
    p2 = make_audio('02.mp3', music, artist='Artist 2', title='Title 2')
    (music / 'notes.txt').write_text('not audio')
    table = mainwin._table
    user.activate()
    table.setFocus()
    dialogs.answer(GET_DIRECTORY, str(music))
    open_folder(user)
    wait_for_rows(qtbot, table, [p1, p2])
    assert [a['title'] for a in table.model().taginfo] == [['Title 1'], ['Title 2']]
    assert in_file(p1)['title'] == ['Title 1']


def test_open_folder_replaces_the_files(mainwin, make_audio, tmp_path, qtbot, user, dialogs, loaded):
    # Add Folder: "Works as Open Folder, but instead of replacing the
    # File-Views's contents, appends the newly loaded files."
    table, paths = loaded
    p3 = make_audio('03.mp3', tmp_path / 'other', artist='Artist 3', title='Title 3')
    dialogs.answer(GET_DIRECTORY, str(p3.parent))
    user.click_menu('&Open Folder')
    wait_for_rows(qtbot, table, [p3])


def test_open_folder_cancelled(mainwin, user, dialogs, loaded):
    # Synthetic (docs-silent): Cancel in the dialog leaves the table as it
    # was.
    table, paths = loaded
    dialogs.answer(GET_DIRECTORY, '')
    user.click_menu('&Open Folder')
    assert loaded_paths(table) == [str(p) for p in paths]


def test_open_folder_starts_in_the_last_folder(mainwin, user, dialogs, loaded):
    # Synthetic (docs-silent, #352): the dialog starts in the last loaded
    # folder.
    table, paths = loaded
    dialogs.answer(GET_DIRECTORY, '')
    user.click_menu('&Open Folder')
    assert dialogs.calls[-1][1][2] == str(paths[0].parent)


def test_subfolders_off(mainwin, make_audio, tmp_path, qtbot, user, dialogs):
    # "Otherwise, just files residing in the selected directories will be
    # loaded."
    a = tmp_path / 'a'
    p1 = make_audio('01.mp3', a, artist='Artist 1', title='Title 1')
    make_audio('02.mp3', a / 'sub', artist='Artist 2', title='Title 2')
    set_subfolders(mainwin, qtbot, user, False)
    dialogs.answer(GET_DIRECTORY, str(a))
    user.click_menu('&Open Folder')
    wait_for_rows(qtbot, mainwin._table, [p1])


def test_subfolders_on(mainwin, make_audio, tmp_path, qtbot, user, dialogs):
    # "If checked, Subfolders of directories selected for import will be
    # checked for supported files (which'll then be loaded)."
    a = tmp_path / 'a'
    p1 = make_audio('01.mp3', a, artist='Artist 1', title='Title 1')
    p2 = make_audio('02.mp3', a / 'sub', artist='Artist 2', title='Title 2')
    set_subfolders(mainwin, qtbot, user, True)
    dialogs.answer(GET_DIRECTORY, str(a))
    user.click_menu('&Open Folder')
    wait_for_rows(qtbot, mainwin._table, [p1, p2])


@pytest.mark.parametrize('add', ADD.values(), ids=ADD.keys())
def test_add_folder(mainwin, make_audio, tmp_path, qtbot, user, dialogs, loaded, add):
    # "Works as Open Folder, but instead of replacing the File-Views's
    # contents, appends the newly loaded files."
    table, paths = loaded
    p3 = make_audio('03.mp3', tmp_path / 'other', artist='Artist 3', title='Title 3')
    dialogs.answer(GET_DIRECTORY, str(p3.parent))
    add(user)
    wait_for_rows(qtbot, table, [*paths, p3])


def test_add_folder_greyed_out_before_any_folder(mainwin, user):
    # Synthetic (docs-silent): Add Folder is greyed out before anything is
    # loaded.
    assert not user.action('&Add Folder').isEnabled()


def test_add_folder_keeps_previews(mainwin, make_audio, tmp_path, qtbot, user, dialogs, loaded):
    # "Works as Open Folder, but instead of replacing the File-Views's
    # contents, appends the newly loaded files": the shown rows stay as
    # they are, and "any values you change that differ from the original
    # will be shown as emboldened text".
    table, paths = loaded
    p3 = make_audio('03.mp3', tmp_path / 'other', artist='Artist 3', title='Title 3')
    user.click_menu('Enabl&e Preview Mode')
    edit(user, qtbot, 0, 'title', 'New')
    dialogs.answer(GET_DIRECTORY, str(p3.parent))
    user.click_menu('&Add Folder')
    wait_for_rows(qtbot, table, [*paths, p3])
    model = table.model()
    index = user.cell(0, 'title')
    assert model.data(index) == 'New'
    assert model.data(index, Qt.ItemDataRole.FontRole).bold()
    assert in_file(paths[0])['title'] == ['Title 1']


def test_open_folder_with_previews_asks(mainwin, make_audio, tmp_path, qtbot, user, dialogs, loaded):
    # Synthetic (docs-silent): like Refresh and Exit, Open Folder asks
    # before dropping unsaved previews; No keeps the table as it was.
    table, paths = loaded
    p3 = make_audio('03.mp3', tmp_path / 'other', artist='Artist 3', title='Title 3')
    user.click_menu('Enabl&e Preview Mode')
    edit(user, qtbot, 0, 'title', 'New')
    dialogs.answer(GET_DIRECTORY, str(p3.parent))
    dialogs.answer('QMessageBox.question', No)
    user.click_menu('&Open Folder')
    qtbot.waitUntil(lambda: not dialogs.unused_answers(), timeout=2000)
    assert loaded_paths(table) == [str(p) for p in paths]
    model = table.model()
    index = user.cell(0, 'title')
    assert model.data(index) == 'New'
    assert model.data(index, Qt.ItemDataRole.FontRole).bold()


# Refresh, Refresh Selected and Unload Everything

REFRESH = {
    'File menu': lambda user: user.click_menu('&Refresh'),
    'shortcut': lambda user: user.press(Key.Key_F5),
    'toolbar': lambda user: user.click_toolbar('&Refresh'),
}


def two_folders(mainwin, make_audio, qtbot, tmp_path, user):
    """a/01.mp3, a/02.mp3 and b/03.mp3, opened one folder after the other."""
    a, b = tmp_path / 'a', tmp_path / 'b'
    paths = [make_audio('01.mp3', a, title='Title 1'),
             make_audio('02.mp3', a, title='Title 2'),
             make_audio('03.mp3', b, title='Title 3')]
    table = mainwin._table
    mainwin.openDir(str(a), False)
    wait_for_rows(qtbot, table, paths[:2])
    mainwin.openDir(str(b), True)
    wait_for_rows(qtbot, table, paths)
    user.activate()
    return table, paths


def change_on_disk(path, title):
    tag = audioinfo.Tag(str(path))
    tag['title'] = [title]
    tag.save()


@pytest.mark.parametrize('run', REFRESH.values(), ids=REFRESH)
def test_refresh(mainwin, make_audio, user, loaded, qtbot, run):
    # menus.txt: "Refreshes the files currently loaded in the File-View. If
    # any directories are loaded, they'll be re-read and checked for new
    # files." tut2.txt: "it re-reads those files again (useful if you've
    # moved or deleted files outside of puddletag)."
    table, paths = loaded
    paths[1].unlink()
    p3 = make_audio('03.mp3', paths[0].parent, title='Title 3')
    change_on_disk(paths[0], 'Changed')

    run(user)

    wait_for_rows(qtbot, table, [paths[0], p3])
    assert table.model().taginfo[0]['title'] == ['Changed']


@pytest.mark.parametrize('answer', [No, Yes], ids=['No', 'Yes'])
def test_refresh_with_previews_asks(mainwin, user, loaded, qtbot, dialogs, answer):
    # Docs-silent: with unsaved previews Refresh asks "There are unsaved
    # changes pending. Do you want to discard and reload?"; No keeps
    # everything, Yes re-reads and drops the previews, Preview Mode stays on.
    table, paths = loaded
    model = table.model()
    user.click_menu('Enabl&e Preview Mode')
    edit(user, qtbot, 0, 'title', 'New')
    paths[1].unlink()
    dialogs.answer('QMessageBox.question', answer)
    user.activate()
    table.setFocus()

    user.press(Key.Key_F5)

    if answer == No:
        qtbot.waitUntil(lambda: not dialogs.unused_answers())
        assert loaded_paths(table) == [str(p) for p in paths]
        assert model.data(user.cell(0, 'title')) == 'New'
    else:
        wait_for_rows(qtbot, table, [paths[0]])
        assert model.data(user.cell(0, 'title')) == 'Title 1'
        assert model.previewMode
    assert in_file(paths[0])['title'] == ['Title 1']


def test_refresh_rereads_files_from_a_playlist(mainwin, make_audio, user, qtbot, tmp_path, dialogs):
    # tut2.txt: "If you've added files ad hoc to puddletag, it re-reads
    # those files again"; menus.txt: "If any directories are loaded,
    # they'll be re-read and checked for new files" (none is).
    music = tmp_path / 'music'
    p1 = make_audio('01.mp3', music, title='Title 1')
    playlist = tmp_path / 'list.m3u'
    playlist.write_text('#EXTM3U\nmusic/01.mp3\n', encoding='utf-8')
    table = mainwin._table
    model = table.model()
    user.activate()
    dialogs.answer('QFileDialog.getOpenFileName', (str(playlist), ''))
    user.click_menu('Load &playlist')
    wait_for_rows(qtbot, table, [p1])
    change_on_disk(p1, 'Changed')
    make_audio('02.mp3', music)
    user.activate()
    table.setFocus()

    user.press(Key.Key_F5)

    qtbot.waitUntil(lambda: model.taginfo[0]['title'] == ['Changed'])
    assert loaded_paths(table) == [str(p1)]


def test_refresh_selected(mainwin, make_audio, user, qtbot, tmp_path):
    # menus.txt: "Re-reads the folders of the selected files: new files in
    # them are added and deleted ones are removed. The other loaded folders
    # are left as they are."
    table, paths = two_folders(mainwin, make_audio, qtbot, tmp_path, user)
    a, b = tmp_path / 'a', tmp_path / 'b'
    paths[1].unlink()
    p4 = make_audio('04.mp3', a)
    make_audio('05.mp3', b)
    user.click_cell(user.cell(0, 'title'))

    user.click_menu('Refresh &Selected')

    qtbot.waitUntil(lambda: loaded_paths(table) == [str(paths[0]), str(paths[2]), str(p4)])


@pytest.mark.parametrize('answer', [No, Yes], ids=['No', 'Yes'])
def test_refresh_selected_with_previews_asks(mainwin, make_audio, user, qtbot, tmp_path, dialogs, answer):
    # Docs-silent: like Refresh, it asks "Do you want to discard and
    # reload?" before dropping the previews of the folders it re-reads;
    # the other folders' previews stay.
    a, b = tmp_path / 'a', tmp_path / 'b'
    paths = [make_audio('01.mp3', a, title='Title 1'),
             make_audio('02.mp3', b, title='Title 2')]
    table = mainwin._table
    model = table.model()
    mainwin.openDir(str(a), False)
    wait_for_rows(qtbot, table, paths[:1])
    mainwin.openDir(str(b), True)
    wait_for_rows(qtbot, table, paths)
    user.activate()
    table.setFocus()
    user.click_menu('Enabl&e Preview Mode')
    edit(user, qtbot, 0, 'title', 'New 1')
    user.activate()
    table.setFocus()
    edit(user, qtbot, 1, 'title', 'New 2')
    p3 = make_audio('03.mp3', a)
    dialogs.answer('QMessageBox.question', answer)
    user.click_cell(user.cell(0, 'title'))

    user.click_menu('Refresh &Selected')

    assert not dialogs.unused_answers()
    if answer == No:
        assert loaded_paths(table) == [str(p) for p in paths]
        assert model.data(user.cell(0, 'title')) == 'New 1'
    else:
        wait_for_rows(qtbot, table, [*paths, p3])
        assert model.data(user.cell(0, 'title')) == 'Title 1'
        assert model.data(user.cell(1, 'title')) == 'New 2'
    assert [in_file(p)['title'] for p in paths] == [['Title 1'], ['Title 2']]


def test_unload_everything(mainwin, user, loaded):
    # menus.txt: "Clear's the File-View and unloads any files/directories
    # that have been imported."
    table, paths = loaded

    user.click_menu('&Unload Everything')

    assert table.model().rowCount() == 0
    assert all(p.exists() for p in paths)
    assert in_file(paths[0])['title'] == ['Title 1']


def test_unload_everything_unloads_the_folders(mainwin, user, loaded):
    # menus.txt: "Clear's the File-View and unloads any files/directories
    # that have been imported." Nothing is loaded afterwards, so the
    # commands that need files are greyed out.
    table, paths = loaded

    user.click_menu('&Unload Everything')

    assert not any(user.action(name).isEnabled() for name in (
        '&Add Folder', '&Refresh', '&Unload Everything', 'Sa&ve playlist'))


def test_load_playlist_after_unload_everything(mainwin, user, loaded, qtbot, tmp_path, dialogs):
    # menus.txt: "Clear's the File-View and unloads any files/directories
    # that have been imported." and, for Load playlist, "Opens a dialog to
    # import an m3u playlist into puddletag."
    table, paths = loaded
    playlist = tmp_path / 'list.m3u'
    playlist.write_text('#EXTM3U\nmusic/01.mp3\n', encoding='utf-8')
    user.click_menu('&Unload Everything')
    user.activate()
    dialogs.answer('QFileDialog.getOpenFileName', (str(playlist), ''))

    user.click_menu('Load &playlist')

    wait_for_rows(qtbot, table, [paths[0]])


@pytest.mark.parametrize('answer', [No, Yes], ids=['No', 'Yes'])
def test_unload_everything_with_previews_asks(mainwin, user, loaded, qtbot, dialogs, answer):
    # Docs-silent: with unsaved previews Unload Everything asks before it
    # drops them; No keeps the rows and the preview.
    table, paths = loaded
    model = table.model()
    user.click_menu('Enabl&e Preview Mode')
    edit(user, qtbot, 0, 'title', 'New')
    dialogs.answer('QMessageBox.question', answer)

    user.click_menu('&Unload Everything')

    assert not dialogs.unused_answers()
    if answer == No:
        assert loaded_paths(table) == [str(p) for p in paths]
        assert model.data(user.cell(0, 'title')) == 'New'
    else:
        assert model.rowCount() == 0
    assert in_file(paths[0])['title'] == ['Title 1']


def test_refresh_after_refresh_selected_finds_new_files(mainwin, make_audio, tmp_path, qtbot, user):
    # menus.txt: "If any directories are loaded, they'll be re-read and
    # checked for new files."
    a = tmp_path / 'a'
    b = tmp_path / 'b'
    first = [make_audio(name, a, title=name) for name in ('01.mp3', '02.mp3')]
    third = make_audio('03.mp3', b, title='03.mp3')
    mainwin.openDir(str(a), False)
    table = mainwin._table
    wait_for_rows(qtbot, table, first)
    mainwin.openDir(str(b), True)
    wait_for_rows(qtbot, table, [*first, third])
    user.activate()
    model = table.model()
    old = model.taginfo[0]
    user.click_cell(user.cell(0, 'title'))
    user.click_menu('Refresh &Selected')
    qtbot.waitUntil(lambda: old not in model.taginfo)
    new = make_audio('05.mp3', b, title='05.mp3')
    user.activate()
    table.setFocus()
    user.press(Key.Key_F5)
    qtbot.waitUntil(lambda: str(new) in loaded_paths(table))


# menus.txt (Refresh): "If any directories are loaded, they'll be re-read
# and checked for new files." A file in the second folder's subfolder
# showed twice.
def test_refresh_with_two_folders_and_subfolders(mainwin, make_audio, tmp_path, qtbot, user):
    a = tmp_path / 'a'
    b = tmp_path / 'b'
    p1 = make_audio('01.mp3', a, title='Title 1')
    p2 = make_audio('02.mp3', b / 'sub', title='Title 2')
    set_subfolders(mainwin, qtbot, user, True)
    table = mainwin._table
    model = table.model()
    mainwin.openDir(str(a), False)
    wait_for_rows(qtbot, table, [p1])
    mainwin.openDir(str(b), True)
    wait_for_rows(qtbot, table, [p1, p2])
    user.activate()
    table.setFocus()
    old = list(model.taginfo)

    user.press(Key.Key_F5)

    # Refresh builds new row objects.
    qtbot.waitUntil(lambda: model.taginfo and not any(audio in model.taginfo for audio in old))
    assert sorted(loaded_paths(table)) == [str(p1), str(p2)]


# menus.txt (Load playlist): "Opens a dialog to import an m3u playlist into
# puddletag." A file removed from the list, in a folder still loaded, was
# skipped.
def test_load_playlist_skipped_files_inside_a_loaded_folder(loaded, tmp_path, qtbot, user, dialogs):
    table, paths = loaded
    select_rows(user, 0, 1)
    user.click_menu('Remove from &List')
    qtbot.waitUntil(lambda: table.model().rowCount() == 0)
    playlist = tmp_path / 'list.m3u'
    playlist.write_text('#EXTM3U\nmusic/01.mp3\n', encoding='utf-8')
    dialogs.answer('QFileDialog.getOpenFileName', (str(playlist), ''))

    user.click_menu('Load &playlist')

    wait_for_rows(qtbot, table, [paths[0]])


# menus.txt (Load playlist): "Opens a dialog to import an m3u playlist into
# puddletag." A folder whose name starts with a loaded folder's, music2
# beside music (synthetic), counted as inside it.
def test_load_playlist_folder_sharing_a_prefix(loaded, make_audio, tmp_path, qtbot, user, dialogs):
    table, paths = loaded
    p3 = make_audio('03.mp3', tmp_path / 'music2', title='Title 3')
    playlist = tmp_path / 'list.m3u'
    playlist.write_text('#EXTM3U\nmusic2/03.mp3\n', encoding='utf-8')
    dialogs.answer('QFileDialog.getOpenFileName', (str(playlist), ''))

    user.click_menu('Load &playlist')

    wait_for_rows(qtbot, table, [*paths, p3])


# Load and Save playlist ------------------------------------------------------

@pytest.fixture
def unicode_music(mainwin, make_audio, tmp_path, qtbot, user):
    """música/01 Ölü.mp3 and música/02.mp3, opened, and an empty lists/."""
    music = tmp_path / 'música'
    paths = [make_audio('01 Ölü.mp3', music, artist='Ärtist', title='Tïtle 1'),
             make_audio('02.mp3', music, artist='Artist 2', title='Title 2')]
    (tmp_path / 'lists').mkdir()
    mainwin.openDir(str(music), False)
    table = mainwin._table
    wait_for_rows(qtbot, table, paths)
    user.activate()
    return table, paths


@pytest.fixture
def playlist(make_audio, tmp_path):
    """list.m3u, naming música/01 Ölü.mp3 relative to itself and
    música/sub/02, b.mp3 by its absolute path, with a comment and a blank
    line between them (not opened)."""
    p1 = make_audio('01 Ölü.mp3', tmp_path / 'música', artist='Ärtist', title='Tïtle 1')
    p2 = make_audio('02, b.mp3', tmp_path / 'música' / 'sub', title='T2')
    path = tmp_path / 'list.m3u'
    path.write_text(f'#EXTM3U\n#EXTINF:1,Ärtist - Tïtle 1\nmúsica/01 Ölü.mp3\n\n{p2}\n', encoding='utf-8')
    return path, [p1, p2]


def save_playlist(user, dialogs, out):
    """Sa&ve playlist, answered with this file; returns its lines."""
    dialogs.answer('QFileDialog.getSaveFileName', (str(out), ''))
    user.click_menu('Sa&ve playlist')
    return out.read_text(encoding='utf-8').split('\n')


def load_playlist(user, dialogs, path):
    user.activate()
    dialogs.answer('QFileDialog.getOpenFileName', (str(path), ''))
    user.click_menu('Load &playlist')


def titles(table):
    return [audio['title'] for audio in table.model().taginfo]


def test_save_playlist(mainwin, user, dialogs, unicode_music, tmp_path):
    # "Save's the selected files of the File_view to a playlist, or every
    # file when none is selected. The format to write for the extended info
    # can be set in Preferences." (both rows are selected) and "Write
    # extended info: When enabled the pattern you will be used to write
    # extended info for M3U playlists."
    table, (p1, p2) = unicode_music
    select_rows(user, 0, 1)
    out = tmp_path / 'lists' / 'out.m3u'
    assert save_playlist(user, dialogs, out) == [
        '#EXTM3U', '#EXTINF: 1, Ärtist - Tïtle 1', str(p1), '#EXTINF: 1, Artist 2 - Title 2', str(p2)]
    assert in_file(p1)['title'] == ['Tïtle 1']


def test_save_playlist_with_one_row_selected(user, dialogs, loaded, tmp_path):
    # "Save's the selected files of the File_view to a playlist, or every
    # file when none is selected." After a folder loads, its first cell is
    # selected.
    table, (p1, p2) = loaded
    out = tmp_path / 'out.m3u'
    assert save_playlist(user, dialogs, out) == ['#EXTM3U', '#EXTINF: 1, Artist 1 - Title 1', str(p1)]


def test_save_playlist_with_nothing_selected(user, dialogs, loaded, tmp_path):
    # "Save's the selected files of the File_view to a playlist, or every
    # file when none is selected." A click below the last row clears the
    # selection.
    table, (p1, p2) = loaded
    rect = table.visualRect(user.cell(1, 'title'))
    below = rect.center()
    below.setY(rect.bottom() + 20)
    user.click(table.viewport(), below)
    assert not table.selectedIndexes()
    out = tmp_path / 'out.m3u'
    assert save_playlist(user, dialogs, out) == [
        '#EXTM3U', '#EXTINF: 1, Artist 1 - Title 1', str(p1), '#EXTINF: 1, Artist 2 - Title 2', str(p2)]


def test_save_playlist_greyed_out_with_nothing_loaded(user):
    # Docs-silent: nothing is loaded, so there is nothing to save.
    assert not user.action('Sa&ve playlist').isEnabled()


def test_save_playlist_suggests_the_filename_pattern(mainwin, qtbot, user, dialogs, make_audio, tmp_path):
    # "Filename pattern: Then default filename pattern to use when saving
    # playlists." The dialog starts in the last loaded folder (docs-silent).
    window = open_preferences(mainwin, qtbot, user, 'Playlist')
    set_text(user, labelled(window, '&Filename pattern.'), '%artist%.m3u')
    close_preferences(window, qtbot, user)
    music = tmp_path / 'music'
    p1 = make_audio('01.mp3', music, artist='Artist 1', title='Title 1')
    mainwin.openDir(str(music), False)
    wait_for_rows(qtbot, mainwin._table, [p1])
    user.activate()
    dialogs.answer('QFileDialog.getSaveFileName', ('', ''))
    user.click_menu('Sa&ve playlist')
    assert dialogs.calls[-1][1][2] == str(music / 'Artist 1.m3u')
    assert not (music / 'Artist 1.m3u').exists()


def test_save_playlist_without_extended_info(mainwin, qtbot, user, dialogs, unicode_music, tmp_path):
    # "Write extended info: When enabled the pattern you will be used to
    # write extended info for M3U playlists."
    table, (p1, p2) = unicode_music
    window = open_preferences(mainwin, qtbot, user, 'Playlist')
    set_check_box(user, window, '&Write extended info', False)
    close_preferences(window, qtbot, user)
    select_rows(user, 0, 1)
    assert save_playlist(user, dialogs, tmp_path / 'lists' / 'out.m3u') == ['#EXTM3U', str(p1), str(p2)]


def test_save_playlist_extended_info_pattern(mainwin, qtbot, user, dialogs, unicode_music, tmp_path):
    # "Write extended info: When enabled the pattern you will be used to
    # write extended info for M3U playlists." The pattern field has no
    # label.
    table, (p1, p2) = unicode_music
    window = open_preferences(mainwin, qtbot, user, 'Playlist')
    set_text(user, window.stack.currentWidget().extpattern, '%title%')
    close_preferences(window, qtbot, user)
    select_rows(user, 0, 1)
    assert save_playlist(user, dialogs, tmp_path / 'lists' / 'out.m3u') == [
        '#EXTM3U', '#EXTINF: 1, Tïtle 1', str(p1), '#EXTINF: 1, Title 2', str(p2)]


def test_save_playlist_relative_entries(mainwin, qtbot, user, dialogs, unicode_music, tmp_path):
    # "Entries relative to working directory: When enabled, the entries are
    # written relative to the playlist's folder, not as absolute paths."
    table, (p1, p2) = unicode_music
    window = open_preferences(mainwin, qtbot, user, 'Playlist')
    set_check_box(user, window, 'Entries &relative to working directory', True)
    close_preferences(window, qtbot, user)
    select_rows(user, 0, 1)
    assert save_playlist(user, dialogs, tmp_path / 'lists' / 'out.m3u') == [
        '#EXTM3U', '#EXTINF: 1, Ärtist - Tïtle 1', os.path.join('..', 'música', '01 Ölü.mp3'),
        '#EXTINF: 1, Artist 2 - Title 2', os.path.join('..', 'música', '02.mp3')]


def test_save_playlist_with_windows_separators(mainwin, qtbot, user, dialogs, unicode_music, tmp_path):
    # "Use windows path separator: When enabled, the entries are written
    # with \ instead of /."
    table, (p1, p2) = unicode_music
    window = open_preferences(mainwin, qtbot, user, 'Playlist')
    set_check_box(user, window, 'Use windows path separator (\\)', True)
    set_check_box(user, window, '&Write extended info', False)
    close_preferences(window, qtbot, user)
    select_rows(user, 0, 1)
    assert save_playlist(user, dialogs, tmp_path / 'lists' / 'out.m3u') == [
        '#EXTM3U', str(p1).replace('/', '\\'), str(p2).replace('/', '\\')]


def test_load_playlist(mainwin, qtbot, user, dialogs, playlist):
    # "Opens a dialog to import an m3u playlist into puddletag." Entries
    # relative to the playlist's folder and absolute ones are read, comment
    # and blank lines skipped, a comma and non-ASCII text kept in a name
    # (docs-silent).
    path, (p1, p2) = playlist
    table = mainwin._table
    load_playlist(user, dialogs, path)
    wait_for_rows(qtbot, table, [p1, p2])
    assert titles(table) == [['Tïtle 1'], ['T2']]


def test_save_then_load_playlist(mainwin, qtbot, user, dialogs, unicode_music, tmp_path):
    # "Save's the selected files of the File_view to a playlist, or every
    # file when none is selected." and "Opens a
    # dialog to import an m3u playlist into puddletag." An empty folder
    # replaces the shown files first.
    table, (p1, p2) = unicode_music
    select_rows(user, 0, 1)
    out = tmp_path / 'lists' / 'out.m3u'
    save_playlist(user, dialogs, out)
    empty = tmp_path / 'empty'
    empty.mkdir()
    mainwin.openDir(str(empty), False)
    qtbot.waitUntil(lambda: table.model().rowCount() == 0)
    load_playlist(user, dialogs, out)
    wait_for_rows(qtbot, table, [p1, p2])
    assert titles(table) == [['Tïtle 1'], ['Title 2']]


def test_load_playlist_adds_to_the_shown_files(mainwin, qtbot, user, dialogs, make_audio, playlist, tmp_path):
    # "Opens a dialog to import an m3u playlist into puddletag. The
    # playlist's files are added after the files already shown."
    path, (p1, p2) = playlist
    other = tmp_path / 'other'
    p9 = make_audio('09.mp3', other, title='Title 9')
    mainwin.openDir(str(other), False)
    table = mainwin._table
    wait_for_rows(qtbot, table, [p9])
    load_playlist(user, dialogs, path)
    wait_for_rows(qtbot, table, [p9, p1, p2])


def test_load_playlist_skips_missing_files(mainwin, qtbot, user, dialogs, make_audio, tmp_path):
    # Docs-silent: an entry whose file is missing is skipped, without a
    # message.
    p1 = make_audio('01.mp3', tmp_path / 'music', title='Title 1')
    path = tmp_path / 'list.m3u'
    path.write_text('#EXTM3U\nmusic/01.mp3\nmusic/gone.mp3\n', encoding='utf-8')
    load_playlist(user, dialogs, path)
    wait_for_rows(qtbot, mainwin._table, [p1])
    assert not [name for name, *_ in dialogs.calls if name.startswith('QMessageBox')]


def test_load_playlist_not_utf8(mainwin, user, dialogs, tmp_path):
    # Docs-silent: a playlist that isn't UTF-8 says so.
    path = tmp_path / 'list.m3u'
    path.write_bytes('#EXTM3U\nÖlü.mp3\n'.encode('latin-1'))
    dialogs.answer('QMessageBox.information', QMessageBox.StandardButton.Ok)
    load_playlist(user, dialogs, path)
    assert dialogs.calls[-1][1][2] == 'The playlist is not encoded in UTF-8'
    assert mainwin._table.model().rowCount() == 0


@pytest.mark.xfail(strict=True, reason='#222: readm3u keeps the backslash in sub\\01.mp3 as part of the '
                   'name on Linux, so no file loads; it should read it as a separator')
def test_load_playlist_with_backslashes(mainwin, qtbot, user, dialogs, make_audio, tmp_path):
    # "Use windows path separator: When enabled, the entries are written
    # with \ instead of /." puddletag writes such entries, so it reads them.
    p1 = make_audio('01.mp3', tmp_path / 'sub', title='Title 1')
    path = tmp_path / 'list.m3u'
    path.write_text('#EXTM3U\nsub\\01.mp3\n', encoding='utf-8')
    load_playlist(user, dialogs, path)
    wait_for_rows(qtbot, mainwin._table, [p1])


def test_load_playlist_cancelled(user, dialogs, loaded):
    # Docs-silent: Cancel leaves the files as they were.
    table, paths = loaded
    dialogs.answer('QFileDialog.getOpenFileName', ('', ''))
    user.click_menu('Load &playlist')
    assert not dialogs.unused_answers()
    assert loaded_paths(table) == [str(p) for p in paths]
    assert not [name for name, *_ in dialogs.calls if name.startswith('QMessageBox')]


def set_player(mainwin, qtbot, user, command):
    window = open_preferences(mainwin, qtbot, user)
    set_text(user, labelled(window, 'Program to &play files with:'), command)
    close_preferences(window, qtbot, user)


PLAY = {
    'File menu': lambda user, index: user.click_menu('&Play'),
    'right-click menu': lambda user, index: user.right_click_cell(index, '&Play'),
    'shortcut': lambda user, index: user.press(Key.Key_P, Ctrl),
}

EXIT = {
    'File menu': lambda user: user.click_menu('&Exit'),
    'shortcut': lambda user: user.press(Key.Key_Q, Ctrl),
}


@pytest.mark.parametrize('run', PLAY.values(), ids=PLAY.keys())
def test_play(run, loaded, mainwin, qtbot, user, tmp_path):
    # menus.txt: "Play's the currently selected files using the player
    # defined in Preferences."
    # preferences.txt: "Enter the command of the program puddletag should
    # use to play files with. The list of selected files will be appended
    # to the argument list."
    table, paths = loaded
    set_player(mainwin, qtbot, user, str(player(tmp_path)))
    select_rows(user, 0, 1)
    run(user, user.cell(1, 'title'))
    out = tmp_path / 'player.txt'
    qtbot.waitUntil(out.exists)
    assert out.read_text().splitlines() == [str(paths[0]), str(paths[1])]
    assert in_file(paths[0])['title'] == ['Title 1']
    assert in_file(paths[1])['title'] == ['Title 2']


def test_play_appends_the_files_to_the_arguments(loaded, mainwin, qtbot, user, tmp_path):
    # preferences.txt: "The list of selected files will be appended to the
    # argument list."
    table, paths = loaded
    set_player(mainwin, qtbot, user, f'{player(tmp_path)} --enqueue')
    user.click_cell(user.cell(0, 'title'))
    user.press(Key.Key_P, Ctrl)
    out = tmp_path / 'player.txt'
    qtbot.waitUntil(out.exists)
    assert out.read_text().splitlines() == ['--enqueue', str(paths[0])]


def test_play_greyed_out_with_nothing_selected(loaded, user):
    # menus.txt: "Play's the currently selected files": with no file shown,
    # none is selected.
    user.click_menu('&Unload Everything')
    assert not user.action('&Play').isEnabled()


def test_play_missing_player(loaded, mainwin, qtbot, user, tmp_path, dialogs):
    # Docs-silent: a player that doesn't exist is reported.
    table, paths = loaded
    missing = str(tmp_path / 'missing')
    set_player(mainwin, qtbot, user, missing)
    dialogs.answer('QMessageBox.critical', QMessageBox.StandardButton.Ok)
    user.click_cell(user.cell(0, 'title'))
    user.press(Key.Key_P, Ctrl)
    qtbot.waitUntil(lambda: not dialogs.unused_answers())
    assert missing in dialogs.calls[-1][1][2]


@pytest.mark.parametrize('run', EXIT.values(), ids=EXIT.keys())
def test_exit(run, loaded, mainwin, qtbot, user):
    # menus.txt: "Closes puddletag."
    # preferences.txt: "the last folder that was loaded upon closing
    # puddletag will be re-opened when puddletag is started."
    table, paths = loaded
    run(user)
    qtbot.waitUntil(lambda: not mainwin.isVisible())
    assert PuddleConfig().get('main', 'lastfolder', None) == str(paths[0].parent)


@pytest.mark.parametrize('answer, visible', [(No, True), (Yes, False)], ids=['No', 'Yes'])
def test_exit_with_previews_asks(answer, visible, loaded, mainwin, qtbot, user, dialogs):
    # Docs-silent: exiting with unsaved previews asks; No keeps the window,
    # Yes closes it without writing them.
    table, paths = loaded
    user.click_menu('Enabl&e Preview Mode')
    edit(user, qtbot, 0, 'title', 'New')
    dialogs.answer('QMessageBox.question', answer)
    user.activate()
    table.setFocus()
    user.press(Key.Key_Q, Ctrl)
    qtbot.waitUntil(lambda: not dialogs.unused_answers())
    assert mainwin.isVisible() == visible
    assert in_file(paths[0])['title'] == ['Title 1']
