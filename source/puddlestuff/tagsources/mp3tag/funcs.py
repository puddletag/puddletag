from copy import deepcopy

import re

from html.parser import HTMLParser

from ...functions import replace_regex
from ...audioinfo import CaselessDict

conditionals = set(['if', 'ifnot'])


def debug(cursor, flag, filename=None, maxsize=None):
    if flag == 'on':
        cursor.debug = True
        cursor.debug_file = filename
    else:
        cursor.debug = False
    return


def do(cursor):
    cursor._domodified = deepcopy(cursor.output)
    cursor.num_loop += 1
    return


def _else(cursor):
    num_if = 0

    for i, (command, l, a) in enumerate(cursor.source[cursor.cmd_index + 1:]):
        if command == 'if' or command == 'ifnot':
            num_if += 1
        elif command == 'endif':
            if num_if == 0:
                cursor.next_cmd = i + cursor.cmd_index + 2
                return True
            else:
                num_if -= 1


def endif(cursor): return


def findinline(cursor, text, n=1, exit=None):
    cursor.log('findinline %s %d\n' % (text, n))
    line = cursor.line[cursor.charno:]
    i = 1
    t_len = len(text)
    start = 0
    while line.find(text, start) != -1:
        pos = line.find(text, start) + len(text)
        start = pos
        if i == n:
            cursor.charno += pos
            return
        i += 1
    cursor.charno = len(cursor.line) - 1
    return


def findline(cursor, text, index=1, exit=None, no_case=False):
    num_found = 1
    if no_case:
        text = text.lower()
    if index < 0:
        index = 0 - index
        if no_case:
            lines = reversed(cursor.all_lowered[:cursor.lineno])
        else:
            lines = reversed(cursor.all_lines[:cursor.lineno])
        for i, line in enumerate(lines):
            if text in line:
                if num_found == index:
                    cursor.log('Found %s at line %d\n' % (text, i))
                    cursor.lineno = cursor.lineno - i - 1
                    cursor.charno = 0
                    return
                else:
                    num_found += 1
    else:
        if no_case:
            lines = cursor.lowered
        else:
            lines = cursor.lines
        for i, line in enumerate(lines):
            if text in line:
                if num_found == index:
                    cursor.log('Found %s at line %d\n' % (text, i))
                    cursor.lineno = cursor.lineno + i
                    cursor.charno = 0
                    return
                else:
                    num_found += 1

    cursor.lineno = len(cursor.all_lines) - 1


def findlinenocase(cursor, text, num=1, exit=None):
    return findline(cursor, text, num, text, True)


def gotochar(cursor, num):
    cursor.charno = num - 1


def gotoline(cursor, num):
    cursor.lineno = num - 1
    cursor.charno = num - 1


def _if(cursor, text, ifnot=False):
    if ifnot:
        if not cursor.line[cursor.charno:].startswith(text):
            return
    else:
        if cursor.line[cursor.charno:].startswith(text):
            return

    num_if = 0
    for i, (command, lineno, args) in enumerate(cursor.source[cursor.cmd_index + 1:]):
        if command in ('if', 'ifnot'):
            num_if += 1
            # print 'if', cursor.source[i + cursor.cmd_index + 1]
        elif command == 'endif':
            # print 'end_if', cursor.source[i + cursor.cmd_index + 1]
            if num_if == 0:
                cursor.next_cmd = i + cursor.cmd_index + 2
                # print 'endif', cursor.source[i + cursor.cmd_index + 1]
                return True
            else:
                num_if -= 1
        elif command == 'else' and num_if == 0:
            # print 'else', cursor.source[i + cursor.cmd_index + 1]
            cursor.next_cmd = i + cursor.cmd_index + 2
            # print 'else', cursor.source[i + cursor.cmd_index + 2]
            # pdb.set_trace()
            return True


def ifnot(cursor, text):
    return _if(cursor, text, True)


def joinlines(cursor, num):
    ret = cursor.lines[:num]
    cursor.all_lines[cursor.lineno] = ''.join(ret)
    del (cursor.all_lines[cursor.lineno: cursor.lineno + num])
    cursor.lineno = cursor.lineno


