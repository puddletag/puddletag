"""The action editor (tut2.txt, tut3.txt, function.txt, menus.txt): the
Actions window, Edit Action and the Functions window, run from the main
window as a user runs them, with clicks and keys in the windows. Each result
is checked in the window, in the saved .action files and settings, and in
the files and the table. Synthetic files, tags and actions.
"""
import json
import os

import pytest
from PyQt6.QtCore import QPoint, QPointF, QSize, QTranslator, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem

from puddlestuff import audioinfo, puddleobjects
from puddlestuff.actiondlg import ActionWindow, CreateAction, CreateFunction
from puddlestuff.constants import ACTIONDIR
from puddlestuff.findfunc import Macro
from puddlestuff.helperwin import ImportTextFile
from puddlestuff.mainwin.action_dialogs import ActionDialog
from puddlestuff.puddleobjects import PuddleConfig

pytestmark = pytest.mark.ui

Key = Qt.Key
Ctrl = Qt.KeyboardModifier.ControlModifier
Shift = Qt.KeyboardModifier.ShiftModifier



def test_functions_dialog_can_shrink_with_long_history(qtbot, qapp, clean_profile):
    from puddlestuff.actiondlg import CreateFunction
    from puddlestuff.constants import CONFIGDIR
    from puddlestuff.findfunc import Function
    from puddlestuff.puddleobjects import PuddleConfig

    pattern = '%title%' * 100
    PuddleConfig(os.path.join(CONFIGDIR, 'combos')).set(
        '&Format string', 'values', [pattern])

    dialog = CreateFunction(Function('format'))
    qtbot.addWidget(dialog)
    dialog.show()
    qapp.processEvents()

    assert dialog.width() <= dialog.screen().availableGeometry().width()
    dialog.resize(640, dialog.height())
    qapp.processEvents()
    assert dialog.width() == 640
    assert dialog.stack.currentWidget().controls[0].currentText() == pattern


def test_actions_window_lists_the_actions_in_name_order(qtbot, clean_profile, monkeypatch):
    # The docs don't say; users shouldn't see an order that varies by machine.
    # Synthetic: the listing comes back in reverse name order.
    import glob as glob_module
    from puddlestuff.actiondlg import ActionWindow

    real_glob = glob_module.glob
    monkeypatch.setattr(glob_module, 'glob', lambda pattern: sorted(real_glob(pattern), reverse=True))
    window = ActionWindow()
    qtbot.addWidget(window)
    names = [window.listbox.item(row).text() for row in range(window.listbox.count())]
    assert names == ['Case Conversion', 'Standard']


def click_row(user, listbox, row):
    user.click(listbox.viewport(), listbox.visualItemRect(listbox.item(row)).center())


def test_action_steps_can_be_removed_with_no_file_selected(mainwin, user, qtbot):
    # #933: in the Actions dock with no file selected, editing an action and
    # removing a step crashed. The action is the default Case Conversion.
    from PyQt6.QtWidgets import QApplication
    from puddlestuff.actiondlg import CreateAction
    from puddlestuff.mainwin.action_dialogs import ActionDialog

    user.click_menu('Actions')
    [dock] = mainwin.findChildren(ActionDialog)
    qtbot.waitUntil(dock.isVisible)
    assert dock.example is None
    click_row(user, dock.listbox, 0)
    user.click(dock.buttonlist.editButton)
    qtbot.waitUntil(lambda: isinstance(QApplication.activeWindow(), CreateAction))
    editor = QApplication.activeWindow()
    assert editor.listbox.count() == 1
    click_row(user, editor.listbox, 0)
    user.click(editor.buttonlist.removeButton)
    assert editor.listbox.count() == 0
    assert editor.functions == []


DEFAULTS = ['Case Conversion', 'Standard']


def tags(i):
    return {'artist': [f'artist {i}'], 'title': [f'title {i}']}


@pytest.fixture
def loaded(mainwin, make_audio, tmp_path, qtbot, user):
    """Two synthetic MP3s, their title cells selected."""
    music = tmp_path / 'music'
    paths = [make_audio(f'0{i}.mp3', music, artist=f'artist {i}', title=f'title {i}') for i in (1, 2)]
    mainwin.openDir(str(music), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == 2)
    user.activate()
    table.setFocus()
    user.click_cell(user.cell(0, 'title'))
    user.click_cell(user.cell(1, 'title'), Shift)
    return table, paths


def in_files(paths):
    return [audioinfo.usertags(audioinfo.Tag(str(p))) for p in paths]


def in_table(table):
    return [audioinfo.usertags(audio) for audio in table.model().taginfo]


def written(qtbot, user, path, field, value):
    qtbot.waitUntil(lambda: audioinfo.Tag(str(path)).get(field) == value)
    user.activate()


def opened(qtbot, kind):
    """The modal window of this kind."""
    qtbot.waitUntil(lambda: isinstance(QApplication.activeModalWidget(), kind))
    return QApplication.activeModalWidget()


def shown(qtbot, kind):
    """The one visible window of this kind, modal or not: Edit Action opened
    by Edit or Duplicate isn't modal."""
    found = lambda: [w for w in QApplication.topLevelWidgets() if isinstance(w, kind) and w.isVisible()]
    qtbot.waitUntil(lambda: len(found()) == 1)
    return found()[0]


def none_shown(kind):
    return not [w for w in QApplication.topLevelWidgets() if isinstance(w, kind) and w.isVisible()]


def open_actions(user, qtbot):
    """Actions > Actions "opens the actions dialog" (menus.txt:202)."""
    user.click_menu('&Actions')
    window = opened(qtbot, ActionWindow)
    user.activate(window)
    return window


