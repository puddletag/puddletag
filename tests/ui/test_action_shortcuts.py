"""Action shortcuts (tut3.txt): the Actions window's Assign Shortcut
button gives the checked actions a name and a key, as an item on the
Actions menu, and the key runs them on the selected files. Edit
Shortcuts, the same button's menu, changes or removes them. Synthetic
files and tags.
"""
import pytest
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QApplication, QMenu, QPushButton, QStyle, QStyleOptionViewItem,
                             QToolButton)

from puddlestuff import action_shortcuts, audioinfo
from puddlestuff.actiondlg import (ActionWindow, CreateAction, CreateFunction, ShortcutDialog,
                                   ShortcutName)

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
LEFT = Qt.MouseButton.LeftButton

FIELDS = ['album', 'artist', 'title']


def tags(i):
    return {field: [f'{field} {i}'] for field in FIELDS}


def mixed(i):
    # The Case Conversion action "changes the album, title and artist
    # fields to 'Mixed Case'" (tut2.txt:58), which "capitalises each word"
    # (function.txt:41).
    return {field: [f'{field} {i}'.title()] for field in FIELDS}


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    """Two files, the first one selected."""
    music = tmp_path / 'music'
    paths = [make_audio(f'0{i}.mp3', music, **{field: f'{field} {i}' for field in FIELDS})
             for i in (1, 2)]
    mainwin.openDir(str(music), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == 2)
    assert [audio.filepath for audio in table.model().taginfo] == [str(p) for p in paths]
    user.activate()
    user.click_cell(user.cell(0, 'title'))
    return table, paths


def in_files(paths):
    return [audioinfo.usertags(audioinfo.Tag(str(p))) for p in paths]


def in_table(table):
    return [audioinfo.usertags(audio) for audio in table.model().taginfo]


def written(qtbot, path, expected):
    qtbot.waitUntil(lambda: audioinfo.usertags(audioinfo.Tag(str(path))) == expected)


def check(user, window, name):
    """Ticks the action's check box."""
    listbox = window.listbox
    [item] = listbox.findItems(name, Qt.MatchFlag.MatchExactly)
    option = QStyleOptionViewItem()
    listbox.initViewItemOption(option)
    option.rect = listbox.visualItemRect(item)
    option.features |= QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
    box = listbox.style().subElementRect(QStyle.SubElement.SE_ItemViewItemCheckIndicator, option, listbox)
    user.click(listbox.viewport(), box.center())
    assert item.checkState() == Qt.CheckState.Checked


def click_row(user, listbox, row):
    user.click(listbox.viewport(), listbox.visualItemRect(listbox.item(row)).center())


def open_actions(user, qtbot):
    """Actions > Actions "opens the actions dialog" (menus.txt:202)."""
    user.click_menu('&Actions')
    qtbot.waitUntil(lambda: isinstance(QApplication.activeModalWidget(), ActionWindow))
    return QApplication.activeModalWidget()


def close(user, window):
    """Cancel closes the Actions window; the main window is active again,
    the File-View focused, so a key goes to the main window."""
    user.click(window.okcancel.cancelButton)
    user.activate()
    user.table.setFocus()


def button(window, text):
    """The window's own button with this text, not one of a window it
    opened."""
    [found] = [b for b in window.findChildren(QPushButton) if b.text() == text and b.window() is window]
    return found


def tool_button(window, tooltip):
    [found] = [b for b in window.findChildren(QToolButton)
               if b.toolTip() == tooltip and b.window() is window]
    return found


def answer(monkeypatch, user, cls, steps):
    """The name and key dialogs run with exec(), which the dialogs fixture
    stands in for on QDialog. Patched on the dialog's own class, exec()
    shows the real dialog and steps(dialog) types and clicks in it, as a
    user does, before it returns."""
    def exec_(dialog):
        dialog.show()
        user.activate(dialog)
        steps(dialog)
        return 0

    monkeypatch.setattr(cls, 'exec', exec_)


