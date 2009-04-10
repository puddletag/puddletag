#!/usr/bin/env python

"""
Contains objects used throughout puddletag"""

#puddleobjects.py

#Copyright (C) 2008-2009 concentricpuddle

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


from PyQt4.QtGui import *
from PyQt4.QtCore import *
import sys

from itertools import groupby # for unique function.
from bisect import bisect_left, insort_left # for unique function.
from copy import copy

HORIZONTAL = 1
VERTICAL = 0

class MoveButtons(QWidget):
    def __init__(self, arrayname, index = 0, orientation = HORIZONTAL, parent = None):
        QWidget.__init__(self, parent)
        self.next = QPushButton('&>>')
        self.prev = QPushButton('&<<')
        if orientation == VERTICAL:
            box = QVBoxLayout()
            box.addWidget(self.next, 0)
            box.addWidget(self.prev, 0)
        else:
            box = QHBoxLayout()
            box.addWidget(self.prev)
            box.addWidget(self.next)


        self.arrayname = arrayname

        self.setLayout(box)
        self.index = index
        self.connect(self.next, SIGNAL('clicked()'), self.nextClicked)
        self.connect(self.prev, SIGNAL('clicked()'), self.prevClicked)

    def _setCurrentIndex(self, index):
        try:
            if index >= len(self.arrayname) or index < 0:
                return
            else:
                self._currentindex = index
                if self._currentindex >= len(self.arrayname) - 1:
                    self.next.setEnabled(False)
                else:
                    self.next.setEnabled(True)

                if self._currentindex <= 0:
                    self.prev.setEnabled(False)
                else:
                    self.prev.setEnabled(True)
        except TypeError:
            "Probably arrayname is None or something."
            self.prev.setEnabled(False)
            self.next.setEnabled(False)

        if (not self.prev.isEnabled()) and (not self.next.isEnabled()):
            self.prev.hide()
            self.next.hide()
        else:
            self.prev.show()
            self.next.show()

        self.emit(SIGNAL('indexChanged'), index)

    def _getCurrentIndex(self):
        return self._currentindex

    index = property(_getCurrentIndex, _setCurrentIndex)

    def nextClicked(self):
        self.index += 1

    def prevClicked(self):
        self.index -= 1

    def updateButtons(self):
        self.index = self.index

def unique(seq, stable = False):
    """unique(seq, stable=False): return a list of the elements in seq in arbitrary
    order, but without duplicates.
    If stable=True it keeps the original element order (using slower algorithms)."""
    # Developed from Tim Peters version:
    #   http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/52560

    #if uniqueDebug and len(str(seq))<50: print "Input:", seq # For debugging.

    # Special case of an empty s:
    if not seq: return []

    # if it's a set:
    if isinstance(seq, set): return list(seq)

    if stable:
        # Try with a set:
        seqSet= set()
        result = []
        try:
            for e in seq:
                if e not in seqSet:
                    result.append(e)
                    seqSet.add(e)
        except TypeError:
            pass # move on to the next method
        else:
            #if uniqueDebug: print "Stable, set."
            return result

        # Since you can't hash all elements, use a bisection on sorted elements
        result = []
        sortedElem = []
        try:
            for elem in seq:
                pos = bisect_left(sortedElem, elem)
                if pos >= len(sortedElem) or sortedElem[pos] != elem:
                    insort_left(sortedElem, elem)
                    result.append(elem)
        except TypeError:
            pass  # Move on to the next method
        else:
            #if uniqueDebug: print "Stable, bisect."
            return result
    else: # Not stable
        # Try using a set first, because it's the fastest and it usually works
        try:
            u = set(seq)
        except TypeError:
            pass # move on to the next method
        else:
            #if uniqueDebug: print "Unstable, set."
            return list(u)

        # Elements can't be hashed, so bring equal items together with a sort and
        # remove them out in a single pass.
        try:
            t = sorted(seq)
        except TypeError:
            pass  # Move on to the next method
        else:
            #if uniqueDebug: print "Unstable, sorted."
            return [elem for elem,group in groupby(t)]

    # Brute force:
    result = []
    for elem in seq:
        if elem not in result:
            result.append(elem)
    #if uniqueDebug: print "Brute force (" + ("Unstable","Stable")[stable] + ")."
    return result

if sys.version_info[:2] < (2, 5):
    def partial(func, arg):
        def callme():
            return func(arg)
        return callme
else:
    from functools import partial

def safe_name(name, to = None):
    """Make a filename safe for use (remove some special chars)

    If any special chars are found they are replaced by to."""
    if not to:
        to = ""
    else:
        to = unicode(to)
    escaped = ""
    for ch in name:
        if ch not in r'/\*?;"|:': escaped = escaped + ch
        else: escaped = escaped + to
    if not escaped: return '""'
    return escaped

