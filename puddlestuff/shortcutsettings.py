import os

from PyQt6.QtCore import QEvent, Qt, pyqtRemoveInputHook
from PyQt6.QtGui import QAction, QKeySequence, QPalette, QPen
from PyQt6.QtWidgets import QAbstractItemDelegate, QAbstractItemView, QItemDelegate, QKeySequenceEdit, QLabel, \
    QLineEdit, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from .constants import CONFIGDIR
from .puddleobjects import HeldModifiers, MODIFIERS, PuddleConfig
from .translations import translate

pyqtRemoveInputHook()


class KeyCell(HeldModifiers, QKeySequenceEdit):
    """The Shortcut column's editor: one key, the modifiers held shown in the order pressed."""
    press_order = True

    def __init__(self, parent):
        super().__init__(parent)
        self.setMaximumSequenceLength(1)
        self.setFinishingKeyCombinations([])  # Tab and Esc are keys here
        self.setClearButtonEnabled(True)
        self.findChild(QLineEdit).setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.typed = self.done = False


class ActionEditorDelegate(QItemDelegate):

    def __init__(self, parent=None):

        QItemDelegate.__init__(self, parent)

    def createEditor(self, parent, option, index):

        editor = KeyCell(parent)
        editor.editingFinished.connect(lambda: self._finish(editor))
        clear = editor.findChild(QAction, '_q_qlineeditclearaction')
        assert clear is not None, "Qt's clear button has no action of that name"
        clear.triggered.connect(lambda: self._clear(editor))
        return editor

    def _end(self, editor, commit):
        # Once only: the focus lost after closing would finish the editing again.
        if editor.done:
            return
        editor.done = True
        if commit:
            self.commitData.emit(editor)
        self.closeEditor.emit(editor, QAbstractItemDelegate.EndEditHint.NoHint)

    def _finish(self, editor):
        if editor.typed and not editor.keySequence().isEmpty():
            self._end(editor, True)

    def _clear(self, editor):
        editor.typed = True
        self._end(editor, True)

    def eventFilter(self, editor, event):
        kind = event.type()
        if kind == QEvent.Type.ShortcutOverride:
            # Not accepted: the window's own keys (F8) run instead of being typed.
            return True
        if kind == QEvent.Type.KeyPress:
            if event.key() not in MODIFIERS:
                editor.typed = True
            return False
        if kind == QEvent.Type.KeyRelease:
            own = MODIFIERS.get(event.key(), Qt.KeyboardModifier.NoModifier)
            if not editor.typed and not (event.modifiers() & ~own):
                self._end(editor, False)  # a modifier alone, or a key the window ran (F8), changes nothing
                return True
            return False
        return QItemDelegate.eventFilter(self, editor, event)

    def paint(self, painter, option, index):

        if index.column() != 0:
            QItemDelegate.paint(self, painter, option, index)
            return

        painter.fillRect(option.rect, option.palette.brush(QPalette.ColorRole.Base))
        painter.setPen(QPen(option.palette.color(QPalette.ColorRole.Text)))
        painter.drawText(option.rect.adjusted(4, 4, -4, -4),
                         Qt.TextFlag.TextShowMnemonic | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         str(index.data()))

    def setEditorData(self, editor, index):

        # Shows every key of the command; the sequence stays empty until one is typed.
        editor.findChild(QLineEdit).setText(str(index.data()))

    def setModelData(self, editor, model, index):
        if not editor.typed:
            return
        text = editor.keySequence().toString()
        if text != str(index.data()):
            index.model().edited = True
        model.setData(index, text)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class ActionEditorDialog(QWidget):

    def __init__(self, actions, parent=None):

        super(ActionEditorDialog, self).__init__(parent)
        self.actions = actions
        self._rows = [action for action in actions if action.text()]
        self._keys = [[key.toString() for key in action.shortcuts()] for action in self._rows]

        help = QLabel(translate("Shortcut Settings", '<b>Double click a cell in the Shortcut Column'
                                                     ' to <br />modify the key sequence.</b>'))

        self.actionTable = QTableWidget(self)
        self.actionTable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.actionTable.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.actionTable.setColumnCount(2)
        self.actionTable.setHorizontalHeaderLabels(
            [translate("Shortcut Settings", "Description"),
             translate("Shortcut Settings", "Shortcut")]
        )
        self.actionTable.horizontalHeader().setStretchLastSection(True)
        self.actionTable.verticalHeader().hide()
        self.actionTable.setItemDelegate(ActionEditorDelegate(self))

        for row, action in enumerate(self._rows):
            self.actionTable.insertRow(self.actionTable.rowCount())

            item = QTableWidgetItem()
            item.setText(action.text())
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.actionTable.setItem(row, 0, item)

            item = QTableWidgetItem()
            item.setText(QKeySequence.listToString(action.shortcuts()))
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsSelectable)
            self.actionTable.setItem(row, 1, item)

        self.actionTable.resizeColumnsToContents()
        self.actionTable.cellChanged.connect(self.validateAction)

        self._notice = QLabel()

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(help)
        mainLayout.setContentsMargins(8, 8, 8, 8)
        mainLayout.setSpacing(8)
        mainLayout.addWidget(self.actionTable)
        mainLayout.addWidget(self._notice)
        self.setLayout(mainLayout)
        self._model = self.actionTable.model()
        self._model.edited = False

    def applySettings(self, control=None):
        if not self._model.edited:
            return

        # self.actions is the live list: a command added while this page is open has no row.
        for row, action in enumerate(self._rows):
            if action not in self.actions:
                continue
            action.setText(self.actionTable.item(row, 0).text())
            if self._keys[row] != [key.toString() for key in action.shortcuts()]:
                action.setShortcuts([QKeySequence(key) for key in self._keys[row]])
        self.saveSettings(self.actions)
        self._model.edited = False

    def _loadSettings(self, actions):

        cparser = PuddleConfig(os.path.join(CONFIGDIR, 'user_shortcuts'))

        for action in actions:
            shortcut = cparser.get('shortcuts', str(action.text()), None)
            if shortcut is not None:
                keys = [key for key in QKeySequence.listFromString(shortcut) if not key.isEmpty()]
                action.setShortcuts(keys)

    _loadSettings = classmethod(_loadSettings)

    def saveSettings(self, actions):

        cparser = PuddleConfig(os.path.join(CONFIGDIR, 'user_shortcuts'))
        section = cparser.data['shortcuts']
        for action in actions:
            section[str(action.text())] = QKeySequence.listToString(action.shortcuts())
        cparser.save()

    saveSettings = classmethod(saveSettings)

    def validateAction(self, row, column):
        item = self.actionTable.item(row, column)
        key = QKeySequence(item.text()).toString()
        self._keys[row] = [key] if key else []
        self._notice.setText('')

        if key:
            for other, keys in enumerate(self._keys):
                if other == row or key not in keys:
                    continue
                keys.remove(key)
                self._setCell(other)
                self._notice.setText(translate("Shortcut Settings", "{key} moved from {old} to {new}.").format(
                    key=key, old=self._rows[other].text().replace('&', ''),
                    new=self._rows[row].text().replace('&', '')))

        self._setCell(row)
        self.actionTable.resizeColumnToContents(1)

    def _setCell(self, row):
        """Shows the row's keys in its cell without calling validateAction."""
        keys = QKeySequence.listToString([QKeySequence(key) for key in self._keys[row]])
        blocked = self.actionTable.blockSignals(True)
        self.actionTable.item(row, 1).setText(keys)
        self.actionTable.blockSignals(blocked)
