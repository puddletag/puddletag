from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QAction, QInputDialog

from .. import status, connect_control
from ...puddletag import add_shortcuts


class _SignalObject(QObject):
    highlight = pyqtSignal(list, name='highlight')


obj = _SignalObject()


def highlight_dupe_field():
    field, ok = QInputDialog.getText(None, 'puddletag', 'Field to compare')
    if not ok:
        return

    field = str(field)
    files = status['selectedfiles']
    if not files or len(files) <= 1:
        return

    highlight = []
    prev = files[0]
    value = prev.get(field)

    for f in files[1:]:
        if f.get(field) == value:
            if value is not None:
                if highlight and highlight[-1] != prev:
                    highlight.append(prev)
                elif not highlight:
                    highlight.append(prev)
                highlight.append(f)
        value = f.get(field)
        prev = f
    obj.highlight.emit(highlight)
    obj.sender().setChecked(True)


def remove_highlight():
    obj.highlight.emit([])
    obj.sender().setChecked(False)


def init(parent=None):
    def sep():
        k = QAction(parent)
        k.setSeparator(True)
        return k

    action = QAction('Dupe highlight', parent)
    action.setCheckable(True)
    action.toggled.connect(
        lambda v: highlight_dupe_field() if v else remove_highlight())
    add_shortcuts('&Plugins', [sep(), action, sep()])

    global obj
    obj.receives = []
    obj.emits = ['highlight']
    connect_control(obj)
