from puddleobjects import PuddleConfig
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import sys, pdb, resource,os

SEPARATOR = 'separator'
ALWAYS = 'always'

def get_menus(section, filepath=None):
    cparser = PuddleConfig()
    if not filepath:
        filepath = os.path.join(cparser.savedir, 'menus')
    cparser.filename = filepath
    menus = []
    settings = cparser.settings
    temp = settings[section]
    menus = [(z, temp[z]) for z in settings[section + 'attrs']['order']]
    return menus

def menubar(menus, actions):
    texts = [unicode(action.text()) for action in actions]
    menubar = QMenuBar()
    for title, actionlist in menus:
        menu = menubar.addMenu(title)
        for action in actionlist:
            if action in texts:
                menu.addAction(actions[texts.index(action)])
            elif action == SEPARATOR:
                menu.addSeparator()
    return menubar

def context_menu(section, actions, filepath=None):
    cparser = PuddleConfig(filepath)
    if not filepath:
        filepath = os.path.join(cparser.savedir, 'menus')
        cparser.filename = filepath
    order = cparser.get(section, 'order', [])
    if not order:
        return
    texts = [unicode(action.text()) for action in actions]
    menu = QMenu()
    for action in order:
        if action in texts:
            menu.addAction(actions[texts.index(action)])
        elif action == SEPARATOR:
            menu.addSeparator()
    return menu

def toolbar(groups, actions, controls=None):
    texts = [unicode(action.text()) for action in actions]
    if controls:
        controls = dict([('widget-' + z, v) for z,v in controls.items()])
    toolbars = []
    for name, actionlist in groups:
        toolbar = QToolBar(name)
        toolbar.setObjectName(name)
        for action in actionlist:
            if action in texts:
                toolbar.addAction(actions[texts.index(action)])
            elif action in controls:
                toolbar.addWidget(controls[action])
        toolbars.append(toolbar)
    return toolbars

def create_action(win, name, control, command, icon = None, enabled=ALWAYS,
                    tooltip=None, shortcut=None, checked=None, status=None):
    if icon:
        action = QAction(QIcon(icon), name, win)
    else:
        action = QAction(name, win)
    action.setEnabled(False)

    if shortcut:
        action.setShortcut(shortcut)

    if tooltip:
        action.setToolTip(tooltip)

    if checked:
        action.setCheckState(True)

    action.enabled = enabled
    action.command = command
    action.control = control
    action.status = status

    return action

def get_actions(parent, filepath=None):
    cparser = PuddleConfig()
    if not filepath:
        filepath = os.path.join(cparser.savedir, 'shortcuts')
    cparser.filename = filepath
    setting = cparser.settings
    actions = []
    for section in cparser.sections():
        values = dict([(str(k), v) for k,v in  setting[section].items()])
        actions.append(create_action(parent, **values))
    return actions

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.toolbar = win.addToolBar('toolbar')
    loadShortCuts()
    win.show()
    app.exec_()
