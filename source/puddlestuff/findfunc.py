#findfunc.py

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


import audioinfo, os, pdb, functions, sys, string
if sys.version_info[:2] >= (2, 5): import re as sre
else: import sre
try:
    from pyparsing import Word, alphas,Literal, OneOrMore,NotAny, alphanums, nums, ZeroOrMore, Forward, delimitedList, Combine, QuotedString
except ImportError:
    sys.stderr.write("The PyParsing module wasn't found. Did you install it correctly?")
    self.exit(0)
from puddlesettings import PuddleConfig
numtimes = 0 #Used in filenametotag to keep track of shit.. Do not modify.

import cPickle as pickle
stringtags = audioinfo.stringtags

def filenametotag(pattern, filename, checkext = False):
    """Retrieves tag values from your filename
        pattern is the rule with which to extract
        the tags from filename. Which does not have to
        be an existing file. Returns a dictionary with
        elements {tag:value} on success.
        If checkext=True, then the extension of the filename
        is included during the extraction process.

        E.g. if you want to retrieve a tags according to
        >>>pattern = "%artist% - %track% - %title%"
        You set a dictionary like so...
        >>>filename = "Mr. Jones - 123 - Title of a song"
        >>>filenametotag(pattern,filename)
        {"artist":"Mr. Jones", "track":"123","title":"Title of a song"}
        If checkext = True then filenametotag just operates on the
        filename and not the extension of the filename.

        E.g.
        >>>filename = "Mr. Jones - 123 - Title of a song.mp3"
        >>>filenametotag(pattern,filename)
        {"artist":"Mr. Jones", "track":"123","title":"Title of a song.mp3"}
        >>>filenametotag(pattern,filename, True)
        {"artist":"Mr. Jones", "track":"123","title":"Title of a song"}

        None is the returned if the pattern does not match the filename."""

    if checkext:
        filename = os.path.splitext(filename)[0]

    text = re_escape(pattern)
    taglist = []

    #what is run numtimes times. What I want to do is
    #match all but the last tag as non-greedy.
    #Otherwise filenames such as "01. artistname"
    #won't be matched.
    def what(s, loc, tok):
        global numtimes
        taglist.append(tok[0][1:-1])
        numtimes -= 1
        if numtimes == 0:
            return "(.*)"
        return "(.*?)"

    #Replace the tags with a regular expression
    tag = Combine(Literal("%") + OneOrMore(Word(alphas)) + Literal("%")).setParseAction(what)
    global numtimes
    numtimes = len([z for z in tag.scanString(text)])
    text = tag.transformString(text)
    try:
        tags = sre.search(text, filename).groups()
    except AttributeError:
        #AttributeError means that the expression probabably wasn't found.
        return

    mydict={}
    for i in range(len(tags)):
        if mydict.has_key(taglist[i]):
            mydict[taglist[i]] = ''.join([mydict[taglist[i]],tags[i]])
        else:
            mydict[taglist[i]]=tags[i]

    if mydict.has_key("dummy"):
        del(mydict["dummy"])

    return mydict

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
        #Since, a functions docstring wouldn't be reflected back to puddletag
        #if it were changed calling this function to 're-read' it is a good idea.
        self.doc = self.function.__doc__.split("\n")

        identifier = QuotedString('"') | Combine(Word(alphanums + ' !"#$%&\'()*+-./:;<=>?@[\\]^_`{|}~'))
        tags = delimitedList(identifier)

        self.info = [z for z in tags.parseString(self.doc[0])]

    def setArgs(self, args):
        self.args = args

    def runFunction (self, arg1 = None, audio = None):
        varnames = self.function.func_code.co_varnames
        if isinstance(arg1, (list,tuple)):
            arg1 = arg1[0]
        if varnames[-1] == 'tags':
            return self.function(*([arg1] + self.args + [audio]))
        elif varnames[0] == 'tags':
            return self.function(*([audio] + self.args))
        else:
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

