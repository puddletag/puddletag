# -*- coding: utf-8 -*-
from PyQt4.QtGui import QApplication
import re

class UnicodeMod(unicode):
    """Emulates the arg method of QStrings. Not meant for use anywhere other
    than the translate function above."""

    def arg(self, value):
        matches = [z for z in re.finditer("%(\d+)", self)]
        if not matches:
            print 'Undefined result for arg'
            return UnicodeMod(self[::])
        elif len(matches) == 1:
            lowest = matches[0]
        else:
            lowest = sorted(matches, key=lambda m: m.groups())[0]
        return UnicodeMod(self.replace(lowest.group(), value))

    def __metaclass__(name, bases, d):
        'Make it behave like unicode object'
        return type.__new__(type(unicode), 'unicode', bases, d)

translate = lambda k,v : UnicodeMod(QApplication.translate(k,v))

#General Translations
QApplication.translate("GenSettings", 'Su&bfolders')
QApplication.translate("GenSettings", 'Show &gridlines')
QApplication.translate("GenSettings", 'Show tooltips in file-view:')
QApplication.translate("GenSettings", 'Show &row numbers')
QApplication.translate("GenSettings", 'Automatically resize columns to contents')
QApplication.translate("GenSettings", '&Preserve file modification times')
QApplication.translate("GenSettings", 'Program to &play files with:')
QApplication.translate("GenSettings", '&Load last folder at startup')

#Artwork
QApplication.translate("Artwork Context", 'Cover Varies')
QApplication.translate("Artwork Context", 'No Images')

#Dialogs
QApplication.translate("Dialogs", 'Functions')
QApplication.translate("Dialogs", 'Actions')
QApplication.translate("Dialogs", 'Artwork')
QApplication.translate("Dialogs", 'Mass Tagging')
QApplication.translate("Dialogs", 'Tag Panel')
QApplication.translate("Dialogs", 'Filter')
QApplication.translate("Dialogs", 'Filesystem')
QApplication.translate("Dialogs", 'Tag Sources')
QApplication.translate("Dialogs", 'Stored Tags')
QApplication.translate("Dialogs", 'Logs')

#Menus
QApplication.translate('Menus', '&Open Folder')
QApplication.translate('Menus', '&Add Folder')
QApplication.translate('Menus', 'Load &playlist')
QApplication.translate('Menus', 'Sa&ve playlist')
QApplication.translate('Menus', '&Refresh')
QApplication.translate('Menus', '&Save')
QApplication.translate('Menus', '&Play')
QApplication.translate('Menus', '&File->Tag')
QApplication.translate('Menus', '&Undo')
QApplication.translate('Menus', 'Autonumbering &Wizard...')
QApplication.translate('Menus', '&Clear')
QApplication.translate('Menus', '&Format')
QApplication.translate('Menus', '&Text File->Tag')
QApplication.translate('Menus', '&Import Music Library...')
QApplication.translate('Menus', '&Actions')
QApplication.translate('Menus', '&Preferences')
QApplication.translate('Menus', '&Functions')
QApplication.translate('Menus', '&QuickActions')
QApplication.translate('Menus', '&Rename Directories')
QApplication.translate('Menus', '&Exit')
QApplication.translate('Menus', '&Tag->File')
QApplication.translate('Menus', '&Increase Font')
QApplication.translate('Menus', '&Decrease Font')
QApplication.translate('Menus', '&Clipboard->Tag')
QApplication.translate('Menus', 'Select &All')
QApplication.translate('Menus', '&Invert Selection')
QApplication.translate('Menus', '&Select Column')
QApplication.translate('Menus', '&Cut')
QApplication.translate('Menus', '&Copy Selection')
QApplication.translate('Menus', '&Paste')
QApplication.translate('Menus', '&Remove Tag')
QApplication.translate('Menus', 'E&xtended Tags')
QApplication.translate('Menus', '&Delete')
QApplication.translate('Menus', '&Properties')
QApplication.translate('Menus', 'Paste &Onto Selection')
QApplication.translate('Menus', '&Lock Layout')
QApplication.translate('Menus', 'Select &Next Directory')
QApplication.translate('Menus', 'Copy All &Fields')
QApplication.translate('Menus', 'Delete &Without Confirmation')
QApplication.translate('Menus', 'In &Library')
QApplication.translate('Menus', 'Replace...')
QApplication.translate('Menus', 'Remove &APEv2 Tag')
QApplication.translate('Menus', 'Remove All &ID3 Tags')
QApplication.translate('Menus', 'Move Selected &Up')
QApplication.translate('Menus', 'Move Selected Do&wn')
QApplication.translate('Menus', 'Select &Previous Directory')
QApplication.translate('Menus', 'Remove ID3v&2 Tag')
QApplication.translate('Menus', 'Remove ID3v&1 Tag')

translate('Functions', 'Tag to filename')
translate('Functions', 'Tag->File: $1')
translate('Functions', 'Replace')
translate('Functions', 'Replace $0: \'$1\' -> \'$2\', Match Case: $3, Words Only: $4')
translate('Functions', 'Update from tag')
translate('Functions', 'Update from $2, Fields: $1')
translate('Functions', 'Trim whitespace')
translate('Functions', 'Trim $0')
translate('Functions', 'Autonumbering')
translate('Functions', 'Autonumbering: $0, Start: $1, Restart for dir: $2, Padding: $3')
translate('Functions', 'Sort values')
translate('Functions', 'Sort $0, order=\'$1\', Match Case=\'$2\'')
translate('Functions', 'Tag to Dir')
translate('Functions', 'Tag->Dir: $1')
translate('Functions', 'Format value')
translate('Functions', 'Format $0 using $1')
translate('Functions', 'Replace with RegExp')
translate('Functions', 'RegReplace $0: RegExp \'$1\' with \'$2\', Match Case: $3')
translate('Functions', 'Load Artwork')
translate('Functions', 'Artwork: Filenames=\'$1\', Description=\'$2\', Case Sensitive=$3')
translate('Functions', 'Merge field')
translate('Functions', 'Merge field: $0, sep=\'$1\'')
translate('Functions', 'Remove duplicate values')
translate('Functions', 'Remove Dupes: $0, Match Case $1')
translate('Functions', 'Import text file')
translate('Functions', 'Text File: $0, \'$1\'')
translate('Functions', 'Split fields using separator')
translate('Functions', 'Split using separator $0: sep=\'$1\'')
translate('Functions', 'Remove all fields except')
translate('Functions', 'Remove fields except: $1')
translate('Functions', 'Remove Fields')
translate('Functions', '<blank> $0')
translate('Functions', 'Case conversion')
translate('Functions', 'Convert Case: $0: $1')
translate('Functions', 'Convert from non-standard encoding')
translate('Functions', 'Convert to encoding: $0, Encoding: $1')
translate('Functions', 'Text to Tag')
translate('Functions', 'Text to Tag: $0 -> $1, $2')
translate('Functions', 'Filename to Tag')
translate('Functions', 'File->Tag \'$1\'')
