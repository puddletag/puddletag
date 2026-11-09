"""Preferences > Shortcuts as a user drives it: a Shortcut cell double-clicked, a key
pressed or the cell's x clicked, then OK or Cancel; the commands' keys checked on their
menu items, by pressing them, in the saved user_shortcuts file and after a restart
(preferences.txt, menus.txt). Files, keys and profiles are synthetic."""
import os

import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QApplication, QLabel

from puddlestuff import constants, tagmodel
from puddlestuff.puddleobjects import PuddleConfig
from puddlestuff.puddlesettings import SettingsDialog
from puddlestuff.shortcutsettings import ActionEditorWidget

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier

USER_SHORTCUTS = os.path.join(constants.CONFIGDIR, 'user_shortcuts')


def shortcuts_page(user):
    """Edit > Preferences, then Shortcuts in its list: the window and the page's table."""
    window = user.open_preferences('Shortcuts')
    return window, window.stack.currentWidget().actionTable


def key_cell(table, name):
    """The Shortcut cell of the command's row."""
    [row] = [r for r in range(table.rowCount()) if table.item(r, 0).text() == name]
    return table.item(row, 1)


def open_key_editor(user, qtbot, table, name):
    """Double-clicks the command's Shortcut cell (preferences.txt:154); the editor that
    opens takes the keyboard."""
    cell = key_cell(table, name)
    table.scrollToItem(cell)
    user.double_click(table.viewport(), table.visualItemRect(cell).center())
    qtbot.waitUntil(lambda: isinstance(QApplication.focusWidget(), ActionEditorWidget))
    return QApplication.focusWidget()


def type_key(user, qtbot, table, name, key, modifier=Ctrl):
    """Enters the key in the command's cell. The editor closes and is deleted on the
    first key that isn't a modifier: don't touch it afterwards."""
    open_key_editor(user, qtbot, table, name)
    user.press(key, modifier)


def click_x(user, qtbot, table, name):
    """Clicks the x drawn at the right of the cell's editor, which empties the cell."""
    editor = open_key_editor(user, qtbot, table, name)
    size = editor.height() / 2
    user.click(editor, QPoint(int(editor.width() - size / 2 - 2), int(size)))


def cells(table, *names):
    return {name: key_cell(table, name).text() for name in names}


def saved(name):
    """The key saved for the command; None when none is."""
    return PuddleConfig(USER_SHORTCUTS).get('shortcuts', name, None)


def keys(user, name):
    """The command's keys, as its menu item has them."""
    return [k.toString() for k in user.action(name).shortcuts()]


def preferences_shown(win):
    return any(w.isVisible() for w in win.findChildren(SettingsDialog))


def notice(window):
    """The texts of the Shortcuts page's visible labels."""
    return [label.text() for label in window.stack.currentWidget().findChildren(QLabel)
            if label.isVisible()]


def restarted(restart, qtbot, user):
    """Quits puddletag and starts it again: the new window and a user driving it."""
    win = restart()
    return win, type(user)(qtbot, win)


def load_one(win, user, qtbot, folder):
    """Opens the folder (one file) in the window, then Select All (Ctrl+A,
    menus.txt:125): an unambiguous key, so Qt's count of ambiguous presses starts
    afresh, and the file is selected."""
    win.openDir(str(folder), False)
    qtbot.waitUntil(lambda: win._table.model().rowCount() == 1)
    user.activate()
    user.table.setFocus()
    user.press(Key.Key_A, Ctrl)
    qtbot.waitUntil(lambda: win._table.selectedRows == [0])


@pytest.fixture
def played(monkeypatch):
    """What Play started: its player command and files."""
    calls = []
    monkeypatch.setattr(tagmodel, 'Popen', lambda args: calls.append(args))
    return calls


@pytest.fixture
def play_and_preferences_on_ctrl_p(clean_profile):
    """A profile an earlier version saved after #1090's steps and a later OK: Play and
    Preferences both on Ctrl+P. List it before mainwin."""
    for name in ('&Play', '&Preferences'):
        PuddleConfig(USER_SHORTCUTS).set('shortcuts', name, 'Ctrl+P')


def test_typed_key_reaches_the_menu_item_and_runs_the_command(mainwin, user, qtbot):
    # "With this panel you can edit the keyboard shortcuts of any menu item in puddletag.
    # Just double-click on the desired shortcut in the shortcut column and enter the
    # desired shortcut." (preferences.txt:154); Preferences "Opens the Preferences
    # dialog." (menus.txt:145-147). Ctrl+L is synthetic: no command has it.
    window, table = shortcuts_page(user)
    type_key(user, qtbot, table, '&Preferences', Key.Key_L)
    assert cells(table, '&Preferences') == {'&Preferences': 'Ctrl+L'}
    user.close_preferences(window)
    user.table.setFocus()
    user.press(Key.Key_L, Ctrl)
    qtbot.waitUntil(lambda: preferences_shown(mainwin))
    assert keys(user, '&Preferences') == ['Ctrl+L']
    assert saved('&Preferences') == 'Ctrl+L'
    [reopened] = [w for w in mainwin.findChildren(SettingsDialog) if w.isVisible()]
    user.close_preferences(reopened, 'Cancel')


