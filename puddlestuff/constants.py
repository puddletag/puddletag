# -*- coding: utf-8 -*-
import os
import sys
from os.path import dirname, join

from PyQt5.QtCore import Qt

from .translations import translate

YES = translate('Defaults', 'Yes')
NO = translate('Defaults', 'No')
BLANK = translate('Defaults', '<blank>')
KEEP = translate('Defaults', '<keep>')
VARIOUS = translate('Defaults', 'Various')
MUSICBRAINZ = translate('Defaults', 'MusicBrainz')
SYNTAX_ERROR = translate('Defaults', 'SYNTAX ERROR in $%1: %2')
SYNTAX_ARG_ERROR = translate('Defaults', 'SYNTAX ERROR: %s expects a number at argument %d.')


def trans_strings():
    from .translations import translate

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
    VARIOUS = translate('Defaults', 'Various Artists')
    MUSICBRAINZ = translate('Defaults', 'MusicBrainz')
    SYNTAX_ERROR = translate('Defaults', 'SYNTAX ERROR in $%1: %2')
    SYNTAX_ARG_ERROR = translate('Defaults', 'SYNTAX ERROR: %s expects a number at argument %d.')


SEPARATOR = '\\\\'

FS_ENC = sys.getfilesystemencoding()

# Paths

PROGDIR = dirname(dirname(__file__))
DATADIR = join(dirname(__file__), 'data')

_config_dir = os.environ.get('XDG_CONFIG_HOME', os.path.join(os.path.expanduser("~"), '.config'))
CONFIGDIR = os.path.join(_config_dir, 'puddletag')
HOMEDIR = os.path.expanduser('~')

CONFIG = join(CONFIGDIR, 'puddletag.conf')
QT_CONFIG = join(CONFIGDIR, 'qt.conf')

_data_dir = os.environ.get('XDG_DATA_HOME', os.path.join(os.path.expanduser("~"), '.local/share'))

SAVEDIR = os.path.join(_data_dir, 'puddletag')
LOG_FILENAME = os.path.join(CONFIGDIR, 'puddletag.log')
PLUGINDIR = join(SAVEDIR, 'plugins')

ACTIONDIR = join(SAVEDIR, 'actions')
TRANSDIR = join(SAVEDIR, 'translations')

# Values used for controls in creating functions in actiondlg
TEXT = 'text'
COMBO = 'combo'
CHECKBOX = 'check'
TAGLIST = 'taglist'
SPINBOX = 'spinbox'

# Plugin constants
FORMATFUNCTIONS = 'FORMATFUNCTIONS'
FUNCTIONS = 'FUNCTIONS'
FUNCTIONS_NO_PREVIEW = 'FUNCTIONS_NO_PREVIEW'
TAGSOURCE = 'TAGSOURCE'
DIALOGS = 'DIALOGS'
MUSICLIBS = 'MUSICLIBS'
MODULES = 'MODULES'

# Dock Positions
LEFTDOCK = Qt.LeftDockWidgetArea
RIGHTDOCK = Qt.RightDockWidgetArea
BOTTOMDOCK = Qt.BottomDockWidgetArea
TOPDOCK = Qt.TopDockWidgetArea

# Tag constants
PATH = "__path"
FILENAME = "__filename"
EXTENSION = '__ext'
DIRPATH = '__dirpath'
DIRNAME = '__dirname'
FILENAME_NO_EXT = '__filename_no_ext'
PARENT_DIR = '__parent_dir'
READONLY = ('__bitrate', '__frequency', "__length",
            "__modified", "__size", "__created", "__library")
IMAGE = '__image'
FILETAGS = [PATH, FILENAME, EXTENSION, DIRPATH, DIRNAME, FILENAME_NO_EXT,
            PARENT_DIR]
INFOTAGS = FILETAGS + list(READONLY)

# SIGNALS
SELECTIONCHANGED = "tagselectionchanged"

# Signals used in enabling/disabling actions.
# An actions default state is to be disabled.
# and action can use these signals to enable
# Signals used in enabling/disabling actions.
# An actions default state is to be disabled.
# and action can use these signals to enable
# itself. See the loadshortcuts module for more info.
ALWAYS = 'always'
FILESLOADED = 'filesloaded'
VIEWFILLED = 'viewfilled'
FILESSELECTED = 'filesselected'
ENABLESIGNALS = dict((k, k) for k in
                     [ALWAYS, FILESLOADED, VIEWFILLED, FILESSELECTED])
