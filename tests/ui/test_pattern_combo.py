"""The Pattern Combo, the toolbar's editable list of patterns that File->Tag,
Tag->File, Format and Rename Directories use, and its Preferences page.
tut3.txt: "Pressing F8 switches focus between it and the file-view" and
"Patterns aren't saved by default. Just press Enter and whatever's currently
there will be added to the list"; preferences.txt (Patterns): "Modify the
patterns listed in the pattern combo here." Synthetic files and patterns.
"""
import json

import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import (QApplication, QPushButton, QStyle, QStyleOptionComboBox, QToolBar,
                             QToolButton)

from puddlestuff import audioinfo, constants
from puddlestuff.mainwin.patterncombo import PatternCombo, SettingsWin
from puddlestuff.puddlesettings import SettingsDialog

pytestmark = pytest.mark.ui

Key = Qt.Key


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    """One MP3, its Title cell clicked: the File-View has the focus."""
    music = tmp_path / 'music'
    path = make_audio('01.mp3', music, artist='Artist 1', title='Title 1')
    mainwin.openDir(str(music), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == 1)
    user.activate()
    user.click_cell(user.cell(0, 'title'))
    assert table.hasFocus()
    return mainwin.findChild(PatternCombo), path


def listed(combo):
    return [combo.itemText(i) for i in range(combo.count())]


def type_into_combo(user, text):
    """F8 goes to the combo with its text selected; the typing replaces it."""
    user.press(Key.Key_F8)
    user.type(text)


def pick(user, qtbot, combo, text):
    """Opens the combo's list with its arrow and clicks the pattern."""
    option = QStyleOptionComboBox()
    combo.initStyleOption(option)
    arrow = combo.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, option,
                                         QStyle.SubControl.SC_ComboBoxArrow, combo)
    user.click(combo, arrow.center())
    view = combo.view()
    qtbot.waitUntil(view.isVisible)
    # Qt ignores a click on the list sooner than a double-click's interval
    # after it opened: it could be the end of the click that opened it.
    qtbot.wait(QApplication.doubleClickInterval() + 100)
    user.click(view.viewport(), view.visualRect(combo.model().index(combo.findText(text), 0)).center())
    qtbot.waitUntil(lambda: not view.isVisible())


def saved_patterns():
    """What closing puddletag wrote to its config: the list, and the index
    of the pattern that was current."""
    with open(constants.CONFIG, encoding='utf-8') as f:
        return json.load(f)['editor']


def preferences():
    return next((w for w in QApplication.topLevelWidgets()
                 if isinstance(w, SettingsDialog) and w.isVisible()), None)


def open_preferences(user, qtbot):
    user.click_menu('&Preferences')
    qtbot.waitUntil(lambda: preferences() is not None)
    return preferences()


def open_patterns_page(user, qtbot):
    """Edit->Preferences, then Patterns in its list of pages."""
    dialog = open_preferences(user, qtbot)
    pages = dialog.listbox.model()
    [index] = [pages.index(row, 0) for row in range(pages.rowCount())
               if pages.data(pages.index(row, 0)) == 'Patterns']
    user.click(dialog.listbox.viewport(), dialog.listbox.visualRect(index).center())
    qtbot.waitUntil(lambda: isinstance(dialog.stack.currentWidget(), SettingsWin))
    return dialog, dialog.stack.currentWidget()


def on_page(page):
    return [page.listbox.item(row).text() for row in range(page.listbox.count())]


def click_row(user, page, row):
    listbox = page.listbox
    user.click(listbox.viewport(), listbox.visualItemRect(listbox.item(row)).center())


def page_button(page, name):
    """Add, Edit, Remove, Move Up and Move Down show only an icon, named
    by their tooltip; &Sort has its text."""
    [button] = [b for b in page.findChildren((QPushButton, QToolButton))
                if b.isVisible() and name in (b.toolTip(), b.text())]
    return button


def close_preferences(user, qtbot, dialog, button):
    """Clicks OK or Cancel. The main window gets the activation back, as on
    a desktop."""
    user.click(button)
    qtbot.waitUntil(lambda: not dialog.isVisible())
    user.activate()


