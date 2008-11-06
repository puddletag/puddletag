"""This module contains the functions needed
    to extract tags from files according to patterns
    specified. 
    
    See the docstrings for tagfromfilename and
    filenametotag for more details"""
    
"""findfunc.py

Copyright (C) 2008 concentricpuddle

This file is part of puddletag, a semi-good music tag editor.

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""

import audioinfo, os, pdb, functions, string
import sys
if sys.version_info[0] >= 2 and sys.version_info[1] > 4:
    import re as sre
else:
    import sre
    
from pyparsing import Word, alphas,Literal, OneOrMore,NotAny, alphanums, nums, ZeroOrMore, Forward, delimitedList, Combine, NotAny
numtimes = 0 #Used in filenametotag to keep track of shit.. Do not modify.

def parsefunc(text):
    """Parses a function in the form $name(arguments)
    the function $name from the functions module is called
    with the arguments."""
    
    identifier = Combine(ZeroOrMore("\$") + Word(alphanums + "_ '!#$%&\'*+-./:;<=>?@[\\]^`{|}~"))
    integer  = Word( nums )
    funcstart =  NotAny("\\") + Combine(Literal("$") + ZeroOrMore(Word(alphanums + "_")) + "(")
    arg = identifier | integer
    args = arg + ZeroOrMore("," + arg)

    
    def callfunc(s,loc,tok):
        arguments = tuple(tok[1:])
        funcname = tok[0][1:-1]
        try:
            return getattr(functions,funcname)(*arguments)
        except: 
            getattr(functions,funcname)(*arguments)
    
    
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

def getfunc(text):
    """Parses text and replaces all functions
    with their appropriate values.
    
    Function must be of the form $name(args)
    Returns None if unsuccesful"""
    
    pat = sre.compile(r'[^\\]\$[a-z]+\(')
    
    addspace = False
    #pat doesn't match if the text starts with the pattern, because there isn't
    #a character in front of the function
    if text.startswith("$"):
        text = " " + text
        addspace = True
        
    start = 0
    funcs=[]
    #Get the functions
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
            #print "indexerror ", text
            return text

        #Replace a function with its parsed text
        text = text.replace(text[match.start(0) + 1: idx],
                        parsefunc(text[match.start(0) + 1: idx]))
        start = idx + 1
    if addspace:
        return text[1:]
    return text


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
    
    #Make sure percentages aren't escaped
    pat = sre.compile(r'[^\\|.*]%\w*%')
    
    #if pattern == "%track% %title%": pdb.set_trace()
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
        #Attribute Error means that the expression probabably wasn't found.
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
    if type(filename) == dict:
        #if it was a dictionary, then use that as the tags.
        tags = filename
    else:
        tag = audioinfo.Tag()
        if tag.link(filename) is None:
            return 0
        #get tag info
        tags = tag.tags
    
    
    #for each tag with a value, replace it in the pattern
    #with that value
    pattern = unicode(pattern)
    for idx in tags.keys():
        if tags[idx] is None:
            tags[idx] = ""
        try:
            pattern=pattern.replace(unicode('%' + unicode(idx) + '%'), unicode(tags[idx]))
        except UnicodeDecodeError:
            print "Unicode Error in pattern.replace with, ", tags["__filename"]


    if addext == False:
        return getfunc(pattern)
    elif (addext == True) and (extension is not None):
        return getfunc(pattern) + os.path.extsep + extension
    else:
        return getfunc(pattern) + os.path.extsep + tag.filetype
