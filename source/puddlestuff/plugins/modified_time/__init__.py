# -*- coding: utf-8 -*-
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from puddlestuff.plugins import add_shortcuts, status
from datetime import timedelta, datetime
import time
import os
from puddelstuff.audioinfo import lngtime

def init(parent=None):
    action = QAction('Add 2 seconds to modified time', parent)
    action.connect(action, SIGNAL('triggered()'), add_seconds)
    action.setShortcut('Ctrl+M')
    
    def sep():
        k = QAction(parent)
        k.setSeparator(True)
        return k
    add_shortcuts('&Plugins', [sep(), action, sep()])

def add_seconds():
    files = status['selectedfiles']
    for f in files:
        modified_time = lngtime(f['__modified'])
        modified_time = datetime.fromtimestamp(modified_time) + timedelta(seconds=2)
        accessed_time = lngtime(f['__accessed'])
        os.utime(f.filepath, (accessed_time, time.mktime(modified_time.timetuple())))