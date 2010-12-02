# -*- coding: utf-8 -*-
import re, os
from sgmllib import SGMLParser
import htmlentitydefs
from puddlestuff.functions import replaceWithReg

conditionals = set(['if', 'ifnot'])

def debug(cursor, flag, filename=None, maxsize=None):
    if flag == 'on':
        cursor.debug = True
        cursor.debug_file = filename
    else:
        cursor.debug = False
    return

def do(cursor):
    cursor.num_loop += 1
    return

def _else(cursor):
    num_if = 0

    for i, (command, l, a) in enumerate(cursor.source[cursor.cmd_index + 1:]):
        if command == 'if' or command == 'ifnot':
            num_if += 1
        elif command == 'endif' :
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

def findline(cursor, text, index=1, exit=None):
    num_found = 1
    for i, line in enumerate(cursor.lines):
        if text in line:
            if num_found == index:
                cursor.log('Found %s at line %d\n' % (text, i))
                cursor.lineno = cursor.lineno + i
                cursor.charno = 0
                return
            else:
                num_found += 1

def findlinenocase(cursor, text, num=1, exit=None):
    text = text.lower()
    i = 1
    for line in cursor.lowered:
        if text in line:
            if i == num:
                cursor.lineno = line
                cursor.charno = 0
                return
            else:
                i += 1

def gotochar(cursor, num):
    cursor.charno = num - 1

def gotoline(cursor, num):
    cursor.lineno = num - 1
    cursor.charno = num - 1

def _if(cursor, text, ifnot=False):
    #if text == '"':
        #pdb.set_trace()
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
            #print 'if', cursor.source[i + cursor.cmd_index + 1]
        elif command == 'endif':
            #print 'end_if', cursor.source[i + cursor.cmd_index + 1]
            if num_if == 0:
                cursor.next_cmd = i + cursor.cmd_index + 2
                #print 'endif', cursor.source[i + cursor.cmd_index + 1]
                #pdb.set_trace()
                return True
            else:
                num_if -= 1
        elif command == 'else' and num_if == 0:
            #print 'else', cursor.source[i + cursor.cmd_index + 1]
            cursor.next_cmd = i + cursor.cmd_index + 2
            #print 'else', cursor.source[i + cursor.cmd_index + 2]
            #pdb.set_trace()
            return True

def ifnot(cursor, text):
    return _if(cursor, text, True)

def joinlines(cursor, num):
    ret = cursor.lines[:num]
    cursor.all_lines[cursor.lineno] = u''.join(ret)
    del(cursor.all_lines[cursor.lineno: cursor.lineno + num])

def joinuntil(cursor, text):
    ret = []
    for line in cursor.lines:
        if text in line:
            index = line.find(text) + len(text)
            ret.append(line[:index])
            break
        else:
            ret.append(line + u' ')

    append = line[index:]
    cursor.all_lines[cursor.lineno] = u''.join(ret)
    del(cursor.all_lines[cursor.lineno + 1: cursor.lineno + len(ret)])
    cursor.all_lines.insert(cursor.lineno + len(ret) +1, append)

def killtag(cursor, tag, repl=u' '):
    if repl:
        cursor.log('Killing HTML tag %s with %s\n' % (tag, repl))
    else:
        cursor.log('Killing HTML tag %s\n' % tag)

    if tag == '*':
        parser = TagProcessor()
        parser.feed(cursor.line)
        text = u'%s%s%s' % (u' ', repl.join(parser.pieces), u' ')
        cursor.log(cursor.line  + u' becomes ' + text + u'\n')
        cursor.all_lines[cursor.lineno] = text
        return
    else:
        leave, to_rep = cursor.line[:cursor.charno], cursor.line[cursor.charno:]
        try:
            cursor.all_lines[cursor.lineno] = leave + to_rep.replace(u'<%s>' % tag, repl)
        except:
            import pdb
            pdb.set_trace()
            print 'here'

def movechar(cursor, num):
    cursor.charno = cursor.charno + num

def moveline(cursor, num, exit=None):
    cursor.log('Moving to line %d' % (cursor.lineno + num))
    cursor.lineno = cursor.lineno + num
    cursor.charno = 0

def outputto(cursor, text):
    if text.lower() == 'tracks' and cursor.num_loop:
        cursor.log('Outputting Tracks')
        if cursor.output is not cursor.album:
            cursor.tracks.append(cursor.output)
        cursor.output = {}
        cursor.field = 'title'
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
    cursor.all_lines[cursor.lineno] = cursor.line[:cursor.charno] + text

def regexpreplace(cursor, regexp, s):
    text = replaceWithReg(cursor.line[cursor.charno:], regexp, s)
    cursor.all_lines[cursor.lineno] = cursor.line[:cursor.charno] + text

def say(cursor, text):
    cursor.log('say %s' % text)
    cursor.cache += text

def saynchars(cursor, num):
    cursor.cache += cursor.line[cursor.charno + 1: cursor.charno + num]
    cursor.charno += num

def saynewline(cursor):
    cursor.cache += u'\n'

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
    cursor.cache += cursor.output.get(field, u'')

def sayregexp(cursor, rexp, separator=None, check=None):
    #if rexp == r"\d\d?(?=(\.|-))":
        #pdb.set_trace()
    if (check is not None) and (check not in cursor.line):
        return
    if separator is not None:
        #end = 0
        for match in re.finditer(rexp, cursor.line[cursor.charno:]):
            cursor.cache = separator + match.group()
            #end = match.end()
        #cursor.charno += end
    else:
        try:
            match = re.search(rexp, cursor.line[cursor.charno]).group()
            if match:
                cursor.cache += match.group()
                #cursor.charno += match.end()
        except:
            pdb.set_trace()
            cursor.cache += re.search(rexp, cursor.line).group()

def sayrest(cursor):
    cursor.log('Saying the rest of line from position %d.' % cursor.charno)
    cursor.log('Line: %s.' % cursor.line)
    cursor.log('Saying: %s\n' % cursor.line[cursor.charno:])
    cursor.cache += cursor.line[cursor.charno:]
    cursor.lineno += 1
    cursor.charno = 0

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
    for i, line in enumerate(cursor.lines):
        index = line.find(text)
        if index != -1:
            cache.append(line)
        else:
            cache.append(line[:index])
            cursor.cache += u'\n'.join(cache)
            cursor.charno = index + 1
            cursor.lineno += i
            return

def _set(cursor, field, value=None):
    if value is None:
        if field in cursor.output: del(cursor.output[field])
    else:
        cursor.output[field] = value if \
            isinstance(value, unicode) else unicode(value)

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

def unspace(cursor):
    cursor.all_lines[cursor.lineno] = cursor.line.strip()
    cursor.charno = 0

class TagProcessor(SGMLParser):
    def reset(self):
        self.pieces = []
        SGMLParser.reset(self)

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
    