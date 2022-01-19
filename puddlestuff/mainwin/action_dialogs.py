from functools import partial

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QPushButton, QHBoxLayout, QListWidgetItem

from ..actiondlg import ActionWindow, CreateFunction
from ..constants import RIGHTDOCK, SELECTIONCHANGED
from ..mainwin.funcs import run_func, applyaction
from ..puddleobjects import PuddleConfig
from ..translations import translate


class ActionDialog(ActionWindow):
    def __init__(self, *args, **kwargs):
        self.emits = []
        self.receives = [(SELECTIONCHANGED, self._update)]
        if 'status' in kwargs:
            self._status = kwargs['status']
            del (kwargs['status'])
        super(ActionDialog, self).__init__(*args, **kwargs)
        self.okcancel.okButton.hide()
        self.okcancel.cancelButton.hide()
        self._apply = QPushButton(translate("Defaults", 'Appl&y'))
        write = lambda funcs: applyaction(self._status['selectedfiles'], funcs)
        self._apply.clicked.connect(partial(self.okClicked, False))
        self.donewithmyshit.connect(write)
        hbox = QHBoxLayout()
        hbox.addStretch()
        hbox.addWidget(self._apply)
        self.grid.addLayout(hbox, 2, 0, 1, 1)

    def _update(self):
        try:
            self.example, selected = self._status['firstselection']
        except IndexError:
            self.example = None
        if self.isVisible():
            self.updateExample()

    def updateChecked(self, rows):
        item = self.listbox.item
        for row in range(self.listbox.count()):
            if row in rows:
                item(row).setCheckState(Qt.Checked)
            else:
                item(row).setCheckState(Qt.Unchecked)

    def updateOrder(self):
        self.listbox.clear()
        self.macros = self.loadMacros()
        cparser = PuddleConfig()
        to_check = cparser.get('actions', 'checked', [])
        for i, m in sorted(self.macros.items()):
            func_name = m.name
            item = QListWidgetItem(func_name)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            if func_name in to_check:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
            self.listbox.addItem(item)

    def saveSettings(self):
        self.saveOrder()
        self.saveChecked()

    def showEvent(self, event):
        super(ActionDialog, self).showEvent(event)
        if self.example:
            self.updateExample()


class FunctionDialog(CreateFunction):
    def __init__(self, *args, **kwargs):
        self.emits = []
        self.receives = [(SELECTIONCHANGED, self._update)]
        if 'status' in kwargs:
            self._status = kwargs['status']
            del (kwargs['status'])
        super(FunctionDialog, self).__init__(*args, **kwargs)
        self.okcancel.okButton.hide()
        self.okcancel.cancelButton.hide()
        self._apply = QPushButton(translate("Defaults", 'Appl&y'))
        write = lambda func: run_func(self._status['selectedfiles'], func)
        self._apply.clicked.connect(partial(self.okClicked, False))
        self.valschanged.connect(write)
        self.okcancel.cancel.disconnect(self.close)

        hbox = QHBoxLayout()
        hbox.addStretch()
        hbox.addWidget(self._apply)
        self.vbox.addLayout(hbox)

    def _update(self):
        if not self.isVisible():
            return
        widget = self.stack.currentWidget()
        try:
            f, selected = self._status['firstselection']
        except IndexError:
            widget.updateExample.emit('')
            return

        field = list(selected.keys())[0]
        self.example = f
        self._text = f.get(field, '')

        widget._combotags = list(selected.keys())

        widget._text = self._text
        widget.example = f

        widget.showexample()

    def reject(self):
        pass

    def showEvent(self, event):
        self._update()
        return super(FunctionDialog, self).showEvent(event)


controls = [
    ("Functions", FunctionDialog, RIGHTDOCK, False),
    ("Actions", ActionDialog, RIGHTDOCK, False)]