def joinuntil(cursor, text):
    ret = []
    index = None
    for line in cursor.lines:
        if text in line:
            index = line.find(text) + len(text)
            ret.append(line[:index])
            # if line.strip() == text:
            break
        else:
            v = line.strip()
            if v:
                ret.append(v)

    if index is None:
        return

    append = [line[index:]] if line[index:].strip() else []
    al = cursor.all_lines
    cursor.all_lines = al[:cursor.lineno] + [''.join(ret)] + \
                       append + al[cursor.lineno + len(ret):]
    cursor.lineno = cursor.lineno


def killtag(cursor, tag, repl=' '):
    if repl:
        cursor.log('Killing HTML tag %s with %s\n' % (tag, repl))
    else:
        cursor.log('Killing HTML tag %s\n' % tag)

    if tag == '*':
        parser = TagProcessor()
        parser.feed(cursor.line)
        text = '%s%s%s' % (' ', repl.join(parser.pieces), ' ')
        cursor.log(cursor.line + ' becomes ' + text + '\n')
        cursor.line = text
        return
    else:
        leave, to_rep = cursor.line[:cursor.charno], cursor.line[cursor.charno:]
        cursor.line = leave + to_rep.replace('<%s>' % tag, repl)


def movechar(cursor, num):
    cursor.charno = cursor.charno + num


def moveline(cursor, num, exit=None):
    cursor.log('Moving to line %d' % (cursor.lineno + num))
    cursor.lineno = cursor.lineno + num
    cursor.charno = 0


def outputto(cursor, text):
    if text.lower() == 'tracks' and cursor.num_loop:
        if cursor.output is not cursor.album:
            cursor.tracks.append(cursor.output)
        cursor.output = CaselessDict()
        cursor.field = 'title'
    elif text.lower() == 'tracks':
        if cursor.field in cursor.output:
            cursor.output[cursor.field] += cursor.cache
        else:
            cursor.output[cursor.field] = cursor.cache
        field = cursor.field
        cursor.cache = ''
        cursor.tracks = {}
        cursor.output = CaselessDict()
        cursor.field = 'title'
        del (cursor.output[field])
    elif not cursor.num_loop:
        if cursor.output is not cursor.album:
            cursor.output = cursor.album
        cursor.log('Outputting %s' % text)
        cursor.field = text
    else:
        cursor.log('Outputting %s' % text)
        cursor.field = text


def replace(cursor, s, repl):
    text = cursor.line[cursor.charno:].replace(s, repl)
    cursor.line = cursor.line[:cursor.charno] + text


def regexpreplace(cursor, regexp, s):
    text = replace_regex({}, cursor.line, regexp, s,
                         matchcase=True)
    # Now uses whole line instead of just from the current char onwards
    # because Mp3tag is being a fucking idiot.
    cursor.line = text
    cursor.charno = 0


def say(cursor, text):
    cursor.log('say %s' % text)
    cursor.cache += text


def saynchars(cursor, num):
    cursor.cache += cursor.line[cursor.charno + 1: cursor.charno + num]
    cursor.charno += num


def saynewline(cursor):
    cursor.cache += '\n'


def saynextnumber(cursor):
    try:
        number = re.search('\d+', cursor.line[cursor.charno:]).group()
        cursor.log('Saying number %s\n' % number)
        cursor.cache += number
        cursor.charno += len(number)
    except AttributeError:
        return


def saynextword(cursor):
    word = re.search('\w+', cursor.line[cursor.charno:]).group()
    cursor.cache += word
    cursor.charno += len(word)


def sayoutput(cursor, field):
    if field.lower().strip() == 'tracks' and cursor.tracks:
        field = 'title'

    track_field = [field.lower(), cursor.field.lower()]
    track_field = cursor.track_fields.intersection(track_field)
    track_field = track_field or (cursor.field.lower() == 'track')

    if track_field and cursor.tracks:
        field = field.lower()
        if field in cursor.output:
            v = [z.strip() for z in cursor.output[field].split("|")]
            v_len = len(v)
        for i, t in enumerate(cursor.tracks):
            if field in t:
                t[cursor.field] = t.get(field)
            elif v and i < v_len:
                t[cursor.field] = v[i]
    else:
        v = cursor.output.get(field, '')
        cursor.cache += v


