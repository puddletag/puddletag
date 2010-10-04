#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, os
from puddlestuff.puddleobjects import (PuddleConfig, PuddleDock, winsettings,
                                       progress, PuddleStatus, errormsg, dircmp)
import tagmodel
from tagmodel import TagTable
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import pdb, resource
import mainwin.dirview, mainwin.tagpanel, mainwin.patterncombo
import mainwin.filterwin, mainwin.storedtags, mainwin.logdialog
import mainwin.action_dialogs, mainwin.tagtools
import mainwin.previews, mainwin.artwork
import puddlestuff.masstagging
import puddlestuff.webdb
import loadshortcuts as ls
import m3u, findfunc, genres

from puddlestuff.puddlesettings import SettingsDialog, load_gen_settings
import puddlestuff.mainwin.funcs as mainfuncs
from functools import partial
from itertools import izip
import puddlestuff.audioinfo as audioinfo
from audioinfo import lnglength, strlength, PATH, str_filesize
from errno import EEXIST
from operator import itemgetter
from collections import defaultdict
import constants, shortcutsettings

import puddlestuff.findfunc, puddlestuff.tagsources
import puddlestuff.confirmations as confirmations

pyqtRemoveInputHook()

#Signals used in enabling/disabling actions.
#An actions default state is to be disabled.
#and action can use these signals to enable
#itself. See the loadshortcuts module for more info.
ALWAYS = 'always'
FILESLOADED = 'filesloaded'
VIEWFILLED = 'viewfilled'
FILESSELECTED = 'filesselected'

ENABLESIGNALS = {ALWAYS: SIGNAL('always'),
FILESLOADED: SIGNAL('filesloaded'),
VIEWFILLED: SIGNAL('viewfilled'),
FILESSELECTED: SIGNAL('filesselected')}

#A global variable that hold the status of
#various puddletag statuses.
#It is passed to any and all modules that asks for it.
#Feel free to read as much as you want from it, but
#modify only values that you've created or that are
#intended to be modified. This rule may be enforced
#in the future.
status = PuddleStatus()
mainfuncs.status = status
tagmodel.status = status
mainwin.previews.set_status(status)
mainwin.tagtools.set_status(status)

confirmations.add('rename_dirs', True, 'Confirm when renaming directories.')
confirmations.add('preview_mode', True, 'Confirm when exiting preview mode.')
confirmations.add('delete_files', True, 'Confirm when deleting files.')

def create_tool_windows(parent):
    """Creates the dock widgets for the main window (parent) using
    the modules stored in puddlestuff/mainwin.

    Returns (the toggleViewActions of the docks, the dockWidgets the
    mselves)."""
    actions = []
    docks = []
    cparser = PuddleConfig()
    cparser.filename = ls.menu_path
    controls = [z.control for z in (mainwin.tagpanel, mainwin.dirview,
        mainwin.patterncombo, mainwin.filterwin, puddlestuff.webdb, 
        mainwin.storedtags, mainwin.logdialog, mainwin.artwork,
        puddlestuff.masstagging)]
    controls.extend(mainwin.action_dialogs.controls)
    for z in controls:
        name = z[0]
        try:
            if not z[2]:
                PuddleDock._controls[name] = z[1](status=status)
                continue
        except IndexError:
            pass

        p = PuddleDock(*z[:2], **{'status':status})
        parent.addDockWidget(z[2], p)
        p.setVisible(z[3])
        docks.append(p)
        action = p.toggleViewAction()
        scut = cparser.get('winshortcuts', name, '')
        if scut:
            action.setShortcut(scut)
        actions.append(action)
    return actions, docks

def create_context_menus(controls, actions):
    """Creates context menus for controls using actions
    depending on whether and action in actions is
    supposed to be in a menu. See the context_menu
    function in the loadshortcuts module for more info."""
    for name in controls:
        menu = ls.context_menu(name, actions)
        if menu:
            controls[name].contextMenu = menu

def connect_controls(controls):
    """Connects the signals emitted by controls to any
    controls that receive them."""
    emits = {}
    for c in controls:
        for sig in c.emits:
            emits[sig].append(c) if sig in emits else emits.update({sig:[c]})

    connect = QObject.connect

    for c in controls:
        for signal, slot in c.receives:
            if signal in emits:
                [connect(i, SIGNAL(signal), slot) for i in emits[signal]]

