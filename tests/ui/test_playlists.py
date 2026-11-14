"""Load playlist and Save playlist (menus.txt, preferences.txt's Playlist
page), run from the File menu with each file dialog answered: the files
loaded, the playlist written, and what a load leaves behind (the working
folder, open files, the last folder). Synthetic files.
"""
import gc
import os
import shutil
import tempfile
import warnings
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QMessageBox, QStyle, QStyleOptionButton

from puddlestuff.mainwin.filterwin import FilterView
from puddlestuff.puddleobjects import PuddleConfig

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier
Ok = QMessageBox.StandardButton.Ok
GET_DIRECTORY = 'QFileDialog.getExistingDirectory'


@pytest.fixture
def music(mainwin, make_audio, tmp_path, qtbot, user):
    """music/01.mp3 and music/02.mp3, opened, and an empty lists/."""
    folder = tmp_path / 'music'
    paths = [make_audio(f'0{i}.mp3', folder, artist=f'Artist {i}', title=f'Title {i}')
             for i in (1, 2)]
    (tmp_path / 'lists').mkdir()
    mainwin.openDir(str(folder), False)
    table = mainwin._table
    wait_for_rows(qtbot, table, paths)
    user.activate()
    table.setFocus()
    return table, paths


@pytest.fixture
def elsewhere(tmp_path):
    """A folder under another top-level folder than tmp_path's, so the two
    share only /."""
    root = '/dev/shm' if tmp_path.parts[1] == 'var' else '/var/tmp'
    path = Path(tempfile.mkdtemp(dir=root))
    yield path
    shutil.rmtree(path)


def loaded_paths(table):
    return [audio.filepath for audio in table.model().taginfo]


def wait_for_rows(qtbot, table, paths):
    """Files load through a progress window: wait for the rows."""
    expected = [str(p) for p in paths]
    qtbot.waitUntil(lambda: loaded_paths(table) == expected)


def load_playlist(user, dialogs, path):
    """Load playlist from the File menu, answered with this file."""
    user.activate()
    dialogs.answer('QFileDialog.getOpenFileName', (str(path), ''))
    user.click_menu('Load &playlist')


def save_playlist(user, dialogs, out):
    """Sa&ve playlist, answered with this file; returns its lines."""
    user.activate()
    dialogs.answer('QFileDialog.getSaveFileName', (str(out), ''))
    user.click_menu('Sa&ve playlist')
    return out.read_text(encoding='utf-8').split('\n')


def select_rows(user, first, last):
    user.click_cell(user.cell(first, 'title'))
    user.click_cell(user.cell(last, 'title'), Shift)


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


def set_preference(user, page, text, checked):
    window = user.open_preferences(page)
    set_check_box(user, window, text, checked)
    user.close_preferences(window)


def filter_table(user, mainwin, text):
    [view] = mainwin.findChildren(FilterView)
    user.click(view.combo.combo.lineEdit())
    user.press(Key.Key_A, Ctrl)
    user.type(text)
    user.press(Key.Key_Return)


def unclosed(caught, path):
    """The ResourceWarnings among caught that name this file."""
    return [str(w.message) for w in caught
            if issubclass(w.category, ResourceWarning) and str(path) in str(w.message)]


# Reading and writing ---------------------------------------------------------

def test_load_playlist_not_utf8_leaves_the_working_folder(mainwin, user, dialogs, tmp_path, monkeypatch):
    # Synthetic (docs-silent): a playlist that isn't UTF-8 says so and leaves
    # the working folder as it was.
    start = tmp_path / 'start'
    start.mkdir()
    monkeypatch.chdir(start)
    path = tmp_path / 'lists' / 'list.m3u'
    path.parent.mkdir()
    path.write_bytes('#EXTM3U\nÖlü.mp3\n'.encode('latin-1'))
    dialogs.answer('QMessageBox.information', Ok)
    load_playlist(user, dialogs, path)
    assert dialogs.calls[-1][1][2] == 'The playlist is not encoded in UTF-8'
    assert os.getcwd() == str(start)
    assert mainwin._table.model().rowCount() == 0


@pytest.mark.parametrize('content, encoding', [('#EXTM3U\nmusic/01.mp3\n', 'utf-8'),
                                               ('#EXTM3U\nÖlü.mp3\n', 'latin-1')],
                         ids=['UTF-8', 'not UTF-8'])
def test_load_playlist_closes_the_file(mainwin, make_audio, user, dialogs, qtbot, tmp_path, monkeypatch,
                                       content, encoding):
    # Synthetic (docs-silent): the playlist is closed once read.
    p1 = make_audio('01.mp3', tmp_path / 'music', title='Title 1')
    path = tmp_path / 'list.m3u'
    path.write_bytes(content.encode(encoding))
    monkeypatch.chdir(tmp_path)
    if encoding == 'latin-1':
        dialogs.answer('QMessageBox.information', Ok)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always', ResourceWarning)
        load_playlist(user, dialogs, path)
        if encoding == 'utf-8':
            wait_for_rows(qtbot, mainwin._table, [p1])
        gc.collect()
    assert unclosed(caught, path) == []


