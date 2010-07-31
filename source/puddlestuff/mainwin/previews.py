# -*- coding: utf-8 -*-
import puddlestuff.findfunc as findfunc
from puddlestuff.puddleobjects import dircmp, safe_name, natcasecmp, LongInfoMessage
import puddlestuff.actiondlg as actiondlg
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import os, pdb
path = os.path
import puddlestuff.helperwin as helperwin
from functools import partial
from itertools import izip
from puddlestuff.audioinfo import stringtags
from operator import itemgetter
import puddlestuff.musiclib, puddlestuff.about as about
import traceback
from puddlestuff.util import split_by_tag
import puddlestuff.functions as functions

status = {}

def toggle_preview_display(action, value):
    if value:
        action.setText('Disabl&e Preview Mode')
        if not action.isChecked():
            action.blockSignals(True)
            action.setChecked(True)
            action.blockSignals(False)
    else:
        action.setText('Enabl&e Preview Mode')
        if action.isChecked():
            action.blockSignals(True)
            action.setChecked(False)
            action.blockSignals(False)

def toggle_preview_mode(value):
    if value:
        emit('enable_preview_mode')
    else:
        emit('disable_preview_mode')

def clear_selected():
    emit('setpreview', [{} for z in status['selectedrows']])

def create_actions(parent):
    enable_preview = QAction('Enabl&e Preview Mode', parent)
    enable_preview.setCheckable(True)
    enable_preview.setShortcut('Ctrl+Shift+P')
    obj.connect(enable_preview, SIGNAL('toggled(bool)'), toggle_preview_mode)
    obj.receives.append(['previewModeChanged', 
        partial(toggle_preview_display, enable_preview)])
    
    clear_selection = QAction('Clear Selected &Files', parent)
    clear_selection.setShortcut('Ctrl+Shift+F')
    obj.connect(clear_selection, SIGNAL('triggered()'), clear_selected)
    
    return [enable_preview, clear_selection]

def set_status(stat):
    global status
    status = stat

obj = QObject()
obj.emits = ['enable_preview_mode', 'disable_preview_mode', 'setpreview']
obj.receives = []


def emit(sig, *args):
    obj.emit(SIGNAL(sig), *args)