def connect_control(control, controls):
    emits = defaultdict(lambda: [])
    for c in controls:
        [emits[sig].append(c) for sig in c.emits]

    connect = QObject.connect

    for signal, slot in control.receives:
        if signal in emits:
            [connect(c, SIGNAL(signal), slot) for c in emits[signal]]

    for c in controls:
        for signal, slot in c.receives:
            if signal in control.emits:
                connect(control, SIGNAL(signal), slot)

TRIGGERED = SIGNAL('triggered()')

def connect_actions(actions, controls):
    """Connect the triggered() signals in actions to the respective
    slot in controls if it exists. Just a message is shown if it
    doesn't."""
    emits = {}
    for c in controls.values():
        for sig in c.emits:
            emits[sig].append(c) if sig in emits else emits.update({sig:[c]})
    connect = QObject.connect
    for action in actions:
        if action.enabled in emits:
            if action.enabled in ENABLESIGNALS:
                [connect(c, ENABLESIGNALS[action.enabled], action.setEnabled)
                        for c in emits[action.enabled]]
            else:
                [connect(c, SIGNAL(action.enabled), action.setEnabled)
                        for c in emits[action.enabled]]
        else:
            print 'No enable signal found for', action.text()
            action.setEnabled(False)
            continue
        if action.togglecheck and action.togglecheck in emits:
            if action.togglecheck in ENABLESIGNALS:
                [connect(c, ENABLESIGNALS[action.togglecheck], action.setEnabled)
                    for c in emits[action.togglecheck]]
            else:
                [connect(c, SIGNAL(action.togglecheck), action.setEnabled)
                    for c in emits[action.togglecheck]]
        command = action.command
        if action.control == 'mainwin' and hasattr(mainfuncs, command):
            f = getattr(mainfuncs, command)
            if 'parent' in f.func_code.co_varnames:
                f = partial(f, parent=c)
            if action.togglecheck:
                connect(action, SIGNAL('toggled(bool)'), f)
            else:
                connect(action, TRIGGERED, f)
            continue
        elif action.control in controls:
            c = controls[action.control]
            if hasattr(c, command):
                connect(action, TRIGGERED, getattr(c, command))
            else:
                print action.command, 'slot not found for', action.text()

def connect_action_shortcuts(actions):
    cparser = PuddleConfig()
    cparser.filename = ls.menu_path
    for action in actions:
        shortcut = cparser.get('shortcuts', unicode(action.text()), '')
        if shortcut:
            action.setShortcut(shortcut)

def help_menu(parent):
    menu = QMenu('Help', parent)
    about = QAction('About puddletag', parent)
    about_qt = QAction('About Qt', parent)
    about_qt.connect(about_qt, SIGNAL('triggered()'), QApplication.aboutQt)
    about.connect(about, SIGNAL('triggered()'), 
        partial(mainfuncs.show_about, parent))
    menu.addAction(about)
    menu.addAction(about_qt)
    return menu

def load_plugins():
    from puddlestuff.pluginloader import load_plugins
    plugins = load_plugins()
    puddlestuff.findfunc.functions.update(plugins[constants.FUNCTIONS])
    puddlestuff.tagsources.tagsources.extend(plugins[constants.TAGSOURCE])

class PreviewLabel(QLabel):
    def __init__(self, *args, **kwargs):
        super(PreviewLabel, self).__init__(*args, **kwargs)
        self._enabled = False
    
    def mouseDoubleClickEvent(self, event):
        self._enabled = not self._enabled
        self.emit(SIGNAL('valueChanged'), self._enabled)

