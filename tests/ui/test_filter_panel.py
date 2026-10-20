"""The Filter (menus.txt: "Allows you to Filter the main-view using any
Filter Expressions"), run as a user runs it: an expression typed into the
Filter Panel and applied with Enter, the Go button or the box's list.
filter.txt: "If it evaluates to True for a file, then that file will be
shown. Otherwise, puddletag will hide it." The expressions themselves are
tested in tests/unit/test_filter.py. Each result is checked in the table,
and in the files where a command writes them. Synthetic files.

A plain word is searched for in every field, the file's path included, so
test names and ids don't contain the words searched for.
"""
import os

import pytest
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication, QPushButton

from puddlestuff import audioinfo
from puddlestuff.mainwin.filterwin import FilterView

pytestmark = pytest.mark.ui

Key = Qt.Key
Alt = Qt.KeyboardModifier.AltModifier
Ctrl = Qt.KeyboardModifier.ControlModifier
NoModifier = Qt.KeyboardModifier.NoModifier
Shift = Qt.KeyboardModifier.ShiftModifier


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    """Three MP3s; the first is filter.txt's example file."""
    music = tmp_path / 'music'
    paths = [make_audio('01.mp3', music, artist='Bongo Maffin', title='Monster'),
             make_audio('02.mp3', music, artist='Jon Smith', title='Angel'),
             make_audio('03.mp3', music, artist='Bongo Maffin', title='Monster (Live)')]
    mainwin.openDir(str(music), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == 3)
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]
    user.activate()
    table.setFocus()
    return table, paths


def in_file(path):
    return audioinfo.usertags(audioinfo.Tag(str(path)))


def shown(table):
    """The files the File-View shows, in its order."""
    return [os.path.basename(audio.filepath) for audio in table.model().taginfo]


def titles(table):
    return {os.path.basename(a.filepath): a['title'] for a in table.model().taginfo}


def filter_box(mainwin):
    [view] = mainwin.findChildren(FilterView)
    return view.combo.combo


def type_text(user, text):
    """Types text a key at a time. QTest takes only ASCII characters as
    keys; the others arrive as a keyboard layout sends them, a key event
    carrying the character."""
    for char in text:
        if char.isascii():
            user.press(char)
            continue
        widget = QApplication.focusWidget()
        for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            QApplication.sendEvent(widget, QKeyEvent(kind, 0, NoModifier, char))


def enter_filter(user, mainwin, text):
    """Clicks into the Filter box, types over its text and presses Enter.
    The filter is applied at once."""
    user.click(filter_box(mainwin).lineEdit())
    user.press(Key.Key_A, Ctrl)
    if text:
        type_text(user, text)
    else:
        user.press(Key.Key_Delete)
    user.press(Key.Key_Return)


def test_enter_applies_the_filter(user, loaded, mainwin):
    # filter.txt: "If it evaluates to True for a file, then that file will be
    # shown. Otherwise, puddletag will hide it." and "string: Evaluates to
    # True if a contains string in any of it's fields."
    table, paths = loaded
    enter_filter(user, mainwin, 'Maffin')
    assert shown(table) == ['01.mp3', '03.mp3']
    assert table.model().rowCount() == 2
    assert table.verticalHeader().count() == 2
    assert in_file(paths[1]) == {'artist': ['Jon Smith'], 'title': ['Angel']}


def test_go_button_applies_the_filter(user, loaded, mainwin):
    # filter.txt: "field HAS expr ... Eg. artist HAS Jon".
    table, paths = loaded
    user.click(filter_box(mainwin).lineEdit())
    type_text(user, 'artist HAS Jon')
    [view] = mainwin.findChildren(FilterView)
    [go] = [b for b in view.findChildren(QPushButton) if b.text() == 'Go']
    user.click(go)
    assert shown(table) == ['02.mp3']


