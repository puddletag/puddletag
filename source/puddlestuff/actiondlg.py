# -*- coding: utf-8 -*-
import os
import string
import sys
from copy import copy, deepcopy
from functools import partial

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QAbstractItemView, QAction, QApplication, QCheckBox, QComboBox, QCompleter, \
    QDialog, QFrame, QGridLayout, QInputDialog, QLabel, QLineEdit, QListWidgetItem, QMenu, QMessageBox, \
    QScrollArea, QSizePolicy, QSpinBox, QStackedWidget, QToolButton, QVBoxLayout, QWidget
from pyparsing import delimitedList, alphanums, Combine, Word, QuotedString

from . import findfunc, functions
from . import functions_dialogs
from .audioinfo import INFOTAGS, READONLY
from .constants import (TEXT, COMBO, CHECKBOX, SAVEDIR, CONFIGDIR, ACTIONDIR)
from .findfunc import Function, apply_macros, apply_actions, Macro
from .puddleobjects import (ListBox, OKCancel, ListButtons, winsettings, gettaglist, settaglist, safe_name, open_resourcefile)
from .puddleobjects import PuddleConfig, PuddleCombo
from .puddleobjects import ShortcutEditor
from .util import (PluginFunction, translate, pprint_tag)

READONLY = list(READONLY)
FUNC_SETTINGS = os.path.join(CONFIGDIR, 'function_settings')

FIELDS_TOOLTIP = translate('Functions Dialog',
                           """<p>Fields that will
                           get written to.</p>
                       
                           <ul>
                           <li>Enter a list of comma-separated fields
                           eg. <b>artist, title, album</b></li>
                           <li>Use <b>__selected</b> to write only to the selected cells.
                           It is not allowed when creating an action.</li>
                           <li>Combinations like <b>__selected, artist, title</b> are
                           allowed.</li>
                           <li>But using <b>__selected</b> in Actions is <b>not</b>.</li>
                           <li>'~' will write to all the the fields, except what follows it
                           . Eg <b>~artist, title</b> will write to all but the artist and
                           title fields found in the selected files.<li>
                           </ul>""")


def displaytags(tags):
    text = pprint_tag(tags)
    if not text:
        return translate('Functions Dialog', '<b>No change.</b>')

    if text.endswith('<br />'):
        text = text[:-len('<br />')]
    return text


class ShortcutDialog(QDialog):
    shortcutChanged = pyqtSignal(str, name='shortcutChanged')

    def __init__(self, shortcuts=None, parent=None):
        super(ShortcutDialog, self).__init__(parent)
        self.setWindowTitle('puddletag')
        self.ok = False
        label = QLabel(translate('Shortcut Editor', 'Enter a key sequence for the shortcut.'))
        self._text = ShortcutEditor(shortcuts)

        okcancel = OKCancel()
        okcancel.cancelButton.setText(translate('Shortcut Editor', "&Don't assign keyboard shortcut."))
        okcancel.okButton.setEnabled(False)

        okcancel.ok.connect(self.okClicked)
        okcancel.cancel.connect(self.close)

        self._text.validityChanged.connect(okcancel.okButton.setEnabled)

        vbox = QVBoxLayout()
        vbox.addWidget(label)
        vbox.addWidget(self._text)
        vbox.addLayout(okcancel)
        vbox.addStretch()
        self.setLayout(vbox)

        self._shortcuts = shortcuts

    def okClicked(self):
        self.shortcutChanged.emit(str(self._text.text()))
        self.ok = True
        self.close()

    def getShortcut(self):
        self.exec_()
        if self._text.valid:
            return str(self._text.text()), self.ok
        else:
            return '', self.ok


class ShortcutName(QDialog):
    def __init__(self, texts, default='', parent=None):
        super(ShortcutName, self).__init__(parent)
        self.setWindowTitle('puddletag')
        self.ok = False
        self._texts = texts
        label = QLabel(translate('Actions', 'Enter a name for the shortcut.'))
        self._text = QLineEdit(default)

        okcancel = OKCancel()
        self._ok = okcancel.okButton
        self.enableOK(self._text.text())

        okcancel.ok.connect(self.okClicked)
        okcancel.cancel.connect(self.close)

        self._text.textChanged.connect(self.enableOK)

        vbox = QVBoxLayout()
        vbox.addWidget(label)
        vbox.addWidget(self._text)
        vbox.addLayout(okcancel)
        vbox.addStretch()
        self.setLayout(vbox)

    def okClicked(self):
        self.ok = True
        self.close()

    def enableOK(self, text):
        if text and str(text) not in self._texts:
            self._ok.setEnabled(True)
        else:
            self._ok.setEnabled(False)

    def getText(self):
        self.exec_()
        return str(self._text.text()), self.ok


