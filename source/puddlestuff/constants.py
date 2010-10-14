# -*- coding: utf-8 -*-
import os, sys
from PyQt4.QtCore import Qt, SIGNAL
from PyQt4.QtGui import QWidget
from os.path import dirname, join

SEPARATOR = u'\\\\'

FS_ENC = sys.getfilesystemencoding()

#Paths
HOMEDIR = os.getenv('HOME')
SAVEDIR = join(HOMEDIR,'.puddletag')
CONFIG = join(SAVEDIR, 'puddletag.conf')
QT_CONFIG = join(SAVEDIR, 'qt.conf')
PLUGINDIR = join(SAVEDIR, 'plugins')
PROGDIR = dirname(dirname(__file__))
DATADIR = join(dirname(__file__), 'data')
ACTIONDIR = join(SAVEDIR, 'actions')

#Misc
BLANK = u'<blank>'
KEEP = u'<keep>'

#Values used for controls in creating functions in actiondlg
TEXT = 'text'
COMBO = 'combo'
CHECKBOX = 'check'
TAGLIST = 'taglist'

#Plugin contstants
FORMATFUNCTIONS = 'FORMATFUNCTIONS'
FUNCTIONS = 'FUNCTIONS'
TAGSOURCE = 'TAGSOURCE'

#Dock Positions
LEFTDOCK = Qt.LeftDockWidgetArea
RIGHTDOCK = Qt.RightDockWidgetArea
BOTTOMDOCK = Qt.BottomDockWidgetArea
TOPDOCK = Qt.TopDockWidgetArea

#Tag constants
PATH = u"__path"
FILENAME = u"__filename"
EXTENSION = '__ext'
DIRPATH = '__dirpath'
READONLY = ('__bitrate', '__frequency', "__length",
    "__modified", "__size", "__created", "__library")
IMAGE = '__image'
FILETAGS = [PATH, FILENAME, EXTENSION, DIRPATH]
INFOTAGS = FILETAGS + list(READONLY)

#SIGNALS
SELECTIONCHANGED = "tagselectionchanged"