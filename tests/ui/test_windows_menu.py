"""The Windows menu and the main window's layout, used as menus.txt
describes them: each tool window shown and hidden from the Windows menu,
the layout kept from one session to the next, the Logs window, Lock
Layout's key, and the window fitting the screen. Synthetic files, keys and
log lines.
"""
import os

import pytest
from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QMouseEvent, QWheelEvent
from PyQt6.QtWidgets import QApplication, QDockWidget, QMenu, QPushButton, QWidget

from puddlestuff import audioinfo
from puddlestuff.constants import CONFIGDIR
from puddlestuff.mainwin.tagpanel import FrameCombo, savesettings
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


def in_file(path):
    return audioinfo.usertags(audioinfo.Tag(str(path)))


def wheel(widget, notches):
    """Turns the mouse wheel over the widget: positive notches roll it up,
    away from the user. The desktop sends the wheel to the widget under the
    pointer, whether it has the focus or not."""
    pos = QPointF(widget.rect().center())
    event = QWheelEvent(pos, QPointF(widget.mapToGlobal(pos)), QPoint(0, 0), QPoint(0, 120 * notches),
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(widget, event)


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


def test_lock_layout_key_locks_the_docks(lock_key, mainwin, user, qtbot):
    # The docs don't say what locking does; this is what puddletag does.
    lock_with_key(mainwin, user, qtbot)
    # A hidden dock's blank title bar has not been laid out yet.
    assert all(d.titleBarWidget().height() == 0 for d in docks(mainwin).values() if d.isVisible())


def test_locked_dock_does_not_float(lock_key, mainwin, user, qtbot):
    # The docs don't say; this is what puddletag does.
    lock_with_key(mainwin, user, qtbot)
    fs = docks(mainwin)['Filesystem']
    user.double_click(fs, QPoint(fs.width() // 2, 2))
    qtbot.wait(100)
    assert not fs.isFloating()
    toggle(user, 'Filesystem')
    qtbot.waitUntil(lambda: not fs.isVisible())


def test_layout_is_unlocked_after_a_restart(lock_key, mainwin, user, qtbot, restart):
    # The docs don't say; this is what puddletag does: the lock isn't saved.
    lock_with_key(mainwin, user, qtbot)
    win = restart()
    assert all(d.titleBarWidget() is None for d in docks(win).values())


# The window fitting the screen


def test_three_right_docks_fit_the_screen(mainwin, user, qtbot):
    # The docs don't say; this is what puddletag does. #768: "the window ...
    # resizes to be too big ... and also loses the maximize button", after
    # showing "Tag Sources", "Functions" and "Actions".
    for name in ['Tag Sources', 'Functions', 'Actions']:
        toggle(user, name)
        qtbot.waitUntil(docks(mainwin)[name].isVisible)
    assert mainwin.minimumSizeHint().height() <= QApplication.primaryScreen().availableGeometry().height()
    # Qt reports a tab only between shown windows
    toggle(user, 'Mass Tagging')
    qtbot.waitUntil(docks(mainwin)['Mass Tagging'].isVisible)
    assert mainwin.tabifiedDockWidgets(docks(mainwin)['Functions']) == [docks(mainwin)['Actions']]
    assert mainwin.tabifiedDockWidgets(docks(mainwin)['Tag Sources']) == [docks(mainwin)['Mass Tagging']]


def test_layout_saved_in_an_earlier_session_keeps_its_windows_out_of_the_default_tabs(mainwin, user, qtbot, restart):
    # news.txt: "the layout is saved from the previous session." Actions,
    # moved to the left side, stays out of the tabs the first start makes.
    left = Qt.DockWidgetArea.LeftDockWidgetArea
    for name in ['Functions', 'Actions']:
        toggle(user, name)
        qtbot.waitUntil(docks(mainwin)[name].isVisible)
    actions = docks(mainwin)['Actions']
    # Stands in for the user dragging the window there, which the offscreen
    # platform doesn't carry out.
    mainwin.addDockWidget(left, actions)
    qtbot.waitUntil(lambda: mainwin.dockWidgetArea(actions) == left)

    win = restart()
    actions = docks(win)['Actions']
    assert win.dockWidgetArea(actions) == left
    assert actions.isVisible()
    assert actions not in win.tabifiedDockWidgets(docks(win)['Functions'])


@pytest.fixture
def tall_panel(clean_profile):
    """40 one-field rows in the Tag Panel, as Edit > Preferences > Tag Panel
    saves them in an earlier session (synthetic fields field1..field39 after
    Title)."""
    rows = {row: [(f'Field {row}', f'field{row}')] for row in range(1, 40)}
    rows[0] = [('&Title', 'title')]
    savesettings(rows)


def test_long_tag_panel_fits_the_screen(tall_panel, mainwin):
    # menus.txt: "Tag Panel: ... Configure the fields in
    # Edit->Preferences->Tag Panel". #1092: "It is impossible for me to look
    # at the Filesystem because I cannot scroll".
    assert mainwin.minimumSizeHint().height() <= QApplication.primaryScreen().availableGeometry().height()


def test_long_tag_panel_scrolls_to_its_last_field(tall_panel, mainwin, qtbot):
    # #1092: "I cannot scroll". The panel's last field can be scrolled to.
    panel = mainwin.findChild(FrameCombo)
    scroll = panel.parentWidget().parentWidget()
    combo = panel.combos['field39']
    scroll.ensureWidgetVisible(combo)
    viewport = scroll.viewport()
    qtbot.waitUntil(lambda: viewport.rect().contains(combo.mapTo(viewport, combo.rect().center())))


def title_field(mainwin, make_audio, tmp_path, qtbot, user):
    """Three synthetic MP3s loaded and the first selected: returns their paths
    and the Tag Panel's Title field."""
    music = tmp_path / 'music'
    paths = [make_audio(f'0{n}.mp3', music, title=f'Title {n}') for n in range(1, 4)]
    mainwin.openDir(str(music), False)
    qtbot.waitUntil(lambda: mainwin._table.model().rowCount() == 3)
    user.activate()
    user.click_cell(user.cell(0, 'title'))
    combo = mainwin.findChild(FrameCombo).combos['title']
    qtbot.waitUntil(lambda: combo.isEnabled() and combo.currentText() == 'Title 1')
    return paths, combo


def test_wheel_over_a_tag_panel_field_keeps_its_value(mainwin, make_audio, tmp_path, qtbot, user):
    # tut1.txt: "To remove a field, change the text to <blank> and the
    # field'll be removed upon saving." tut3.txt: "Each field's list holds
    # <keep>, <blank> and the values the selected files have: pick one to
    # give it to all of them." #1094: the wheel should not change a field "so
    # that it cannot be executed unintentionally".
    paths, combo = title_field(mainwin, make_audio, tmp_path, qtbot, user)
    wheel(combo, 1)
    assert combo.currentText() == 'Title 1'
    user.activate()
    user.press(Key.Key_S, Ctrl)
    qtbot.waitUntil(lambda: in_file(paths[0]).get('title') == ['Title 1'])
    assert mainwin._table.model().taginfo[0]['title'] == ['Title 1']


def test_wheel_over_a_clicked_tag_panel_field_changes_its_value(mainwin, make_audio, tmp_path, qtbot, user):
    # tut3.txt: "pick one to give it to all of them." Once the user has
    # clicked a field, it takes the wheel.
    paths, combo = title_field(mainwin, make_audio, tmp_path, qtbot, user)
    user.click(combo.lineEdit())
    wheel(combo, 1)
    assert combo.currentText() == '<blank>'
