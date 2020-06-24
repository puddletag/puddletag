import sys

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QApplication, QComboBox, QFrame, QHBoxLayout, QInputDialog, QPushButton, \
    QShortcut, QVBoxLayout

from ..puddleobjects import (PuddleConfig, ListBox,
                             ListButtons)
from ..translations import translate


def load_patterns(filepath=None):
    settings = PuddleConfig(filepath)
    return [settings.get('editor', 'patterns',
                         ['%artist% - $num(%track%,2) - %title%',
                          '%artist% - %album% - $num(%track%,2) - %title%',
                          '%artist% - %title%', '%artist% - %album%',
                          '%artist% - Track %track%', '%artist% - %title%']),
            settings.get('editor', 'index', 0, True)]


class PatternCombo(QComboBox):
    name = 'toolbar-patterncombo'
    patternchanged = pyqtSignal(str, name='patternchanged')

    def __init__(self, items=None, parent=None, status=None):
        self.emits = ['patternchanged']
        self.receives = [('patterns', self.setItems)]
        self.settingsdialog = SettingsWin
        QComboBox.__init__(self, parent)
        self._status = status
        status['patterns'] = self.items
        status['patterntext'] = lambda: str(self.currentText())

        self.setEditable(True)
        if items:
            self.addItems(items)
        pchange = lambda text: self.patternchanged.emit(str(text))
        self.editTextChanged.connect(pchange)

        shortcut = QShortcut(self)
        shortcut.setKey('F8')
        shortcut.setContext(Qt.ApplicationShortcut)

        def set_focus():
            if self.hasFocus():
                status['table'].setFocus()
            else:
                self.lineEdit().selectAll()
                self.setFocus()

        shortcut.activated.connect(set_focus)

    def setItems(self, texts):
        self.clear()
        self.addItems(texts)

    def items(self):
        text = self.itemText
        return [str(text(i)) for i in range(self.count())]

    def loadSettings(self):
        patterns, index = load_patterns()
        self.setItems(patterns)
        self.setCurrentIndex(index)

    def saveSettings(self):
        settings = PuddleConfig()
        settings.set('editor', 'patterns', list(self.items()))
        settings.set('editor', 'index', self.currentIndex())


class SettingsWin(QFrame):
    def __init__(self, parent=None, cenwid=None, status=None):
        QFrame.__init__(self, parent)
        self.title = translate('Settings', "Patterns")
        connect = lambda c, signal, s: getattr(c, signal).connect(s)
        self.setFrameStyle(QFrame.Box)
        self.listbox = ListBox()
        self.listbox.setSelectionMode(self.listbox.ExtendedSelection)
        buttons = ListButtons()

        self.listbox.addItems(status['patterns'])
        hbox = QHBoxLayout()
        hbox.addWidget(self.listbox)
        self.setLayout(hbox)

        vbox = QVBoxLayout()
        sortlistbox = QPushButton(translate("Pattern Settings", '&Sort'))
        self._sortOrder = Qt.AscendingOrder
        connect(sortlistbox, 'clicked', self._sortListBox)
        vbox.addWidget(sortlistbox)
        vbox.addLayout(buttons)
        vbox.addStretch()

        hbox.addLayout(vbox)

        connect(buttons, "add", self.addPattern)
        connect(buttons, "edit", self.editItem)
        buttons.duplicateButton.setVisible(False)
        self.listbox.connectToListButtons(buttons)
        self.listbox.editButton = buttons.editButton
        connect(self.listbox, 'itemDoubleClicked', self._doubleClicked)

    def _sortListBox(self):
        if self._sortOrder == Qt.AscendingOrder:
            self.listbox.sortItems(Qt.DescendingOrder)
            self._sortOrder = Qt.DescendingOrder
        else:
            self.listbox.sortItems(Qt.AscendingOrder)
            self._sortOrder = Qt.AscendingOrder

    def saveSettings(self):
        patterns = [str(self.listbox.item(row).text()) for row in range(self.listbox.count())]
        cparser = PuddleConfig()
        cparser.setSection('editor', 'patterns', patterns)

    def addPattern(self):
        l = self.listbox.item
        patterns = [str(l(z).text()) for z in range(self.listbox.count())]
        row = self.listbox.currentRow()
        if row < 0:
            row = 0
        (text, ok) = QInputDialog().getItem(self, 'puddletag',
                                            translate("Pattern Settings", 'Enter a pattern'), patterns, row)
        if ok:
            self.listbox.clearSelection()
            self.listbox.addItem(text)
            self.listbox.setCurrentRow(self.listbox.count() - 1)

    def _doubleClicked(self, item):
        self.editItem()

    def editItem(self, row=None):
        if row is None:
            row = self.listbox.currentRow()
        l = self.listbox.item
        patterns = [str(l(z).text()) for z in range(self.listbox.count())]
        (text, ok) = QInputDialog().getItem(self, 'puddletag',
                                            translate("Pattern Settings", 'Enter a pattern'),
                                            patterns, row)
        if ok:
            item = l(row)
            item.setText(text)
            item.setSelected(True)

    def applySettings(self, control):
        item = self.listbox.item
        patterns = [item(row).text() for row in range(self.listbox.count())]
        control.setItems(patterns)


control = ('patterncombo', PatternCombo, False)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = PatternCombo(['one', 'the', 'three'])
    win.show()
    app.exec_()
