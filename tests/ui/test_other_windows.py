"""Opening Preferences, the Actions window and the Music Library from the
main window as a user does (menus.txt, tut2.txt, preferences.txt): each
window shows and is the right one, and Cancel closes it without changing
the files, the table or the saved settings. What's inside each window is
tested elsewhere. Synthetic files and keys.
"""
import os

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QCheckBox, QDockWidget, QPushButton, QStyle,
                             QStyleOptionButton, QStyleOptionViewItem)

from puddlestuff import audioinfo
from puddlestuff.actiondlg import ActionWindow
from puddlestuff.constants import CONFIGDIR
from puddlestuff.musiclib import LibChooseDialog
from puddlestuff.puddleobjects import PuddleConfig
from puddlestuff.puddlesettings import SettingsDialog

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier

FIELDS = ['album', 'artist', 'title']


def tags(i):
    return {field: [f'{field} {i}'] for field in FIELDS}


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    music = tmp_path / 'music'
    paths = [make_audio(f'0{i}.mp3', music, **tags(i)) for i in (1, 2)]
    mainwin.openDir(str(music), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == 2)
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]
    user.activate()
    table.setFocus()
    return table, paths


def in_files(paths):
    return [audioinfo.usertags(audioinfo.Tag(str(p))) for p in paths]


def in_table(table):
    return [audioinfo.usertags(audio) for audio in table.model().taginfo]


def docks(win):
    return sorted(dock.objectName() for dock in win.findChildren(QDockWidget))


def preferences_windows(mainwin):
    """The Preferences windows showing. Each Edit > Preferences builds a new
    one, and a closed one stays, hidden, as the main window's child."""
    return [w for w in mainwin.findChildren(SettingsDialog) if w.isVisible()]


def open_preferences(mainwin, qtbot, user):
    """Edit > Preferences; returns the window."""
    user.click_menu('&Preferences')
    qtbot.waitUntil(lambda: len(preferences_windows(mainwin)) == 1)
    [window] = preferences_windows(mainwin)
    return window


def cancel_preferences(mainwin, qtbot, user, window):
    user.activate(window)
    user.click(window.okbuttons.cancelButton)
    qtbot.waitUntil(lambda: not preferences_windows(mainwin))
    user.activate()


def modal(qtbot, kind):
    """The modal window of this kind the last click opened."""
    qtbot.waitUntil(lambda: isinstance(QApplication.activeModalWidget(), kind))
    return QApplication.activeModalWidget()


def button(window, text):
    """The window's own button with this text."""
    [found] = [b for b in window.findChildren(QPushButton) if b.text() == text and b.window() is window]
    return found


def check_box(window, text):
    [box] = [c for c in window.findChildren(QCheckBox) if c.text() == text]
    return box


def click_check_box(user, box):
    """Clicks the box's indicator: the box stretches across the page, and
    a click at its center misses the label."""
    option = QStyleOptionButton()
    box.initStyleOption(option)
    user.click(box, box.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, box).center())


def check(user, listbox, name):
    """Ticks the list item's check box."""
    [item] = listbox.findItems(name, Qt.MatchFlag.MatchExactly)
    option = QStyleOptionViewItem()
    listbox.initViewItemOption(option)
    option.rect = listbox.visualItemRect(item)
    option.features |= QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
    box = listbox.style().subElementRect(QStyle.SubElement.SE_ItemViewItemCheckIndicator, option, listbox)
    user.click(listbox.viewport(), box.center())
    assert item.checkState() == Qt.CheckState.Checked


# Preferences

@pytest.fixture
def preferences_key(clean_profile):
    """A key for Preferences, set in Preferences > Shortcuts in an earlier
    session."""
    PuddleConfig(os.path.join(CONFIGDIR, 'user_shortcuts')).set('shortcuts', '&Preferences', 'Ctrl+L')


def test_preferences_opens_from_the_edit_menu(mainwin, qtbot, user):
    # menus.txt (Edit): "Preferences ... Opens the Preferences dialog."
    # preferences.txt describes the General page first.
    assert user.action('&Preferences').isEnabled()
    window = open_preferences(mainwin, qtbot, user)
    shown = [title for title, widget, control in window._widgets.values()
             if widget is window.stack.currentWidget()]
    assert {'modal': QApplication.activeModalWidget() is not None,
            'page': shown,
            'parent': window.parent() is mainwin,
            'title': window.windowTitle(),
            'window': window.isWindow()} == {'modal': False, 'page': ['General'], 'parent': True,
                                             'title': 'puddletag settings', 'window': True}
    cancel_preferences(mainwin, qtbot, user, window)
    assert not window.isVisible()


