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

from puddleobjects import (PuddleConfig, safe_name, fnmatch,
    dircmp, natcasecmp, encode_fn, decode_fn)
import string, pdb, sys, audioinfo, decimal, os, pyparsing, re, imp, shutil, time, unicodedata
from operator import itemgetter
from copy import deepcopy
from functools import partial

PATH = audioinfo.PATH
DIRPATH = audioinfo.DIRPATH

true = u'1'
false = u'0'
path = os.path

def add(text,text1):
    D = decimal.Decimal
    try:
        return unicode((D(unicode(text)) + D(unicode(text1))).normalize().to_eng_string())
    except decimal.InvalidOperation:
        return

_padding = u'0'
def _pad(text, numlen):
    if len(text) < numlen:
        text = _padding * ((numlen - len(text)) / len(_padding)) + text
    return text

def autonumbering(r_tags, minimum=1, restart=False, padding=1, state=None):
    '''Autonumbering, "Autonumbering: $0, Start: $1, Restart for dir: $2, Padding: $3"
oi,spinbox,1
aoeu,check, False
au,spinbox,1'''
    if 'autonumbering' not in state:
        state['autonumbering'] = {}
    
    dir_list = state['autonumbering']
    
    if restart:
        key = r_tags.dirpath
    else:
        key = 'temp'

    if key in dir_list:
        dir_list[key] += 1
    else:
        dir_list[key] = minimum

    tracknum = unicode(dir_list[key])

    if padding > 1:
        return _pad(tracknum, padding)
    else:
        return tracknum

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

# Contributed by Stjujsckij Nickolaj
def enconvert(text, enc_name):
    ''' Convert from non-standard encoding, "Convert to encoding: $0, Encoding: $1"
&Encoding, combo, cp1250, cp1251, cp1252, cp1253, cp1254, cp1255, cp1256, cp1257, cp1258'''
    return text.encode("latin1", 'replace').decode(enc_name, 'replace')

def export_cover(tags, pattern):
    dirpath = tags['__dirpath']

def filenametotag(m_tags, pattern):
    """Filename to Tag, File->Tag '$1'
&Pattern, text"""
    return findfunc.filenametotag(pattern, m_tags[PATH], True)

def finddups(tracks, key = 'title', method=None):
    from puddleobjects import dupes
    li = []
    for z in tracks:
        try:
            li.append(z[key])
        except KeyError:
            li.append(None)
    return dupes(li, method)

def formatValue(m_tags, pattern, state=None):
    """Format value, Format $0 using $1
&Format string, text"""
    ret = findfunc.tagtofilename(pattern, m_tags, state=state)
    if not ret:
        return
    else:
        return ret

format_value = formatValue

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

def import_text(m_tags, pattern, r_tags):
    '''Import text file, "Text File: $0, '$1'"
&Pattern (can be relative path), text, lyrics.txt'''
    path = os.path
    dirpath = r_tags.dirpath
    if os.path.isabs(pattern):
         filename = path.splitext(move(m_tags, pattern, r_tags)['__path'])[0]
         filename = path.normpath(filename)
    else:
        pattern = u'/' + pattern
        filename = path.splitext(move(m_tags, pattern, r_tags)['__path'])[0]
        filename = path.normpath(path.join(dirpath, encode_fn(filename[1:])))
    try:
        return open(filename, 'r').read().decode('utf8')
    except EnvironmentError:
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

def load_images(r_tags, filepatterns, desc, matchcase,state=None):
    '''Load Artwork, "Artwork: Filenames='$1', Description='$2', Case Sensitive=$3"
"&Filenames to check (;-separated, shell wildcards [eg. *] allowed)", text
&Default description (can be pattern):, text
Match filename's &case:, check'''
    tags = r_tags
    if state is None:
        state = {}
    
    dirpath = tags.dirpath
    key = 'image_dirpath' + dirpath
    if key in state:
        files = state[key]
    else:
        files = os.listdir(dirpath)
    images = []
    pictures = fnmatch(filepatterns, files, matchcase)
    for pic in pictures:
        filename = os.path.join(dirpath, pic)
        key = 'loaded_image' + filename
        if key in state:
            image = deepcopy(state[key])
        else:
            image = _load_image(filename)
            if not image:
                continue
            desc = formatValue(tags, desc)
            if desc is None:
                desc = u''
            image[audioinfo.DESCRIPTION] = desc
            image[audioinfo.IMAGETYPE] = 3
            state[key] = image
        images.append(image)

    if images:
        return {'__image': images}

def lower(text):
    return string.lower(text)

def merge_values(m_text, separator=u';'):
    '''Merge field, "Merge field: $0, sep='$1'"
&Separator, text, ;'''
    if isinstance(m_text, basestring):
        return m_text
    else:
        return separator.join(m_text)

def meta_sep(m_tags, field, sep=u', '):
    value = m_tags.get(field)
    if value is None:
        return None
    elif isinstance(value, basestring):
        return value
    else:
        return sep.join(value)