def close_window(user, qtbot, window):
    user.click(window.okcancel.cancelButton)
    qtbot.waitUntil(lambda: not window.isVisible())
    user.activate()


def names(listbox):
    return [listbox.item(row).text() for row in range(listbox.count())]


def select_row(user, listbox, row, modifier=Qt.KeyboardModifier.NoModifier):
    user.click(listbox.viewport(), listbox.visualItemRect(listbox.item(row)).center(), modifier)


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


def pick(user, qtbot, combo, text):
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


def type_into(user, line_edit, text):
    """Clicks the field, selects what's there and types over it."""
    user.click(line_edit)
    user.press(Key.Key_A, Ctrl)
    if text:
        user.type(text)
    else:
        user.press(Key.Key_Backspace)
    assert line_edit.text() == text


def upper_case(user, qtbot, window, fields):
    """Sets UPPER CASE on the Case Conversion function, with these fields."""
    pick(user, qtbot, window.functions, 'Case Conversion')
    function = window.stack.currentWidget()
    pick(user, qtbot, function.controls[0], 'UPPER CASE')
    user.activate(window)
    type_into(user, function.tagcombo.lineEdit(), fields)


def rename(user, window, row, text):
    """F2 on the row, type the new name, Enter."""
    user.activate(window)
    select_row(user, window.listbox, row)
    user.press(Key.Key_F2)
    user.press(Key.Key_A, Ctrl)
    if text:
        user.type(text)
    else:
        user.press(Key.Key_Backspace)
    user.press(Key.Key_Return)


def action_path(filename):
    return os.path.join(ACTIONDIR, filename)


def write_action(filename, name, functions):
    """A synthetic .action file; functions are (func_name, fields, arguments)."""
    data = {'info': {'name': name}}
    for i, (func_name, fields, arguments) in enumerate(functions):
        data[f'Func{i}'] = {'arguments': arguments, 'fields': fields,
                            'func_name': func_name, 'module': 'puddlestuff.functions'}
    with open(action_path(filename), 'w') as f:
        json.dump(data, f)


def steps(filename):
    """The steps the saved action holds, as Edit Action lists them."""
    return [function.description() for function in Macro(action_path(filename)).actions]


def edit_action(user, qtbot, window, row):
    """Selects the action's row and clicks Edit: the Edit Action window."""
    select_row(user, window.listbox, row)
    user.click(window.buttonlist.editButton)
    editor = shown(qtbot, CreateAction)
    user.activate(editor)
    return editor


def test_add_action(loaded, user, qtbot, dialogs):
    # tut2.txt:48 "Actions are just a bunch of functions run one after the
    # other."; tut2.txt:50 "What they do is run previously defined functions
    # on the selected files."
    table, paths = loaded
    window = open_actions(user, qtbot)
    dialogs.answer('QInputDialog.getText', ('Upper', True))
    user.click(window.buttonlist.addButton)
    editor = opened(qtbot, CreateAction)
    assert editor.windowTitle() == 'Add Action: Upper'
    user.click(editor.buttonlist.addButton)
    function = opened(qtbot, CreateFunction)
    upper_case(user, qtbot, function, 'title')
    user.click(function.okcancel.okButton)
    qtbot.waitUntil(lambda: editor.listbox.count() == 1)
    user.click(editor.okcancel.okButton)
    qtbot.waitUntil(lambda: not editor.isVisible())
    user.activate(window)
    assert names(window.listbox) == DEFAULTS + ['Upper']
    assert Macro(action_path('Upper.action')).name == 'Upper'
    check(user, window, 'Upper')
    user.click(window.okcancel.okButton)
    written(qtbot, user, paths[1], 'title', ['TITLE 2'])
    expected = [{'artist': ['artist 1'], 'title': ['TITLE 1']},
                {'artist': ['artist 2'], 'title': ['TITLE 2']}]
    assert in_files(paths) == expected
    assert in_table(table) == expected


def test_cancel_a_new_action(loaded, user, qtbot, dialogs):
    # Docs silent: cancelling a new action leaves no trace.
    table, paths = loaded
    window = open_actions(user, qtbot)
    dialogs.answer('QInputDialog.getText', ('Upper', True))
    user.click(window.buttonlist.addButton)
    editor = opened(qtbot, CreateAction)
    user.click(editor.okcancel.cancelButton)
    qtbot.waitUntil(lambda: not editor.isVisible())
    assert names(window.listbox) == DEFAULTS
    assert not os.path.exists(action_path('Upper.action'))
    close_window(user, qtbot, window)
    assert in_files(paths) == [tags(1), tags(2)]
    assert in_table(table) == [tags(1), tags(2)]


def test_duplicate_action(loaded, user, qtbot, dialogs):
    # tut2.txt:58 Case Conversion "changes the album, title and artist
    # fields"; Duplicate itself is docs-silent: the copy has the same steps.
    window = open_actions(user, qtbot)
    select_row(user, window.listbox, 0)
    dialogs.answer('QInputDialog.getText', ('Mixed', True))
    user.click(window.buttonlist.duplicateButton)
    editor = shown(qtbot, CreateAction)
    assert editor.windowTitle() == 'Edit Action: Mixed'
    assert names(editor.listbox) == steps('caseconversion.action')
    [(name, args, kwargs)] = dialogs.calls
    assert args[1] == 'Copy Case Conversion action'
    user.click(editor.okcancel.okButton)
    qtbot.waitUntil(lambda: not editor.isVisible())
    assert names(window.listbox) == DEFAULTS + ['Mixed']
    assert steps('Mixed.action') == steps('caseconversion.action')
    assert Macro(action_path('Mixed.action')).name == 'Mixed'
    close_window(user, qtbot, window)


