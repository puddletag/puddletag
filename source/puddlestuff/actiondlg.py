# -*- coding: utf-8 -*-
#actiondlg.py

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
from PyQt4 import QtGui, QtCore
import sys, findfunc, pdb, os, resource, string, functions
from copy import copy
from pyparsing import delimitedList, alphanums, Combine, Word, ZeroOrMore, \
                        QuotedString, Literal, NotAny, nums
import cPickle as pickle
from puddleobjects import ListBox, OKCancel, ListButtons, winsettings, gettaglist, settaglist
from findfunc import Function, runAction, runQuickAction
from puddleobjects import PuddleConfig, PuddleCombo
from audioinfo import REVTAGS, INFOTAGS, READONLY
from functools import partial
from constants import TEXT, COMBO, CHECKBOX
from util import open_resourcefile, PluginFunction

READONLY = list(READONLY) + ['__dirpath', ]

def displaytags(tags):
    if tags:
        s = u"<b>%s</b>: %s<br /> "
        ret = u"".join([s % (z, v) if isinstance(v, basestring) else 
            u'\\\\'.join(v) for z,v in sorted(tags.items()) 
            if z not in READONLY and z != u'__image'])[:-2]
        if u'__image' in tags:
            ret += u'<b>__image</b>: %s images<br />' % len(tags['__image'])
        return ret
    else:
        return '<b>No change.</b>'

class ScrollLabel(QScrollArea):
    def __init__(self, text = '', parent=None):
        QScrollArea.__init__(self, parent)
        label = QLabel()
        #self.setText = label.setText
        self.setWidget(label)
        self.setText(text)
        self.text = label.text
        label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        self.setFrameStyle(QFrame.NoFrame)
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def wheelEvent(self, e):
        h = self.horizontalScrollBar()
        if h.isVisible():
            numsteps = e.delta() / 5
            h.setValue(h.value() - numsteps)
            e.accept()
        else:
            QScrollArea.wheelEvent(self, e)
    
    def setText(self, text):
        label = self.widget()
        label.setText(text)
        height = label.sizeHint().height()
        self.setMaximumHeight(height)
        self.setMinimumHeight(height)