def naming(user, name=None):
    """Answers the name dialog: the name it offers, or the one typed."""
    def steps(dialog):
        if name is not None:
            user.press(Key.Key_A, Ctrl)
            user.type(name)
        user.click(dialog._ok)
    return steps


def pressing(user, key, modifier=Ctrl):
    """Answers the key dialog: presses the key, then OK."""
    def steps(dialog):
        user.press(key, modifier)
        user.click(button(dialog, 'OK'))
    return steps


def no_key(user):
    def steps(dialog):
        user.click(button(dialog, "&Don't assign keyboard shortcut."))
    return steps


def assign(user, monkeypatch, window, key_steps, name=None):
    """Clicks Assign Shortcut and answers its two dialogs."""
    answer(monkeypatch, user, ShortcutName, naming(user, name))
    answer(monkeypatch, user, ShortcutDialog, key_steps)
    user.click(window.shortcutButton)


def assigned(user, qtbot, monkeypatch):
    """Opens the Actions window, ticks Case Conversion, assigns it Ctrl+1
    and closes the window."""
    window = open_actions(user, qtbot)
    check(user, window, 'Case Conversion')
    assign(user, monkeypatch, window, pressing(user, Key.Key_1))
    close(user, window)


def actions_menu(win):
    [menu] = [m for m in win.menuBar().findChildren(QMenu) if m.title() == '&Actions']
    return menu


def shortcuts_on_menu(win):
    """The (name, key) of each item after the Actions menu's separator."""
    items = actions_menu(win).actions()
    last = max(i for i, item in enumerate(items) if item.isSeparator())
    return [(item.text(), item.shortcut().toString()) for item in items[last + 1:]]


def menu_item(win, name):
    """Edit Shortcuts makes new items with no parent, which User.action
    (a search of the window's children) can't find."""
    [item] = [a for a in actions_menu(win).actions() if a.text() == name]
    return item


def shown(cls):
    found = [w for w in QApplication.topLevelWidgets() if isinstance(w, cls) and w.isVisible()]
    return found[0] if found else None


def edit_shortcuts(user, qtbot, window):
    """Edit Shortcuts is the Assign Shortcut button's menu, "found by
    pressing down on this button" (its tooltip). The menu runs its own
    event loop, so the pick waits on a timer, as User.right_click does."""
    picked = []

    def pick(tries=200):
        menu = QApplication.activePopupWidget()
        if not (isinstance(menu, QMenu) and menu.isVisible()):
            if tries:
                QTimer.singleShot(10, lambda: pick(tries - 1))
            return
        [item] = [a for a in menu.actions() if a.text() == 'Edit Shortcuts']
        picked.append(item)
        user.click(menu, menu.actionGeometry(item).center())

    QTimer.singleShot(0, pick)
    qtbot.mousePress(window.shortcutButton, LEFT)
    qtbot.waitUntil(lambda: bool(picked))
    qtbot.mouseRelease(window.shortcutButton, LEFT)
    qtbot.waitUntil(lambda: shown(action_shortcuts.ShortcutEditor) is not None)
    editor = shown(action_shortcuts.ShortcutEditor)
    user.activate(editor)
    return editor


def edit_item(user, qtbot, editor, row):
    """Double-clicking a shortcut opens its Edit Shortcut window."""
    listbox = editor._listbox
    user.double_click(listbox.viewport(), listbox.visualItemRect(listbox.item(row)).center())
    qtbot.waitUntil(lambda: shown(action_shortcuts.Editor) is not None)
    dialog = shown(action_shortcuts.Editor)
    user.activate(dialog)
    return dialog


def nothing_ran(qtbot, user, paths):
    """A key that runs nothing: after a moment the files are as made, and
    Undo is greyed out, "when there's nothing left to undo" (menus.txt:62)."""
    qtbot.wait(500)
    assert in_files(paths) == [tags(1), tags(2)]
    assert not user.action('&Undo').isEnabled()


