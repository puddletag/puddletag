# -*- coding: utf-8 -*-
import re
from copy import copy
from functools import partial

from .constants import YES, NO

pattern = re.compile(r'[\\]*\$\d+')


def func(match, d):
    matchtext = match.group()
    if matchtext.startswith('\\'):
        return matchtext[1:]
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


def pprint(text, args):
    args = copy(args)
    f = partial(func, d=args)
    return pattern.sub(f, text)