def meta(m_tags, field, n_index=None):
    value = m_tags.get(field)
    if value is None:
        return None
    if n_index is not None:
        try:
            return value[n_index]
        except IndexError:
            return u''
    else:
        if isinstance(value, basestring):
            return value
        return u', '.join(value)

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

def move(m_tags, pattern, r_tags, ext=True, state=None):
    """Tag to filename, Tag->File: $1
&Pattern, text"""
    
    tags = m_tags
    tf = findfunc.tagtofilename

    if state is None:
        state = {}

    if os.path.isabs(pattern):
        
        new_name = lambda d: safe_name(tf(d, tags, state=state))
        subdirs = pattern.split(u'/')
        newdirs = map(new_name, subdirs[1:-1])
        newdirs.append(safe_name(tf(subdirs[-1], tags, ext, state=state)))
        newdirs.insert(0, u'/')
        return {'__path': os.path.join(*newdirs)}
    else:

        new_name = lambda d: encode_fn(safe_name(tf(d, tags, state=state)))
        subdirs = pattern.split(u'/')
        count = pattern.count(u'/')
        
        newdirs = map(new_name, subdirs[:-1])
        newdirs.append(encode_fn(safe_name(tf(subdirs[-1], tags, ext, state=state))))

        dirpath = r_tags.dirpath

        if count:
            parent = dirpath.split('/')[:-count]
        else:
            parent = dirpath.split('/')
        if not parent[0]:
            parent.insert(0, '/')
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
    if len(text) < numlen:
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
    escaped = u""
    for ch in rex:
        if ch in r'^$[]\+*?.(){},|' : escaped = escaped + u'\\' + ch
        else: escaped = escaped + ch
    return escaped

def remove_fields():
    '''Remove Fields, <blank> $0'''
    return u''

def remove_except(tags, fields):
    '''Remove all fields except, "Remove fields except: $1"
&Field list (; separated):, text, '''
    fields = [field for field in fields.split(u';')]
    ret = dict([(field.strip(), u'') for field in audioinfo.usertags(tags)
        if field not in fields])
    if '__image' not in fields:
        ret['__image'] = []
    if ret:
        return ret

import mutagen.id3, mutagen.apev2

_tag_classes = {
    'APEv2': mutagen.apev2.delete,
    'ID3v1': partial(mutagen.id3.delete, v1=True, v2=False),
    'ID3v2': partial(mutagen.id3.delete, v1=False, v2=True),
    'All ID3': partial(mutagen.id3.delete, v1=True, v2=True)}
    
def remove_tag(r_tags, tag='APEv2'):
    '''Remove Tag, "Remove $1 Tag"
&Tag, combo, Base, APEv2, ID3v1, ID3v2, All ID3'''
    
    if tag in _tag_classes:
        _tag_classes[tag](r_tags.filepath)

def rename_dirs(tags, state, pattern):
    '''Rename Directory, "Rename dir: $1"
&Pattern:, text'''
    dirname = safe_name(format_value(tags, pattern))
    old_path = tags['__dirpath']
    dirpath = path.join(path.dirname(old_path), dirname)
    if 'rename_dirs' in state:
        state['rename_dirs'][old_path] = dirpath
    else:
        state['rename_dirs'] = {old_path: dirpath}

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

def replaceWithReg(text, expr, rep, matchcase=False):
    """Replace with RegExp, "RegReplace $0: RegExp '$1' with '$2', Match Case: $3"
&Regular Expression, text
Replace &matches with:, text
Match &Case, check"""
    t = time.time()
    if not expr:
        return text
    try:
        match = re.search(expr, text, re.I)
    except re.error, e:
        raise findfunc.FuncError(unicode(e))

    ret = []
    unmatched = 0
    append = ret.append
    
    if not matchcase:
        matches = re.finditer(expr, text, re.I)
    else:
        matches = re.finditer(expr, text)

    for match in matches:
        group = match.group()
        groups = match.groups()
        if not group:
            continue
        if groups:
            d = dict((i + 1, g) for i, g in enumerate(groups))
        else:
            d = {1: group}

        replacetext = findfunc.parsefunc(rep, {}, d)
        replacetext = replacetokens(replacetext, d, replacetext)

        append(text[unmatched:match.start(0)])
        unmatched = match.end(0)
        append(replacetext)
    ret.append(text[unmatched:])
    return u''.join(ret)

replace_regex = replaceWithReg

validFilenameChars = "'-_.!()[]{}&~+^ %s%s%s" % (
    string.ascii_letters, string.digits, os.path.sep)

#Contributed by Erik Reckase
def removeDisallowedFilenameChars(t_filename):
    cleanedFilename = unicodedata.normalize('NFKD', t_filename).encode('ASCII', 'ignore')
    return u''.join(c for c in cleanedFilename if c in validFilenameChars)

def remove_dupes(m_text, matchcase=False):
    """Remove duplicate values, "Remove Dupes: $0, Match Case $1"
Match &Case, check"""
    text = m_text
    if isinstance(text, basestring):
        return text

    if matchcase:
        ret = []
        append = temp.append
        [append(z) for z in text if z not in ret]
        return ret
    else:
        ret = []
        lowered = set()
        for z in text:
            if z.lower() not in lowered:
                lowered.add(z.lower())
                ret.append(z)
	return ret

