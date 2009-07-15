#!/usr/bin/env python
# -*- coding: utf-8 -*-
#puddletag.py

#Copyright (C) 2008 concentricpuddle

#This file is part of puddletag, a semi-good music tag editor.

#This program is free software; you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation; either version 2 of the License, or
#(at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program; if not, write to the Free Software
#Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import actiondlg, findfunc, mainwin, puddlesettings, os, resource,sys, time, pdb
from audioinfo import FILENAME, PATH
from copy import copy, deepcopy
import helperwin
from helperwin import PicWidget
from puddleobjects import (ProgressWin, safe_name, unique, PuddleThread, natcasecmp)
from PyQt4.QtCore import QDir, Qt, QSettings, QString, QVariant, SIGNAL
from PyQt4.QtGui import (QAction, QApplication, QFileDialog, QFrame, QInputDialog,
                        QLabel, QLineEdit, QMainWindow, QMessageBox, QPixmap,
                        QShortcut)
from operator import itemgetter
import m3u

path = os.path
MSGARGS = (QMessageBox.Warning, QMessageBox.Yes or QMessageBox.Default,
                        QMessageBox.No or QMessageBox.Escape, QMessageBox.YesAll)
HIDEPROGRESS = 'HIDETHEPROGRESS!'

def showwriteprogress(func):
    """To be used as a decorator for fonction that need a progressbar.

    Use *only* in MainWin objects. It'll probably fail otherwise.

    func is the function you want wrapped. To work it must yield None when
    the progressbar is to be updated. If an error occurs, yield a tuple to
    be used in MainWin.writeError. Otherwise, if you want to show your
    own error message, but just want to hide the progress window, yield
    HIDEPROGRESS."""
    def s(*args):
        self = args[0]
        win = ProgressWin(self, len(self.cenwid.table.selectedRows), 'Writing ')
        win.show()
        #Sometimes when doing a quick action (like writing to only 1 file)
        #this window will display, but nothing will be drawn on it, because
        #(I assume) it got killed before anything happened. So I force that shit.
        #It doesn't work all the time. So if you have a fix, don't hesitate to
        #to share the knowledge.
        win.repaint()
        win.update()
        QApplication.processEvents()
        f = func(*args)
        self.showmessage = True

        def what():
            i = 0
            err = False
            while not win.wasCanceled:
                try:
                    temp = f.next()
                    if temp == HIDEPROGRESS:
                        err = True
                        self.t.emit(SIGNAL('win(int)'), -2)
                        break
                    elif temp is not None:
                        self.t.emit(SIGNAL('error(QString, QString, int)'),
                                                    temp[0], temp[1], temp[2])
                        err = True
                        break
                    else:
                        self.t.emit(SIGNAL('win(int)'), i)
                except StopIteration:
                    break
                i += 1

            if not err:
                self.t.emit(SIGNAL('win(int)'), -1)

        def shit(*theargs):
            if theargs[0] == -2:
                win.hide()
                try:
                    ret = f.next()
                    if ret:
                        self.t.start()
                    else:
                        raise StopIteration
                except StopIteration:
                    self.setTag(True)
                    self.fillCombos()
            elif theargs[0] == -1:
                win.close()
                self.setTag(True)
                self.fillCombos()
            elif isinstance(theargs[0], QString):
                if self.showmessage:
                    ret = self.writeError(unicode(theargs[0]), unicode(theargs[1]), int(theargs[2]))
                    if ret is True:
                        self.showmessage = False
                    elif ret is False:
                        self.t.emit(SIGNAL('win(int)'), -1)
                        return
                if not win.isVisible():
                    win.show()
                while self.t.isRunning():
                    pass
                self.t.start()
            win.setValue(win.value + 1)

        self.t = PuddleThread(what)
        self.shit = shit
        self.connect(self.t, SIGNAL('win(int)'), self.shit)
        self.connect(self.t, SIGNAL('error(QString, QString, int)'), self.shit)
        self.t.start()
    return s

