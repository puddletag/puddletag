"""Tag→File (menus.txt: "Uses the pattern in the Pattern Combo to carry out
the Tag to File function"), run as a user runs it: the toolbar button, the
Convert menu and Ctrl+F. Each rename is checked on disk and in the table.
The pattern rules themselves are in tests/unit/test_filename_patterns.py.
Synthetic files.
"""
import os

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier

# tut1.txt's album: Bob Marley & The Wailers, track numbers with a leading
# zero. Synthetic titles.
TITLES = ['Positive Vibration', 'Punky Reggae Party', 'Exodus']


def load(mainwin, qtbot, user, paths):
    mainwin.openDir(str(paths[0].parent), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == len(paths))
    user.activate()
    table.setFocus()
    return table


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    music = tmp_path / 'Bob Marley - Babylon By Bus'
    paths = [make_audio(f'Bob Marley & The Wailers - 0{i} - {title}.mp3', music,
                        artist='Bob Marley & The Wailers', tracknumber=f'0{i}', title=title)
             for i, title in enumerate(TITLES, 1)]
    return load(mainwin, qtbot, user, paths), paths


def set_pattern(user, pattern):
    """F8 goes to the Pattern Combo, its text selected, and back
    (tut3.txt: "Pressing F8 switches focus between it and the
    file-view")."""
    user.press(Key.Key_F8)
    user.type(pattern)
    user.press(Key.Key_F8)


def select_all_rows(user, rows):
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(rows - 1, 'title'), Shift)


def renamed(user, qtbot, folder, names):
    """Several files are renamed in a thread, behind a progress window."""
    qtbot.waitUntil(lambda: sorted(os.listdir(folder)) == sorted(names))
    user.activate()


TAG_TO_FILE = {
    'toolbar': lambda user: user.click_toolbar('&Tag->File'),
    'Convert menu': lambda user: user.click_menu('&Tag->File'),
    'Ctrl+F': lambda user: user.press(Key.Key_F, Ctrl),
}


@pytest.mark.parametrize('tag_to_file', TAG_TO_FILE.values(), ids=TAG_TO_FILE.keys())
def test_tutorial_renames(user, loaded, qtbot, tag_to_file):
    # tut1.txt: "some people like their filenames in a %track% - %title%
    # format. This can be done by entering it in the pattern combo and
    # using Tag-File", then "I don't want any [leading zeroes] so I'll use
    # $num(%track%, 1) and rename the files again using Tag->File."
    table, paths = loaded
    folder = paths[0].parent
    select_all_rows(user, 3)
    set_pattern(user, '%track% - %title%')
    tag_to_file(user)
    first = [f'0{i} - {title}.mp3' for i, title in enumerate(TITLES, 1)]
    renamed(user, qtbot, folder, first)
    assert [audio.filepath for audio in table.model().taginfo] == [str(folder / name) for name in first]
    set_pattern(user, '$num(%track%, 1) - %title%')
    tag_to_file(user)
    second = [f'{i} - {title}.mp3' for i, title in enumerate(TITLES, 1)]
    renamed(user, qtbot, folder, second)
    assert [audio.filepath for audio in table.model().taginfo] == [str(folder / name) for name in second]


def test_non_ascii_names(user, mainwin, make_audio, tmp_path, qtbot):
    # #131: renaming with accented letters in the tags froze; #398: no
    # name with a Λ. Synthetic tags.
    path = make_audio('song.mp3', tmp_path / 'music', artist='Café Λ', title='Ünïcode 藏經')
    table = load(mainwin, qtbot, user, [path])
    user.click_cell(user.cell(0, 'title'))
    set_pattern(user, '%artist% - %title%')
    user.press(Key.Key_F, Ctrl)
    qtbot.waitUntil(lambda: os.listdir(path.parent) == ['Café Λ - Ünïcode 藏經.mp3'])
    assert table.model().taginfo[0].filepath == str(path.parent / 'Café Λ - Ünïcode 藏經.mp3')


@pytest.mark.skipif(os.geteuid() == 0, reason='root can rename in a read-only folder')
def test_read_only_folder(user, loaded, qtbot, dialogs):
    # A file Tag->File can't rename is reported, with the question whether
    # to go on with the others, and it keeps its name, on disk and in the
    # table.
    table, paths = loaded
    folder = paths[0].parent
    names = sorted(os.listdir(folder))
    dialogs.answer('QMessageBox.exec', *[QMessageBox.StandardButton.Yes] * 3)
    os.chmod(folder, 0o555)
    try:
        select_all_rows(user, 3)
        set_pattern(user, '%track% - %title%')
        user.press(Key.Key_F, Ctrl)
        qtbot.waitUntil(lambda: len(dialogs.calls) == 3)
    finally:
        os.chmod(folder, 0o755)
    messages = [box.text() for name, (box,), kwargs in dialogs.calls]
    assert all('Permission denied' in m and 'Do you want to continue?' in m for m in messages)
    assert sorted(os.listdir(folder)) == names
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]
