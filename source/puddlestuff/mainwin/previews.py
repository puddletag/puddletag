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

_previews = []

ENABLED = u'Enabl&e Preview Mode'
DISABLED = u'Disabl&e Preview Mode'

def toggle_preview_display(action, value):
    if value:
        action.setText(DISABLED)
    else:
        action.setText(ENABLED)
        global _previews
        _previews = []

def toggle_preview_mode():
    action = QObject().sender()
    if action.text() == ENABLED:
        emit('enable_preview_mode')
    else:
        emit('disable_preview_mode')

def clear_selected():
    files = status['selectedfiles']
    _previews.append(dict([(f, f.preview) for f in files]))
    emit('setpreview', [{} for f in files])

def create_actions(parent):
    enable_preview = QAction(ENABLED, parent)
    enable_preview.setShortcut('Ctrl+Shift+P')
    obj.connect(enable_preview, SIGNAL('triggered()'), toggle_preview_mode)
    obj.receives.append(['previewModeChanged', 
        partial(toggle_preview_display, enable_preview)])
    
    clear_selection = QAction('Clear Selected &Files', parent)
    clear_selection.setShortcut('Ctrl+Shift+F')
    obj.connect(clear_selection, SIGNAL('triggered()'), clear_selected)
    
    write = QAction('&Write Previews', parent)
    write.setShortcut('Ctrl+W')
    
    obj.connect(write, SIGNAL('triggered()'), lambda: emit('writepreview'))
    
    revert = QAction('&Undo Last Clear', parent)
    revert.setShortcut('Ctrl+Shift+Z')
    obj.connect(revert, SIGNAL('triggered()'), undo_last)
    
    return [enable_preview, clear_selection, write, revert]

def set_status(stat):
    global status
    status = stat

def undo_last():
    if _previews:
        emit('setpreview', _previews.pop())

obj = QObject()
obj.emits = ['enable_preview_mode', 'disable_preview_mode', 'setpreview',
    'writepreview']
obj.receives = []


def emit(sig, *args):
    obj.emit(SIGNAL(sig), *args)
