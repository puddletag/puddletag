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

status = {}

def applyaction(files, funcs):
    r = findfunc.runAction
    emit('writeselected', (r(funcs, f) for f in files))

def applyquickaction(files, funcs):
    qa = findfunc.runQuickAction
    selected = status['selectedtags']
    t = (qa(funcs, f, s.keys()) for f, s in izip(files, selected))
    emit('writeselected', t)

def auto_numbering(parent=None):
    """Shows the autonumbering wizard and sets the tracks
        numbers should be filled in"""
    tags = status['selectedfiles']
    def convert(num):
        try:
            return long(num)
        except TypeError:
            return 1

    numtracks = len(tags)

    numbers = [tag['track'][0] for tag in tags if 'track' in tag]
    if not numbers:
        mintrack = 1
        enablenumtracks = False
    else:
        mintrack = sorted(numbers, cmp=natcasecmp)[0]
        if "/" in mintrack:
            enablenumtracks = True
            mintrack, numtracks = [convert(z) for z in mintrack.split("/", 2)]
        else:
            enablenumtracks = False
            mintrack = convert(mintrack)

    win = helperwin.TrackWindow(parent, mintrack, numtracks, enablenumtracks)
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
        if f.images:
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
        return "<b>Error in pattern</b>"
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

    x = [findfunc.filenametotag(pattern, path.basename(tag.filepath), True)
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

def load_musiclib(parent=None):
    m = puddlestuff.musiclib.LibChooseDialog()
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
    emit('writeselected', (tag for tag in tags))

def paste_onto():
    data = QApplication.clipboard().mimeData().data(
                'application/x-puddletag-tags').data()
    if not data:
        return
    clip = eval(data.decode('utf8'), {"__builtins__":None},{})
    selected = status['selectedtags']
    emit('writeselected', (dict(zip(s, cliptag.values()))
                            for s, cliptag in izip(selected, clip)))

def rename_dirs(parent=None):
    """Changes the directory of the currently selected files, to
    one as per the pattern in self.patterncombo."""

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

def run_function(parent=None):

    selectedfiles = status['selectedfiles']
    prevfunc = status['prevfunc']

    example = selectedfiles[0]
    text = example.get('title')
    if prevfunc:
        f = actiondlg.CreateFunction(prevfunc=prevfunc, parent=self,
                                        showcombo=False, example=example,
                                        text=text)
    else:
        f = actiondlg.CreateFunction(parent=parent, showcombo=False,
                                        example=example, text=text)

    f.connect(f, SIGNAL("valschanged"), partial(run_func, selectedfiles))
    f.setModal(True)
    f.show()

def run_func(selectedfiles, func):
    selectedtags = status['selectedtags']
    if func.function.func_code.co_varnames[0] == 'tags':
        useaudio = True
    else:
        useaudio = False

    function = func.runFunction

    def tagiter():
        for s, f in izip(selectedtags, selectedfiles):
            tags = stringtags(s)
            rowtags = f.stringtags()
            for tag in s:
                if useaudio:
                    val = function(rowtags, rowtags)
                else:
                    val = function(tags[tag] if tag in tags else '', rowtags)
                if val is not None:
                    tags[tag] = val
            yield tags
    emit('writeselected', tagiter())

run_quick_action = lambda parent=None: run_action(parent, True)

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
        t = tf(pattern, f.filepath, True, f.ext)
        return join(dirname(f.filepath), safe_name(t))

    emit('renameselected', (newfilename(f) for f in files))

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

    x = findfunc.filenametotag(pattern, path.basename(tag.filepath), True)
    emit('ftstatus', display_tag(x))

    newfilename = (tf(pattern, tag, True, tag.ext))
    newfilename = path.join(path.dirname(tag.filepath), safe_name(newfilename))
    emit('tfstatus', u"New Filename: <b>%s</b>" % newfilename)

    oldir = path.dirname(tag.dirpath)
    newfolder = path.join(oldir, path.basename(safe_name(tf(pattern, tag))))
    dirstatus = u"Rename: <b>%s</b> to: <i>%s</i>" % (tag.dirpath, newfolder)
    emit('renamedirstatus', dirstatus)

    selected = status['selectedtags']
    if not selected:
        emit('formatstatus', display_tag(''))
    else:
        selected = selected[0]
        val = tf(pattern, tag)
        newtag = dict([(key, val) for key in selected])
        emit('formatstatus', display_tag(newtag))

obj = QObject()
obj.emits = ['writeselected', 'ftstatus', 'tfstatus', 'renamedirstatus',
                'formatstatus', 'renamedirs', 'onetomany', 'renameselected',
                'adddock']
obj.receives = [('filesselected', update_status),
                ('patternchanged', update_status)]

def emit_received(signal):
    def emit(*args):
        obj.emit(SIGNAL(signal), *args)
    return emit

def emit(sig, value):
    obj.emit(SIGNAL(sig), value)