@pytest.mark.parametrize('expression, expected', [
    pytest.param('title IS monster', ['01.mp3'], id='lower-is'),
    pytest.param('MAFFIN', ['01.mp3', '03.mp3'], id='upper-word'),
])
def test_case_is_ignored(user, loaded, mainwin, expression, expected):
    # filter.txt: "Comparisons ignore case, except GREATER and LESS between
    # texts." and the example "title IS Monster".
    table, paths = loaded
    enter_filter(user, mainwin, expression)
    assert shown(table) == expected


def test_a_new_filter_sees_every_file(user, loaded, mainwin):
    # filter.txt: "The filter expression will be evaluated for each file
    # loaded."
    table, paths = loaded
    enter_filter(user, mainwin, 'Maffin')
    assert shown(table) == ['01.mp3', '03.mp3']
    enter_filter(user, mainwin, 'artist HAS Jon')
    assert shown(table) == ['02.mp3']


def test_clearing_shows_every_file(user, loaded, mainwin):
    # The docs don't speak of an empty filter; every file shows, as with no
    # filter. The order has its own test.
    table, paths = loaded
    enter_filter(user, mainwin, 'Maffin')
    enter_filter(user, mainwin, '')
    assert sorted(shown(table)) == ['01.mp3', '02.mp3', '03.mp3']
    assert titles(table) == {
        '01.mp3': ['Monster'], '02.mp3': ['Angel'], '03.mp3': ['Monster (Live)']}


TOGGLE = {
    'F3': lambda user: user.press(Key.Key_F3),
    'Windows menu': lambda user: user.click_menu('Filter'),
}


@pytest.mark.parametrize('toggle', TOGGLE.values(), ids=TOGGLE.keys())
def test_panel_shown_and_hidden(user, loaded, mainwin, qtbot, toggle):
    # filter.txt: "They can be entered into the Filter Panel (Windows->Filter
    # or F3)." news.txt: "A filter like in Mp3tag. F3 shows/hides it."
    table, paths = loaded
    [view] = mainwin.findChildren(FilterView)
    action = user.action('Filter')
    assert view.isVisible() and action.isChecked()
    table.setFocus()
    toggle(user)
    qtbot.waitUntil(lambda: not view.isVisible())
    assert not action.isChecked()
    table.setFocus()
    toggle(user)
    qtbot.waitUntil(view.isVisible)
    assert action.isChecked()


@pytest.fixture
def loaded_non_ascii(mainwin, make_audio, tmp_path, qtbot, user):
    """Three MP3s with names in Latin and Greek letters; synthetic, #463
    gives no example."""
    music = tmp_path / 'music'
    paths = [make_audio('01.mp3', music, artist='Björk', title='Jóga'),
             make_audio('02.mp3', music, artist='Bjarne', title='Hav'),
             make_audio('03.mp3', music, artist='Λόγος', title='Ωμέγα')]
    mainwin.openDir(str(music), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == 3)
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]
    user.activate()
    table.setFocus()
    return table, paths


# #463: "Filtering doesn't work well when using a field that has
# non-English characters. No error message is shown, but nothing is
# filtered." filter.txt: "Strings are either a single word containing no
# white-space"; a word of any script is one.
NON_ASCII = pytest.mark.xfail(strict=True, reason='an unquoted word ends at its first non-ASCII letter (#463)')


@pytest.mark.parametrize('expression, expected', [
    pytest.param('artist HAS Λόγος', ['03.mp3'], id='I463-has', marks=NON_ASCII),
    pytest.param('artist IS björk', ['01.mp3'], id='I463-is', marks=NON_ASCII),
    pytest.param('artist IS "björk"', ['01.mp3'], id='I463-is-quoted'),
    pytest.param('björk', ['01.mp3'], id='I463-word', marks=NON_ASCII),
    pytest.param('Λόγος', ['03.mp3'], id='I463-word-greek'),
])
def test_non_ascii_text(mainwin, loaded_non_ascii, user, expression, expected):
    # filter.txt: "field HAS expr: Evaluates to True if expr is contained in
    # field"; "field IS expr: Evaluates to True if field=expr";
    # "Comparisons ignore case"; "string: Evaluates to True if a contains
    # string in any of it's fields."
    table, paths = loaded_non_ascii
    enter_filter(user, mainwin, expression)
    assert shown(table) == expected


