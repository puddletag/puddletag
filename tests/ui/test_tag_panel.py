"""The Tag Panel, as a user uses it: select files in the File-View, fill in
a field, Save (menus.txt: "Select some files, fill in some text and save
the changes (File->Save)"). Each save is checked in the files and in the
panel. Synthetic files.
"""
import os

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QStyle, QStyleOptionComboBox

from puddlestuff import audioinfo, constants
from puddlestuff.mainwin.tagpanel import FrameCombo

pytestmark = pytest.mark.ui

Key = Qt.Key
Alt = Qt.KeyboardModifier.AltModifier
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    """Three MP3s, all selected: the same artist, each its own title, and
    an album in the first two only."""
    music = tmp_path / 'music'
    paths = [make_audio('01.mp3', music, artist='Same', title='T1', album='A1'),
             make_audio('02.mp3', music, artist='Same', title='T2', album='A2'),
             make_audio('03.mp3', music, artist='Same', title='T3')]
    mainwin.openDir(str(music), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == 3)
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]
    user.activate()
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(2, 'title'), Shift)
    assert table.selectedRows == [0, 1, 2]
    # Qt counts the presses of an ambiguous shortcut for the whole app,
    # across windows (see test_alt_letter_again). Pressing Alt+B, the
    # Album field's own letter, starts each test as a session starts.
    user.press(Key.Key_B, Alt)
    [panel] = mainwin.findChildren(FrameCombo)
    return panel, paths


def in_file(path):
    return audioinfo.usertags(audioinfo.Tag(str(path)))


def shown(panel):
    return {field: combo.currentText() for field, combo in panel.combos.items()}


def listed(combo):
    return [combo.itemText(i) for i in range(combo.count())]


def fill(user, panel, field, text):
    """Clicks into the field, selects its text and types over it."""
    user.click(panel.combos[field].lineEdit())
    user.press(Key.Key_A, Ctrl)
    user.type(text)


def saved(qtbot, paths, field, value):
    """Saving several files writes them in a thread, behind a progress
    window."""
    qtbot.waitUntil(lambda: all(in_file(p).get(field) == value for p in paths))


def focused_field(panel):
    widget = QApplication.focusWidget()
    return next((field for field, combo in panel.combos.items()
                 if widget in (combo, combo.lineEdit())), None)


# "Notice that the artist combo box contains Bob Marley & The Wailers.
# This is because all files have the same artist. On occasions where the
# value differs between files it would contain <keep>" (tut1.txt): a
# field one file lacks differs too.

def test_shown_values(loaded):
    panel, paths = loaded
    assert shown(panel) == {'album': '<keep>', 'artist': 'Same', 'comment': '', 'genre': '',
                            'title': '<keep>', 'track': '', 'year': ''}


# Save: "Save's whatever's currently entered in the Tag Panel to the
# selected files" (menus.txt), from File->Save, its toolbar button
# ("click Save", tut1.txt) or Ctrl+S.

SAVE = {
    'File menu': lambda user: user.click_menu('&Save'),
    'toolbar': lambda user: user.click_toolbar('&Save'),
    'Ctrl+S': lambda user: user.press(Key.Key_S, Ctrl),
}


@pytest.mark.parametrize('save', SAVE.values(), ids=SAVE.keys())
def test_save(user, loaded, qtbot, save):
    panel, paths = loaded
    fill(user, panel, 'album', 'New album')
    save(user)
    saved(qtbot, paths, 'album', ['New album'])
    assert [in_file(p) for p in paths] == [
        {'album': ['New album'], 'artist': ['Same'], 'title': ['T1']},
        {'album': ['New album'], 'artist': ['Same'], 'title': ['T2']},
        {'album': ['New album'], 'artist': ['Same'], 'title': ['T3']}]
    assert [audio['album'] for audio in user.table.model().taginfo] == [['New album']] * 3
    assert shown(panel)['album'] == 'New album'


def test_nothing_written_before_save(user, loaded, qtbot):
    # "fill in some text and save the changes": filling in alone writes
    # nothing.
    panel, paths = loaded
    fill(user, panel, 'album', 'New album')
    user.press(Key.Key_Tab)
    qtbot.wait(200)
    assert [in_file(p).get('album') for p in paths] == [['A1'], ['A2'], None]