def test_assigned_key_runs_the_action(mainwin, loaded, user, qtbot, monkeypatch):
    # "I recommend you assign shortcuts to your favourite actions like
    # Ctrl+1, Ctrl+2 etc. Use the Assign Shortcut button on the Actions
    # Dialog." (tut3.txt:97-99). Actions "run previously defined functions
    # on the selected files" (tut2.txt:50); Case Conversion "changes the
    # album, title and artist fields to 'Mixed Case'" (tut2.txt:58).
    table, paths = loaded
    assigned(user, qtbot, monkeypatch)
    assert shortcuts_on_menu(mainwin) == [('Case Conversion', 'Ctrl+1')]
    user.press(Key.Key_1, Ctrl)
    written(qtbot, paths[0], mixed(1))
    assert in_files(paths) == [mixed(1), tags(2)]
    assert in_table(table) == [mixed(1), tags(2)]


def test_shortcut_menu_item_runs_the_action(mainwin, loaded, user, qtbot, monkeypatch):
    # As the key: the shortcut's menu item is the command's other way in
    # (tut2.txt:50, tut2.txt:58).
    table, paths = loaded
    assigned(user, qtbot, monkeypatch)
    assert shortcuts_on_menu(mainwin) == [('Case Conversion', 'Ctrl+1')]
    user.click_menu('Case Conversion')
    written(qtbot, paths[0], mixed(1))
    assert in_files(paths) == [mixed(1), tags(2)]
    assert in_table(table) == [mixed(1), tags(2)]


def test_key_in_preview_mode(mainwin, loaded, user, qtbot, monkeypatch):
    # "When enabled any changes you make will not get written. Instead any
    # values you change that differ from the original will be shown as
    # emboldened text in the File-View" (menus.txt:262).
    table, paths = loaded
    assigned(user, qtbot, monkeypatch)
    user.click_menu('Enabl&e Preview Mode')
    user.activate()
    user.table.setFocus()
    user.press(Key.Key_1, Ctrl)
    qtbot.waitUntil(lambda: in_table(table) == [mixed(1), tags(2)])
    assert in_files(paths) == [tags(1), tags(2)]
    assert table.model().data(user.cell(0, 'title'), Qt.ItemDataRole.FontRole).bold()


def test_undo_after_the_key(mainwin, loaded, user, qtbot, monkeypatch):
    # "Undo (Ctrl+Z) ... Undo's the last edit." (menus.txt:60-62).
    table, paths = loaded
    assigned(user, qtbot, monkeypatch)
    user.press(Key.Key_1, Ctrl)
    written(qtbot, paths[0], mixed(1))
    user.activate()
    user.press(Key.Key_Z, Ctrl)
    written(qtbot, paths[0], tags(1))
    assert in_files(paths) == [tags(1), tags(2)]
    assert in_table(table) == [tags(1), tags(2)]


def restarted(qtbot, user, restart):
    """Quits and starts puddletag again: the new window and its user."""
    win = restart()
    return win, type(user)(qtbot, win)


def reopened(qtbot, win, user2, paths):
    """Opens the folder in the new window."""
    win.openDir(str(paths[0].parent), False)
    qtbot.waitUntil(lambda: win._table.model().rowCount() == 2)
    user2.activate()


def test_shortcut_kept_after_a_restart(loaded, qtbot, user, monkeypatch, restart):
    # The docs don't say; this is what puddletag does: the shortcut and its
    # key come back at the next start.
    table, paths = loaded
    assigned(user, qtbot, monkeypatch)

    win, user2 = restarted(qtbot, user, restart)

    assert shortcuts_on_menu(win) == [('Case Conversion', 'Ctrl+1')]
    reopened(qtbot, win, user2, paths)
    user2.click_cell(user2.cell(0, 'title'))
    user2.press(Key.Key_1, Ctrl)
    written(qtbot, paths[0], mixed(1))
    assert in_files(paths) == [mixed(1), tags(2)]
    qtbot.waitUntil(lambda: in_table(win._table) == [mixed(1), tags(2)])


