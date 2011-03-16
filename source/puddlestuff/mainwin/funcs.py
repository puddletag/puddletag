# -*- coding: utf-8 -*-
import puddlestuff.findfunc as findfunc
from puddlestuff.puddleobjects import (dircmp, safe_name, natcasecmp,
    LongInfoMessage, PuddleConfig, PuddleDock, encode_fn, decode_fn)
import puddlestuff.actiondlg as actiondlg
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import os, pdb
path = os.path
import puddlestuff.helperwin as helperwin
from functools import partial
from itertools import izip
from puddlestuff.audioinfo import stringtags, PATH, DIRPATH, EXTENSION, FILETAGS
from operator import itemgetter
import puddlestuff.musiclib, puddlestuff.about as about
import traceback
from puddlestuff.util import split_by_tag, translate, to_string
import puddlestuff.functions as functions
from tagtools import *
import puddlestuff.confirmations as confirmations
from puddlestuff.constants import HOMEDIR

status = {}

def applyaction(files=None, funcs=None):
    if files is None:
        files = status['selectedfiles']
    r = findfunc.runAction
    state = {'__total_files': unicode(len(files))}
    state['__files'] = files
    def func():
        for i, f in enumerate(files):
            yield r(funcs, f, state)
    emit('writeaction', func(), None, state)

def applyquickaction(files, funcs):
    qa = findfunc.runQuickAction
    selected = status['selectedtags']
    state = {'__total_files': unicode(len(selected))}
    t = (qa(funcs, f, state, s.keys()) for f, s in izip(files, selected))
    emit('writeselected', t)

def auto_numbering(parent=None):
    """Shows the autonumbering wizard and sets the tracks
        numbers should be filled in"""
    tags = status['selectedfiles']
    numtracks = len(tags)

    win = helperwin.TrackWindow(parent, 1, numtracks, False)
    win.setModal(True)
    t = partial(number_tracks, tags)
    win.connect(win, SIGNAL("newtracks"), t)
    win.show()

def clipboard_to_tag(parent=None):
    win = helperwin.ImportWindow(parent, clipboard = True)
    win.setModal(True)
    win.patterncombo.addItems(status['patterns'])

    cparser = PuddleConfig()
    last_dir = cparser.get('importwindow', 'lastdir', HOMEDIR)
    win.lastDir = last_dir
    last_pattern = cparser.get('importwindow', 'lastpattern', u'')
    if last_pattern:
        win.patterncombo.setEditText(last_pattern)

    def fin_edit(taglist, pattern):
        cparser.set('importwindow', 'lastdir', win.lastDir)
        cparser.set('importwindow', 'lastpattern', pattern)
        emit('writeselected', taglist)
    
    win.connect(win, SIGNAL("Newtags"), fin_edit)
    
    win.show()

def connect_status(actions):
    connect = lambda a: obj.connect(obj, SIGNAL(a.status), a.setStatusTip)
    map(connect, actions)

def copy():
    selected = status['selectedtags']
    ba = QByteArray(unicode(selected).encode('utf8'))
    mime = QMimeData()
    mime.setData('application/x-puddletag-tags', ba)
    QApplication.clipboard().setMimeData(mime)

def copy_whole():
    tags = []
    def usertags(f):
        ret = f.usertags
        if hasattr(f, 'images') and f.images:
            ret.update({'__image': f.images})
        return ret
    tags = [usertags(f) for f in status['selectedfiles']]
    ba = QByteArray(unicode(tags).encode('utf8'))
    mime = QMimeData()
    mime.setData('application/x-puddletag-tags', ba)
    QApplication.clipboard().setMimeData(mime)

def cut():
    selected = status['selectedtags']
    ba = QByteArray(unicode(selected).encode('utf8'))
    mime = QMimeData()
    mime.setData('application/x-puddletag-tags', ba)
    QApplication.clipboard().setMimeData(mime)

    emit('writeselected', (dict([(z, "") for z in s if z not in FILETAGS])
        for s in selected))

def display_tag(tag):
    """Used to display tags in the status bar in a human parseable format."""
    if not tag:
        return "<b>Error: Pattern does not match filename.</b>"
    s = "%s: <b>%s</b>, "
    tostr = lambda i: i if isinstance(i, basestring) else i[0]
    return "".join([s % (z, tostr(v)) for z, v in tag.items()])[:-2]

