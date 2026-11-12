"""Format (menus.txt: "Applies the Format Value function to the selected
files using the pattern in the Pattern Combo"), run as a user runs it: the
toolbar button and the Convert menu. Each result is checked in the files
and in the table. Synthetic files.
"""
import os

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

from puddlestuff import audioinfo

pytestmark = pytest.mark.ui

Key = Qt.Key
Shift = Qt.KeyboardModifier.ShiftModifier


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    music = tmp_path / 'music'
    paths = [make_audio(f'0{i}.mp3', music, artist=f'Artist {i}', title=f'Title {i}', tracknumber=str(i))
             for i in (1, 2, 3)]
    mainwin.openDir(str(music), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == 3)
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]
    user.activate()
    table.setFocus()
    return table, paths


def in_file(path, field):
    return audioinfo.Tag(str(path)).get(field)


def set_pattern(user, pattern):
    """F8 goes to the Pattern Combo, its text selected, and back
    (tut3.txt: "Pressing F8 switches focus between it and the
    file-view")."""
    user.press(Key.Key_F8)
    user.type(pattern)
    user.press(Key.Key_F8)


FORMAT = {
    'toolbar': lambda user: user.click_toolbar('&Format'),
    'Convert menu': lambda user: user.click_menu('&Format'),
}


@pytest.mark.parametrize('format_', FORMAT.values(), ids=FORMAT.keys())
def test_format(user, loaded, qtbot, format_):
    # The selected cells take the pattern's value, each from its own file.
    table, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(2, 'title'), Shift)
    set_pattern(user, '%artist% - %title%')
    format_(user)
    qtbot.waitUntil(lambda: in_file(paths[2], 'title') == ['Artist 3 - Title 3'])
    user.activate()
    assert [in_file(p, 'title') for p in paths] == [[f'Artist {i} - Title {i}'] for i in (1, 2, 3)]
    assert [in_file(p, 'artist') for p in paths] == [[f'Artist {i}'] for i in (1, 2, 3)]
    assert [audio['title'] for audio in table.model().taginfo] == [
        [f'Artist {i} - Title {i}'] for i in (1, 2, 3)]


def test_filename_cell_loses_its_extension(user, mainwin, make_audio, tmp_path, qtbot):
    # "Be careful if you have a filename cell selected, because the file
    # will be renamed using the Pattern Combo's pattern without preserving
    # extensions. So using the %artist% - %title% pattern as before will
    # result in the file being renamed to 'Before The Fame - Sounds Better
    # Than Anything After' (<- note the absence of an extension)."
    path = make_audio('song.mp3', tmp_path / 'music', artist='Before The Fame',
                      title='Sounds Better Than Anything After')
    mainwin.openDir(str(path.parent), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == 1)
    user.activate()
    user.click_cell(user.cell(0, '__filename'))
    set_pattern(user, '%artist% - %title%')
    user.click_toolbar('&Format')
    renamed = path.with_name('Before The Fame - Sounds Better Than Anything After')
    qtbot.waitUntil(renamed.exists)
    assert os.listdir(path.parent) == [renamed.name]
    assert table.model().taginfo[0].filepath == str(renamed)


