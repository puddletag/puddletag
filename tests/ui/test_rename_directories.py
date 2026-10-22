"""Rename Directories (the Convert menu and its toolbar, menus.txt), run from
the main window as a user runs it, on the selected files: "Renames the
selected files' directories based on the pattern in Pattern Combo. It's also
a shortcut for Tag->Dir." Synthetic files; their tags are function.txt's
examples.
"""
import pytest
from PyQt6.QtCore import Qt

from puddlestuff.mainwin.patterncombo import PatternCombo

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier

RENAME_DIRECTORIES = {
    'Convert menu': lambda user: user.click_menu('&Rename Directories'),
    'toolbar': lambda user: user.click_toolbar('&Rename Directories'),
}


def set_pattern(user, pattern):
    """F8 goes to the Pattern Combo, its text selected, and back (tut3.txt:
    "Pressing F8 switches focus between it and the file-view"). Delete drops
    the rest of a saved pattern that the combo completes the typed text to."""
    user.press(Key.Key_F8)
    user.type(pattern)
    user.press(Key.Key_Delete)
    user.press(Key.Key_F8)


@pytest.mark.parametrize('rename_directories', RENAME_DIRECTORIES.values(), ids=RENAME_DIRECTORIES.keys())
def test_rename_directories(mainwin, make_audio, tmp_path, qtbot, user, rename_directories):
    # tut2.txt: "if the Pattern Combo contained, %artist% - %album%, it would
    # behave the same way as file renaming (except on the directory)". Two
    # of the three files share a folder, which is renamed once.
    music = tmp_path / 'music'
    for folder, name, artist, album in [('other', '03.mp3', 'Before The Fame', 'The Vinyl LP'),
                                        ('unsorted', '01.mp3', 'Relatively Unknown', 'Fans like it'),
                                        ('unsorted', '02.mp3', 'Relatively Unknown', 'Fans like it')]:
        make_audio(name, music / folder, artist=artist, album=album, title=name)
    mainwin.openDir(str(music), False)
    model = mainwin._table.model()
    qtbot.waitUntil(lambda: model.rowCount() == 3)
    user.activate()
    mainwin._table.setFocus()
    user.press(Key.Key_A, Ctrl)
    qtbot.waitUntil(lambda: len(mainwin._table.selectedRows) == 3)
    set_pattern(user, '%artist% - %album%')
    assert mainwin.findChild(PatternCombo).currentText() == '%artist% - %album%'
    rename_directories(user)
    expected = [str(music / path) for path in ['Before The Fame - The Vinyl LP/03.mp3',
                                               'Relatively Unknown - Fans like it/01.mp3',
                                               'Relatively Unknown - Fans like it/02.mp3']]
    qtbot.waitUntil(lambda: sorted(audio.filepath for audio in model.taginfo) == expected)
    assert sorted(str(path) for path in music.rglob('*.mp3')) == expected


def test_rename_directories_needs_a_selection(mainwin, make_audio, tmp_path, qtbot, user):
    # menus.txt: "Renames the selected files' directories". With no file
    # selected, the command is greyed out.
    music = tmp_path / 'music'
    make_audio('01.mp3', music / 'unsorted', artist='Relatively Unknown', album='Fans like it', title='01.mp3')
    mainwin.openDir(str(music), False)
    qtbot.waitUntil(lambda: mainwin._table.model().rowCount() == 1)
    user.activate()
    user.click_cell(user.cell(0, 'title'))
    qtbot.waitUntil(lambda: len(mainwin._table.selectedRows) == 1)
    assert user.action('&Rename Directories').isEnabled()
    user.click_cell(user.cell(0, 'title'), Ctrl)
    qtbot.waitUntil(lambda: mainwin._table.selectedRows == [])
    assert not user.action('&Rename Directories').isEnabled()