def extended_tags(parent=None):
    rows = status['selectedrows']
    if len(rows) == 1:
        win = helperwin.ExTags(parent, rows[0], status['alltags'],
            status['previewmode'])
    else:
        win = helperwin.ExTags(files = status['selectedfiles'], parent=parent)
    win.loadSettings()
    x = lambda val: emit('onetomany', val)
    obj.connect(win, SIGNAL('extendedtags'), x)
    win.show()

def filename_to_tag():
    """Get tags from the selected files using the pattern in
    self.patterncombo."""
    tags = status['selectedfiles']
    pattern = status['patterntext']

    x = [findfunc.filenametotag(pattern, tag[PATH], True)
        for tag in tags]
    emit('writeselected', x)

def format(parent=None, preview = None):
    """Formats the selected tags."""
    files = status['selectedfiles']
    pattern = status['patterntext']
    selected = status['selectedtags']

    ret = []
    tf = findfunc.tagtofilename

    state = {'__total_files': unicode(len(files))}
    for i, (audio, s) in enumerate(zip(files, selected)):
        state['__counter'] = unicode(i + 1)
        val = tf(pattern, audio, state = state)
        ret.append(dict([(tag, val) for tag in s]))
    emit('writeselected', ret)

def in_lib(state, parent=None):
    if state:
        if not status['library']:
            QMessageBox.critical(parent, translate("MusicLib", 'No libraries found'),
                translate("MusicLib", "Load a lib first."))
            return False
        files = status['allfiles']
        lib = status['library']
        libartists = status['library'].artists
        to_highlight = []
        for artist, tracks in split_by_tag(files, 'artist', None).items():
            if artist in libartists:
                libtracks = lib.get_tracks('artist', artist)
                titles = [track['title'][0].lower() 
                    if 'title' in track else '' for track in libtracks]
                for track in tracks:
                    if track.get('title', [u''])[0].lower() in titles:
                        to_highlight.append(track)
        emit('highlight', to_highlight)
        return True
    else:
        emit('highlight', [])
        return False

def load_musiclib(parent=None):
    try:
        m = puddlestuff.musiclib.LibChooseDialog()
    except puddlestuff.musiclib.MusicLibError:
        QMessageBox.critical(parent, translate("MusicLib", 'No libraries found'),
           translate("MusicLib", "No supported music libraries were found. Most likely "
            "the required dependencies aren't installed. Visit the "
            "puddletag website, <a href='http://puddletag.sourceforge.net'>"
            "puddletag.sourceforge.net</a> for more details."))
        return
    m.setModal(True)
    obj.connect(m, SIGNAL('adddock'), emit_received('adddock'))
    m.show()

_padding = u'0'
def _pad(text, numlen):
    if len(text) < numlen:
        text = _padding * ((numlen - len(text)) / len(_padding)) + text
    return text

def number_tracks(tags, start, numtracks, restartdirs, padlength):
    """Numbers the selected tracks sequentially in the range
    between the indexes.
    The first item of indices is the starting track.
    The second item of indices is the number of tracks."""
    if numtracks:
        num = "/" + unicode(numtracks)
    else: num = ""

    if restartdirs: #Restart dir numbering
        folders = {}
        taglist = []
        for tag in tags:
            folder = tag[DIRPATH]
            if folder in folders:
                folders[folder] += 1
            else:
                folders[folder] = start
            taglist.append({"track": _pad(unicode(folders[folder]) + num,
                padlength)})
    else:
        taglist = [{"track": _pad(unicode(z) + num, padlength)}
            for z in range(start, start + len(tags) + 1)]

    emit('writeselected', taglist)

def paste():
    rows = status['selectedrows']
    if not rows:
        return
    data = QApplication.clipboard().mimeData().data(
        'application/x-puddletag-tags').data()
    if not data:
        return
    clip = eval(data.decode('utf8'), {"__builtins__":None},{})
    tags = []
    while len(tags) < len(rows):
        tags.extend(clip)
    tags.extend(clip)
    emit('writeselected', tags)

def paste_onto():
    data = QApplication.clipboard().mimeData().data(
        'application/x-puddletag-tags').data()
    if not data:
        return
    clip = eval(data.decode('utf8'), {"__builtins__":None}, {})
    selected = status['selectedtags']
    tags = []
    while len(tags) < len(selected):
        tags.extend(clip)
    emit('writeselected', (dict(zip(s, cliptag.values()))
                            for s, cliptag in izip(selected, tags)))

