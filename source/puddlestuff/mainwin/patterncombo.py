from PyQt4.QtGui import *
from PyQt4.QtCore import *
import sys
from puddlestuff.puddleobjects import (PuddleStatus, PuddleConfig, ListBox,
                                        ListButtons)

def load_patterns(filepath=None):
    settings = PuddleConfig(filepath)
    return [settings.get('editor', 'patterns',
                            ['%artist% - $num(%track%,2) - %title%',
                            '%artist% - %title%', '%artist% - %album%',
                            '%artist% - Track %track%', '%artist% - %title%']),
           settings.get('editor', 'index', 0, True)]

class PatternCombo(QComboBox):
    name = 'toolbar-patterncombo'
    def __init__(self, items=None, parent=None, status=None):
        self.emits = ['patternchanged']
        self.receives = [('patterns', self.setItems)]
        self.settingsdialog = SettingsWin
        QComboBox.__init__(self, parent)
        self._status = status
        status['patterns'] = self.items
        status['patterntext'] = lambda: unicode(self.currentText())

        self.setEditable(True)
        if items:
            self.addItems(items)
        pchange = lambda text: self.emit(SIGNAL('patternchanged'),
                                        unicode(text))
        self.connect(self, SIGNAL('editTextChanged ( const QString &)'),
                     pchange)

    def setItems(self, texts):
        self.clear()
        self.addItems(texts)

    def items(self):
        text = self.itemText
        return [unicode(text(i)) for i in range(self.count())]

    def loadSettings(self):
        patterns, index = load_patterns()
        self.setItems(patterns)
        self.setCurrentIndex(index)

    def saveSettings(self):
        settings = PuddleConfig()
        settings.set('editor', 'patterns', self.items())
        settings.set('editor', 'index', self.currentIndex())


class SettingsWin(QFrame):
    title = 'Patterns'
    def __init__(self, parent = None, cenwid = None, status=None):
        QFrame.__init__(self, parent)
        connect = lambda c, signal, s: self.connect(c, SIGNAL(signal), s)
        self.setFrameStyle(QFrame.Box)
        self.listbox = ListBox()
        self.listbox.setSelectionMode(self.listbox.ExtendedSelection)
        buttons = ListButtons()

        self.listbox.addItems(status['patterns'])
        hbox = QHBoxLayout()
        hbox.addWidget(self.listbox)
        self.setLayout(hbox)

        vbox = QVBoxLayout()
        sortlistbox = QPushButton('&Sort')
        self._sortOrder = Qt.AscendingOrder
        connect(sortlistbox, 'clicked()', self._sortListBox)
        vbox.addWidget(sortlistbox)
        vbox.addLayout(buttons)
        vbox.addStretch()

        hbox.addLayout(vbox)

        connect(buttons, "add", self.addPattern)
        connect(buttons, "edit", self.editItem)
        buttons.duplicate.setVisible(False)
        self.listbox.connectToListButtons(buttons)
        self.listbox.editButton = buttons.edit
        connect(self.listbox, 'itemDoubleClicked(QListWidgetItem *)',
                    self._doubleClicked)

    def _sortListBox(self):
        if self._sortOrder == Qt.AscendingOrder:
            self.listbox.sortItems(Qt.DescendingOrder)
            self._sortOrder = Qt.DescendingOrder
        else:
            self.listbox.sortItems(Qt.AscendingOrder)
            self._sortOrder = Qt.AscendingOrder

    def saveSettings(self):
        patterns = [unicode(self.listbox.item(row).text()) for row in xrange(self.listbox.count())]
        cparser = PuddleConfig()
        cparser.setSection('editor', 'patterns', patterns)

    def addPattern(self):
        self.listbox.addItem("")
        row = self.listbox.currentRow()
        self.listbox.setCurrentRow(self.listbox.count() - 1)
        self.listbox.clearSelection()
        self._add = True
        self.editItem(True, row)
        self.listbox.setFocus()

    def _doubleClicked(self, item):
        self.editItem()

    def editItem(self, add = False, row = None):
        if row is None:
            row = self.listbox.currentRow()
        if not add and row < 0:
            return
        l = self.listbox.item
        items = [unicode(l(z).text()) for z in range(self.listbox.count())]
        (text, ok) = QInputDialog().getItem (self, 'puddletag', 'Enter a pattern', items, row)
        if ok:
            item = l(row)
            self.listbox.setItemSelected(item, True)
            item.setText(text)
        else:
            if self._add:
                self.listbox.takeItem(self.listbox.count() - 1)
                self._add = False

    def applySettings(self, control):
        item = self.listbox.item
        patterns = [item(row).text() for row in xrange(self.listbox.count())]
        control.setItems(patterns)

control = ('patterncombo', PatternCombo, False)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = PatternCombo(['keith', 'the', 'grea'])
    win.show()
    app.exec_()