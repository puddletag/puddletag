# -*- coding: utf-8 -*-
import pdb, sys, logging
from pyparsing import *

import puddlestuff.findfunc as findfunc
import puddlestuff.audioinfo as audioinfo
from puddlestuff.util import to_string
from puddlestuff.puddleobjects import gettaglist, timemethod
import time
import re

def str_cmp(a, b):
    if not isinstance(a, basestring):
        a = u'\\'.join(a)

    if not isinstance(b, basestring):
        b = u'\\'.join(b)

    return a.lower() == b.lower()

FIELDS = set(z.lower() for z in gettaglist()).union(audioinfo.FILETAGS)

def parse_arg(audio, text):
    if not isinstance(text, basestring):
        return text
    if text[0] == u'%' and text[-1] == u'%':
        return to_string(audio.get(text[1:-1], u''))
    elif text in FIELDS:
        return to_string(audio.get(text, u''))
    else:
        if text[0] == u'"' and text[-1] == u'"':
            text = text[1:-1]
        return findfunc.parsefunc(text, audio)
    return u""

def wrap_nonzero(nonzero):
    def __nonzero__(self):
        if hasattr(self, 'args'):
            self.args = [parse_arg(self.audio, z) for z in self.args]
        else:
            self.arg = parse_arg(self.audio, self.arg)
        return nonzero(self)
    return __nonzero__

class BoolOperand(object):
    def __init__(self,t):
        self.args = t[0][0::2]
    
class BoolAnd(BoolOperand):
    @wrap_nonzero
    def __nonzero__(self):
        logging.debug('and: ' + unicode(self.args))
        for a in self.args:
            if not bool(a):
                return False
        return True

class BoolOr(BoolOperand):
    @wrap_nonzero
    def __nonzero__(self):
        logging.debug('or: ' + unicode(self.args))
        for a in self.args:
            if bool(a):
                return True
        return False

class BoolNot(BoolOperand):
    def __init__(self,t):
        self.arg = t[0][1]

    @wrap_nonzero
    def __nonzero__(self):
        logging.debug('not: ' + unicode(self.arg))
        if isinstance(self.arg, basestring):
            arg = self.arg.lower()
            for v in self.audio.values():
                if isinstance(v, basestring):
                    v = [v]
                v = u'\\\\'.join(v).lower()
                if arg in v:
                    return False
            return True
        return not bool(self.arg)

class Greater(BoolOperand):
    @wrap_nonzero
    def __nonzero__(self):
        logging.debug('greater: ' + unicode(self.args))
        try: self.args = map(float, self.args)
        except ValueError: pass
        return self.args[0] > self.args[1]

class Less(BoolOperand):
    @wrap_nonzero
    def __nonzero__(self):
        logging.debug('less: ' + unicode(self.args))
        try: self.args = map(float, self.args)
        except ValueError: pass
        return self.args[0] < self.args[1]

class Equal(BoolOperand):
    @wrap_nonzero
    def __nonzero__(self):
        logging.debug('equal: ' + unicode(self.args))
        return str_cmp(self.args[0], self.args[1])

class Missing(BoolOperand):
    def __init__(self, t):
        self.arg = t[0][1]

    def __nonzero__(self):
        logging.debug('missing: ' + unicode(self.arg))
        if getattr(self, "audio", None):
            return not (self.arg in self.audio)
        return False

class Present(BoolOperand):
    def __init__(self, t):
        self.arg = t[0][1]

    def __nonzero__(self):
        logging.debug('present: ' + unicode(self.arg))
        if getattr(self, "audio", None):
            return (self.arg in self.audio)
        return False

class BoolIs(BoolOperand):
    @wrap_nonzero
    def __nonzero__(self):
        logging.debug('is: ' + unicode(self.args))
        return str_cmp(self.args[0], self.args[1])

class Has(BoolOperand):
    @wrap_nonzero
    def __nonzero__(self):
        logging.debug('has: ' + unicode(self.args))
        return self.args[1].lower() in self.args[0].lower()

class Matches(BoolOperand):
    @wrap_nonzero
    def __nonzero__(self):
        logging.debug('matches: ' + unicode(self.args))
        return not re.search(self.args[1].lower(), self.args[0].lower()) is None
    
bool_exprs = [
    (CaselessLiteral("missing"), 1, opAssoc.RIGHT, Missing),
    (CaselessLiteral("present"), 1, opAssoc.RIGHT, Present),
    (CaselessLiteral("greater"), 2, opAssoc.LEFT, Greater),
    (CaselessLiteral("less"), 2, opAssoc.LEFT, Less),
    (CaselessLiteral("equal"), 2, opAssoc.LEFT, Equal),
    (CaselessLiteral("has"), 2, opAssoc.LEFT, Has),
    (CaselessLiteral("matches"), 2, opAssoc.LEFT, Matches),
    (CaselessLiteral("is"), 2, opAssoc.LEFT, BoolIs),
    (CaselessLiteral("and"), 2, opAssoc.LEFT,  BoolAnd),
    (CaselessLiteral("or"),  2, opAssoc.LEFT,  BoolOr),
    (CaselessLiteral("not"), 1, opAssoc.RIGHT, BoolNot),
    ]

field_expr = Combine(u'%' + Word(alphanums + '_') + u'%')
tokens = QuotedString('"', unquoteResults=False) \
    | field_expr | Word(alphanums + '_')
bool_expr = operatorPrecedence(tokens, bool_exprs)
bool_expr.enablePackrat()

def parse(audio, expr):
    for i in bool_exprs:
        i[3].audio = audio
    res = bool_expr.parseString(expr)[0]
    if isinstance(res, basestring):
        res = res.lower()
        for field, value in audio.items():
            if isinstance(value, basestring):
                value = [value]
            elif isinstance(value, (int, float)):
                value = [unicode(value)]
            try:
                if res in u'\\\\'.join(value).lower():
                    return True
            except TypeError, e:
                continue
    else:
        return bool(res)
    return False

if __name__ == '__main__':
    audio = audioinfo.Tag('clen.mp3')
    #parse(audio, "not p")
    #parse(audio, 'not missing artist')
    #parse(audio, '7 greater 6')
    #parse(audio, '%track% greater 14')
    #parse(audio, '%track% greater "$add($len(%artist%), 50)"')
    #t = time.time()
    #parse(audio, '(not missing artist) and (20 greater 19)')
    #parse(audio, 'not (20 greater 19)')
    #print time.time() - t
    #parse(audio, 'not missing artist and 18 greater 19')
    #parse(audio, 'artist is "Carl Douglas"')
    #parse(audio, "artist has aarl")
    #parse(audio, "artist has Carl")
    import time
    t = time.time()
    print audio.filepath
    print parse(audio, '__filename has clen')
    