def rename_dirs(parent=None):
    """Changes the directory of the currently selected files, to
    one as per the pattern in self.patterncombo."""
    if status['table'].model().previewMode:
        QMessageBox.information(parent, 'puddletag',
            translate("Dir Renaming", 'Disable Preview Mode first to enable renaming of directories.'))
        return

    tagtofilename = findfunc.tagtofilename

    dirname = os.path.dirname
    basename = os.path.basename
    path = os.path

    files = status['selectedfiles']
    pattern = status['patterntext']

    #Get distinct folders
    newdirs = {}
    for f in files:
        if f.dirpath not in newdirs:
            newdirs[f.dirpath] = f

    #Create the msgbox, I like that there'd be a difference between
    #the new and the old filename, so I bolded the new and italicised the old.
    state = {'__total_files': unicode(len(files))}
    title = translate("Dir Renaming", "<b>Are you sure you want to rename the following directories?</b>")
    dirs = []
    newname = lambda x, st: encode_fn(basename(safe_name(tagtofilename(pattern, x, state=st))))
    msg = u''
    for counter, (d, f) in enumerate(newdirs.items()):
        state['__counter'] = unicode(counter + 1)
        newfolder = path.join(dirname(d), newname(f, state))
        msg += u'%s -> <b>%s</b><br /><br />' % (
            f[DIRPATH], newfolder.decode('utf8', 'replace'))
        dirs.append([d, newfolder])

    msg = msg[:-len('<br /><br />')]

    if confirmations.should_show('rename_dirs'):
        info = LongInfoMessage(translate("Dir Renaming", 'Rename dirs?'), title, msg, parent)
        if not info.exec_():
            return
    dirs = sorted(dirs, dircmp, itemgetter(0))
    emit('renamedirs', dirs)

def run_action(parent=None, quickaction=False):
    files = status['selectedfiles']
    if files:
        example = files[0]
    else:
        example = {}

    if quickaction:
        tags = status['selectedtags'][0]
        win = actiondlg.ActionWindow(parent, example, tags.keys())
    else:
        win = actiondlg.ActionWindow(parent, example)
    win.setModal(True)

    if quickaction:
        func = partial(applyquickaction, files)
        win.connect(win, SIGNAL("donewithmyshit"), func)
    else:
        func = partial(applyaction, files)
        win.connect(win, SIGNAL("donewithmyshit"), func)
    action_tool = PuddleDock._controls['Actions']
    parent.connect(win, SIGNAL('actionOrderChanged'),
        action_tool.updateOrder)
    parent.connect(win, SIGNAL('checkedChanged'),
        action_tool.updateChecked)
    win.show()

def run_function(parent=None, prevfunc=None):

    selectedfiles = status['selectedfiles']
    
    if not prevfunc:
        prevfunc = status['prevfunc']

    example = selectedfiles[0]
    try:
        selected_file = status['selectedtags'][0]
        selected_fields = selected_file.keys()
        text = selected_file[selected_fields[0]]
    except IndexError:
        text = example.get('title')

    if prevfunc:
        f = actiondlg.CreateFunction(prevfunc=prevfunc, parent=parent,
            showcombo=selected_fields, example=example, text=text)
    else:
        f = actiondlg.CreateFunction(parent=parent, showcombo=selected_fields,
            example=example, text=text)

    f.connect(f, SIGNAL("valschanged"), partial(run_func, selectedfiles))
    f.setModal(True)
    f.show()

def run_func(selectedfiles, func):
    status['prevfunc'] = func
    selectedtags = status['selectedtags']
    
    varnames = func.function.func_code.co_varnames
    
    if varnames and ((varnames[0] == 'tags') or (varnames[-1] == 'tags')):
        useaudio = True
    else:
        useaudio = False

    function = func.runFunction
    state = {'__total_files': unicode(len(selectedtags))}

    def tagiter():
        for i, (selected, f) in enumerate(izip(selectedtags, selectedfiles)):
            state['__counter'] = unicode(i + 1)
            fields = findfunc.parse_field_list(func.tag, f, selected.keys())
            rowtags = f.tags
            ret = {}
            for field in fields:
                val = function(rowtags.get(field, u''), rowtags, state, r_tags=f)
                if val is not None:
                    if hasattr(val, 'items'):
                        ret.update(val)
                    else:
                        ret[field] = val
            yield ret
    emit('writeselected', tagiter())

