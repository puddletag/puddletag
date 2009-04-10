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
    The Second contains the control itself, either QLineEdit, QComboBox or QCheckBox
    The third contains the default arguments as shown to the user."""


import findfunc, string, pdb, sys, audioinfo, decimal, os
path = os.path
if sys.version_info[:2] >= (2, 5): import re as sre
else: import sre
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
        start = sre.search("[a-zA-Z]", text).start(0)
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
    Feat &String, QLineEdit,  ft
    O&pening bracket, QLineEdit, "("
    C&losing bracket, QLineEdit, ")"'''
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

def finddups(tracks, key = 'title'):
    the = time.time()
    li = [z[key].lower() for z in tracks if key in z and z[key] is not None]
    temp = set(li)
    dups = {}
    for i, z in enumerate(li):
        if z in temp:
            temp.discard(z)
        else:
            index = li.index(z)
            try:
                dups[index].append(i)
            except:
                dups[index] = [i]
    return dups

def formatValue(tags, pattern):
    """Format Value, Format $0 using $1
&Format string, QLineEdit"""
    return findfunc.tagtofilename(pattern, tags)

def ftArtist(tags, ftval = " ft "):
    '''Get FT Artist, "FT Artist: $0, String: $1"
Featuring &String, QLineEdit, " ft "'''

    try:
        text = tags["artist"]
    except KeyError:
        return
    index = text.find(ftval)
    if index != -1:
        return(text[:index])

def ftTitle(tags, ftval = " ft ", replacetext = None):
    '''Get FT Title, "FT Title: $0, String: $1"
Featuring &String, QLineEdit, " ft "
&Text to append, QLineEdit, " ft "'''
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
    return unicode(text)[:n + 1]

def len_(text):
    return len(unicode(text))

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
    return unicode(text)[n:i+1]

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

def replace(text, word, replaceword, matchcase = False, whole = False):
    '''Replace, "Replace '$0': '$1' -> '$2'"
&Replace, QLineEdit
w&ith:, QLineEdit
Match c&ase:, QCheckBox
only as &whole word, QCheckBox'''
    if (matchcase) and (not whole):
        return text.replace(word, replaceword)
    elif (not matchcase) and (not whole):
        return replaceAsWord(text, word, replaceword, matchcase, "")
    else:
        return replaceAsWord(text, word, replaceword, matchcase, None)

def replaceAsWord(text, word, replaceword, matchcase = False, characters = None):
    start = 0
    if characters is None:
        characters = [',','.', '(', ')', ' ', '!','[',']']
    #This function works by getting searching for word, checking if it has any of the characters
    #in characters on it's left or right. If it does then it's replaced.
    #I'm converting text to string because then it's easier to make string substitutions
    #such as text[2:5] = "saotehustnu", that would do the replacing easily.
    start = 0
    if characters is None:
        characters = ['.', '(', ')', ' ', '!']
    if not matchcase:
        word = word.lower()
    text = list(text)

    while True:
        if not matchcase:
            newtext = "".join(text).lower()
        else:
            newtext = "".join(text)
        start = newtext.find(word, start)
        if start == -1:
            break
        end = start + len(word)
        if (end == len(newtext) and newtext[start - 1] in characters) or (start == 0 and newtext[end] in characters) or characters == "":
            text[start: end] = replaceword
        elif text[start - 1] in characters and text[end] in characters:
            text[start: end] = replaceword
        start = start + len(word) + 1
    return "".join(text)

def right(text,n):
    return text[n:]

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

def titleCase(text, ctype = None, characters = ['.', '(', ')', ' ', '!']):
    '''Case Conversion, "$0: $1"
&Type, QComboBox, Mixed Case,UPPER CASE,lower case
"For &Mixed Case, after any of:", QLineEdit, "., !"'''
    if ctype == "UPPER CASE":
        return text.upper()
    elif ctype == "lower case":
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