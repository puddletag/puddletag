# -*- coding: utf-8 -*-

import audioinfo, os, pdb, sys, string, re
from decimal import Decimal, InvalidOperation
from pyparsing import (Word, alphas,Literal, OneOrMore, NotAny, alphanums, 
    nums, ZeroOrMore, Forward, delimitedList, Combine, QuotedString, 
    CharsNotIn, White, originalTextFor, nestedExpr, 
    Optional, commaSeparatedList)
from puddleobjects import PuddleConfig
from funcprint import pprint
from puddlestuff.util import PluginFunction, translate
numtimes = 0 #Used in filenametotag to keep track of shit.
import cPickle as pickle
stringtags = audioinfo.stringtags
from copy import deepcopy
from constants import ACTIONDIR, CHECKBOX, SPINBOX, SYNTAX_ERROR, SYNTAX_ARG_ERROR
import glob
from collections import defaultdict
from functools import partial

NOT_ALL = audioinfo.INFOTAGS + ['__image']
FILETAGS = audioinfo.FILETAGS
FUNC_NAME = 'func_name'
FIELDS = 'fields'
FUNC_MODULE = 'module'
ARGS = 'arguments'

class ParseError(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)
        self.message = message

class FuncError(ParseError): pass

from functions import functions, no_fields

def arglen_error(e, passed, function, to_raise = True):
    varnames = function.func_code.co_varnames[:function.func_code.co_argcount]
    args_len = len(passed)
    param_len = len(varnames)
    if args_len > param_len:
        message = translate('Functions',
            'At most %1 arguments expected. %2 given.')
    elif args_len < param_len:
        default_len = len(function.func_defaults) if \
            function.func_defaults else 0
        if args_len < (param_len - default_len):
            message = translate('Functions',
            'At least %1 arguments expected. %2 given.')
    else:
        raise e
    message = message.arg(unicode(param_len)).arg(unicode(args_len))
    if to_raise:
        raise ParseError(message)
    else:
        return message

def convert_actions(dirpath, new_dir):
    backup = os.path.join(dirpath, 'actions.bak')
    if not os.path.exists(backup):
        os.mkdir(backup)
    if not os.path.exists(new_dir):
        os.mkdir(new_dir)
    path_join = os.path.join
    basename = os.path.basename
    for filename in glob.glob(path_join(dirpath, '*.action')):
        funcs, name = get_old_action(filename)
        os.rename(filename, path_join(backup, basename(filename)))
        save_action(path_join(new_dir, basename(filename)), name, funcs)

def filenametotag(pattern, filename, checkext = False, split_dirs=True):
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
    if split_dirs:
        filenames = filename.split(u'/')[-len(patterns):]
    else:
        filenames = [filename]
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

def get_old_action(filename):
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

def load_action(filename):
    modules = defaultdict(lambda: defaultdict(lambda: {}))
    for function in functions.values():
        if isinstance(function, PluginFunction):
            f = function.function
            modules[f.__module__][f.__name__] = function
        else:
            modules[function.__module__][function.__name__] = function
    cparser = PuddleConfig(filename)
    funcs = []
    name = cparser.get('info', 'name', u'')
    for section in cparser.sections():
        if section.startswith(u'Func'):
            get = partial(cparser.get, section)
            func_name = get(FUNC_NAME, u'')
            fields = get(FIELDS, [])
            func_module = get(FUNC_MODULE, u'')
            arguments = get(ARGS, [])
            try:
                func = Function(modules[func_module][func_name], fields)
            except IndexError:
                continue
            newargs = []
            for i, (control, arg) in enumerate(zip(func.controls, arguments)):
                if control == CHECKBOX:
                    if arg == u'False':
                        newargs.append(False)
                    else:
                        newargs.append(True)
                elif control == SPINBOX:
                    newargs.append(int(arg))
                else:
                    newargs.append(arg)
            if func.controls:
                func.args = newargs
            else:
                func.args = arguments
            funcs.append(func)
    return [funcs, name]

def load_action_from_name(name):
    filename = os.path.join(ACTIONDIR, safe_name(name) + '.action')
    return get_action(filename)

def getfunc(text, audio, dictionary=None):
    """Parses text and replaces all functions
    with their appropriate values.

    Function must be of the form $name(args)
    Returns the text unmodified if unsuccesful,"""

    if not isinstance(text, unicode):
        text = unicode(text, 'utf8')

    return function_parser(audio, dictionary=dictionary).transformString(text)

def func_tokens(dictionary, parse_action):
    func_name = Word(alphas+'_', alphanums+'_')

    func_ident = Combine('$' + func_name.copy()('funcname'))
    func_tok = func_ident + originalTextFor(nestedExpr())('args')
    func_tok.leaveWhitespace()
    func_tok.setParseAction(parse_action)
    func_tok.enablePackrat()

    rx_tok = Combine(Literal('$').suppress() + Word(nums)('num'))

    def replace_token(tokens):
        index = int(tokens.num)
        return dictionary.get(index, u'')

    rx_tok.setParseAction(replace_token)

    strip = lambda s, l, tok: tok[0].strip()
    text_tok = CharsNotIn(u',').setParseAction(strip)
    quote_tok = QuotedString('"')

    if dictionary:
        arglist = Optional(delimitedList(quote_tok | rx_tok | text_tok))
    else:
        arglist = Optional(delimitedList(quote_tok | text_tok))

    return func_tok, arglist, rx_tok