def test_duplicate_with_two_actions_selected_does_nothing(loaded, user, qtbot, dialogs):
    # Docs silent: Duplicate needs exactly one selected action.
    window = open_actions(user, qtbot)
    select_row(user, window.listbox, 0)
    select_row(user, window.listbox, 1, Ctrl)
    user.click(window.buttonlist.duplicateButton)
    qtbot.wait(100)
    assert dialogs.calls == []
    assert none_shown(CreateAction)
    assert names(window.listbox) == DEFAULTS
    assert sorted(os.listdir(ACTIONDIR)) == ['caseconversion.action', 'standard.action']
    close_window(user, qtbot, window)


def test_rename_action_with_f2(loaded, user, qtbot):
    # Docs silent: F2 renames the action and the file keeps its name.
    window = open_actions(user, qtbot)
    rename(user, window, 0, 'Mixed')
    qtbot.waitUntil(lambda: window.listbox.item(0).text() == 'Mixed')
    assert Macro(action_path('caseconversion.action')).name == 'Mixed'
    close_window(user, qtbot, window)
    window = open_actions(user, qtbot)
    assert names(window.listbox) == ['Mixed', 'Standard']
    close_window(user, qtbot, window)


def test_remove_one_action(loaded, mainwin, user, qtbot):
    # Docs silent: Remove sets the action's file aside as .deleted.
    window = open_actions(user, qtbot)
    select_row(user, window.listbox, 1)
    user.click(window.buttonlist.removeButton)
    assert names(window.listbox) == ['Case Conversion']
    assert sorted(os.listdir(ACTIONDIR)) == ['caseconversion.action', 'standard.action.deleted']
    close_window(user, qtbot, window)
    [dock] = mainwin.findChildren(ActionDialog)
    assert names(dock.listbox) == ['Case Conversion']
    window = open_actions(user, qtbot)
    assert names(window.listbox) == ['Case Conversion']
    close_window(user, qtbot, window)


def test_action_order_kept_on_reopen(loaded, mainwin, user, qtbot):
    # Docs silent: Move Up and Move Down order is kept after closing.
    window = open_actions(user, qtbot)
    select_row(user, window.listbox, 0)
    user.click(window.buttonlist.movedownButton)
    assert names(window.listbox) == ['Standard', 'Case Conversion']
    select_row(user, window.listbox, 1)
    user.click(window.buttonlist.moveupButton)
    assert names(window.listbox) == DEFAULTS
    select_row(user, window.listbox, 0)
    user.click(window.buttonlist.movedownButton)
    close_window(user, qtbot, window)
    assert PuddleConfig().get('puddleactions', 'order', []) == [
        action_path('standard.action'), action_path('caseconversion.action')]
    [dock] = mainwin.findChildren(ActionDialog)
    assert names(dock.listbox) == ['Standard', 'Case Conversion']
    window = open_actions(user, qtbot)
    assert names(window.listbox) == ['Standard', 'Case Conversion']
    close_window(user, qtbot, window)


def test_checked_actions_kept_on_reopen(loaded, mainwin, user, qtbot):
    # tut2.txt:50 "What they do is run previously defined functions on the
    # selected files."; keeping the checked state is docs-silent.
    table, paths = loaded
    window = open_actions(user, qtbot)
    check(user, window, 'Standard')
    user.click(window.okcancel.okButton)
    qtbot.waitUntil(lambda: not window.isVisible())
    user.activate()
    assert PuddleConfig().get('actions', 'checked', []) == ['Standard']
    assert in_files(paths) == [tags(1), tags(2)]
    assert in_table(table) == [tags(1), tags(2)]
    [dock] = mainwin.findChildren(ActionDialog)
    [item] = dock.listbox.findItems('Standard', Qt.MatchFlag.MatchExactly)
    assert item.checkState() == Qt.CheckState.Checked
    window = open_actions(user, qtbot)
    [standard] = window.listbox.findItems('Standard', Qt.MatchFlag.MatchExactly)
    [case] = window.listbox.findItems('Case Conversion', Qt.MatchFlag.MatchExactly)
    assert standard.checkState() == Qt.CheckState.Checked
    assert case.checkState() == Qt.CheckState.Unchecked
    close_window(user, qtbot, window)


class SyntheticTranslation(QTranslator):
    def __init__(self, texts):
        super().__init__()
        self._texts = texts

    def translate(self, context, source, disambiguation=None, n=-1):
        return self._texts.get((context, source))


@pytest.mark.parametrize('kind', ['window', 'dock'])
@pytest.mark.xfail(strict=True, reason='Edit and Duplicate are enabled with no action selected, and raise KeyError -1')
def test_edit_and_duplicate_need_a_selected_action(kind, loaded, mainwin, user, qtbot, dialogs):
    # The docs don't say; with no action selected there is nothing to edit,
    # duplicate, remove or move, so those buttons are off (Edit used to raise
    # KeyError -1).
    if kind == 'window':
        # Not activated, as offscreen: no row is current.
        user.click_menu('&Actions')
        window = opened(qtbot, ActionWindow)
    else:
        user.click_menu('Actions')
        [window] = mainwin.findChildren(ActionDialog)
        qtbot.waitUntil(window.isVisible)
    buttons = window.buttonlist
    assert window.listbox.currentRow() == -1
    assert not buttons.editButton.isEnabled()
    assert not buttons.duplicateButton.isEnabled()
    assert not buttons.removeButton.isEnabled()
    assert not buttons.moveupButton.isEnabled()
    assert not buttons.movedownButton.isEnabled()
    assert buttons.addButton.isEnabled()
    user.click(buttons.editButton)
    user.click(buttons.duplicateButton)
    qtbot.wait(100)
    assert none_shown(CreateAction)
    assert dialogs.calls == []
    select_row(user, window.listbox, 0)
    assert buttons.editButton.isEnabled()
    assert buttons.duplicateButton.isEnabled()


