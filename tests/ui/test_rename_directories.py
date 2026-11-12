"""Rename Directories (the Convert menu and its toolbar, menus.txt), run from
the main window as a user runs it, on the selected files: "Renames the
selected files' directories based on the pattern in Pattern Combo. It's also
a shortcut for Tag->Dir." Synthetic files; their tags are function.txt's
examples.
"""
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

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


def tree(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob('*'))


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


def test_emptied_folders_are_left(mainwin, make_audio, tmp_path, qtbot, user):
    # function.txt, Tag to Dir: "Works as Tag To Filename (below), but
    # renames/moves directories instead". Tag to filename leaves the folders
    # a move empties. The absolute pattern is function.txt's
    # /mnt/music/%album%/... example.
    music = tmp_path / 'music'
    make_audio('01.mp3', music / 'Indie' / 'unsorted', album='Fans like it', title='t')
    mainwin.openDir(str(music), False)
    qtbot.waitUntil(lambda: mainwin._table.model().rowCount() == 1)
    user.activate()
    mainwin._table.setFocus()
    user.click_cell(user.cell(0, 'title'))
    set_pattern(user, str(tmp_path / 'library') + '/%album%')
    user.click_menu('&Rename Directories')
    moved = tmp_path / 'library' / 'Fans like it' / '01.mp3'
    qtbot.waitUntil(moved.exists)
    assert tree(tmp_path) == ['library', 'library/Fans like it', 'library/Fans like it/01.mp3',
                              'music', 'music/Indie']
    assert mainwin._table.model().taginfo[0].filepath == str(moved)


def test_into_its_own_subfolder(mainwin, make_audio, tmp_path, qtbot, user, dialogs):
    # A folder can't be moved into itself: the error says so, and the tree
    # is unchanged.
    music = tmp_path / 'music'
    path = make_audio('01.mp3', music / 'unsorted', album='Fans like it', title='t')
    mainwin.openDir(str(music), False)
    qtbot.waitUntil(lambda: mainwin._table.model().rowCount() == 1)
    user.activate()
    mainwin._table.setFocus()
    user.click_cell(user.cell(0, 'title'))
    dialogs.answer('QMessageBox.warning', QMessageBox.StandardButton.Ok)
    set_pattern(user, str(music / 'unsorted' / 'sub'))
    user.click_menu('&Rename Directories')
    qtbot.waitUntil(lambda: len(dialogs.calls) == 1)
    [(name, (parent, title, message), kwargs)] = dialogs.calls
    assert str(music / 'unsorted') in message
    assert 'Cannot move directory to a subdirectory within itself.' in message
    assert tree(tmp_path) == ['music', 'music/unsorted', 'music/unsorted/01.mp3']
    assert mainwin._table.model().taginfo[0].filepath == str(path)
