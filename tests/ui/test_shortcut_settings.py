"""Preferences > Shortcuts as a user drives it: a Shortcut cell double-clicked, a key
pressed or the cell's x clicked, then OK or Cancel; the commands' keys checked on their
menu items, by pressing them, in the saved user_shortcuts file and after a restart
(preferences.txt, menus.txt). Files, keys and profiles are synthetic."""
import os

import pytest
from PyQt6.QtCore import QEvent, QPoint, QRect, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QAbstractItemView, QApplication, QLabel, QLineEdit

from puddlestuff import constants, tagmodel
from puddlestuff.puddleobjects import PuddleConfig
from puddlestuff.puddlesettings import SettingsDialog

pytestmark = pytest.mark.ui

Alt = Qt.KeyboardModifier.AltModifier
Ctrl = Qt.KeyboardModifier.ControlModifier
Key = Qt.Key
Keypad = Qt.KeyboardModifier.KeypadModifier
Meta = Qt.KeyboardModifier.MetaModifier
NoModifier = Qt.KeyboardModifier.NoModifier
Shift = Qt.KeyboardModifier.ShiftModifier

USER_SHORTCUTS = os.path.join(constants.CONFIGDIR, 'user_shortcuts')


def shortcuts_page(user):
    """Edit > Preferences, then Shortcuts in its list: the window and the page's table."""
    window = user.open_preferences('Shortcuts')
    return window, window.stack.currentWidget().actionTable


def key_cell(table, name):
    """The Shortcut cell of the command's row."""
    [row] = [r for r in range(table.rowCount()) if table.item(r, 0).text() == name]
    return table.item(row, 1)


def editing(table):
    """A cell's key editor is open."""
    return table.state() == QAbstractItemView.State.EditingState


def open_key_editor(user, qtbot, table, name):
    """Double-clicks the command's Shortcut cell (preferences.txt:155); the editor that
    opens has the keyboard focus."""
    cell = key_cell(table, name)
    table.scrollToItem(cell)
    user.double_click(table.viewport(), table.visualItemRect(cell).center())
    qtbot.waitUntil(lambda: editing(table))
    return QApplication.focusWidget()


def shown(editor):
    """The text the open key editor shows."""
    field = editor if isinstance(editor, (QLabel, QLineEdit)) else editor.findChild(QLineEdit)
    return field.text()


def hold(key, held=NoModifier):
    """Presses a modifier key and keeps it down. As a desktop sends it, the event carries
    the modifiers held before it; QTest can't let go of one modifier and keep another."""
    QApplication.sendEvent(QApplication.focusWidget(), QKeyEvent(QEvent.Type.KeyPress, key.value, held))


def let_go(key, held):
    """Lets go of a modifier key; held still includes it, as a desktop sends it."""
    QApplication.sendEvent(QApplication.focusWidget(), QKeyEvent(QEvent.Type.KeyRelease, key.value, held))


def click_at(user, widget, pos):
    """Clicks at pos as a mouse does: the widget under the pointer gets the click, which
    may be a child of widget."""
    target = widget.childAt(pos) or widget
    user.click(target, target.mapFrom(widget, pos))


def x_point(editor):
    """Where the x sits: at the right end of the editor, halfway down."""
    size = editor.height() / 2
    return QPoint(int(editor.width() - size / 2 - 2), int(size))


def type_key(user, qtbot, table, name, key, modifier=Ctrl):
    """Enters the key in the command's cell. The editor closes and is deleted on the
    first key that isn't a modifier: don't touch it afterwards."""
    open_key_editor(user, qtbot, table, name)
    user.press(key, modifier)


def click_x(user, qtbot, table, name):
    """Clicks the x at the right of the cell's editor, which empties the cell."""
    editor = open_key_editor(user, qtbot, table, name)
    click_at(user, editor, x_point(editor))


def click_row(user, table, name):
    """Clicks the command's Description cell."""
    [row] = [r for r in range(table.rowCount()) if table.item(r, 0).text() == name]
    item = table.item(row, 0)
    table.scrollToItem(item)
    user.click(table.viewport(), table.visualItemRect(item).center())


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
    # desired shortcut." (preferences.txt:155); Preferences "Opens the Preferences
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
    qtbot.waitUntil(lambda: not editing(table))
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
    # with OK is there at the next start (preferences.txt:155). Ctrl+L is synthetic.
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