class FunctionDialog(QWidget):
    "A dialog that allows you to edit or create a Function class."
    controls = {'text': PuddleCombo, 'combo': QComboBox, 'check': QCheckBox}
    signals = {TEXT: SIGNAL('editTextChanged(const QString&)'),
                COMBO : SIGNAL('currentIndexChanged(int)'),
                CHECKBOX : SIGNAL('stateChanged(int)')}
    def __init__(self, funcname, showcombo = False, userargs = None, 
        defaulttags = None, parent = None, example = None, text = None):
        """funcname is name the function you want to use(can be either string, or functions.py function).
        if combotags is true then a combobox with tags that the user can choose from are shown.
        userargs is the default values you want to fill the controls in the dialog with
        [make sure they don't exceed the number of arguments of funcname]."""
        QWidget.__init__(self,parent)
        identifier = QuotedString('"') | Combine(Word(alphanums + ' !"#$%&\'()*+-./:;<=>?@[\\]^_`{|}~'))
        tags = delimitedList(identifier)
        self.func = Function(funcname)
        docstr = self.func.doc[1:]
        self.vbox = QVBoxLayout()
        self.retval = []
        self._combotags = []

        if showcombo:
            fields = ['__all'] + sorted(INFOTAGS) + showcombo
        else:
            fields = ['__selected', '__all'] + sorted(INFOTAGS)

        self.tagcombo = QComboBox()
        tooltip = "Fields that will get written to.<br /><br />"\
                    "Enter a list of comma-seperated fields eg. <b>artist, title, album</b>"
        self.tagcombo.setToolTip(tooltip)
        self.tagcombo.setEditable(True)
        self.tagcombo.addItems(fields)
        self._combotags = showcombo
        if defaulttags:
            index = self.tagcombo.findText(" , ".join(defaulttags))
            if index != -1:
                self.tagcombo.setCurrentIndex(index)
            else:
                self.tagcombo.insertItem(0, ", ".join(defaulttags))
                self.tagcombo.setCurrentIndex(0)
        self.connect(self.tagcombo, SIGNAL('editTextChanged(const QString&)'), self.showexample)

        if self.func.function.__name__ not in ['move', 'load_images']:
            self.vbox.addWidget(QLabel("Fields"))
            self.vbox.addWidget(self.tagcombo)
        self.example = example
        self._text = text

        self.textcombos = []
        #Loop that creates all the controls
        for argno, line in enumerate(docstr):
            args = tags.parseString(line)
            ctype = args[1]
            #Get the control

            if ctype == 'text':
                control = self.controls['text'](args[0], parent = self)
            else:
                control = self.controls[ctype](self)

            defaultarg = args[2:]

            #Create the controls with their default values
            #if default values have been defined, we set them.
            #self.retval contains the method to be called when we get
            #the value of the control
            if ctype == 'combo':
                self.retval.append(control.currentText)
                if defaultarg:
                    control.addItems(defaultarg)
                    if userargs:
                        index = control.findText(userargs[argno])
                        control.setCurrentIndex(index)
            elif ctype == 'text':
                self.textcombos.append(control)
                self.retval.append(control.combo.currentText)
                if defaultarg:
                    control.combo.setEditText(defaultarg[0])
                if userargs:
                    control.combo.setEditText(userargs[argno])
            elif ctype == 'check':
                self.retval.append(control.checkState)
                if defaultarg:
                    if defaultarg[0] == "True":
                        control.setCheckState(Qt.Checked)
                    else:
                        control.setCheckState(Qt.Unchecked)
                if userargs:
                    if userargs[argno]:
                        control.setCheckState(Qt.Checked)
                    else:
                        control.setCheckState(Qt.Unchecked)
                control.setText(args[0])

            if ctype != 'check':
                label = QLabel(args[0])
                label.setBuddy(control)
                self.vbox.addWidget(label)

            if self.example is not None:
                control.connect(control, self.signals[ctype], self.showexample)

            self.vbox.addWidget(control)
        self.vbox.addStretch()
        self.setLayout(self.vbox)
        self.setMinimumSize(self.sizeHint())

    def argValues(self):
        """Returns the values in the windows controls.
        The last argument is the tags value.
        Also sets self.func's arg and tag values."""
        newargs = []
        for method in self.retval:
            if method.__name__ == 'checkState':
                if method() == Qt.Checked:
                    newargs.append(True)
                elif (method() == Qt.PartiallyChecked) or (method() == Qt.Unchecked):
                    newargs.append(False)
            else:
                if isinstance(method(), (int, long)):
                    newargs.append(method())
                else:
                    newargs.append(unicode(method()))
        [z.save() for z in self.textcombos]
        self.func.setArgs(newargs)
        if hasattr(self, "tagcombo"):
            tags = [x for x in [z.strip().lower() for z in unicode(self.tagcombo.currentText()).split(",")] if z != ""]
            self.func.setTag(tags)
            return newargs + tags
        else:
            return newargs + [""]

    def showexample(self, *args, **kwargs):
        self.argValues()
        if self.example is not None:
            audio = self.example.stringtags()
            if not self._text:
                try:
                    if self.func.tag == [u'__all']:
                        text = 'Some random text, courtesy of puddletag.'
                    elif self.func.tag[0] == [u'__selected']:
                        text = audio.get(self.showcombo.keys()[0])
                    else:
                        text = audio.get(self.func.tag[0])
                except IndexError:
                    text = ''
                if not text:
                    text = u''
            else:
                text = self._text
            try:
                if self.func.funcname == 'Load Artwork':
                    self.emit(SIGNAL('updateExample'), 
                        'No preview for is shown for this function.')
                    return
                val = self.func.runFunction(text, audio)
            except findfunc.ParseError, e:
                val = u'<b>%s</b>' % (e.message)
            if val:
                self.emit(SIGNAL('updateExample'), val)
            else:
                self.emit(SIGNAL('updateExample'), '')