def sayregexp(cursor, rexp, separator=None, check=None):
    if (check is not None) and (check not in cursor.line):
        return
    if cursor.charno + 1 == len(cursor.line):
        return
    if check:
        line = cursor.line[cursor.charno: cursor.line.find(check, cursor.charno)]
    else:
        line = cursor.line[cursor.charno:]
    if separator is not None:
        matches = [match.group() for match in
                   re.finditer(rexp, line)]
        cursor.cache += separator.join(matches)
    else:
        match = re.search(rexp, line).group()
        if match:
            cursor.cache += match


def sayrest(cursor):
    cursor.log('Saying the rest of line from position %d.' % cursor.charno)
    cursor.log('Line: %s.' % cursor.line)
    cursor.log('Saying: %s\n' % cursor.line[cursor.charno:])
    cursor.cache += cursor.line[cursor.charno:]
    cursor.charno = len(cursor.line) - 1


def sayuntil(cursor, text):
    cursor.log('SayUntil start: %d' % cursor.charno)
    cursor.log('Line: %s.' % cursor.line)
    line = cursor.line[cursor.charno:]
    index = line.find(text)
    if index != -1:
        cursor.cache += line[:index]
        cursor.log('Saying: %s\n' % line[:index])
        cursor.charno = cursor.charno + index
    else:
        cursor.log('%s not found.\n' % text)
        cursor.log('Saying: %s\n' % line)
        cursor.cache += line
        cursor.charno = len(cursor.line) - 1


def sayuntilml(cursor, text):
    cache = []
    lines = cursor.lines[::]
    lines[0] = cursor.line[cursor.charno:]
    for i, line in enumerate(lines):
        index = line.find(text)
        if index == -1:
            cache.append(line)
        else:
            cache.append(line[:index])
            cursor.cache += '\n'.join(cache)
            cursor.charno = index + 1
            cursor.lineno += i
            return


def _set(cursor, field, value=None):
    if not value:
        if field in cursor.output:
            del (cursor.output[field])
        elif cursor.field == field:
            cursor.cache = ""
    else:
        cursor.output[field] = value if \
            isinstance(value, str) else str(value)


def _while(cursor, condition, numtimes=None):
    cursor.num_loop -= 1
    cursor.num_iters = 0
    nested = 0
    if cursor.line[cursor.charno:].startswith(condition):
        for i, (cmd, lineno, args) in enumerate(reversed(cursor.source[:cursor.cmd_index])):
            if cmd == 'do':
                if nested > 0:
                    nested -= 1
                    continue
                if numtimes is None:
                    cursor.next_cmd = cursor.cmd_index - i - 1
                    return True
                elif numtimes >= cursor.num_iters:
                    cursor.next_cmd = cursor.cmd_index - i - 1
                    return True
                cursor.num_iters += 1
            elif cmd == 'while':
                nested += 1

    if cursor.tracks == {}:
        cursor.tracks = [{'title': z.strip()} for z in
                         cursor.cache.split('|')]
        cursor.track_fields.add('title')
    elif cursor.output and cursor.tracks:
        if cursor.output != cursor._domodified:
            cursor.tracks.append(cursor.output)
            list(map(cursor.track_fields.add, (z.lower() for z in cursor.output)))


def unspace(cursor):
    cursor.line = cursor.line.strip()
    cursor.charno = 0


class TagProcessor(HTMLParser):
    def reset(self):
        self.pieces = []
        HTMLParser.reset(self)

    def handle_data(self, text):
        self.pieces.append(text)


FUNCTIONS = {
    'debug': debug,
    'do': do,
    'else': _else,
    'endif': endif,
    'findinline': findinline,
    'findline': findline,
    'findlinenocase': findlinenocase,
    'gotochar': gotochar,
    'gotoline': gotoline,
    'if': _if,
    'ifnot': ifnot,
    'joinlines': joinlines,
    'joinuntil': joinuntil,
    'killtag': killtag,
    'movechar': movechar,
    'moveline': moveline,
    'outputto': outputto,
    'regexpreplace': regexpreplace,
    'replace': replace,
    'say': say,
    'saynchars': saynchars,
    'saynewline': saynewline,
    'saynextnumber': saynextnumber,
    'saynextword': saynextword,
    'sayoutput': sayoutput,
    'sayregexp': sayregexp,
    'sayrest': sayrest,
    'sayuntil': sayuntil,
    'sayuntilml': sayuntilml,
    'set': _set,
    'unspace': unspace,
    'while': _while}