def parse_arglist(text):
    in_quote=False
    escape = False
    current = []
    arglist = []
    for i, c in enumerate(text):
        if c == u',' and not in_quote:
            arglist.append(u''.join(current).strip())
            current = []
            continue
        elif c == u'"' and not escape:
            in_quote = not in_quote
        elif c == u'\\':
            escape = not escape
        current.append(c)

    if current:
        arglist.append(u''.join(current).strip())
    elif text.endswith(u','):
        arglist.append(u'')

    return [z if z else u'""' for z in arglist]

def function_parser(m_audio, audio=None, dictionary=None):
    """Parses a function in the form $name(arguments)
    the function $name from the functions module is called
    with the arguments."""
    def replaceNestedMacros(tokens):
        #if tokens.funcname == 'if':
            #pdb.set_trace()
        if func_tok.searchString(tokens.args):
            tokens['args'] = func_tok.transformString(tokens.args)

        if tokens.funcname not in functions:
            return u''
        function = functions[tokens.funcname]
        
        if tokens.args == u'()':
            try:
                return function()
            except TypeError, e:
                arglen_error(e, [], function)

        arguments = parse_arglist(tokens.args[1:-1])
        arguments = arglist.parseString(u','.join(arguments)).asList()

        varnames = function.func_code.co_varnames
        
        for i,v in enumerate(varnames):
            if v == 'tags':
                arguments.insert(i, audio)
            elif v == 'm_tags':
                arguments.insert(i, m_audio)
        topass = []
        for no, (arg, param) in enumerate(zip(arguments, varnames)):
            if param.startswith('t_') or param.startswith('text'):
                topass.append(replacevars(arg, audio, dictionary))
            elif param.startswith('n_'):
                try:
                    if float(arg) == int(arg):
                        topass.append(int(arg))
                    else:
                        topass.append(float(arg))
                except ValueError:
                    raise ParseError(SYNTAX_ARG_ERROR % (tokens.funcname, no))
            else:
                topass.append(arg)
        try:
            ret = function(*topass)
            if ret is None:
                return u''
            return ret
        except TypeError, e:
            message = SYNTAX_ERROR.arg(tokens.funcname)
            message = message.arg(arglen_error(e, topass, function, False))
            raise ParseError(message)
        except FuncError, e:
            message = SYNTAX_ERROR.arg(tokens.funcname).arg(e.message)
            raise ParseError(message)

    if audio is None:
        audio = stringtags(m_audio)

    func_tok, arglist, rx_tok = func_tokens(dictionary, replaceNestedMacros)

    return func_tok

def parsefunc(text, audio, d=None):
    return function_parser(audio, None, d).transformString(text)

def parse_field_list(fields, audio, selected=None):
    fields = fields[::]
    not_fields = [i for i, z in enumerate(fields) if z.startswith('~')]

    if not_fields:
        index = not_fields[0]
        not_fields = fields[index:]
        not_fields[0] = not_fields[0][1:]
        while '__all' in not_fields:
            not_fields.remove('__all')

        if '__selected' in not_fields:
            if selected:
                not_fields.extend(selected)
            while '__selected' in not_fields:
                not_fields.remove('__selected')
        fields = fields[:index]
        fields.extend([key for key in audio if key not in
            not_fields and key not in NOT_ALL])

    if '__all' in fields:
        while '__all' in fields:
            fields.remove('__all')
        fields.extend([key for key in audio if key not in NOT_ALL])

    if '__selected' in fields:
        while '__selected' in fields:
            fields.remove('__selected')
        if selected:
            fields.extend(selected)
    return list(set(fields))

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
def replacevars(text, dictionary, extra = None):
    """Replaces the tags in pattern with their corresponding value in audio.

    A tag is a string enclosed by percentages, .e.g. %tag%.

    >>>replacevars('%artist% - %title%', {'artist':'Artist', 'title':'Title"}
    Artist - Title."""

    if extra is None:
        extra = {}
    
    dictionary = stringtags(dictionary)
    start = 0
    l = []
    append = l.append
    for match in _varpat.finditer(text):
        append(text[start: match.start(0)])
        try: append(dictionary[match.groups()[0]])
        except KeyError:
            try: append(extra[match.groups()[0]])
            except KeyError: pass
        start = match.end(0)
    else:
        append(text[start:])
    return u''.join(l)