def test_keep_leaves_each_files_value(user, loaded, qtbot):
    # "<keep>, signifying that upon saving that field will remain unchanged
    # for each file" (tut1.txt): album and title stay <keep>.
    panel, paths = loaded
    fill(user, panel, 'artist', 'New artist')
    user.press(Key.Key_S, Ctrl)
    saved(qtbot, paths, 'artist', ['New artist'])
    assert [in_file(p) for p in paths] == [
        {'album': ['A1'], 'artist': ['New artist'], 'title': ['T1']},
        {'album': ['A2'], 'artist': ['New artist'], 'title': ['T2']},
        {'artist': ['New artist'], 'title': ['T3']}]


def test_blank_removes_the_field(user, loaded, qtbot):
    # "To remove a field, change the text to <blank> and the field'll be
    # removed upon saving." (tut1.txt)
    panel, paths = loaded
    fill(user, panel, 'artist', '<blank>')
    user.press(Key.Key_S, Ctrl)
    saved(qtbot, paths, 'artist', None)
    assert [in_file(p) for p in paths] == [{'album': ['A1'], 'title': ['T1']},
                                           {'album': ['A2'], 'title': ['T2']},
                                           {'title': ['T3']}]
    assert 'artist' not in user.table.model().taginfo[0]


def test_multiple_values(user, loaded, qtbot):
    # "Like in the file-view multiple values are shown like value1\\value2.
    # Entering any value like that will automatically split it." (tut3.txt)
    panel, paths = loaded
    fill(user, panel, 'title', 'One\\\\Two')
    user.press(Key.Key_S, Ctrl)
    saved(qtbot, paths, 'title', ['One', 'Two'])
    assert shown(panel)['title'] == 'One\\\\Two'


def test_genre_list(loaded):
    # "The list of genres as used in the Tag Panel" (preferences.txt): a
    # fresh profile's, ID3's genres, before the selected files' values.
    panel, paths = loaded
    assert listed(panel.combos['genre']) == ['<keep>', '<blank>'] + audioinfo.GENRES + ['']


# "Use & in your Title to create an accelerator eg. '&Artist' will allow
# you to set focus to the relevant combo box by pressing 'Alt+A'"
# (preferences.txt); "Pressing Alt+B will switch the focus to the Album
# field" (tut3.txt). A fresh profile's titles: &Artist, &Title, Al&bum,
# T&rack, &Year, &Genre, &Comment.

LETTERS = {'A': 'artist', 'B': 'album', 'C': 'comment', 'G': 'genre', 'R': 'track', 'T': 'title',
           'Y': 'year'}
# These are also the letters of menus: Qt then alternates between the
# field and the menu, so every other press opens the menu.
MENUS = {'A': '&Actions', 'C': '&Convert', 'G': 'Ta&g Tools', 'T': '&Tools'}


@pytest.mark.parametrize('letter, field', LETTERS.items())
def test_alt_letter(user, loaded, letter, field):
    panel, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    user.press(getattr(Key, 'Key_' + letter), Alt)
    assert focused_field(panel) == field


def again(letter, field):
    if letter not in MENUS:
        return letter, field
    return pytest.param(letter, field, marks=pytest.mark.xfail(
        strict=True, reason=f'Alt+{letter} is also the {MENUS[letter]} menu\'s letter'))


@pytest.mark.parametrize('letter, field', [again(*item) for item in LETTERS.items()])
def test_alt_letter_again(user, loaded, letter, field):
    panel, paths = loaded
    key = getattr(Key, 'Key_' + letter)
    user.click_cell(user.cell(0, 'title'))
    user.press(key, Alt)
    user.click_cell(user.cell(1, 'title'))
    user.press(key, Alt)
    focused = focused_field(panel)
    menu = QApplication.activePopupWidget()
    if menu:
        menu.close()
    assert (focused, menu and menu.title()) == (field, None)


def test_tab_through_the_fields(user, loaded):
    # "I usually just switch to the first (Artist) and TAB through
    # everything." (tut3.txt)
    panel, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    user.press(Key.Key_A, Alt)
    order = [focused_field(panel)]
    for i in range(6):
        user.press(Key.Key_Tab)
        order.append(focused_field(panel))
    assert order == ['artist', 'title', 'album', 'track', 'year', 'genre', 'comment']