class compare:
    "Natural sorting class."
    def try_int(self, s):
        "Convert to integer if possible."
        try: return int(s)
        except: return s

    def natsort_key(self, s):
        "Used internally to get a tuple by which s is sorted."
        import re
        return map(self.try_int, re.findall(r'(\d+|\D+)', s))

    def natcmp(self, a, b):
        "Natural string comparison, case sensitive."
        return cmp(self.natsort_key(a), self.natsort_key(b))

    def natcasecmp(self, a, b):
        "Natural string comparison, ignores case."
        a = list(a)
        b = list(b)
        return self.natcmp("".join(a).lower(), "".join(b).lower())

class HeaderSetting(QDialog):
    """A dialog that allows you to edit the header of a TagTable widget."""
    def __init__(self, tags = None, parent = None, showok = True, showedits = True):
        QDialog.__init__(self, parent)
        self.listbox = ListBox()
        self.tags = [list(z) for z in tags]
        self.listbox.addItems([z[0] for z in self.tags])

        self.vbox = QVBoxLayout()
        self.vboxgrid = QGridLayout()
        self.textname = QLineEdit()
        self.tag = QLineEdit()
        self.buttonlist = ListButtons()
        self.buttonlist.edit.setVisible(False)
        if showedits:
            self.vboxgrid.addWidget(QLabel("Name"),0,0)
            self.vboxgrid.addWidget(self.textname,0,1)
            self.vboxgrid.addWidget(QLabel("Tag"), 1,0)
            self.vboxgrid.addWidget(self.tag,1,1)
            self.vboxgrid.addLayout(self.buttonlist,2,0)
        else:
            self.vboxgrid.addLayout(self.buttonlist,1,0)
        self.vboxgrid.setColumnStretch(0,0)

        self.vbox.addLayout(self.vboxgrid)
        self.vbox.addStretch()

        self.grid = QGridLayout()
        self.grid.addWidget(self.listbox,0,0)
        self.grid.addLayout(self.vbox,0,1)
        self.grid.setColumnStretch(1,2)

        self.connect(self.listbox, SIGNAL("currentItemChanged (QListWidgetItem *,QListWidgetItem *)"), self.fillEdits)
        self.connect(self.listbox, SIGNAL("itemSelectionChanged()"),self.enableEdits)


        self.okbuttons = OKCancel()
        if showok is True:
            self.grid.addLayout(self.okbuttons, 1,0,1,2)
        self.setLayout(self.grid)

        self.connect(self.okbuttons, SIGNAL("ok"), self.okClicked)
        self.connect(self.okbuttons, SIGNAL("cancel"), self.close)
        self.connect(self.textname, SIGNAL("textChanged (const QString&)"), self.updateList)
        self.connect(self.buttonlist, SIGNAL("add"), self.add)
        self.connect(self.buttonlist, SIGNAL("moveup"), self.moveup)
        self.connect(self.buttonlist, SIGNAL("movedown"), self.movedown)
        self.connect(self.buttonlist, SIGNAL("remove"), self.remove)

        self.listbox.setCurrentRow(0)

    def enableEdits(self):
        if len(self.listbox.selectedItems()) > 1:
            self.textname.setEnabled(False)
            self.tag.setEnabled(False)
            return
        self.textname.setEnabled(True)
        self.tag.setEnabled(True)

    def remove(self):
        if len(self.tags) == 1: return
        self.disconnect(self.textname, SIGNAL("textChanged (const QString&)"), self.updateList)
        self.disconnect(self.listbox, SIGNAL("currentItemChanged (QListWidgetItem *,QListWidgetItem *)"), self.fillEdits)
        self.listbox.removeSelected(self.tags)
        row = self.listbox.currentRow()
        #self.listbox.clear()
        #self.listbox.addItems([z[0] for z in self.tags])

        if row == 0:
            self.listbox.setCurrentRow(0)
        elif row + 1 < self.listbox.count():
            self.listbox.setCurrentRow(row+1)
        else:
            self.listbox.setCurrentRow(self.listbox.count() -1)
        self.fillEdits(self.listbox.currentItem(), None)
        self.connect(self.textname, SIGNAL("textChanged (const QString&)"), self.updateList)
        self.connect(self.listbox, SIGNAL("currentItemChanged (QListWidgetItem *,QListWidgetItem *)"), self.fillEdits)

    def moveup(self):
        self.listbox.moveUp(self.tags)

    def movedown(self):
        self.listbox.moveDown(self.tags)

    def updateList(self, text):
        self.listbox.currentItem().setText(text)

    def fillEdits(self, current, prev):
        row = self.listbox.row(prev)
        try: #An error is raised if the last item has just been removed
            if row > -1:
                self.tags[row][0] = unicode(self.textname.text())
                self.tags[row][1] = unicode(self.tag.text())
        except IndexError:
            pass

        row = self.listbox.row(current)
        if row > -1:
            self.textname.setText(self.tags[row][0])
            self.tag.setText(self.tags[row][1])

    def okClicked(self):
        row = self.listbox.currentRow()
        if row > -1:
            self.tags[row][0] = unicode(self.textname.text())
            self.tags[row][1] = unicode(self.tag.text())
        self.emit(SIGNAL("headerChanged"),[z for z in self.tags])
        self.close()

    def add(self):
        row = self.listbox.count()
        self.tags.append(["",""])
        self.listbox.addItem("")
        [self.listbox.setItemSelected(item, False) for item in self.listbox.selectedItems()]
        self.listbox.setCurrentRow(row)
        self.textname.setFocus()