def right(text,n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        raise FuncError(u'Integer expected, got "%s"' % unicode(n))
    if n == 0:
        return u''
    return text[-int(n):]

def sort_field(m_text, order='Ascending', matchcase=False):
    """Sort values, "Sort $0, order='$1', Match Case='$2'"
&Order, combo, Ascending, Descending,
Match &Case, check"""
    text = m_text
    if not matchcase:
        cmp = natcasecmp
    else:
        cmp = None
    if isinstance(text, basestring):
        return text
    if order == u'Ascending':
        return sorted(text, cmp)
    else:
        return sorted(text, cmp, reverse=True)

def split_by_sep(m_text, sep):
    """Split fields using separator, "Split using separator $0: sep='$1'"
&Separator, text, ;"""
    if isinstance(m_text, basestring):
        return m_text
    else:
        ret = []
        for t in m_text:
            ret.extend(t.split(sep))
        return ret

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
        return  unicode(D(text) - D(text1))
    except decimal.InvalidOperation:
        return

def tag_dir(m_tags, pattern, r_tags, state = None):
    '''Tag to Dir, "Tag->Dir: $1"
&Pattern (can be relative path), text, %artist% - %album%'''
    if state is None:
        state = {'tag_dir': set()}
    elif 'tag_dir' not in state:
        state['tag_dir'] = set()
    if r_tags.dirpath in state['tag_dir']:
        return
    path = os.path
    dirpath = r_tags.dirpath
    if pattern.endswith(u'/') and len(pattern) > 1:
        pattern = pattern[:-1]
    if os.path.isabs(pattern):
        filename = move(m_tags, pattern, r_tags, False)['__path']
        filename = path.normpath(filename)
    else:
        pattern = u'/' + pattern
        filename = move(m_tags, pattern, r_tags, False)['__path']
        filename = path.normpath(path.join(dirpath,
            os.path.pardir, encode_fn(filename[1:])))
    if filename:
        state['tag_dir'].add(filename)
        return {DIRPATH: filename}

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

_update = {'APEv2': audioinfo.apev2.Tag, 'ID3': audioinfo.id3.Tag}
def update_from_tag(r_tags, fields, tag='APEv2'):
    '''Update from tag, "Update from $2, Fields: $1"
&Field list (; separated):, text,
&Tag, combo, APEv2, ID3'''
    try:
        tag = _update[tag]().link(r_tags.filepath)
        if tag is None:
            return
    except EnvironmentError:
        return
    fields = filter(None, [z.strip() for z in fields.split(u';')])    
    if not fields:
        return tag.usertags
    else:
        if fields[0].startswith(u'~'):
            return dict([(k,v) for k,v in tag.usertags.iteritems()
                if k not in fields])
        else:
            return dict([(k,v) for k,v in tag.usertags.iteritems()
                if k in fields])

def upper(text):
    return text.upper()

def validate(text, to=None, chars=None):
    from puddleobjects import safe_name
    if chars is None:
        return safe_name(text, to=to)
    else:
        return safe_name(text, chars, to=to)

functions = {
    "add": add,
    "and": and_,
    'artwork': load_images,
    'autonumbering': autonumbering,
    "caps": caps,
    "caps2": caps2,
    "caps3": caps3,
    "char": char,
    "div": div,
    "enconvert": enconvert,
    'filenametotag': filenametotag,
    "find": find,
    "format": formatValue,
    "geql": geql,
    "grtr": grtr,
    "hasformat": hasformat,
    "if": if_,
    "iflonger": iflonger,
    #'image_to_file': image_to_file,
    'import_text': import_text,
    "isdigit": isdigit,
    "left": left,
    "len": len_,
    "leql": leql,
    "less": less,
    "lower": lower,
    'merge_values': merge_values,
    'meta_sep': meta_sep,
    'meta': meta,
    "mid": mid,
    "mod": mod,
    "move": move,
    "mul": mul,
    'remove_dupes': remove_dupes,
    "neql": neql,
    "not": not_,
    "num": num,
    "odd": odd,
    "or": or_,
    "rand": rand,
    "re_escape": re_escape,
    'remove_except': remove_except,
    #'remove_tag': remove_tag,
    "replace": replace,
    "replaceWithReg": replaceWithReg,
    "right": right,
    'sort': sort_field,
    'split_by_sep': split_by_sep,
    "strip": strip,
    "sub": sub,
    'tag_dir': tag_dir,
    "texttotag": texttotag,
    'testfunction': testfunction,
    "titleCase": titleCase,
    'remove_fields': remove_fields,
    "upper": upper,
    'update_from_tag': update_from_tag,
    "validate": validate,
    'to_ascii': removeDisallowedFilenameChars}

no_fields = (filenametotag, load_images, move, remove_except, tag_dir,
    update_from_tag)
no_preview = (autonumbering, load_images, remove_tag)

import findfunc
FuncError = findfunc.FuncError
ParseError = findfunc.ParseError