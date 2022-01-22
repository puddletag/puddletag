# -*- coding: utf-8 -*-
import os
import sys

from PyQt5.QtWidgets import QAction, QApplication, QMainWindow, QMenu, QMenuBar, QToolBar

from .constants import CONFIGDIR
from .puddleobjects import PuddleConfig, get_icon, open_resourcefile
from .translations import translate

__version__ = 30

files = [open_resourcefile(filename)
         for filename in [':/caseconversion.action', ':/standard.action']]

SEPARATOR = 'separator'
ALWAYS = 'always'
menu_path = os.path.join(CONFIGDIR, 'menus')
shortcut_path = os.path.join(CONFIGDIR, 'shortcuts')


def create_file(path, resource):
    text = open_resourcefile(resource).read()
    f = open(path, 'w')
    f.write(text)
    f.close()


def check_file(path, resource):
    if not os.path.exists(path):
        create_file(path, resource)
    else:
        cparser = PuddleConfig(path)
        version = cparser.get('info', 'version', 0)
        if version < __version__:
            create_file(path, resource)


def create_files():
    check_file(menu_path, ':/menus')
    check_file(shortcut_path, ':/shortcuts')


def get_menus(section, filepath=None):
    cparser = PuddleConfig()
    if not filepath:
        filepath = menu_path
    cparser.filename = filepath
    menus = []
    settings = cparser.data
    temp = settings[section]
    menus = [(z, temp[z]) for z in settings[section + 'attrs']['order']]
    return menus


def menubar(menus, actions):
    texts = [str(action.text()) for action in actions]

    menubar = QMenuBar()
    winmenu = None
    _menus = {}
    for title, actionlist in menus:
        menu = menubar.addMenu(translate("Menus", title))
        _menus[title] = [menu]
        if title == '&Windows':
            winmenu = menu
            tr_section = 'Dialogs'
        else:
            tr_section = 'Menus'
        for action in actionlist:
            if action in texts:
                shortcut = actions[texts.index(action)]
                shortcut.setText(translate(tr_section, action))
                menu.addAction(shortcut)
                _menus[title].append(shortcut)
            elif action == SEPARATOR:
                menu.addSeparator()
    return menubar, winmenu, _menus


def context_menu(section, actions, filepath=None):
    cparser = PuddleConfig(filepath)
    if not filepath:
        filepath = menu_path
        cparser.filename = filepath
    order = [translate('Menus', z) for z in cparser.get(section, 'order', [])]
    if not order:
        return
    texts = [str(action.text()) for action in actions]
    menu = QMenu()
    for action in order:
        if action in texts:
            menu.addAction(actions[texts.index(action)])
        elif action == SEPARATOR:
            menu.addSeparator()
    return menu


def toolbar(groups, actions, controls=None):
    texts = [str(action.text()) for action in actions]
    if controls:
        controls = dict([('widget-' + z, v) for z, v in controls.items()])
    toolbar = QToolBar('Toolbar')
    for name, actionlist in groups:
        for action in actionlist:
            if action in texts:
                toolbar.addAction(actions[texts.index(action)])
            elif action in controls:
                toolbar.addWidget(controls[action])
        toolbar.addSeparator()
    return toolbar


def create_action(win, name, control, command, icon=None, enabled=ALWAYS,
                  tooltip=None, shortcut=None, status=None, togglecheck=None,
                  checkstate=None, icon_name=None):
    if icon:
        action = QAction(get_icon(icon_name, icon), name, win)
    else:
        action = QAction(name, win)
    action.setEnabled(False)

    if shortcut:
        try:
            action.setShortcut(shortcut)
        except TypeError:
            action.setShortcuts(shortcut)

    if tooltip:
        action.setToolTip(translate('Menus', tooltip))

    if togglecheck is not None:
        action.setCheckable(True)
        checked = int(checkstate)
        action.setChecked(bool(checked))

    action.togglecheck = togglecheck
    action.enabled = enabled
    action.command = command
    action.control = control
    action.status = status

    return action


def get_actions(parent, filepath=None):
    cparser = PuddleConfig()
    if not filepath:
        filepath = shortcut_path
    cparser.filename = filepath
    setting = cparser.data
    actions = []
    for section in cparser.sections():
        if section.startswith('shortcut'):
            values = dict([(str(k), v) for k, v in setting[section].items()])
            actions.append(create_action(parent, **values))
    return actions


if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.toolbar = win.addToolBar('toolbar')
    loadShortCuts()
    win.show()
    app.exec_()