@pytest.mark.xfail(strict=True, reason="Removing two actions at once leaves the second one's entry behind, "
                                       "so Edit opens the wrong action")
def test_remove_two_actions_then_edit(loaded, user, qtbot):
    # The docs don't say; removing two actions at once must leave the list and
    # the actions it stands for in step. The three actions are synthetic.
    for filename, name in (('u.action', 'U'), ('v.action', 'V'), ('w.action', 'W')):
        write_action(filename, name, [('titleCase', ['title'], ['UPPER CASE', '., !'])])
    window = open_actions(user, qtbot)
    assert names(window.listbox) == DEFAULTS + ['U', 'V', 'W']
    select_row(user, window.listbox, 1)
    select_row(user, window.listbox, 2, Ctrl)
    user.click(window.buttonlist.removeButton)
    assert names(window.listbox) == ['Case Conversion', 'V', 'W']
    assert sorted(f for f in os.listdir(ACTIONDIR) if f.endswith('.deleted')) == [
        'standard.action.deleted', 'u.action.deleted']
    editor = edit_action(user, qtbot, window, 1)
    assert editor.windowTitle() == 'Edit Action: V'
    user.click(editor.okcancel.cancelButton)
    qtbot.waitUntil(lambda: none_shown(CreateAction))
    user.activate(window)
    close_window(user, qtbot, window)


@pytest.mark.xfail(strict=True, reason='An empty action name is saved')
def test_rename_to_an_empty_name_is_refused(loaded, user, qtbot, dialogs):
    # The docs don't say; an action with no name can't be told apart in the
    # list, so the old name comes back with a warning.
    window = open_actions(user, qtbot)
    dialogs.answer('QMessageBox.warning', None)
    rename(user, window, 0, '')
    qtbot.waitUntil(lambda: bool(dialogs.calls))
    [(name, args, kwargs)] = dialogs.calls
    assert name == 'QMessageBox.warning'
    assert args[2] == 'An action needs a name.'
    assert window.listbox.item(0).text() == 'Case Conversion'
    assert Macro(action_path('caseconversion.action')).name == 'Case Conversion'
    close_window(user, qtbot, window)


@pytest.mark.xfail(strict=True, reason='Renaming to a taken name is undone without a word')
def test_rename_to_a_taken_name_says_so(loaded, user, qtbot, dialogs):
    # The docs don't say; two actions can't share a name, and the program
    # says why the old name came back.
    window = open_actions(user, qtbot)
    dialogs.answer('QMessageBox.warning', None)
    rename(user, window, 0, 'Standard')
    qtbot.waitUntil(lambda: bool(dialogs.calls))
    [(name, args, kwargs)] = dialogs.calls
    assert name == 'QMessageBox.warning'
    assert args[2] == 'An action named <b>Standard</b> already exists.'
    assert names(window.listbox) == DEFAULTS
    assert Macro(action_path('caseconversion.action')).name == 'Case Conversion'
    assert Macro(action_path('standard.action')).name == 'Standard'
    close_window(user, qtbot, window)


@pytest.mark.xfail(strict=True, reason='A name with nothing left for a file name is accepted')
@pytest.mark.parametrize('how', ['add', 'duplicate', 'rename'])
def test_name_with_nothing_for_a_file_name_is_refused(how, loaded, user, qtbot, dialogs):
    # The docs don't say; the name '***' is synthetic. The name is the action's
    # file name, so one with nothing left of it is refused and nothing changes.
    window = open_actions(user, qtbot)
    files = sorted(os.listdir(ACTIONDIR))
    dialogs.answer('QMessageBox.warning', None)
    if how == 'rename':
        rename(user, window, 0, '***')
    else:
        select_row(user, window.listbox, 0)
        dialogs.answer('QInputDialog.getText', ('***', True))
        user.click(window.buttonlist.addButton if how == 'add' else window.buttonlist.duplicateButton)
    qtbot.waitUntil(lambda: any(call[0] == 'QMessageBox.warning' for call in dialogs.calls))
    [(name, args, kwargs)] = [call for call in dialogs.calls if call[0] == 'QMessageBox.warning']
    assert args[2] == "An action's name can't be only spaces, dots or the characters / \\ * ? \" | :"
    assert none_shown(CreateAction)
    assert names(window.listbox) == DEFAULTS
    assert sorted(os.listdir(ACTIONDIR)) == files
    close_window(user, qtbot, window)


@pytest.mark.xfail(strict=True, reason='An action named with a leading dot is saved as a hidden file and gone on reopen')
def test_name_starting_with_a_dot_kept_on_reopen(loaded, user, qtbot, dialogs):
    # The docs don't say; the name '.mp3 fix' is synthetic. An action must
    # still be listed after the window is reopened.
    window = open_actions(user, qtbot)
    dialogs.answer('QInputDialog.getText', ('.mp3 fix', True))
    user.click(window.buttonlist.addButton)
    editor = opened(qtbot, CreateAction)
    user.activate(editor)
    user.click(editor.buttonlist.addButton)
    function = opened(qtbot, CreateFunction)
    user.activate(function)
    upper_case(user, qtbot, function, 'title')
    user.click(function.okcancel.okButton)
    qtbot.waitUntil(lambda: none_shown(CreateFunction))
    user.activate(editor)
    user.click(editor.okcancel.okButton)
    qtbot.waitUntil(lambda: none_shown(CreateAction))
    user.activate(window)
    assert names(window.listbox) == DEFAULTS + ['.mp3 fix']
    assert os.path.exists(action_path('mp3 fix.action'))
    close_window(user, qtbot, window)
    window = open_actions(user, qtbot)
    assert names(window.listbox) == DEFAULTS + ['.mp3 fix']
    close_window(user, qtbot, window)


