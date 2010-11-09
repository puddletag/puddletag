# -*- coding: utf-8 -*-
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import sys, os, traceback

from puddlestuff.puddleobjects import (create_buddy, ListBox,
    ListButtons, load_actions, OKCancel, PuddleConfig)
from puddlestuff.constants import ACTIONDIR
from functools import partial
from findfunc import load_action
import pdb
import puddlestuff.puddletag
from puddlestuff.shortcutsettings import ActionEditorDialog

FILENAME = os.path.join(ACTIONDIR, 'action_shortcuts')

save_shortcuts = lambda: ActionEditorDialog.saveSettings(puddlestuff.puddletag.status['actions'])

NAME = 'name'
FILENAMES = 'filenames'
SHORTCUT_SECTION = 'Shortcut'

def create_action_shortcut(name, funcs, scut_key=None, method=None, parent=None, add=False):
    if not method:
        from puddlestuff.mainwin.funcs import applyaction
        method = applyaction
    if not parent:
        parent = puddlestuff.puddletag.status['mainwin']
    shortcut = QAction(name, parent)

    shortcut.enabled = 'filesselected'
    shortcut.control = None
    shortcut.command = None
    shortcut.togglecheck = None

    parent.connect(shortcut, SIGNAL('triggered()'),
        partial(method, funcs=funcs))

    if add:
        from puddlestuff.puddletag import add_shortcuts
        add_shortcuts('&Actions', [shortcut])
    if scut_key:
        shortcut.setShortcut(scut_key)
        save_shortcuts()
    return shortcut

def create_action_shortcuts(method, parent=None):
    actions, shortcuts = load_settings()
    menu_shortcuts = []
    for name, filenames in shortcuts:
        funcs = []
        try:
            for f in filenames:
                funcs.extend(load_action(f)[0])
        except EnvironmentError:
            traceback.print_exc()
            continue
        shortcut = QAction(name, parent)
        shortcut.enabled = 'filesselected'
        shortcut.control = None
        shortcut.command = None
        shortcut.togglecheck = None
        
        parent.connect(shortcut, SIGNAL('triggered()'),
            partial(method, funcs=funcs))
        menu_shortcuts.append(shortcut)
    return menu_shortcuts

def load_settings(filename=None, actions=None):
    if filename is None:
        filename = FILENAME

    cparser = PuddleConfig(filename)

    if actions is None:
        actions = load_actions()
    else:
        self._actions = actions

    shortcuts = []
    for section in sorted(cparser.sections()):
        if section.startswith(SHORTCUT_SECTION):
            name = cparser.get(section, NAME, 'Default')
            filenames = cparser.get(section, FILENAMES, [])
            shortcuts.append([name, filenames])
    return actions, shortcuts

def save_shortcut(name, filenames):
    cparser = PuddleConfig(FILENAME)
    section = SHORTCUT_SECTION + unicode(len(cparser.sections()))
    cparser.set(section, NAME, name)
    cparser.set(section, FILENAMES, filenames)

class Editor(QDialog):
    def __init__(self, title='Add Action', actions=None, parent=None):
        super(Editor, self).__init__(parent)
        self.setWindowTitle(title)

        self._items = {}

        self._name = QLineEdit('Name')
        
        self._actionList = ListBox()
        self.connect(self._actionList,
            SIGNAL('itemDoubleClicked (QListWidgetItem *)'), self._addAction)
        self._newActionList = ListBox()
        listbuttons = ListButtons()
        listbuttons.duplicate.hide()
        listbuttons.insertStretch(0)
        self.connect(listbuttons, SIGNAL('add'), self._addAction)

        self._newActionList.connectToListButtons(listbuttons)

        okcancel = OKCancel()
        self.connect(okcancel, SIGNAL('ok'), self.okClicked)
        self.connect(okcancel, SIGNAL('cancel'), self.close)

        hbox = QHBoxLayout()
        hbox.addLayout(
            create_buddy('Actions', self._actionList, QVBoxLayout()), 1)
        hbox.addLayout(listbuttons, 0)
        hbox.addLayout(create_buddy('Actions to run for shortcut',
            self._newActionList, QVBoxLayout()), 1)

        layout = QVBoxLayout()
        layout.addLayout(create_buddy('Shortcut Name: ', self._name))
        layout.addLayout(hbox)
        layout.addLayout(okcancel)
        self.setLayout(layout)

        if actions:
            self.setActions(actions)

    def _addAction(self, item=None):
        if item is None:
            for item in self._actionList.selectedItems():
                self._addAction(item)
            return
        new_item = QListWidgetItem(item)
        new_item._action = item._action
        self._newActionList.addItem(new_item)
        self._newActionList.setCurrentItem(new_item,
            QItemSelectionModel.ClearAndSelect)

    def okClicked(self):
        alist = self._newActionList
        items = map(alist.item, xrange(alist.count()))
        actions = [item._action[1] for item in items]
        self.emit(SIGNAL('actionChanged'), unicode(self._name.text()), actions)
        self.close()

    def setActions(self, actions):
        self._actionList.clear()
        self._actions = []
        for funcs, name, filename in actions:
            item = QListWidgetItem(name)
            item.setToolTip(u'\n'.join([func.description() for func in funcs]))
            item._action = [name, filename]
            self._actionList.addItem(item)

    def setName(self, name):
        self._name.setText(name)

    def setAttrs(self, name, actions, filenames):
        names = dict([(z[2], z[1]) for z in actions])
        self.setActions(actions)
        self.setName(name)
        self._newActionList.clear()
        if filenames:
            for filename in filenames:
                item = QListWidgetItem(names[filename])
                item._action = [names[filename], filename]
                self._newActionList.addItem(item)

