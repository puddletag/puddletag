# -*- coding: utf-8 -*-
import logging
import re

from pyparsing import (CaselessLiteral, Combine, OpAssoc, ParserElement,
                       QuotedString, Word, alphanums, infix_notation)


from . import findfunc, audioinfo
from .puddleobjects import gettaglist
from .util import to_string


ParserElement.enable_packrat()


def str_cmp(a, b):
    if not isinstance(a, str):
        a = '\\'.join(a)

    if not isinstance(b, str):
        b = '\\'.join(b)

    return a.lower() == b.lower()


FIELDS = set(z.lower() for z in gettaglist()).union(audioinfo.FILETAGS)


def parse_arg(audio, text):
    if not isinstance(text, str):
        return text
    if text[0] == '%' and text[-1] == '%':
        return to_string(audio.get(text[1:-1], ''))
    elif text in FIELDS:
        return to_string(audio.get(text, ''))
    else:
        if text[0] == '"' and text[-1] == '"':
            text = text[1:-1]
        return findfunc.parsefunc(text, audio)


def wrap_bool(original):
    def __bool__(self):
        if hasattr(self, 'args'):
            self.args = [parse_arg(self.audio, z) for z in self.args]
        else:
            self.arg = parse_arg(self.audio, self.arg)
        return original(self)

    return __bool__


class BoolOperand(object):
    def __init__(self, t):
        self.args = t[0][0::2]


class BoolAnd(BoolOperand):
    @wrap_bool
    def __bool__(self):
        logging.debug('and: ' + str(self.args))
        for a in self.args:
            if not bool(a):
                return False
        return True


class BoolOr(BoolOperand):
    @wrap_bool
    def __bool__(self):
        logging.debug('or: ' + str(self.args))
        for a in self.args:
            if bool(a):
                return True
        return False


class BoolNot(BoolOperand):
    def __init__(self, t):
        self.arg = t[0][1]

    @wrap_bool
    def __bool__(self):
        logging.debug('not: ' + str(self.arg))
        if isinstance(self.arg, str):
            arg = self.arg.lower()
            for v in self.audio.values():
                if isinstance(v, str):
                    v = [v]
                v = '\\\\'.join(v).lower()
                if arg in v:
                    return False
            return True
        return not bool(self.arg)


class Greater(BoolOperand):
    @wrap_bool
    def __bool__(self):
        logging.debug('greater: ' + str(self.args))
        try:
            self.args = list(map(float, self.args))
        except ValueError:
            pass
        return self.args[0] > self.args[1]


class Less(BoolOperand):
    @wrap_bool
    def __bool__(self):
        logging.debug('less: ' + str(self.args))
        try:
            self.args = list(map(float, self.args))
        except ValueError:
            pass
        return self.args[0] < self.args[1]


class Equal(BoolOperand):
    @wrap_bool
    def __bool__(self):
        logging.debug('equal: ' + str(self.args))
        return str_cmp(self.args[0], self.args[1])


class Missing(BoolOperand):
    def __init__(self, t):
        self.arg = t[0][1]

    def __bool__(self):
        logging.debug('missing: ' + str(self.arg))
        if getattr(self, "audio", None):
            return not (self.arg in self.audio)
        return False


class Present(BoolOperand):
    def __init__(self, t):
        self.arg = t[0][1]

    def __bool__(self):
        logging.debug('present: ' + str(self.arg))
        if getattr(self, "audio", None):
            return (self.arg in self.audio)
        return False


class BoolIs(BoolOperand):
    @wrap_bool
    def __bool__(self):
        logging.debug('is: ' + str(self.args))
        return str_cmp(self.args[0], self.args[1])


class Has(BoolOperand):
    @wrap_bool
    def __bool__(self):
        logging.debug('has: ' + str(self.args))
        return self.args[1].lower() in self.args[0].lower()


class Matches(BoolOperand):
    @wrap_bool
    def __bool__(self):
        logging.debug('matches: ' + str(self.args))
        return not re.search(self.args[1].lower(), self.args[0].lower()) is None


bool_exprs = [
    (CaselessLiteral("missing"), 1, OpAssoc.RIGHT, Missing),
    (CaselessLiteral("present"), 1, OpAssoc.RIGHT, Present),
    (CaselessLiteral("greater"), 2, OpAssoc.LEFT,  Greater),
    (CaselessLiteral("less"),    2, OpAssoc.LEFT,  Less),
    (CaselessLiteral("equal"),   2, OpAssoc.LEFT,  Equal),
    (CaselessLiteral("has"),     2, OpAssoc.LEFT,  Has),
    (CaselessLiteral("matches"), 2, OpAssoc.LEFT,  Matches),
    (CaselessLiteral("is"),      2, OpAssoc.LEFT,  BoolIs),
    (CaselessLiteral("and"),     2, OpAssoc.LEFT,  BoolAnd),
    (CaselessLiteral("or"),      2, OpAssoc.LEFT,  BoolOr),
    (CaselessLiteral("not"),     1, OpAssoc.RIGHT, BoolNot),
]

field_expr = Combine('%' + Word(alphanums + '_') + '%')
tokens = QuotedString('"', unquote_results=False) \
         | field_expr | Word(alphanums + '_')
bool_expr = infix_notation(tokens, bool_exprs)


def parse(audio, expr):
    for i in bool_exprs:
        i[3].audio = audio
    try:
        res = bool_expr.parse_string(expr)[0]
    except ParseException as e:
        res = expr
    if isinstance(res, str):
        res = res.lower()
        for field, value in audio.items():
            if isinstance(value, str):
                value = [value]
            elif isinstance(value, (int, float)):
                value = [str(value)]
            try:
                logging.debug('simple filter: %s in %s', res, value)
                if res in '\\\\'.join(value).lower():
                    return True
            except TypeError as e:
                continue
    else:
        return bool(res)
    return False


if __name__ == '__main__':
    audio = audioinfo.Tag('clen.mp3')
    # parse(audio, "not p")
    # parse(audio, 'not missing artist')
    # parse(audio, '7 greater 6')
    # parse(audio, '%track% greater 14')
    # parse(audio, '%track% greater "$add($len(%artist%), 50)"')
    # t = time.time()
    # parse(audio, '(not missing artist) and (20 greater 19)')
    # parse(audio, 'not (20 greater 19)')
    # print time.time() - t
    # parse(audio, 'not missing artist and 18 greater 19')
    # parse(audio, 'artist is "Carl Douglas"')
    # parse(audio, "artist has aarl")
    # parse(audio, "artist has Carl")
    import time

    t = time.time()
    print(audio.filepath)
    print(parse(audio, '__filename has clen'))
