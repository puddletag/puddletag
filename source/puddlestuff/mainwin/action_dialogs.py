# -*- coding: utf-8 -*-
from puddlestuff.actiondlg import ActionWindow, CreateFunction
from puddlestuff.constants import RIGHTDOCK, SELECTIONCHANGED
from PyQt4.QtGui import QPushButton, QHBoxLayout, QListWidgetItem, QApplication
from PyQt4.QtCore import SIGNAL, Qt
from puddlestuff.mainwin.funcs import run_func, applyaction
from puddlestuff.puddleobjects import PuddleConfig
from functools import partial
import pdb

class ActionDialog(ActionWindow):
    def __init__(self, *args, **kwargs):
        self.emits = []
        self.receives = [(SELECTIONCHANGED, self._update)]
        if 'status' in kwargs:
            self._status = kwargs['status']
            del(kwargs['status'])
        super(ActionDialog, self).__init__(*args, **kwargs)
        self.okcancel.ok.hide()
        self.okcancel.cancel.hide()
        self._apply = QPushButton(QApplication.translate("Defaults", 'Appl&y'))
        write = lambda funcs: applyaction(self._status['selectedfiles'], funcs)
        self.connect(self._apply, SIGNAL('clicked()'),
            partial(self.okClicked, False))
        self.connect(self, SIGNAL('donewithmyshit'), write)
        hbox = QHBoxLayout()
        hbox.addStretch()
        hbox.addWidget(self._apply)
        self.grid.addLayout(hbox, 2, 0, 1, 1)

    def _update(self):
        try:
            self.example = self._status['selectedfiles'][0]
        except IndexError:
            self.example = None
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
        self.funcs = self.loadActions()
        cparser = PuddleConfig()
        to_check = cparser.get('actions', 'checked', [])
        for z in self.funcs:
            func_name = self.funcs[z][1]
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

class FunctionDialog(CreateFunction):
    def __init__(self, *args, **kwargs):
        self.emits = []
        self.receives = [(SELECTIONCHANGED, self._update)]
        if 'status' in kwargs:
            self._status = kwargs['status']
            del(kwargs['status'])
        super(FunctionDialog, self).__init__(*args, **kwargs)
        self.okcancel.ok.hide()
        self.okcancel.cancel.hide()
        self._apply = QPushButton(QApplication.translate("Defaults", 'Appl&y'))
        write = lambda func: run_func(self._status['selectedfiles'], func)
        self.connect(self._apply, SIGNAL('clicked()'),
            partial(self.okClicked, False))
        self.connect(self, SIGNAL('valschanged'), write)
        self.disconnect(self.okcancel, SIGNAL('cancel'), self.close)
        
        hbox = QHBoxLayout()
        hbox.addStretch()
        hbox.addWidget(self._apply)
        self.vbox.addLayout(hbox)

    def _update(self):
        try:
            f, field = self._status['firstselection']
        except IndexError:
            return
        field = field.keys()[0]
        self.example = f
        self._text = f.get(field, u'')
        
        widget = self.stack.currentWidget()
        
        widget._text = self._text
        widget.example = f

        widget.showexample()

    def reject(self):
        pass


controls = [
    ("Functions", FunctionDialog, RIGHTDOCK, False),
    ("Actions", ActionDialog, RIGHTDOCK, False)]