class ListButtons(QVBoxLayout):
    """A Layout that contains five buttons usually
    associated with listboxes. They are
    add, edit, movedown, moveup and remove.

    Each button, when clicked sends signal with the
    buttons name. e.g. add sends SIGNAL("add").

    You can find them all in the widgets attribute."""

    def __init__(self, parent = None):
        QVBoxLayout.__init__(self, parent)
        self.add = QToolButton()
        self.add.setIcon(QIcon(':/filenew.png'))
        self.add.setToolTip('Add')
        self.remove = QToolButton()
        self.remove.setIcon(QIcon(':/remove.png'))
        self.remove.setToolTip('Remove')
        self.moveup = QToolButton()
        self.moveup.setIcon(QIcon(':/moveup.png'))
        self.moveup.setToolTip('Move Up')
        self.movedown = QToolButton()
        self.movedown.setIcon(QIcon(':/movedown.png'))
        self.movedown.setToolTip('Move Down')
        self.edit = QToolButton()
        self.edit.setIcon(QIcon(':/edit.png'))
        self.edit.setToolTip('Edit')

        self.widgets = [self.add, self.edit, self.remove, self.moveup, self.movedown]
        [self.addWidget(widget) for widget in self.widgets]
        [z.setIconSize(QSize(16,16)) for z in self.widgets]
        self.addStretch()

        clicked = SIGNAL("clicked()")
        self.connect(self.add, clicked, self.addClicked)
        self.connect(self.remove, clicked, self.removeClicked)
        self.connect(self.moveup, clicked, self.moveupClicked)
        self.connect(self.movedown, clicked, self.movedownClicked)
        self.connect(self.edit, clicked, self.editClicked)

    def addClicked(self):
        self.emit(SIGNAL("add"))

    def removeClicked(self):
        self.emit(SIGNAL("remove"))

    def moveupClicked(self):
        self.emit(SIGNAL("moveup"))

    def movedownClicked(self):
        self.emit(SIGNAL("movedown"))

    def editClicked(self):
        self.emit(SIGNAL("edit"))