def test_f8_switches_focus_between_the_combo_and_the_file_view(loaded, user):
    # tut3.txt: "Pressing F8 switches focus between it and the file-view."
    # The docs don't say the text is selected; this is what puddletag does,
    # so that typing replaces the pattern.
    combo, path = loaded
    user.press(Key.Key_F8)
    assert QApplication.focusWidget() is combo
    assert combo.lineEdit().selectedText() == combo.currentText()
    user.press(Key.Key_F8)
    assert user.table.hasFocus()


def test_f8_after_clicking_into_the_combo(loaded, user):
    # tut3.txt: "Pressing F8 switches focus between it and the file-view."
    combo, path = loaded
    user.click(combo.lineEdit())
    assert QApplication.focusWidget() is combo
    user.press(Key.Key_F8)
    assert user.table.hasFocus()


def test_enter_adds_the_pattern(loaded, user):
    # tut3.txt: "Just press Enter and whatever's currently there will be
    # added to the list." The docs don't say where; this is what puddletag
    # does: at the bottom, and the text stays.
    combo, path = loaded
    before = listed(combo)
    type_into_combo(user, '%title% - %album%')
    user.press(Key.Key_Return)
    assert listed(combo) == before + ['%title% - %album%']
    assert combo.currentText() == '%title% - %album%'


def test_typed_pattern_is_not_added(loaded, user):
    # tut3.txt: "Patterns aren't saved by default. Just press Enter and
    # whatever's currently there will be added to the list." Without Enter
    # nothing is added; the typed pattern is still the one the commands use.
    combo, path = loaded
    before = listed(combo)
    type_into_combo(user, '%title% - %album%')
    user.press(Key.Key_F8)
    assert listed(combo) == before
    assert combo.currentText() == '%title% - %album%'


def test_entered_pattern_is_kept_after_a_restart(loaded, user, restart):
    # tut3.txt: "Patterns aren't saved by default. Just press Enter and
    # whatever's currently there will be added to the list."
    combo, path = loaded
    before = listed(combo)
    type_into_combo(user, '%title% - %album%')
    user.press(Key.Key_Return)
    win = restart()
    new = win.findChild(PatternCombo)
    assert listed(new) == before + ['%title% - %album%']
    assert new.currentText() == '%title% - %album%'
    assert saved_patterns() == {'index': len(before), 'patterns': before + ['%title% - %album%']}


def test_typed_pattern_is_lost_after_a_restart(loaded, user, restart):
    # tut3.txt: "Patterns aren't saved by default. Just press Enter and
    # whatever's currently there will be added to the list." #421 asked why
    # typed patterns were gone: this is why.
    combo, path = loaded
    before = listed(combo)
    type_into_combo(user, '%title% - %album%')
    user.press(Key.Key_F8)
    win = restart()
    new = win.findChild(PatternCombo)
    assert listed(new) == before
    assert new.currentText() == before[0]
    assert saved_patterns() == {'index': 0, 'patterns': before}


def test_picked_pattern_is_current_after_a_restart(loaded, user, qtbot, restart):
    # The docs don't say; this is what puddletag does: the pattern picked
    # from the list is the current one again at the next start.
    combo, path = loaded
    before = listed(combo)
    pick(user, qtbot, combo, '%artist% - %album%')
    assert combo.currentText() == '%artist% - %album%'
    win = restart()
    assert win.findChild(PatternCombo).currentText() == '%artist% - %album%'
    assert saved_patterns() == {'index': before.index('%artist% - %album%'), 'patterns': before}


def test_enter_on_a_listed_pattern_adds_nothing(loaded, user):
    # The docs don't say; this is what puddletag does: a pattern already in
    # the list isn't added again, its first item becomes current. Delete
    # drops any completion; here there is none, since the typed text is an
    # exact item.
    combo, path = loaded
    before = listed(combo)
    type_into_combo(user, '%artist% - %title%')
    user.press(Key.Key_Delete)
    user.press(Key.Key_Return)
    assert listed(combo) == before
    assert combo.currentIndex() == before.index('%artist% - %title%')


def test_enter_on_an_empty_combo_adds_nothing(loaded, user):
    # The docs don't say; this is what puddletag does: an empty text isn't
    # added.
    combo, path = loaded
    before = listed(combo)
    user.press(Key.Key_F8)
    user.press(Key.Key_Backspace)  # F8 selected the whole text
    user.press(Key.Key_Return)
    assert listed(combo) == before
    assert combo.currentText() == ''