def runAction(funcs, audio, state = None, quick_action=None):
    """Runs an action on audio

    funcs can be a list of Function objects or a filename of an action file (see getAction).
    audio must dictionary-like object."""
    if isinstance(funcs, basestring):
        funcs = getAction(funcs)[0]
    
    if state is None:
        state = {}
    if '__counter' not in state:
        state['__counter'] = 0
    state['__counter'] = unicode(int(state['__counter']) + 1)

    r_tags = audio
   
    if hasattr(audio, 'tags'):
        audio = deepcopy(audio.tags)
    else:
        audio = deepcopy(audio)
    
    changed = set()
    for func in funcs:
        if quick_action is None:
            fields = parse_field_list(func.tag, audio)
        else:
            fields = quick_action[::]
        ret = {}

        for field in fields:
            val = audio.get(field, u'')
            temp = func.runFunction(val, audio, state, None, r_tags)
            if temp is None:
                continue
            if isinstance(temp, basestring):
                ret[field] = temp
            elif hasattr(temp, 'items'):
                ret.update(temp)
                break
            elif not temp:
                continue
            elif hasattr(temp[0], 'items'):
                [ret.update(z) for z in temp]
                break
            elif isinstance(temp[0], basestring):
                if field in FILETAGS:
                    ret[field] = temp[0]
                else:
                    ret[field] = temp
            else:
                ret[field] = temp[0]
        ret = dict([z for z in ret.items() if z[1] is not None])
        if ret:
            [changed.add(z) for z in ret]
            audio.update(ret)
    return dict([(z, audio[z]) for z in changed])

def runQuickAction(funcs, audio, state, tag):
    """Same as runAction, except that all funcs are 
    applied not in the values stored but on audio[tag]."""
    return runAction(funcs, audio, state, tag)

def save_action(filename, name, funcs):
    f = open(filename, 'w')
    f.close()
    cparser = PuddleConfig(filename)
    cparser.set('info', 'name', name)
    set_value = lambda i, key, value: cparser.set('Func%d' % i, key, value)
    for i, func in enumerate(funcs):
        set_value(i, FIELDS, func.tag)
        set_value(i, FUNC_NAME, func.function.__name__)
        set_value(i, FUNC_MODULE, func.function.__module__)
        set_value(i, ARGS, func.args)

def saveAction(filename, actionname, funcs):
    """Saves an action to filename.

    funcs is a list of funcs, and actionname is...er...the name of the action."""
    if isinstance(filename, basestring):
        fileobj = open(filename, 'wb')
    else:
        fileobj = filename
    pickle.dump(actionname, fileobj)
    pickle.dump(funcs, fileobj)

def tagtofilename(pattern, filename, addext=False, extension=None, state=None):
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

    if not addext:
        return replacevars(getfunc(pattern, tags, state), tags, state)
    elif addext and (extension is not None):
        return replacevars(getfunc(pattern, tags, state), tags, state) + os.path.extsep + extension
    else:
        return replacevars(getfunc(pattern, tags, state), tags, state) + os.path.extsep + tags["__ext"]

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

    def __init__(self, funcname, fields=None):
        """funcname must be either a function or string(which is the functions name)."""
        if type(funcname) is str:
            self.function = functions[funcname]
        elif isinstance(funcname, PluginFunction):
            self.function = funcname.function
            self.doc = [u','.join([funcname.name, funcname.print_string])] + \
                [','.join(z) for z in funcname.args]
            self.info = [funcname.name, funcname.print_string]
        else:
            self.function = funcname

        self.reInit()

        self.funcname = self.info[0]
        if fields is not None:
            self.tag = fields
        else:
            self.tag = ''
        self.args = None
        
        self.controls = self._getControls()

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

    def runFunction (self, text=None, m_tags=None, state=None, tags=None, r_tags=None):
        function = self.function
        varnames = function.func_code.co_varnames[:function.func_code.co_argcount]
        
        if not varnames:
            return function()
        
        if tags is None:
            tags = stringtags(m_tags)
        
        if state is None:
            state = {}
        
        arguments = self.args[::]
        first_text = True

        d = {'tags': tags, 'r_tags': r_tags, 'm_tags': m_tags, 'state':state}

        offset = 0
        for i, v in enumerate(varnames):
            if v in d:
                arguments.insert(i + offset, d[v])
                offset += 1

        if varnames[0] in d:
            first_text = False
        
        if first_text:
            if isinstance(text, basestring):
                if varnames[0].startswith('m_'):
                    return function([text], *arguments)
                else:
                    return function(text, *arguments)
            elif varnames[0].startswith('m_'):
                return function(text, *arguments)
            else:
                ret = (function(v, *arguments) for v in text)
                temp = []
                append = temp.append
                [append(z) for z in ret if z not in temp]
                return temp
        else:
            return function(*arguments)


    def description(self):
        d = [u", ".join(self.tag)] + self.args
        return pprint(translate('Functions', self.info[1]), d)
        
    def _getControls(self):
        identifier = QuotedString('"') | CharsNotIn(',')
        arglist = delimitedList(identifier)
        docstr = self.doc[1:]
        return [(arglist.parseString(line)[1]).strip() for line in docstr]

    def setTag(self, tag):
        self.tag = tag
        self.fields = tag

    def addArg(self, arg):
        if self.function.func_code.co_argcount > len(self.args) + 1:
            self.args.append(arg)

