# -*- coding: utf-8 -*-
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


import audioinfo, os, pdb, sys, string, re
from decimal import Decimal, InvalidOperation
try:
    from pyparsing import Word, alphas,Literal, OneOrMore,NotAny, alphanums, nums, ZeroOrMore, Forward, delimitedList, Combine, QuotedString, CharsNotIn, White, originalTextFor, nestedExpr, Optional, commaSeparatedList
except ImportError:
    sys.stderr.write("The PyParsing module wasn't found. Did you install it correctly?\n")
    sys.exit(0)
from puddlesettings import PuddleConfig
from funcprint import pprint
from puddlestuff.util import PluginFunction
numtimes = 0 #Used in filenametotag to keep track of shit.
import cPickle as pickle
stringtags = audioinfo.stringtags

NOT_ALL = audioinfo.INFOTAGS

class ParseError(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)
        self.message = message

class FuncError(ParseError): pass

from functions import functions

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


    e = Combine(Literal("%").suppress() + OneOrMore(Word(alphas)) + Literal("%").suppress())
    patterns = filter(None, pattern.split(u'/'))
    filenames = filename.split(u'/')[-len(patterns):]
    mydict = {}
    for pattern, filename in zip(patterns, filenames):
        new_fields = tagtotag(pattern, filename, e)
        if not new_fields:
            continue
        for key in new_fields:
            if key in mydict:
                mydict[key] += new_fields[key]
            else:
                mydict[key] = new_fields[key]
    if mydict:
        if mydict.has_key("dummy"):
            del(mydict["dummy"])
        return mydict
    return {}

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

def getActionFromName(name):
    actionpath = os.path.join(os.getenv('HOME'),'.puddletag', removeSpaces(name) + '.action')
    funcs = getAction(actionpath)
    return funcs

def getfunc(text, audio):
    """Parses text and replaces all functions
    with their appropriate values.

    Function must be of the form $name(args)
    Returns the text unmodified if unsuccesful,"""

    #This function exists because I couldn't figure out
    #how to get PyParsing to leave alone anything but the function
    #without a lot of buggy work.
    #So, if you have a way to do that, send me a mail at concentricpuddle@gmail.com
    if not isinstance(text, unicode):
        text = unicode(text, 'utf8')

    return function_parser(audio).transformString(text)

def function_parser(audio):
    """Parses a function in the form $name(arguments)
    the function $name from the functions module is called
    with the arguments."""
    
    ident = Word(alphas+'_', alphanums+'_')

    funcIdent = Combine('$' + ident.copy()('funcname'))
    funcMacro = funcIdent + originalTextFor(nestedExpr())('args')
    funcMacro.leaveWhitespace()
    #def strip(s, l, tok):
        #print s, l, tok
        #return s.strip()
    strip = lambda s, l, tok: tok[0].strip()
    arglist = Optional(delimitedList(QuotedString('"') | 
        CharsNotIn(u',').setParseAction(strip)))

    def replaceNestedMacros(tokens):
        if funcMacro.searchString(tokens.args):
            tokens['args'] = funcMacro.transformString(tokens.args)
        
        if tokens.funcname not in functions:
            return u''
        function = functions[tokens.funcname]
        
        if tokens.args == u'()':
            return function()

        arguments = arglist.parseString(tokens.args[1:-1]).asList()
        
        varnames = function.func_code.co_varnames
        if varnames[0] == 'tags':
            arguments.insert(0, audio)
        topass = []
        for no, (arg, param) in enumerate(zip(arguments, varnames)):
            if param.startswith('t_') or param.startswith('text'):
                topass.append(replacevars(arg, audio))
            elif param.startswith('n_'):
                try:
                    if float(arg) == int(arg):
                        topass.append(int(arg))
                    else:
                        topass.append(float(arg))
                except ValueError:
                    message = 'SYNTAX ERROR: %s expects a number at argument %d.'
                    raise ParseError(message % (tokens.funcname, no))
            else:
                topass.append(arg)
        try:
            return function(*topass)
        except TypeError, e:
            message = e.message
            if message.endswith(u'given)'):
                start = message.find(u'takes')
                message = u'SYNTAX ERROR in $%s: %s' % (tokens.funcname, message[start:])
                raise ParseError(message)
            else:
                raise e
        except FuncError, e:
            message = u'SYNTAX ERROR in $%s: %s' % (tokens.funcname, e.message)
            raise ParseError(message)
        
        return functions[tokens.funcname](*args)

    funcMacro.setParseAction(replaceNestedMacros)

    return funcMacro

def parsefunc(text, audio):
    return function_parser(audio).transformString(text)

# This function is from name2id3 by  Kristian Kvilekval
def re_escape(rex):
    """Escape regular expression special characters"""
    escaped = ""
    for ch in rex:
        if ch in r'^$[]\+*?.(){},|' : escaped = escaped + '\\' + ch
        else: escaped = escaped + ch
    return escaped

