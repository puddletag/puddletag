from PyQt5.QtCore import QMutex
from PyQt5.QtGui import QTextOption
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout, QWidget

from ..constants import RIGHTDOCK
from ..translations import translate

mutex = QMutex()


class LogDialog(QWidget):
    def __init__(self, parent=None, status=None):
        QWidget.__init__(self, parent)
        self.emits = []
        self.receives = [('logappend', self.appendText)]

        self._text = QTextEdit()
        self._text.setWordWrapMode(QTextOption.NoWrap)

        copy = QPushButton(translate("Logs", '&Copy'))
        clear = QPushButton(translate("Logs", '&Clear'))

        copy.clicked.connect(self._copy)
        clear.clicked.connect(self._clear)

        vbox = QVBoxLayout()
        vbox.addWidget(self._text)

        hbox = QHBoxLayout()
        hbox.addStretch()
        hbox.addWidget(copy)
        hbox.addWidget(clear)

        vbox.addLayout(hbox)
        self.setLayout(vbox)

    def appendText(self, text):
        self._text.append(text)

    def _clear(self):
        self._text.setPlainText('')

    def _copy(self):
        text = self._text.toPlainText()
        QApplication.clipboard().setText(text)

    def setText(self, text, html=True):
        if html:
            self._text.setHtml(text)
        else:
            self._text.setPlaintext(text)


control = ('Logs', LogDialog, RIGHTDOCK, False)

if __name__ == '__main__':
    app = QApplication([])
    win = LogDialog()
    win.show()
    app.exec_()