def test_save_playlist_relative_entries_up_to_the_root(mainwin, make_audio, user, dialogs, qtbot, tmp_path,
                                                       elsewhere):
    # "Entries relative to working directory: When enabled, the entries are
    # written relative to the playlist's folder, not as absolute paths." The
    # music and the playlist share only /.
    p1 = make_audio('01.mp3', elsewhere, title='Title 1')
    mainwin.openDir(str(elsewhere), False)
    table = mainwin._table
    wait_for_rows(qtbot, table, [p1])
    user.activate()
    lists = tmp_path / 'lists'
    lists.mkdir()
    set_preference(user, 'Playlist', 'Entries &relative to working directory', True)
    set_preference(user, 'Playlist', '&Write extended info', False)
    lines = save_playlist(user, dialogs, lists / 'out.m3u')
    assert lines == ['#EXTM3U', os.path.join(*['..'] * (len(lists.parts) - 1), *p1.parts[1:])]
    empty = tmp_path / 'empty'
    empty.mkdir()
    mainwin.openDir(str(empty), False)
    qtbot.waitUntil(lambda: table.model().rowCount() == 0)
    load_playlist(user, dialogs, lists / 'out.m3u')
    wait_for_rows(qtbot, table, [p1])


def test_save_then_load_relative_playlist(mainwin, music, user, dialogs, qtbot, tmp_path):
    # "Entries relative to working directory: When enabled, the entries are
    # written relative to the playlist's folder, not as absolute paths." and
    # "Opens a dialog to import an m3u playlist into puddletag."
    table, paths = music
    set_preference(user, 'Playlist', 'Entries &relative to working directory', True)
    select_rows(user, 0, 1)
    out = tmp_path / 'lists' / 'out.m3u'
    lines = save_playlist(user, dialogs, out)
    assert lines == ['#EXTM3U',
                     '#EXTINF: 1, Artist 1 - Title 1', os.path.join('..', 'music', '01.mp3'),
                     '#EXTINF: 1, Artist 2 - Title 2', os.path.join('..', 'music', '02.mp3')]
    empty = tmp_path / 'empty'
    empty.mkdir()
    mainwin.openDir(str(empty), False)
    qtbot.waitUntil(lambda: table.model().rowCount() == 0)
    load_playlist(user, dialogs, out)
    wait_for_rows(qtbot, table, paths)


def test_load_playlist_keeps_quotes_in_names(mainwin, make_audio, user, dialogs, qtbot, tmp_path):
    # "Opens a dialog to import an m3u playlist into puddletag." A name is
    # read as written, and one no file has is read as csv quoting (the
    # maintainer's decision). Synthetic names.
    folder = tmp_path / 'music'
    best = make_audio('"Best" of.mp3', folder, title='Best')
    ab_quoted = make_audio('a,"b".mp3', folder, title='B')
    a_b = make_audio('"a, b".mp3', folder, title='AB')
    path = folder / 'list.m3u'
    path.write_text('#EXTM3U\n"Best" of.mp3\na,"b".mp3\n"a, b".mp3\n', encoding='utf-8')
    table = mainwin._table
    load_playlist(user, dialogs, path)
    qtbot.waitUntil(lambda: len(loaded_paths(table)) == 3, timeout=3000)
    assert sorted(loaded_paths(table)) == sorted(map(str, [best, ab_quoted, a_b]))


def test_load_playlist_reads_a_csv_quoted_entry(mainwin, make_audio, user, dialogs, qtbot, tmp_path):
    # "Opens a dialog to import an m3u playlist into puddletag." A name is
    # read as written, and one no file has is read as csv quoting (the
    # maintainer's decision). Synthetic names.
    folder = tmp_path / 'music'
    p1 = make_audio('a, b.mp3', folder, title='AB')
    path = folder / 'list.m3u'
    path.write_text('#EXTM3U\n"a, b.mp3"\n', encoding='utf-8')
    load_playlist(user, dialogs, path)
    wait_for_rows(qtbot, mainwin._table, [p1])


def test_load_playlist_prefers_the_name_as_written(mainwin, make_audio, user, dialogs, qtbot, tmp_path):
    # "Opens a dialog to import an m3u playlist into puddletag." A name is
    # read as written, and one no file has is read as csv quoting (the
    # maintainer's decision). Synthetic names: both files exist.
    folder = tmp_path / 'music'
    quoted = make_audio('"a, b".mp3', folder, title='Quoted')
    make_audio('a, b.mp3', folder, title='Plain')
    path = folder / 'list.m3u'
    path.write_text('#EXTM3U\n"a, b".mp3\n', encoding='utf-8')
    load_playlist(user, dialogs, path)
    wait_for_rows(qtbot, mainwin._table, [quoted])