def removeSpaces(text):
    for char in string.whitespace:
        text = text.replace(char, '')
    return text.lower()

_varpat = re.compile('%([\w ]+)%')
def replacevars(text, dictionary):
    """Replaces the tags in pattern with their corresponding value in audio.

    A tag is a string enclosed by percentages, .e.g. %tag%.

    >>>replacevars('%artist% - %title%', {'artist':'Artist', 'title':'Title"}
    Artist - Title."""
    start = 0
    l = []
    append = l.append
    for match in _varpat.finditer(text):
        append(text[start: match.start(0)])
        try:
            append(dictionary[match.groups()[0]])
        except KeyError:
            pass
        start = match.end(0)
    else:
        append(text[start:])
    return u''.join(l)


def runAction(funcs, audio):
    """Runs an action on audio

    funcs can be a list of Function objects or a filename of an action file (see getAction).
    audio must dictionary-like object."""
    if isinstance(funcs, basestring):
        funcs = getAction(funcs)[0]

    audio = stringtags(audio)
    changed = set()
    for func in funcs:
        tag = func.tag
        val = {}
        if tag[0] == u"__all":
            tag = [key for key in audio.keys() if key not in NOT_ALL]
        for z in tag:
            try:
                t = audio.get(z)
                ret = func.runFunction(t if t else u'', audio = audio)
                if isinstance(ret, basestring) or not ret:
                    val[z] = ret
                else:
                    val.update(ret)
                    break
            except KeyError:
                """The tag doesn't exist or is empty.
                In either case we do nothing"""
            except ParseError, e:
                message = u'SYNTAX ERROR IN FUNCTION <b>%s</b>: %s' % (
                    func.funcname, e.message)
                raise ParseError(message)
        val = dict([z for z in val.items() if z[1] is not None])
        if val:
            [changed.add(z) for z in val]
            audio.update(val)
    return dict([(z,audio[z]) for z in changed])

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
            tag = [key for key in audio.keys() if key not in NOT_ALL]
        for z in tag:
            try:
                val[z] = func.runFunction(tags[z], audio = audio)
            except KeyError:
                try:
                    val[z] = func.runFunction(audio[z], audio = audio)
                except KeyError:
                    """The tag doesn't exist or is empty.
                    In either case we do nothing"""
        val = dict([z for z in val.items() if z[1] is not None])
        if val:
            tags.update(val)
    return dict([(z, tags[z]) for z in tag if z in tags])

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

def tagtotag(pattern, text, expression):
    """See filenametotag for an implementation example and explanation.

    pattern is a string with position of each token in text
    text is the text to be matched
    expression is a pyparsing object (i.e. what a token look like)

    >>>tagtotag('$1 - $2', 'Artist - Title', Literal('$').suppress() + Word(nums))
    {'1': 'Artist', '2': 'Title'}
    """
    pattern = re_escape(pattern)
    taglist = []
    def what(s, loc, tok):
        global numtimes
        taglist.append(tok[0])
        numtimes -= 1
        if numtimes == 0:
            return "(.*)"
        return "(.*?)"
    expression.setParseAction(what)
    global numtimes
    numtimes = len([z for z in expression.scanString(pattern)])
    if not numtimes:
        return
    pattern = expression.transformString(pattern)
    try:
        tags = re.search(pattern, text).groups()
    except AttributeError:
        #No matches were found
        return  u''
    mydict={}
    for i in range(len(tags)):
        if mydict.has_key(taglist[i]):
            mydict[taglist[i]] = ''.join([mydict[taglist[i]],tags[i]])
        else:
            mydict[taglist[i]]=tags[i]
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
            self.function = functions[funcname]
        elif isinstance(funcname, PluginFunction):
            self.function = funcname.function
            self.doc = [','.join([funcname.name, funcname.print_string])] + [','.join(z) for z in funcname.args]
            self.info = [funcname.name, funcname.print_string]
        else:
            self.function = funcname

        self.reInit()

        self.funcname = self.info[0]
        self.tag = ""

    def reInit(self):
        #Since this class gets pickled in ActionWindow, the class is never 'destroyed'
        #Since, a functions docstring wouldn't be reflected back to puddletag
        #if it were changed calling this function to 're-read' it is a good idea.
        if not self.function.__doc__:
            return
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
        if not varnames:
            return self.function()
        if varnames[-1] == 'tags':
            return self.function(*([arg1] + self.args + [audio]))
        elif varnames[0] == 'tags':
            return self.function(*([audio] + self.args))
        else:
            return self.function(*([arg1] + self.args))

    def description(self):
        d = [", ".join(self.tag)] + self.args
        return pprint(self.info[1], d)

    def setTag(self, tag):
        self.tag = tag

    def addArg(self, arg):
        if self.function.func_code.co_argcount > len(self.args) + 1:
            self.args.append(arg)