def test_key_set_for_preferences_opens_it(preferences_key, mainwin, qtbot, user):
    # preferences.txt (Shortcuts): "With this panel you can edit the keyboard
    # shortcuts of any menu item in puddletag." Ctrl+L is synthetic: no
    # command uses it.
    user.activate()
    mainwin._table.setFocus()
    user.press(Key.Key_L, Ctrl)
    qtbot.waitUntil(lambda: len(preferences_windows(mainwin)) == 1)
    [window] = preferences_windows(mainwin)
    assert window.windowTitle() == 'puddletag settings'
    cancel_preferences(mainwin, qtbot, user, window)


def test_preferences_cancel_saves_nothing(mainwin, qtbot, user):
    # preferences.txt (General): "Show gridlines: Shows/Hides the gridlines
    # in the file view depending on whether it checked/unchecked."
    settings = os.path.join(CONFIGDIR, 'gensettings')
    assert mainwin._table.showGrid()
    assert not os.path.exists(settings)
    window = open_preferences(mainwin, qtbot, user)
    user.activate(window)
    box = check_box(window, 'Show &gridlines')
    assert box.isChecked()
    click_check_box(user, box)
    assert not box.isChecked()
    cancel_preferences(mainwin, qtbot, user, window)
    assert mainwin._table.showGrid()
    assert not os.path.exists(settings)
    window = open_preferences(mainwin, qtbot, user)
    assert check_box(window, 'Show &gridlines').isChecked()
    cancel_preferences(mainwin, qtbot, user, window)


# The Actions window

def test_actions_window_cancel_runs_nothing(loaded, mainwin, qtbot, user):
    # menus.txt (Actions): "Opens the actions dialog, with which you can edit
    # actions." tut2.txt: "It opens up the Actions window" and "What they do
    # is run previously defined functions on the selected files."
    table, paths = loaded
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(1, 'title'), Shift)
    user.click_menu('&Actions')
    window = modal(qtbot, ActionWindow)
    assert {'parent': window.parent() is mainwin, 'title': window.windowTitle()} == \
        {'parent': True, 'title': 'Actions'}
    check(user, window.listbox, 'Case Conversion')
    user.click(window.okcancel.cancelButton)
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is None)
    user.activate()
    qtbot.wait(200)  # nothing should be written: give a wrong write its time
    assert in_files(paths) == [tags(1), tags(2)]
    assert in_table(table) == [tags(1), tags(2)]
    assert PuddleConfig().get('actions', 'checked', None) is None
    user.click_menu('&Actions')
    window = modal(qtbot, ActionWindow)
    [item] = window.listbox.findItems('Case Conversion', Qt.MatchFlag.MatchExactly)
    assert item.checkState() == Qt.CheckState.Unchecked
    user.click(window.okcancel.cancelButton)
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is None)


# The Music Library

def open_music_library(qtbot, user):
    """Tools > Import Music Library...; returns the window."""
    user.click_menu('&Import Music Library...')
    return modal(qtbot, LibChooseDialog)


def cancel_music_library(qtbot, user, window):
    user.click(button(window, 'Cancel'))
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is None)
    assert not window.isVisible()
    user.activate()


def test_import_music_library_opens_its_window(mainwin, qtbot, user):
    # menus.txt (Tools): "Import Music Library... Open's a dialog to allow you to
    # import a supported Music Library into puddletag to edit its tags."
    assert user.action('&Import Music Library...').isEnabled()
    before = docks(mainwin)
    window = open_music_library(qtbot, user)
    assert {'parent': window.parent() is mainwin, 'title': window.windowTitle()} == \
        {'parent': True, 'title': 'Import Music Library'}
    cancel_music_library(qtbot, user, window)
    assert docks(mainwin) == before


@pytest.mark.xfail(strict=True, reason="The window opens with no library picked in its list while the "
                                       "first one's page shows, so OK raises AttributeError")
def test_music_library_window_picks_its_first_library(mainwin, qtbot, user):
    # Synthetic: menus.txt (Tools) only says the window imports a supported
    # Music Library, so a user expects the library whose page shows to be the
    # one picked.
    window = open_music_library(qtbot, user)
    assert window.listbox.currentRow() == 0
    assert window.listbox.currentItem().isSelected()
    cancel_music_library(qtbot, user, window)
