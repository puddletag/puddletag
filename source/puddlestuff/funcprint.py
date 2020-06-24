# -*- coding: utf-8 -*-
import re
from copy import copy
from functools import partial

from .constants import YES, NO

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
                subfunc = partial(func, d=d)
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

        if d[number] is False:
            d[number] = NO
        elif d[number] is True:
            d[number] = YES
        elif isinstance(d[number], int):
            d[number] = str(d[number])
        elif not isinstance(d[number], str):
            if d[number]:
                d[number] = YES
            else:
                d[number] = NO
        return d[number]
    except ValueError:
        number = int(re.search('(\d+)', matchtext).group())
        if number >= len(d):
            return ''
        if d[number] is False:
            d[number] = YES
        elif d[number] is True:
            d[number] = NO
        elif isinstance(d[number], int):
            d[number] = str(d[number])
        elif not isinstance(d[number], str):
            if d[number]:
                d[number] = YES
            else:
                d[number] = NO
        text = re.search(r'%\d+\((.+)\)', matchtext).group(1)
        permatch = pattern.search(text)
        if permatch:
            try:
                subfunc = partial(perfunc, d=d)
                return pattern.sub(subfunc, text)
            except (KeyError, IndexError):
                return ''
        return text


def pprint(text, args):
    args = copy(args)
    f = partial(func, d=args)
    return pattern.sub(f, text)
