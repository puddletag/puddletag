from functools import partial

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QAction, QMenu

from ..puddleobjects import PuddleConfig

from copy import deepcopy
from ..constants import FILESSELECTED
from ..plugins import connect_shortcut
from ..translations import translate

status = {}

_previews = []
_sort_action = None

ENABLED = translate("Menus", 'Enabl&e Preview Mode')
DISABLED = translate("Menus", 'Disabl&e Preview Mode')


class PreviewAction(QAction):
    def setEnabled(self, value):
        if status['previewmode'] and value:
            super(PreviewAction, self).setEnabled(True)
        else:
            super(PreviewAction, self).setEnabled(False)


def toggle_preview_display(action, preview_actions, value):
    if value:
        action.setText(DISABLED)
        files = status['selectedfiles']
        for p in preview_actions:
            if files:
                p.setEnabled(True)
    else:
        action.setText(ENABLED)
        global _previews
        _previews = []
        for p in preview_actions:
            p.setEnabled(False)


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
    for fields, f in zip(selected, files):
        ret.append(dict([(k, v) for k, v in f.preview.items()
                         if k not in fields]))
    emit('setpreview', ret)


def create_actions(parent):
    enable_preview = QAction('Enabl&e Preview Mode', parent)
    enable_preview.setShortcut('Ctrl+Shift+P')
    enable_preview.triggered.connect(toggle_preview_mode)

    clear_selection = PreviewAction('Clear Selected &Files', parent)
    clear_selection.setShortcut('Ctrl+Shift+F')
    clear_selection.triggered.connect(clear_selected)

    write = PreviewAction('&Write Previews', parent)
    write.setShortcut('Ctrl+W')

    write.triggered.connect(lambda: emit('writepreview'))

    revert = PreviewAction('&Undo Last Clear', parent)
    revert.setShortcut('Ctrl+Shift+Z')
    revert.triggered.connect(undo_last)

    sort = QAction('Sort &By', parent)
    sort.triggered.connect(sort_by_fields)

    clear_cells = PreviewAction('Clear Selected &Cells', parent)
    clear_cells.triggered.connect(clear_selected_cells)

    cparser = PuddleConfig()
    options = cparser.get('table', 'sortoptions',
                          ['__filename,track,__dirpath', 'track, album',
                           '__filename,album,__dirpath'])
    global _sort_action
    _sort_action = sort
    sort_actions = set_sort_options(options)

    preview_actions = [clear_selection, write, revert, clear_cells]

    toggle = partial(toggle_preview_display, enable_preview, preview_actions)

    obj.receives.append(['previewModeChanged', toggle])

    [connect_shortcut(z, FILESSELECTED) for z in preview_actions]

    return [enable_preview, clear_selection, write, revert, sort,
            clear_cells] + sort_actions


def set_sort_options(options):
    parent = _sort_action.parentWidget()
    menu = QMenu(parent)
    sort_actions = []
    options = [[z.strip() for z in option.split(',')] for option in options]
    for option in options:
        action = QAction('/'.join(option), parent)
        action.sortOption = option
        menu.addAction(action)
        action.triggered.connect(sort_by_fields)
        sort_actions.append(action)
    _sort_action.setMenu(menu)
    status['sort_actions'] = sort_actions
    return sort_actions


def sort_by_fields():
    options = QObject().sender().sortOption
    files = status['selectedfiles']
    model = status['table'].model()
    if files and len(files) > 1:
        model.sortByFields(options,
                           status['selectedfiles'], status['selectedrows'])
    else:
        model.sortByFields(options)


def set_status(stat):
    global status
    status = stat


def undo_last():
    if _previews:
        emit('setpreview', _previews.pop())


class _SignalObject(QObject):
    enable_preview_mode = pyqtSignal(name='enable_preview_mode')
    disable_preview_mode = pyqtSignal(name='disable_preview_mode')
    setpreview = pyqtSignal(object, name='setpreview')
    writepreview = pyqtSignal(name='writepreview')


obj = _SignalObject()
obj.emits = ['enable_preview_mode', 'disable_preview_mode', 'setpreview',
             'writepreview']
obj.receives = []


def emit(sig, *args):
    getattr(obj, sig).emit(*args)
