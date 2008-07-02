"""This module contains the function needed
    to extract tags from files according to patterns
    specified. 
    
    See the docstrings for tagfromfilename and
    filenametotag for more details"""

import sre,audioinfo,os,pdb
import eyeD3
from pyparsing import Word, alphas,Literal, OneOrMore,NotAny, alphanums, nums, ZeroOrMore, Forward, delimitedList, Combine, NotAny
import functions
numtimes = 0

def parsefunc(text):
    identifier = Combine(ZeroOrMore("\$") + Word(alphanums + "_ \\($%!@"))
    integer  = Word( nums )
    funcstart =  NotAny("\\") + Combine(Literal("$") + ZeroOrMore(Word(alphanums + "_")) + "(")
    arg = identifier | integer
    args = arg + ZeroOrMore("," + arg)
    #expression = functor + lparen + args + rparen
    
    def what(s,loc,tok):
        arguments = tuple(tok[1:])
        funcname = tok[0][1:-1]
        try:
            return getattr(functions,funcname)(*arguments)
        except: 
            #pdb.set_trace()
            getattr(functions,funcname)(*arguments)
    
    
    ignored = ZeroOrMore(Word(alphanums + " !@#$^&*(){}|\\][?+=/_~`"))
    
    content = Forward()
    expression = funcstart + delimitedList(content) + Literal(")").suppress()
    expression.setParseAction(what)
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
    """getfunc(text)
    parses the functions it text and replaces
    them with their return value. The functions
    are defined in functions.py
    
    Function must be of the form $name(args)
    Returns None if unsuccesful"""
    pat = sre.compile(r'[^\\]\$[a-z]+\(')
    
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
        #print text[match.start(0)+1:idx]
        #Replace a function with its parsed text
        text=text.replace(text[match.start(0)+1:idx],
                        parsefunc(text[match.start(0)+1:idx]))
        start = idx + 1
    return text


def filenametotag(pattern, filename, checkext = False):    
    """filenametotag(pattern,filename,checkext=False)
        Retrieves tag values from your filename
        pattern is the rule with which to extract
        the tags from filename. Which does not have to
        be an existing file.
        Returns a dictionary with
        elements {tag:value} on success.
        If checkext=True, then the extension of the filename
        is included during the extraction process.
        
        E.g. if you want to retrieve a tags according to
        pattern="%artist% - %track% - %title%"
        You set a dictionary like so...
        filename = "Mr. Jones - 123 - Title of a song"
        filename to tag returns
        {"artist":"Mr. Jones", "track":"123","title":"Title of a song" """
    
    #Make sure percentages aren't escaped
    pat = sre.compile(r'[^\\|.*]%\w*%')
    
    #if pattern == "%track% %title%": pdb.set_trace()
    if checkext:
        filename=os.path.splitext(filename)[0]
    #if pattern == '%track%. %title%': pdb.set_trace()
    text=re_escape(pattern)
    taglist = []
    def what(s, loc, tok):
        global numtimes
        taglist.append(tok[0][1:-1])
        numtimes -=1 
        if numtimes == 0:
            return "(.*)"
        return "(.*?)"
    #Replace the tags with the regular expression "(.*)"
    tag = Combine(Literal("%") + OneOrMore(Word(alphas)) + Literal("%")).setParseAction(what)
    global numtimes
    numtimes = len([z for z in tag.scanString(text)])
    text = tag.transformString(text)
    try:
        tags=sre.search(text, filename).groups()
    except AttributeError:
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
    
def tagtofilename(pattern,filename,addext=False,extension=None):
    """tagtofilename(pattern,filename)
    tagtofilename sets the filename of an mp3 or ogg file
    according to the rule specified in pattern.
    returns the filename if successful
    returns 0 if not.
    tagtofilename does nothing to the original
    file though.
    
    E.g. if you want to set a tag according to
    pattern = "%artist% - %track% - %title%"
    filename = "Mr. Jones - 123 - Title of a song"
    call tagtofilename(pattern,filename)"""
    
    #First check if a filename was passed or a dictionary.
    if type(filename)==dict:
        #if it was a dictionary, then use that as the tags.
        tags=filename
    else:
        tag=audioinfo.Tag()
        if tag.link(filename)==0 or tag.link(filename)==1:
            return 0
        #get tag info
        tag.gettags()
        tags=tag.tags
    
    
    #for each tag with a value, replace it in the pattern
    #with that value
    pattern=unicode(pattern)
    for idx in tags.keys():
        if tags[idx]==None:
            tags[idx]=""
        try:
            pattern=pattern.replace(unicode('%' + idx + '%'), unicode(tags[idx]))
        except UnicodeDecodeError:
            print "Unicode Error in pattern.replace with, ", tags["__filename"]
    
    #ret=getfunc(pattern)
    #if ret==pattern:
        #for idx in tags.keys():
            #if tags[idx]==None:
                #tags[idx]=""
                        
            #patterncopy=patterncopy.replace(unicode('%' + idx + '%') ,unicode(tags[idx]))
        #return patterncopy

    if addext==False:
        return getfunc(pattern)
    elif (addext==True) and (extension is not None):
        return getfunc(pattern) + os.path.extsep + extension
    else:
        return getfunc(pattern) + os.path.extsep + tag.filetype