run_quick_action = lambda parent=None: run_action(parent, True)

def search_replace(parent=None):

    selectedfiles = status['selectedfiles']
    audio, selected = status['firstselection']

    try: text = to_string(selected.values()[0])
    except IndexError: text = translate('Defaults', u'')

    func = puddlestuff.findfunc.Function('replace')
    func.args = [text, u'', False, False]
    func.tag = ['__selected']

    dialog = actiondlg.CreateFunction(prevfunc=func, parent=parent,
        showcombo=selected.keys(), example=audio, text=text)

    dialog.connect(dialog, SIGNAL("valschanged"), partial(run_func, selectedfiles))
    dialog.setModal(True)
    dialog.controls[0].combo.setFocus()
    dialog.show()

def show_about(parent=None):
    win = about.AboutPuddletag(parent)
    win.setModal(True)
    win.exec_()

def tag_to_file():
    pattern = status['patterntext']
    files = status['selectedfiles']

    tf = functions.move
    state = {'__total_files': unicode(len(files))}

    def rename():
        for i, f in enumerate(files):
            state['__counter'] = unicode(i + 1)
            yield tf(f, pattern, f, state=state)['__path']

    emit('renameselected', rename())

def text_file_to_tag(parent=None):
    dirpath = status['selectedfiles'][0].dirpath

    win = helperwin.ImportWindow(parent)
    cparser = PuddleConfig()
    last_dir = cparser.get('importwindow', 'lastdir', HOMEDIR)
    if win.openFile(dirpath=last_dir):
        win.close()
        return
    win.setModal(True)
    win.patterncombo.addItems(status['patterns'])

    last_pattern = cparser.get('importwindow', 'lastpattern', u'')
    if last_pattern:
        win.patterncombo.setEditText(last_pattern)

    def fin_edit(taglist, pattern):
        cparser.set('importwindow', 'lastdir', win.lastDir)
        cparser.set('importwindow', 'lastpattern', pattern)
        emit('writeselected', taglist)

    win.connect(win, SIGNAL("Newtags"), fin_edit)
    win.show()

def update_status(enable = True):
    files = status['selectedfiles']
    pattern = status['patterntext']
    tf = lambda *args, **kwargs: encode_fn(findfunc.tagtofilename(*args, **kwargs))
    if not files:
        return
    tag = files[0]

    state = {'__counter': u'1', '__total_files': unicode(len(files))}

    x = findfunc.filenametotag(pattern, tag[PATH], True)
    emit('ftstatus', display_tag(x))

    bold_error = translate("Status Bar", "<b>%s</b>")
    
    try:
        newfilename = functions.move(tag, pattern, tag, state=state.copy())['__path']
        emit('tfstatus', translate("Status Bar",
            "New Filename: <b>%1</b>").arg(newfilename.decode('utf8', 'replace')))
    except findfunc.ParseError, e:
        emit('tfstatus', bold_error % e.message)

    oldir = path.dirname(tag.dirpath)
    try:
        newfolder = path.join(oldir, path.basename(
            safe_name(tf(pattern, tag, state=state.copy()))))
        dirstatus = translate("Dir Renaming",
            "Rename: <b>%1</b> to: <i>%2</i>").arg(tag[DIRPATH]).arg(newfolder.decode('utf8'))
        emit('renamedirstatus', dirstatus)
    except findfunc.ParseError, e:
        emit('renamedirstatus', bold_error % e.message)

    selected = status['selectedtags']
    if not selected:
        emit('formatstatus', display_tag(''))
    else:
        selected = selected[0]
    try:
        
        val = tf(pattern, tag, state=state.copy()).decode('utf8')
        newtag = dict([(key, val) for key in selected])
        emit('formatstatus', display_tag(newtag))
    except findfunc.ParseError, e:
        emit('formatstatus', bold_error % e.message)

obj = QObject()
obj.emits = ['writeselected', 'ftstatus', 'tfstatus', 'renamedirstatus',
    'formatstatus', 'renamedirs', 'onetomany', 'renameselected',
    'adddock', 'highlight', 'writeaction']
obj.receives = [('filesselected', update_status),
    ('patternchanged', update_status)]

def emit_received(signal):
    def emit(*args):
        obj.emit(SIGNAL(signal), *args)
    return emit

def emit(sig, *args):
    obj.emit(SIGNAL(sig), *args)