class ScrollLabel(QScrollArea):
    def __init__(self, text='', parent=None):
        QScrollArea.__init__(self, parent)
        label = QLabel()
        label.setMargin(3)
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
            numsteps = e.angleDelta().y() / 5
            h.setValue(h.value() - numsteps)
            e.accept()
        else:
            QScrollArea.wheelEvent(self, e)

    def setText(self, text):
        label = self.widget()
        label.setText(text)
        hbar = self.horizontalScrollBar()
        height = label.sizeHint().height() + hbar.height()
        self.setMaximumHeight(height)
        self.setMinimumHeight(height)


class FunctionDialog(QWidget):
    "A dialog that allows you to edit or create a Function class."

    _controls = {'text': PuddleCombo, 'combo': QComboBox, 'check': QCheckBox}

    signals = {
        TEXT: 'editTextChanged',
        COMBO: 'currentIndexChanged',
        CHECKBOX: 'stateChanged',
    }

    updateExample = pyqtSignal(object, name='updateExample')

    def __init__(self, funcname, selected_fields=False, userargs=None,
                 default_fields=None, parent=None, example=None, text=None):
        """funcname is name the function you want to use(can be either string, or functions.py function).
        if combotags is true then a combobox with tags that the user can choose from are shown.
        userargs is the default values you want to fill the controls in the dialog with
        [make sure they don't exceed the number of arguments of funcname]."""
        QWidget.__init__(self, parent)
        identifier = QuotedString('"') | Combine(Word
                                                 (alphanums + ' !"#$%&\'()*+-./:;<=>?@[\\]^_`{|}~'))
        tags = delimitedList(identifier)
        self.func = Function(funcname)
        docstr = self.func.doc[1:]
        self.vbox = QVBoxLayout()
        self.retval = []
        self._selectedFields = selected_fields

        if selected_fields:
            fields = ['__all'] + sorted(INFOTAGS) + \
                     selected_fields + gettaglist()
        else:
            fields = ['__selected', '__all'] + sorted(INFOTAGS) + \
                     gettaglist()

        self.tagcombo = QComboBox(self)
        self.tagcombo.setToolTip(FIELDS_TOOLTIP)
        self.tagcombo.setEditable(True)
        self.tagcombo.setCompleter(QCompleter(self.tagcombo))
        self.tagcombo.addItems(fields)

        self.tagcombo.editTextChanged.connect(self.showexample)

        if self.func.function not in functions.no_fields:
            label = QLabel(translate('Defaults', "&Fields"))
            self.vbox.addWidget(label)
            self.vbox.addWidget(self.tagcombo)
            label.setBuddy(self.tagcombo)
        else:
            self.tagcombo.setVisible(False)
        self.example = example
        self._text = text

        if self.func.function in functions_dialogs.dialogs:
            vbox = QVBoxLayout()
            vbox.addWidget(self.tagcombo)
            self.widget = functions_dialogs.dialogs[self.func.function](self)
            vbox.addWidget(self.widget)
            vbox.addStretch()
            self.setLayout(vbox)
            self.setMinimumSize(self.sizeHint())

            self.setArguments(default_fields, userargs)
            return
        else:
            self.widget = None

        self.textcombos = []
        # Loop that creates all the controls
        self.controls = []
        for argno, line in enumerate(docstr):
            args = tags.parseString(line)
            label = args[0]
            ctype = args[1]
            default = args[2:]

            control, func, label = self._createControl(label, ctype, default)

            self.retval.append(func)
            self.controls.append(control)
            getattr(control, self.signals[ctype]).connect(self.showexample)

            if label:
                self.vbox.addWidget(label)
            self.vbox.addWidget(control)

        self.setArguments(default_fields, userargs)

        self.vbox.addStretch()
        self.setLayout(self.vbox)
        self.setMinimumSize(self.sizeHint())

    def argValues(self):
        """Returns the values in the windows controls.
        The last argument is the tags value.
        Also sets self.func's arg and tag values."""

        if self.widget:
            newargs = self.widget.arguments()
        else:
            newargs = []
            for method in self.retval:
                if method.__name__ == 'checkState':
                    if method() == Qt.Checked:
                        newargs.append(True)
                    elif (method() == Qt.PartiallyChecked) or (method() == Qt.Unchecked):
                        newargs.append(False)
                else:
                    if isinstance(method(), int):
                        newargs.append(method())
                    else:
                        newargs.append(str(method()))
            [z.save() for z in self.textcombos]
        self.func.setArgs(newargs)

        fields = [z.strip() for z in
                  str(self.tagcombo.currentText()).split(",") if z]

        if self.func.function in functions.no_fields:
            self.func.setTag(['just nothing to do with this'])
        else:
            self.func.setTag(fields)
        return newargs + fields

    def _createControl(self, label, ctype, default=None):
        if ctype == 'text':
            control = self._controls['text'](label, parent=self)
        else:
            control = self._controls[ctype](self)

        if ctype == 'combo':
            func = control.currentText
            if default:
                control.addItems([translate('Functions', d) for d in default])
        elif ctype == 'text':
            self.textcombos.append(control)
            func = control.currentText
            if default:
                control.setEditText(default[0])
        elif ctype == 'check':
            func = control.checkState
            if default:
                if default[0] == "True" or default[0] is True:
                    control.setChecked(True)
                else:
                    control.setChecked(False)
            control.setText(translate('Functions', label))

        if ctype != 'check':
            label = QLabel(translate('Functions', label))
            label.setBuddy(control)
        else:
            label = None

        return control, func, label

    def loadSettings(self, filename=None):
        if filename is None:
            filename = FUNC_SETTINGS
        cparser = PuddleConfig(filename)
        function = self.func.function
        section = '%s_%s' % (function.__module__, function.__name__)
        arguments = cparser.get(section, 'arguments', [])
        fields = cparser.get(section, 'fields', [])
        if not fields:
            fields = None
        self.setArguments(fields, arguments)

    def saveSettings(self, filename=None):
        if not filename:
            filename = FUNC_SETTINGS
        function = self.func.function
        section = '%s_%s' % (function.__module__, function.__name__)

        cparser = PuddleConfig(filename)
        args = self.argValues()
        cparser.set(section, 'arguments', self.func.args)
        cparser.set(section, 'fields', self.func.tag)

    def showexample(self, *args, **kwargs):
        self.argValues()
        if self.example is not None:
            audio = self.example
            try:
                if self.func.function in functions.no_preview:
                    self.updateExample.emit(
                        translate('Functions Dialog',
                                  'No preview for is shown for this function.'))
                    return
                fields = findfunc.parse_field_list(self.func.tag, audio,
                                                   self._selectedFields)
                from .puddletag import status
                files = status['selectedfiles']
                files = str(len(files)) if files else '1'
                state = {'__counter': '0', '__total_files': files}
                val = apply_actions([self.func], audio, state, fields)
            except findfunc.ParseError as e:
                val = '<b>%s</b>' % (e.message)
            if val is not None:
                self.updateExample.emit(val)
            else:
                self.updateExample.emit(translate('Functions Dialog', '<b>No change</b>'))

    def _sanitize(self, ctype, value):
        if ctype in ['combo', 'text']:
            return value
        elif ctype == 'check':
            if value is True or value == 'True':
                return True
            else:
                return False
        elif ctype == 'spinbox':
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0

    def setArguments(self, fields=None, args=None):
        if fields is not None:
            text = ', '.join(fields)
            index = self.tagcombo.findText(text)
            if index != -1:
                self.tagcombo.setCurrentIndex(index)
            else:
                self.tagcombo.insertItem(0, text)
                self.tagcombo.setCurrentIndex(0)
            self.tagcombo.setEditText(text)

        if not args:
            return

        if self.widget:
            self.widget.setArguments(*args)
            return

        for argument, control in zip(args, self.controls):
            if isinstance(control, QComboBox):
                index = control.findText(argument)
                if index != -1:
                    control.setCurrentIndex(index)
            elif isinstance(control, PuddleCombo):
                control.setEditText(argument)
            elif isinstance(control, QCheckBox):
                control.setChecked(self._sanitize('check', argument))
            elif isinstance(control, QSpinBox):
                control.setValue(self._sanitize('spinbox', argument))


