# -*- coding: utf-8 -*-
#functions.py

#Copyright (C) 2008-2010 concentricpuddle, GPLv2

"""A modules that defines function that are to be used througout puddletag.

Basically, this modules contains functions that are called via
the getfunc function in findfunc.py. Most of the time though,
getfunc isn't called directly, but via the tagtofilename function
also found in the findfunc module.

The docstrings of these functions are also used as metadata in the
actiondlg modules in order to draw windows to allow the user
to create and edit actiondlg.Function objects.

The first parameter of a function should be name one of two things.
If it's named text, a line of text[like tag value] will be passed to it.
If it's named tags, then a dictionary of tags is passed to it.

The other restriction is that if the function is not successful, return None.

Now for the docstrings of the functions:
The first line of the docstring contains the function name as shown to
the user and the description(what the user sees once they've set values).

After the first line, there should be a line for each parameter of the function
not including the first[it's either tags or text].

actiondlg.FunctionDialog creates controls using this line.
This line is further split into three parts
    The first contains the Explanatory Label above the control.
    The Second contains the control itself, either text, combo or check
    The third contains the default arguments as shown to the user."""

from puddleobjects import PuddleConfig, safe_name, fnmatch
import string, pdb, sys, audioinfo, decimal, os, pyparsing, re, imp, shutil, time, unicodedata

true = u'1'
false = u'0'
path = os.path

def add(text,text1):
    D = decimal.Decimal
    try:
        return unicode((D(unicode(text)) + D(unicode(text1))).normalize().to_eng_string())
    except decimal.InvalidOperation:
        return

def check_truth(text):
    return 0 if ((not text) or (text == u'0')) else 1

def and_(text, text1):
    return unicode(check_truth(text) and check_truth(text1))

def caps(text):
    return titleCase(text)

def caps2(text):
    upcase = [z for z,i in enumerate(text) if i in string.uppercase]
    text = list(titleCase(text))
    for z in upcase:
        text[z] = text[z].upper()
    return "".join(text)

def caps3(text):
    try:
        start = re.search("\w", text, re.U).start(0)
    except AttributeError:
        return
    return text[:start] + text[start].upper() + text[start + 1:].lower()

def char(text):
    try:
        return unicode(ord(text))
    except TypeError:
        return

def changeartist(artist, *files):
    for audio in files:
        audio['artist'] = artist
        audio.save()

def div(text,text1):
    D = decimal.Decimal
    try:
        return unicode((D(text) / D(text1)).normalize())
    except decimal.InvalidOperation:
        return


def featFormat(text, ftstring = "ft", opening = "(", closing = ")"):
    #'''Remove brackets from (ft), Brackets remove: $0
    #Feat &String, text,  ft
    #O&pening bracket, text, "("
    #C&losing bracket, text, ")"'''
    ##Removes parenthesis from feat string
    ##say if you had a title string "Booty (ft the boot man)"
    ##featFormat would return "Booty ft the boot man"
    ##In the same way "Booty (ft the boot man"
    ##would give "Booty ft the boot man"
    ##but "Booty ft the boot man)" would remain unchanged.
    ##the opening and closing parens can be changed to whatever.
    textli = list(text)
    start = text.find(ftstring)
    if start == -1: return text
    if start != 0:
        if text[start -1] == opening:
            del (textli[start - 1])
            closeparen = "".join(textli).find(closing, start)
            if closeparen == -1: return "".join(textli)
            del textli[closeparen]
            return "".join(textli)
    return text

def finddups(tracks, key = 'title', method=None):
    from puddleobjects import dupes
    li = []
    for z in tracks:
        try:
            li.append(z[key])
        except KeyError:
            li.append(None)
    return dupes(li, method)

def formatValue(tags, pattern):
    """Format value, Format $0 using $1
&Format string, text"""
    return findfunc.tagtofilename(pattern, tags)

format_value = formatValue

def ftArtist(tags, ftval = " ft "):
    #'''Get FT Artist, "FT Artist: $0, String: $1"
