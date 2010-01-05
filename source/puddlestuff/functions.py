# -*- coding: utf-8 -*-
#functions.py

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


import findfunc, string, pdb, sys, audioinfo, decimal, os, pyparsing, re
import pyparsing

path = os.path
import time

def add(text,text1):
    try:
        return unicode((decimal.Decimal(unicode(text)) + decimal.Decimal(unicode(text1))).normalize())
    except decimal.InvalidOperation:
        return

def and_(text,text1):
    return unicode(bool(text) and bool(text1))


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
    try:
        return unicode((decimal.Decimal(unicode(text)) / decimal.Decimal(unicode(text1))).normalize())
    except decimal.InvalidOperation:
        return


def featFormat(text, ftstring = "ft", opening = "(", closing = ")"):
    '''Remove brackets from (ft), Brackets remove: $0
    Feat &String, text,  ft
    O&pening bracket, text, "("
    C&losing bracket, text, ")"'''
    #Removes parenthesis from feat string
    #say if you had a title string "Booty (ft the boot man)"
    #featFormat would return "Booty ft the boot man"
    #In the same way "Booty (ft the boot man"
    #would give "Booty ft the boot man"
    #but "Booty ft the boot man)" would remain unchanged.
    #the opening and closing parens can be changed to whatever.
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
    """Format Value, Format $0 using $1
&Format string, text"""
    return findfunc.tagtofilename(pattern, tags)

def ftArtist(tags, ftval = " ft "):
    '''Get FT Artist, "FT Artist: $0, String: $1"
Featuring &String, text, " ft "'''

    try:
        text = tags["artist"]
    except KeyError:
        return
    index = text.find(ftval)
    if index != -1:
        return(text[:index])

def ftTitle(tags, ftval = " ft ", replacetext = None):
    '''Get FT Title, "FT Title: $0, String: $1"
Featuring &String, text, " ft "
&Text to append, text, " ft "'''
    if replacetext == None:
        replacetext = ftval
    try:
        text = tags["artist"]
    except KeyError:
        return
    index = text.find(ftval)
    if index != -1:
        try:
            return tags["title"] + replacetext + text[index + len(ftval):]
        except:
            pdb.set_trace()
            return tags["title"] + replacetext + text[index + len(ftval):]

def geql(text,text1):
    if text >= text1:
        return unicode(True)
    else:
        return unicode(False)

def grtr(text,text1):
    if text > text1:
        return unicode(True)
    else:
        return unicode(False)

def hasformat(pattern, tagname = "__filename"):
    pdb.set_trace()
    if findfunc.filenametotag(pattern, tagname):
        return unicode(True)
    return unicode(False)

def if_(text,text1,z):
    if text != "False" and bool(text):
        return text1
    else:
        return z

def ifgreater(a, b, text, text1):
    try:
        if float(a) > float(b):
            return unicode(text)
        else:
            return unicode(text1)
    except ValueError:
        return

def iflonger(a, b, text, text1):
    try:
        if len(unicode(a)) > len(unicode(b)):
            return unicode(text)
        else:
            return unicode(text1)
    except TypeError:
        return

def isdigit(text):
    try:
        return decimal.Decimal(text)
    except decimal.InvalidOperation:
        return

def left(text,n):
    n = int(decimal.Decimal(n))
    return unicode(text)[:n + 1]

def len_(text):
    return unicode(len(text))

def leql(text,text1):
    if text <= text1:
        return unicode(True)
    else:
        return unicode(False)

def less(text,text1):
    if text < text1:
        return unicode(True)
    else:
        return unicode(False)

def libstuff(dirname):
    files = []
    for filename in os.listdir(dirname):
        tag = audioinfo.Tag(path.join(dirname, filename))
        if tag:
            files.append(tag)
    return files

def lower(text):
    return string.lower(text)

def mid(text,n,i):
    try:
        return unicode(text)[int(n):int(i)+1]
    except ValueError:
        return

def mod(text,text1):
    try:
        return unicode((decimal.Decimal(unicode(text)) % decimal.Decimal(unicode(text1))).normalize())
    except decimal.InvalidOperation:
        return

def mul(text,text1):
    try:
        return unicode((decimal.Decimal(unicode(text)) * decimal.Decimal(unicode(text1))).normalize())
    except decimal.InvalidOperation:
        return

def neql(text,text1):
    if unicode(text) != unicode(text1):
        return unicode(True)
    else:
        return unicode(False)

def not_(text):
    if text == "False":
        return True
    return unicode(not text)

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
    if decimal.Decimal(text) % 2 != decimal.Decimal(0):
        return unicode(True)
    else:
        return unicode(False)

def or_(text,text1):
    return unicode(bool(text) or bool(text1))

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
    '''Replace, "Replace '$0': '$1' -> '$2'"
&Replace, text
w&ith:, text
Match c&ase:, check
only as &whole word, check'''
    word = re_escape(word)
    if matchcase:
        matchcase = 0
    else:
        matchcase = re.IGNORECASE
    if chars is None:
        chars = '\,\.\(\) \!\[\]'

    if whole:
        pat = re.compile('(^|[%s])%s([%s]|$)' %(chars, word, chars), matchcase)
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
        text = pat.sub(replaceword, text)
    return text

def replacetokens(text, dictionary):

    pat = re.compile('\$\d+')
    start = 0
    match = pat.search(text, start)
    if match:
        start = match.start()
        l = [text[:start]]
        end = start
    else:
        return
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
    return ''.join(l)


def replaceWithReg(text, expr, rep):
    """Replace with RegExp, "RegReplace $0: RegExp $1, with $1"
&Regular Expression, text
w&ith, text"""
    match = re.search(expr, text)
    if match:
        groups = match.groups()
        if groups:
            d = dict(enumerate(groups))
            return parsefunc(replacetokens(rep, d), {})
        else:
            return parsefunc(re.sub(expr, rep, text), {})
    else:
        return

def right(text,n):
    try:
        n = decimal.Decimal(n)
    except decimal.InvalidOperation:
        return
    return text[-int(n):]

def strip(text):
    '''Trim whitespace, Trim $0'''
    return text.strip()

def strstr(text,text1):
    val = text.find(text1)
    if val > 0:
        return unicode(val)
    else:
        return unicode()

def sub(text,text1):
    try:
        return unicode((decimal.Decimal(unicode(text)) - decimal.Decimal(unicode(text1))).normalize())
    except decimal.InvalidOperation:
        return

def texttotag(tags, text, text1, text2):
    """Text to Tag, "Tag to Tag: $0 -> $1, $2"
&Text, text
&Pattern, text
&Output, text"""
    pattern = text1
    tagpattern = pyparsing.Literal('%').suppress() + pyparsing.Word(pyparsing.nums)
    print pattern, findfunc.tagtofilename(text, tags)
    d = findfunc.tagtotag(pattern, findfunc.tagtofilename(text, tags), tagpattern)
    if d:
        output = text2
        for key in d:
            output = output.replace(u'%' + unicode(key), unicode(d[key]))
        return findfunc.tagtofilename(output, tags)
    return ''

def titleCase(text, ctype = None, characters = ['.', '(', ')', ' ', '!']):
    '''Case Conversion, "$0: $1"
&Type, combo, Mixed Case,UPPER CASE,lower case
"For &Mixed Case, after any of:", text, "., !"'''
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
    return string.upper(text)

def validate(text, to):
    from puddleobjects import safe_name
    return safe_name(text,to)