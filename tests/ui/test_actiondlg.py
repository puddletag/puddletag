import os

import pytest

pytestmark = pytest.mark.ui


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