@pytest.mark.xfail(strict=True, reason="Duplicate's title is formatted before it is translated")
def test_duplicate_window_title_is_translated(loaded, user, qtbot, dialogs):
    # "puddletag's texts can be translated" (translate.txt). The translation
    # is synthetic.
    window = open_actions(user, qtbot)
    select_row(user, window.listbox, 0)
    translator = SyntheticTranslation({('Actions', 'Copy {} action'): 'Synthetic copy of {}'})
    QApplication.installTranslator(translator)
    try:
        dialogs.answer('QInputDialog.getText', ('', False))
        user.click(window.buttonlist.duplicateButton)
    finally:
        QApplication.removeTranslator(translator)
    assert dialogs.calls[0][1][1] == 'Synthetic copy of Case Conversion'
    assert none_shown(CreateAction)
    close_window(user, qtbot, window)


@pytest.mark.xfail(strict=True, reason='Esc forgets the new order; Cancel keeps it')
def test_escape_keeps_the_action_order(loaded, user, qtbot):
    # The docs don't say; Cancel keeps the new order, so Esc and the close
    # button do too.
    window = open_actions(user, qtbot)
    select_row(user, window.listbox, 0)
    user.click(window.buttonlist.movedownButton)
    user.activate(window)
    user.press(Key.Key_Escape)
    qtbot.waitUntil(lambda: not window.isVisible())
    user.activate()
    window = open_actions(user, qtbot)
    assert names(window.listbox) == ['Standard', 'Case Conversion']
    close_window(user, qtbot, window)


def test_edit_action_moves_steps(loaded, user, qtbot):
    # tut2.txt:48 "Actions are just a bunch of functions run one after the other."
    window = open_actions(user, qtbot)
    editor = edit_action(user, qtbot, window, 1)
    before = names(editor.listbox)
    assert len(before) > 1
    select_row(user, editor.listbox, 0)
    user.click(editor.buttonlist.movedownButton)
    assert names(editor.listbox) == [before[1], before[0], *before[2:]]
    select_row(user, editor.listbox, 1)
    user.click(editor.buttonlist.moveupButton)
    assert names(editor.listbox) == before
    select_row(user, editor.listbox, 0)
    user.click(editor.buttonlist.movedownButton)
    user.click(editor.okcancel.okButton)
    qtbot.waitUntil(lambda: not editor.isVisible())
    assert steps('standard.action') == [before[1], before[0], *before[2:]]
    close_window(user, qtbot, window)


def test_edit_action_duplicates_a_step(loaded, user, qtbot):
    # tut2.txt:52-58: the steps of an action can be duplicated.
    window = open_actions(user, qtbot)
    editor = edit_action(user, qtbot, window, 0)
    [step] = names(editor.listbox)
    select_row(user, editor.listbox, 0)
    user.click(editor.buttonlist.duplicateButton)
    function = opened(qtbot, CreateFunction)
    assert function.stack.currentWidget().tagcombo.currentText() == 'artist, album, title'
    user.click(function.okcancel.okButton)
    qtbot.waitUntil(lambda: not function.isVisible())
    assert names(editor.listbox) == [step, step]
    user.activate(editor)
    user.click(editor.okcancel.okButton)
    qtbot.waitUntil(lambda: not editor.isVisible())
    assert steps('caseconversion.action') == [step, step]
    close_window(user, qtbot, window)


def test_selected_field_refused_in_an_action(loaded, user, qtbot, dialogs):
    # The Fields tooltip: "But using __selected in Actions is not."; tut3.txt:90.
    window = open_actions(user, qtbot)
    before = steps('caseconversion.action')
    editor = edit_action(user, qtbot, window, 0)
    user.click(editor.buttonlist.addButton)
    function = opened(qtbot, CreateFunction)
    pick(user, qtbot, function.functions, 'Case Conversion')
    assert function.stack.currentWidget().tagcombo.currentText() == '__selected'
    dialogs.answer('QMessageBox.warning', None)
    user.click(function.okcancel.okButton)
    [(name, args, kwargs)] = dialogs.calls
    assert name == 'QMessageBox.warning'
    assert args[2] == 'Error: Using <b>__selected</b> in Actions is not allowed.'
    assert function.isVisible()
    assert editor.listbox.count() == 1
    user.click(function.okcancel.cancelButton)
    qtbot.waitUntil(lambda: not function.isVisible())
    user.activate(editor)
    user.click(editor.okcancel.cancelButton)
    qtbot.waitUntil(lambda: not editor.isVisible())
    close_window(user, qtbot, window)
    assert steps('caseconversion.action') == before


def test_edit_action_cancel_keeps_the_action(loaded, user, qtbot):
    # Synthetic: the docs are silent on what Cancel does to a step removed in
    # Edit Action; the program leaves the saved action as it was.
    window = open_actions(user, qtbot)
    with open(action_path('caseconversion.action'), 'rb') as f:
        before = f.read()
    editor = edit_action(user, qtbot, window, 0)
    select_row(user, editor.listbox, 0)
    user.click(editor.buttonlist.removeButton)
    assert editor.listbox.count() == 0
    user.click(editor.okcancel.cancelButton)
    qtbot.waitUntil(lambda: not editor.isVisible())
    with open(action_path('caseconversion.action'), 'rb') as f:
        assert f.read() == before
    user.activate(window)
    editor = edit_action(user, qtbot, window, 0)
    assert editor.listbox.count() == 1
    user.click(editor.okcancel.cancelButton)
    qtbot.waitUntil(lambda: not editor.isVisible())
    close_window(user, qtbot, window)