def test_typing_completes_to_a_listed_pattern(loaded, user):
    # tut3.txt: "Typing completes to the first saved pattern that starts the
    # same way; press Delete to keep just what you typed."
    combo, path = loaded
    type_into_combo(user, '%artist% - %album%')
    assert combo.currentText() == '%artist% - %album% - $num(%track%,2) - %title%'
    assert combo.lineEdit().selectedText() == ' - $num(%track%,2) - %title%'
    user.press(Key.Key_Delete)
    user.press(Key.Key_Return)
    assert combo.currentText() == '%artist% - %album%'
    assert combo.currentIndex() == combo.findText('%artist% - %album%')


def test_fresh_profile_patterns(loaded):
    # The docs don't list the default patterns; this is what puddletag
    # starts with, each pattern once.
    combo, path = loaded
    assert listed(combo) == ['%artist% - $num(%track%,2) - %title%',
                             '%artist% - %album% - $num(%track%,2) - %title%',
                             '%artist% - %title%', '%artist% - %album%',
                             '%artist% - Track %track%']
    assert combo.currentText() == '%artist% - $num(%track%,2) - %title%'


def test_page_lists_the_combo_patterns(loaded, user, qtbot):
    # preferences.txt (Patterns): "Modify the patterns listed in the pattern
    # combo here." (tut3.txt names the Tag Panel page for this: the page is
    # called Patterns.)
    combo, path = loaded
    dialog, page = open_patterns_page(user, qtbot)
    assert on_page(page) == listed(combo)
    close_preferences(user, qtbot, dialog, dialog.okbuttons.cancelButton)


def test_add_a_pattern(loaded, user, qtbot, dialogs):
    # preferences.txt (Patterns): "Modify the patterns listed in the pattern
    # combo here."
    combo, path = loaded
    before = listed(combo)
    dialog, page = open_patterns_page(user, qtbot)
    dialogs.answer('QInputDialog.getItem', ('%title% - %album%', True))
    user.click(page_button(page, 'Add'))
    assert on_page(page) == before + ['%title% - %album%']
    close_preferences(user, qtbot, dialog, dialog.okbuttons.okButton)
    assert listed(combo) == before + ['%title% - %album%']


def test_remove_a_pattern(loaded, user, qtbot):
    # preferences.txt (Patterns): "Modify the patterns listed in the pattern
    # combo here."
    combo, path = loaded
    before = listed(combo)
    dialog, page = open_patterns_page(user, qtbot)
    click_row(user, page, 0)
    user.click(page_button(page, 'Remove'))
    assert on_page(page) == before[1:]
    close_preferences(user, qtbot, dialog, dialog.okbuttons.okButton)
    assert listed(combo) == before[1:]


MOVES = {
    'Move Down': (0, lambda p: [p[1], p[0]] + p[2:]),
    'Move Up': (-1, lambda p: p[:-2] + [p[-1], p[-2]]),
}


@pytest.mark.parametrize('name', sorted(MOVES))
def test_move_a_pattern(loaded, user, qtbot, name):
    # preferences.txt (Patterns): "Modify the patterns listed in the pattern
    # combo here."
    combo, path = loaded
    before = listed(combo)
    row, expected = MOVES[name]
    dialog, page = open_patterns_page(user, qtbot)
    click_row(user, page, row % len(before))
    user.click(page_button(page, name))
    assert on_page(page) == expected(before)
    close_preferences(user, qtbot, dialog, dialog.okbuttons.okButton)
    assert listed(combo) == expected(before)


EDIT = {
    'double-click': lambda user, page: user.double_click(
        page.listbox.viewport(), page.listbox.visualItemRect(page.listbox.item(0)).center()),
    'Edit button': lambda user, page: (click_row(user, page, 0), user.click(page_button(page, 'Edit'))),
}


@pytest.mark.parametrize('way', sorted(EDIT))
def test_edit_a_pattern(loaded, user, qtbot, dialogs, way):
    # preferences.txt (Patterns): "Modify the patterns listed in the pattern
    # combo here."
    combo, path = loaded
    before = listed(combo)
    dialog, page = open_patterns_page(user, qtbot)
    dialogs.answer('QInputDialog.getItem', ('%title% - %album%', True))
    EDIT[way](user, page)
    assert on_page(page) == ['%title% - %album%'] + before[1:]
    close_preferences(user, qtbot, dialog, dialog.okbuttons.okButton)
    assert listed(combo) == ['%title% - %album%'] + before[1:]