def test_restarted_shortcut_needs_a_selection(loaded, qtbot, user, monkeypatch, restart):
    # The docs don't say; tut2.txt:50: actions "run previously defined
    # functions on the selected files". After a restart the shortcut is
    # greyed out until files are selected.
    table, paths = loaded
    assigned(user, qtbot, monkeypatch)
    win, user2 = restarted(qtbot, user, restart)
    enabled = [user2.action('Case Conversion').isEnabled()]

    reopened(qtbot, win, user2, paths)
    user2.click_cell(user2.cell(0, 'title'))
    enabled.append(user2.action('Case Conversion').isEnabled())
    user2.click_cell(user2.cell(0, 'title'), Ctrl)
    assert win._table.selectedRows == []
    enabled.append(user2.action('Case Conversion').isEnabled())

    assert enabled == [False, True, False]


def test_shortcut_without_a_key(loaded, qtbot, user, monkeypatch, mainwin):
    # The docs don't say; this is what puddletag does: "Don't assign
    # keyboard shortcut" makes a menu item with no key, which runs the
    # action.
    table, paths = loaded
    window = open_actions(user, qtbot)
    check(user, window, 'Case Conversion')
    assign(user, monkeypatch, window, no_key(user))
    close(user, window)

    assert shortcuts_on_menu(mainwin) == [('Case Conversion', '')]
    user.click_menu('Case Conversion')
    written(qtbot, paths[0], mixed(1))
    assert in_files(paths) == [mixed(1), tags(2)]


def test_taken_key_is_refused(loaded, qtbot, user, monkeypatch, mainwin):
    # The docs don't say; this is what puddletag does: a key another
    # command has (Save's Ctrl+S) is shown but OK stays disabled.
    table, paths = loaded
    window = open_actions(user, qtbot)
    check(user, window, 'Case Conversion')
    refused = []

    def steps(dialog):
        ok = button(dialog, 'OK')
        user.press(Key.Key_S, Ctrl)  # Save's key
        refused.append((dialog._text.text(), ok.isEnabled()))
        user.press(Key.Key_1, Ctrl)
        user.click(ok)

    assign(user, monkeypatch, window, steps)
    close(user, window)

    assert refused == [('Ctrl+S', False)]
    assert shortcuts_on_menu(mainwin) == [('Case Conversion', 'Ctrl+1')]
    assert user.action('&Save').shortcut().toString() == 'Ctrl+S'


def test_taken_name_is_refused(loaded, qtbot, user, monkeypatch, mainwin):
    # The docs don't say; this is what puddletag does: the name another
    # action shortcut has leaves OK disabled, a new name enables it.
    table, paths = loaded
    window = open_actions(user, qtbot)
    check(user, window, 'Case Conversion')
    assign(user, monkeypatch, window, pressing(user, Key.Key_1))
    offered = []

    def steps(dialog):
        offered.append((dialog._text.text(), dialog._ok.isEnabled()))
        user.press(Key.Key_A, Ctrl)
        user.type('Title Case')
        offered.append((dialog._text.text(), dialog._ok.isEnabled()))
        user.click(dialog._ok)

    answer(monkeypatch, user, ShortcutName, steps)
    answer(monkeypatch, user, ShortcutDialog, pressing(user, Key.Key_2))
    user.click(window.shortcutButton)
    close(user, window)

    assert offered == [('Case Conversion', False), ('Title Case', True)]
    assert shortcuts_on_menu(mainwin) == [('Case Conversion', 'Ctrl+1'), ('Title Case', 'Ctrl+2')]


