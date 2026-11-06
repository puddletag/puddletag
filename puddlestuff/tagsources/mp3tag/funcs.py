import re

from html.parser import HTMLParser

from puddlestuff.functions import replace_regex

conditionals = set(['if', 'ifnot'])


def debug(cursor, flag, filename=None, maxsize=None):
    if flag == 'on':
        cursor.debug = True
        cursor.debug_file = filename
    else:
        cursor.debug = False
    return


def do(cursor):
    """Only marks where `_while` jumps back to."""
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
    if exit == 1:
        cursor.charno = len(cursor.line)
    else:
        cursor.stop = True


def findline(cursor, text, index=1, exit=None, no_case=False):
    num_found = 1
    if no_case:
        text = text.lower()
    if index < 0:
        index = 0 - index
        lines = reversed(cursor.all_lines[:cursor.lineno])
        for i, line in enumerate(lines):
            if no_case:
                line = line.lower()
            if text in line:
                if num_found == index:
                    cursor.log('Found %s at line %d\n' % (text, i))
                    cursor.lineno = cursor.lineno - i - 1
                    cursor.charno = 0
                    return
                else:
                    num_found += 1
    else:
        for i, line in enumerate(cursor.lines):
            if no_case:
                line = line.lower()
            if text in line:
                if num_found == index:
                    cursor.log('Found %s at line %d\n' % (text, i))
                    cursor.lineno = cursor.lineno + i
                    cursor.charno = 0
                    return
                else:
                    num_found += 1

    if exit == 1:
        cursor.lineno = len(cursor.all_lines) - 1
    else:
        cursor.stop = True


def findlinenocase(cursor, text, num=1, exit=None):
    return findline(cursor, text, num, exit, True)


def gotochar(cursor, num):
    cursor.charno = num - 1


def gotoline(cursor, num):
    cursor.lineno = num - 1
    cursor.charno = 0


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
    # The page's last line is Cursor's extra end line: never join or delete it.
    lines = cursor.lines[:-1]
    if not lines:
        return
    count = len(lines) if num == -1 else min(num + 1, len(lines))
    cursor.all_lines[cursor.lineno] = ''.join(z.strip() for z in lines[:count])
    del (cursor.all_lines[cursor.lineno + 1: cursor.lineno + count])
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
        regexp = re.compile(r'</?%s(\s[^>]*)?>' % re.escape(tag), re.I)
        cursor.line = regexp.sub(lambda m: repl, cursor.line)


def movechar(cursor, num):
    cursor.charno = cursor.charno + num


def moveline(cursor, num, exit=None):
    cursor.log('Moving to line %d' % (cursor.lineno + num))
    target = cursor.lineno + num
    if target < 0 or target >= len(cursor.all_lines):
        if exit == 1:
            cursor.lineno = len(cursor.all_lines) - 1
            cursor.charno = 0
        else:
            cursor.stop = True
        return
    cursor.lineno = target
    cursor.charno = 0


def outputto(cursor, text):
    cursor.log('Outputting %s' % text)
    cursor.field = text


def replace(cursor, s, repl):
    cursor.line = cursor.line.replace(s, repl)


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
    cursor.cache += cursor.line[cursor.charno: cursor.charno + num]
    cursor.charno += num


def saynewline(cursor):
    cursor.cache += '\n'


def saynextnumber(cursor):
    m = re.search(r'\d+', cursor.line[cursor.charno:])
    if m is None:
        return
    cursor.log('Saying number %s\n' % m.group())
    cursor.cache += m.group()
    cursor.charno += m.end()


def saynextword(cursor):
    m = re.search(r'\w+', cursor.line[cursor.charno:])
    if m is None:
        return
    cursor.cache += m.group()
    cursor.charno += m.end()


def sayoutput(cursor, field):
    if field.lower() == 'currenturl':
        cursor.cache += cursor.url or ''
    elif field.lower() == cursor.field.lower():
        cursor.cache += cursor.cache
    else:
        cursor.cache += cursor.album.get(field, '')


def sayregexp(cursor, rexp, separator=' ', check=None):
    if (check is not None) and (check not in cursor.line):
        return
    if check:
        line = cursor.line[cursor.charno: cursor.line.find(check, cursor.charno)]
    else:
        line = cursor.line[cursor.charno:]
    matches = [match.group() for match in re.finditer(rexp, line)]
    cursor.cache += separator.join(matches)


def sayrest(cursor):
    cursor.log('Saying the rest of line from position %d.' % cursor.charno)
    cursor.log('Line: %s.' % cursor.line)
    cursor.log('Saying: %s\n' % cursor.line[cursor.charno:])
    cursor.cache += cursor.line[cursor.charno:]
    cursor.charno = len(cursor.line)


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
        cursor.charno = len(cursor.line)


def sayuntilml(cursor, text):
    cache = []
    lines = [z.strip() for z in cursor.lines]
    lines[0] = cursor.line[cursor.charno:]
    for i, line in enumerate(lines):
        index = line.find(text)
        if index == -1:
            cache.append(line)
        else:
            cache.append(line[:index])
            cursor.cache += '\n'.join(cache)
            if i:
                cursor.lineno += i
                cursor.charno = index
            else:
                cursor.charno += index
            return


def _set(cursor, field, value=None):
    value = '' if value is None else str(value)
    if field in cursor.album:
        del cursor.album[field]
    if field.lower() == cursor.field.lower():
        cursor.cache = value
    elif value:
        cursor.album[field] = value


def _while(cursor, condition, numtimes=None):
    nested = 0
    for i, (cmd, lineno, args) in enumerate(reversed(cursor.source[:cursor.cmd_index])):
        if cmd == 'while':
            nested += 1
        elif cmd == 'do':
            if nested > 0:
                nested -= 1
                continue
            do_index = cursor.cmd_index - i - 1
            cursor.passes[do_index] = cursor.passes.get(do_index, 0) + 1
            if (cursor.line[cursor.charno:].startswith(condition)
                    and (numtimes is None or cursor.passes[do_index] < numtimes)):
                cursor.next_cmd = do_index
                return True
            cursor.passes[do_index] = 0
            return


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
