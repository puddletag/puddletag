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