#Featuring &String, text, " ft "'''

    try:
        text = tags["artist"]
    except KeyError:
        return
    index = text.find(ftval)
    if index != -1:
        return(text[:index])

def ftTitle(tags, ftval = " ft ", replacetext = None):
    #'''Get FT Title, "FT Title: $0, String: $1"
#Featuring &String, text, " ft "
#&Text to append, text, " ft "'''
    if replacetext == None:
        replacetext = ftval
    try:
        text = tags["artist"]
    except KeyError:
        return
    title = tags.get('title') if tags.get('title') else ''
    index = text.find(ftval)
    if index != -1:
        return title + replacetext + text[index + len(ftval):]

def geql(text,text1):
    if text >= text1:
        return true
    else:
        return false

def grtr(text, text1):
    if text > text1:
        return true
    else:
        return false

def hasformat(pattern, tagname = "__filename"):
    if findfunc.filenametotag(pattern, tagname):
        return true
    return false

def if_(text, text1, z):
    if check_truth(text):
        return text1
    else:
        return z

def iflonger(a, b, text, text1):
    try:
        if len(a) > len(b):
            return text
        else:
            return text1
    except TypeError:
        return

def isdigit(text):
    try:
        decimal.Decimal(text)
        return true
    except decimal.InvalidOperation:
        return false