class ListBox(QListWidget):
    """Puddletag's replacement of QListWidget, because
    removing, moving and deleting items in a listbox
    is done a lot.

    First the modifier methods.
    removeSelected, moveUp and moveDown each does as the
    name implies. See docstrings for more info.

    connectToListButtons -> connects removeSelected etc. to
    the respective buttons in a ListButtons object.

    Attributes:
    editButton -> Set this to a button or control which will be enabled only
    when a single item is selected.

    yourlist -> The list that will be used in removeSelected et al, if None
    is passed when calling the function.."""
    def __init__(self, parent = None):
        QListWidget.__init__(self, parent)
        self.yourlist = None
        self.editButton = None
        self.setSelectionMode(self.ExtendedSelection)

    def selectionChanged(self, selected, deselected):
        if self.editButton:
            if len(self.selectedItems()) == 1:
                self.editButton.setEnabled(True)
            else:
                self.editButton.setEnabled(False)
        QListWidget.selectionChanged(self, selected, deselected)

    def connectToListButtons(self, listbuttons, yourlist = None):
        """Connect the moveUp, moveDown and removeSelected to the
        moveup, movedown and remove signals of listbuttons and
        sets the editButton.

        yourlist is used a the argument in these functions if
        no other yourlist is passed."""
        self.editButton = listbuttons.edit
        self.connect(listbuttons, SIGNAL('moveup'), self.moveUp)
        self.connect(listbuttons, SIGNAL('movedown'), self.moveDown)
        self.connect(listbuttons, SIGNAL('remove'), self.removeSelected)
        self.yourlist = yourlist

    def removeSelected(self, yourlist = None, rows = None):
        """Removes the currently selected items.
        If yourlist is not None, then the selected
        items are removed for yourlist also. Note, that
        the indexes of the items in yourlist and the listbox
        have to correspond.

        If you want to remove anything other than the selected,
        just set rows to a list of integers."""
        if not yourlist:
            yourlist = self.yourlist
        if rows:
            rows = sorted(rows)
        else:
            rows = sorted([self.row(item) for item in self.selectedItems()])

        for i in range(len(rows)):
            self.takeItem(rows[i])
            if yourlist:
                try:
                    del(yourlist[rows[i]])
                except (KeyError, IndexError):
                    "The list doesn't have enough items or something"
            rows = [z - 1 for z in rows]

    def moveUp(self, yourlist = None, rows = None):
        """Moves the currently selected items up one place.
        If yourlist is not None, then the indexes of yourlist
        are updated in tandem. Note, that
        the indexes of the items in yourlist and the listbox
        have to correspond."""
        if not rows:
            rows = [self.row(item) for item in self.selectedItems()]
        rows = sorted(rows)
        if not yourlist:
            yourlist = self.yourlist

        if 0 in rows:
            return
        #import pdb
        #pdb.set_trace()
        [self.setItemSelected(item, False) for item in self.selectedItems()]
        for i in range(len(rows)):
            row = rows[i]
            item = self.takeItem(row)
            self.insertItem(row - 1, item)
            if yourlist:
                temp = copy(yourlist[row - 1])
                yourlist[row - 1] = yourlist[row]
                yourlist[row] = temp
        [self.setItemSelected(self.item(row - 1), True) for row in rows]

    def moveDown(self, yourlist = None, rows = None):
        """See moveup. It's exactly the opposite."""
        if rows is None:
            rows = [self.row(item) for item in self.selectedItems()]
        if self.count() - 1 in rows:
            return
        [self.setItemSelected(item, False) for item in self.selectedItems()]
        if not yourlist:
            yourlist = self.yourlist
        rows = sorted(rows)
        lastindex = rows[0]
        groups = {lastindex:[lastindex]}
        lastrow = lastindex
        for row in rows[1:]:
            if row - 1 == lastindex:
                groups[lastrow].append(row)
            else:
                groups[row] = [row]
                lastrow = row
            lastindex = row

        for group in groups:
            item = self.takeItem(group + len(groups[group]))
            if yourlist:
                temp = copy(yourlist[group + len(groups[group])])
                for index in reversed(groups[group]):
                    yourlist[index + 1] = copy(yourlist[index])
                yourlist[group] = temp
            self.insertItem(group, item)

        [self.setItemSelected(self.item(row + 1), True) for row in rows]

class PuddleThread(QThread):
    """puddletag rudimentary thread.
    pass a command to run in another thread. The result
    is stored in retval."""
    def __init__(self, command, parent = None):
        QThread.__init__(self, parent)
        self.command = command
    def run(self):
        self.retval = self.command()

class ProgressWin(QProgressDialog):
    def __init__(self, parent=None, maximum = 100, increment = 1):
        QProgressDialog.__init__(self, "", "Cancel", 0, maximum, parent)
        self.setModal(True)
        self.setWindowTitle("Please Wait...")
        self.increment = increment
        self.nextinc = increment
        self.numcalled = 0
        self.setAutoClose(True)
        self.setValue(0)

    def updateVal(self, value = None):
        if value:
            self.setValue(self.value() + value)
        else:
            self.setValue(self.value() + 1)
        QApplication.processEvents()

class PuddleDock(QDockWidget):
    """A normal QDockWidget that emits a 'visibilitychanged' signal
    when...uhm...it changes visibility."""
    def __init__(self, title = None, parent = None):
        QDockWidget.__init__(self, title, parent)

    def setVisible(self, visible):
        self.emit(SIGNAL('visibilitychanged'), visible)
        QDockWidget.setVisible(self, visible)

class OKCancel(QHBoxLayout):
    """Yes, I know about QDialogButtonBox, but I'm not using PyQt4.2 here."""
    def __init__(self, parent = None):
        QHBoxLayout.__init__(self, parent)

        self.addStretch()

        self.ok = QPushButton("&OK")
        self.cancel = QPushButton("&Cancel")
        self.ok.setDefault(True)

        self.addWidget(self.ok)
        self.addWidget(self.cancel)

        self.connect(self.ok, SIGNAL("clicked()"), self.yes)
        self.connect(self.cancel, SIGNAL("clicked()"), self.no)

    def yes(self):
        self.emit(SIGNAL("ok"))

    def no(self):
        self.emit(SIGNAL("cancel"))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    listbox = ListBox()
    listbox.addItems([u'%artist% - $num(%track%, 2) - %title%', u'%artist% - %title%', u'%artist% - %album%', u'%artist% - Track %track%', u'%artist% - %title%', u'%artist%'])
    buttons = ListButtons()
    listbox.connectToListButtons(buttons)
    widget = QWidget()
    hbox = QHBoxLayout()
    hbox.addWidget(listbox)
    hbox.addLayout(buttons)
    widget.setLayout(hbox)
    widget.show()
    app.exec_()
