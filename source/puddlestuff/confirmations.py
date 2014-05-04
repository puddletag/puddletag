# -*- coding: utf-8 -*-
from puddlestuff.constants import CONFIGDIR
from puddlestuff.puddleobjects import PuddleConfig
from puddlestuff.translations import translate
import os

from PyQt4.QtGui import QApplication, QWidget, QCheckBox, QVBoxLayout

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
            name = cparser.get(section, NAME, u'')
            desc = cparser.get(section, DESC, u'')
            value = cparser.get(section, VALUE, True)
            confirmations[name] = [value, desc]
    return confirmations

def load():
    #_confirmations.clear()
    _confirmations.update(_load(_filename))

def save(filename=None, confirmations=None):
    if filename is None:
        filename = _filename
    cparser = PuddleConfig(filename)
    
    if confirmations is None:
        confirmations = _confirmations
    
    for i, name in enumerate(confirmations):
        set_value = lambda k,v: cparser.set(SECTION + unicode(i), k, v)
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
        for name, control in self._controls.iteritems():
            _confirmations[name][0] = control.isChecked()
        save()

if __name__ == '__main__':
    app = QApplication([])
    add('First True', True)
    add('Name', False, 'Description')
    print _confirmations
    win = Settings()
    win.show()
    app.exec_()