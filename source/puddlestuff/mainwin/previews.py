# -*- coding: utf-8 -*-
from puddlestuff.puddleobjects import PuddleConfig
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from functools import partial
from itertools import izip
from copy import deepcopy

status = {}

_previews = []
_sort_action = None

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
    _previews.append(dict([(f, deepcopy(f.preview)) for f in files]))
    emit('setpreview', [{} for f in files])

def clear_selected_cells():
    files = status['selectedfiles']
    selected = status['selectedtags']

    _previews.append(dict([(f, f.preview) for f in files]))

    ret = []
    for fields, f in izip(selected, files):
        ret.append(dict([(k,v) for k,v in f.preview.iteritems()
            if k not in fields]))
    emit('setpreview', ret)

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
    
    sort = QAction('&Sort Selected', parent)
    obj.connect(sort, SIGNAL('triggered()'), sort_by_fields)

    clear_cells = QAction('Clear Selected &Cells', parent)
    obj.connect(clear_cells, SIGNAL('triggered()'), clear_selected_cells)
    
    cparser = PuddleConfig()
    options = cparser.get('table', 'sortoptions', 
        ['__filename,track,__dirpath','track, album', 
            '__filename,album,__dirpath'])
    global _sort_action
    _sort_action = sort
    sort_actions = set_sort_options(options)

    return [enable_preview, clear_selection, write, revert, sort,
        clear_cells] + sort_actions

def set_sort_options(options):
    parent = _sort_action.parentWidget()
    menu = QMenu(parent)
    sort_actions = []
    options = [[z.strip() for z in option.split(u',')] for option in options]
    for option in options:
        action = QAction(u'/'.join(option), parent)
        action.sortOption = option
        menu.addAction(action)
        obj.connect(action, SIGNAL('triggered()'), sort_by_fields)
        sort_actions.append(action)
    _sort_action.setMenu(menu)
    status['sort_actions'] = sort_actions
    return sort_actions

def sort_by_fields():
    options = QObject().sender().sortOption
    status['table'].model().sortByFields(options, 
        status['selectedfiles'], status['selectedrows'])

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