def test_key_another_command_holds_moves_to_the_command_typed_for(mainwin, user, qtbot):
    # Play is "Play (Ctrl+P)" (menus.txt:29); #387's and #1090's reports: Ctrl+P given
    # to Preferences stays on Play too. The key moves, and the page says so.
    window, table = shortcuts_page(user)
    type_key(user, qtbot, table, '&Preferences', Key.Key_P)
    assert cells(table, '&Play', '&Preferences') == {'&Play': '', '&Preferences': 'Ctrl+P'}
    assert 'Ctrl+P moved from Play to Preferences.' in notice(window)
    user.close_preferences(window)
    assert keys(user, '&Play') == []
    assert keys(user, '&Preferences') == ['Ctrl+P']


def test_clearing_then_taking_a_held_key_leaves_one_command_per_key(mainwin, user, qtbot):
    # Save is "Save (Ctrl+S)" (menus.txt:25). The docs don't say what happens when a key
    # is cleared and then taken; Open Folder's Ctrl+O is from data/shortcuts and the
    # sequence of steps is synthetic. A key is in one row only.
    window, table = shortcuts_page(user)
    click_x(user, qtbot, table, '&Open Folder')
    type_key(user, qtbot, table, '&Properties', Key.Key_O)
    type_key(user, qtbot, table, '&Open Folder', Key.Key_S)
    shown = cells(table, '&Open Folder', '&Properties', '&Save')
    assert shown == {'&Open Folder': 'Ctrl+S', '&Properties': 'Ctrl+O', '&Save': ''}
    typed = [text for text in shown.values() if text]
    assert len(typed) == len(set(typed))
    user.close_preferences(window, 'Cancel')


def test_second_key_is_kept(mainwin, user, qtbot, restart):
    # Paste is "Paste (Ctrl+V)" (menus.txt:86); its Shift+Ins is from data/shortcuts
    # (the docs don't mention it). Ctrl+L is synthetic. An OK for another command's key
    # leaves Paste's keys as they were.
    window, table = shortcuts_page(user)
    type_key(user, qtbot, table, '&Preferences', Key.Key_L)
    user.close_preferences(window)
    assert keys(user, '&Paste') == ['Ctrl+V', 'Shift+Ins']
    assert saved('&Paste') == 'Ctrl+V; Shift+Ins'
    window, table = shortcuts_page(user)
    assert cells(table, '&Paste') == {'&Paste': 'Ctrl+V; Shift+Ins'}
    user.close_preferences(window, 'Cancel')
    win, user2 = restarted(restart, qtbot, user)
    assert keys(user2, '&Paste') == ['Ctrl+V', 'Shift+Ins']


def test_typed_key_replaces_both_keys(mainwin, user, qtbot):
    # The docs don't say; this is what puddletag does: the key typed in a cell is the
    # command's only key. Paste is "Paste (Ctrl+V)" (menus.txt:86); Ctrl+B is synthetic.
    window, table = shortcuts_page(user)
    type_key(user, qtbot, table, '&Paste', Key.Key_B)
    user.close_preferences(window)
    assert keys(user, '&Paste') == ['Ctrl+B']
    assert saved('&Paste') == 'Ctrl+B'


def test_x_clears_both_keys(mainwin, user, qtbot):
    # The docs don't say; this is what puddletag does: the x takes away all of the
    # command's keys. Paste is "Paste (Ctrl+V)" (menus.txt:86).
    window, table = shortcuts_page(user)
    click_x(user, qtbot, table, '&Paste')
    user.close_preferences(window)
    assert keys(user, '&Paste') == []
    assert saved('&Paste') == ''


def test_cancel_undoes_a_moved_key(mainwin, user, qtbot):
    # "Cancel or Esc closes the window without saving anything" (preferences.txt). Play
    # is "Play (Ctrl+P)" (menus.txt:29): the Ctrl+P moved off it is still there.
    window, table = shortcuts_page(user)
    type_key(user, qtbot, table, '&Preferences', Key.Key_P)
    assert cells(table, '&Play', '&Preferences') == {'&Play': '', '&Preferences': 'Ctrl+P'}
    user.close_preferences(window, 'Cancel')
    assert keys(user, '&Play') == ['Ctrl+P']
    assert keys(user, '&Preferences') == []
    assert not os.path.exists(USER_SHORTCUTS)


