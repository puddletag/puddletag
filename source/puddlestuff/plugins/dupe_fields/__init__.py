# -*- coding: utf-8 -*-
import mutagen, os, cPickle as pickle, sys, traceback

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from puddlestuff.plugins import status, add_shortcuts, connect_control

obj = QObject()

def highlight_dupe_field():
    field, ok = QInputDialog.getText(None, 'puddletag', 'Field to compare')
    if not ok:
        return

    field = unicode(field)
    files = status['selectedfiles']
    if not files or len(files) <= 1:
        return

    highlight = []
    prev = files[0]
    value = prev.get(field)
    
    for f in files[1:]:
        if f.get(field) == value:
            if value is not None:
                if highlight and highlight[-1] != prev:
                    highlight.append(prev)
                elif not highlight:
                    highlight.append(prev)
                highlight.append(f)
        value = f.get(field)
        prev = f
    obj.emit(SIGNAL('highlight'), highlight)
    obj.sender().setChecked(True)

def remove_highlight():
    obj.emit(SIGNAL('highlight'), [])
    obj.sender().setChecked(False)

def init(parent=None):

    def sep():
        k = QAction(parent)
        k.setSeparator(True)
        return k

    action = QAction('Dupe highlight', parent)
    action.setCheckable(True)
    action.connect(action, SIGNAL('toggled(bool)'),
        lambda v: highlight_dupe_field() if v else remove_highlight())
    add_shortcuts('&Plugins', [sep(), action, sep()])

    global obj
    obj.receives = []
    obj.emits = ['highlight']
    connect_control(obj)
    