def test_edit_shortcuts_changes_the_key(loaded, mainwin, user, qtbot, monkeypatch):
    # The docs don't say; this is what puddletag does: Edit Shortcuts, "found
    # by pressing down on this button" (the button's tooltip), changes the
    # key of a shortcut, and only the new key runs it.
    table, paths = loaded
    window = open_actions(user, qtbot)
    check(user, window, 'Case Conversion')
    assign(user, monkeypatch, window, pressing(user, Key.Key_1))
    editor = edit_shortcuts(user, qtbot, window)
    assert [item.text() for item in editor._listbox.items()] == ['Case Conversion']
    dialog = edit_item(user, qtbot, editor, 0)
    assert dialog._shortcut.text() == 'Ctrl+1'
    user.click(dialog._shortcut)
    user.press(Key.Key_2, Ctrl)
    user.click(dialog._ok)
    user.activate(editor)
    user.click(button(editor, 'OK'))
    close(user, window)
    assert shortcuts_on_menu(mainwin) == [('Case Conversion', 'Ctrl+2')]
    user.press(Key.Key_1, Ctrl)
    nothing_ran(qtbot, user, paths)
    user.press(Key.Key_2, Ctrl)
    written(qtbot, paths[0], mixed(1))
    assert in_files(paths) == [mixed(1), tags(2)]


def test_edit_shortcuts_removes_a_shortcut(loaded, mainwin, user, qtbot, monkeypatch, restart):
    # The docs don't say; this is what puddletag does: removing a shortcut
    # in Edit Shortcuts takes its item off the Actions menu, its key stops
    # running it, and it stays gone at the next start.
    table, paths = loaded
    window = open_actions(user, qtbot)
    check(user, window, 'Case Conversion')
    assign(user, monkeypatch, window, pressing(user, Key.Key_1))
    editor = edit_shortcuts(user, qtbot, window)
    click_row(user, editor._listbox, 0)
    user.click(tool_button(editor, 'Remove'))
    assert editor._listbox.count() == 0
    user.click(button(editor, 'OK'))
    close(user, window)
    assert shortcuts_on_menu(mainwin) == []
    user.press(Key.Key_1, Ctrl)
    nothing_ran(qtbot, user, paths)
    win = restart()
    assert shortcuts_on_menu(win) == []


def pick_text(user, qtbot, combo, text):
    row = combo.findText(text, Qt.MatchFlag.MatchFixedString)
    assert row != -1, text
    user.click(combo)
    view = combo.view()
    qtbot.waitUntil(view.isVisible)
    # A second click inside the double-click interval is read as one.
    qtbot.wait(QApplication.doubleClickInterval() + 100)
    index = combo.model().index(row, 0)
    view.scrollTo(index)
    user.click(view.viewport(), view.visualRect(index).center())
    qtbot.waitUntil(lambda: not view.isVisible())
    assert combo.currentIndex() == row


def test_shortcut_runs_the_edited_action(mainwin, loaded, user, qtbot, monkeypatch):
    # The docs don't say; this is what puddletag does: after Case Conversion
    # is edited, as tut2.txt:52-58 describes, to UPPER CASE, the shortcut
    # runs the edited action.
    table, paths = loaded
    window = open_actions(user, qtbot)
    check(user, window, 'Case Conversion')
    assign(user, monkeypatch, window, pressing(user, Key.Key_1))
    user.activate(window)
    [item] = window.listbox.findItems('Case Conversion', Qt.MatchFlag.MatchExactly)
    click_row(user, window.listbox, window.listbox.row(item))
    user.click(window.buttonlist.editButton)
    qtbot.waitUntil(lambda: isinstance(QApplication.activeWindow(), CreateAction))
    action = QApplication.activeWindow()
    click_row(user, action.listbox, 0)
    user.click(action.buttonlist.editButton)
    qtbot.waitUntil(lambda: isinstance(QApplication.activeWindow(), CreateFunction))
    function = QApplication.activeWindow()
    pick_text(user, qtbot, function.stack.currentWidget().controls[0], 'UPPER CASE')
    user.click(function.okcancel.okButton)
    qtbot.waitUntil(lambda: not function.isVisible())
    user.activate(action)
    user.click(action.okcancel.okButton)
    qtbot.waitUntil(lambda: menu_item(mainwin, 'Case Conversion').funcs[0].args[0] == 'UPPER CASE')
    close(user, window)
    user.press(Key.Key_1, Ctrl)
    upper = {f: [f'{f} 1'.upper()] for f in FIELDS}
    written(qtbot, paths[0], upper)
    assert in_files(paths) == [upper, tags(2)]
    assert in_table(table) == [upper, tags(2)]