class MainWin(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.emits = ['loadFiles', 'always', 'dirsmoved', 'libfilesedited',
            'enable_preview_mode', 'disable_preview_mode']
        self.receives = [('writeselected', self.writeTags),
            ('filesloaded', self._filesLoaded),
            ('viewfilled', self._viewFilled),
            ('filesselected', self._filesSelected),
            ('renamedirs', self.renameDirs),
            ('filesloaded', self.updateTotalStats),
            ('filesselected', self.updateSelectedStats),
            ('onetomany', self.writeOneToMany),
            ('dirschanged', self._dirChanged),
            ('writepreview', self._writePreview),
            ('clearpreview', self._clearPreview),
            ('renameselected', self._renameSelected),
            ('playlistchanged', self._dirChanged),
            ('adddock', self.addDock),
            ('writeaction', self.writeAction),
            ('onetomanypreview', self.writeSinglePreview)]
        self.gensettings = [('&Load last folder at startup', False, 1)]
        self._playlist = None
        load_plugins()

        self.setWindowTitle("puddletag")
        self.setDockNestingEnabled(True)
        self._table = TagTable()
        self.connect(self._table, SIGNAL('dirsmoved'), self.updateDirs)
        win = QSplitter()

        layout = QVBoxLayout()
        layout.addWidget(self._table)
        win.setLayout(layout)
        self.setCentralWidget(win)

        PuddleDock._controls = {'table': self._table,
                                'mainwin':self,
                                'funcs': mainfuncs.obj}
        ls.create_files()
        winactions, self._docks = create_tool_windows(self)
        self.createStatusBar()

        actions = ls.get_actions(self)
        menus = ls.get_menus('menu')
        previewactions = mainwin.previews.create_actions(self)
        #tag_actions = mainwin.tagtools.create_actions(self)
        all_actions = actions + winactions + previewactions
        menubar, winmenu = ls.menubar(menus, all_actions)
        
        if winmenu:
            winmenu.addSeparator()
            self._winmenu = winmenu
        else:
            self._winmenu = QMenu('&Windows', self)
            menubar.addMenu(self._winmenu)
        self.setMenuBar(menubar)
        menubar.addMenu(help_menu(self))
        mainfuncs.connect_status(actions)

        controls = PuddleDock._controls

        toolgroup = ls.get_menus('toolbar')
        toolbar = ls.toolbar(toolgroup, all_actions, controls)
        toolbar.setObjectName('Toolbar')
        self.addToolBar(toolbar)

        connect_actions(actions, controls)
        connect_action_shortcuts(all_actions)
        create_context_menus(controls, all_actions)
        status['actions'] = all_actions
        shortcutsettings.ActionEditorDialog._loadSettings(status['actions'])

        self.restoreSettings()
        self.emit(SIGNAL('always'), True)

    def addDock(self, name, dialog, position):
        controls = PuddleDock._controls.values()
        dock = PuddleDock(name, dialog, self, status)
        self.addDockWidget(position, dock)
        self._winmenu.addAction(dock.toggleViewAction())
        connect_control(PuddleDock._controls[name], controls)

    def _status(self, controls):
        x = {}
        def status(k):
            if k in x: return x[value]()
        controls = controls.values()
        connect = self.connect(c, SIGNAL('getstatus'), status)
        [x.update(z.status) for z in controls]
        self._status = x
        self.connect(control, 'getstatus', getstatus)

    def _clearPreview(self):
        self._table.model().unSetTestData()

    def _dirChanged(self, dirs):
        if not dirs:
            self.setWindowTitle('puddletag')
            self._lastdir = []
            return
        
        if isinstance(dirs, basestring):
            dirs = [dirs]

        if self._lastdir:
            initial = self._lastdir[0]
        else:
            initial = None
        
        if initial not in dirs:
            initial = dirs[0]
        
        if len(dirs) > 1:
            self.setWindowTitle(u'puddletag: %s + others' % initial)
        else:
            self.setWindowTitle(u'puddletag: %s' % initial)
        self._lastdir = dirs

    def _getDir(self):
        dirname = self._lastdir[0] if self._lastdir else QDir.homePath()
        filedlg = QFileDialog()
        filedlg.setFileMode(filedlg.DirectoryOnly)
        filename = unicode(filedlg.getExistingDirectory(self,
            'Import directory.', dirname ,QFileDialog.ShowDirsOnly))
        return filename

    def appendDir(self, filename=None):
        self.openDir(filename, append=True)

    def _filesLoaded(self, val):
        self.emit(SIGNAL('filesloaded'), val)

    def _filesSelected(self, val):
        self.emit(SIGNAL('filesselected'), val)

    def applyGenSettings(self, settings, a=None):
        if a == 1:
            if settings['&Load last folder at startup']:
                self.openDir(self._lastdir[0], False)

    def closeEvent(self, e):
        controls = PuddleDock._controls
        for control in PuddleDock._controls.values():
            if hasattr(control, 'saveSettings'):
                control.saveSettings()

        cparser = PuddleConfig()
        settings = QSettings(constants.QT_CONFIG, QSettings.IniFormat)
        if self._lastdir:
            cparser.set('main', 'lastfolder', self._lastdir[0])
        cparser.set("main", "maximized", self.isMaximized())
        settings.setValue('main/state', QVariant(self.saveState()))

        headstate = self._table.horizontalHeader().saveState()
        settings.setValue('table/header', QVariant(headstate))
        genres.save_genres(status['genres'])
        e.accept()
        #QMainWindow.closeEvent(self, e)

    def createStatusBar(self):
        statusbar = self.statusBar()
        statuslabel = QLabel()
        statuslabel.setFrameStyle(QFrame.NoFrame)
        statusbar.addPermanentWidget(statuslabel, 1)
        self._totalstats = QLabel('00 (00:00:00 | 00 MB)')
        self._selectedstats = QLabel('00 (00:00:00 | 00 MB)')
        preview_status = PreviewLabel('Preview Mode: Off')
        statusbar.addPermanentWidget(preview_status, 0)
        statusbar.addPermanentWidget(self._selectedstats, 0)
        statusbar.addPermanentWidget(self._totalstats, 0)
        
        def set_preview_status(value):
            if value:
                preview_status.setText('<b>Preview Mode: On</b>')
            else:
                preview_status.setText('Preview Mode: Off')
        
        def change_preview(value):
            if value:
                self.emit(SIGNAL('enable_preview_mode'))
            else:
                self.emit(SIGNAL('disable_preview_mode'))
        
        self.connect(preview_status, SIGNAL('valueChanged'),
            change_preview)
        self.connect(self._table.model(), SIGNAL('previewModeChanged'),
            set_preview_status)
        statusbar.setMaximumHeight(statusbar.height())
        self.connect(statusbar,SIGNAL("messageChanged (const QString&)"),
                                            statuslabel.setText)

    def loadPlayList(self):
        filedlg = QFileDialog()
        dirname = self._lastdir[0] if self._lastdir else QDir.homePath()
        filename = unicode(filedlg.getOpenFileName(self,
            'Select m3u file', ))
        if not filename:
            return
        try:
            files = m3u.readm3u(filename)
            self.emit(SIGNAL('loadFiles'), files, None, None, None, filename)
        except (OSError, IOError), e:
            QMessageBox.information(self._table, 'Error',
                   'Could not read file: <b>%s</b><br />%s' % (filename,
                    e.strerror),
                    QMessageBox.Ok, QMessageBox.NoButton)
        except Exception, e:
            QMessageBox.information(self._table, 'Error',
                   'Could not read file: <b>%s</b><br />%s' % (filename,
                    unicode(e)),
                    QMessageBox.Ok)

    def openDir(self, filename=None, append=False):
        """Opens a folder. If filename != None, then
        the table is filled with the folder.

        If filename is None, show the open folder dialog and open that.

        If appenddir = True, the folder is appended.
        Otherwise, the folder is just loaded."""
        if filename is None:
            filename = self._getDir()
            if not filename:
                return
        else:
            if not isinstance(filename, basestring):
                filename = filename[0]

            filename = os.path.realpath(filename)

            if isinstance(filename, str):
                filename = unicode(filename, 'utf8')
        self.emit(SIGNAL('loadFiles'), None, [filename], append)

    def openPrefs(self):
        win = SettingsDialog(PuddleDock._controls.values(), self, status)
        win.show()

    def restoreSettings(self):
        cparser = PuddleConfig()
        settings = QSettings(constants.QT_CONFIG, QSettings.IniFormat)
        gensettings = {}
        controls = PuddleDock._controls.values()
        for control in controls:
            if hasattr(control, 'loadSettings'):
                control.loadSettings()
            if hasattr(control, 'gensettings'):
                t = load_gen_settings(control.gensettings)
                gensettings[control] = dict(t)

        for control, val in gensettings.items():
            control.applyGenSettings(val, 0)

        home = os.getenv('HOME')
        self._lastdir = [cparser.get('main', 'lastfolder', constants.HOMEDIR)]

        filepath = os.path.join(cparser.savedir, 'mappings')
        audioinfo.setmapping(audioinfo.loadmapping(filepath))
        status['genres'] = genres.load_genres()

        h = self._table.horizontalHeader()
        h.restoreState(settings.value('table/header').toByteArray())
        self.restoreState(settings.value('main/state').toByteArray())

        connect_controls(controls + [mainwin.previews.obj])

        winsettings('mainwin', self)
        if cparser.get("main", "maximized", True):
            self.showMaximized()
        QApplication.processEvents()
        for control, val in gensettings.items():
            control.applyGenSettings(val, 1)
        confirmations.load()

    def savePlayList(self):
        tags = self._table.model().taginfo
        settings = PuddleConfig()
        try:
            dirname = self._lastdir[0]
        except IndexError:
            dirname = constants.HOMEDIR
        filepattern = settings.get('playlist', 'filepattern','puddletag.m3u')
        default = findfunc.tagtofilename(filepattern, tags[0])
        f = unicode(QFileDialog.getSaveFileName(self,
                'Save Playlist', os.path.join(dirname, default)))
        if f:
            if settings.get('playlist', 'extinfo', 1, True):
                pattern = settings.get('playlist', 'extpattern','%artist% - %title%')
            else:
                pattern = None

            reldir = settings.get('playlist', 'reldir', 0, True)
            m3u.exportm3u(tags, f, pattern, reldir)

    def _viewFilled(self, val):
        self.emit(SIGNAL('viewfilled'), val)

    def _updateStatus(self, files):
        if not files:
            return '00 (00:00:00 | 00 KB)'
        numfiles = len(files)
        stats = [(int(z.size), lnglength(z.length)) for z in files]
        totalsize = sum([z[0] for z in stats])
        totallength = strlength(sum([z[1] for z in stats]))

        sizetext = str_filesize(totalsize)
        return '%d (%s | %s)' % (numfiles, totallength, sizetext)

    def lockLayout(self):
        for dw in self._docks:
            dw.setTitleBarWidget(QWidget())

    def updateSelectedStats(self, *args):
        self._selectedstats.setText(self._updateStatus(status['selectedfiles']))

    def updateTotalStats(self, *args):
        self._totalstats.setText(self._updateStatus(status['alltags']))

    def _write(self, tagiter, rows=None):
        if not rows:
            rows = status['selectedrows']
        model = self._table.model()
        setRowData = model.setRowData
        def fin():
            model.undolevel += 1
            self._table.selectionChanged()
            if not model.previewMode:
                self.emit(SIGNAL('libfilesedited'), lib_updates)
        lib_updates = []

        if model.previewMode:
            [setRowData(row, f, undo=True) for row, f in izip(rows, tagiter)]
            fin()
            return

        def func():
            for row, f in izip(rows, tagiter):
                try:
                    update = setRowData(row, f, undo=True)
                    if update:
                        lib_updates.append(update)
                    yield None
                except (IOError, OSError), e:
                    m = 'An error occured while writing to <b>%s</b>. (%s)' % (
                            e.filename, e.strerror)
                    if row == rows[-1]:
                        yield m, 1
                    else:
                        yield m, len(rows)
        
        return func, fin, rows

    def writeTags(self, tagiter, rows=None):
        ret = self._write(tagiter, rows)
        if ret is None:
            return
        
        func, fin, rows = ret
        s = progress(func, 'Writing ', len(rows), fin)
        s(self)
    
    def writeAction(self, tagiter, rows=None, state=None):
        if state is None:
            state = {}
        ret = self._write(tagiter, rows)
        if ret is None:
            return
        func, fin, rows = ret
        def finished():
            fin()
            if 'rename_dirs' in state:
                self.renameDirs(state['rename_dirs'].items())
        s = progress(func, 'Writing ', len(rows), finished)
        s(self)

    def writeOneToMany(self, d):
        model = self._table.model()
        rows = status['selectedrows']
        setRowData = model.setRowData
        lib_updates = []

        def fin():
            model.undolevel += 1
            self._table.selectionChanged()
            if not model.previewMode:
                self.emit(SIGNAL('libfilesedited'), lib_updates)

        if model.previewMode:
            [setRowData(row, d, undo=True) for row in rows]
            fin()
            return

        def func():
            for row in rows:
                try:
                    update = setRowData(row, d, undo=True)
                    if update:
                        lib_updates.append(update)
                    yield None
                except (IOError, OSError), e:
                    m = 'An error occured while writing to <b>%s</b>. (%s)' % (
                            e.filename, e.strerror)
                    if row == rows[-1]:
                        yield m, 1
                    else:
                        yield m, len(rows)

        s = progress(func, 'Writing ', len(rows), fin)
        s(self)
    
    def writeSinglePreview(self, d):
        model = self._table.model()
        rows = status['selectedrows']
        setRowData = model.setRowData

        [setRowData(row, d, undo=False, temp=True) for row in rows]
        columns = filter(None, map(model.columns.get, d))
        if columns:
            start = model.index(min(rows), min(columns))
            end = model.index(max(rows), max(columns))
            model.emit(SIGNAL("dataChanged(QModelIndex,QModelIndex)"),
                start, end)

    def _writePreview(self):
        taginfo = self._table.model().taginfo
        def get(audio):
            ret = audio.preview
            audio.preview = {}
            return ret
        data = [(row, get(audio)) for row, audio in 
                    enumerate(taginfo) if audio.preview]
        if not data:
            return
        self._table.model().previewMode = False
        self.writeTags((z[1] for z in data), [z[0] for z in data])

    def _renameSelected(self, filenames):
        rows = status['selectedrows']
        files = status['selectedfiles']
        model = self._table.model()
        setRowData = model.setRowData
        
        def fin():
            model.undolevel += 1
            self._table.selectionChanged()

        if model.previewMode:
            for row, audio, filename in izip(rows, files, filenames):
                tag = PATH
                if tag in audio.mapping:
                    tag = audio.mapping[tag]
                setRowData(row, {tag: filename}, True, True)
            fin()
            return

        def func():
            for row, audio, filename in izip(rows, files, filenames):
                tag = PATH
                if tag in audio.mapping:
                    tag = audio.mapping[tag]
                try:
                    setRowData(row, {tag: filename}, True, True)
                    yield None
                except EnvironmentError, e:
                    m = 'An error occured while renaming <b>%s</b> to ' \
                        '<b>%s</b>. (%s)' % (audio.filepath, filename, e.strerror)
                    if row == rows[-1]:
                        yield m, 1
                    else:
                        yield m, len(rows)

        s = progress(func, 'Renaming ', len(rows), fin)
        s(self)

    def renameDirs(self, dirs):
        self._table.saveSelection()
        showmessage = True
        dirs = sorted(dirs, dircmp, itemgetter(0))
        for index, (olddir, newdir) in enumerate(dirs):
            try:
                if os.path.exists(newdir) and (olddir != newdir):
                    raise IOError(EEXIST, os.strerror(EEXIST), newdir)
                os.rename(olddir, newdir)
                self._table.changeFolder(olddir, newdir)
                if self._lastdir and olddir in self._lastdir:
                    self._lastdir[self._lastdir.index(olddir)] = newdir
            except (IOError, OSError), detail:
                msg = u"I couldn't rename: <i>%s</i> to <b>%s</b> (%s)" % (olddir, newdir, unicode(detail.strerror))
                if index == len(dirs) - 1:
                    dirlen = 1
                else:
                    dirlen = len(dirs)
                if showmessage:
                    ret = errormsg(self, msg, dirlen)
                    if ret is True:
                        showmessage = False
                    elif ret is False:
                        break
        self.emit(SIGNAL('dirsmoved'), dirs)
        self._dirChanged(self._lastdir)
        self._table.restoreSelection()
    
    def updateDirs(self, dirs):
        if self._lastdir:
            last = self._lastdir[::]
        else:
            last = None
        for index, (olddir, newdir) in enumerate(dirs):
            self._table.changeFolder(olddir, newdir, False)
            if last and olddir in last:
                last[last.index(olddir)] = newdir
        self.emit(SIGNAL('dirsmoved'), dirs)
        self._dirChanged(last)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = MainWin()
    win.show()
    app.exec_()
