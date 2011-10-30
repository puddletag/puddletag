# -*- coding: utf-8 -*-
from PyQt4.QtCore import *
from PyQt4.QtGui import *

from puddlestuff.plugins import add_shortcuts, status
from puddlestuff.puddleobjects import natcasecmp
from puddlestuff.tagmodel import TableHeader

state = {}

def show_all_fields():
    tb = status['table']
    header = tb.horizontalHeader()
    if state:
        tb.model().setHeader(state['headerdata'])
        tb.setHorizontalHeader(state['header'])
        state.clear()
        return

    files = status['allfiles']
    keys = set()
    for f in files:
        keys = keys.union(f.usertags)

    state['headerdata'] = tb.model().headerdata[:]
    state['header'] = header

    data = map(lambda k: (k, k), sorted(keys, cmp=natcasecmp))
    tb.model().setHeader(data)

def init(parent=None):
    def sep():
        k = QAction(parent)
        k.setSeparator(True)
        return k
    action = QAction('Show all fields', parent)
    action.connect(action, SIGNAL('triggered()'), show_all_fields)
    add_shortcuts('&Plugins', [sep(), action, sep()])