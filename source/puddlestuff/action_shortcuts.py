# -*- coding: utf-8 -*-
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import sys, os, traceback

from puddlestuff.puddleobjects import (create_buddy, ListBox,
    ListButtons, load_actions, OKCancel, PuddleConfig)
from puddlestuff.constants import ACTIONDIR
from functools import partial
from findfunc import load_macro_info as load_action
import pdb
import puddlestuff.puddletag
from puddlestuff.shortcutsettings import ActionEditorDialog
import puddlestuff.puddleobjects as puddleobjects
from puddlestuff.translations import translate

FILENAME = os.path.join(ACTIONDIR, 'action_shortcuts')

NAME = 'name'
FILENAMES = 'filenames'
SHORTCUT_SECTION = 'Shortcut'

def create_action_shortcut(name, filenames, scut_key=None, method=None, parent=None, add=False):
    
    if not method:
        from puddlestuff.mainwin.funcs import applyaction
        method = applyaction

    if not parent:
        parent = puddlestuff.puddletag.status['mainwin']

    shortcut = Shortcut(name, filenames, method, parent, scut_key)

    if add:
        from puddlestuff.puddletag import add_shortcuts
        add_shortcuts('&Actions', [shortcut], save=bool(scut_key))
    return shortcut

def create_action_shortcuts(method, parent=None):
    actions, shortcuts = load_settings()
    menu_shortcuts = []
    for name, filenames in shortcuts:
        menu_shortcuts.append(Shortcut(name, filenames, method, parent))
    return menu_shortcuts

def get_shortcuts(default=None):
    from puddlestuff.puddletag import status
    if status['actions']:
        ret = filter(None,
            (unicode(z.shortcut().toString()) for z in status['actions']))
    else:
        ret = []
    if default:
        return set(ret + default)
    else:
        return set(ret)

def load_settings(filename=None, actions=None):
    if filename is None:
        filename = FILENAME

    if not os.path.exists(os.path.dirname(filename)):
        os.makedirs(os.path.dirname(filename))

    cparser = PuddleConfig(filename)

    actions = load_actions() if actions is None else actions

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

class Shortcut(QAction):
    def __init__(self, name, filenames, method, parent, shortcut=u''):
        super(Shortcut, self).__init__(name, parent)

        self.enabled = 'filesselected'
        self.control = None
        self.command = None
        self.togglecheck = None
        self._method = method
        
        if shortcut:
            self.setShortcut(shortcut)
        self.filenames = filenames
        self.funcs = self.get_funcs()
        self.connect(self, SIGNAL('triggered()'), self.runAction)

        self._watcher = QFileSystemWatcher(filter(os.path.exists, filenames),
            self)
        self._watcher.connect(self._watcher,
            SIGNAL('fileChanged(const QString&)'), self._checkFile)

    def _checkFile(self, filename):
        #There's some fucked up behaviour going on with QFileSystemWatcher.
        #Without the code here, this method will be called 404 times
        #whenever the file changes. I spent the last hour trying
        #to figure it out and I'm giving up and brute forcing it.

        #Disconnecting and reconnecting doesn't work either.
        #Nor does using blockSignals
        
        self._watcher.disconnect(self._watcher,
            SIGNAL('fileChanged(const QString&)'), self._checkFile)
        filename = filename.toLocal8Bit().data()
        if not os.path.exists(filename):
            self.filenames.remove(filename)
        self.funcs = self.get_funcs()
        self._watcher = QFileSystemWatcher(self.filenames, self)
        self._watcher.connect(self._watcher,
            SIGNAL('fileChanged(const QString&)'), self._checkFile)

    def get_funcs(self, filenames=None):
        if filenames is None:
            filenames = self.filenames
        funcs = []
        for f in filenames:
            if os.path.exists(f):
                funcs.extend(load_action(f)[0])
        return funcs

    def runAction(self):
        return self._method(funcs = self.funcs)
        

class Editor(QDialog):
    def __init__(self, title='Add Action', shortcut=u'', actions=None, names=None, shortcuts=None, parent=None):
        super(Editor, self).__init__(parent)
        self.setWindowTitle(title)

        self._items = {}

        self._name = QLineEdit('Name')
        
        if shortcut and shortcut in shortcuts:
            shortcuts.remove(shortcut)

        self._shortcut = puddleobjects.ShortcutEditor(shortcuts)
        self._shortcut.setText(shortcut)
        clear = QPushButton(translate('Shortcuts', '&Clear'))
        self.connect(clear, SIGNAL('clicked()'), self._shortcut.clear)
        
        if names is None:
            names = []
        self._names = names
        
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
        self._ok = okcancel.ok
        self.connect(self._name, SIGNAL('textChanged(const QString)'), self.enableOk)
        scut_status = QLabel('')
        self.connect(self._shortcut, SIGNAL('validityChanged'),
            lambda v: scut_status.setText(u'') if v or (not self._shortcut.text()) else
                scut_status.setText(translate('Shortcuts', "Invalid shortcut sequence.")))
        okcancel.insertWidget(0, scut_status)

        hbox = QHBoxLayout()
        hbox.addLayout(
            create_buddy('Actions', self._actionList, QVBoxLayout()), 1)
        hbox.addLayout(listbuttons, 0)
        hbox.addLayout(create_buddy('Actions to run for shortcut',
            self._newActionList, QVBoxLayout()), 1)

        layout = QVBoxLayout()
        layout.addLayout(create_buddy('Shortcut &Name: ', self._name))
        scut_layout = create_buddy('&Keyboard Shortcut: ', self._shortcut)
        scut_layout.addWidget(clear)
        layout.addLayout(scut_layout)
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

    def enableOk(self, text):
        if not text or text in self._names:
            self._ok.setEnabled(False)
        else:
            self._ok.setEnabled(True)

    def okClicked(self):
        alist = self._newActionList
        items = map(alist.item, xrange(alist.count()))
        actions = [item._action[1] for item in items]
        self.emit(SIGNAL('actionChanged'), unicode(self._name.text()), actions,
            unicode(self._shortcut.text()) if self._shortcut.valid else u'')
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

    def setAttrs(self, name, actions, filenames, shortcut=u''):
        names = dict([(z[2], z[1]) for z in actions])
        self.setActions(actions)
        self.setName(name)
        self._newActionList.clear()
        self.setShortcut(shortcut)
        if filenames:
            for filename in filenames:
                item = QListWidgetItem(names.get(filename, translate('Shortcuts', '(Deleted)')))
                item._action = [names.get(filename, u''), filename]
                self._newActionList.addItem(item)

    def setShortcut(self, text):
        self._shortcut.setText(text)