class MainWin(QMainWindow):
    """The brain of puddletag. Everything happens here."""
    def __init__(self):
        #Things to remember when editing this function:
        #1. If you add a QAction, add it to self.actions.
        #It's a list that's disabled and enabled depending on state of the app.
        #I also have a pretty bad convention of having action names in lower
        #case and the action's triggered() slot being the action name in
        #camelCase

        QMainWindow.__init__(self)

        #Shows or doesn't show path in titlebar of current folder
        self.pathinbar = False
        self.setWindowTitle("puddletag")
        mainwin.createActions(self)
        mainwin.createControls(self)
        self.loadInfo()
        mainwin.createMenus(self)
        mainwin.connectActions(self)

        self.statusbar = self.statusBar()
        statuslabel = QLabel()
        statuslabel.setFrameStyle(QFrame.NoFrame)
        self.statusbar.addPermanentWidget(statuslabel,1)
        self.connect(self.statusbar,SIGNAL("messageChanged (const QString&)"), statuslabel.setText)

    def newFolderLoaded(self, *args):
        actions = [self.fileinlib, self.duplicates]
        for action in actions:
            action.blockSignals(True)
            action.setChecked(False)
            action.blockSignals(False)

    @showwriteprogress
    def cut(self):
        """The same as the cut operation in normal apps. In this case, though,
        the tag data isn't cut to the clipboard and instead remains in
        the copied atrribute."""
        table = self.cenwid.table
        rows = table.selectedRows[::]
        headerdata = [z[1] for z in table.model().headerdata]
        tags = table.selectedTags[::]
        sel = table.currentRowSelection()

        for i, row in enumerate(sel):
            tags[i] = [(headerdata[z], tags[i][headerdata[z]])
                                                for z in sel[row]]
        clip = unicode(tags)
        sel = table.currentRowSelection()
        QApplication.clipboard().setText(clip)

        for row, tag in zip(rows, tags):
            try:
                self.setTag(row, dict([(z[0], "") for z in tag]))
                yield None
            except (IOError, OSError), detail:
                yield (table.rowTags(row)[FILENAME], unicode(detail.strerror), len(rows))

    @showwriteprogress
    def paste(self):
        try:
            clip = eval(unicode(QApplication.clipboard().text()))
        except:
            raise StopIteration
        table = self.cenwid.table
        ulevel = table.model().undolevel
        rows = table.selectedRows[::]
        selected = table.currentRowSelection()
        headerdata = [z[1] for z in table.model().headerdata]
        for row, tag in zip(rows, clip):
            seltags = [headerdata[z] for z in selected[row]]
            try:
                self.setTag(row, dict(zip(seltags, [z[1] for z in tag])))
                yield None
            except (IOError, OSError), detail:
                yield (table.rowTags(row)[FILENAME], unicode(detail.strerror), len(rows))


    def clipcopy(self):
        table = self.cenwid.table
        rows = table.selectedRows[::]
        headerdata = [z[1] for z in table.model().headerdata]
        tags = table.selectedTags[::]
        sel = table.currentRowSelection()

        for i, row in enumerate(sel):
            tags[i] = [(headerdata[z], tags[i][headerdata[z]])
                                                for z in sel[row]]
        clip = unicode(tags)
        sel = table.currentRowSelection()
        QApplication.clipboard().setText(clip)

    def inLib(self, visible):

        table = self.cenwid.table
        if visible:
            self.duplicates.setChecked(False)
            try:
                libclass = self.librarywin.tree.library
            except AttributeError:
                self.warningMessage("Dude, you don't have a music library loaded")
                self.fileinlib.blockSignals(True)
                self.fileinlib.setChecked(False)
                self.fileinlib.blockSignals(False)
                return
            rowTags = table.rowTags
            rowtracks = [rowTags(row).stringtags() for row in xrange(table.rowCount())]
            libartists = libclass.getArtists()
            oldartist = ""
            rows = []
            for row, track in enumerate(rowtracks):
                try:
                    artist = track['artist']
                    if artist in libartists and artist != oldartist:
                        tracks = libclass.getTracks(artist)
                        titles = [z['title'][0] for z in tracks]
                        oldartist = artist
                    if artist in libartists and artist == oldartist:
                        if track['title'] in titles:
                            rows.append(row)
                        else:
                            if track['title'] in titles:
                                rows.append(row)
                except (KeyError, IndexError):
                    pass
            table.model().rowColors(rows)
        else:
            table.model().rowColors()

    def showDupes(self, visible):
        from functions import finddups
        from puddleobjects import ratio
        table = self.cenwid.table
        if visible:
            self.fileinlib.setChecked(False)
            key, val = QInputDialog.getText(self, 'puddletag',
                        "Enter name of tag to check for duplicates.",
                        QLineEdit.Normal, 'title')
            if not val:
                self.duplicates.blockSignals(True)
                self.duplicates.setChecked(False)
                self.duplicates.blockSignals(False)
                return
            key = unicode(key)
            rowTags = table.rowTags
            tofind = [rowTags(row).stringtags() for row in xrange(table.rowCount())]
            if key.startswith(':'):
                rows = finddups(tofind, key[1:], ratio)
            else:
                rows = finddups(tofind, key)
            arows = []
            [arows.extend(z) for z in rows]
            table.model().rowColors(arows)
        else:
            table.model().rowColors()

    def warningMessage(self, msg):
        """Like the name implies, shows a warning messagebox with message msg."""
        QMessageBox.warning(self.cenwid.table, 'Error', msg, QMessageBox.Ok, QMessageBox.NoButton)

    def writeError(self, filename, error, single):
        """Shows a messagebox containing an error message indicating that
        writing to filename has failed and asks the user to continue, stop,
        or continue without interruption.

        error is the error that caused the disruption.
        single is the number of files that are being written. If it is 1, then
        just a warningMessage is shown.

        Returns:
            True if yes to all.
            False if No.
            None if just yes."""
        if single > 1:
            errormsg = u"I couldn't write to: <b>%s</b> (%s)<br /> Do you want to continue?" % \
                        (filename, error)
            mb = QMessageBox('Error', errormsg , *(MSGARGS + (self.cenwid.table, )))
            ret = mb.exec_()
            if ret == QMessageBox.No:
                return False
            elif ret == QMessageBox.YesAll:
                return True
        else:
            self.warningMessage(u"I couldn't write to: <b>%s</b> (%s)" % (filename, error))

    def addFolder(self, filename = None):
        """Appends a folder. If filename is None, then show a dialog to
        open a folder first. Otherwise open the folder, filename"""
        if filename is None:
            self.openFolder(None, True)
        else:
            self.openFolder(filename, True)

    def autoTagging(self):
        """Opens Musicbrainz window"""
        try:
            from webdb import MainWin
            win = MainWin(self.cenwid.table, self)
            win.show()
        except ImportError:
            self.warningMessage("There was an error loading the musicbrainz library.<br />" +
                                "Do you have the <a href='http://musicbrainz2.org/doc/PythonMusicBrainz2'>python musicbrainz</a> bindings installed?")

    def changefocus(self):
        """Switches between different controls in puddletag, after user presses shortcut key."""
        controls = [self.cenwid.table, self.patterncombo]
        if self.combogroup.combos:
            #Found it by trial and error
            combo = self.combogroup.layout().itemAt(3).layout().itemAt(0).widget()
            controls.append(combo)
        if not hasattr(self, "currentfocus"):
            try:
                self.currentfocus = [i for i,control in enumerate(controls) if control.hasFocus()][0]
            except IndexError: #None of these control have focus
                self.currentfocus = len(controls) + 1
        if (self.currentfocus < (len(controls)-1)) :
            self.currentfocus += 1
        else:
            self.currentfocus = 0
        controls[self.currentfocus].setFocus()

    def clearTable(self):
        self.cenwid.table.model().taginfo = []
        self.cenwid.table.model().reset()
        self.fillCombos()

    def closeEvent(self, event):
        """Save settings and close."""
        cparser = puddlesettings.PuddleConfig()
        settings = QSettings(cparser.filename, QSettings.IniFormat)

        settings.setValue("table/sortcolumn", QVariant(self.cenwid.sortColumn))
        settings.setValue("main/lastfolder", QVariant(self.lastfolder))
        settings.setValue("main/maximized", QVariant(self.isMaximized()))
        settings.setValue('main/state', QVariant(self.saveState()))

        settings.setValue('main/height', QVariant(self.height()))
        settings.setValue('main/width', QVariant(self.width()))

        settings.setValue("editor/showfilter",QVariant(self.filtertable.isVisible()))
        settings.setValue("editor/showcombo",QVariant(self.combodock.isVisible()))
        settings.setValue("editor/showtree",QVariant(self.treedock.isVisible()))

        table = self.cenwid.table
        columnwidths = [unicode(table.columnWidth(z)) for z in range(table.model().columnCount())]
        cparser.setSection('columnwidths', 'column', columnwidths)

        titles = [z[0] for z in self.cenwid.headerdata]
        tags = [z[1] for z in self.cenwid.headerdata]

        cparser.setSection('tableheader', 'titles', titles)
        cparser.setSection('tableheader', 'tags', tags)
        patterns = [unicode(self.patterncombo.itemText(z)) for z in xrange(self.patterncombo.count())]
        cparser.setSection('editor', 'patterns', patterns)

    def loadInfo(self):
        """Loads the settings from puddletags settings and sets it."""

        cparser = puddlesettings.PuddleConfig()
        settings = QSettings(cparser.filename, QSettings.IniFormat)

        self.lastfolder = cparser.load("main","lastfolder", unicode(QDir.homePath()))
        maximise = bool(cparser.load('main','maximized', True))

        self.setWindowState(Qt.WindowMaximized)
        height = settings.value('main/height', QVariant(600)).toInt()[0]
        width = settings.value('main/width', QVariant(800)).toInt()[0]
        self.resize(width, height)
        if maximise:
            self.setWindowState(Qt.WindowNoState)

        titles = cparser.load('tableheader', 'titles',
        ['Path', 'Artist', 'Title', 'Album', 'Track', 'Length', 'Year', 'Bitrate', 'Genre', 'Comment', 'Filename'])

        tags = cparser.load('tableheader', 'tags',
        ['__path', 'artist', 'title', 'album', 'track', '__length', 'year', '__bitrate', 'genre', 'comment', '__filename'])

        headerdata = []
        for title, tag in zip(titles, tags):
            headerdata.append((title,tag))

        self.cenwid.inittable(headerdata)
        self.connect(self.cenwid.table.model(), SIGNAL('enableUndo'), self.undo.setEnabled)
        self.connect(self.cenwid.table.model(), SIGNAL('dataChanged (const QModelIndex&,const QModelIndex&)'), self.fillCombos)
        self.connect(self.cenwid.table.model(), SIGNAL('dataChanged (const QModelIndex&,const QModelIndex&)'), self.filterTable)

        columnwidths = [z for z in cparser.load("columnwidths","column",[356, 190, 244, 206, 48, 52, 60, 100, 76, 304, 1191], True)]
        [self.cenwid.table.setColumnWidth(i, z) for i,z in enumerate(columnwidths)]

        sortColumn = cparser.load("table","sortcolumn",1, True)
        self.cenwid.sortTable(int(sortColumn))
        header = self.cenwid.table.horizontalHeader()
        header.setSortIndicator (sortColumn, Qt.AscendingOrder)

        #self.splitter.restoreState(settings.value("splittersize").toByteArray())
        puddlesettings.MainWin(self, readvalues = True)
        self.showcombodock.setChecked(settings.value("editor/showcombo",QVariant(True)).toBool())
        self.showtreedock.setChecked(settings.value("editor/showtree",QVariant(True)).toBool())
        #For some fucking reason I need to do this, otherwise filterframe is always loaded.
        showfilter = settings.value("editor/showfilter",QVariant(False)).toBool()
        self.showfilter.setChecked(showfilter)
        self.filterframe.setVisible(showfilter)
        self.restoreState(settings.value('main/state').toByteArray())

        self.connect(self.reloaddir, SIGNAL("triggered()"),self.reloadFiles)
        self.loadShortcuts()


    def displayTag(self, tag):
        """Used to display tags in the status bar in a human parseable format."""
        if not tag:
            return "<b>Error in pattern</b>"
        s = "%s: <b>%s</b>, "
        return "".join([s % (z,v) for z,v in tag.items()])[:-2]

    def fillCombos(self, **args):
        """Fills the QComboBoxes in FrameCombo with
        the tags selected from self.table.

        It's **args, because many methods connect to fillCombos
        which pass arguments. None are needed(or used)."""

        table = self.cenwid.table
        combos = self.combogroup.combos
        if not combos:
            return
        self.rowEmpty()
        if not hasattr(table, "selectedRows") or (table.rowCount() == 0) or not table.selectedRows:
            self.combogroup.disableCombos()
            return
        self.combogroup.initCombos()

        tags = dict([(tag,[]) for tag in combos if tag != '__image'])
        images = []
        imagetags = set()
        for row in table.selectedRows:
            audio = table.rowTags(row)
            try:
                imagetags = imagetags.union(audio.IMAGETAGS)
            except AttributeError:
                pass
            if ('__image' in combos):
                if hasattr(audio,'image'):
                    images.extend(audio.images)
            for tag in tags:
                try:
                    if isinstance(audio[tag],(unicode, str)):
                        tags[tag].append(audio[tag])
                    else:
                            tags[tag].append("\\\\".join(audio[tag]))
                except KeyError:
                    tags[tag].append("")

        if '__image' in combos:
            images = unique(images)
            if images:
                combos['__image'].images.extend(images)
                if (len(images) == 1 or len(table.selectedRows) == 1):
                    combos['__image'].currentImage = 2
                else:
                    combos['__image'].currentImage = 0
            else:
                combos['__image'].currentImage = 1
            combos['__image'].setImageTags(imagetags)

        for z in tags:
            tags[z] = list(set(tags[z]))
        #Add values to combos
        for tagset in tags:
            [combos[tagset].addItem(unicode(z)) for z in sorted(tags[tagset])
                    if combos.has_key(tagset)]

        for combo in combos.values():
            combo.setEnabled(True)
            #If a combo has more than 3 items it's not more than one artist, so we
            #set it to the defaultvalue.
            try:
                if (combo.count() > 3) or (combo.count() < 2):
                    combo.setCurrentIndex(0)
                else:
                    combo.setCurrentIndex(2)
            except AttributeError:
                pass

        #There are already prefefined genres so I have to check
        #the selected file's one is there.
        if 'genre' in tags and len(tags['genre']) == 1:
            combo = combos['genre']
            index = combo.findText(tags['genre'][0])
            if index > -1:
                combo.setCurrentIndex(index)
            else:
                combo.setEditText(tags['genre'][0])
        else:
            combos['genre'].setCurrentIndex(0)

        self.patternChanged()


    def filterTable(self, *args):
        """Filter the table. args are ignored,
        self.filtertables controls are used."""
        tag = unicode(self.filtertable.currentText())
        text = unicode(self.filtertext.text())
        if text == u"":
            tag = u"None"
        table = self.cenwid.table
        if tag == u"None":
            [table.showRow(z) for z in range(table.rowCount())]
        elif tag == u"__all":
            for z in range(table.rowCount()):
                table.hideRow(z)
                for y in table.rowTags(z).values():
                    if (y is not None) and (text in unicode(y)):
                        table.showRow(z)
                        break

        else:
            for z in range(table.rowCount()):
                if (tag in table.rowTags(z)) and (text in unicode(table.rowTags(z)[tag])):
                    table.showRow(z)
                else:
                    table.hideRow(z)

    @showwriteprogress
    def formatValue(self, test = None):
        """Get tags from the selected files using the pattern in
        self.patterncombo."""
        table = self.cenwid.table
        pattern = unicode(self.patterncombo.currentText())
        rowselection = table.currentRowSelection()
        headerdata = [z[1] for z in table.model().headerdata]

        for row in table.selectedRows:
            audio = table.rowTags(row).stringtags()
            tags = [headerdata[c] for c in rowselection[row]]
            val = findfunc.tagtofilename(pattern, audio)
            newtag = dict([(tag, val) for tag in tags])
            try:
                self.setTag(row, newtag)
                yield None
            except (IOError, OSError), detail:
                yield (table.rowTags(row)[FILENAME], unicode(detail.strerror), len(table.selectedRows))

    def puddleFunctions(self):
        """Show format value window."""
        table = self.cenwid.table
        row = table.selectedRows[0]
        column = table.currentRowSelection()[row][0]
        tag = table.model().headerdata[column][1]
        text = table.selectedTags[0][tag]

        example = [text, table.selectedTags[0]]
        if hasattr(self, "prevfunc"):
            f = actiondlg.CreateFunction(prevfunc = self.prevfunc, parent = self, showcombo = False, example = example)
        else:
            f = actiondlg.CreateFunction(parent = self, showcombo = False, example = example)
        f.setModal(True)
        f.show()
        self.connect(f, SIGNAL("valschanged"), self.puddleFunctionsBuddy)

    @showwriteprogress
    def puddleFunctionsBuddy(self, func):
        self.prevfunc = func
        table = self.cenwid.table
        headerdata = self.cenwid.headerdata

        if func.function.func_code.co_varnames[0] == 'tags':
            useaudio = True
        else:
            useaudio = False

        function = func.runFunction
        tagnames = [column[1] for column in headerdata]

        for row in table.selectedRows:
            tags = {}
            rowtags = table.rowTags(row).stringtags()
            for column in table.currentRowSelection()[row]:
                try:
                    tagname = tagnames[column]
                    tags[tagname] = copy(rowtags[tagname])
                except KeyError: #The key doesn't consist of any text
                    tags[tagname] = ''
            for tag in tags:
                try:
                    if useaudio:
                        val = function(rowtags, rowtags)
                    else:
                        val = function(tags[tag], rowtags)
                    if val is not None:
                        tags[tag] = val
                except KeyError:
                    pass
            try:
                self.setTag(row,tags)
                yield None
            except (IOError, OSError), detail:
                yield (table.rowTags(row)[FILENAME], unicode(detail.strerror), len(table.selectedRows))

    @showwriteprogress
    def getTagFromFile(self):
        """Get tags from the selected files using the pattern in
        self.patterncombo."""
        table = self.cenwid.table
        pattern = unicode(self.patterncombo.currentText())

        for row in table.selectedRows:
            filename = table.rowTags(row)["__filename"]
            newtag = findfunc.filenametotag(pattern, path.basename(filename), True)
            try:
                if newtag is not None:
                    self.setTag(row, newtag)
                yield None
            except (IOError, OSError), detail:
                yield (table.rowTags(row)[FILENAME], unicode(detail.strerror), len(table.selectedRows))


    def importFile(self):
        """Shows a window that allows the user to import a text file to extract
        tags from."""
        filedlg = QFileDialog()
        foldername = self.cenwid.table.rowTags(self.cenwid.table.selectedRows[0])["__folder"]
        filename = unicode(filedlg.getOpenFileName(self,
                'OpenFolder',foldername))

        if filename:
            win = helperwin.ImportWindow(self, filename)
            win.setModal(True)
            patternitems = [self.patterncombo.itemText(z) for z in range(self.patterncombo.count())]
            win.patterncombo.addItems(patternitems)
            self.connect(win,SIGNAL("Newtags"), self.importFileBuddy)

    @showwriteprogress
    def importFileBuddy(self, taglist):
        table = self.cenwid.table
        for i, row in enumerate(table.selectedRows):
            try:
                self.setTag(row, taglist[i])
                yield None
            except IndexError:
                break
            except (IOError, OSError), detail:
                yield (table.rowTags(row)[FILENAME], unicode(detail.strerror), len(taglist))

    def importLib(self):
        """Shows window to import music library."""
        from musiclib import MainWin
        win = MainWin(self)
        win.setModal(True)
        win.show()
        self.connect(win, SIGNAL('libraryAvailable'), self.loadLib)

    def loadLib(self, libclass):
        """Loads a music library. Creates tree and everything."""
        import musiclib
        if libclass:
            if not hasattr(self, 'librarywin'):
                self.librarywin = musiclib.LibraryWindow(libclass, self.cenwid.table.model().load, self)
                self.connect(self.librarywin.tree, SIGNAL('loadFiles'),
                                                        self.newFolderLoaded)
                self.librarywin.setObjectName("LibraryDock")
                self.connect(self.showlibrarywin, SIGNAL('toggled(bool)'), self.librarywin.setVisible)
                self.connect(self.librarywin, SIGNAL('visibilitychanged'), self.showlibrarywin.setChecked)
                self.showlibrarywin.setEnabled(True)
                self.addDockWidget(Qt.RightDockWidgetArea, self.librarywin)
                self.connect(self.cenwid.table.model(),
                            SIGNAL('libFileChanged'), self.librarywin.tree.filesEdited)
                self.connect(self.cenwid.table.model(),
                            SIGNAL('delLibFile'), self.librarywin.tree.delTracks)
            else:
                self.librarywin.loadLibrary(libclass, self.cenwid.table.model().load)
                self.connect(self.librarywin.tree, SIGNAL('loadFiles'),
                                                        self.newFolderLoaded)
            self.librarywin.show()

    def loadShortcuts(self):
        """Used to load user defined shortcuts."""
        settings = QSettings()
        controls = {'table':self.cenwid.table,'patterncombo':self.patterncombo, 'main':self}
        size = settings.beginReadArray('Shortcuts')
        if size <= 0:
            settings = QSettings(":/puddletag.conf", QSettings.IniFormat)
            size = settings.beginReadArray('Shortcuts')

        for z in xrange(size):
            settings.setArrayIndex(z)
            control = "" #So that if control is defined incorrectly, no error is raised.
            try:
                control = controls[unicode(settings.value("control").toString())]
            except KeyError:
                val = unicode(settings.value("control").toString())
                if val.startswith("combo") and val[len('combo'):] in self.combogroup.combos:
                    control = self.combogroup.combos[val[len('combo'):]]
            command = unicode(settings.value("command").toString())
            key = settings.value("key").toString()
            if hasattr(control, command):
                QShortcut(key, self, getattr(control,command))
        settings.endArray()

    def loadPlayList(self):
        filedlg = QFileDialog()
        filename = unicode(filedlg.getOpenFileName(None,
            'OpenFolder'))
        try:
            files = m3u.readm3u(filename)
        except (OSError, IOError), e:
            QMessageBox.information(self.cenwid.table, 'Error',
                   'Could not read file: <b>%s</b><br />%s' % (filename,
                    e.strerror),
                    QMessageBox.Ok, QMessageBox.NoButton)
        except Exception, e:
            QMessageBox.information(self.cenwid.table, 'Error',
                   'Could not read file: <b>%s</b><br />%s' % (filename,
                    unicode(e)),
                    QMessageBox.Ok, QMessageBox.NoButton)

        selectionChanged = SIGNAL("itemSelectionChanged()")

        self.disconnect(self.tree, selectionChanged, self.openTree)
        self.disconnect(self.cenwid.table, selectionChanged, self.patternChanged)
        if self.pathinbar:
            self.setWindowTitle("puddletag " + filename)
        else:
            self.setWindowTitle("puddletag")
        self.cenwid.fillTable(files, False)

        self.connect(self.cenwid.table, selectionChanged, self.patternChanged)
        self.connect(self.tree, selectionChanged, self.openTree)
        self.cenwid.table.setFocus()
        self.fillCombos()
        self.newFolderLoaded()

    def openActions(self, quickaction = False):
        """Shows the action window and calls either RunAction or RunQuickaction
        depending on the value of quickaction."""
        self.qb = actiondlg.ActionWindow(self.cenwid.headerdata, self)
        self.qb.setModal(True)
        self.qb.show()
        if quickaction:
            self.connect(self.qb, SIGNAL("donewithmyshit"), self.runQuickAction)
        else:
            self.connect(self.qb, SIGNAL("donewithmyshit"), self.runAction)

    @showwriteprogress
    def runAction(self, funcs):
        """Runs the action selected in openActions.

        funcs is a list of lists. Each list in turn consisting of
        actiondlg.Function objects. These are applied to
        the selected files.

        See the actiondlg module for more details on funcs."""
        table = self.cenwid.table
        for audio, row in zip(table.selectedTags, table.selectedRows):
            tags = findfunc.runAction(funcs, audio)
            try:
                self.setTag(row, tags)
                yield None
            except (IOError, OSError), detail:
                yield (audio[FILENAME], unicode(detail.strerror), len(table.selectedRows))

    @showwriteprogress
    def runQuickAction(self, funcs):
        """Basically the same as runAction, except that
        all the functions in funcs are executed on the curently selected cells.

        Say you had a action that would convert "__path" to Mixed Case.
        If you ran it using runAction, it would do just that, but if you ran
        it using this function but had the title column selected, then
        all the files selected in the title column would have their titles
        converted to Mixed Case.

        funcs is a list of actiondlg.Function objects.
        No error checking is done, so don't pass shitty values."""

        table = self.cenwid.table
        headerdata = self.cenwid.headerdata

        for row, audio in zip(table.selectedRows, table.selectedTags):
            #looks complicated, but it's just the selected tags.
            selectedtags = [headerdata[column][1]
                    for column in table.currentRowSelection()[row]]
            tags = findfunc.runQuickAction(funcs, audio, selectedtags)
            try:
                self.setTag(row, tags)
                yield None
            except (IOError, OSError), detail:
                yield (audio[FILENAME], unicode(detail.strerror), len(table.selectedRows))

    def openFolder(self, filename = None, appenddir = False):
        """Opens a folder. If filename != None, then
        the table is filled with the folder.

        If filename is None, show the open folder dialog and open that.

        If appenddir = True, the folder is appended.
        Otherwise, the folder is just loaded."""
        selectionChanged = SIGNAL("itemSelectionChanged()")

        self.disconnect(self.tree, selectionChanged, self.openTree)
        self.disconnect(self.cenwid.table, selectionChanged, self.patternChanged)
        if filename is None:
            filedlg = QFileDialog()
            filedlg.setFileMode(filedlg.DirectoryOnly)
            filename = unicode(filedlg.getExistingDirectory(self,
                'OpenFolder', self.lastfolder ,QFileDialog.ShowDirsOnly))

        if not isinstance(filename, basestring):
            filename = unicode(filename[0], 'utf8')
        if not filename:
            return
        if isinstance(filename, basestring):
            if path.isdir(filename):
                #I'm doing this just to be safe.
                try:
                    filename = path.realpath(filename)
                except UnicodeDecodeError:
                    filename = path.realpath(filename.encode('utf8')).decode('utf8')
                self.lastfolder = filename
                if not appenddir:
                    self.tree.setFileIndex(filename)
                    self.tree.resizeColumnToContents(0)
                if self.pathinbar:
                    self.setWindowTitle("puddletag " + filename)
                else:
                    self.setWindowTitle("puddletag")
            if not self.isVisible():
                #If puddletag is started via the command line with a
                #large folder then the progress window is shown by itself without this window.
                self.show()
            QApplication.processEvents()
            self.cenwid.fillTable(filename, appenddir)
        else:
            self.cenwid.fillTable(filename, appenddir)
            self.setWindowTitle("Puddletag")

        self.connect(self.cenwid.table, selectionChanged, self.patternChanged)
        self.connect(self.tree, selectionChanged, self.openTree)
        self.cenwid.table.setFocus()
        self.fillCombos()
        self.newFolderLoaded()

    def openPrefs(self):
        """Nothing much. Just opens a preferences window and shows it.

        The preferences windows does everything like setting of values, updating
        and so forth."""
        win = puddlesettings.MainWin(self, self)
        win.setModal(True)
        win.show()

    def openTree(self, filename = None):
        """If a folder in self.tree is clicked then it should be opened.

        If filename is not None, then nothing is opened. The currently
        selected index is just set to that filename."""
        selectionChanged = SIGNAL("itemSelectionChanged()")
        if filename is None:
            filename = unicode(self.dirmodel.filePath(self.tree.selectedIndexes()[0]))
            self.openFolder(filename)
        else:
            self.disconnect(self.tree, selectionChanged, self.openTree)
            index = self.dirmodel.index(filename)
            self.tree.setCurrentIndex(index)
            self.connect(self.tree, selectionChanged, self.openTree)


    def patternChanged(self):
        """This function is called everytime patterncombo changes.
        It sets the values of the StatusTips for various actions
        to a preview of the resulf if that action is hovered over."""
        #There's an error everytime an item is deleted, we account for that
        try:
            if hasattr(self.cenwid.table,'selectedRows'):
                table = self.cenwid.table
                pattern = unicode(self.patterncombo.currentText())
                tag = table.rowTags(table.selectedRows[0], True)

                tip = self.displayTag(findfunc.filenametotag(pattern, path.basename(tag["__filename"]), True))
                self.tagfromfile.setStatusTip(tip)

                newfilename = (findfunc.tagtofilename(pattern, tag, True,
                                                        tag["__ext"] ))
                newfilename = path.join(path.dirname(tag["__filename"]), safe_name(newfilename))
                self.tagtofile.setStatusTip(u"New Filename: <b>%s</b>" % newfilename)

                oldir = path.dirname(tag['__folder'])
                newfolder = path.join(oldir, path.basename(findfunc.tagtofilename(pattern, tag)))
                dirstatus = u"Rename: <b>%s</b> to: <i>%s</i>" % (tag["__folder"], newfolder)
                self.renamedir.setStatusTip(dirstatus)

                rowselection = table.currentRowSelection()
                headerdata = [z[1] for z in table.model().headerdata]
                row = rowselection.keys()[0]
                audio = table.rowTags(row).stringtags()
                tags = [headerdata[c] for c in rowselection[row]]
                val = findfunc.tagtofilename(pattern, audio)
                newtag = dict([(tag, val) for tag in tags])
                tip = self.displayTag(newtag)
                self.formattag.setStatusTip(tip)
        except IndexError: pass

    def reloadFiles(self):
        """Guess..."""
        selectionChanged = SIGNAL("itemSelectionChanged()")
        self.disconnect(self.tree, selectionChanged, self.openTree)
        self.disconnect(self.cenwid.table, selectionChanged, self.patternChanged)
        self.cenwid.table.reloadFiles()
        self.connect(self.cenwid.table, selectionChanged, self.patternChanged)
        self.connect(self.tree, selectionChanged, self.openTree)

    def renameFolder(self):
        """Changes the directory of the currently selected files, to
        one as per the pattern in self.patterncombo."""

        tagtofilename = findfunc.tagtofilename
        selectionChanged = SIGNAL('itemSelectionChanged()')
        table = self.cenwid.table
        showmessage = True

        dirname = os.path.dirname
        basename = os.path.basename
        path = os.path

        #Get distinct folders
        folders = [[row, table.rowTags(row)["__folder"]] for row in table.selectedRows]
        newdirs = []
        for z in folders:
            if z[1] not in (z[1] for z in newdirs):
                newdirs.append(z)

        self.disconnect(table, selectionChanged, self.patternChanged)
        self.disconnect(self.tree, selectionChanged, self.openTree)

        #Create the msgbox, I like that there'd be a difference between
        #the new and the old filename, so I bolded the new and italicised the old.
        msg = u"Are you sure you want to rename: <br />"
        dirs = []
        for z in newdirs:
            currentdir = z[1]
            newfolder = path.join(dirname(z[1]), (basename(tagtofilename(unicode(self.patterncombo.currentText()), table.rowTags(z[0])))))
            msg += u'<i>%s</i> to <b>%s</b><br /><br />' % (currentdir, newfolder)
            dirs.append([z[1], newfolder])

        msg = msg[:-len('<br /><br />')]

        result = QMessageBox.question(self, 'Rename dirs?', msg, "Yes","No", "" ,1, 1)

        #Compare function to sort directories via parent.
        #So that the child is renamed before parent, thereby not giving Permission Denied errors.
        def comp(a, b):
            if a == b:
                return 0
            elif a in b:
                return 1
            elif b in a:
                return -1
            elif len(a) > len(b):
                return 1
            elif len(b) > len(a):
                return -1
            elif len(b) == len(a):
                return 0

        dirs = sorted(dirs, comp, itemgetter(0))

        table.saveSelection()
        #Finally, renaming
        if result == 0:
            for olddir, newdir in dirs:
                try:
                    idx = self.dirmodel.index(olddir)
                    os.rename(olddir, newdir)
                    self.cenwid.table.model().changeFolder(olddir, newdir)
                    self.dirmodel.refresh(self.dirmodel.parent(idx))
                    self.tree.setFileIndex(newdir)
                    if hasattr(self, "lastfolder"):
                        if olddir == self.lastfolder:
                            self.lastfolder = newdir
                            self.setWindowTitle(u'puddletag: ' + self.lastfolder)
                except (IOError, OSError), detail:
                    errormsg = u"I couldn't rename: <i>%s</i> to <b>%s</b> (%s)" % (olddir, newdir, unicode(detail.strerror))
                    if len(dirs) > 1:
                        if showmessage:
                            mb = QMessageBox('Error during rename', errormsg + u"<br />Do you want me to continue?", *(MSGARGS[:-1] + (QMessageBox.NoButton, self)))
                            ret = mb.exec_()
                            if ret == QMessageBox.Yes:
                                continue
                            if ret == QMessageBox.YesAll:
                                showmessage = False
                            else:
                                break
                    else:
                        self.warningMessage(u"I couldn't rename:<br /> <b>%s</b> to <i>%s</i> (%s)" % (olddir, newdir, unicode(detail.strerror)))
        self.connect(self.tree, selectionChanged, self.openTree)
        self.connect(self.cenwid.table, selectionChanged, self.patternChanged)
        self.fillCombos()
        table.restoreSelection()


    def rowEmpty(self):
        """If nothing's selected or if self.cenwid.table's empty,
        disable what needs to be disabled."""
        #An error gets raised if the table's empty.
        #So we disable everything in that case
        table = self.cenwid.table
        if table.isempty:
            [action.setEnabled(False) for action in self.supportactions]
        else:
            [action.setEnabled(True) for action in self.supportactions]

        try:
            if self.cenwid.table.selectedRows:
                [action.setEnabled(True) for action in self.actions]
                self.patterncombo.setEnabled(True)
                return
        except AttributeError:
                pass

        [action.setEnabled(False) for action in self.actions]
        self.patterncombo.setEnabled(False)

    @showwriteprogress
    def saveCombos(self):
        """Writes the tags of the selected files to the values in self.combogroup.combos."""
        combos = self.combogroup.combos
        table = self.cenwid.table
        if hasattr(table,'selectedRows') or table.selectedRows:
            self.disconnect(self.cenwid.table.model(),
                        SIGNAL('dataChanged (const QModelIndex&,const QModelIndex&)'),
                                 self.fillCombos)
            if '__image' in combos:
                combo = combos['__image']
                images = None
                if combo.currentImage == 1: #<blank>
                    images = []
                elif combo.currentImage > 1:
                    if len(table.selectedRows) == 1:
                        images = combo.images[2:]
                    else:
                        images = [combo.images[combo.currentImage]]


            for row in table.selectedRows:
                tags = {}
                for tag in combos:
                    try:
                        if tag == '__image':
                            if images is not None:
                                tags['__image'] = images
                        else:
                            curtext = unicode(combos[tag].currentText())
                            if curtext == "<blank>": tags[tag] = ""
                            elif curtext == "<keep>": pass
                            else:
                                tags[tag] = unicode(combos[tag].currentText()).split("\\\\")
                    except KeyError:
                        pass
                try:
                    self.setTag(row, tags)
                    yield None
                except (IOError, OSError), detail:
                    yield (table.rowTags(row)[FILENAME], unicode(detail.strerror), len(table.selectedRows))

    def savePlayList(self):
        tags = self.cenwid.table.model().taginfo
        cparser = puddlesettings.PuddleConfig()
        filepattern = cparser.load('playlist', 'filepattern','puddletag.m3u')
        default = findfunc.tagtofilename(filepattern, tags[0])
        f = unicode(QFileDialog.getSaveFileName(self,
                'Save Playlist', os.path.join(self.lastfolder, default)))
        if f:
            if cparser.load('playlist', 'extinfo', 1, True):
                pattern = cparser.load('playlist', 'extpattern','%artist% - %title%')
            else:
                pattern = None

            reldir = cparser.load('playlist', 'reldir',0, True)

            m3u.exportm3u(tags, f, pattern, reldir)
        
    @showwriteprogress
    def saveTagToFile(self):
        """Renames the selected files using the pattern
        in self.patterncombo."""

        pattern = unicode(self.patterncombo.currentText())
        table = self.cenwid.table
        showmessage = True
        taginfo = self.cenwid.tablemodel.taginfo

        showoverwrite = True
        for row in table.selectedRows:
            filename = taginfo[row][FILENAME]
            tag = taginfo[row]
            newfilename = (findfunc.tagtofilename(pattern,tag, True, tag["__ext"]))
            newfilename = path.join(path.dirname(filename), safe_name(newfilename))

            if path.exists(newfilename) and (newfilename != filename):
                if showoverwrite:
                    yield HIDEPROGRESS
                    mb = QMessageBox('Ovewrite existing file?', "The file: <b>" + newfilename + "</b> exists. Should I overwrite it?",
                                    QMessageBox.Question, QMessageBox.Yes,
                                    QMessageBox.Cancel or QMessageBox.Escape or QMessageBox.Default, QMessageBox.NoAll, self)
                    ret = mb.exec_()
                    if ret == QMessageBox.Cancel:
                        yield False
                        break
                    elif ret == QMessageBox.NoAll:
                        showoverwrite = False
                        yield True
                        continue
                else:
                    continue
            try:
                self.setTag(row, {"__path": path.basename(newfilename)}, True)
                yield None
            except (IOError, OSError), detail:
                if showmessage:
                    yield HIDEPROGRESS
                    errormsg = u"I couldn't rename <b>%s</b> to <i>%s</i> (%s)" \
                                 % (filename, newfilename, unicode(detail.strerror))
                    if len(table.selectedRows) > 1:
                        errormsg += "<br /> Do you want to continue?"
                        mb = QMessageBox('Renaming Failed', errormsg , *(MSGARGS + (self,)))
                        ret = mb.exec_()
                        if ret == QMessageBox.No:
                            break
                        elif ret == QMessageBox.YesAll:
                            showmessage = False
                        yield True
                    else:
                        self.warningMessage(errormsg)
                        yield False

    def setTag(self, row, tag = None, rename = False):
        """Used to write tags.

        row is the the row that's to be written to. If it
        is True, then nothing is written and the undolevel is updated.
        tag is a tag as normal
        if rename is True, then just renaming is done(for speed)

        Call this function if you have many files to write to and
        you want them all to have the same undo level. Make sure
        to call it with row = True afterwards.
        """
        table = self.cenwid.table
        if row is not True:
            rowtags = table.rowTags(row).copy()

        if row is True:
            #print 'row:', row, 'undolevel: ', table.model().undolevel
            table.model().updateTable(table.selectedRows)
            table.model().undolevel += 1
            if hasattr(self, 'librarywin'):
                self.librarywin.tree.cacheFiles(True)
            return
        level = table.model().undolevel
        mydict = {}
        #Create undo level for file
        try:
            for z in tag:
                if z not in rowtags:
                    mydict[z] = ""
                else:
                    mydict[z] = deepcopy(rowtags[z])
            tag[level] = mydict
        except TypeError: #If tag is None, or not a dictionary
            return
        table.updateRow(row, tag, justrename = rename)

        if (row is not True) and ('__library' in rowtags):
            newfile = rowtags.copy()
            newfile.update(tag)
            self.librarywin.tree.cacheFiles([rowtags], [newfile])

    def trackWizard(self):
        """Shows the autonumbering wizard and sets the tracks
            numbers should be filled in"""

        selectedRows = self.cenwid.table.selectedRows
        numtracks = len(selectedRows)
        rowTags = self.cenwid.table.rowTags
        tags = [rowTags(row, True) for row in selectedRows]

        for tag in tags:
            if 'track' not in tags:
                tag['track'] = ""
        mintrack = sorted(tags, natcasecmp, key = itemgetter("track"))[0]["track"]

        try:
            if "/" in mintrack:
                enablenumtracks = True
                mintrack = long(mintrack.split("/")[0])
            else:
                enablenumtracks = False
                mintrack = long(mintrack)
        except ValueError:
            mintrack = 1

        win = helperwin.TrackWindow(self, mintrack, numtracks, enablenumtracks)
        win.setModal(True)
        self.connect(win, SIGNAL("newtracks"), self.numberTracks)
        win.show()

    @showwriteprogress
    def numberTracks(self, indexes):
        """Numbers the selected tracks sequentially in the range
        between the indexes.
        The first item of indices is the starting track.
        The second item of indices is the number of tracks."""
        fromnum = indexes[0]
        if indexes[1] != "":
            num = "/" + indexes[1]
        else: num = ""

        table = self.cenwid.table
        rows = table.selectedRows

        if indexes[2]: #Restart dir numbering
            rowTags = table.rowTags
            folders = {}
            taglist = []
            for row in rows:
                folder = rowTags(row)["__folder"]
                if folder in folders:
                    folders[folder] += 1
                else:
                    folders[folder] = fromnum
                taglist.append({"track": unicode(folders[folder]) + num})
        else:
            taglist = [{"track": unicode(z) + num} for z in range(fromnum, fromnum + len(rows) + 1)]

        for i, row in enumerate(rows):
            try:
                self.setTag(row, taglist[i])
                yield None
            except IndexError:
                break
            except (IOError, OSError), detail:
                yield (table.rowTags(row)[FILENAME], unicode(detail.strerror), len(table.selectedRows))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    filename = sys.argv[1:]
    app.setOrganizationName("Puddle Inc.")
    app.setApplicationName("puddletag")

    qb = MainWin()
    qb.rowEmpty()
    if filename:
        pixmap = QPixmap(':/puddlelogo.png')
        splash = QSplash(pixmap)
        splash.show()
        QApplication.processEvents()
        qb.openFolder(filename)
    qb.show()
    app.exec_()
