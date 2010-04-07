import re, pdb
from functools import partial
from copy import copy
pattern = re.compile(r'(%\d+\(.+\))|([\\]*\$\d+)')

def perfunc(match, d):
    matchtext = match.group()
    if matchtext.startswith('\\'):
        return matchtext[1:]
    try:
        number = int(matchtext[1:])
        if number >= len(d):
            return ''
        return d[number]
    except ValueError:
        text = matchtext[1:-1]
        if pattern.search(text):
            try:
                subfunc = partial(func, d = d)
                return pattern.sub(subfunc, text)
            except KeyError:
                return ''
        return matchtext

def func(match, d):
    matchtext = match.group()
    if matchtext.startswith('\\'):
        return matchtext[1:]
    try:
        number = int(matchtext[1:])
        if number >= len(d):
            return ''
        if not isinstance(d[number], basestring):
            if d[number]:
                d[number] = u'Yes'
            else:
                d[number] = u'No'
        return d[number]
    except ValueError:
        number = int(re.search('(\d+)', matchtext).group())
        if number >= len(d):
            return ''
        if not isinstance(d[number], basestring):
            if d[number]:
                d[number] = u'Yes'
            else:
                d[number] = u'No'
        text = re.search(r'%\d+\((.+)\)', matchtext).group(1)
        permatch = pattern.search(text)
        if permatch:
            try:
                subfunc = partial(perfunc, d = d)
                return pattern.sub(subfunc,text)
            except (KeyError, IndexError):
                return ''
        return text

def pprint(text, args):
    args = copy(args)
    f = partial(func, d=args)
    return pattern.sub(f, text)

if __name__ == '__main__':
    text = '$1 - %5( first ) $4'
    j = {1: 'keith',
        2: 'the great',
        4: 'i am'}
    print pprint(text, j)