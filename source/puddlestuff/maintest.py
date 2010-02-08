import sys, os
from puddlestuff.puddleobjects import (PuddleConfig, PuddleDock, winsettings,
                                       progress, PuddleStatus)
import tagmodel
from tagmodel import TagTable
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import pdb, resource
import mainwin.dirview, mainwin.tagpanel, mainwin.patterncombo, mainwin.filterwin
import puddlestuff.webdb
import loadshortcuts as ls
import m3u

from puddlestuff.puddlesettings import SettingsDialog, load_gen_settings
import puddlestuff.mainwin.funcs as mainfuncs
from functools import partial
from itertools import izip
import puddlestuff.audioinfo as audioinfo
from audioinfo import lnglength, strlength

ALWAYS = 'always'
FILESLOADED = 'filesloaded'
VIEWFILLED = 'viewfilled'
FILESSELECTED = 'filesselected'

ENABLESIGNALS = {ALWAYS: SIGNAL('always'),
FILESLOADED: SIGNAL('filesloaded'),
VIEWFILLED: SIGNAL('viewfilled'),
FILESSELECTED: SIGNAL('filesselected')}

pyqtRemoveInputHook()
status = PuddleStatus()
mainfuncs.status = status
tagmodel.status = status

def create_tool_windows(parent):
    actions = []
    cparser = PuddleConfig()
    cparser.filename = os.path.join(cparser.savedir, 'menus')
    for z in (mainwin.tagpanel.control, mainwin.dirview.control,
                mainwin.patterncombo.control, mainwin.filterwin.control,
                puddlestuff.webdb.control):
        name = z[0]
        try:
            if not z[2]:
                PuddleDock._controls[name] = z[1](status=status)
                continue
        except IndexError:
            pass

        p = PuddleDock(*z, **{'status':status})
        parent.addDockWidget(Qt.LeftDockWidgetArea, p)
        action = p.toggleViewAction()
        scut = cparser.get('winshortcuts', name, '')
        if scut:
            action.setShortcut(scut)
        actions.append(action)
    menu = ls.context_menu('windows', actions)
    return menu

def create_context_menus(controls, actions):
    for name in controls:
        menu = ls.context_menu(name, actions)
        if menu:
            controls[name].contextMenu = menu

def connect_controls(controls, actions=None):
    emits = {}
    for c in controls:
        for sig in c.emits:
            emits[sig].append(c) if sig in emits else emits.update({sig:[c]})

    connect = QObject.connect

    for c in controls:
        for signal, slot in c.receives:
            if signal in emits:
                [connect(i, SIGNAL(signal), slot) for i in emits[signal]]

TRIGGERED = SIGNAL('triggered()')

def connect_actions(actions, controls):
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
        command = action.command
        if action.control == 'mainwin' and hasattr(mainfuncs, command):
            f = getattr(mainfuncs, command)
            if 'parent' in f.func_code.co_varnames:
                f = partial(f, parent=c)
            connect(action, TRIGGERED, f)
            continue
        elif action.control in controls:
            c = controls[action.control]
            if hasattr(c, command):
                connect(action, TRIGGERED, getattr(c, command))
            else:
                print action.command, 'not found', action.text()

