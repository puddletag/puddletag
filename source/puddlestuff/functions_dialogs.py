# -*- coding: utf-8 -*-
from PyQt4.QtGui import (QCheckBox, QLabel, QHBoxLayout, QSpinBox,
    QVBoxLayout, QWidget)
from PyQt4.QtCore import SIGNAL

class AutoNumbering(QWidget):
    def __init__(self, parent = None):
        QWidget.__init__(self, parent)

        def hbox(*widgets):
            box = QHBoxLayout()
            [box.addWidget(z) for z in widgets]
            box.addStretch()
            return box

        vbox = QVBoxLayout()

        startlabel = QLabel("&Start: ")
        self._start = QSpinBox()
        startlabel.setBuddy(self._start)
        self._start.setValue(1)
        self._start.setMaximum(65536)

        vbox.addLayout(hbox(startlabel, self._start))

        label = QLabel('Max length after padding with zeroes: ')
        self._padlength = QSpinBox()
        label.setBuddy(self._padlength)
        self._padlength.setValue(1)
        self._padlength.setMaximum(65535)
        self._padlength.setMinimum(1)
        vbox.addLayout(hbox(label, self._padlength))

        self._restart_numbering = QCheckBox("&Restart numbering at each directory.")

        vbox.addWidget(self._restart_numbering)
        vbox.addStretch()

        self.setLayout(vbox)
        

    def setArguments(self, *args):
        minimum = args[0]
        restart = args[1]
        padding = args[2]

        self._start.setValue(minimum)
        self._restart_numbering.setChecked(restart)
        self._padlength.setValue(padding)

    def arguments(self):
        x = [self._start.value(),
                self._restart_numbering.isChecked(),
                self._padlength.value()]
        return x

from functions import autonumbering

dialogs = {autonumbering: AutoNumbering}