def removeSpaces(text):
    for char in string.whitespace:
        text = text.replace(char, '')
    return text.lower()

def getActionFromName(name):
    actionpath = os.getenv('HOME') + u'/.config/Puddle Inc./' + removeSpaces(name) + '.action'
    funcs = getAction(actionpath)
    return funcs

def getAction(filename):
    """Gets the action from filename, where filename is either a string or
    file-like object.

    An action is just a list of functions with a name attached. In puddletag
    these are stored as pickled objects.

    Returns [list of Function objects, action name]."""
    if isinstance(filename, basestring):
        f = open(filename, "rb")
    else:
        f = filename
    name = pickle.load(f)
    funcs = pickle.load(f)
    f.close()
    return [funcs, name]

def getfunc(text, audio):
    """Parses text and replaces all functions
    with their appropriate values.

    Function must be of the form $name(args)
    Returns the text unmodified if unsuccesful,"""

    #This function exists because I couldn't figure out
    #how to get PyParsing to leave alone anything but the function
    #without a lot of buggy work.
    #So, if you have a way to do that, send me a mail at concentricpuddle@gmail.com

    pat = sre.compile(r'[^\\]\$[a-z_]+\(')

    addspace = False
    #pat doesn't match if the text starts with the pattern, because there isn't
    #a character in front of the function
    if text.startswith("$"):
        text = " " + text
        addspace = True

    start = 0
    #Get the functions
    #Got this from comp.lang.python
    while 1:
        match = pat.search(text, start)
        if match is None: break
        idx = match.end(0)
        num_brackets_open = 1
        try:
            while num_brackets_open > 0:
                if text[idx] == ')':
                    num_brackets_open -= 1
                elif text[idx] == '(':
                    num_brackets_open += 1
                idx += 1  # Check for end-of-text!
        except IndexError:
            return text
        #Replace a function with its parsed text
        torep = text[match.start(0) + 1: idx]
        replacetext = parsefunc(text[match.start(0) + 1: idx], audio)
        text = text.replace(torep, replacetext)
        idx += len(replacetext) - len(torep)
        start = idx + 1
    if addspace:
        return text[1:]
    return text

def parsefunc(text, audio):
    """Parses a function in the form $name(arguments)
    the function $name from the functions module is called
    with the arguments."""

    identifier = QuotedString('"') | Combine(ZeroOrMore("\$") + Word(alphanums + "_ '!#$%&\'*+-./:;<=>?@[\\]^`{|}~"))
    integer  = Word( nums )
    funcstart =  NotAny("\\") + Combine(Literal("$") + ZeroOrMore(Word("_" + alphas)) + "(")

    def callfunc(s,loc,tok):
        arguments = tok[1:]
        function = getattr(functions,tok[0][1:-1])
        for i, param in enumerate(function.func_code.co_varnames):
            if param.startswith('text'):
                arguments[i] = replacevars(arguments[i], audio)
        return function(*arguments)

    content = Forward()
    expression = funcstart + delimitedList(content) + Literal(")").suppress()
    expression.setParseAction(callfunc)
    content << (expression | identifier | integer)
    return content.transformString(text)

# This function is from name2id3 by  Kristian Kvilekval
def re_escape(rex):
    """Escape regular expression special characters"""
    escaped = ""
    for ch in rex:
        if ch in r'^$[]\+*?.(){},|' : escaped = escaped + '\\' + ch
        else: escaped = escaped + ch
    return escaped


def replacevars(pattern, audio):
    """Replaces the tags in pattern with their corresponding value in audio.

    A tag is a string enclosed by percentages, .e.g. %tag%.

    >>>replacevars('%artist% - %title%', {'artist':'Artist', 'title':'Title"}
    Artist - Title."""

    for tag in audio.keys():
        if not audio[tag]:
            audio[tag] = ''
        pattern = pattern.replace(unicode('%' + unicode(tag) + '%'),
                                        unicode(audio[tag]))
    return pattern