def test_cancel_changes_nothing(loaded, user, qtbot):
    # The docs don't say; this is what puddletag does: Cancel leaves the
    # combo's list as it was.
    combo, path = loaded
    before = listed(combo)
    dialog, page = open_patterns_page(user, qtbot)
    click_row(user, page, 0)
    user.click(page_button(page, 'Remove'))
    assert on_page(page) == before[1:]
    close_preferences(user, qtbot, dialog, dialog.okbuttons.cancelButton)
    assert listed(combo) == before


def test_sort(loaded, user, qtbot):
    # The docs don't say; this is what puddletag does: the first click on
    # Sort sorts Z to A, the second A to Z.
    combo, path = loaded
    before = listed(combo)
    dialog, page = open_patterns_page(user, qtbot)
    user.click(page_button(page, '&Sort'))
    assert on_page(page) == sorted(before, reverse=True)
    user.click(page_button(page, '&Sort'))
    assert on_page(page) == sorted(before)
    close_preferences(user, qtbot, dialog, dialog.okbuttons.okButton)
    assert listed(combo) == sorted(before)


def test_edited_list_is_kept_after_a_restart(loaded, user, qtbot, dialogs, restart):
    # preferences.txt (Patterns): "Modify the patterns listed in the pattern
    # combo here."
    combo, path = loaded
    before = listed(combo)
    dialog, page = open_patterns_page(user, qtbot)
    dialogs.answer('QInputDialog.getItem', ('%title% - %album%', True))
    user.click(page_button(page, 'Add'))
    close_preferences(user, qtbot, dialog, dialog.okbuttons.okButton)
    win = restart()
    assert listed(win.findChild(PatternCombo)) == before + ['%title% - %album%']
    assert saved_patterns()['patterns'] == before + ['%title% - %album%']


def test_preferences_ok_keeps_a_typed_pattern(loaded, user, qtbot):
    # The docs don't say; a pattern being used shouldn't be lost by saving
    # preferences. OK on the General page, Patterns never opened.
    combo, path = loaded
    type_into_combo(user, '%title% - %album%')
    user.press(Key.Key_F8)
    dialog = open_preferences(user, qtbot)
    close_preferences(user, qtbot, dialog, dialog.okbuttons.okButton)
    assert combo.currentText() == '%title% - %album%'


def test_preferences_ok_keeps_a_picked_pattern(loaded, user, qtbot):
    # The docs don't say; a pattern being used shouldn't be lost by saving
    # preferences.
    combo, path = loaded
    pick(user, qtbot, combo, '%artist% - %album%')
    dialog = open_preferences(user, qtbot)
    close_preferences(user, qtbot, dialog, dialog.okbuttons.okButton)
    assert combo.currentText() == '%artist% - %album%'
    assert combo.currentIndex() == combo.findText('%artist% - %album%')


def test_picked_pattern_feeds_format(user, loaded, qtbot):
    # menus.txt: Format "Applies the Format Value function to the selected
    # files using the pattern in the Pattern Combo". The pattern is picked
    # from the list here, not typed.
    combo, path = loaded
    pick(user, qtbot, combo, '%artist% - %title%')
    assert combo.currentText() == '%artist% - %title%'
    user.click_toolbar('&Format')
    qtbot.waitUntil(lambda: audioinfo.Tag(str(path)).get('title') == ['Artist 1 - Title 1'])
    assert user.table.model().taginfo[0]['title'] == ['Artist 1 - Title 1']


def test_typed_pattern_previews_in_the_status_bar(mainwin, user, loaded, qtbot):
    # The docs don't say; this is what puddletag does: the pointer over
    # Tag->File shows the name the typed pattern would give.
    combo, path = loaded
    type_into_combo(user, '%title% x')
    user.press(Key.Key_F8)
    action = user.action('&Tag->File')
    [button] = [bar.widgetForAction(action) for bar in mainwin.findChildren(QToolBar)
                if bar.widgetForAction(action)]
    # A move to where the pointer already is sends the window no event.
    qtbot.mouseMove(mainwin.windowHandle(), QPoint(5, 5))
    qtbot.mouseMove(button)
    qtbot.waitUntil(lambda: mainwin.statusBar().currentMessage()
                    == f'New Filename: <b>{path.parent / "Title 1 x.mp3"}</b>')
    assert path.exists()