class MainWin(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.emits = ['loadFiles', 'always']
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
                          ('clearpreview', self._clearPreview)]
        self.gensettings = [('&Load last folder at startup', False, 1)]

        self.setWindowTitle("puddletag")
        self._table = TagTable()
        win = QSplitter()

        layout = QVBoxLayout()
        layout.addWidget(self._table)
        win.setLayout(layout)
        self.setCentralWidget(win)

        PuddleDock._controls = {'table': self._table,
                                'mainwin':self,
                                'funcs': mainfuncs.obj}
        self._winmenu = create_tool_windows(self)
        self._winmenu.setTitle('&Windows')
        self.createStatusBar()

        actions = ls.get_actions(self)
        menus = ls.get_menus('menu')
        menubar = ls.menubar(menus, actions)
        menubar.addMenu(self._winmenu)
        self.setMenuBar(menubar)
        mainfuncs.connect_status(actions)

        controls = PuddleDock._controls

        toolgroup = ls.get_menus('toolbar')
        [(z.setIconSize(QSize(16,16)), self.addToolBar(z)) for z in
                                    ls.toolbar(toolgroup, actions, controls)]

        connect_actions(actions, controls)
        create_context_menus(controls, actions)

        self.restoreSettings()
        self.emit(SIGNAL('always'), True)

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
        initial = self._lastdir[0]
        if initial in dirs and len(dirs) > 1:
            self.setWindowTitle('puddletag: %s + others' % initial)
        elif initial not in dirs and len(dirs) == 1:
            self.setWindowTitle('puddletag: %s' % dirs[0])
        elif initial not in dirs and len(dirs) > 1:
            self.setWindowTitle('puddletag: %s + others' % dirs[0])
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
        cparser = PuddleConfig()
        settings = QSettings(cparser.filename, QSettings.IniFormat)
        for control in PuddleDock._controls.values():
            if hasattr(control, 'saveSettings'):
                control.saveSettings()

        settings.setValue("main/lastfolder", QVariant(self._lastdir[0]))
        cparser.set("main", "maximized", self.isMaximized())
        settings.setValue('main/state', QVariant(self.saveState()))

        headstate = self._table.horizontalHeader().saveState()
        settings.setValue('table/header', QVariant(headstate))
        e.accept()
        #QMainWindow.closeEvent(self, e)

    def createStatusBar(self):
        statusbar = self.statusBar()
        statuslabel = QLabel()
        statuslabel.setFrameStyle(QFrame.NoFrame)
        statusbar.addPermanentWidget(statuslabel, 1)
        self._totalstats = QLabel('00 (00:00:00 | 00 MB)')
        self._selectedstats = QLabel('00 (00:00:00 | 00 MB)')
        statusbar.addPermanentWidget(self._selectedstats, 0)
        statusbar.addPermanentWidget(self._totalstats, 0)
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
            self.emit(SIGNAL('loadFiles'), files)
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
        settings = QSettings(cparser.filename, QSettings.IniFormat)
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
        self._lastdir = [unicode(settings.value('main/lastfolder',
                                        QVariant(home)).toString())]

        filepath = os.path.join(cparser.savedir, 'mappings')
        audioinfo.setmapping(audioinfo.loadmapping(filepath))

        h = self._table.horizontalHeader()
        h.restoreState(settings.value('table/header').toByteArray())
        self.restoreState(settings.value('main/state').toByteArray())

        connect_controls(controls)

        winsettings('mainwin', self)
        if cparser.get("main", "maximized", True):
            self.showMaximized()
        QApplication.processEvents()
        for control, val in gensettings.items():
            control.applyGenSettings(val, 1)

    def savePlayList(self):
        tags = self._table.model().taginfo
        settings = puddlesettings.PuddleConfig()
        filepattern = settings.get('playlist', 'filepattern','puddletag.m3u')
        default = findfunc.tagtofilename(filepattern, tags[0])
        f = unicode(QFileDialog.getSaveFileName(self,
                'Save Playlist', os.path.join(self.lastfolder, default)))
        if f:
            if cparser.get('playlist', 'extinfo', 1, True):
                pattern = cparser.get('playlist', 'extpattern','%artist% - %title%')
            else:
                pattern = None

            reldir = cparser.get('playlist', 'reldir', 0, True)

            m3u.exportm3u(tags, f, pattern, reldir)

    def _viewFilled(self, val):
        self.emit(SIGNAL('viewfilled'), val)

    def _updateStatus(self, files):
        numfiles = len(files)
        stats = [(int(z['__size']), lnglength(z['__length'])) for z in files]
        totalsize = sum([z[0] for z in stats])
        totallength = strlength(sum([z[1] for z in stats]))

        sizes = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB'}

        valid = [z for z in sizes if totalsize / (1024.0**z) > 1]
        val = max(valid)
        sizetext = '%.2f %s' % (totalsize/(1024.0**val), sizes[val])
        return '%d (%s | %s)' % (numfiles, totallength, sizetext)

    def updateSelectedStats(self, *args):
        files = status['selectedfiles']
        if files:
            self._selectedstats.setText(self._updateStatus(files))
        else:
            self._selectedstats.setText('0 (00:00 | 0 KB)')

    def updateTotalStats(self, *args):
        self._totalstats.setText(self._updateStatus(status['alltags']))

    def writeTags(self, tagiter, rows=None):
        if not rows:
            rows = status['selectedrows']
        setRowData = self._table.model().setRowData

        def func():
            for row, f in izip(rows, tagiter):
                try:
                    setRowData(row, f, undo=True)
                    yield None
                except (IOError, OSError), e:
                    m = 'An error occured while writing to <b>%s</b>. (%s)' % (
                            e.filename, e.strerror)
                    if row == rows[-1]:
                        yield m, 1
                    else:
                        yield m, len(rows)
        def fin():
            self._table.model().undolevel += 1
            self._table.selectionChanged()
        s = progress(func, 'Writing', len(rows), fin)
        s(self)

    def writeOneToMany(self, d):
        rows = status['selectedrows']
        setRowData = self._table.model().setRowData

        def func():
            for row in rows:
                try:
                    setRowData(row, d, undo=True)
                    yield None
                except (IOError, OSError), e:
                    yield e.filename, e.strerror, len(rows)
        def fin():
            self._table.model().undolevel += 1
            self._table.selectionChanged()
        s = progress(func, 'Writing', len(rows), fin)
        s(self)

    def _writePreview(self):
        taginfo = self._table.model().taginfo
        data = [z for z in enumerate(taginfo) if z[1].testData]
        self.writeTags((z[1].testData for z in data), [z[0] for z in data])

    def renameDirs(self, dirs):
        self._table.saveSelection()
        showmessage = True
        changed = []
        for olddir, newdir in dirs:
            try:
                os.rename(olddir, newdir)
                self._table.changeFolder(olddir, newdir)
            except (IOError, OSError), detail:
                errormsg = u"I couldn't rename: <i>%s</i> to <b>%s</b> (%s)" % (olddir, newdir, unicode(detail.strerror))
                #if len(dirs) > 1:
                if showmessage:
                    mb = QMessageBox('Error during rename', errormsg + u"<br />Do you want me to continue?", *(MSGARGS[:-1] + (QMessageBox.NoButton, self)))
                    ret = mb.exec_()
                    if ret == QMessageBox.Yes:
                        continue
                    if ret == QMessageBox.YesAll:
                        showmessage = False
                    else:
                        break
        self._table.restoreSelection()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = MainWin()
    win.show()
    app.exec_()
