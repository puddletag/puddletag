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

"""functions.py

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

import sre, pdb
import findfunc, string
import decimal
from PyQt4.QtCore import QString, Qt, QStringList

def re_escape(rex):
    escaped = ""
    for ch in rex:
        if ch in r'^$[]\+*?.(){},|' : escaped = escaped + '\\' + ch
        else: escaped = escaped + ch
    return escaped
        
def num(number,numlen):
    number=str(number)
    index = number.find("/")
    if index >= 0:
        number = number[:index]
    try:
        numlen = long(numlen)
    except ValueError:
        return number
    if len(number)<numlen:
        number='0' * (numlen - len(number)) + number
    if len(number)>numlen:
        while number.startswith('0') and len(number)>numlen:
            number=number[1:]
    return number

def validate(text, to):
    from puddleobjects import safe_name
    return safe_name(text,to)

def strip(text):
    '''Trim whitespace, Trim $0'''    
    return text.strip()

def formatValue(tags, pattern):
    """Format Value, Format $0 using $1
Format string, QLineEdit"""
    return findfunc.tagtofilename(pattern, tags)

def titleCase(text, ctype = None, characters = ['.', '(', ')', ' ', '!']):
    '''Case Conversion, "$0: $1"
Type, QComboBox, Mixed Case,UPPER CASE,lower case
"For Mixed Case, after any of:", QLineEdit, "., !"'''
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

def caps(text):
    return titleCase(text)

def caps2(text):
    upcase = [z for z,i in enumerate(text) if i in string.uppercase]
    text = list(titleCase(text))
    newtext = ""
    for z in upcase:
        text[z] = text[z].upper()
    return "".join(text)

def caps3(text):
    try:
        start = sre.search("[a-zA-Z]", text).start(0)
    except AttributeError:
        return
    return text[:start] + text[start].upper() + text[start + 1:].lower()

def upper(text):
    return string.upper(text)

def lower(text):
    return string.lower(text)

def add(x,y):
    try:
        return unicode((decimal.Decimal(unicode(x)) + decimal.Decimal(unicode(y))).normalize())
    except decimal.InvalidOperation:
        return

def and_(x,y):
    return unicode(bool(x) and bool(y))

def div(x,y):
    try:
        return unicode((decimal.Decimal(unicode(x)) / decimal.Decimal(unicode(y))).normalize())
    except decimal.InvalidOperation:
        return

def char(x):
    try:
        return unicode(ord(x))
    except TypeError:
        return

def geql(x,y):
    if x >= y:
        return unicode(True)
    else:
        return unicode(False)

def grtr(x,y):
    if x > y:
        return unicode(True)
    else:
        return unicode(False)

def if_(x,y,z):
    if x != "False" and bool(x):
        return y
    else:
        return z

def ifgreater(a, b, x, y):
    try:
        if float(a) > float(b):
            return unicode(x)
        else:
            return unicode(y)
    except ValueError:
        return

def iflonger(a, b, x, y):
    try:
        if len(unicode(a)) > len(unicode(b)):
            return unicode(x)
        else:
            return unicode(y)
    except TypeError:
        return

def isdigit(x):
    try:
        return decimal.Decimal(x)
    except decimal.InvalidOperation:
        return

def left(x,n):
    return unicode[:n + 1]

def len_(x):
    return len(unicode(x))

def leql(x,y):
    if x <= y:
        return unicode(True)
    else:
        return unicode(False)    

def less(x,y):
    if x < y:
        return unicode(True)
    else:
        return unicode(False)

def mid(x,n,i):
    return unicode(x)[n:i+1]

def mod(x,y):
    try:
        return unicode((decimal.Decimal(unicode(x)) % decimal.Decimal(unicode(y))).normalize())
    except decimal.InvalidOperation:
        return

def mul(x,y):
    try:
        return unicode((decimal.Decimal(unicode(x)) * decimal.Decimal(unicode(y))).normalize())
    except decimal.InvalidOperation:
        return

def neql(x,y):
    if unicode(x) != unicode(y):
        return unicode(True)
    else:
        return unicode(False)    

def not_(x):
    return unicode(not x)

def odd(x):
    if decimal.Decimal(x) % 2 != decimal.Decimal(0):
        return unicode(True)
    else:
        return unicode(False)

def or_(x,y):
    return unicode(bool(x) or bool(y))

def rand():
    import random
    return random.random()

def right(x,n):
    return x[n:]

def strstr(x,y):
    val = x.find(y)
    if val > 0:
        return unicode(val)
    else:
        return ""

def sub(x,y):
    try:
        return unicode((decimal.Decimal(unicode(x)) - decimal.Decimal(unicode(y))).normalize())
    except decimal.InvalidOperation:
        return

def replace(text, word, replaceword, matchcase = False, whole = False):
    '''Replace, "Replace '$0': '$1' -> '$2'"
Replace, QLineEdit
with:, QLineEdit
Match case:, QCheckBox
only as whole word, QCheckBox'''
    if (matchcase) and (not whole):
        return text.replace(word, replaceword)
    elif (not matchcase) and (not whole):
        return replaceAsWord(text, word, replaceword, matchcase, "")
    else:
        return replaceAsWord(text, word, replaceword, matchcase, None)
    
        
def replaceAsWord(text, word, replaceword, matchcase = False, characters = None):
    start = 0
    if characters is None:
        characters = [',','.', '(', ')', ' ', '!']
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

        
def featFormat(text, ftstring = "ft", opening = "(", closing = ")"):
    '''Remove brackets from (ft), Brackets remove: $0
    Feat String, QLineEdit, ft
    Opening bracket, QLineEdit, "("
    Closing bracket, QLineEdit, ")"'''
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
            
def ftArtist(tags, ftval = " ft "):
    '''Get FT Artist, "FT Artist: $0, String: $1"
Featuring String, QLineEdit'''
    
    try:
        text = tags["artist"]
    except KeyError:
        return
    x = text.find(ftval)
    if x != -1:
        return(text[:x])

def ftTitle(tags, ftval = " ft ", replacetext = None):
    '''Get FT Title, "FT Title: $0, String: $1"
Featuring String, QLineEdit
Append text, QLineEdit'''
    if replacetext == None:
        replacetext = ftval
    try:
        text = tags["artist"]
    except KeyError:
        return
    x = text.find(ftval)
    if x != -1:
        return tags["title"] + replacetext + text[x + len(ftval):]