class CreateFunction(QDialog):
    """A dialog to allow the creation of functions using only one window and a QStackedWidget.
    For each function in functions, a dialog is created and displayed in the stacked widget."""
    def __init__(self, prevfunc = None, showcombo = True, parent = None, example = None, text = None):
        """tags is a list of the tags you want to show in the FunctionDialog.
        Each item should be in the form (DisplayName, tagname) as used in audioinfo.
        prevfunc is a Function object that is to be edited."""
        QDialog.__init__(self,parent)
        winsettings('createfunction', self)
        self.realfuncs = []
        #Get all the function from the functions module.
        for z, funcname in functions.functions.items():
            if isinstance(funcname, PluginFunction):
                self.realfuncs.append(funcname)
            elif callable(funcname) and (not (funcname.__name__.startswith("__") or (funcname.__doc__ is None))):
                self.realfuncs.append(z)

        funcnames = sorted([(Function(z).funcname, z) for z in  self.realfuncs])
        self.realfuncs = [z[1] for z in funcnames]

        self.vbox = QVBoxLayout()
        self.functions = QComboBox()
        self.functions.addItems([z[0] for z in funcnames])
        self.vbox.addWidget(self.functions)

        self.stack = QStackedWidget()
        self.vbox.addWidget(self.stack)
        self.okcancel = OKCancel()

        self.mydict = {}    #Holds the created windows in the form self.functions.index: window
        self.setLayout(self.vbox)
        self.setMinimumHeight(self.sizeHint().height())
        self.connect(self.okcancel, SIGNAL("ok"), self.okClicked)
        self.connect(self.okcancel, SIGNAL('cancel'), self.close)
        self.setWindowTitle("Format")
        self.example = example
        self._text = text
        if showcombo:
            self.showcombo = gettaglist()
        else:
            self.showcombo = showcombo
        self.exlabel = ScrollLabel('')

        if prevfunc is not None:
            index = self.functions.findText(prevfunc.funcname)
            if index >= 0:
                self.functions.setCurrentIndex(index)
                self.createWindow(index, prevfunc.args, prevfunc.tag)
        else:
            self.createWindow(0)

        self.connect(self.functions, SIGNAL("activated(int)"), self.createWindow)

        self.vbox.addWidget(self.exlabel)
        self.vbox.addLayout(self.okcancel)
        self.setLayout(self.vbox)

    def okClicked(self):
        w = self.stack.currentWidget()
        w.argValues()
        self.close()
        if self.showcombo:
            newtags = [z for z in w.func.tag if z not in self.showcombo]
            if newtags:
                settaglist(sorted(newtags + self.showcombo))
        self.emit(SIGNAL("valschanged"), w.func)

    def createWindow(self, index, defaultargs = None, defaulttags = None):
        """Creates a Function dialog in the stack window
        if it doesn't exist already."""
        self.stack.setFrameStyle(QFrame.Box)
        if index not in self.mydict:
            what = FunctionDialog(self.realfuncs[index], self.showcombo, defaultargs, defaulttags, example = self.example, text=self._text)
            self.mydict.update({index: what})
            self.stack.addWidget(what)
            if self.example:
                self.connect(what, SIGNAL('updateExample'), self.updateExample)
                what.showexample()
        self.stack.setCurrentWidget(self.mydict[index])
        self.setMinimumHeight(self.sizeHint().height())
        if self.sizeHint().width() > self.width():
            self.setMinimumWidth(self.sizeHint().width())

    def updateExample(self, text):
        if not text:
            self.exlabel.setText('')
        else:
            if isinstance(text, basestring):
                self.exlabel.setText(text)
            else:
                self.exlabel.setText(displaytags(text))
        QApplication.processEvents()

