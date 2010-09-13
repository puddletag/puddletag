# -*- coding: utf-8 -*-
import puddlestuff.findfunc as findfunc
from puddlestuff.puddleobjects import dircmp, safe_name, natcasecmp, LongInfoMessage
import puddlestuff.actiondlg as actiondlg
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import os, pdb
path = os.path
import puddlestuff.helperwin as helperwin
from functools import partial
from itertools import izip
from puddlestuff.audioinfo import stringtags
from operator import itemgetter
import puddlestuff.musiclib, puddlestuff.about as about
import traceback
from puddlestuff.util import split_by_tag
import puddlestuff.functions as functions

status = {}

def applyaction(files, funcs):
    r = findfunc.runAction
    state = {'numfiles': len(files)}
    state['files'] = files
    def func():
        for i, f in enumerate(files):
            state['filenum'] = i
            value = r(funcs, f, state)
            yield value
    emit('writeaction', func(), None, state)

def applyquickaction(files, funcs):
    qa = findfunc.runQuickAction
    selected = status['selectedtags']
    t = (qa(funcs, f, s.keys()) for f, s in izip(files, selected))
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
    x = lambda taglist: emit('writeselected', taglist)
    win.connect(win, SIGNAL("Newtags"), x)
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
    """The same as the cut operation in normal apps. In this case, though,
    the tag data isn't cut to the clipboard and instead remains in
    the copied atrribute."""
    selected = status['selectedtags']
    ba = QByteArray(unicode(selected).encode('utf8'))
    mime = QMimeData()
    mime.setData('application/x-puddletag-tags', ba)
    QApplication.clipboard().setMimeData(mime)

    emit('writeselected', (dict([(z, "") for z in s])
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
        win = helperwin.ExTags(parent, rows[0], status['alltags'])
    else:
        win = helperwin.ExTags(files = status['selectedfiles'], parent=parent)
    x = lambda val: emit('onetomany', val)
    obj.connect(win, SIGNAL('extendedtags'), x)
    win.show()

def filename_to_tag():
    """Get tags from the selected files using the pattern in
    self.patterncombo."""
    tags = status['selectedfiles']
    pattern = status['patterntext']

    x = [findfunc.filenametotag(pattern, tag.filepath, True)
                for tag in tags]
    emit('writeselected', x)

def format(parent=None, preview = None):
    """Formats the selected tags."""
    files = status['selectedfiles']
    pattern = status['patterntext']
    selected = status['selectedtags']

    ret = []
    tf = findfunc.tagtofilename

    for audio, s in zip(files, selected):
        val = tf(pattern, audio)
        ret.append(dict([(tag, val) for tag in s]))
    emit('writeselected', ret)

def in_lib(state, parent=None):
    if state:
        if not status['library']:
            print 'no lib loaded'
            return
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
    else:
        emit('highlight', [])

def load_musiclib(parent=None):
    try:
        m = puddlestuff.musiclib.LibChooseDialog()
    except puddlestuff.musiclib.MusicLibError:
        QMessageBox.critical(parent, 'No libraries found',
            "No supported music libraries were found. Most likely "
            "the required dependencies aren't installed. Visit the "
            "puddletag website, <a href='http://puddletag.sourceforge.net'>"
            "puddletag.sourceforge.net</a> for more details.")
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
            folder = tag.dirpath
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
            'Disable Preview Mode first to enable renaming of directories.')
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
    title = u"<b>Are you sure you want to rename the following directories?</b>"
    dirs = []
    newname = lambda x: basename(safe_name(tagtofilename(pattern, x)))
    msg = ''
    for d, f in newdirs.items():
        newfolder = path.join(dirname(d), newname(f))
        msg += u'%s -> <b>%s</b><br /><br />' % (d, newfolder)
        dirs.append([d, newfolder])

    msg = msg[:-len('<br /><br />')]

    info = LongInfoMessage('Rename dirs?', title, msg, parent)
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
    win.show()

def run_function(parent=None, prevfunc=None):

    selectedfiles = status['selectedfiles']
    
    if not prevfunc:
        prevfunc = status['prevfunc']

    example = selectedfiles[0]
    try:
        selected_file = status['selectedtags'][0]
        key = selected_file.keys()[0]
        text = selected_file[key]
    except IndexError:
        text = example.get('title')

    if prevfunc:
        f = actiondlg.CreateFunction(prevfunc=prevfunc, parent=parent,
            showcombo=False, example=example, text=text)
    else:
        f = actiondlg.CreateFunction(parent=parent, showcombo=False,
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

    def tagiter():
        for s, f in izip(selectedtags, selectedfiles):
            selected = stringtags(s, True)
            fields = set()
            for key in func.tag:
                if key == u'__selected':
                    [fields.add(z) for z in selected.keys()]
                else:
                    fields.add(key)
            rowtags = f.stringtags()
            for field in fields:
                if useaudio:
                    val = function(rowtags, rowtags)
                else:
                    val = function(selected.get(field, u''), rowtags)
                if val is not None:
                    if isinstance(val, basestring):
                        selected[field] = val
                    else:
                        selected.update(val)
            yield selected
    emit('writeselected', tagiter())

run_quick_action = lambda parent=None: run_action(parent, True)

def search_replace(parent=None):
    function = puddlestuff.findfunc.Function('replace')
    function.args = [u'', u'', False, False]
    run_function(parent, function)

def show_about(parent=None):
    win = about.AboutPuddletag(parent)
    win.setModal(True)
    win.exec_()

def tag_to_file():
    pattern = status['patterntext']
    files = status['selectedfiles']

    tf = findfunc.tagtofilename
    join = path.join
    dirname = path.dirname

    def newfilename(f):
        t = tf(pattern, f, True, f.ext)
        return join(f.dirpath, safe_name(t))

    emit('renameselected', (newfilename(f) for f in files))

def tag_to_file():
    pattern = status['patterntext']
    files = status['selectedfiles']

    tf = functions.move
    join = path.join
    dirname = path.dirname

    emit('renameselected', (tf(f, pattern)['__path'] for f in files))

def text_file_to_tag(parent=None):
    dirpath = status['selectedfiles'][0].dirpath

    filedlg = QFileDialog()
    filename = unicode(filedlg.getOpenFileName(parent, 'Select text file',
                        dirpath))

    if filename:
        win = helperwin.ImportWindow(parent, filename)
        win.setModal(True)
        win.patterncombo.addItems(status['patterns'])
        x = lambda taglist: emit('writeselected', taglist)
        win.connect(win, SIGNAL("Newtags"), x)
        win.show()

def update_status(enable = True):
    files = status['selectedfiles']
    pattern = status['patterntext']
    tf = findfunc.tagtofilename
    if not files:
        return
    tag = files[0]

    x = findfunc.filenametotag(pattern, tag.filepath, True)
    emit('ftstatus', display_tag(x))
    
    try:
        newfilename = functions.move(tag, pattern)['__path']
        emit('tfstatus', u"New Filename: <b>%s</b>" % newfilename)
    except findfunc.ParseError, e:
        emit('tfstatus', u"<b>SYNTAX ERROR: %s</b>" % e.message)

    oldir = path.dirname(tag.dirpath)
    try:
        newfolder = path.join(oldir, path.basename(
            safe_name(tf(pattern, tag))))
        dirstatus = u"Rename: <b>%s</b> to: <i>%s</i>" % (
            tag.dirpath, newfolder)
        emit('renamedirstatus', dirstatus)
    except findfunc.ParseError, e:
        emit('renamedirstatus', u"<b>SYNTAX ERROR: %s</b>" % e.message)

    selected = status['selectedtags']
    if not selected:
        emit('formatstatus', display_tag(''))
    else:
        selected = selected[0]
    try:
        val = tf(pattern, tag)
        newtag = dict([(key, val) for key in selected])
        emit('formatstatus', display_tag(newtag))
    except findfunc.ParseError, e:
        emit('formatstatus', u"<b>SYNTAX ERROR: %s</b>" % e.message)

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