def test_load_playlist_skips_a_bom_and_blank_lines(mainwin, make_audio, user, dialogs, qtbot, tmp_path):
    # Docs-silent (the maintainer's decision): a BOM is ignored and a line of
    # spaces is skipped.
    p1 = make_audio('01.mp3', tmp_path / 'music', title='Title 1')
    path = tmp_path / 'list.m3u'
    path.write_text('#EXTM3U\n   \nmusic/01.mp3\n', encoding='utf-8-sig')
    load_playlist(user, dialogs, path)
    wait_for_rows(qtbot, mainwin._table, [p1])


# Load playlist and the folders ------------------------------------------------

@pytest.fixture
def music_and_playlist(music, make_audio, tmp_path, qtbot, user, dialogs):
    """music/ opened, then lists/list.m3u (holding ../other/09.mp3) loaded
    after it."""
    table, paths = music
    p9 = make_audio('09.mp3', tmp_path / 'other', title='Title 9')
    playlist = tmp_path / 'lists' / 'list.m3u'
    playlist.write_text('#EXTM3U\n../other/09.mp3\n', encoding='utf-8')
    load_playlist(user, dialogs, playlist)
    wait_for_rows(qtbot, table, [*paths, p9])
    return table, paths, p9


def test_load_playlist_starts_in_the_last_folder(music, user, dialogs, tmp_path):
    # menus.txt (Load playlist): "Opens a dialog to import an m3u playlist
    # into puddletag." It says nothing about where the dialog starts: in the
    # last folder, as Open Folder's does (the maintainer's decision).
    dialogs.answer('QFileDialog.getOpenFileName', ('', ''))
    user.click_menu('Load &playlist')
    assert dialogs.calls[-1][1][2:] == (str(tmp_path / 'music'),)


def test_save_playlist_after_load_playlist_starts_in_its_folder(music_and_playlist, user, dialogs, tmp_path):
    # preferences.txt: "the last folder that was loaded upon closing
    # puddletag will be re-opened when puddletag is started." The last
    # folder after Load playlist is the playlist's folder (the maintainer's
    # decision).
    user.activate()
    dialogs.answer('QFileDialog.getSaveFileName', ('', ''))
    user.click_menu('Sa&ve playlist')
    assert dialogs.calls[-1][1][2] == str(tmp_path / 'lists' / 'puddletag.m3u')


def test_open_folder_after_load_playlist_starts_in_its_folder(music_and_playlist, user, dialogs, tmp_path):
    # preferences.txt: "the last folder that was loaded upon closing
    # puddletag will be re-opened when puddletag is started." The last
    # folder after Load playlist is the playlist's folder (the maintainer's
    # decision).
    dialogs.answer(GET_DIRECTORY, '')
    user.click_menu('&Open Folder')
    assert dialogs.calls[-1][1][2] == str(tmp_path / 'lists')


def test_exit_after_load_playlist_saves_its_folder(music_and_playlist, mainwin, user, qtbot, tmp_path):
    # preferences.txt: "the last folder that was loaded upon closing
    # puddletag will be re-opened when puddletag is started." The last
    # folder after Load playlist is the playlist's folder (the maintainer's
    # decision).
    user.click_menu('&Exit')
    qtbot.waitUntil(lambda: not mainwin.isVisible())
    assert PuddleConfig().get('main', 'lastfolder', None) == str(tmp_path / 'lists')


def test_refresh_after_load_playlist_rereads_the_folders(music_and_playlist, make_audio, user, qtbot, tmp_path):
    # menus.txt: Refresh "Refreshes the files currently loaded in the
    # File-View. If any directories are loaded, they'll be re-read and
    # checked for new files." Load playlist: "The playlist's files are added
    # after the files already shown." So the folders loaded before it stay
    # loaded (the maintainer's decision).
    table, paths, p9 = music_and_playlist
    p3 = make_audio('03.mp3', tmp_path / 'music', title='Title 3')
    user.activate()
    table.setFocus()
    user.press(Key.Key_F5)
    qtbot.waitUntil(lambda: sorted(loaded_paths(table)) == sorted(map(str, [*paths, p3, p9])))