def test_empty_fields_refused(loaded, user, qtbot, dialogs):
    # tut3.txt:88-93 (the Fields list). Synthetic: the docs are silent on the
    # refusal of an empty list.
    table, paths = loaded
    user.click_menu('&Functions')
    function = opened(qtbot, CreateFunction)
    pick(user, qtbot, function.functions, 'Case Conversion')
    user.activate(function)
    type_into(user, function.stack.currentWidget().tagcombo.lineEdit(), '')
    dialogs.answer('QMessageBox.information', None)
    user.click(function.okcancel.okButton)
    [(name, args, kwargs)] = dialogs.calls
    assert name == 'QMessageBox.information'
    assert args[2] == 'Please enter some fields to write to.'
    assert function.isVisible()
    user.click(function.okcancel.cancelButton)
    qtbot.waitUntil(lambda: not function.isVisible())
    user.activate()
    assert in_files(paths) == [tags(1), tags(2)]
    assert in_table(table) == [tags(1), tags(2)]


def test_function_without_fields_hides_them(loaded, user, qtbot, dialogs):
    # function.txt:252 "Removes all the fields in the file (including cover
    # art) except the ones you specify."
    table, paths = loaded
    user.click_menu('&Functions')
    function = opened(qtbot, CreateFunction)
    pick(user, qtbot, function.functions, 'Remove all fields except')
    widget = function.stack.currentWidget()
    assert not widget.tagcombo.isVisible()
    user.activate(function)
    type_into(user, widget.controls[0].combo.lineEdit(), 'title')
    user.click(function.okcancel.okButton)
    qtbot.waitUntil(lambda: 'artist' not in audioinfo.Tag(str(paths[1])))
    user.activate()
    assert dialogs.calls == []
    expected = [{'title': ['title 1']}, {'title': ['title 2']}]
    assert in_files(paths) == expected
    assert in_table(table) == expected


def test_edit_action_preview_no_change(loaded, user, qtbot):
    # Synthetic: the docs are silent on the preview of an action that changes
    # nothing. The files have no genre.
    write_action('blank.action', 'Blank', [('formatValue', ['genre'], [''])])
    window = open_actions(user, qtbot)
    editor = edit_action(user, qtbot, window, 0)
    assert editor._examplelabel.text() == '<b>No change.</b>'
    user.click(editor.okcancel.cancelButton)
    qtbot.waitUntil(lambda: not editor.isVisible())
    close_window(user, qtbot, window)


def test_previews_show_a_parse_error(loaded, user, qtbot):
    # Synthetic: the docs are silent on the preview of an action whose format
    # string doesn't parse.
    table, paths = loaded
    write_action('broken.action', 'Broken', [('formatValue', ['title'], ['$upper(%title%'])])
    window = open_actions(user, qtbot)
    check(user, window, 'Broken')
    message = 'SYNTAX ERROR in $upper: No closing bracket found.'
    assert window._examplelabel.text() == message
    editor = edit_action(user, qtbot, window, 0)
    assert editor._examplelabel.text() == message
    user.click(editor.okcancel.cancelButton)
    qtbot.waitUntil(lambda: not editor.isVisible())
    close_window(user, qtbot, window)
    assert in_files(paths) == [tags(1), tags(2)]
    assert in_table(table) == [tags(1), tags(2)]


def test_ticked_match_case_reopens_ticked(loaded, user, qtbot):
    # function.txt:289-299 (Replace with RegExp's arguments). Synthetic: the
    # docs are silent on the window keeping the last settings.
    from PyQt6.QtWidgets import QStyleOptionButton

    table, paths = loaded
    user.click_toolbar('&Functions')
    function = opened(qtbot, CreateFunction)
    pick(user, qtbot, function.functions, 'Replace with RegExp')
    widget = function.stack.currentWidget()
    user.activate(function)
    type_into(user, widget.tagcombo.lineEdit(), 'title')
    type_into(user, widget.controls[0].combo.lineEdit(), 'zzz')
    # The box is as wide as the window: the middle of it isn't on the box.
    box = widget.controls[2]
    option = QStyleOptionButton()
    box.initStyleOption(option)
    user.click(box, box.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, box).center())
    assert widget.controls[2].isChecked()
    user.click(function.okcancel.okButton)
    qtbot.waitUntil(lambda: not function.isVisible())
    user.activate()
    user.click_menu('&Functions')
    function = opened(qtbot, CreateFunction)
    assert function.functions.currentText() == 'Replace with RegExp'
    assert function.stack.currentWidget().controls[2].isChecked()
    user.click(function.okcancel.cancelButton)
    qtbot.waitUntil(lambda: not function.isVisible())
    user.activate()
    assert in_files(paths) == [tags(1), tags(2)]
    assert in_table(table) == [tags(1), tags(2)]


