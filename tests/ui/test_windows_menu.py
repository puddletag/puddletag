"""The Windows menu and the main window's layout, used as menus.txt
describes them: each tool window shown and hidden from the Windows menu,
the layout kept from one session to the next, the Logs window, and Lock
Layout's key. Synthetic keys and log lines.
"""
import os

import pytest
from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QDockWidget, QMenu, QPushButton, QWidget

from puddlestuff.constants import CONFIGDIR
from puddlestuff.puddleobjects import PuddleConfig
from puddlestuff.tagsources import write_log

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier


def docks(win):
    """The window's tool windows by name."""
    return {dock.objectName(): dock for dock in win.findChildren(QDockWidget)}


def shown(win):
    return sorted(name for name, dock in docks(win).items() if dock.isVisible())


def toggle(user, name):
    """Windows > name, clicked with the main window active."""
    user.activate()
    user.click_menu(name)


def double_click_title(user, dock):
    """Double-clicks the tool window's title bar, as a user does to float it
    or dock it again."""
    user.double_click(dock, QPoint(dock.width() // 2, 5))


# The Filter's F3 and menu toggles are tested in
# test_filter_panel.py::test_panel_shown_and_hidden, and the Tag Sources
# window's in
# test_tag_sources.py::test_windows_menu_shows_and_hides_the_window.

DOCK_DOCS = {
    'Actions': 'menus.txt: "Actions: Shows the Actions dialog as a tool window."',
    'Artwork': 'menus.txt: "Artwork: Shows the Artwork window with which you can edit album art."',
    'Filesystem': 'menus.txt: "Filesystem: Displays the filesystem window which lists directories."',
    'Functions': 'menus.txt: "Functions: Shows the Functions dialog as a tool window."',
    'Logs': 'menus.txt: "Logs: Shows/Hides the Logs dialog."',
    'Mass Tagging': 'menus.txt: "Mass Tagging: See the Masstagging Tutorial for more info."',
    'Stored Tags': 'menus.txt: "Stored Tags: The Stored Tags dialog displays the Tags of the '
                   'currently selected files as stored on disk."',
    'Tag Panel': 'menus.txt: "Tag Panel: Select some files, fill in some text and save the '
                 'changes (File->Save)."',
}


def windows_menu(mainwin):
    [menu] = [m for m in mainwin.menuBar().findChildren(QMenu) if m.title() == '&Windows']
    return menu


def test_windows_menu_lists_the_tool_windows(mainwin):
    # menus.txt's Windows headings are Filter (F3), Tag Panel, Artwork,
    # Filesystem, Tag Sources, Stored Tags, Logs, Mass Tagging, Functions
    # and Actions. The test checks the menu's own names and order.
    menu = windows_menu(mainwin)
    entries = [a for a in menu.actions() if not a.isSeparator()]
    assert [(a.text(), a.shortcut().toString()) for a in entries] == [
        ('Filter', 'F3'), ('Tag Panel', ''), ('Artwork', ''), ('Filesystem', ''),
        ('Tag Sources', ''), ('Stored Tags', ''), ('Logs', ''), ('Mass Tagging', ''),
        ('Functions', ''), ('Actions', '')]
    assert all(a.isCheckable() for a in entries)


def test_fresh_start_shows_the_filesystem_filter_and_tag_panel(mainwin, user):
    # tut3.txt: "Artwork isn't shown by default". The docs don't say which
    # others are; this is what puddletag does.
    assert shown(mainwin) == ['Filesystem', 'Filter', 'Tag Panel']
    for name, dock in docks(mainwin).items():
        assert user.action(name).isChecked() == dock.isVisible(), name


@pytest.mark.parametrize('name', sorted(DOCK_DOCS))
def test_windows_menu_shows_and_hides_the_dock(mainwin, user, qtbot, name):
    # Each window's menus.txt line is in DOCK_DOCS.
    dock = docks(mainwin)[name]
    action = user.action(name)
    before = dock.isVisible()
    toggle(user, name)
    qtbot.waitUntil(lambda: dock.isVisible() != before)
    assert action.isChecked() == (not before)
    toggle(user, name)
    qtbot.waitUntil(lambda: dock.isVisible() == before)
    assert action.isChecked() == before


def test_showing_a_dock_keeps_the_others(mainwin, user, qtbot):
    # The docs don't say; this is what puddletag does: showing the Logs
    # leaves the other windows shown, and the Logs on the right.
    toggle(user, 'Logs')
    logs = docks(mainwin)['Logs']
    qtbot.waitUntil(logs.isVisible)
    assert shown(mainwin) == ['Filesystem', 'Filter', 'Logs', 'Tag Panel']
    assert mainwin.dockWidgetArea(logs) == Qt.DockWidgetArea.RightDockWidgetArea


# The layout after a restart


def double_click_window_title(dock):
    """A floating tool window's title bar is the window system's, which hands
    Qt the double-click as a non-client event."""
    pos = QPoint(dock.width() // 2, -5)
    QApplication.sendEvent(dock, QMouseEvent(QEvent.Type.NonClientAreaMouseButtonDblClick, QPointF(pos),
                                             QPointF(dock.mapToGlobal(pos)), Qt.MouseButton.LeftButton,
                                             Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))


def test_hidden_and_shown_docks_stay_so_after_a_restart(mainwin, user, qtbot, restart):
    # news.txt: "Not everything moves around when resising puddletag anymore
    # and the layout is saved from the previous session."
    toggle(user, 'Filesystem')
    qtbot.waitUntil(lambda: not docks(mainwin)['Filesystem'].isVisible())
    toggle(user, 'Logs')
    qtbot.waitUntil(docks(mainwin)['Logs'].isVisible)

    win = restart()
    user2 = type(user)(qtbot, win)
    assert shown(win) == ['Filter', 'Logs', 'Tag Panel']
    assert not user2.action('Filesystem').isChecked()
    assert user2.action('Logs').isChecked()


def test_floated_dock_stays_floating_after_a_restart(mainwin, user, qtbot, restart):
    # news.txt: "The main window's layout in addition to its size is now
    # saved."
    user.activate()
    fs = docks(mainwin)['Filesystem']
    double_click_title(user, fs)
    qtbot.waitUntil(fs.isFloating)

    win = restart()
    fs2 = docks(win)['Filesystem']
    assert fs2.isFloating()
    assert fs2.isVisible()
    assert [name for name, dock in docks(win).items() if dock.isFloating()] == ['Filesystem']


def test_double_click_docks_a_floating_window_again(mainwin, user, qtbot):
    # The docs don't say; this is what puddletag does (#867: "there is not
    # button to force it to [re-dock]"). news.txt: "The main window's layout
    # in addition to its size is now saved."
    user.activate()
    fs = docks(mainwin)['Filesystem']
    double_click_title(user, fs)
    qtbot.waitUntil(fs.isFloating)

    user.activate(fs)
    double_click_window_title(fs)
    qtbot.waitUntil(lambda: not fs.isFloating())
    assert mainwin.dockWidgetArea(fs) == Qt.DockWidgetArea.LeftDockWidgetArea


def test_hidden_dock_shown_after_a_restart_returns_to_its_area(mainwin, user, qtbot, restart):
    # The docs don't say; this is what puddletag does (#768: "if you
    # close/hide the Logs window ... and then show it again, it will appear
    # where it was before"). news.txt: "Not everything moves around when
    # resising puddletag anymore and the layout is saved from the previous
    # session."
    toggle(user, 'Logs')
    qtbot.waitUntil(docks(mainwin)['Logs'].isVisible)
    toggle(user, 'Logs')
    qtbot.waitUntil(lambda: not docks(mainwin)['Logs'].isVisible())

    win = restart()
    user2 = type(user)(qtbot, win)
    user2.activate()
    user2.click_menu('Logs')
    logs = docks(win)['Logs']
    qtbot.waitUntil(logs.isVisible)
    assert win.dockWidgetArea(logs) == Qt.DockWidgetArea.RightDockWidgetArea


# The Logs window


def show_logs(mainwin, user, qtbot):
    """Windows > Logs; returns the dock and its text box."""
    toggle(user, 'Logs')
    dock = docks(mainwin)['Logs']
    qtbot.waitUntil(dock.isVisible)
    return dock, dock.widget()._text


def log_button(dock, text):
    [button] = [b for b in dock.widget().findChildren(QPushButton) if b.text() == text]
    return button


def test_log_line_shows_in_the_logs_window(mainwin, user, qtbot):
    # menus.txt: "Logs: Shows/Hides the Logs dialog. Currently shows debugging
    # information for Tag Sources." The lines are synthetic, sent through the
    # call tag sources make.
    dock, logs = show_logs(mainwin, user, qtbot)
    write_log('Synthetic line one')
    write_log('Synthetic line two')
    qtbot.waitUntil(lambda: logs.toPlainText() == 'Synthetic line one\nSynthetic line two')


def test_clear_empties_the_logs(mainwin, user, qtbot):
    # The docs don't say; this is what puddletag does.
    dock, logs = show_logs(mainwin, user, qtbot)
    write_log('Synthetic line one')
    qtbot.waitUntil(lambda: logs.toPlainText() == 'Synthetic line one')
    user.click(log_button(dock, '&Clear'))
    assert logs.toPlainText() == ''


def test_copy_puts_the_logs_on_the_clipboard(mainwin, user, qtbot):
    # The docs don't say; this is what puddletag does.
    dock, logs = show_logs(mainwin, user, qtbot)
    write_log('Synthetic line one')
    write_log('Synthetic line two')
    qtbot.waitUntil(lambda: logs.toPlainText() == 'Synthetic line one\nSynthetic line two')
    user.click(log_button(dock, '&Copy'))
    assert QApplication.clipboard().text() == 'Synthetic line one\nSynthetic line two'
    assert logs.toPlainText() == 'Synthetic line one\nSynthetic line two'


# Lock Layout

LOCK_KEY_DOES_NOTHING = "Lock Layout's key, set in Preferences > Shortcuts, does nothing: the command is on no widget"


@pytest.fixture
def lock_key(clean_profile):
    """A key for Lock Layout, set in Preferences > Shortcuts in an earlier
    session: preferences.txt: "With this panel you can edit the keyboard
    shortcuts of any menu item in puddletag." Ctrl+L is synthetic; no other
    command uses it."""
    PuddleConfig(os.path.join(CONFIGDIR, 'user_shortcuts')).set('shortcuts', '&Lock Layout', 'Ctrl+L')


def lock_with_key(mainwin, user, qtbot):
    user.activate()
    mainwin._table.setFocus()
    user.press(Key.Key_L, Ctrl)
    qtbot.waitUntil(lambda: all(type(d.titleBarWidget()) is QWidget for d in docks(mainwin).values()))


@pytest.mark.xfail(strict=True, reason=LOCK_KEY_DOES_NOTHING)
def test_lock_layout_key_locks_the_docks(lock_key, mainwin, user, qtbot):
    # The docs don't say what locking does; this is what puddletag does.
    lock_with_key(mainwin, user, qtbot)
    # A hidden dock's blank title bar has not been laid out yet.
    assert all(d.titleBarWidget().height() == 0 for d in docks(mainwin).values() if d.isVisible())


@pytest.mark.xfail(strict=True, reason=LOCK_KEY_DOES_NOTHING)
def test_locked_dock_does_not_float(lock_key, mainwin, user, qtbot):
    # The docs don't say; this is what puddletag does.
    lock_with_key(mainwin, user, qtbot)
    fs = docks(mainwin)['Filesystem']
    user.double_click(fs, QPoint(fs.width() // 2, 2))
    qtbot.wait(100)
    assert not fs.isFloating()
    toggle(user, 'Filesystem')
    qtbot.waitUntil(lambda: not fs.isVisible())


@pytest.mark.xfail(strict=True, reason=LOCK_KEY_DOES_NOTHING)
def test_layout_is_unlocked_after_a_restart(lock_key, mainwin, user, qtbot, restart):
    # The docs don't say; this is what puddletag does: the lock isn't saved.
    lock_with_key(mainwin, user, qtbot)
    win = restart()
    assert all(d.titleBarWidget() is None for d in docks(win).values())