def test_refresh_keeps_a_playlist_file_from_a_subfolder(mainwin, make_audio, user, qtbot, tmp_path, dialogs):
    # tut2.txt: "If you've added files ad hoc to puddletag, it re-reads those
    # files again"; menus.txt (Refresh): "Refreshes the files currently
    # loaded in the File-View." A file of the playlist inside a subfolder of
    # a folder added with Subfolders off stays loaded (the maintainer's
    # decision).
    table = mainwin._table
    set_preference(user, 'General', 'Su&bfolders', False)
    p1 = make_audio('01.mp3', tmp_path / 'music', title='Title 1')
    p3 = make_audio('03.mp3', tmp_path / 'music' / 'sub', title='Title 3')
    playlist = tmp_path / 'list.m3u'
    playlist.write_text('#EXTM3U\nmusic/sub/03.mp3\n', encoding='utf-8')
    load_playlist(user, dialogs, playlist)
    wait_for_rows(qtbot, table, [p3])
    dialogs.answer(GET_DIRECTORY, str(tmp_path / 'music'))
    user.click_menu('&Add Folder')
    wait_for_rows(qtbot, table, [p3, p1])
    old = list(table.model().taginfo)
    user.activate()
    table.setFocus()

    user.press(Key.Key_F5)

    qtbot.waitUntil(lambda: table.model().taginfo and not any(a in table.model().taginfo for a in old))
    assert sorted(loaded_paths(table)) == [str(p1), str(p3)]


# Docs-silent pins -------------------------------------------------------------

def test_load_playlist_unreadable(mainwin, user, dialogs, tmp_path, monkeypatch):
    # menus.txt, Load playlist: "Opens a dialog to import an m3u playlist
    # into puddletag." A playlist without read permission shows the error
    # message and loads nothing (docs-silent; the maintainer's decision).
    assert os.getuid() != 0, 'root reads any file'
    path = tmp_path / 'list.m3u'
    path.write_text('#EXTM3U\n', encoding='utf-8')
    path.chmod(0)
    monkeypatch.chdir(tmp_path)
    cwd = os.getcwd()
    dialogs.answer('QMessageBox.information', Ok)
    load_playlist(user, dialogs, path)
    assert dialogs.calls[-1][1][2] == f'An error occurred while reading <b>{path}</b> (Permission denied)'
    assert mainwin._table.model().rowCount() == 0
    assert os.getcwd() == cwd


def test_save_playlist_with_every_row_filtered_out(mainwin, user, dialogs, music, qtbot, tmp_path):
    # menus.txt, Save playlist: "Save's the selected files of the File_view
    # to a playlist, or every file when none is selected." With a filter
    # hiding every row the command stays enabled and does nothing (docs-silent;
    # the maintainer's decision).
    table, paths = music
    filter_table(user, mainwin, 'nomatch')
    qtbot.waitUntil(lambda: table.model().rowCount() == 0)
    assert user.action('Sa&ve playlist').isEnabled()
    user.click_menu('Sa&ve playlist')
    assert not [name for name, *_ in dialogs.calls if name.startswith('QFileDialog')]
    assert sorted(p.name for p in (tmp_path / 'music').iterdir()) == ['01.mp3', '02.mp3']


@pytest.mark.parametrize('kind', ['empty folder', 'playlist of missing files'])
def test_loading_no_files_gives_no_qt_warning(mainwin, user, dialogs, qtbot, qtlog, tmp_path, monkeypatch, kind):
    # menus.txt, Load playlist: "Opens a dialog to import an m3u playlist
    # into puddletag." A load that finds no file to show gives no Qt warning
    # (docs-silent; the maintainer's decision).
    monkeypatch.chdir(tmp_path)
    with qtbot.waitSignal(mainwin._table.filesloaded, timeout=5000, check_params_cb=bool):
        if kind == 'empty folder':
            empty = tmp_path / 'empty'
            empty.mkdir()
            mainwin.openDir(str(empty), False)
        else:
            path = tmp_path / 'list.m3u'
            path.write_text('#EXTM3U\ngone.mp3\n', encoding='utf-8')
            load_playlist(user, dialogs, path)
    assert not [r.message for r in qtlog.records if 'dataChanged' in r.message]


def test_save_playlist_unwritable(user, dialogs, music, tmp_path, request):
    # menus.txt, Save playlist: "Save's the selected files of the File_view
    # to a playlist, or every file when none is selected." A folder it can't
    # write shows an error message and writes nothing (docs-silent; the
    # maintainer's decision).
    assert os.getuid() != 0, 'root writes anywhere'
    table, paths = music
    locked = tmp_path / 'locked'
    locked.mkdir()
    locked.chmod(0o500)
    request.addfinalizer(lambda: locked.chmod(0o700))
    out = locked / 'out.m3u'
    dialogs.answer('QMessageBox.information', Ok)
    dialogs.answer('QFileDialog.getSaveFileName', (str(out), ''))
    user.click_menu('Sa&ve playlist')
    assert dialogs.calls[-1][1][2] == f'An error occurred while writing <b>{out}</b> (Permission denied)'
    assert not out.exists()
