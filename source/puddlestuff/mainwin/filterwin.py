# -*- coding: utf-8 -*-
from PyQt4.QtGui import (QWidget, QLabel, QComboBox,
    QLineEdit, QHBoxLayout, QPushButton, QApplication)
from PyQt4.QtCore import SIGNAL, QTimer
from puddlestuff.puddleobjects import gettaglist, create_buddy
from puddlestuff.constants import BOTTOMDOCK
from puddlestuff.translations import translate

class DelayedEdit(QLineEdit):
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
        self.connect(self, SIGNAL("textChanged(QString)"), self.__time)

    def __time(self, text):
        timer = self.__timer
        timer.stop()
        if self.__timerslot is not None:
            self.disconnect(timer, SIGNAL('timeout()'), self.__timerslot)
        self.__timerslot = lambda: self.emit(SIGNAL('delayedText'), text)
        self.connect(timer, SIGNAL('timeout()'), self.__timerslot)
        timer.start()

class FilterView(QWidget):
    def __init__(self, parent=None, status=None):
        QWidget.__init__(self, parent)
        self.emits = ['filter']
        self.receives = []
        text = QLineEdit()
        hbox = create_buddy(translate("Defaults", "Filter: "), text)
        go_button = QPushButton(translate('Defaults', 'Go'))
        hbox.addWidget(go_button)
        self.setLayout(hbox)

        emit_filter = lambda: self.emit(SIGNAL('filter'),
            unicode(text.text()))
        self.connect(go_button, SIGNAL('clicked()'), emit_filter)
        self.connect(text, SIGNAL('returnPressed()'), emit_filter)


control = ("Filter", FilterView, BOTTOMDOCK, True)