class CreateFunction(QDialog):
    """A dialog to allow the creation of functions using only one window and a QStackedWidget.
    For each function in functions, a dialog is created and displayed in the stacked widget."""
    valschanged = pyqtSignal(object, name='valschanged')

    def __init__(self, prevfunc=None, selected_fields=None, parent=None,
                 example=None, text=None):
        """tags is a list of the tags you want to show in the FunctionDialog.
        Each item should be in the form (DisplayName, tagname) as used in audioinfo.
        prevfunc is a Function object that is to be edited."""
        QDialog.__init__(self, parent)
        self.setWindowTitle(translate('Functions Dialog', "Functions"))
        winsettings('createfunction', self)

        # Allow __selected field to be used.
        self.allowSelected = True

        self.realfuncs = []
        # Get all the function from the functions module.
        for z, funcname in functions.functions.items():
            if isinstance(funcname, PluginFunction):
                self.realfuncs.append(funcname)
            elif callable(funcname) and (not (funcname.__name__.startswith("__") or (funcname.__doc__ is None))):
                self.realfuncs.append(z)

        funcnames = [(Function(z).funcname, z) for z in self.realfuncs]
        funcnames.sort(key=lambda x: translate('Functions', x[0]))
        self.realfuncs = [z[1] for z in funcnames]

        self.vbox = QVBoxLayout()
        self.functions = QComboBox()
        self.functions.addItems(
            sorted([translate('Functions', x[0]) for x in funcnames]))
        self.vbox.addWidget(self.functions)

        self.stack = QStackedWidget()
        self.vbox.addWidget(self.stack)
        self.okcancel = OKCancel()

        self.stackWidgets = {}  # Holds the created windows in the form self.functions.index: window
        self.setLayout(self.vbox)
        self.setMinimumHeight(self.sizeHint().height())
        self.okcancel.ok.connect(self.okClicked)
        self.okcancel.cancel.connect(self.close)

        self.example = example
        self._text = text
        if not selected_fields:
            self.selectedFields = []
        else:
            self.selectedFields = selected_fields

        self.exlabel = ScrollLabel('')

        if prevfunc is not None:
            index = self.functions.findText(
                translate('Functions', prevfunc.funcname))
            if index >= 0:
                self.functions.setCurrentIndex(index)
                self.createWindow(index, prevfunc.tag, prevfunc.args)
        else:
            self.createWindow(0)

        self.functions.activated.connect(self.createWindow)

        self.vbox.addWidget(self.exlabel)
        self.vbox.addLayout(self.okcancel)
        self.setLayout(self.vbox)

    def createWindow(self, index, fields=None, args=None):
        """Creates a Function dialog in the stack window
        if it doesn't exist already."""
        self.stack.setFrameStyle(QFrame.Box)
        if index not in self.stackWidgets:
            widget = FunctionDialog(self.realfuncs[index],
                                    self.selectedFields, args, fields,
                                    example=self.example, text=self._text)
            if args is None:
                widget.loadSettings()
            self.stackWidgets.update({index: widget})
            self.stack.addWidget(widget)
            widget.updateExample.connect(self.updateExample)
        self.stack.setCurrentWidget(self.stackWidgets[index])
        self.stackWidgets[index].showexample()
        self.controls = getattr(self.stackWidgets[index], 'controls', [])
        self.setMinimumHeight(self.sizeHint().height())
        if self.sizeHint().width() > self.width():
            self.setMinimumWidth(self.sizeHint().width())

    def okClicked(self, close=True):
        w = self.stack.currentWidget()
        w.argValues()
        if not self.checkFields(w.func.tag):
            return

        if close:
            self.close()

        if w.func.tag:
            fields = gettaglist()
            new_fields = [z for z in w.func.tag if z not in fields]
            if new_fields:
                settaglist(sorted(new_fields + fields))

        for widget in self.stackWidgets.values():
            widget.saveSettings()
        self.saveSettings()
        self.valschanged.emit(w.func)

    def checkFields(self, fields):
        func = self.stack.currentWidget().func
        msg = translate('Actions',
                        "Error: Using <b>__selected</b> in Actions is not allowed.")
        if not self.allowSelected and '__selected' in fields:
            QMessageBox.warning(self, 'puddletag', msg)
            return False
        elif func is not None and func not in functions.no_fields:
            msg = translate('Actions',
                            "Please enter some fields to write to.")
            if not [_f for _f in fields if _f]:
                QMessageBox.information(self, 'puddletag', msg)
                return False
        return True

    def loadSettings(self):
        cparser = PuddleConfig()
        func_name = cparser.get('functions', 'last_used', '')
        if not func_name:
            return

        try:
            index = self.realfuncs.index(func_name)
            self.createWindow(index)
            self.functions.setCurrentIndex(index)
        except ValueError:
            return

    def saveSettings(self):
        cparser = PuddleConfig()
        funcname = self.realfuncs[self.functions.currentIndex()]
        cparser.set('functions', 'last_used', funcname)

    def updateExample(self, text):
        if not text:
            self.exlabel.setText('')
        else:
            self.exlabel.setText(displaytags(text))