class CreateAction(QDialog):
    "An action is defined as a collection of functions. This dialog serves the purpose of creating an action"
    def __init__(self, parent = None, prevfunctions = None, example = None):
        """tags is a list of the tags you want to show in the FunctionDialog.
        Each item should be in the form (DisplayName, tagname as used in audioinfo).
        prevfunction is the previous function that is to be edited."""
        QDialog.__init__(self, parent)
        self.setWindowTitle("Modify Action")
        winsettings('editaction', self)
        self.grid = QGridLayout()

        self.listbox = ListBox()
        self.functions = []
        self.buttonlist = ListButtons()
        self.grid.addWidget(self.listbox, 0, 0)
        self.grid.addLayout(self.buttonlist, 0, 1)

        self.okcancel = OKCancel()
        #self.grid.addLayout(self.okcancel,1,0,1,2)
        self.setLayout(self.grid)
        self.example = example

        self.connect(self.okcancel, SIGNAL("cancel"), self.close)
        self.connect(self.okcancel, SIGNAL("ok"), self.okClicked)
        self.connect(self.buttonlist, SIGNAL("add"), self.add)
        self.connect(self.buttonlist, SIGNAL("edit"), self.edit)
        self.connect(self.buttonlist, SIGNAL("moveup"), self.moveUp)
        self.connect(self.buttonlist, SIGNAL("movedown"), self.moveDown)
        self.connect(self.buttonlist, SIGNAL("remove"), self.remove)
        self.connect(self.buttonlist, SIGNAL("duplicate"), self.duplicate)
        self.connect(self.listbox, SIGNAL("currentRowChanged(int)"), self.enableOK)
        self.connect(self.listbox, SIGNAL("itemDoubleClicked (QListWidgetItem *)"), self.edit)

        if prevfunctions is not None:
            self.functions = copy(prevfunctions)
            self.listbox.addItems([function.description() for function in self.functions])

        if example:
            self._examplelabel = ScrollLabel('')
            self.grid.addWidget(self._examplelabel,1,0)
            self.grid.setRowStretch(0,1)
            self.grid.setRowStretch(1,0)
            self._example = example
            self.updateExample()
            self.grid.addLayout(self.okcancel,2,0,1,2)
        else:
            self.grid.addLayout(self.okcancel,1,0,1,2)

    def updateExample(self):
        try:
            tags = runAction(self.functions, self._example)
            self._examplelabel.setText(displaytags(tags))
        except findfunc.ParseError, e:
            self._examplelabel.setText(e.message)

    def enableOK(self, val):
        if val == -1:
            [button.setEnabled(False) for button in self.buttonlist.widgets[1:]]
        else:
            [button.setEnabled(True) for button in self.buttonlist.widgets[1:]]

    def moveDown(self):
        self.listbox.moveDown(self.functions)

    def moveUp(self):
        self.listbox.moveUp(self.functions)

    def remove(self):
        self.listbox.removeSelected(self.functions)
        self.updateExample()

    def add(self):
        self.win = CreateFunction(None, parent = self, example = self.example)
        self.win.setModal(True)
        self.win.show()
        self.connect(self.win, SIGNAL("valschanged"), self.addBuddy)

    def edit(self):
        self.win = CreateFunction(self.functions[self.listbox.currentRow()], self, example = self.example)
        self.win.setModal(True)
        self.win.show()
        self.connect(self.win, SIGNAL("valschanged"), self.editBuddy)

    def editBuddy(self, func):
        self.listbox.currentItem().setText(func.description())
        self.functions[self.listbox.currentRow()] = func
        self.updateExample()

    def addBuddy(self, func):
        self.listbox.addItem(func.description())
        self.functions.append(func)
        self.updateExample()

    def okClicked(self):
        self.close()
        self.emit(SIGNAL("donewithmyshit"), self.functions)

    def duplicate(self):
        self.win = CreateFunction(self.functions[self.listbox.currentRow()], self, example = self.example)
        self.win.setModal(True)
        self.win.show()
        self.connect(self.win, SIGNAL("valschanged"), self.addBuddy)

