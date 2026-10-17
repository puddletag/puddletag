"""Format (menus.txt: "Applies the Format Value function to the selected
files using the pattern in the Pattern Combo"), run as a user runs it: the
toolbar button and the Convert menu. Each result is checked in the files
and in the table. Synthetic files.
"""
import os

import pytest
from PyQt6.QtCore import Qt

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