def test_editing_a_shortcut_keeps_its_key(loaded, mainwin, user, qtbot, monkeypatch):
    # The docs don't say; this is what puddletag should do: renaming a
    # shortcut in Edit Shortcuts, leaving its key field as it opened, keeps
    # its key.
    table, paths = loaded
    window = open_actions(user, qtbot)
    check(user, window, 'Case Conversion')
    assign(user, monkeypatch, window, pressing(user, Key.Key_1))
    editor = edit_shortcuts(user, qtbot, window)
    dialog = edit_item(user, qtbot, editor, 0)
    user.click(dialog._name)
    user.press(Key.Key_A, Ctrl)
    user.type('Title Case')
    user.click(dialog._ok)
    user.activate(editor)
    user.click(button(editor, 'OK'))
    close(user, window)
    assert shortcuts_on_menu(mainwin) == [('Title Case', 'Ctrl+1')]
    user.press(Key.Key_1, Ctrl)
    written(qtbot, paths[0], mixed(1))
    assert in_files(paths) == [mixed(1), tags(2)]


def test_removed_shortcut_key_stays_removed(loaded, mainwin, user, qtbot, monkeypatch, restart):
    # The docs don't say; this is what puddletag should do: a shortcut
    # removed in Edit Shortcuts, then assigned again under the same name
    # with "Don't assign keyboard shortcut", has no key after a restart.
    table, paths = loaded
    window = open_actions(user, qtbot)
    check(user, window, 'Case Conversion')
    assign(user, monkeypatch, window, pressing(user, Key.Key_1))
    editor = edit_shortcuts(user, qtbot, window)
    click_row(user, editor._listbox, 0)
    user.click(tool_button(editor, 'Remove'))
    user.click(button(editor, 'OK'))
    assert shortcuts_on_menu(mainwin) == []
    assign(user, monkeypatch, window, no_key(user))
    close(user, window)
    win = restart()
    assert shortcuts_on_menu(win) == [('Case Conversion', '')]


@pytest.mark.xfail(strict=True, reason='with eleven or more shortcuts, Edit Shortcuts moves '
                                       'keys between them')
def test_eleven_shortcuts_keep_their_keys(loaded, mainwin, user, qtbot, monkeypatch):
    # The docs don't say; this is what puddletag should do: pressing OK in
    # Edit Shortcuts without a change leaves every shortcut with its own
    # key.
    keys = [Key.Key_1, Key.Key_2, Key.Key_3, Key.Key_4, Key.Key_5, Key.Key_6, Key.Key_7,
            Key.Key_8, Key.Key_9, Key.Key_0, Key.Key_B]
    table, paths = loaded
    window = open_actions(user, qtbot)
    check(user, window, 'Case Conversion')
    for i, key in enumerate(keys, 1):
        assign(user, monkeypatch, window, pressing(user, key), name=f'Case {i}')
    expected = {f'Case {i}': f'Ctrl+{"B" if i == 11 else i % 10}' for i in range(1, 12)}
    assert dict(shortcuts_on_menu(mainwin)) == expected
    editor = edit_shortcuts(user, qtbot, window)
    user.click(button(editor, 'OK'))
    close(user, window)
    assert dict(shortcuts_on_menu(mainwin)) == expected
