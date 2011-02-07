# -*- coding: utf-8 -*-
import os, sys
from PyQt4.QtCore import Qt, SIGNAL
from PyQt4.QtGui import QWidget, QApplication
from os.path import dirname, join
from puddlestuff.translations import translate

def trans_strings():
    from puddlestuff.translations import translate
    
    global YES
    global NO
    global VARIOUS
    global MUSICBRAINZ
    global BLANK
    global KEEP
    global SYNTAX_ERROR
    global SYNTAX_ARG_ERROR

    YES = translate('Defaults', 'Yes')
    NO = translate('Defaults', 'No')
    BLANK = translate('Defaults', '<blank>')
    KEEP = translate('Defaults', '<keep>')
    VARIOUS = translate('Defaults', u'Various Artists')
    MUSICBRAINZ  = translate('Defaults', 'MusicBrainz')
    SYNTAX_ERROR = translate('Defaults', 'SYNTAX ERROR in $%1: %2')
    SYNTAX_ARG_ERROR = translate('Defaults', 'SYNTAX ERROR: %s expects a number at argument %d.')

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
TRANSDIR = join(SAVEDIR, 'translations')

#Values used for controls in creating functions in actiondlg
TEXT = 'text'
COMBO = 'combo'
CHECKBOX = 'check'
TAGLIST = 'taglist'
SPINBOX = 'spinbox'

#Plugin constants
FORMATFUNCTIONS = 'FORMATFUNCTIONS'
FUNCTIONS = 'FUNCTIONS'
TAGSOURCE = 'TAGSOURCE'
DIALOGS = 'DIALOGS'
MUSICLIBS = 'MUSICLIBS'
MODULES = 'MODULES'

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

#Signals used in enabling/disabling actions.
#An actions default state is to be disabled.
#and action can use these signals to enable
#Signals used in enabling/disabling actions.
#An actions default state is to be disabled.
#and action can use these signals to enable
#itself. See the loadshortcuts module for more info.
ALWAYS = 'always'
FILESLOADED = 'filesloaded'
VIEWFILLED = 'viewfilled'
FILESSELECTED = 'filesselected'

ENABLESIGNALS = dict((k, SIGNAL(k)) for k in
    [ALWAYS, FILESLOADED, VIEWFILLED, FILESSELECTED])