def test_action_holding_autonumbering(loaded, user, qtbot):
    # function.txt:21 "Numbers tracks sequentially beginning with Start."
    window = open_actions(user, qtbot)
    editor = edit_action(user, qtbot, window, 0)
    user.click(editor.buttonlist.addButton)
    function = opened(qtbot, CreateFunction)
    pick(user, qtbot, function.functions, 'Autonumbering')
    widget = function.stack.currentWidget()
    user.activate(function)
    type_into(user, widget.tagcombo.lineEdit(), 'track')
    user.click(widget.widget._start)
    user.press(Key.Key_A, Ctrl)
    user.type('5')
    assert widget.widget._start.value() == 5
    user.click(function.okcancel.okButton)
    qtbot.waitUntil(lambda: not function.isVisible())
    assert editor.listbox.count() == 2
    user.activate(editor)
    select_row(user, editor.listbox, 1)
    user.click(editor.buttonlist.editButton)
    again = opened(qtbot, CreateFunction)
    assert again.stack.currentWidget().widget._start.value() == 5
    user.click(again.okcancel.cancelButton)
    qtbot.waitUntil(lambda: not again.isVisible())
    user.activate(editor)
    user.click(editor.okcancel.cancelButton)
    qtbot.waitUntil(lambda: not editor.isVisible())
    close_window(user, qtbot, window)


@pytest.mark.xfail(strict=True, reason="OK in the Functions window with a plugin's function raises TypeError: "
                   "the function itself, not its name, is saved as the last one used")
def test_plugin_function_with_a_check_box(loaded, user, qtbot, monkeypatch):
    # Synthetic plugin function: the docs are silent on check box arguments.
    from puddlestuff import functions
    from puddlestuff.util import PluginFunction

    def exclaim(text, loud):
        return text + '!' if loud else text

    monkeypatch.setitem(functions.functions, 'synthetic_exclaim',
                        PluginFunction('Synthetic exclaim', exclaim, 'Exclaim $0, loud: $1',
                                       args=[('&Loud', 'check', True)]))
    table, paths = loaded
    user.click_menu('&Functions')
    function = opened(qtbot, CreateFunction)
    pick(user, qtbot, function.functions, 'Synthetic exclaim')
    widget = function.stack.currentWidget()
    assert widget.controls[0].isChecked()
    assert widget.controls[0].text() == '&Loud'
    user.activate(function)
    type_into(user, widget.tagcombo.lineEdit(), 'title')
    user.click(function.okcancel.okButton)
    written(qtbot, user, paths[1], 'title', ['title 2!'])
    expected = [{'artist': ['artist 1'], 'title': ['title 1!']},
                {'artist': ['artist 2'], 'title': ['title 2!']}]
    assert in_files(paths) == expected
    assert in_table(table) == expected
    # Docs-silent: the function used last is selected again.
    user.click_menu('&Functions')
    function = opened(qtbot, CreateFunction)
    assert function.functions.currentText() == 'Synthetic exclaim'
    assert function.stack.currentWidget().controls[0].text() == '&Loud'
    user.click(function.okcancel.cancelButton)
    qtbot.waitUntil(lambda: not function.isVisible())
    user.activate()


