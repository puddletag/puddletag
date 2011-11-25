# -*- coding: utf-8 -*-

import os

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from puddlestuff.constants import SAVEDIR
from puddlestuff.plugins import add_config_widget, add_shortcuts, status
from puddlestuff.puddleobjects import (natcasecmp, ListButtons,
    ListBox, PuddleConfig)
from puddlestuff.tagmodel import TableHeader
from puddlestuff.translations import translate

CONFIGPATH = os.path.join(SAVEDIR, 'view_all_fields')
ADD_TEXT = translate('Defaults', "Add item?")

state = {}

def load_fields():
    cparser = PuddleConfig(CONFIGPATH)
    return cparser.get('view_all_fields', 'fields',
        ['__filename', '__dirpath'])

def restore_view(state):
    tb = status['table']
    header = tb.horizontalHeader()
    tb.model().setHeader(state['headerdata'])
    QApplication.processEvents()
    header.restoreState(state['headerstate'])

def show_all_fields(fields=None):

    files = status['allfiles']
    keys = set()
    for f in files:
        keys = keys.union(f.usertags)

    if fields is None:
        fields = load_fields()

    for f in fields:
        if f in keys:
            keys.remove(f)

    data = map(lambda k: (k, k), fields + sorted(keys, cmp=natcasecmp))
    tb = status['table']
    tb.model().setHeader(data)
    hd = TableHeader(Qt.Horizontal, data)
    tb.setHorizontalHeader(hd)
    hd.show()
    

def init(parent=None):
    state = {}
    
    def sep():
        k = QAction(parent)
        k.setSeparator(True)
        return k

    def show_fields(checked):
        if checked:
            tb = status['table']
            header = tb.horizontalHeader()
            state['headerdata'] = tb.model().headerdata[:]
            state['headerstate'] = header.saveState()
            show_all_fields()
        else:
            restore_view(state)


    action = QAction('Show all fields', parent)
    action.setCheckable(True)
    action.connect(action, SIGNAL('toggled(bool)'), show_fields)
    add_shortcuts('&Plugins', [sep(), action, sep()])
    add_config_widget(Settings)

class ButtonsAndList(QFrame):
    def __init__(self, parent=None, title=u'', add_text=ADD_TEXT,
        help_text=u''):
            
        QFrame.__init__(self, parent)
        self.title = title
        connect = lambda c, signal, s: self.connect(c, SIGNAL(signal), s)
        self.setFrameStyle(QFrame.Box)
        self.listbox = ListBox()
        self.listbox.setSelectionMode(self.listbox.ExtendedSelection)
        buttons = ListButtons()

        hbox = QHBoxLayout()
        hbox.addWidget(self.listbox)

        vbox = QVBoxLayout()
        sortlistbox = QPushButton(translate("Defaults", '&Sort'))
        self._sortOrder = Qt.AscendingOrder
        connect(sortlistbox, 'clicked()', self._sortListBox)
        vbox.addWidget(sortlistbox)
        vbox.addLayout(buttons)
        vbox.addStretch()

        hbox.addLayout(vbox)

        if help_text:
            label = QLabel(help_text)
            layout = QVBoxLayout()
            layout.addWidget(label)
            layout.addLayout(hbox, 1)
            self.setLayout(layout)
        else:
            self.setLayout(hbox)

        connect(buttons, "add", self.addItem)
        connect(buttons, "edit", self.editItem)
        buttons.duplicate.setVisible(False)
        self.listbox.connectToListButtons(buttons)
        self.listbox.editButton = buttons.edit
        connect(self.listbox, 'itemDoubleClicked(QListWidgetItem *)',
                    self._doubleClicked)
        self.addText = add_text

    def _doubleClicked(self, item):
        self.editItem()

    def _sortListBox(self):
        if self._sortOrder == Qt.AscendingOrder:
            self.listbox.sortItems(Qt.DescendingOrder)
            self._sortOrder = Qt.DescendingOrder
        else:
            self.listbox.sortItems(Qt.AscendingOrder)
            self._sortOrder = Qt.AscendingOrder

    def addItem(self):
        l = self.listbox.item
        patterns = [unicode(l(z).text()) for z in range(self.listbox.count())]
        row = self.listbox.currentRow()
        if row < 0:
            row = 0
        (text, ok) = QInputDialog().getItem(self, 'puddletag',
            self.addText, patterns, row)
        if ok:
            self.listbox.clearSelection()
            self.listbox.addItem(text)
            self.listbox.setCurrentRow(self.listbox.count() - 1)

    def addItems(self, items):
        self.listbox.addItems(items)

    def editItem(self, row=None):
        if row is None:
            row = self.listbox.currentRow()
        l = self.listbox.item
        patterns = [unicode(l(z).text()) for z in range(self.listbox.count())]
        (text, ok) = QInputDialog().getItem (self, 'puddletag',
            self.addText, patterns, row)
        if ok:
            item = l(row)
            item.setText(text)
            self.listbox.setItemSelected(item, True)

    def getItems(self):
        return [item.text() for item in self.listbox.items()]

class Settings(ButtonsAndList):
    title = translate('ViewAllFields', 'View All Fields')
    def __init__(self, parent=None, status=None):
        ButtonsAndList.__init__(self, parent,
            translate('ViewAllFields', 'View All Fields'),
            translate("ViewAllFields", 'Add Field'),
            translate("ViewAllFields", 'Edit fields for "View All Fields"'),
            )
        self.addItems(load_fields())
        self.status = status

    def applySettings(self, *args):
        cparser = PuddleConfig(CONFIGPATH)
        fields = self.getItems()
        cparser.set('view_all_fields', 'fields', fields)

        if state:
            show_all_fields()

if __name__ == '__main__':
    app = QApplication([])
    win = Settings()
    win.show()
    app.exec_()