class ActionWindow(QDialog):
    """Just a dialog that allows you to add, remove and edit actions
    On clicking OK, a signal "donewithmyshit" is emitted.
    It returns a list of lists.
    Each element of a list contains one complete action. While
    the elements of that action are just normal Function objects."""
    def __init__(self, parent = None, example = None, quickaction = None):
        """tags are the tags to be shown in the FunctionDialog"""
        QDialog.__init__(self,parent)
        self.setWindowTitle("Actions")
        winsettings('actions', self)
        self._quickaction = quickaction
        self.listbox = ListBox()
        self.listbox.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.example = example

        self.funcs = self.loadActions()
        cparser = PuddleConfig()
        to_check = cparser.get('actions', 'checked', [])
        for z in self.funcs:
            func_name = self.funcs[z][1]
            item = QListWidgetItem(func_name)
            if func_name in to_check:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
            self.listbox.addItem(item)

        self.okcancel = OKCancel()
        self.okcancel.ok.setDefault(True)
        self.grid = QGridLayout()

        self.buttonlist = ListButtons()

        self.grid.addWidget(self.listbox,0, 0)
        self.grid.setRowStretch(0, 1)
        self.grid.addLayout(self.buttonlist, 0,1)
        self.setLayout(self.grid)

        self.connect(self.okcancel, SIGNAL("ok") , self.okClicked)
        self.connect(self.okcancel, SIGNAL("cancel"),self.close)
        self.connect(self.buttonlist, SIGNAL("add"), self.add)
        self.connect(self.buttonlist, SIGNAL("edit"), self.edit)
        self.connect(self.buttonlist, SIGNAL("moveup"), self.moveUp)
        self.connect(self.buttonlist, SIGNAL("movedown"), self.moveDown)
        self.connect(self.buttonlist, SIGNAL("remove"), self.remove)
        self.connect(self.buttonlist, SIGNAL("duplicate"), self.duplicate)
        self.connect(self.listbox, SIGNAL("itemDoubleClicked (QListWidgetItem *)"), self.edit)
        self.connect(self.listbox, SIGNAL("currentRowChanged(int)"), self.enableListButtons)
        self.connect(self.listbox, SIGNAL("itemChanged(QListWidgetItem *)"), self.enableOK)

        if example:
            self._examplelabel = ScrollLabel('')
            self.grid.addWidget(self._examplelabel, 1, 0, 1,-1)
            self.grid.setRowStretch(1, 0)
            self._example = example
            self.connect(self.listbox, SIGNAL('itemChanged (QListWidgetItem *)'),
                                self.updateExample)
            self.grid.addLayout(self.okcancel,2,0,1,2)
            self.updateExample()
        else:
            self.grid.addLayout(self.okcancel,1,0,1,2)
        self.enableOK(None)

    def moveUp(self):
        self.listbox.moveUp(self.funcs)

    def moveDown(self):
        self.listbox.moveDown(self.funcs)

    def remove(self):
        cparser = PuddleConfig()
        filedir = os.path.dirname(cparser.filename)
        listbox = self.listbox
        rows = sorted([listbox.row(item) for item in listbox.selectedItems()])
        for row in rows:
            name = self.funcs[row][1]
            filename = os.path.join(filedir, self.removeSpaces(name) + u'.action')
            os.rename(filename, filename + '.deleted')
        self.listbox.removeSelected(self.funcs)

    def enableListButtons(self, val):
        if val == -1:
            [button.setEnabled(False) for button in self.buttonlist.widgets[1:]]
        else:
            [button.setEnabled(True) for button in self.buttonlist.widgets[1:]]


    def enableOK(self, val):
        item = self.listbox.item
        enable = [row for row in range(self.listbox.count()) if
                    item(row).checkState() == Qt.Checked]
        if enable:
            self.okcancel.ok.setEnabled(True)
        else:
            self.okcancel.ok.setEnabled(False)

    def loadActions(self):
        funcs = {}

        cparser = PuddleConfig()
        firstrun = cparser.load('puddleactions', 'firstrun', 0, True)
        filedir = os.path.dirname(cparser.filename)
        from glob import glob
        files = glob(os.path.join(filedir, u'*.action'))
        if not firstrun and not files:
            import StringIO
            files = [open_resourcefile(filename)
                        for filename in [':/caseconversion.action', ':/standard.action']]
            cparser.setSection('puddleactions', 'firstrun',1)

            for i, f in enumerate(files):
                funcs[i] = findfunc.getAction(f)
                self.saveAction(funcs[i][1], funcs[i][0])
        else:
            order = cparser.load('puddleactions', 'order', [])
            files = [z for z in order if z in files] + [z for z in files if z not in order]
            for i, f in enumerate(files):
                funcs[i] = findfunc.getAction(f)
        return funcs

    def updateExample(self, *args):
        l = self.listbox
        items = [l.item(z) for z in range(l.count())]
        selectedrows = [i for i,z in enumerate(items) if z.checkState() == Qt.Checked]
        if selectedrows:
            tempfuncs = [self.funcs[row][0] for row in selectedrows]
            funcs = []
            [funcs.extend(func) for func in tempfuncs]
            try:
                if self._quickaction:
                    tags = runQuickAction(funcs, self._example, self._quickaction)
                else:
                    tags = runAction(funcs, self._example)
                self._examplelabel.show()
                self._examplelabel.setText(displaytags(tags))
            except findfunc.ParseError, e:
                self._examplelabel.show()
                self._examplelabel.setText(e.message)
        else:
            self._examplelabel.hide()

    def removeSpaces(self, text):
        for char in string.whitespace:
            text = text.replace(char, '')
        return text.lower()

    def saveAction(self, name, funcs):
        cparser = PuddleConfig()
        filedir = os.path.dirname(cparser.filename)
        filename = os.path.join(filedir, self.removeSpaces(name) + u'.action')
        findfunc.saveAction(filename, name, funcs)

    def add(self):
        (text, ok) = QInputDialog.getText (self, "New Configuration", "Enter a name for the new action.", QLineEdit.Normal)
        if (ok is True) and (text != ""):
            item = QListWidgetItem(text)
            item.setCheckState(Qt.Unchecked)
            self.listbox.addItem(item)
        else:
            return
        win = CreateAction(self, example = self.example)
        win.setWindowTitle("Edit Action: " + self.listbox.item(self.listbox.count() - 1).text())
        win.setModal(True)
        win.show()
        self.connect(win, SIGNAL("donewithmyshit"), self.addBuddy)

    def addBuddy(self, funcs):
        name = unicode(self.listbox.item(self.listbox.count() - 1).text())
        self.funcs.update({self.listbox.count() - 1: [funcs, name]})
        self.saveAction(name, funcs)

    def edit(self):
        win = CreateAction(self, self.funcs[self.listbox.currentRow()][0], example = self.example)
        win.setWindowTitle("Edit Action: " + self.listbox.currentItem().text())
        win.show()
        self.connect(win, SIGNAL("donewithmyshit"), self.editBuddy)

    def editBuddy(self, funcs):
        self.saveAction(self.funcs[self.listbox.currentRow()][1], funcs)
        self.funcs[self.listbox.currentRow()][0] = funcs
        self.updateExample()

    def close(self):
        order = [unicode(self.listbox.item(row).text()) for row in
                                                xrange(self.listbox.count())]
        cparser = PuddleConfig()
        filedir = os.path.dirname(cparser.filename)
        filenames = [os.path.join(filedir,self.removeSpaces(z) + u'.action') for z in order]
        cparser.setSection('puddleactions', 'order', filenames)
        QDialog.close(self)

    def okClicked(self):
        """When clicked, save the current contents of the listbox and the associated functions"""
        l = self.listbox
        items = [l.item(z) for z in range(l.count())]
        selectedrows = [i for i,z in enumerate(items) if z.checkState() == Qt.Checked]
        tempfuncs = [self.funcs[row][0] for row in selectedrows]
        names = [self.funcs[row][1] for row in selectedrows]
        funcs = []
        [funcs.extend(func) for func in tempfuncs]
        cparser = PuddleConfig()
        cparser.set('actions', 'checked', names)
        self.close()
        self.emit(SIGNAL("donewithmyshit"), funcs)

    def duplicate(self):
        l = self.listbox
        if len(l.selectedItems()) > 1:
            return
        row = l.currentRow()
        oldname = self.funcs[row][1]
        (text, ok) = QInputDialog.getText (self, "Copy %s action" % oldname,
                        "Enter a name for the new action.", QLineEdit.Normal)
        if not (ok and text):
            return
        funcs = copy(self.funcs[row][0])
        name = unicode(text)
        win = CreateAction(self, funcs, example = self.example)
        win.setWindowTitle("Edit Action: %s" % name)
        win.show()
        dupebuddy = partial(self.duplicateBuddy, name)
        self.connect(win, SIGNAL("donewithmyshit"), dupebuddy)

    def duplicateBuddy(self, name, funcs):
        item = QListWidgetItem(name)
        item.setCheckState(Qt.Unchecked)
        self.listbox.addItem(item)
        self.funcs.update({self.listbox.count() - 1: [funcs, name]})
        self.saveAction(name, funcs)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setOrganizationName("Puddle Inc.")
    app.setApplicationName("puddletag")
    qb = ActionWindow([(u'Path', u'__path'), ('Artist', 'artist'), ('Title', 'title'), ('Album', 'album'), ('Track', 'track'), ('Length', '__length'), (u'Year', u'date')])
    qb.show()
    app.exec_()