def test_wheel_scrolls_a_wide_preview_sideways(mainwin, make_audio, tmp_path, qtbot, user):
    # Synthetic: the docs are silent on a preview wider than the window.
    music = tmp_path / 'wide'
    make_audio('01.mp3', music, title='x' * 400)
    mainwin.openDir(str(music), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == 1)
    user.activate()
    user.click_cell(user.cell(0, 'title'))
    user.click_menu('&Functions')
    function = opened(qtbot, CreateFunction)
    upper_case(user, qtbot, function, 'title')
    label = function.exlabel
    qtbot.waitUntil(lambda: label.horizontalScrollBar().isVisible())
    event = QWheelEvent(QPointF(5, 5), QPointF(label.mapToGlobal(QPoint(5, 5))), QPoint(), QPoint(0, -120),
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(label.viewport(), event)
    assert label.horizontalScrollBar().value() > 0
    user.click(function.okcancel.cancelButton)
    qtbot.waitUntil(lambda: not function.isVisible())
    user.activate()


# function.txt: "Matches a regular expression."; tut3.txt: "Multiple-valued
# fields are shown like value1\\value2."; #642: "When applying a Replace with
# Regexp Action on a multi-value field, even if there is no match, the
# double-slash is replaced by a single slash, joining all values together
# awkwardly."
@pytest.mark.parametrize('regexp, replacement, expected', [
    ('B', 'A', ['A']),
    ('B', 'C', ['A', 'C']),
    ('zzz', '', ['A', 'B']),
], ids=['values become equal', 'match', 'no match'])
@pytest.mark.xfail(strict=True, reason='Replace with RegExp joins a multi-valued field into one value (#642)')
def test_replace_with_regexp_keeps_multiple_values(mainwin, make_audio, tmp_path, qtbot, user,
                                                    regexp, replacement, expected):
    path = make_audio('01.mp3', tmp_path / 'multi', artist=['A', 'B'], title='title 1')
    mainwin.openDir(str(path.parent), False)
    table = mainwin._table
    qtbot.waitUntil(lambda: table.model().rowCount() == 1)
    user.activate()
    user.click_cell(user.cell(0, 'artist'))
    user.click_toolbar('&Functions')
    window = opened(qtbot, CreateFunction)
    pick(user, qtbot, window.functions, 'Replace with RegExp')
    function = window.stack.currentWidget()
    user.activate(window)
    type_into(user, function.tagcombo.lineEdit(), 'artist')
    type_into(user, function.controls[0].combo.lineEdit(), regexp)
    type_into(user, function.controls[1].combo.lineEdit(), replacement)
    user.click(window.okcancel.okButton)
    qtbot.waitUntil(lambda: audioinfo.Tag(str(path)).get('artist') == expected)
    user.activate()
    assert table.model().taginfo[0]['artist'] == expected
    assert table.model().data(user.cell(0, 'artist')) == '\\\\'.join(expected)


def open_edit_action(user, qtbot):
    window = open_actions(user, qtbot)
    return edit_action(user, qtbot, window, 0)


def open_import(user, qtbot):
    user.click_menu('&Clipboard->Tag')
    window = opened(qtbot, ImportTextFile)
    user.activate(window)
    return window


def cancel_button(window):
    return window.okcancel.cancelButton if isinstance(window, CreateAction) else window.cancel


def leave(user, qtbot, window, close):
    """Closes the window with `close`, then the Actions window behind Edit
    Action."""
    close(window)
    qtbot.waitUntil(lambda: not window.isVisible())
    for actions in [w for w in QApplication.topLevelWidgets() if isinstance(w, ActionWindow) and w.isVisible()]:
        close_window(user, qtbot, actions)
    user.activate()


def click_cancel(user):
    return lambda window: user.click(cancel_button(window))


def press_escape(user):
    def close(window):
        user.activate(window)
        user.press(Key.Key_Escape)
    return close


@pytest.fixture(autouse=True)
def forget_sizes():
    """The window sizes' settings are shared by the whole session."""
    yield
    settings = puddleobjects.winsettings.__defaults__[0]
    settings.remove('editaction')
    settings.remove('importwin')


WINDOWS = pytest.mark.parametrize(
    'open_window', [open_edit_action, open_import], ids=['Edit Action', 'Import tags from text'])


CANCEL_WINDOWS = pytest.mark.parametrize('open_window', [
    pytest.param(open_edit_action, id='Edit Action', marks=pytest.mark.xfail(
        strict=True, reason='Cancel in Edit Action saves no window size')),
    pytest.param(open_import, id='Import tags from text')])


@CANCEL_WINDOWS
def test_window_keeps_its_size(loaded, user, qtbot, open_window):
    # #379: "Instead of maximizing, just enlarge them. If they are enlarged,
    # but not maximized, puddletag correctly preserves their size".
    window = open_window(user, qtbot)
    window.resize(700, 500)
    qtbot.waitUntil(lambda: window.size() == QSize(700, 500))
    leave(user, qtbot, window, click_cancel(user))

    window = open_window(user, qtbot)
    assert window.size() == QSize(700, 500)
    leave(user, qtbot, window, click_cancel(user))


@CANCEL_WINDOWS
def test_maximized_window_reopens_maximized(loaded, user, qtbot, open_window):
    # #379: "The size (maximized) should be preserved".
    window = open_window(user, qtbot)
    window.showMaximized()
    qtbot.waitUntil(window.isMaximized)
    leave(user, qtbot, window, click_cancel(user))

    window = open_window(user, qtbot)
    assert window.isMaximized()
    leave(user, qtbot, window, click_cancel(user))


@pytest.mark.xfail(strict=True, reason='Esc saves no window size')
@WINDOWS
def test_escape_keeps_the_window_size(loaded, user, qtbot, open_window):
    # As #379's enlarged window, closed with Esc: it comes back as it was
    # left, as it does after Cancel.
    window = open_window(user, qtbot)
    window.resize(700, 500)
    qtbot.waitUntil(lambda: window.size() == QSize(700, 500))
    leave(user, qtbot, window, press_escape(user))

    window = open_window(user, qtbot)
    assert window.size() == QSize(700, 500)
    leave(user, qtbot, window, click_cancel(user))


@pytest.mark.xfail(strict=True, reason='The Functions window shows an empty preview when nothing changes')
def test_functions_preview_no_change(loaded, user, qtbot):
    # Synthetic: the docs are silent on the preview of a function that changes
    # nothing; Edit Action shows "No change." for it. The files have no genre.
    table, paths = loaded
    user.click_menu('&Functions')
    function = opened(qtbot, CreateFunction)
    pick(user, qtbot, function.functions, 'Format value')
    user.activate(function)
    widget = function.stack.currentWidget()
    type_into(user, widget.tagcombo.lineEdit(), 'genre')
    type_into(user, widget.controls[0].combo.lineEdit(), '')
    assert function.exlabel.text() == '<b>No change.</b>'
    user.click(function.okcancel.cancelButton)
    qtbot.waitUntil(lambda: not function.isVisible())
    user.activate()
    assert in_files(paths) == [tags(1), tags(2)]
    assert in_table(table) == [tags(1), tags(2)]


@pytest.mark.xfail(strict=True, reason='The message has a stray "for"')
def test_functions_window_says_when_a_function_has_no_preview(loaded, user, qtbot):
    # function.txt:8 lists Autonumbering. Synthetic: the docs are silent on the
    # preview of a function that can't show one.
    user.click_menu('&Functions')
    function = opened(qtbot, CreateFunction)
    pick(user, qtbot, function.functions, 'Autonumbering')
    assert function.exlabel.text() == 'No preview is shown for this function.'
    user.click(function.okcancel.cancelButton)
    qtbot.waitUntil(lambda: not function.isVisible())
    user.activate()


@pytest.mark.xfail(strict=True, reason='Saving a new action prints "Error parsing config file"')
def test_add_action_prints_no_parse_error(loaded, user, qtbot, dialogs, capsys):
    # Synthetic: the docs are silent on the program's console output.
    window = open_actions(user, qtbot)
    dialogs.answer('QInputDialog.getText', ('Upper', True))
    user.click(window.buttonlist.addButton)
    editor = opened(qtbot, CreateAction)
    user.click(editor.buttonlist.addButton)
    function = opened(qtbot, CreateFunction)
    upper_case(user, qtbot, function, 'title')
    user.click(function.okcancel.okButton)
    qtbot.waitUntil(lambda: editor.listbox.count() == 1)
    user.click(editor.okcancel.okButton)
    qtbot.waitUntil(lambda: not editor.isVisible())
    user.activate(window)
    assert Macro(action_path('Upper.action')).name == 'Upper'
    assert 'Error parsing' not in capsys.readouterr().out
    close_window(user, qtbot, window)