def test_select_all_reaches_only_shown_files(loaded, mainwin, qtbot, user):
    # menus.txt: "Select All (Ctrl+A): It's obvious if you think about it."
    # Beyond it, Select All selects the files shown only, so an edit typed
    # over the selection writes those and leaves the hidden file alone.
    table, paths = loaded
    enter_filter(user, mainwin, 'Maffin')
    user.click_cell(user.cell(0, 'title'))
    user.press(Key.Key_A, Ctrl)
    assert table.selectedRows == [0, 1]
    user.press(Key.Key_F2)
    user.type('New')
    user.press(Key.Key_Return)
    qtbot.waitUntil(lambda: in_file(paths[2])['title'] == ['New'])
    user.activate()

    assert [in_file(p)['title'] for p in paths] == [['New'], ['Angel'], ['New']]
    enter_filter(user, mainwin, '')
    assert titles(table) == {'01.mp3': ['New'], '02.mp3': ['Angel'], '03.mp3': ['New']}


def test_format_reaches_only_shown_files(loaded, mainwin, qtbot, user):
    # menus.txt: "Applies the Format Value function to the selected files
    # using the pattern in the Pattern Combo." Beyond it, the selected
    # files are the ones shown: the hidden file isn't formatted.
    table, paths = loaded
    enter_filter(user, mainwin, 'Maffin')
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(1, 'title'), Shift)
    user.press(Key.Key_F8)
    user.type('%artist% - %title%')
    user.press(Key.Key_F8)
    user.click_toolbar('&Format')
    qtbot.waitUntil(lambda: in_file(paths[2])['title'] == ['Bongo Maffin - Monster (Live)'])
    user.activate()

    assert [in_file(p)['title'] for p in paths] == [
        ['Bongo Maffin - Monster'], ['Angel'], ['Bongo Maffin - Monster (Live)']]


def test_a_hidden_file_leaves_the_selection(loaded, mainwin, qtbot, user):
    # menus.txt: "Applies the Format Value function to the selected files
    # using the pattern in the Pattern Combo." Beyond it, a selected file
    # that the filter hides leaves the selection, and isn't selected again
    # when it is shown.
    table, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(2, 'title'), Shift)
    user.press(Key.Key_F8)
    user.type('%artist% - %title%')
    user.press(Key.Key_F8)
    enter_filter(user, mainwin, 'Maffin')
    assert [a.filepath for a in table.selectedTags] == [str(paths[0]), str(paths[2])]

    user.click_toolbar('&Format')
    qtbot.waitUntil(lambda: in_file(paths[2])['title'] == ['Bongo Maffin - Monster (Live)'])
    user.activate()

    assert in_file(paths[1])['title'] == ['Angel']
    enter_filter(user, mainwin, '')
    assert sorted(a.filepath for a in table.selectedTags) == [str(paths[0]), str(paths[2])]


def test_filter_stays_while_the_panel_is_hidden(loaded, mainwin, qtbot, user):
    # news.txt: "A filter like in Mp3tag. F3 shows/hides it." Beyond it,
    # hiding the panel doesn't clear the filter: the files stay hidden.
    table, paths = loaded
    enter_filter(user, mainwin, 'Maffin')
    table.setFocus()
    user.press(Key.Key_F3)
    [view] = mainwin.findChildren(FilterView)
    qtbot.waitUntil(lambda: not view.isVisible())

    assert shown(table) == ['01.mp3', '03.mp3']


