# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (QCheckBox, QLabel, QHBoxLayout, QSpinBox,
                             QVBoxLayout, QWidget)

from .translations import translate


def sanitize(type_, value, default=None):
    if type_ is int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    elif type_ is bool:
        if value is True or value == 'True':
            return True
        else:
            return False
    else:
        return value


class AutoNumbering(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

        def hbox(*widgets):
            box = QHBoxLayout()
            [box.addWidget(z) for z in widgets]
            box.addStretch()
            return box

        vbox = QVBoxLayout()

        startlabel = QLabel(translate('Autonumbering Wizard', "&Start: "))
        self._start = QSpinBox()
        startlabel.setBuddy(self._start)
        self._start.setValue(1)
        self._start.setMaximum(65536)

        vbox.addLayout(hbox(startlabel, self._start))

        label = QLabel(translate('Autonumbering Wizard', 'Max length after padding with zeroes: '))
        self._padlength = QSpinBox()
        label.setBuddy(self._padlength)
        self._padlength.setValue(1)
        self._padlength.setMaximum(65535)
        self._padlength.setMinimum(1)
        vbox.addLayout(hbox(label, self._padlength))

        self._restart_numbering = QCheckBox(translate('Autonumbering Wizard', "&Restart numbering at each directory."))

        vbox.addWidget(self._restart_numbering)
        vbox.addStretch()

        self.setLayout(vbox)

    def setArguments(self, *args):
        minimum = sanitize(int, args[0], 0)
        restart = sanitize(bool, args[1], True)
        padding = sanitize(int, args[2], 1)

        self._start.setValue(minimum)
        self._restart_numbering.setChecked(restart)
        self._padlength.setValue(padding)

    def arguments(self):
        x = [
            self._start.value(),
            self._restart_numbering.isChecked(),
            self._padlength.value()]
        return x


from .functions import autonumbering

dialogs = {autonumbering: AutoNumbering}