@pytest.mark.parametrize('modifier, text', [
    (Alt | Shift, 'Alt+Shift+1'),
    (Ctrl | Alt, 'Ctrl+Alt+1'),
    (Ctrl | Shift, 'Ctrl+Shift+1'),
    (Ctrl | Meta, 'Meta+Ctrl+1'),
    (Alt | Ctrl | Meta | Shift, 'Meta+Ctrl+Alt+Shift+1'),
])
def test_chord_names_its_modifiers_in_qt_order(mainwin, user, qtbot, modifier, text):
    # "Just double-click on the desired shortcut in the shortcut column and enter the
    # desired shortcut." (preferences.txt:155); the docs name Select Column's chord
    # "Select Column (Meta+Alt+C)" (menus.txt:121), the modifiers in this order. The
    # chords with key 1 are synthetic.
    window, table = shortcuts_page(user)
    type_key(user, qtbot, table, '&Preferences', Key.Key_1, modifier)
    assert cells(table, '&Preferences') == {'&Preferences': text}
    user.close_preferences(window)
    assert keys(user, '&Preferences') == [text]
    assert saved('&Preferences') == text


def test_ctrl_pressed_before_shift_gives_the_same_key(mainwin, user, qtbot):
    # The docs don't say; this is what puddletag does: Ctrl, then Shift, then 1, each
    # still held, enters the same key as pressing the chord at once. Synthetic key.
    window, table = shortcuts_page(user)
    open_key_editor(user, qtbot, table, '&Preferences')
    qtbot.keyPress(QApplication.focusWidget(), Key.Key_Control)
    qtbot.keyPress(QApplication.focusWidget(), Key.Key_Shift, Ctrl)
    qtbot.keyClick(QApplication.focusWidget(), Key.Key_1, Ctrl | Shift)
    qtbot.keyRelease(QApplication.focusWidget(), Key.Key_Shift, Ctrl | Shift)
    qtbot.keyRelease(QApplication.focusWidget(), Key.Key_Control, Ctrl)
    assert cells(table, '&Preferences') == {'&Preferences': 'Ctrl+Shift+1'}
    assert not editing(table)
    user.close_preferences(window)
    assert saved('&Preferences') == 'Ctrl+Shift+1'


@pytest.mark.parametrize('key', [Key.Key_Alt, Key.Key_Meta, Key.Key_Shift])
def test_modifier_alone_changes_nothing(mainwin, user, qtbot, key):
    # The docs don't say; this is what puddletag does: a modifier pressed alone closes
    # the key editor and leaves the key as it was. Save is "Save (Ctrl+S)"
    # (menus.txt:25).
    window, table = shortcuts_page(user)
    open_key_editor(user, qtbot, table, '&Save')
    user.press(key)
    qtbot.waitUntil(lambda: not editing(table))
    assert cells(table, '&Save') == {'&Save': 'Ctrl+S'}
    user.close_preferences(window)
    assert keys(user, '&Save') == ['Ctrl+S']
    assert not os.path.exists(USER_SHORTCUTS)


@pytest.mark.parametrize('key, modifier, text', [
    (Key.Key_5, Keypad, '5'),
    (Key.Key_A, NoModifier, 'A'),
    (Key.Key_F9, NoModifier, 'F9'),
    (Key.Key_Space, NoModifier, 'Space'),
])
def test_key_without_a_modifier(mainwin, user, qtbot, key, modifier, text):
    # The docs don't say; this is what puddletag does: a key needs no modifier to be a
    # command's key. The keys are synthetic.
    window, table = shortcuts_page(user)
    type_key(user, qtbot, table, '&Preferences', key, modifier)
    assert cells(table, '&Preferences') == {'&Preferences': text}
    user.close_preferences(window)
    assert saved('&Preferences') == text
    assert keys(user, '&Preferences') == [text]


