# -*- coding: utf-8-*-
import sys, pdb, os
from puddlestuff.puddleobjects import PuddleConfig, winsettings, OKCancel
from puddlestuff.constants import CONFIGDIR
import puddlestuff.loadshortcuts as ls
from PyQt4.QtCore import *
from PyQt4.QtGui import *
pyqtRemoveInputHook()
from puddlestuff.translations import translate

from PyQt4.QtCore import QEvent, QRect, QString, Qt, QVariant, SIGNAL
from PyQt4.QtGui import qApp, QBrush, QColor, QDialog, QHBoxLayout, \
    QItemDelegate, QKeySequence, QLabel, QPainter, QPalette, QPen, \
    QPushButton, QStyle, QTableWidget, QTableWidgetItem, QVBoxLayout


class ActionEditorWidget(QLabel):

    # Redefine the tr() function for this class.
    def tr(self, text):
    
        return qApp.translate("ActionEditorWidget", text)

    def __init__(self, text, parent):
    
        QLabel.__init__(self, text, parent)
        self.key = ""
        self.modifiers = {}
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setBrush(palette.Base, palette.brush(palette.AlternateBase))
        self.setPalette(palette)
        self.valid = False
        self.setFrameStyle(QFrame.Panel)
    
    def keyPressEvent(self, event):
    
        other = None
        
        if event.key() == Qt.Key_Shift:
            self.modifiers[Qt.Key_Shift] = u"Shift"
        elif event.key() == Qt.Key_Control:
            self.modifiers[Qt.Key_Control] = u"Ctrl"
        elif event.key() == Qt.Key_Meta:
            self.modifiers[Qt.Key_Meta] = u"Meta"
        elif event.key() == Qt.Key_Alt:
            self.modifiers[Qt.Key_Alt] = u"Alt"
        else:
            other = QString(QKeySequence(event.key()))
        
        if other:
            key_string = u"+".join(self.modifiers.values() + [unicode(other),])
            self.valid = True
        else:
            key_string = u"+".join(self.modifiers.values())
        
        self.setText(key_string)
    
    def keyReleaseEvent(self, event):
    
        if self.valid:
            return
        
        if event.key() == Qt.Key_Shift:
            if self.modifiers.has_key(Qt.Key_Shift):
                del self.modifiers[Qt.Key_Shift]
        elif event.key() == Qt.Key_Control:
            if self.modifiers.has_key(Qt.Key_Control):
                del self.modifiers[Qt.Key_Control]
        elif event.key() == Qt.Key_Meta:
            if self.modifiers.has_key(Qt.Key_Meta):
                del self.modifiers[Qt.Key_Meta]
        elif event.key() == Qt.Key_Alt:
            if self.modifiers.has_key(Qt.Key_Alt):
                del self.modifiers[Qt.Key_Alt]
        
        self.setText(u"+".join(self.modifiers.values()))
        
        if len(self.modifiers) == 0:
            self.releaseKeyboard()
    
    def mousePressEvent(self, event):
    
        if event.button() != Qt.LeftButton:
            return
        
        size = self.height() / 2.0
        rect = QRect(self.width() - size, size * 0.5, size, size)
        
        if rect.contains(event.pos()):
            self.clear()
            self.valid = True
            event.accept()
    
    def paintEvent(self, event):
    
        if not self.text().isEmpty():
        
            painter = QPainter()
            painter.begin(self)
            painter.setRenderHint(QPainter.Antialiasing)
            
            color = self.palette().color(QPalette.Highlight)
            color.setAlpha(127)
            painter.setBrush(QBrush(color))
            color = self.palette().color(QPalette.HighlightedText)
            color.setAlpha(127)
            painter.setPen(QPen(color))
            size = self.height() / 2.0

            left = self.width() - 4
            
            painter.drawRect(left - size, size * 0.5, size, size)
            painter.drawLine(left - size * 0.75, size * 0.75,
                             left - size * 0.25, size * 1.25)
            painter.drawLine(left - size * 0.25, size * 0.75,
                             left - size * 0.75, size * 1.25)
            painter.end()
        
        QLabel.paintEvent(self, event)
    
    def showEvent(self, event):
    
        self.grabKeyboard()