class ShortcutEditor(QWidget):
    def __init__(self, load=False, parent=None):
        super(ShortcutEditor, self).__init__(parent)
        self._names = []

        self._listbox = ListBox()

        listbuttons = ListButtons()
        listbuttons.insertStretch(0)
        self.connect(listbuttons, SIGNAL('add'), self._addShortcut)
        self.connect(listbuttons, SIGNAL('edit'), self._editShortcut)
        self.connect(listbuttons, SIGNAL('duplicate'), self._duplicate)
        
        self._listbox.connectToListButtons(listbuttons)

        layout = QHBoxLayout()
        layout.addLayout(create_buddy('Shortcuts', self._listbox, QVBoxLayout()))
        layout.addLayout(listbuttons)
        self.setLayout(layout)

        if load:
            self.loadSettings()

    def _addShortcut(self):
        win = Editor('Add Shortcut', self._actions, self)
        win.setModal(True)
        self.connect(win, SIGNAL('actionChanged'), self.addShortcut)
        win.show()

    def addShortcut(self, name, filenames, select=True):
        item = QListWidgetItem(name)
        item.actionName = name
        item.filenames = filenames[::]
        self._listbox.addItem(item)
        if select:
            self._listbox.setCurrentItem(item, QItemSelectionModel.ClearAndSelect)

    def applySettings(self, control):
        from puddlestuff.puddletag import remove_shortcuts, add_shortcuts
        remove_shortcuts('&Actions', self._names)

        f = open(FILENAME, 'w')
        f.close()
        
        cparser = PuddleConfig(FILENAME)
        for i, item in enumerate(self._listbox.items()):
            section = SHORTCUT_SECTION + unicode(i)
            cparser.set(section, NAME, item.actionName)
            cparser.set(section, FILENAMES, item.filenames)

        from puddlestuff.mainwin.funcs import applyaction

        shortcuts = create_action_shortcuts(applyaction, control)
        add_shortcuts('&Actions', shortcuts)

    def _duplicate(self):
        try:
            item = self._listbox.selectedItems()[0]
        except IndexError:
            return
        win = Editor('Duplicate Shortcut', self._actions, self)
        win.setAttrs(item.actionName, self._actions, item.filenames)
        win.setModal(True)
        self.connect(win, SIGNAL('actionChanged'), self.addShortcut)
        win.show()

    def _editShortcut(self):
        try:
            item = self._listbox.selectedItems()[0]
        except IndexError:
            return
        win = Editor('Edit Shortcut', self._actions, self)
        win.setAttrs(item.actionName, self._actions, item.filenames)
        win.setModal(True)
        self.connect(win, SIGNAL('actionChanged'),
            partial(self.editShortcut, item))
        win.show()

    def editShortcut(self, item, name, filenames):
        item.actionName = name
        item.filenames = filenames[::]
        item.setText(name)

    def loadSettings(self, filename=None, actions=None):
        self._names = []

        if filename is None:
            filename = os.path.join(ACTIONDIR, 'action_shortcuts')

        self._listbox.clear()
        cparser = PuddleConfig(filename)

        if actions is None:
            self._actions = load_actions()
        else:
            self._actions = actions

        for section in sorted(cparser.sections()):
            if section.startswith('Shortcut'):
                name = cparser.get(section, NAME, 'Default')
                self._names.append(name)
                filenames = cparser.get(section, FILENAMES, [])
                self.addShortcut(name, filenames, False)

if __name__ == '__main__':
    app = QApplication([])
    actions = load_actions()
    win = ShortcutEditor()
    win.loadSettings()
    win.show()
    app.exec_()
    