class ShortcutEditor(QDialog):
    def __init__(self, load=False, parent=None, buttons=False):
        super(ShortcutEditor, self).__init__(parent)
        self._names = []
        self._hotkeys = []

        self._listbox = ListBox()

        listbuttons = ListButtons()
        listbuttons.insertStretch(0)
        self.connect(listbuttons, SIGNAL('add'), self._addShortcut)
        self.connect(listbuttons, SIGNAL('edit'), self._editShortcut)
        self.connect(listbuttons, SIGNAL('duplicate'), self._duplicate)
        self.connect(self._listbox,
            SIGNAL('itemDoubleClicked (QListWidgetItem *)'), self._editShortcut)
        
        self._listbox.connectToListButtons(listbuttons)

        hbox = QHBoxLayout()
        hbox.addLayout(create_buddy('Shortcuts', self._listbox, QVBoxLayout()))
        hbox.addLayout(listbuttons)

        okcancel = OKCancel()

        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        if buttons:
            vbox.addLayout(okcancel)
        self.setLayout(vbox)

        self.connect(okcancel, SIGNAL('ok'), self.okClicked)
        self.connect(okcancel, SIGNAL('cancel'), self.close)

        if load:
            self.loadSettings()

    def _addShortcut(self):
        shortcuts = get_shortcuts().difference(self._hotkeys).union(
            i.shortcut for i in self._listbox.items() if i.shortcut)
            
        win = Editor('Add Shortcut', u'', self._actions, self.names(), shortcuts, self)
        win.setModal(True)
        self.connect(win, SIGNAL('actionChanged'), self.addShortcut)
        win.show()

    def addShortcut(self, name, filenames, shortcut=u'', select=True):
        item = QListWidgetItem(name)
        item.actionName = name
        item.filenames = filenames[::]
        item.shortcut = shortcut
        self._listbox.addItem(item)
        if select:
            self._listbox.setCurrentItem(item, QItemSelectionModel.ClearAndSelect)

    def applySettings(self, control = None):
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
        for item, shortcut in zip(self._listbox.items(), shortcuts):
            if item.shortcut:
                shortcut.setShortcut(item.shortcut)
        add_shortcuts('&Actions', shortcuts, save=True)

    def okClicked(self):
        self.applySettings()
        self.close()

    def _duplicate(self):
        try:
            item = self._listbox.selectedItems()[0]
        except IndexError:
            return
        shortcuts = get_shortcuts().difference(self._hotkeys).union(
            i.shortcut for i in self._listbox.items() if i.shortcut)
        win = Editor('Duplicate Shortcut', u'', self._actions, self.names(), shortcuts, self)
        win.setAttrs(item.actionName, self._actions, item.filenames, u'')
        win.setModal(True)
        self.connect(win, SIGNAL('actionChanged'), self.addShortcut)
        win.show()

    def _editShortcut(self):
        try:
            item = self._listbox.selectedItems()[0]
        except IndexError:
            return
        shortcuts = get_shortcuts().difference(self._hotkeys).union(
            i.shortcut for i in self._listbox.items() if i.shortcut)

        names = self.names()
        names.remove(item.actionName)
        win = Editor('Edit Shortcut', item.shortcut, self._actions, names, shortcuts, self)
        win.setAttrs(item.actionName, self._actions, item.filenames, item.shortcut)
        win.setModal(True)
        self.connect(win, SIGNAL('actionChanged'),
            partial(self.editShortcut, item))
        win.show()

    def editShortcut(self, item, name, filenames, shortcut):
        item.actionName = name
        item.filenames = filenames[::]
        item.shortcut = shortcut
        item.setText(name)

    def loadSettings(self, filename=None, actions=None):
        self._names = []
        self._hotkeys = []

        if filename is None:
            filename = os.path.join(ACTIONDIR, 'action_shortcuts')

        self._listbox.clear()
        cparser = PuddleConfig(filename)

        if actions is None:
            self._actions = load_actions()
        else:
            self._actions = actions

        from puddlestuff.puddletag import status
        if status['actions']:
            shortcuts = dict((unicode(a.text()), unicode(a.shortcut().toString()))
                for a in status['actions'])
        else:
            shortcuts = {}

        for section in sorted(cparser.sections()):
            if section.startswith('Shortcut'):
                name = cparser.get(section, NAME, 'Default')
                self._names.append(name)
                filenames = cparser.get(section, FILENAMES, [])
                shortcut = shortcuts.get(name, u'')
                self.addShortcut(name, filenames, shortcut, select=False)
                self._hotkeys.append(shortcut)

    def names(self):
        return [item.actionName for item in self._listbox.items()]

if __name__ == '__main__':
    import sys
    app = QApplication([])
    actions = load_actions()
    win = ShortcutEditor(buttons=True)
    win.loadSettings()
    win.show()
    app.exec_()
    