def test_save_undone_in_one_step(user, loaded, qtbot):
    # "Edit→Undo puts back all the files a Save wrote to, at once." (Ctrl+Z
    # in a Tag Panel field undoes the typing in the field.)
    panel, paths = loaded
    fill(user, panel, 'album', 'New album')
    user.press(Key.Key_S, Ctrl)
    saved(qtbot, paths, 'album', ['New album'])
    user.activate()
    user.click_menu('&Undo')
    assert [in_file(p).get('album') for p in paths] == [['A1'], ['A2'], None]
    assert [audio.get('album') for audio in user.table.model().taginfo] == [['A1'], ['A2'], None]
    assert not user.action('&Undo').isEnabled()


def test_cleared_field_removed(user, loaded, qtbot):
    # "Clearing a field removes it on saving, as <blank> does."
    panel, paths = loaded
    fill(user, panel, 'artist', '')
    user.press(Key.Key_Delete)
    assert shown(panel)['artist'] == ''
    user.press(Key.Key_S, Ctrl)
    saved(qtbot, paths, 'artist', None)
    assert [in_file(p) for p in paths] == [{'album': ['A1'], 'title': ['T1']},
                                           {'album': ['A2'], 'title': ['T2']},
                                           {'title': ['T3']}]


def test_pick_from_the_list(user, loaded, qtbot):
    # "Each field's list holds <keep>, <blank> and the values the selected
    # files have: pick one to give it to all of them." The file without an
    # album adds an empty value.
    panel, paths = loaded
    combo = panel.combos['album']
    option = QStyleOptionComboBox()
    combo.initStyleOption(option)
    arrow = combo.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, option,
                                         QStyle.SubControl.SC_ComboBoxArrow, combo)
    user.click(combo, arrow.center())
    view = combo.view()
    qtbot.waitUntil(view.isVisible)
    assert listed(combo) == ['<keep>', '<blank>', '', 'A1', 'A2']
    # Qt ignores a click on the list sooner than a double-click's interval
    # after it opened: it could be the end of the click that opened it.
    qtbot.wait(QApplication.doubleClickInterval() + 100)
    user.click(view.viewport(), view.visualRect(combo.model().index(combo.findText('A2'), 0)).center())
    qtbot.waitUntil(lambda: not view.isVisible())
    assert shown(panel)['album'] == 'A2'
    user.press(Key.Key_S, Ctrl)
    saved(qtbot, paths, 'album', ['A2'])


def test_unchanged_save_writes_nothing(user, loaded, qtbot):
    # The docs don't say; this is what puddletag does: nothing is saved,
    # and there's nothing to undo.
    panel, paths = loaded
    for path in paths:
        os.utime(path, (1000000000, 1000000000))
    user.press(Key.Key_S, Ctrl)
    qtbot.wait(200)
    assert [os.stat(p).st_mtime for p in paths] == [1000000000] * 3
    assert not user.action('&Undo').isEnabled()


def test_selecting_other_files_drops_unsaved_text(user, loaded, qtbot):
    # "What you type is written when you Save (File→Save). Selecting other
    # files before that throws it away." #878 asks for a question first.
    panel, paths = loaded
    fill(user, panel, 'album', 'Typed')
    user.click_cell(user.cell(0, 'title'))
    assert shown(panel)['album'] == 'A1'
    user.press(Key.Key_S, Ctrl)
    qtbot.wait(200)
    assert [in_file(p).get('album') for p in paths] == [['A1'], ['A2'], None]


def test_new_genre_joins_the_list(mainwin, user, loaded, qtbot):
    # "A genre you save in the Tag Panel that isn't in the list is added to
    # it" (preferences.txt): offered for other files, and kept when
    # puddletag closes.
    panel, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(1, 'title'), Shift)
    fill(user, panel, 'genre', 'Synthetic Genre')
    user.press(Key.Key_S, Ctrl)
    saved(qtbot, paths[:2], 'genre', ['Synthetic Genre'])
    user.activate()
    user.click_cell(user.cell(2, 'title'))
    assert 'Synthetic Genre' in listed(panel.combos['genre'])
    mainwin.close()
    with open(os.path.join(constants.CONFIGDIR, 'genres')) as genres:
        assert 'Synthetic Genre' in genres.read().splitlines()


def test_nothing_selected(user, loaded):
    # The docs don't say; this is what puddletag does.
    panel, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(0, 'title'), Ctrl)
    assert user.table.selectedRows == []
    assert shown(panel) == dict.fromkeys(panel.combos, '')
    assert not any(combo.isEnabled() for combo in panel.combos.values())
    assert not user.action('&Save').isEnabled()