def test_invalid_expression_shows_no_file(loaded, mainwin, user):
    # filter.txt: "If it evaluates to True for a file, then that file will
    # be shown." Beyond it, an expression that can't be evaluated (a regex
    # missing its ")", synthetic) shows no file, with no message, and the
    # next expression works.
    table, paths = loaded
    enter_filter(user, mainwin, 'title MATCHES "("')
    assert shown(table) == []

    enter_filter(user, mainwin, 'Maffin')
    assert shown(table) == ['01.mp3', '03.mp3']


def test_picking_from_the_list_applies_it(loaded, mainwin, qtbot, user):
    # menus.txt: "Allows you to Filter the main-view using any Filter
    # Expressions". Beyond it, an expression typed before is kept in the
    # box's list, and picking it from there applies it.
    table, paths = loaded
    enter_filter(user, mainwin, 'Maffin')
    enter_filter(user, mainwin, 'artist HAS Jon')
    box = filter_box(mainwin)
    assert [box.itemText(i) for i in range(box.count())] == ['Maffin', 'artist HAS Jon']
    assert shown(table) == ['02.mp3']

    user.press(Key.Key_Down, Alt)
    qtbot.waitUntil(box.view().isVisible)
    qtbot.wait(QApplication.doubleClickInterval() + 50)
    view = box.view()
    user.click(view.viewport(), view.visualRect(box.model().index(0, 0)).center())

    assert shown(table) == ['01.mp3', '03.mp3']
    assert box.lineEdit().text() == 'Maffin'


@pytest.mark.xfail(strict=True, reason="files the Filter hid come back at the bottom, out of the File-View's order")
def test_clearing_keeps_the_order(mainwin, loaded, user):
    # The docs are silent on the order. The files come back in the File-View's
    # sort order, the one they were loaded in.
    table, paths = loaded
    enter_filter(user, mainwin, 'artist HAS Jon')
    enter_filter(user, mainwin, '')
    assert shown(table) == ['01.mp3', '02.mp3', '03.mp3']


@pytest.mark.parametrize('append, expected', [
    pytest.param(True, ['01.mp3', '03.mp3', '04.mp3'], id='add-folder'),
    pytest.param(False, ['04.mp3'], id='open-folder'),
])
@pytest.mark.xfail(strict=True, reason="files loaded after the Filter was applied aren't filtered")
def test_loaded_files_are_filtered(mainwin, loaded, make_audio, tmp_path, qtbot, user, append, expected):
    # filter.txt: "The filter expression will be evaluated for each file
    # loaded. If it evaluates to True for a file, then that file will be
    # shown. Otherwise, puddletag will hide it."
    table, paths = loaded
    enter_filter(user, mainwin, 'Maffin')
    more = tmp_path / 'more'
    make_audio('04.mp3', more, artist='Bongo Maffin', title='Uhuru')
    make_audio('05.mp3', more, artist='Ana Pop', title='Uno')
    mainwin.openDir(str(more), append)
    qtbot.waitUntil(lambda: '04.mp3' in shown(table))
    assert shown(table) == expected
    assert filter_box(mainwin).lineEdit().text() == 'Maffin'


@pytest.mark.xfail(strict=True, reason='Write Previews writes only the files the Filter shows')
def test_write_previews_writes_hidden_files(mainwin, loaded, qtbot, user):
    # menus.txt: "If preview mode has been enabled and some changes were
    # made, they'll get written to the files, and Preview Mode is disabled."
    table, paths = loaded
    table.setFocus()
    user.press(Key.Key_P, Ctrl | Shift)
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(2, 'title'), Shift)
    user.press(Key.Key_F2)
    user.type('New')
    user.press(Key.Key_Return)
    enter_filter(user, mainwin, 'Maffin')
    table.setFocus()
    user.press(Key.Key_W, Ctrl)
    qtbot.waitUntil(lambda: in_file(paths[2])['title'] == ['New'])
    user.activate()
    assert [in_file(p)['title'] for p in paths] == [['New'], ['New'], ['New']]
    assert not table.model().previewMode
