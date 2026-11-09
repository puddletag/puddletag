import os
import sys

from PyQt6.QtCore import QEvent, QLineF, QRectF, Qt, pyqtRemoveInputHook
from PyQt6.QtGui import QBrush, QKeySequence, QPainter, QPalette, QPen
from PyQt6.QtWidgets import QAbstractItemDelegate, QAbstractItemView, QApplication, QFrame, QItemDelegate, QLabel, \
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from . import loadshortcuts as ls
from .constants import CONFIGDIR
from .puddleobjects import PuddleConfig
from .translations import translate

pyqtRemoveInputHook()


class ActionEditorWidget(QLabel):

    def __init__(self, text, parent):

        QLabel.__init__(self, text, parent)
        self.key = ""
        self.modifiers = {}
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setBrush(QPalette.ColorRole.Base, palette.brush(QPalette.ColorRole.AlternateBase))
        self.setPalette(palette)
        self.valid = False
        self.setFrameStyle(QFrame.Shape.Panel)

    def keyPressEvent(self, event):

        other = None

        if event.key() == Qt.Key.Key_Shift:
            self.modifiers[Qt.Key.Key_Shift] = "Shift"
        elif event.key() == Qt.Key.Key_Control:
            self.modifiers[Qt.Key.Key_Control] = "Ctrl"
        elif event.key() == Qt.Key.Key_Meta:
            self.modifiers[Qt.Key.Key_Meta] = "Meta"
        elif event.key() == Qt.Key.Key_Alt:
            self.modifiers[Qt.Key.Key_Alt] = "Alt"
        else:
            other = QKeySequence(event.key()).toString(QKeySequence.SequenceFormat.NativeText)

        if other:
            key_string = "+".join(list(self.modifiers.values()) + [str(other), ])
            self.valid = True
        else:
            key_string = "+".join(list(self.modifiers.values()))

        self.setText(key_string)

    def keyReleaseEvent(self, event):

        if self.valid:
            return

        if event.key() == Qt.Key.Key_Shift:
            if Qt.Key.Key_Shift in self.modifiers:
                del self.modifiers[Qt.Key.Key_Shift]
        elif event.key() == Qt.Key.Key_Control:
            if Qt.Key.Key_Control in self.modifiers:
                del self.modifiers[Qt.Key.Key_Control]
        elif event.key() == Qt.Key.Key_Meta:
            if Qt.Key.Key_Meta in self.modifiers:
                del self.modifiers[Qt.Key.Key_Meta]
        elif event.key() == Qt.Key.Key_Alt:
            if Qt.Key.Key_Alt in self.modifiers:
                del self.modifiers[Qt.Key.Key_Alt]

        self.setText("+".join(list(self.modifiers.values())))

        if len(self.modifiers) == 0:
            self.releaseKeyboard()

    def mousePressEvent(self, event):

        if event.button() != Qt.MouseButton.LeftButton:
            return

        size = self.height() / 2.0
        rect = QRectF(self.width() - size, size * 0.5, size, size)

        if rect.contains(event.position()):
            self.clear()
            self.valid = True
            event.accept()

    def paintEvent(self, event):

        if self.text():
            painter = QPainter()
            painter.begin(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            color = self.palette().color(QPalette.ColorRole.Highlight)
            color.setAlpha(127)
            painter.setBrush(QBrush(color))
            color = self.palette().color(QPalette.ColorRole.HighlightedText)
            color.setAlpha(127)
            painter.setPen(QPen(color))
            size = self.height() / 2.0

            left = self.width() - 4

            painter.drawRect(QRectF(left - size, size * 0.5, size, size))
            painter.drawLine(QLineF(left - size * 0.75, size * 0.75,
                             left - size * 0.25, size * 1.25))
            painter.drawLine(QLineF(left - size * 0.25, size * 0.75,
                             left - size * 0.75, size * 1.25))
            painter.end()

        QLabel.paintEvent(self, event)

    def showEvent(self, event):

        self.grabKeyboard()


class ActionEditorDelegate(QItemDelegate):

    def __init__(self, parent=None):

        QItemDelegate.__init__(self, parent)

    def createEditor(self, parent, option, index):

        self._edited = str(index.data())

        self.editor = ActionEditorWidget(str(index.data()), parent)
        self.editor.installEventFilter(self)
        return self.editor

    def eventFilter(self, obj, event):

        if obj == self.editor:
            if event.type() == QEvent.Type.KeyPress:
                obj.keyPressEvent(event)
                if obj.valid:
                    self.commitData.emit(self.editor)
                    self.closeEditor.emit(self.editor, QAbstractItemDelegate.EndEditHint.NoHint)
                return True

            elif event.type() == QEvent.Type.KeyRelease:
                obj.keyReleaseEvent(event)
                if not obj.text():
                    self.closeEditor.emit(self.editor, QAbstractItemDelegate.EndEditHint.NoHint)
                return True

            elif event.type() == QEvent.Type.MouseButtonPress:
                obj.mousePressEvent(event)
                if obj.valid:
                    self.commitData.emit(self.editor)
                    self.closeEditor.emit(self.editor, QAbstractItemDelegate.EndEditHint.NoHint)
                return True

        return False

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

        editor.setText(str(index.data()))

    def setModelData(self, editor, model, index):
        if editor.text() != self._edited:
            index.model().edited = True
        model.setData(index, editor.text())

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
        self.actionTable.model().edited = False

        self.setWindowTitle(translate("Shortcut Settings", "Edit Shortcuts"))

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

        if column != 1:
            return

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


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # win = ShortcutSettings()
    # win = EditShortcut('Open', 'Ctrl+O')
    widget = QWidget()
    actions = ls.get_actions(widget)
    ActionEditorDialog._loadSettings(actions)
    win = ActionEditorDialog(actions)
    # win.loadSettings(actions)
    win.show()
    app.exec()