class CreateAction(QDialog):
    "An action is defined as a collection of functions. This dialog serves the purpose of creating an action"
    donewithmyshit = pyqtSignal(list, name='donewithmyshit')

    def __init__(self, parent=None, prevfunctions=None, example=None):
        """tags is a list of the tags you want to show in the FunctionDialog.
        Each item should be in the form (DisplayName, tagname as used in audioinfo).
        prevfunction is the previous function that is to be edited."""
        QDialog.__init__(self, parent)
        self.setWindowTitle(translate('Actions', "Modify Action"))
        winsettings('editaction', self)
        self.grid = QGridLayout()

        self.listbox = ListBox()
        self.functions = []
        self.buttonlist = ListButtons()
        self.grid.addWidget(self.listbox, 0, 0)
        self.grid.addLayout(self.buttonlist, 0, 1)

        self.okcancel = OKCancel()
        self.setLayout(self.grid)
        self.example = example

        self.okcancel.cancel.connect(self.cancelClicked)
        self.okcancel.ok.connect(self.okClicked)
        self.buttonlist.add.connect(self.add)
        self.buttonlist.edit.connect(self.edit)
        self.buttonlist.moveup.connect(self.moveUp)
        self.buttonlist.movedown.connect(self.moveDown)
        self.buttonlist.remove.connect(self.remove)
        self.buttonlist.duplicate.connect(self.duplicate)
        self.listbox.currentRowChanged.connect(self.enableEditButtons)
        self.listbox.itemDoubleClicked.connect(self.edit)
        
        if len(self.functions) == 0:
            self.buttonlist.duplicateButton.setEnabled(False)
            self.buttonlist.editButton.setEnabled(False)

        if prevfunctions is not None:
            self.functions = copy(prevfunctions)
            self.listbox.addItems([function.description() for
                                   function in self.functions])

        if example:
            self._examplelabel = ScrollLabel('')
            self.grid.addWidget(self._examplelabel, 1, 0)
            self.grid.setRowStretch(0, 1)
            self.grid.setRowStretch(1, 0)
            self.example = example
            self.updateExample()
            self.grid.addLayout(self.okcancel, 2, 0, 1, 2)
        else:
            self.grid.addLayout(self.okcancel, 1, 0, 1, 2)
        self.enableOK()

    def updateExample(self):
        try:
            from .puddletag import status
            files = status['selectedfiles']
            files = str(len(files)) if files else '1'
            state = {'__counter': '0', '__total_files': files}
            tags = apply_actions(self.functions, self.example, state)
            self._examplelabel.setText(displaytags(tags))
        except findfunc.ParseError as e:
            self._examplelabel.setText(e.message)

    def enableEditButtons(self, val):
        if val == -1:
            [button.setEnabled(False) for button in self.buttonlist.widgets[1:]]
        else:
            [button.setEnabled(True) for button in self.buttonlist.widgets[1:]]

    def enableOK(self):
        if self.listbox.count() > 0:
            self.okcancel.okButton.setEnabled(True)
        else:
            self.okcancel.okButton.setEnabled(False)

    def moveDown(self):
        self.listbox.moveDown(self.functions)

    def moveUp(self):
        self.listbox.moveUp(self.functions)

    def remove(self):
        self.listbox.removeSelected(self.functions)
        self.updateExample()
        self.enableOK()

    def add(self):
        self.win = CreateFunction(None, parent=self, example=self.example)
        self.win.allowSelected = False
        self.win.setModal(True)
        self.win.show()
        self.win.valschanged.connect(self.addBuddy)

    def edit(self):
        self.win = CreateFunction(self.functions[self.listbox.currentRow()],
                                  parent=self, example=self.example)
        self.win.allowSelected = False
        self.win.setModal(True)
        self.win.show()
        self.win.valschanged.connect(self.editBuddy)

    def editBuddy(self, func):
        self.listbox.currentItem().setText(func.description())
        self.functions[self.listbox.currentRow()] = func
        self.updateExample()

    def addBuddy(self, func):
        self.listbox.addItem(func.description())
        self.functions.append(func)
        self.updateExample()
        self.enableOK()

    def okClicked(self):
        self.accept()
        self.close()
        self.donewithmyshit.emit(self.functions)

    def duplicate(self):
        self.win = CreateFunction(self.functions[self.listbox.currentRow()],
                                  parent=self, example=self.example)
        self.win.allowSelected = False
        self.win.setModal(True)
        self.win.show()
        self.win.valschanged.connect(self.addBuddy)

    def cancelClicked(self):
        self.reject()
        self.close()