def left(text, n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        raise FuncError(u'Integer expected, got "%s"' % unicode(n))
    return text[:n]

def len_(text):
    return unicode(len(text))

def leql(text,text1):
    if text <= text1:
        return true
    else:
        return false

def less(text, text1):
    if text < text1:
        return true
    else:
        return false

def libstuff(dirname):
    files = []
    for filename in os.listdir(dirname):
        tag = audioinfo.Tag(path.join(dirname, filename))
        if tag:
            files.append(tag)
    return files

def _load_image(filename):
    try:
        return {'data': open(filename, 'rb').read()}
    except EnvironmentError:
        traceback.print_exc()
        pass

def load_images(tags, filepatterns, desc, matchcase):
    '''Load Artwork, "Artwork: Filenames='$1', Description='$2', Case Sensitive=$3"
"&Filenames to check (;-separated, shell wildcards [eg. *] allowed)", text
&Default description (can be pattern):, text
Match filename's &case:, check'''
    dirpath = tags['__dirpath']
    files = os.listdir(dirpath)
    images = []
    pictures = fnmatch(filepatterns, files, matchcase)
    for pic in pictures:
        image = _load_image(os.path.join(dirpath, pic))
        if not image:
            continue
        image[audioinfo.DESCRIPTION] = formatValue(tags, desc)
        image[audioinfo.IMAGETYPE] = 3
        images.append(image)
    if images:
        return {'__image': images}

def lower(text):
    return string.lower(text)

def mid(text, n, i):
    try:
        n = int(n)
        i = int(i)
        return unicode(text)[n: n + i]
    except (TypeError, ValueError):
        raise FuncError(u'Integer expected, got "%s"' % unicode(n))

def mod(text,text1):
    D = decimal.Decimal
    try:
        return unicode((D(text) % D(text1).normalize()))
    except decimal.InvalidOperation:
        return

def move(tags, pattern):
    """Tag to filename, Tag->File: $1
&Pattern, text"""
    tf = findfunc.tagtofilename
    if pattern.startswith(u'/'):
        subdirs = pattern.split(u'/')
        newdirs =  [safe_name(tf(d, tags)) for d in subdirs[1:-1]]
        newdirs.append(safe_name(tf(subdirs[-1], tags, True)))
        newdirs.insert(0, u'/')
        return {'__path': os.path.join(*newdirs)}
    else:
        subdirs = pattern.split(u'/')
        newdirs =  [safe_name(tf(d, tags)) for d in subdirs[:-1]]
        newdirs.append(safe_name(tf(subdirs[-1], tags, True)))
        count = pattern.count('/')
        if count:
            parent = tags['__dirpath'].split(u'/')[:-count]
        else:
            parent = tags['__dirpath'].split(u'/')
        if not parent[0]:
            parent.insert(0, u'/')
        return {'__path': os.path.join(*(parent + newdirs))}

def mul(text, text1):
    D = decimal.Decimal
    try:
        return unicode((D(text) * D(text1)).normalize())
    except decimal.InvalidOperation:
        return

def neql(text, text1):
    if text == text1:
        return false
    else:
        return true

def not_(text):
    if check_truth(text):
        return false
    return true

def num(text, numlen):
    if not text:
        return u""
    text=str(text)
    index = text.find("/")
    if index >= 0:
        text = text[:index]
    try:
        numlen = long(numlen)
    except ValueError:
        return text
    if len(text)<numlen:
        text='0' * (numlen - len(text)) + text
    if len(text)>numlen:
        while text.startswith('0') and len(text)>numlen:
            text=text[1:]
    return text

def odd(text):
    D = decimal.Decimal
    if D(text) % 2 != 0:
        return true
    else:
        return false

def or_(text,text1):
    return unicode(check_truth(text) or check_truth(text1))

def rand():
    import random
    return unicode(random.random())

def re_escape(rex):
    escaped = ""
    for ch in rex:
        if ch in r'^$[]\+*?.(){},|' : escaped = escaped + '\\' + ch
        else: escaped = escaped + ch
    return escaped

def replace(text, word, replaceword, matchcase = False, whole = False, chars = None):
    '''Replace, "Replace $0: '$1' -> '$2', Match Case: $3, Words Only: $4"
&Replace, text
w&ith:, text
Match c&ase:, check
only as &whole word, check'''
    matchcase, whole = check_truth(matchcase), check_truth(whole)
    word = re_escape(word)
    
    if matchcase:
        matchcase = 0
    else:
        matchcase = re.IGNORECASE
    if chars is None:
        chars = u'\,\.\(\) \!\[\]'
    replaceword = replaceword.replace(u'\\', u'\\\\')

    if whole:
        pat = re.compile('(^|[%s])%s([%s]|$)' % (chars, word, chars), matchcase)
    else:
        pat = re.compile(word, matchcase)

    start = 0
    match = pat.search(text, start)
    if whole:
        while match:
            start = match.start()
            end = match.end()
            sub = text[start: end]
            repl = replaceword
            if sub[0] in chars:
                repl = sub[0] + repl
            if sub[-1] in chars:
                repl = repl + sub[-1]

            text = pat.sub(repl, text, 1)
            match = pat.search(text, start + len(repl))
    else:
        try:
            text = pat.sub(replaceword, text)
        except Exception, e:
            raise findfunc.FuncError(unicode(e))
    return text

def replacetokens(text, dictionary, default=u''):

    pat = re.compile('\$\d+')
    start = 0
    match = pat.search(text, start)
    if match:
        start = match.start()
        l = [text[:start]]
        end = start
    else:
        return default
    while match:
        start = match.start()
        l.append(text[end:start])
        end = match.end()
        sub = int(text[start+1: end])
        try:
            l.append(dictionary[sub])
        except KeyError:
            l.append(text[start: end])
        match = pat.search(text, end)
    l.append(text[end:])
    return u''.join(l)

def replaceWithReg(text, expr, rep):
    """Replace with RegExp, "RegReplace $0: RegExp $1, with $2"
&Regular Expression, text
Replace &matches with:, text"""
    if not expr:
        return text
    try:
        match = re.search(expr, text)
    except re.error, e:
        raise findfunc.FuncError(unicode(e))
    if match:
        groups = match.groups()
        if groups:
            d = dict(enumerate(groups))
            replacetext = findfunc.parsefunc(replacetokens(rep, d, rep), {})
            return re.sub(expr, replacetext, text)
        else:
            return findfunc.parsefunc(re.sub(expr, rep, text), {})
    else:
        return

def right(text,n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        raise FuncError(u'Integer expected, got "%s"' % unicode(n))
    if n == 0:
        return u''
    return text[-int(n):]

def strip(text):
    '''Trim whitespace, Trim $0'''
    return text.strip()

def find(text, text1):
    val = text.find(text1)
    if val >= 0:
        return unicode(val)
    return unicode(-1)

def sub(text,text1):
    D = decimal.Decimal
    try:
        return unicode((D(text) - D(text1)).normalize())
    except decimal.InvalidOperation:
        return

def testfunction(tags, t_text, p_pattern, n_number):
    text = u'%s - %s' % (tags['artist'], tags['title'])
    assert t_text == text
    assert p_pattern == '%artist% - %title%'
    assert n_number == 23
    return u'Passed'

def texttotag(tags, text, text1, text2):
    """Text to Tag, "Text to Tag: $0 -> $1, $2"
&Text, text
&Pattern, text
&Output, text"""
    pattern = text1
    tagpattern = pyparsing.Literal('%').suppress() + pyparsing.Word(pyparsing.nums)
    d = findfunc.tagtotag(pattern, findfunc.tagtofilename(text, tags), tagpattern)
    if d:
        output = text2
        for key in d:
            output = output.replace(u'%' + unicode(key), unicode(d[key]))
        return findfunc.tagtofilename(output, tags)
    return None

def titleCase(text, ctype = None, characters = None):
    '''Case conversion, "Convert Case: $0: $1"
&Type, combo, Mixed Case,UPPER CASE,lower case
"For &Mixed Case, after any of:", text, "., !"'''
    if characters is None:
        characters = ['.', '(', ')', ' ', '!']
    if ctype == "UPPER CASE":
        return text.upper()
    elif ctype == 'lower case':
        return text.lower()

    text = [z for z in text]
    try:
        text[0] = text[0].upper()
    except IndexError:
        return ""
    for char in range(len(text)):
        try:
            if text[char] in characters:
                    text[char + 1] = text[char + 1].upper()
            else:
                text[char + 1] = text[char + 1].lower()
        except IndexError:
            pass
    return "".join(text)

def upper(text):
    return text.upper()

def validate(text, to=None, chars=None):
    from puddleobjects import safe_name
    if chars is None:
        return safe_name(text, to=to)
    else:
        return safe_name(text, chars, to=to)
        
validFilenameChars = "'-_.!()[]{}&~+^ %s%s%s" % (string.ascii_letters, string.digits, os.path.sep)

def removeDisallowedFilenameChars(t_filename):
    cleanedFilename = unicodedata.normalize('NFKD', t_filename).encode('ASCII', 'ignore')
    return u''.join(c for c in cleanedFilename if c in validFilenameChars)

functions = {"add": add,
            "and": and_,
            'artwork': load_images,
            "caps": caps,
            "caps2": caps2,
            "caps3": caps3,
            "char": char,
            "div": div,
            "featFormat": featFormat,
            "find": find,
            "format": formatValue,
            "geql": geql,
            "grtr": grtr,
            "hasformat": hasformat,
            "if": if_,
            "iflonger": iflonger,
            "isdigit": isdigit,
            "left": left,
            "len": len_,
            "leql": leql,
            "less": less,
            "lower": lower,
            "mid": mid,
            "mod": mod,
            "move": move,
            "mul": mul,
            "neql": neql,
            "not": not_,
            "num": num,
            "odd": odd,
            "or": or_,
            "rand": rand,
            "re": re,
            "re_escape": re_escape,
            "replace": replace,
            "replaceWithReg": replaceWithReg,
            "right": right,
            "string": string,
            "strip": strip,
            "sub": sub,
            "texttotag": texttotag,
            'testfunction': testfunction,
            "time": time,
            "titleCase": titleCase,
            "true": true,
            "upper": upper,
            "validate": validate,
            'to_ascii': removeDisallowedFilenameChars}

import findfunc
FuncError = findfunc.FuncError
ParseError = findfunc.ParseError