class ActionEditorDelegate(QItemDelegate):

    def __init__(self, parent = None):
    
        QItemDelegate.__init__(self, parent)
    
    def createEditor(self, parent, option, index):

        self._edited = index.data().toString()
    
        self.editor = ActionEditorWidget(index.data().toString(), parent)
        self.editor.installEventFilter(self)
        return self.editor
    
    def eventFilter(self, obj, event):
    
        if obj == self.editor:
            if event.type() == QEvent.KeyPress:
                obj.keyPressEvent(event)
                if obj.valid:
                    self.emit(SIGNAL("commitData(QWidget *)"), self.editor)
                    self.emit(SIGNAL("closeEditor(QWidget *, QAbstractItemDelegate::EndEditHint)"),
                              self.editor, QItemDelegate.NoHint)
                return True
            
            elif event.type() == QEvent.KeyRelease:
                obj.keyReleaseEvent(event)
                if obj.text().isEmpty():
                    self.emit(SIGNAL("closeEditor(QWidget *, QAbstractItemDelegate::EndEditHint)"),
                              self.editor, QItemDelegate.NoHint)
                return True
            
            elif event.type() == QEvent.MouseButtonPress:
                obj.mousePressEvent(event)
                if obj.valid:
                    self.emit(SIGNAL("commitData(QWidget *)"), self.editor)
                    self.emit(SIGNAL("closeEditor(QWidget *, QAbstractItemDelegate::EndEditHint)"),
                              self.editor, QItemDelegate.NoHint)
                return True
        
        return False
    
    def paint(self, painter, option, index):
    
        if index.column() != 0:
            QItemDelegate.paint(self, painter, option, index)
            return
        
        painter.fillRect(option.rect, option.palette.brush(QPalette.Base))
        painter.setPen(QPen(option.palette.color(QPalette.Text)))
        painter.drawText(option.rect.adjusted(4, 4, -4, -4),
            Qt.TextShowMnemonic | Qt.AlignLeft | Qt.AlignVCenter,
            index.data().toString())
    
    def setEditorData(self, editor, index):
    
        editor.setText(index.data().toString())
    
    def setModelData(self, editor, model, index):
        if editor.text() != self._edited:
            index.model().edited = True
        model.setData(index, QVariant(editor.text()))
    
    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class ActionEditorDialog(QWidget):

    # Redefine the tr() function for this class.
    def tr(self, text):
    
        return qApp.translate("ActionEditorDialog", text)

    def __init__(self, actions, parent=None):
    
        super(ActionEditorDialog, self).__init__(parent)
        self.actions = actions

        help = QLabel(translate("Shortcut Settings", '<b>Double click a cell in the Shortcut Column' \
            ' to <br />modify the key sequence.</b>'))
        
        self.actionTable = QTableWidget(self)
        self.actionTable.setSelectionBehavior(QTableWidget.SelectRows)
        self.actionTable.setEditTriggers(QTableWidget.DoubleClicked)
        self.actionTable.setColumnCount(2)
        self.actionTable.setHorizontalHeaderLabels(
            [translate("Shortcut Settings", "Description"),
            translate("Shortcut Settings", "Shortcut")]
            )
        self.actionTable.horizontalHeader().setStretchLastSection(True)
        self.actionTable.verticalHeader().hide()
        self.actionTable.setItemDelegate(ActionEditorDelegate(self))
        
        self.connect(self.actionTable, SIGNAL("cellChanged(int, int)"),
                     self.validateAction)
        
        row = 0
        for action in self.actions:
        
            if action.text().isEmpty():
                continue
            
            self.actionTable.insertRow(self.actionTable.rowCount())
            
            item = QTableWidgetItem()
            item.setText(action.text())
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.actionTable.setItem(row, 0, item)
            
            item = QTableWidgetItem()
            item.setText(action.shortcut().toString())
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable)
            item.oldShortcutText = item.text()
            self.actionTable.setItem(row, 1, item)
            
            row += 1
        
        self.actionTable.resizeColumnsToContents()
                
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(help)
        mainLayout.setMargin(8)
        mainLayout.setSpacing(8)
        mainLayout.addWidget(self.actionTable)
        self.setLayout(mainLayout)
        self._model = self.actionTable.model()
        self._model.edited = False
        self.actionTable.model().edited = False
        
        self.setWindowTitle(translate("Shortcut Settings", "Edit Shortcuts"))
    
    def applySettings(self, control=None):
        if not self._model.edited:
            return
    
        row = 0
        for action in self.actions:
        
            if not action.text().isEmpty():
                action.setText(self.actionTable.item(row, 0).text())
                action.setShortcut(QKeySequence(self.actionTable.item(row, 1).text()))
                row += 1
        self.saveSettings(self.actions)
        self._model.edited = False
    
    def _loadSettings(self, actions):
        
        cparser = PuddleConfig(os.path.join(CONFIGDIR, 'user_shortcuts'))

        for action in actions:
            shortcut = cparser.get('shortcuts', unicode(action.text()), '')
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
    
    _loadSettings = classmethod(_loadSettings)
    
    def saveSettings(self, actions):
        
        cparser = PuddleConfig(os.path.join(CONFIGDIR, 'user_shortcuts'))
        for action in actions:
            shortcut = unicode(action.shortcut().toString())
            cparser.set('shortcuts', unicode(action.text()), shortcut)
    
    saveSettings = classmethod(saveSettings)
    
    def validateAction(self, row, column):
    
        if column != 1:
            return
        
        item = self.actionTable.item(row, column)
        shortcutText = QKeySequence(item.text()).toString()
        thisRow = self.actionTable.row(item)
        
        if not shortcutText.isEmpty():
            for row in range(self.actionTable.rowCount()):
                if row == thisRow:
                    continue
                
                other = self.actionTable.item(row, 1)
                
                if other.text() == shortcutText:
                    other.setText(item.oldShortcutText)
                    break
            
            item.setText(shortcutText)
            item.oldShortcutText = shortcutText
        
        self.actionTable.resizeColumnToContents(1)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    #win = ShortcutSettings()
    #win = EditShortcut('Open', 'Ctrl+O')
    widget = QWidget()
    actions = ls.get_actions(widget)
    ActionEditorDialog._loadSettings(actions)
    win = ActionEditorDialog(actions)
    #win.loadSettings(actions)
    win.show()
    app.exec_()