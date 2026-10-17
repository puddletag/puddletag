"""File→Tag (menus.txt: "Convert the selected files to tags using the
pattern in the Pattern Combo"), run as a user runs it: the toolbar button,
the Convert menu and Ctrl+T. Each result is checked in the files and in
the table. The matching rules themselves are in
tests/unit/test_filename_patterns.py. Synthetic files, without tags.
"""
import pytest
from PyQt6.QtCore import Qt

from puddlestuff import audioinfo

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier

# tut1.txt's album, its first file named as in the tutorial. Synthetic
# titles for the others.
TITLES = ['Positive Vibration', 'Punky Reggae Party', 'Exodus']
NAMES = [f'Bob Marley & The Wailers - 0{i} - {title}.mp3' for i, title in enumerate(TITLES, 1)]


def load(mainwin, qtbot, user, paths):
    mainwin.openDir(str(paths[0].parent), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == len(paths))
    user.activate()
    table.setFocus()
    return table


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    paths = [make_audio(name, tmp_path / 'Bob Marley - Babylon By Bus') for name in NAMES]
    return load(mainwin, qtbot, user, paths), paths


def in_file(path, *fields):
    tag = audioinfo.Tag(str(path))
    return [tag.get(field) for field in fields]


def set_pattern(user, pattern):
    """F8 goes to the Pattern Combo, its text selected, and back
    (tut3.txt: "Pressing F8 switches focus between it and the
    file-view")."""
    user.press(Key.Key_F8)
    user.type(pattern)
    user.press(Key.Key_F8)


FILE_TO_TAG = {
    'toolbar': lambda user: user.click_toolbar('&File->Tag'),
    'Convert menu': lambda user: user.click_menu('&File->Tag'),
    'Ctrl+T': lambda user: user.press(Key.Key_T, Ctrl),
}


@pytest.mark.parametrize('file_to_tag', FILE_TO_TAG.values(), ids=FILE_TO_TAG.keys())
def test_tutorial(user, loaded, qtbot, file_to_tag):
    # tut1.txt: "After typing %artist% - %track% - %title% into the Pattern
    # Combo and using File->Tag from the Convert menu", on the first file,
    # then "Just by pressing Ctrl-A to select everything and using
    # File->Tag again".
    table, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    set_pattern(user, '%artist% - %track% - %title%')
    file_to_tag(user)
    qtbot.waitUntil(lambda: in_file(paths[0], 'title') == [['Positive Vibration']])
    assert in_file(paths[0], 'artist', 'track') == [['Bob Marley & The Wailers'], ['01']]
    assert in_file(paths[1], 'title') == [None]
    user.press(Key.Key_A, Ctrl)
    file_to_tag(user)
    qtbot.waitUntil(lambda: in_file(paths[2], 'title') == [['Exodus']])
    user.activate()
    assert [in_file(p, 'artist', 'track', 'title') for p in paths] == [
        [['Bob Marley & The Wailers'], [f'0{i}'], [title]] for i, title in enumerate(TITLES, 1)]
    assert [audio['title'] for audio in table.model().taginfo] == [[title] for title in TITLES]


def test_folder_names(user, mainwin, make_audio, tmp_path, qtbot):
    # menus.txt: "For a file with path '/home/cpuddle/Music/Justin Bieber -
    # Dunno/01 - Kinda Terrible.mp3' you could use a pattern like
    # '%artist% - %album%/%track% - %title%' to retrieve the following tag,
    # artist=Justin Bieber, album=Dunno, track=01, title=Kinda Terrible."
    path = make_audio('01 - Kinda Terrible.mp3', tmp_path / 'Music' / 'Justin Bieber - Dunno')
    load(mainwin, qtbot, user, [path])
    user.click_cell(user.cell(0, 'title'))
    set_pattern(user, '%artist% - %album%/%track% - %title%')
    user.press(Key.Key_T, Ctrl)
    qtbot.waitUntil(lambda: in_file(path, 'title') == [['Kinda Terrible']])
    assert in_file(path, 'artist', 'album', 'track') == [['Justin Bieber'], ['Dunno'], ['01']]


def test_name_the_pattern_does_not_match(user, mainwin, make_audio, tmp_path, qtbot):
    # menus.txt: "A file whose name the pattern doesn't match is left as it
    # is"; the other selected files are written.
    paths = [make_audio('Artist - Title.mp3', tmp_path / 'music'),
             make_audio('track01.mp3', tmp_path / 'music', title='Kept')]
    table = load(mainwin, qtbot, user, paths)
    user.press(Key.Key_A, Ctrl)
    set_pattern(user, '%artist% - %title%')
    user.press(Key.Key_T, Ctrl)
    qtbot.waitUntil(lambda: in_file(paths[0], 'title') == [['Title']])
    user.activate()
    assert in_file(paths[1], 'artist', 'title') == [None, ['Kept']]
    assert table.model().taginfo[1].get('title') == ['Kept']
