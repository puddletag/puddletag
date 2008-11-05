#!/usr/bin/env python 
"""See each class's docstring for information on it.
"""

"""
actiondlg.py

Copyright (C) 2008 concentricpuddle

This file is part of puddletag, a semi-good music tag editor.

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""

from PyQt4.QtGui import *
from PyQt4.QtCore import *
from PyQt4 import QtGui
import sys, findfunc, pdb, os, resource
import functions
from copy import copy
from pyparsing import delimitedList, alphanums, Combine, Word, ZeroOrMore, QuotedString, Literal, NotAny, nums
import cPickle as pickle
from puddleobjects import ListBox, OKCancel, ButtonLayout

class Function:
    """Basically, a wrapper for functions, but makes it easier to
    call according to the needs of puddletag.
    Methods of importance are:
    
    description -> Returns the parsed description of the function.
    setArgs -> Sets the 2nd to last arguments that the function is to be called with.
    runFunction(arg1) -> Run the function with arg1 as the first argument.
    setTag -> Sets the tag of the function for editing of tags.
    
    self.info is a tuple with the first element is the function name form the docstring.
    The second element is the description in unparsed format.
    
    See the functions module for more info."""
    
    def __init__(self, funcname):
        """funcname must be either a function or string(which is the functions name)."""        
        if type(funcname) is str:
            self.function = getattr(functions, funcname)
        else:
            self.function = funcname
            
        self.reInit()
        
        self.funcname = self.info[0]
        self.tag = ""
            
    def reInit(self):
        #Since this class gets pickled in ActionWindow, the class is never 'destroyed'
        #Therefore, if a functions docstring was changed, it wouldn't be reflected back
        #to puddletag. So this function is called here and in description just to 're-read'
        #the docstring
        self.doc = self.function.__doc__.split("\n")
        
        identifier = QuotedString('"') | Combine(Word(alphanums + ' !"#$%&\'()*+-./:;<=>?@[\\]^_`{|}~'))
        tags = delimitedList(identifier)
        
        self.info = [z for z in tags.parseString(self.doc[0])]
        
    def setArgs(self, args):
        self.args = args
    
    def runFunction (self, arg1):
        return self.function(*([arg1] + self.args))
    
    def description(self):
        
        def what (s,loc,tok):
            if long(tok[0]) == 0:
                return ", ".join(self.tag)
            return self.args[long(tok[0]) - 1]
        
        self.reInit()
        foo = Combine(NotAny("\\").suppress() + Literal("$").suppress() + Word(nums)).setParseAction(what)        
        return foo.transformString(self.info[1])
    
    def setTag(self, tag):
        self.tag = tag
    
    def addArg(self, arg):
        if self.function.func_code.co_argcount > len(self.args) + 1:
            self.args.append(arg)
        

class FunctionDialog(QDialog):
    "A dialog that allows you to edit or create a Function class."
    def __init__(self, funcname, showcombo = False, defaultargs = None, defaulttags = None, parent = None):
        """funcname is name the function you want to use(can be either string, or functions.py function).
        if combotags is true then a combobox with tags that the user can choose from are shown.
        defaultargs is the default values you want to fill the controls in the dialog with[make sure they don't exceed the number of arguments of funcname]."""
        QDialog.__init__(self,parent)
        identifier = QuotedString('"') | Combine(Word(alphanums + ' !"#$%&\'()*+-./:;<=>?@[\\]^_`{|}~'))
        tags = delimitedList(identifier)
        self.func = Function(funcname)
        docstr = self.func.doc[1:]
        self.vbox = QVBoxLayout()
        self.retval = []        
        
        if showcombo:
            self.tagcombo = QComboBox()
            self.tagcombo.setEditable(True)
            from audioinfo import REVTAGS
            self.tagcombo.addItems(["__all"] + sorted([z for z in REVTAGS]))
            if defaulttags:
                index = self.tagcombo.findText(" | ".join(defaulttags))
                if index != -1:                    
                    self.tagcombo.setCurrentIndex(index)
                else:
                    self.tagcombo.insertItem(0, " | ".join(defaulttags))
                    self.tagcombo.setCurrentIndex(0)
            
            self.vbox.addWidget(QLabel("Tags"))
            self.vbox.addWidget(self.tagcombo)

        i = 0        
        #Loop that creates all the controls        
        for line in docstr:
            args = tags.parseString(line)            
            #Get the control
            try:
                control = getattr(QtGui, args[1])(self)
            except IndexError:
                sys.stderr.write("The function isn't defined correctly, I'll continue anyway.")                        
            
            try:
                defaultarg = args[2:]
            except IndexError:
                defaultarg = None
                                        
            #Create the controls with their default values
            #if default values have been defined, we set them.
            #self.retval contains the method to be called when we get
            #the value of the control
            if type(control) == QComboBox:
                self.retval.append(control.currentText)
                if (defaultarg is not None) and (defaultarg != []) :
                    control.addItems(defaultarg)
                    if defaultargs is not None:
                        index = control.findText(defaultargs[i])
                        if index >= 0:
                            control.setCurrentIndex(index)
                label = QLabel(args[0])
                self.vbox.addWidget(label)
            elif type(control) == QLineEdit:
                self.retval.append(control.text)
                if (defaultarg is not None) and (defaultarg != []):
                    control.setText(defaultarg[0])
                if defaultargs is not None:                    
                    control.setText(defaultargs[i])
                label = QLabel(args[0])
                self.vbox.addWidget(label)
            elif type(control) == QCheckBox:
                self.retval.append(control.checkState)
                if (defaultarg is not None) and (defaultarg != []):
                    if defaultarg[2] == "True":
                        control.setCheckState(Qt.Checked)
                    else:
                        control.setCheckState(Qt.Unchecked)
                if defaultargs is not None:
                    if defaultargs[i] is True:
                        control.setCheckState(Qt.Checked)
                    else:
                        control.setCheckState(Qt.Unchecked)
                control.setText(args[0])
            self.vbox.addWidget(control)
            i += 1
        self.vbox.addStretch()
        self.setLayout(self.vbox)
        self.setMinimumSize(self.sizeHint())
    
    def argValues(self):
        """Returns the values in the windows controls.
        The last argument is the tags value.
        Also sets self.func's arg and tag values."""
        newargs = []
        for method in self.retval:
            if method() == Qt.Checked:
                newargs.append(True) 
            elif (method() == Qt.PartiallyChecked) or (method() == Qt.Unchecked):
                newargs.append(False)
            else:
                newargs.append(unicode(method()))                            
        
        self.func.setArgs(newargs)
        if hasattr(self, "tagcombo"):
            tags = [x for x in [z.strip() for z in unicode(self.tagcombo.currentText()).split("|")] if z != ""]
            self.func.setTag(tags)
            return newargs + tags
        else:
            return newargs + [""]
    
    

class CreateFunction(QDialog):
    """A dialog to allow the creation of functions using only one window and a QStackedWidget.
    For each function in functions, a dialog is created and displayed in the stacked widget."""
    def __init__(self, tags = None, prevfunc = None, showcombo = True, parent = None):
        """tags is a list of the tags you want to show in the FunctionDialog.
        Each item should be in the form (DisplayName, tagname) as used in audioinfo.
        prevfunc is a Function object that is to be edited."""
        QDialog.__init__(self,parent)
        self.tags = tags        
        self.funcnames = []
        #Get all the function from the functions module.
        for z in dir(functions):
            funcname = getattr(functions,z)
            if callable(funcname) and (not (funcname.__name__.startswith("__") or (funcname.__doc__ is None))):
                self.funcnames.append(z)
                
        self.funcnames.sort()
        self.vbox = QVBoxLayout()
        self.functions = QComboBox()
        for z in self.funcnames:
            func = Function(z)
            self.functions.addItem(func.funcname)        
        self.vbox.addWidget(self.functions)
        
        self.stack = QStackedWidget()
        self.vbox.addWidget(self.stack)
        
        self.hbox = QHBoxLayout()
        self.ok = QPushButton("OK")
        self.cancel = QPushButton("Cancel")        
        self.hbox.addStretch()
        self.hbox.addWidget(self.ok)
        self.hbox.addWidget(self.cancel)
        
        self.vbox.addLayout(self.hbox)
        self.mydict = {}    #Holds the created windows in the form self.functions.index: window
        self.ok.setEnabled(False)
        self.setLayout(self.vbox)
        self.setMinimumHeight(self.sizeHint().height())
        self.connect(self.ok, SIGNAL("clicked()"), self.okClicked)
        self.connect(self.cancel, SIGNAL("clicked()"), self.close)
        self.setWindowTitle("Format")
        
        self.showcombo = showcombo
        #pdb.set_trace()
        if prevfunc is not None:
            index = self.functions.findText(prevfunc.funcname)
            if index >= 0:
                self.functions.setCurrentIndex(index)
                self.createWindow(index, prevfunc.args, prevfunc.tag)
        
        self.connect(self.functions, SIGNAL("activated(int)"), self.createWindow)
    
    def okClicked(self):
        self.stack.currentWidget().argValues()
        self.emit(SIGNAL("valschanged"), self.stack.currentWidget().func)
        self.close()
        
    def createWindow(self, index, defaultargs = None, defaulttags = None):
        """Creates a Function dialog in the stack window
        if it doesn't exist already."""
        self.stack.setFrameStyle(QFrame.Box)
        if index not in self.mydict:
            what = FunctionDialog(self.funcnames[index], self.showcombo, defaultargs, defaulttags)
            self.mydict.update({index: what})
            self.stack.addWidget(what)
        self.stack.setCurrentWidget(self.mydict[index])
        self.setMinimumHeight(self.sizeHint().height())
        if self.sizeHint().width() > self.width():
            self.setMinimumWidth(self.sizeHint().width())
        self.ok.setEnabled(True)


class CreateAction(QDialog):
    "An action is defined as a collection of functions. This dialog serves the purpose of creating an action"
    def __init__(self, tags = None, parent = None, prevfunctions = None):
        """tags is a list of the tags you want to show in the FunctionDialog.
        Each item should be in the form (DisplayName, tagname as used in audioinfo).
        prevfunction is the previous function that is to be edited."""
        QDialog.__init__(self,parent)    
        self.setWindowTitle("Modify Action")
        self.tags = tags
        self.grid = QGridLayout()
        
        self.listbox = ListBox()
        self.functions = []
        self.buttonlist = ButtonLayout()
        self.grid.addWidget(self.listbox, 0, 0)
        self.grid.addLayout(self.buttonlist, 0, 1)
        
        self.ok = QPushButton("OK")
        self.ok.setDefault(True)
        self.cancel = QPushButton("Cancel")
                
        self.hbox = QHBoxLayout()
        self.hbox.addStretch()
        self.hbox.addWidget(self.ok)
        self.hbox.addWidget(self.cancel)
        
        
        self.grid.addLayout(self.hbox,1,0,1,2)
        self.setLayout(self.grid)
        
        clicked = SIGNAL("clicked()")
        self.connect(self.cancel, clicked, self.close)
        self.connect(self.ok, clicked, self.okClicked)
        self.connect(self.buttonlist, SIGNAL("add"), self.add)
        self.connect(self.buttonlist, SIGNAL("edit"), self.edit)
        self.connect(self.buttonlist, SIGNAL("moveup"), self.moveUp)
        self.connect(self.buttonlist, SIGNAL("movedown"), self.moveDown)
        self.connect(self.buttonlist, SIGNAL("remove"), self.remove)
        self.connect(self.listbox, SIGNAL("currentRowChanged(int)"), self.enableOK)
                
        if prevfunctions is not None:
            self.functions = copy(prevfunctions)
            self.listbox.addItems([function.description() for function in self.functions])
        
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
        
    def add(self):
        self.win = CreateFunction(self.tags, None, self)
        self.win.setModal(True)
        self.win.show()
        self.connect(self.win, SIGNAL("valschanged"), self.addBuddy)
    
    def edit(self):
        self.win = CreateFunction(self.tags, self.functions[self.listbox.currentRow()], self)
        self.win.setModal(True)
        self.win.show()
        self.connect(self.win, SIGNAL("valschanged"), self.editBuddy)
    
    def editBuddy(self, func):
        self.listbox.currentItem().setText(func.description())
        self.functions[self.listbox.currentRow()] = func
    
    def addBuddy(self, func):
        self.listbox.addItem(func.description())
        self.functions.append(func)
    
    def okClicked(self):
        self.emit(SIGNAL("donewithmyshit"), self.functions)
        self.close()        

        
class ActionWindow(QDialog):
    """Just a dialog that allows you to add, remove and edit actions
    On clicking OK, a signal "donewithmyshit" is emitted.
    It returns a list of lists.
    Each element of a list contains one complete action. While
    the elements of that action are just normal Function objects."""
    def __init__(self, tags, parent = None):
        """tags are the tags to be shown in the FunctionDialog"""
        QDialog.__init__(self,parent)
        settings = QSettings()
        path = os.path.dirname(unicode(settings.fileName()))
        self.funcs = {}
        self.setWindowTitle("Actions")
        self.tags = tags
        self.listbox = ListBox()
        self.listbox.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        self.okcancel = OKCancel()
        self.okcancel.ok.setDefault(True)
        self.grid = QGridLayout()
        
        self.buttonlist = ButtonLayout()
        
        self.grid.addWidget(self.listbox,0,0)
        self.grid.addLayout(self.buttonlist, 0,1)
        self.grid.addLayout(self.okcancel,1,0,1,2)
        
        self.setLayout(self.grid)
        
        self.connect(self.okcancel, SIGNAL("ok") , self.okClicked)
        self.connect(self.okcancel, SIGNAL("cancel"),self.close)
        self.connect(self.buttonlist, SIGNAL("add"), self.add)
        self.connect(self.buttonlist, SIGNAL("edit"), self.edit)
        self.connect(self.buttonlist, SIGNAL("moveup"), self.moveUp)
        self.connect(self.buttonlist, SIGNAL("movedown"), self.moveDown)
        self.connect(self.buttonlist, SIGNAL("remove"), self.remove)
        self.connect(self.listbox, SIGNAL("itemDoubleClicked (QListWidgetItem *)"), self.okClicked)
        #Load previous actions
        try:
            f = open(os.path.join(path, "actions"), "rb")
            self.funcs = pickle.load(f)
            #Add function names to listbox
            self.listbox.addItems([self.funcs[z][1] for z in sorted(self.funcs)])
            f.close()
        except (IOError, ImportError):
            import StringIO
            f = StringIO.StringIO(QFile(":/actions").readData(1024**2))
            self.funcs = pickle.load(f)
            self.listbox.addItems([self.funcs[z][1] for z in sorted(self.funcs)])
        except EOFError: f.close()
        
        self.connect(self.listbox, SIGNAL("currentRowChanged(int)"), self.enableOK)
    
    def moveUp(self):
        self.listbox.moveUp(self.funcs)        
        
    def moveDown(self):
        self.listbox.moveDown(self.funcs)
        
    def remove(self):
        self.listbox.removeSelected(self.funcs)        
                    
    def enableOK(self, val):
        if val == -1:
            [button.setEnabled(False) for button in self.buttonlist.widgets[1:]]
            self.okcancel.ok.setEnabled(False)
        else:
            [button.setEnabled(True) for button in self.buttonlist.widgets[1:]]
            self.okcancel.ok.setEnabled(True)    
    
    def okClicked(self):
        """When clicked, save the current contents of the listbox and the associated functions"""
        settings = QSettings()
        path = os.path.dirname(unicode(settings.fileName()))
        f = open(os.path.join(path, "actions"), "wb")
        pickle.dump(self.funcs, f)
        f.close()
        selectedrows = [self.listbox.row(item) for item in self.listbox.selectedItems()]
        self.emit(SIGNAL("donewithmyshit"), [self.funcs[row][0] for row in selectedrows])
        self.close()
        
    def add(self):
        what = QInputDialog.getText (self, "New Configuration", "Enter a name for the new action.", QLineEdit.Normal)
        if (what[1] is True) and (what[0] != ""):
            self.listbox.addItem(what[0])
        else:
            return
        win = CreateAction(self.tags, self)
        win.setWindowTitle("Edit Action: " + self.listbox.item(self.listbox.count() - 1).text())
        win.setModal(True)
        win.show()
        self.connect(win, SIGNAL("donewithmyshit"), self.addBuddy)
    
    def addBuddy(self, functions):
        itemtext = unicode(self.listbox.item(self.listbox.count() - 1).text())
        self.funcs.update({self.listbox.count() - 1: [functions, itemtext]})

    def edit(self): 
        win = CreateAction(self.tags, self, self.funcs[self.listbox.currentRow()][0])
        win.setWindowTitle("Edit Action: " + self.listbox.currentItem().text())
        win.show()
        self.connect(win, SIGNAL("donewithmyshit"), self.editBuddy)
    
    def editBuddy(self, funcs):
        self.funcs[self.listbox.currentRow()][0] = funcs

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setOrganizationName("Puddle Inc.")
    app.setApplicationName("puddletag")
    qb = ActionWindow([(u'Path', u'__path'), ('Artist', 'artist'), ('Title', 'title'), ('Album', 'album'), ('Track', 'track'), ('Length', '__length'), (u'Year', u'date')])
    qb.show()
    app.exec_()