def test_ctrl_alone_changes_nothing(mainwin, user, qtbot):
    # The docs don't say; this is what puddletag does: Ctrl pressed alone closes the key
    # editor and leaves the key as it was. Save is "Save (Ctrl+S)" (menus.txt:25).
    window, table = shortcuts_page(user)
    open_key_editor(user, qtbot, table, '&Save')
    user.press(Key.Key_Control)
    qtbot.waitUntil(lambda: not isinstance(QApplication.focusWidget(), ActionEditorWidget))
    assert cells(table, '&Save') == {'&Save': 'Ctrl+S'}
    user.close_preferences(window)
    assert keys(user, '&Save') == ['Ctrl+S']
    assert not os.path.exists(USER_SHORTCUTS)


def test_x_clears_the_key(mainwin, user, qtbot):
    # The docs don't say; this is what puddletag does: the x in a cell's editor takes
    # the command's key away.
    window, table = shortcuts_page(user)
    click_x(user, qtbot, table, '&Save')
    assert cells(table, '&Save') == {'&Save': ''}
    user.close_preferences(window)
    assert keys(user, '&Save') == []
    assert saved('&Save') == ''


def test_cancel_keeps_the_old_keys(mainwin, user, qtbot):
    # "Cancel or Esc closes the window without saving anything" (preferences.txt).
    # Ctrl+L is synthetic.
    window, table = shortcuts_page(user)
    type_key(user, qtbot, table, '&Preferences', Key.Key_L)
    click_x(user, qtbot, table, '&Save')
    user.close_preferences(window, 'Cancel')
    assert keys(user, '&Preferences') == []
    assert keys(user, '&Save') == ['Ctrl+S']
    window, table = shortcuts_page(user)
    assert cells(table, '&Preferences', '&Save') == {'&Preferences': '', '&Save': 'Ctrl+S'}
    assert not os.path.exists(USER_SHORTCUTS)
    user.close_preferences(window, 'Cancel')


def test_new_key_survives_a_restart(mainwin, user, qtbot, restart):
    # The docs don't say; this is what puddletag does: a key typed in the page and saved
    # with OK is there at the next start (preferences.txt:154). Ctrl+L is synthetic.
    window, table = shortcuts_page(user)
    type_key(user, qtbot, table, '&Preferences', Key.Key_L)
    user.close_preferences(window)
    win, user2 = restarted(restart, qtbot, user)
    user2.activate()
    user2.table.setFocus()
    user2.press(Key.Key_L, Ctrl)
    qtbot.waitUntil(lambda: preferences_shown(win))
    assert keys(user2, '&Preferences') == ['Ctrl+L']


def test_two_commands_saved_on_one_key_run_neither(play_and_preferences_on_ctrl_p, mainwin, user, qtbot,
                                                   played, make_audio, tmp_path):
    # The docs don't say; this is what puddletag does: a key two enabled commands have
    # (Play and Preferences, from a synthetic saved file) runs neither.
    make_audio('01.mp3', tmp_path / 'music', title='title 1')
    load_one(mainwin, user, qtbot, tmp_path / 'music')
    user.press(Key.Key_P, Ctrl)
    qtbot.wait(300)
    assert not preferences_shown(mainwin)
    assert played == []
    assert keys(user, '&Play') == ['Ctrl+P']
    assert keys(user, '&Preferences') == ['Ctrl+P']


def test_shared_key_runs_the_only_enabled_command(play_and_preferences_on_ctrl_p, mainwin, user, qtbot,
                                                  played):
    # The docs don't say; this is what puddletag does: Play "Play's the currently
    # selected files" (menus.txt:31), so it is greyed out with nothing loaded, and the
    # key they share (synthetic saved file) runs Preferences.
    user.activate()
    user.table.setFocus()
    user.press(Key.Key_P, Ctrl)
    assert not user.action('&Play').isEnabled()
    qtbot.waitUntil(lambda: preferences_shown(mainwin))
    assert played == []


def test_cleared_key_stays_cleared_after_a_restart(mainwin, user, qtbot, restart):
    # The docs don't say; #255's report: a key cleared with the x and saved with OK
    # comes back at the next start.
    window, table = shortcuts_page(user)
    click_x(user, qtbot, table, '&Save')
    user.close_preferences(window)
    win, user2 = restarted(restart, qtbot, user)
    assert keys(user2, '&Save') == []
    assert saved('&Save') == ''


def test_key_taken_off_play_stays_off_after_a_restart(mainwin, user, qtbot, played, make_audio, tmp_path,
                                                      restart):
    # Play is "Play (Ctrl+P)" (menus.txt:29); #1090's report: Ctrl+P given to Preferences
    # is on Play again after a restart.
    window, table = shortcuts_page(user)
    click_x(user, qtbot, table, '&Play')
    type_key(user, qtbot, table, '&Preferences', Key.Key_P)
    user.close_preferences(window)
    win, user2 = restarted(restart, qtbot, user)
    make_audio('01.mp3', tmp_path / 'music', title='title 1')
    load_one(win, user2, qtbot, tmp_path / 'music')
    user2.press(Key.Key_P, Ctrl)
    qtbot.waitUntil(lambda: preferences_shown(win))
    assert played == []
    assert keys(user2, '&Play') == []
