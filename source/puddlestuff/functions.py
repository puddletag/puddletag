# -*- coding: utf-8 -*-
# functions.py

# Copyright (C) 2008-2010 concentricpuddle, GPLv2

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

import decimal
import math
import os
import re
import string
import traceback
import unicodedata
from mutagen.mp3 import HeaderNotFoundError
from collections import defaultdict
from functools import partial

import pyparsing

from . import audioinfo
from .audioinfo import encode_fn
from .puddleobjects import (safe_name, fnmatch, natsort_case_key)

PATH = audioinfo.PATH
DIRPATH = audioinfo.DIRPATH

true = '1'
false = '0'
path = os.path

D = decimal.Decimal


def add(text, text1):
    try:
        return str((D(str(text)) + D(str(text1))).normalize().to_eng_string())
    except decimal.InvalidOperation:
        return


_padding = '0'


def _pad(text, numlen):
    if len(text) < numlen:
        text = _padding * ((numlen - len(text)) // len(_padding)) + text
    return text


def autonumbering(r_tags, minimum=1, restart=False, padding=1, state=None):
    '''Autonumbering, "Autonumbering: $0, Start: $1, Restart for dir: $2, Padding: $3"
oi,spinbox,1
aoeu,check, False
au,spinbox,1'''
    if restart:
        if 'autonumbering' not in state:
            state['autonumbering'] = defaultdict(lambda: 0)

        dircount = state['autonumbering']

        counter = dircount.get(r_tags.dirpath, 0) + 1
        dircount[r_tags.dirpath] = counter
    else:
        counter = int(state.get('__counter', 1))

    tracknum = str(minimum + counter - 1)

    if padding > 1:
        return _pad(tracknum, padding)
    else:
        return tracknum


def check_truth(text):
    if isinstance(text, str):
        text = text.strip()
    return 0 if ((not text) or (text == '0')) else 1


def and_(text, text1):
    return str(check_truth(text) and check_truth(text1))


def caps(text):
    # Capitalizes the first letter of each word in string and
    # converts the rest to lower case.
    return titleCase(text)


def caps2(text):
    # Capitalizes the first letter of each word in string and
    # leaves all other characters unchanged.
    upcase = set(i for i, char in enumerate(text) if char.upper() == char)
    return "".join(ch.upper() if i in upcase else ch
                   for i, ch in enumerate(text.title()))


def caps3(text):
    # Capitalizes the first letter of the string and converts
    # the rest to lower case.
    try:
        start = re.search("\w", text, re.U).start(0)
    except AttributeError:
        return
    return text[:start] + text[start].upper() + text[start + 1:].lower()


def ceiling(n_value):
    return math.ceil(n_value)


def char(text):
    try:
        return str(ord(text))
    except TypeError:
        return


def changeartist(artist, *files):
    for audio in files:
        audio['artist'] = artist
        audio.save()


def div(n_numerator, n_divisor):
    if n_divisor == 0:
        raise FuncError("Cannot divide by zero.")
    try:
        return str((D(n_numerator) / D(n_divisor)).normalize())
    except decimal.InvalidOperation:
        return
    # ret = unicode(float(n_numerator) / n_divisor)
    # if len(ret) < len(normalized):
    # return ret
    # else:
    # return normalized


def eql(text, text1):
    return true if text == text1 else false


# Contributed by Stjujsckij Nickolaj
def enconvert(text, enc_name):
    ''' Convert from non-standard encoding, "Convert to encoding: $0, Encoding: $1"
&Encoding, combo, cp1250, cp1251, cp1252, cp1253, cp1254, cp1255, cp1256, cp1257, cp1258,\
euc_jp, cp932, euc_jis_2004, shift_jis, johab, big5, big5hkscs, gb2312, gb18030, gbk, hz'''
    return text.encode("latin1", 'replace').decode(enc_name, 'replace')


def filenametotag(m_tags, p_pattern):
    """Filename to Tag, File->Tag '$1'
&Pattern, text"""
    return findfunc.filenametotag(p_pattern, m_tags[PATH], True)


def finddups(tracks, key='title', method=None):
    from .puddleobjects import dupes
    li = []
    for z in tracks:
        try:
            li.append(z[key])
        except KeyError:
            li.append(None)
    return dupes(li, method)


def floor(n_value):
    return math.floor(n_value)


def formatValue(m_tags, p_pattern, state=None):
    """Format value, Format $0 using $1
&Format string, text"""
    ret = findfunc.parsefunc(p_pattern, m_tags, state=state)
    if not ret:
        return
    else:
        return ret


format_value = formatValue


def geql(text, text1):
    try:
        text = float(text)
    except (TypeError, ValueError):
        pass

    try:
        text1 = float(text1)
    except (TypeError, ValueError):
        pass

    if text >= text1:
        return true
    else:
        return false


def grtr(text, text1):
    try:
        text = float(text) if text.strip() else 0
    except (TypeError, ValueError):
        pass

    try:
        text1 = float(text1) if text1.strip() else 0
    except (TypeError, ValueError):
        pass

    if text > text1:
        return true
    else:
        return false


def to_num(text):
    match = re.search('[\-\+]?[0-9]+(\.[0-9]+)?', text)
    return match.group() if match else ''


def hasformat(p_pat, tagname="__filename"):
    if findfunc.filenametotag(p_pat, tagname):
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


def import_text(m_tags, p_pattern, r_tags):
    '''Import text file, "Text File: $0, '$1'"
&Pattern (can be relative path), text, lyrics.txt'''
    path = os.path
    dirpath = r_tags.dirpath
    filename = tag_to_filename(p_pattern, m_tags, r_tags, False)
    if not filename:
        return
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
        raise FuncError('Integer expected, got "%s"' % str(n))
    return text[:n]


def len_(text):
    return str(len(text))


def leql(text, text1):
    try:
        text = float(text)
    except (TypeError, ValueError):
        pass

    try:
        text1 = float(text1)
    except (TypeError, ValueError):
        pass

    if text <= text1:
        return true
    else:
        return false


def less(text, text1):
    try:
        text = float(text)
    except (TypeError, ValueError):
        pass

    try:
        text1 = float(text1)
    except (TypeError, ValueError):
        pass

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


def load_images(r_tags, filepatterns, desc, matchcase, state=None):
    '''Load Artwork, "Artwork: Filenames='$1', Description='$2', Case Sensitive=$3"
"&Filenames to check (;-separated, shell wildcards [eg. *] allowed)", text
&Default description (can be pattern):, text
Match filename's &case:, check'''
    tags = r_tags

    images = []
    dirpath = r_tags.dirpath
    pictures = fnmatch(filepatterns, os.listdir(dirpath), matchcase)
    for pic in pictures:
        filename = os.path.join(dirpath, pic)
        image = _load_image(filename)
        if not image:
            continue
        desc = formatValue(tags, desc)
        if desc is None:
            desc = ''
        image[audioinfo.DESCRIPTION] = desc
        image[audioinfo.IMAGETYPE] = 3
        images.append(image)

    if images:
        return {'__image': images}


def lower(text):
    return text.lower()


def merge_values(m_text, separator=';'):
    '''Merge field, "Merge field: $0, sep='$1'"
&Separator, text, ;'''
    if isinstance(m_text, str):
        return m_text
    else:
        return separator.join(m_text)


def meta_sep(m_tags, p_field, p_sep=', '):
    value = m_tags.get(p_field)
    if value is None:
        return None
    elif isinstance(value, str):
        return value
    else:
        return p_sep.join(value)


def meta(m_tags, field, n_index=None):
    value = m_tags.get(field)
    if value is None:
        return None
    if n_index is not None:
        n_index = int(n_index)
        try:
            return value[n_index]
        except IndexError:
            return ''
    else:
        if isinstance(value, str):
            return value
        return ', '.join(value)


def mid(text, n_start, n_len):
    try:
        n_start = int(n_start)
    except (TypeError, ValueError):
        raise FuncError('Integer expected, got "%s"' % str(n_start))

    try:
        n_len = int(n_len)
    except (TypeError, ValueError):
        raise FuncError('Integer expected, got "%s"' % str(n_len))

    return str(text)[n_start: n_start + n_len]


def mod(n_x, n_y):
    try:
        return str((n_x % n_y).normalize())
    except decimal.InvalidOperation:
        return


def tag_to_filename(pattern, m_tags, r_tags, ext=True, state=None,
                    is_dir=False):
    if not pattern:
        return
    if state is None:
        state = {}

    tags = m_tags
    tf = findfunc.parsefunc
    path_join = os.path.join

    if state is None:
        state = {}

    path_seps, text = tf(pattern, tags, state=state, path_sep="/")

    start_pos = 0
    new_dirs = []

    if path_seps:
        for p in path_seps:
            if start_pos != p:
                new_dirs.append(safe_name(text[start_pos:p]))
            start_pos = p
        new_dirs.append(safe_name(text[start_pos + 1:]))
    else:
        new_dirs = [safe_name(text)]

    if os.path.isabs(pattern):
        return add_extension('/' + '/'.join(map(safe_name, new_dirs)), tags, ext)
    else:

        subdirs = new_dirs
        count = len(path_seps)

        dirpath = r_tags.dirpath

        new_fn = encode_fn(path_join(*new_dirs))

        if new_fn.startswith('./'):
            return add_extension(path_join(dirpath, new_fn[len('./'):]), tags, ext)
        elif new_fn.startswith('../'):
            parent = dirpath
            while new_fn.startswith('../'):
                parent = os.path.dirname(parent)
                new_fn = new_fn[len('../'):]
            return add_extension(path_join(parent, new_fn), tags, ext)
        elif count and '..' not in subdirs:
            subdirs = dirpath.split('/')
            if count >= len(subdirs):
                parent = ['']
            else:
                if is_dir:
                    parent = subdirs[:-(count + 1)]
                else:
                    parent = subdirs[:-(count)]
        else:
            if is_dir:
                dirpath = os.path.dirname(r_tags.dirpath)
            parent = dirpath.split('/')

        if not parent[0]:
            parent.insert(0, '/')
        return add_extension(os.path.join(*(parent + [new_fn])), tags, ext)


def add_extension(fn, tags, addext=None, extension=None):
    if not addext:
        return fn
    elif addext and (extension is not None):
        return fn + os.path.extsep + encode_fn(extension)
    else:
        return fn + os.path.extsep + encode_fn(tags["__ext"])


def move(m_tags, p_pattern, r_tags, ext=True, state=None):
    """Tag to filename, Tag->File: $1
&Pattern, text"""

    tags = m_tags
    tf = findfunc.tagtofilename

    fn = tag_to_filename(p_pattern, m_tags, r_tags, ext, state)

    if fn:
        return {'__path': fn}


def mul(n_x, n_y):
    D = decimal.Decimal
    try:
        return str((D(n_x) * D(n_y)).normalize())
    except decimal.InvalidOperation:
        return


def neql(text, text1):
    if text == text1:
        return false
    else:
        return true


def not_(text):
    return false if check_truth(text) else true


def num(text, n_len, add_sep=false):
    if not text:
        return ""
    n_len = int(n_len)

    sep_index = text.find("/")

    if sep_index >= 0:
        total = text[sep_index + 1:]
        tracknum = text[:sep_index]
    else:
        total = None
        tracknum = text

    tracknum = tracknum.lstrip('0')

    if total and check_truth(add_sep):
        return "%s/%s" % (tracknum.zfill(n_len), total)
    else:
        return tracknum.zfill(n_len)


def odd(n_number):
    return true if (n_number % 2 != 0) else false


def or_(text, text1):
    return true if (check_truth(text) or check_truth(text1)) else false


def rand():
    import random
    return str(random.random())


def _round(n_value):
    return round(n_value)


def re_escape(rex, chars=r'^$[]\+*?.(){},|'):
    escaped = ""
    for ch in rex:
        if ch in chars:
            escaped = escaped + '\\' + ch
        else:
            escaped = escaped + ch
    return escaped


def pat_escape(p_pat):
    return re_escape(p_pat, '$%\\')


def remove_fields():
    '''Remove Fields, <blank> $0'''
    return ''


def remove_except(tags, fields):
    '''Remove all fields except, "Remove fields except: $1"
&Field list (; separated):, text, '''
    fields = [field for field in fields.split(';')]
    ret = dict([(field.strip(), '') for field in audioinfo.usertags(tags)
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


def replace(text, word, replaceword, matchcase=False, whole=False, chars=None):
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
        chars = '\,\.\(\) \!\[\]'
    replaceword = replaceword.replace('\\', '\\\\')

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
        except Exception as e:
            raise findfunc.FuncError(str(e))
    return text


class RegHelper(object):
    def __init__(self, groups, repl):
        self.groups = groups
        self._repl = repl

    def repl(self, match):
        v = int(match.group()[1:])
        try:
            if re.search('\$[\w\d_]+\(', self._repl):
                return re_escape(self.groups[v], '"\\,')
            else:
                return self.groups[v]
        except KeyError:
            return '""'


def replaceWithReg(m_tags, text, regex, repl, matchcase=False, m_text=None, state=None):
    """Replace with RegExp, "RegReplace $0: RegExp '$1' with '$2', Match Case: $3"
&Regular Expression, text
Replace &matches with:, text
Match &Case, check"""

    if not regex:
        return text

    if m_text is None:
        m_text = [text]

    if not check_truth(matchcase):
        flags = re.UNICODE | re.I
    else:
        flags = re.UNICODE

    def replace_tokens(match):
        groups = match.groups()
        group = match.group()
        if not group:
            d = {}
        elif groups:
            d = dict([(i, z if z is not None else "") for i, z in enumerate(groups, 1)])
            d[0] = group
        else:
            d = {1: group, 0: group}

        ret = re.sub('(?i)\$\d+', RegHelper(d, repl).repl, repl, 0)
        return findfunc.parsefunc(ret, m_tags)

    def replace_matches(value):
        try:
            try:
                return re.sub(regex, replace_tokens, value, 0, flags)
            except TypeError:
                # Python2.6 doesn't accept flags arg.
                if matchcase:
                    return re.sub('(?i)' + regex, replace_tokens, value, 0)
                else:
                    return re.sub(regex, replace_tokens, value, 0)
        except re.error as e:
            raise findfunc.FuncError(str(e))

    return "\\".join(replace_matches(z) for z in m_text)


replace_regex = replaceWithReg

VALID_FILENAME_CHARS = "'-_.!()[]{}&~+^ %s%s%s" % (
    string.ascii_letters, string.digits, os.path.sep)


# Contributed by Erik Reckase
def to_ascii(t_fn):
    cleaned_fn = unicodedata.normalize('NFKD', t_fn).encode('ASCII', 'ignore')
    return ''.join(chr(c) for c in cleaned_fn if chr(c) in VALID_FILENAME_CHARS)


def remove_dupes(m_text, matchcase=False):
    """Remove duplicate values, "Remove Dupes: $0, Match Case $1"
Match &Case, check"""
    text = m_text
    if isinstance(text, str):
        return text

    if matchcase:
        ret = []
        append = ret.append
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


def right(text, n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        raise FuncError('Integer expected, got "%s"' % str(n))
    if n == 0:
        return ''
    return text[-int(n):]


def gain_to_watts(gain):
    return 10 ** (-gain * .1)


def to_hexstring(x):
    # leading space required; blame Apple
    return " %08X" % int(x)


def rg2sc(gain, peak=None):
    if peak is None:
        gain = gain.split(':')
        if len(gain) == 2:  # gain:peak
            peak = float(gain[1])
            gain = float(gain[0])
        elif len(gain) == 3:  # channel:gain:peak
            peak = float(gain[2])
            gain = float(gain[1])
        else:
            return
    else:
        gain = float(gain)
        peak = float(peak)

    values = [
        to_hexstring(1000 * gain_to_watts(gain)),
        to_hexstring(1000 * gain_to_watts(gain)),
        to_hexstring(2500 * gain_to_watts(gain)),
        to_hexstring(2500 * gain_to_watts(gain)),
        " 00024CA8",  # bogus
        " 00024CA8",  # bogus
        to_hexstring(peak * (32 * 1024 - 1)),
        to_hexstring(peak * (32 * 1024 - 1)),
        " 00024CA8",  # bogus
        " 00024CA8",  # bogus
    ]

    return str(''.join(values))


def save_artwork(m_tags, pattern, r_tags, state=None, write=True):
    """Export artwork to file, "Export Art: pattern='$1'"
&Pattern (extension not required), text, folder_%img_counter%"""
    if state is None:
        state = {}

    if 'artwork_data' not in state:
        state['artwork_data'] = set()

    if '__image' in m_tags:
        images = m_tags['__image']
    else:
        images = r_tags.images

    if not images:
        return

    new_state = state.copy()
    new_state['img_count'] = str(len(images))
    for i, image in enumerate(images):
        data = image[audioinfo.DATA]
        new_state['img_desc'] = image.get(audioinfo.DESCRIPTION, '')
        new_state['img_type'] = audioinfo.IMAGETYPES[
            image.get(audioinfo.IMAGETYPE, 3)]
        mime = image.get(audioinfo.MIMETYPE, '')
        if not mime:
            mime = audioinfo.get_mime(data)
            if not mime:
                continue

        extension = '.png' if 'png' in mime.lower() else '.jpg'

        new_state['img_mime'] = mime
        new_state['img_counter'] = str(i + 1)
        fn = tag_to_filename(pattern, m_tags, r_tags,
                             False, new_state) + extension

        if not fn:
            continue

        if data not in state['artwork_data']:
            state['artwork_data'].add(data)
        elif path.exists(fn):
            continue

        i = 1
        while path.exists(fn):
            fn = path.splitext(fn)[0] + '_' + str(i) + extension
            i += 1

        if write:
            fobj = open(fn, 'w+b')
            fobj.write(data)
            fobj.close()
        else:
            return fn


def sort_field(m_text, order='Ascending', matchcase=False):
    """Sort values, "Sort $0, order='$1', Match Case='$2'"
&Order, combo, Ascending, Descending,
Match &Case, check"""
    text = m_text
    if not matchcase:
        key = natsort_case_key
    else:
        key = None
    if isinstance(text, str):
        return text
    if order == 'Ascending':
        return sorted(text, key=key)
    else:
        return sorted(text, key=key, reverse=True)


def split_by_sep(m_text, sep):
    """Split fields using separator, "Split using separator $0: sep='$1'"
&Separator, text, ;"""
    if isinstance(m_text, str):
        return m_text
    else:
        ret = []
        for t in m_text:
            try:
                ret.extend(t.split(sep))
            except ValueError:
                ret.append(t)
        return ret


def strip(text):
    '''Trim whitespace, Trim $0'''
    return text.strip()


def find(text, text1):
    val = text.find(text1)
    if val >= 0:
        return str(val)
    return '-1'


def sub(n_1, n_2):
    return str(n_1 - n_2)


def tag_dir(m_tags, pattern, r_tags, state=None):
    '''Tag to Dir, "Tag->Dir: $1"
&Pattern (can be relative path), text, %artist% - %album%'''
    if state is None:
        state = {'tag_dir': set()}

    elif 'tag_dir' not in state:
        state['tag_dir'] = set()

    if r_tags.dirpath in state['tag_dir']:
        return

    dirpath = r_tags.dirpath
    if pattern.endswith('/') and len(pattern) > 1:
        pattern = pattern[:-1]

    filename = tag_to_filename(pattern, m_tags, r_tags, False, state, True)
    if filename:
        state['tag_dir'].add(encode_fn(filename))
        return {DIRPATH: filename}


def testfunction(tags, t_text, p_pattern, n_number):
    text = '%s - %s' % (tags['artist'], tags['title'])
    assert t_text == text
    assert p_pattern == '%artist% - %title%'
    assert n_number == 23
    return 'Passed'


def texttotag(tags, input_text, p_pattern, output, state=None):
    """Text to Tag, "Text to Tag: $0 -> $1, $2"
&Text, text
&Pattern, text
&Output, text"""
    tagpattern = pyparsing.Literal('%').suppress() + \
                 pyparsing.Word(pyparsing.nums)
    input_text = findfunc.parsefunc(input_text, tags, state=state)
    d = findfunc.tagtotag(p_pattern, input_text, tagpattern)
    if d:
        for key in d:
            output = output.replace('%' +
                                    str(key), pat_escape(str(d[key])))
        return findfunc.parsefunc(output, tags, state=state)
    return None


def titleCase(text, ctype=None, characters=None):
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
    except mutagen.mp3.HeaderNotFoundError:
        return
    fields = [_f for _f in [z.strip() for z in fields.split(';')] if _f]
    if not fields:
        return tag.usertags
    else:
        if fields[0].startswith('~'):
            return dict([(k, v) for k, v in tag.usertags.items()
                         if k not in fields])
        else:
            return dict([(k, v) for k, v in tag.usertags.items()
                         if k in fields])


def upper(text):
    return text.upper()


def validate(text, to=None, chars=None):
    from .puddleobjects import safe_name
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
    "ceiling": ceiling,
    "char": char,
    "div": div,
    "enconvert": enconvert,
    "equals": eql,
    'filenametotag': filenametotag,
    "find": find,
    "floor": floor,
    "format": formatValue,
    "geql": geql,
    "grtr": grtr,
    "hasformat": hasformat,
    "if": if_,
    "iflonger": iflonger,
    # 'image_to_file': image_to_file,
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
    # 'remove_tag': remove_tag,
    "replace": replace,
    "regex": replaceWithReg,
    "right": right,
    "round": _round,
    'save_artwork': save_artwork,
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
    'to_ascii': to_ascii,
    'to_num': to_num
}

no_fields = [filenametotag, load_images, move, remove_except,
             save_artwork, tag_dir, update_from_tag]
no_preview = [autonumbering, load_images, remove_tag, save_artwork]

from . import findfunc

FuncError = findfunc.FuncError
ParseError = findfunc.ParseError
