# -*- coding: utf-8 -*-
import os

from PyQt5.QtWidgets import QApplication, QWidget, QCheckBox, QVBoxLayout

from .constants import CONFIGDIR
from .puddleobjects import PuddleConfig
from .translations import translate

NAME = 'name'
DESC = 'description'
SECTION = 'Config'
VALUE = 'value'

_filename = os.path.join(CONFIGDIR, 'confirmations')
_confirmations = {}
_registered = []


def add(name, default=True, desc=None):
    if desc is None:
        desc = name
    if name not in _confirmations:
        _confirmations[name] = [default, desc]
        if name not in _registered:
            _registered.append(name)


def should_show(name):
    return _confirmations[name][0]


def _load(filename):
    cparser = PuddleConfig(filename)
    confirmations = {}
    for section in cparser.sections():
        if section.startswith(SECTION):
            name = cparser.get(section, NAME, '')
            desc = cparser.get(section, DESC, '')
            value = cparser.get(section, VALUE, True)
            confirmations[name] = [value, desc]
    return confirmations


def load():
    # _confirmations.clear()
    _confirmations.update(_load(_filename))


def save(filename=None, confirmations=None):
    if filename is None:
        filename = _filename
    cparser = PuddleConfig(filename)

    if confirmations is None:
        confirmations = _confirmations

    for i, name in enumerate(confirmations):
        set_value = lambda k, v: cparser.set(SECTION + str(i), k, v)
        set_value(NAME, name)
        set_value(VALUE, confirmations[name][0])
        set_value(DESC, confirmations[name][1])


class Settings(QWidget):
    def __init__(self, parent=None):
        super(Settings, self).__init__(parent)
        layout = QVBoxLayout()
        load()
        self._controls = {}
        for name in _registered:
            control = QCheckBox(translate('Confirmations',
                                          _confirmations[name][1]))
            control.setChecked(_confirmations[name][0])
            layout.addWidget(control)
            self._controls[name] = control
        layout.addStretch()
        self.setLayout(layout)

    def applySettings(self, control=None):
        for name, control in self._controls.items():
            _confirmations[name][0] = control.isChecked()
        save()


if __name__ == '__main__':
    app = QApplication([])
    add('First True', True)
    add('Name', False, 'Description')
    print(_confirmations)
    win = Settings()
    win.show()
    app.exec_()
