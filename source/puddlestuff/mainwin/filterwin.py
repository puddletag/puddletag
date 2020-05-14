# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (QWidget, QLabel, QComboBox,
    QLineEdit, QHBoxLayout, QPushButton, QApplication)
from PyQt5.QtCore import QTimer, pyqtSignal
from puddlestuff.puddleobjects import gettaglist, create_buddy, PuddleCombo
from puddlestuff.constants import BOTTOMDOCK
from puddlestuff.translations import translate

class DelayedEdit(QLineEdit):
    delayedText = pyqtSignal(str, name='delayedText')
    def __init__(self, text=None, parent=None):
        if parent is None and text is None:
            QLineEdit.__init__(self)
        elif text is not None and parent is None:
            QLineEdit.__init__(self, text)
        else:
            QLineEdit.__init__(self, text, parent)

        self.__timerslot = None
        self.__timer = QTimer(self)
        self.__timer.setInterval(350)
        self.__timer.setSingleShot(True)
        self.textChanged.connect(self.__time)

    def __time(self, text):
        timer = self.__timer
        timer.stop()
        if self.__timerslot is not None:
            timer.timeout.disconnect(self.__timerslot)
        self.__timerslot = lambda: self.delayedText.emit(text)
        timer.timeout.connect(self.__timerslot)
        timer.start()

class FilterView(QWidget):
    filter = pyqtSignal(unicode, name='filter')
    def __init__(self, parent=None, status=None):
        QWidget.__init__(self, parent)
        self.emits = ['filter']
        self.receives = []
        edit = QLineEdit()
        self.combo = PuddleCombo('filter_text')
        self.combo.setEditText(u'')
        self.combo.combo.setLineEdit(edit)
        hbox = create_buddy(translate("Defaults", "Filter: "), self.combo)
        go_button = QPushButton(translate('Defaults', 'Go'))
        hbox.addWidget(go_button)
        self.setLayout(hbox)

        emit_filter = lambda: self.filter.emit(
            unicode(edit.text()))
        go_button.clicked.connect(emit_filter)
        edit.returnPressed.connect(emit_filter)
        self.combo.combo.activated.connect(
            lambda i: emit_filter())

    def saveSettings(self):
        self.combo.save()


control = ("Filter", FilterView, BOTTOMDOCK, True)