def test_folder_cells_left_alone(user, loaded, qtbot, tmp_path, monkeypatch):
    # #636: with every cell selected (Ctrl+A), Format with %track% - %title%
    # wrote the pattern into the Dirpath cell too, so the folder moved to
    # "3 - Title 3" in the working folder (the reporters' home folder or the
    # drive's root). Format leaves the folder cells alone; the Filename
    # cell still renames each file without an extension, as the docs warn.
    monkeypatch.chdir(tmp_path)
    table, paths = loaded
    user.press(Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    set_pattern(user, '%track% - %title%')
    user.click_toolbar('&Format')
    music = paths[0].parent
    qtbot.waitUntil(lambda: (music / '3 - Title 3').exists())
    user.activate()
    assert os.listdir(tmp_path) == ['music']
    assert sorted(os.listdir(music)) == ['1 - Title 1', '2 - Title 2', '3 - Title 3']
    assert [in_file(music / f'{i} - Title {i}', 'title') for i in (1, 2, 3)] == [
        [f'{i} - Title {i}'] for i in (1, 2, 3)]
    assert [audio.dirpath for audio in table.model().taginfo] == [str(music)] * 3


def test_total_in_the_pattern(mainwin, make_audio, tmp_path, qtbot, user):
    # tags.txt: "__total: If the track field is of track/numtracks format,
    # returns numtracks."
    path = make_audio('song.flac', tmp_path / 'music', title='Song', tracknumber='3/12')
    mainwin.openDir(str(path.parent), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == 1)
    user.activate()
    table.setFocus()
    user.click_cell(user.cell(0, 'title'))
    set_pattern(user, '%__total%')
    user.click_toolbar('&Format')
    qtbot.waitUntil(lambda: in_file(path, 'title') == ['12'])
    assert table.model().taginfo[0]['title'] == ['12']


@pytest.fixture
def nested(mainwin, make_audio, tmp_path, qtbot, user):
    """One MP3 in A/B, loaded."""
    path = make_audio('song.mp3', tmp_path / 'A' / 'B', title='Song')
    mainwin.openDir(str(path.parent), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == 1)
    user.activate()
    table.setHeaderTags(table.model().headerdata + [('__ext', '__ext'), ('__parent_dir', '__parent_dir')])
    return table, path


def test_parent_dir_not_written_by_format(user, nested, qtbot, tmp_path):
    # __parent_dir: "Cannot be written to."
    table, path = nested
    user.click_cell(user.cell(0, '__parent_dir'))
    set_pattern(user, 'X')
    user.click_toolbar('&Format')
    # The first Format has run by the time the second one's result shows.
    user.click_cell(user.cell(0, 'title'))
    set_pattern(user, '%title%!')
    user.click_toolbar('&Format')
    qtbot.waitUntil(lambda: in_file(path, 'title') == ['Song!'])
    assert path.exists()
    assert not (tmp_path / 'A' / 'X').exists()
    assert table.model().taginfo[0]['__parent_dir'] == 'A'


def test_extension_written_by_format(user, nested, qtbot):
    # __ext: "Extension of the file." The docs don't say it can't be written
    # to; the maintainer's decision is that Format renames the file.
    table, path = nested
    user.click_cell(user.cell(0, '__ext'))
    set_pattern(user, 'ogg')
    user.click_toolbar('&Format')
    renamed = path.parent / 'song.ogg'
    qtbot.waitUntil(renamed.exists)
    assert not path.exists()
    assert table.model().taginfo[0].filepath == str(renamed)


@pytest.mark.xfail(strict=True, reason='Format into __filename_no_ext renames nothing')
def test_filename_no_ext_written_by_format(user, nested, qtbot):
    # __filename_no_ext: "The file's filename without extension. Can be
    # written to: the file is renamed and keeps its extension."
    table, path = nested
    table.setHeaderTags(table.model().headerdata + [('__filename_no_ext', '__filename_no_ext')])
    user.click_cell(user.cell(0, '__filename_no_ext'))
    set_pattern(user, 'Renamed')
    user.click_toolbar('&Format')
    renamed = path.parent / 'Renamed.mp3'
    qtbot.waitUntil(renamed.exists)
    assert not path.exists()
    assert table.model().taginfo[0].filepath == str(renamed)
    assert in_file(renamed, 'title') == ['Song']


def test_format_with_a_syntax_error(user, loaded, mainwin, dialogs):
    # Tag->File shows a pattern's syntax error in a warning and changes
    # nothing; Format does the same. Synthetic pattern, missing its closing
    # bracket.
    table, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    set_pattern(user, '$upper(abc')
    dialogs.answer('QMessageBox.warning', QMessageBox.StandardButton.Ok)
    user.click_toolbar('&Format')
    assert dialogs.calls == [
        ('QMessageBox.warning',
         (mainwin, 'Error', 'SYNTAX ERROR in $upper: No closing bracket found.'), {})]
    assert in_file(paths[0], 'title') == ['Title 1']
    assert [audio['title'] for audio in table.model().taginfo] == [[f'Title {i}'] for i in (1, 2, 3)]