def test_x_where_there_is_no_key_changes_nothing(mainwin, user, qtbot):
    # The docs don't say; this is what puddletag does: a click where the x would be on a
    # command without a key changes nothing.
    window, table = shortcuts_page(user)
    editor = open_key_editor(user, qtbot, table, '&Preferences')
    click_at(user, editor, x_point(editor))
    click_row(user, table, '&Play')
    qtbot.waitUntil(lambda: not editing(table))
    assert cells(table, '&Preferences') == {'&Preferences': ''}
    user.close_preferences(window)
    assert not os.path.exists(USER_SHORTCUTS)


def test_click_inside_the_editor_keeps_it_open(mainwin, user, qtbot):
    # The docs don't say; this is what puddletag does: a click inside the key editor
    # leaves it open, and the next key is entered. Ctrl+L is synthetic.
    window, table = shortcuts_page(user)
    editor = open_key_editor(user, qtbot, table, '&Save')
    user.click(editor, QPoint(editor.width() // 3, editor.height() // 2))
    assert editing(table)
    user.press(Key.Key_L, Ctrl)
    assert cells(table, '&Save') == {'&Save': 'Ctrl+L'}
    user.close_preferences(window)
    assert saved('&Save') == 'Ctrl+L'


def test_clicking_another_row_keeps_the_key(mainwin, user, qtbot):
    # The docs don't say; this is what puddletag does: clicking another row while a key
    # editor is open closes it and keeps the key. Save is "Save (Ctrl+S)" (menus.txt:25).
    window, table = shortcuts_page(user)
    open_key_editor(user, qtbot, table, '&Save')
    click_row(user, table, '&Play')
    qtbot.waitUntil(lambda: not editing(table))
    assert cells(table, '&Save') == {'&Save': 'Ctrl+S'}
    user.close_preferences(window)
    assert not os.path.exists(USER_SHORTCUTS)


def test_open_editor_shows_both_keys(mainwin, user, qtbot):
    # Paste is "Paste (Ctrl+V)" (menus.txt:86); its Shift+Ins is from data/shortcuts
    # (the docs don't mention it). The docs don't say what the editor shows: both keys.
    window, table = shortcuts_page(user)
    editor = open_key_editor(user, qtbot, table, '&Paste')
    assert shown(editor) == 'Ctrl+V; Shift+Ins'
    click_row(user, table, '&Play')
    qtbot.waitUntil(lambda: not editing(table))
    assert cells(table, '&Paste') == {'&Paste': 'Ctrl+V; Shift+Ins'}
    user.close_preferences(window, 'Cancel')


def test_x_shows_only_when_there_is_a_key(mainwin, user, qtbot):
    # The docs don't say; this is what puddletag does: the x is drawn in the editor of a
    # command with a key and not in an empty one. Save is "Save (Ctrl+S)" (menus.txt:25).
    def colours(editor):
        size = editor.height() // 2
        square = QRect(editor.width() - size - 4, size // 2, size, size)
        image = editor.grab().toImage()
        return {image.pixel(x, y) for x in range(square.left(), square.right() + 1)
                for y in range(square.top(), square.bottom() + 1)}

    window, table = shortcuts_page(user)
    editor = open_key_editor(user, qtbot, table, '&Save')
    qtbot.waitUntil(lambda: len(colours(editor)) > 1)
    click_row(user, table, '&Play')
    qtbot.waitUntil(lambda: not editing(table))
    editor = open_key_editor(user, qtbot, table, '&Preferences')
    qtbot.wait(300)
    assert len(colours(editor)) == 1
    click_row(user, table, '&Play')
    qtbot.waitUntil(lambda: not editing(table))
    user.close_preferences(window, 'Cancel')


@pytest.mark.parametrize('key, modifier, text', [
    (Key.Key_Backspace, NoModifier, 'Backspace'),
    (Key.Key_Enter, Keypad, 'Enter'),
    (Key.Key_Escape, NoModifier, 'Esc'),
    (Key.Key_Return, NoModifier, 'Return'),
    (Key.Key_Backtab, Shift, 'Shift+Backtab'),
    (Key.Key_Tab, NoModifier, 'Tab'),
])
def test_editing_keys_are_keys_too(mainwin, user, qtbot, key, modifier, text):
    # The docs don't say; this is what puddletag does: Esc, Tab, Return and the other
    # editing keys are entered as the command's key, not used to leave or move in the
    # table. The keys are synthetic.
    window, table = shortcuts_page(user)
    type_key(user, qtbot, table, '&Save', key, modifier)
    assert cells(table, '&Save') == {'&Save': text}
    assert not editing(table)
    assert window.isVisible()
    user.close_preferences(window)
    assert saved('&Save') == text


def test_f8_runs_its_own_command(mainwin, user, qtbot):
    # "Pressing F8 switches focus between it and the file-view." (tut3.txt:36, the
    # Pattern Combo). The docs don't say what the key editor does with it; this is what
    # puddletag does: F8 runs its command, closes the editor and enters no key.
    window, table = shortcuts_page(user)
    open_key_editor(user, qtbot, table, '&Preferences')
    user.press(Key.Key_F8)
    qtbot.waitUntil(lambda: not editing(table))
    assert cells(table, '&Preferences') == {'&Preferences': ''}
    user.close_preferences(window, 'Cancel')


def test_holding_a_modifier_while_clicking_another_row_keeps_the_key(mainwin, user, qtbot):
    # The docs don't say; this is what puddletag should do: a key editor closed by a
    # click on another row while Ctrl is held keeps the key. Save is "Save (Ctrl+S)"
    # (menus.txt:25).
    window, table = shortcuts_page(user)
    open_key_editor(user, qtbot, table, '&Save')
    hold(Key.Key_Control)
    click_row(user, table, '&Play')
    let_go(Key.Key_Control, Ctrl)
    qtbot.waitUntil(lambda: not editing(table))
    assert cells(table, '&Save') == {'&Save': 'Ctrl+S'}
    user.close_preferences(window)
    assert keys(user, '&Save') == ['Ctrl+S']


@pytest.mark.parametrize('first, second, texts', [
    (Key.Key_Control, Key.Key_Shift, ['Ctrl', 'Ctrl+Shift', 'Ctrl', 'Ctrl']),
    (Key.Key_Shift, Key.Key_Control, ['Shift', 'Shift+Ctrl', 'Shift', 'Shift']),
])
def test_held_modifiers_show_in_the_order_pressed(mainwin, user, qtbot, first, second, texts):
    # The docs don't say; this is what puddletag does: the key editor shows the
    # modifiers held, in the order they were pressed, and keeps showing the one still
    # held after the other is let go. A modifier held alone enters no key. Save is
    # "Save (Ctrl+S)" (menus.txt:25).
    modifier = {Key.Key_Control: Ctrl, Key.Key_Shift: Shift}
    mod1, mod2 = modifier[first], modifier[second]
    window, table = shortcuts_page(user)
    editor = open_key_editor(user, qtbot, table, '&Save')
    seen = []
    hold(first)
    seen.append(shown(editor))
    hold(second, mod1)
    seen.append(shown(editor))
    let_go(second, mod1 | mod2)
    seen.append(shown(editor))
    qtbot.wait(1200)
    seen.append(shown(editor))
    assert seen == texts
    let_go(first, mod1)
    qtbot.waitUntil(lambda: not editing(table))
    assert cells(table, '&Save') == {'&Save': 'Ctrl+S'}
    user.close_preferences(window, 'Cancel')


def test_modifier_still_held_stays_shown(mainwin, user, qtbot):
    # The docs don't say; this is what puddletag does: Ctrl and Shift held, then Ctrl
    # let go first, the editor goes on showing Shift, and letting Shift go closes it with
    # the key unchanged. Save is "Save (Ctrl+S)" (menus.txt:25).
    window, table = shortcuts_page(user)
    editor = open_key_editor(user, qtbot, table, '&Save')
    hold(Key.Key_Control)
    hold(Key.Key_Shift, Ctrl)
    let_go(Key.Key_Control, Ctrl | Shift)
    assert shown(editor) == 'Shift'
    qtbot.wait(1200)
    assert shown(editor) == 'Shift'
    let_go(Key.Key_Shift, Shift)
    qtbot.waitUntil(lambda: not editing(table))
    assert cells(table, '&Save') == {'&Save': 'Ctrl+S'}
    user.close_preferences(window, 'Cancel')