class ActionWindow(QDialog):
    """Just a dialog that allows you to add, remove and edit actions
    On clicking OK, a signal "donewithmyshit" is emitted.
    It returns a list of lists.
    Each element of a list contains one complete action. While
    the elements of that action are just normal Function objects."""
    donewithmyshit = pyqtSignal(list, name='donewithmyshit')
    actionOrderChanged = pyqtSignal(name='actionOrderChanged')
    checkedChanged = pyqtSignal(list, name='checkedChanged')

    def __init__(self, parent=None, example=None, quickaction=None):
        """tags are the tags to be shown in the FunctionDialog"""
        QDialog.__init__(self, parent)
        self.setWindowTitle(translate('Actions', "Actions"))
        winsettings('actions', self)
        self._shortcuts = []
        self._quickaction = quickaction
        self.listbox = ListBox()
        self.listbox.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.listbox.setEditTriggers(QAbstractItemView.EditKeyPressed)

        self.example = example

        self.macros = self.loadMacros()
        cparser = PuddleConfig()
        self.__configKey = 'quick_actions' if quickaction else 'actions'
        to_check = cparser.get(self.__configKey, 'checked', [])

        for i, m in sorted(self.macros.items()):
            item = QListWidgetItem(m.name)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            if m.name in to_check:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
            self.listbox.addItem(item)

        self.okcancel = OKCancel()
        self.okcancel.okButton.setDefault(True)
        x = QAction(translate('Actions', 'Assign &Shortcut'), self)
        self.shortcutButton = QToolButton()
        self.shortcutButton.setDefaultAction(x)
        x.setToolTip(translate('Actions', '''<p>Creates a
            shortcut for the checked actions on the Actions menu.
            Use Edit Shortcuts (found by pressing down on this button)
            to edit shortcuts after the fact.</p>'''))
        menu = QMenu(self)
        edit_shortcuts = QAction(translate('Actions', 'Edit Shortcuts'), menu)
        edit_shortcuts.triggered.connect(self.editShortcuts)
        menu.addAction(edit_shortcuts)
        self.shortcutButton.setMenu(menu)

        self.okcancel.insertWidget(0, self.shortcutButton)
        self.grid = QGridLayout()

        self.buttonlist = ListButtons()

        self.grid.addWidget(self.listbox, 0, 0)
        self.grid.setRowStretch(0, 1)
        self.grid.addLayout(self.buttonlist, 0, 1)
        self.setLayout(self.grid)

        self.okcancel.ok.connect(self.okClicked)
        self.okcancel.cancel.connect(self.close)
        self.buttonlist.add.connect(self.add)
        self.buttonlist.edit.connect(self.edit)
        self.buttonlist.moveup.connect(self.moveUp)
        self.buttonlist.movedown.connect(self.moveDown)
        self.buttonlist.remove.connect(self.remove)
        self.buttonlist.duplicate.connect(self.duplicate)
        self.listbox.itemDoubleClicked.connect(self.edit)
        self.listbox.currentRowChanged.connect(self.enableListButtons)
        self.listbox.itemChanged.connect(self.renameAction)
        self.listbox.itemChanged.connect(self.enableOK)
        self.shortcutButton.clicked.connect(self.createShortcut)

        self._examplelabel = ScrollLabel('')
        self.grid.addWidget(self._examplelabel, 1, 0, 1, -1)
        self.grid.setRowStretch(1, 0)
        if example is None:
            self._examplelabel.hide()
        self.listbox.itemChanged.connect(self.updateExample)
        self.grid.addLayout(self.okcancel, 2, 0, 1, 2)
        self.updateExample()
        self.enableOK(None)

    def createShortcut(self):
        macros = self.checked()
        names = [m.name for m in macros]
        (name, ok) = ShortcutName(self.shortcutNames(), names[0]).getText()

        if name and ok:
            from . import puddletag
            shortcuts = [str(z.shortcut().toString()) for z in
                         puddletag.status['actions']]
            (shortcut, ok) = ShortcutDialog(shortcuts).getShortcut()
            name = str(name)

            from .action_shortcuts import (
                create_action_shortcut, save_shortcut)

            filenames = [m.filename for m in macros]

            if shortcut and ok:
                create_action_shortcut(name, filenames, shortcut, add=True)
            else:
                create_action_shortcut(name, filenames, add=True)
            save_shortcut(name, filenames)

    def editShortcuts(self):
        from . import action_shortcuts
        win = action_shortcuts.ShortcutEditor(True, self, True)
        win.setModal(True)
        win.show()

    def moveUp(self):
        self.listbox.moveUp(self.macros)

    def moveDown(self):
        self.listbox.moveDown(self.macros)

    def remove(self):
        cparser = PuddleConfig()
        listbox = self.listbox
        rows = sorted([listbox.row(item) for item in
                       listbox.selectedItems()])

        for row in rows:
            filename = self.macros[row].filename
            os.rename(filename, filename + '.deleted')
        self.listbox.removeSelected(self.macros)

        macros = {}
        for i, key in enumerate(self.macros):
            macros[i] = self.macros[key]

        macros = self.macros

        self.macros = dict((i, macros[k]) for i, k in
                           enumerate(sorted(macros)))

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
            self.okcancel.okButton.setEnabled(True)
            self.shortcutButton.setEnabled(True)
        else:
            self.okcancel.okButton.setEnabled(False)
            self.shortcutButton.setEnabled(False)

    def renameAction(self, item):
        name = str(item.text())
        names = [m.name for m in self.macros.values()]
        row = self.listbox.row(item)

        if name not in names:
            macro = self.macros[row]
            macro.name = name
            self.saveMacro(macro)
        else:
            self.listbox.blockSignals(True)
            item.setText(self.macros[row].name)
            self.listbox.blockSignals(False)

    def loadMacros(self):
        from glob import glob
        basename = os.path.basename

        funcs = {}
        cparser = PuddleConfig()
        set_value = partial(cparser.set, 'puddleactions')
        get_value = partial(cparser.get, 'puddleactions')

        firstrun = get_value('firstrun', True)
        set_value('firstrun', False)
        convert = get_value('convert', True)
        order = get_value('order', [])

        if convert:
            set_value('convert', False)
            findfunc.convert_actions(SAVEDIR, ACTIONDIR)
            if order:
                old_order = dict([(basename(z), i) for i, z in
                                  enumerate(order)])
                files = glob(os.path.join(ACTIONDIR, '*.action'))
                order = {}
                for i, action_fn in enumerate(files):
                    try:
                        order[old_order[basename(action_fn)]] = action_fn
                    except KeyError:
                        if not old_order:
                            order[i] = action_fn
                order = [z[1] for z in sorted(order.items())]
                set_value('order', order)

        files = glob(os.path.join(ACTIONDIR, '*.action'))
        if firstrun and not files:
            filenames = [':/caseconversion.action', ':/standard.action']
            files = list(map(open_resourcefile, filenames))
            set_value('firstrun', False)

            for fileobj, filename in zip(files, filenames):
                filename = os.path.join(ACTIONDIR, filename[2:])
                f = open(filename, 'w')
                f.write(fileobj.read())
                f.close()
            files = glob(os.path.join(ACTIONDIR, '*.action'))

        files = [z for z in order if z in files] + \
                [z for z in files if z not in order]

        return dict((i, Macro(f)) for i, f in enumerate(files))

    def updateExample(self, *args):
        if self.example is None:
            self._examplelabel.hide()
            return
        l = self.listbox
        items = [l.item(z) for z in range(l.count())]
        selectedrows = [i for i, z in enumerate(items) if z.checkState() == Qt.Checked]

        if selectedrows:
            from .puddletag import status
            files = status['selectedfiles']
            total = str(len(files)) if files else '1'
            state = {'__counter': '0', '__total_files': total}

            macros = [self.macros[i] for i in selectedrows]
            try:
                tags = apply_macros(macros, self.example, state,
                                    self._quickaction)
                self._examplelabel.setText(displaytags(tags))
            except findfunc.ParseError as e:
                self._examplelabel.setText(e.message)
            self._examplelabel.show()
        else:
            self._examplelabel.hide()

    def removeSpaces(self, text):
        for char in string.whitespace:
            text = text.replace(char, '')
        return text.lower()

    def saveMacro(self, macro, filename=None):
        cparser = PuddleConfig()
        if filename is None and macro.filename:
            macro.save()
        elif filename:
            macro.filename = filename
            macro.save()
        else:
            name = macro.name
            filename = os.path.join(ACTIONDIR, safe_name(name) + '.action')
            base = os.path.splitext(filename)[0]
            i = 0
            while os.path.exists(filename):
                filename = "%s_%d" % (base, i) + '.action'
                i += 1
            macro.save(filename)
            macro.filename = filename
        return filename

    def add(self):
        (text, ok) = QInputDialog.getText(self,
                                          translate('Actions', "New Action"),
                                          translate('Actions', "Enter a name for the new action."),
                                          QLineEdit.Normal)

        if (ok is True) and text:
            item = QListWidgetItem(text)
            item.setCheckState(Qt.Unchecked)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.listbox.addItem(item)
        else:
            return
        win = CreateAction(self, example=self.example)
        win.setWindowTitle(translate('Actions', "Add Action: ") + \
                           self.listbox.item(self.listbox.count() - 1).text())
        win.setModal(True)
        win.donewithmyshit.connect(self.addBuddy)
        win.rejected.connect(lambda: self.listbox.takeItem(self.listbox.count() - 1))
        win.show()

    def addBuddy(self, actions):
        m = Macro()
        m.name = str(self.listbox.item(self.listbox.count() - 1).text())
        m.actions = actions
        self.saveMacro(m)
        self.macros[self.listbox.count() - 1] = m

    def edit(self):
        m = self.macros[self.listbox.currentRow()]
        win = CreateAction(self, m.actions, example=self.example)
        win.setWindowTitle(
            translate('Actions', "Edit Action: ") + m.name)
        win.show()
        win.donewithmyshit.connect(self.editBuddy)

    def editBuddy(self, actions):
        m = self.macros[self.listbox.currentRow()]
        m.actions = actions
        self.saveMacro(m)
        self.updateExample()

    def checked(self):
        return [self.macros[row] for row in self.checkedRows()]

    def checkedRows(self):
        l = self.listbox
        items = [l.item(z) for z in range(l.count())]
        checked = [i for i, z in enumerate(items) if
                   z.checkState() == Qt.Checked]
        return checked

    def saveChecked(self):
        cparser = PuddleConfig()
        m_names = [m.name for m in self.checked()]
        cparser.set(self.__configKey, 'checked', m_names)

    def saveOrder(self):
        macros = self.macros
        cparser = PuddleConfig()
        order = [macros[i].filename for i in sorted(macros)]
        lastorder = cparser.get('puddleactions', 'order', [])
        if lastorder == order:
            return
        cparser.set('puddleactions', 'order', order)
        self.actionOrderChanged.emit()

    def close(self):
        self.saveOrder()
        QDialog.close(self)

    def okClicked(self, close=True):
        """When clicked, save the current contents of the listbox and the associated functions"""
        macros = self.checked()
        names = [m.name for m in macros]
        cparser = PuddleConfig()
        cparser.set(self.__configKey, 'checked', names)
        if close:
            self.close()

        self.checkedChanged.emit(self.checkedRows())
        self.donewithmyshit.emit(macros)

    def duplicate(self):
        l = self.listbox
        if len(l.selectedItems()) > 1:
            return
        row = l.currentRow()
        oldname = self.macros[row].name

        (text, ok) = QInputDialog.getText(self,
                                          translate('Actions', "Copy %s action" % oldname),
                                          translate('Actions', "Enter a name for the new action."),
                                          QLineEdit.Normal)
        if not (ok and text):
            return

        name = str(text)
        actions = deepcopy(self.macros[row].actions)

        win = CreateAction(self, actions, example=self.example)
        win.setWindowTitle(
            translate('Actions', "Edit Action: %s") % name)

        win.show()
        dupebuddy = partial(self.duplicateBuddy, name)
        win.donewithmyshit.connect(dupebuddy)

    def duplicateBuddy(self, name, actions):
        item = QListWidgetItem(name)
        item.setCheckState(Qt.Unchecked)
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self.listbox.addItem(item)

        m = Macro()
        m.name = name
        m.actions = actions
        self.saveMacro(m)
        self.macros[self.listbox.count() - 1] = m

    def shortcutNames(self):
        from .action_shortcuts import load_settings
        return [name for name, filename in load_settings()[1]]


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setOrganizationName("Puddle Inc.")
    app.setApplicationName("puddletag")
    qb = ActionWindow([('Path', '__path'), ('Artist', 'artist'), ('Title', 'title'), ('Album', 'album'), ('Track', 'track'), ('Length', '__length'), ('Year', 'date')])
    qb.show()
    app.exec_()