def runAction(funcs, audio):
    """Runs an action on audio

    funcs can be a list of Function objects or a filename of an action file (see getAction).
    audio must dictionary-like object."""
    if isinstance(funcs, basestring):
        funcs = getAction(funcs)[0]

    audio = stringtags(audio)
    for func in funcs:
        tag = func.tag
        val = {}
        if tag[0] == "__all":
            tag = audio.keys()
        for z in tag:
            try:
                val[z] = func.runFunction(audio[z], audio = audio)
            except KeyError:
                """The tag doesn't exist or is empty.
                In either case we do nothing"""
        val = dict([z for z in val.items() if z[1]])
        if val:
            audio.update(val)
    return audio

def runQuickAction(funcs, audio, tag):
    """Same as runAction, except that all funcs are applied not in the values stored
    but on audio[tag]."""
    if isinstance(funcs, basestring):
        funcs = getAction(funcs)[0]

    audio = stringtags(audio)
    tags = {}
    for func in funcs:
        val = {}
        if tag[0] == "__all":
            tag = audio.keys()
        for z in tag:
            try:
                val[z] = func.runFunction(tags[z], audio = audio)
            except KeyError:
                try:
                    val[z] = func.runFunction(audio[z], audio = audio)
                except KeyError:
                    """The tag doesn't exist or is empty.
                    In either case we do nothing"""
        val = dict([z for z in val.items() if z[1]])
        if val:
            tags.update(val)
    return tags

def saveAction(filename, actionname, funcs):
    """Saves an action to filename.

    funcs is a list of funcs, and actionname is...er...the name of the action."""
    if isinstance(filename, basestring):
        fileobj = open(filename, 'wb')
    else:
        fileobj = filename
    pickle.dump(actionname, fileobj)
    pickle.dump(funcs, fileobj)

def tagtofilename(pattern, filename, addext=False, extension=None):
    """
    tagtofilename sets the filename of an mp3 or ogg file
    according to the rule specified in pattern.

    E.g. if you have a mp3 file with
    tags = {"artist": "Amy Winehouse",
            "title": "Shitty Song",
            "track": "12"}
    and you want to create a filename like,
    >>>filename = "Amy Winehouse - 12 - Shitty Song" # you'd use
    >>>pattern = "%artist% - %track% - %title%"
    >>>tagtofilename(pattern,filename)
    Amy Winehouse - 12 - Shitty Song

    You can also have filename be the path to an music file.
    The tag of that file will then be used.

    If addext == True, then the extension of the file
    is added to the returned filename.

    You can use extension to set the extension of the file
    if the files extension does not match its contents.
    This is useful if you pass tagtofilename a dictionary, but
    want to add a '.mp3' extension.

    For instance, using pattern and filename as before:
    >>>tagtofilename(pattern, filename, True, ".mp3")
    Amy Winehouse - 12 - Shitty Song.mp3

    Note that addext has to be True if you want to set your own extension.

    tagtofilename returns None if tags are missing in filename, but
    used in pattern or if unsuccessful in any way.

    Lastly, function may also be in setting the filename. These
    functions are defined in functions.py and may be called by using
    a $functionname.

    E.g
    >>>pattern = '%artist% - %num(%track%,3) - %title%' #see functions.py for more on num.
    >>>tagtofilename(pattern, filename, True, '.mp3')
    Amy Winehouse - 012 - Shitty Song.mp3"""

    #First check if a filename was passed or a dictionary.
    if not isinstance(filename, basestring):
        #if it was a dictionary, then use that as the tags.
        tags = filename
    else:
        tags = audioinfo.Tag(filename)
        if not tags:
            return 0
    tags = stringtags(tags)

    if not addext:
        return replacevars(getfunc(pattern, tags), tags)
    elif addext and (extension is not None):
        return replacevars(getfunc(pattern, tags), tags) + os.path.extsep + extension
    else:
        return replacevars(getfunc(pattern, tags), tags) + os.path.extsep + tags["__ext"]