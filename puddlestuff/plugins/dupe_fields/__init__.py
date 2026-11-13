from collections import Counter

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QInputDialog

from .. import status, connect_control
from ... import puddletag


class _SignalObject(QObject):
    highlight = pyqtSignal(list, name='highlight')


obj = _SignalObject()


def highlight_dupe_field(action):
    field, ok = QInputDialog.getText(None, 'puddletag', 'Field to compare')
    if not ok:
        action.setChecked(False)
        return

    field = str(field)
    files = status['selectedfiles']
    if not files or len(files) <= 1:
        action.setChecked(False)
        return

    values = [f.get(field) for f in files]
    keys = [None if value is None else tuple(value) for value in values]
    counts = Counter(keys)
    highlight = [f for f, key in zip(files, keys) if key is not None and counts[key] > 1]
    obj.highlight.emit(highlight)


def remove_highlight():
    obj.highlight.emit([])


def init(parent=None):
    def sep():
        k = QAction(parent)
        k.setSeparator(True)
        return k

    action = QAction('Dupe highlight', parent)
    action.setCheckable(True)
    action.toggled.connect(
        lambda v: highlight_dupe_field(action) if v else remove_highlight())
    puddletag.add_shortcuts('&Plugins', [sep(), action, sep()])

    obj.receives = []
    obj.emits = ['highlight']
    connect_control(obj)
