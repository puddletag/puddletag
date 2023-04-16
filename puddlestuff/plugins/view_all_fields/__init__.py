import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAbstractItemView, QAction, QApplication, QFrame, QHBoxLayout, QInputDialog, QLabel, \
    QPushButton, QVBoxLayout

from ...puddlesettings import add_config_widget
from ...puddletag import add_shortcuts, status
from ...constants import SAVEDIR
from ...puddleobjects import (natural_sort_key, ListButtons,
                              ListBox, PuddleConfig)
from ...tagmodel import TableHeader
from ...translations import translate

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

    data = [(k, k) for k in fields + sorted(keys, key=natural_sort_key)]
    tb = status['table']
    tb.model().setHeader(data)
    hd = TableHeader(Qt.Orientation.Horizontal)
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
    action.toggled.connect(show_fields)
    add_shortcuts('&Plugins', [sep(), action, sep()])
    add_config_widget(Settings)


class ButtonsAndList(QFrame):
    def __init__(self, parent=None, title='', add_text=ADD_TEXT,
                 help_text=''):

        QFrame.__init__(self, parent)
        self.title = title
        connect = lambda c, signal, s: getattr(c, signal).connect(s)
        self.setFrameStyle(QFrame.Shape.Box)
        self.listbox = ListBox()
        self.listbox.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        buttons = ListButtons()

        hbox = QHBoxLayout()
        hbox.addWidget(self.listbox)

        vbox = QVBoxLayout()
        sortlistbox = QPushButton(translate("Defaults", '&Sort'))
        self._sortOrder = Qt.SortOrder.AscendingOrder
        connect(sortlistbox, 'clicked', self._sortListBox)
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
        buttons.duplicateButton.setVisible(False)
        self.listbox.connectToListButtons(buttons)
        self.listbox.editButton = buttons.editButton
        connect(self.listbox, 'itemDoubleClicked',
                self._doubleClicked)
        self.addText = add_text

    def _doubleClicked(self, item):
        self.editItem()

    def _sortListBox(self):
        if self._sortOrder == Qt.SortOrder.AscendingOrder:
            self.listbox.sortItems(Qt.SortOrder.DescendingOrder)
            self._sortOrder = Qt.SortOrder.DescendingOrder
        else:
            self.listbox.sortItems(Qt.SortOrder.AscendingOrder)
            self._sortOrder = Qt.SortOrder.AscendingOrder

    def addItem(self):
        l = self.listbox.item
        patterns = [str(l(z).text()) for z in range(self.listbox.count())]
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
        patterns = [str(l(z).text()) for z in range(self.listbox.count())]
        (text, ok) = QInputDialog().getItem(self, 'puddletag',
                                            self.addText, patterns, row)
        if ok:
            item = l(row)
            item.setText(text)
            item.setSelected(True)

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
