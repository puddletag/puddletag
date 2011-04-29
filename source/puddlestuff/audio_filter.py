# -*- coding: utf-8 -*-
import pdb, sys, logging
from pyparsing import *

import puddlestuff.findfunc as findfunc
import puddlestuff.audioinfo as audioinfo
from puddlestuff.util import to_string
import time
if len(sys.argv) > 1:
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

def parse_arg(audio, text):
    if not isinstance(text, basestring):
        return text
    if text[0] == '%' and text[-1] == '%':
        return to_string(audio.get(text[1:-1], ''))
    elif text in audio:
        return to_string(audio[text])
    else:
        if text[0] == '"' and text[-1] == '"':
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
        return not bool(self.arg)

class Greater(BoolOperand):
    @wrap_nonzero
    def __nonzero__(self):
        logging.debug('greater: ' + unicode(self.args))
        t = time.time()
        
        x = self.args[0] > self.args[1]
        print 'a', time.time() - t
        return x

class Less(BoolOperand):
    @wrap_nonzero
    def __nonzero__(self):
        logging.debug('less: ' + unicode(self.args))
        return self.args[0] < self.args[1]

class Equal(BoolOperand):
    @wrap_nonzero
    def __nonzero__(self):
        logging.debug('equal: ' + unicode(self.args))
        return self.args[0] == self.args[1]

class Missing(BoolOperand):
    def __init__(self, t):
        self.arg = t[0][1]

    def __nonzero__(self):
        logging.debug('missing: ' + unicode(self.arg))
        if getattr(self, "audio", None):
            return not (self.arg in audio)
        return False

class Present(BoolOperand):
    def __init__(self, t):
        self.arg = t[0][1]

    def __nonzero__(self):
        logging.debug('present: ' + unicode(self.arg))
        if getattr(self, "audio", None):
            return (self.arg in audio)
        return False

class BoolIs(BoolOperand):
    @wrap_nonzero
    def __nonzero__(self):
        logging.debug('is: ' + unicode(self.args))
        return self.args[0] == self.args[1]

class Has(BoolOperand):
    @wrap_nonzero
    def __nonzero__(self):
        logging.debug('has: ' + unicode(self.args))
        return self.args[1] in self.args[0]
    
bool_exprs = [
    ("missing", 1, opAssoc.RIGHT, Missing),
    ("present", 1, opAssoc.RIGHT, Present),
    ("greater", 2, opAssoc.LEFT, Greater),
    ("less", 2, opAssoc.LEFT, Less),
    ("equal", 2, opAssoc.LEFT, Equal),
    ("has", 2, opAssoc.LEFT, Has),
    ("is", 2, opAssoc.LEFT, BoolIs),
    ("and", 2, opAssoc.LEFT,  BoolAnd),
    ("or",  2, opAssoc.LEFT,  BoolOr),
    ("not", 1, opAssoc.RIGHT, BoolNot),
    ]
    
field_expr = '%' + Word(alphanums) + '%'
tokens = QuotedString('"', unquoteResults=False) \
    | field_expr | Word(alphanums)
bool_expr = operatorPrecedence(tokens, bool_exprs)

def parse(audio, expr):
    for i in bool_exprs:
        i[3].audio = audio
    return bool(bool_expr.parseString(expr)[0])

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
    parse(audio, "artist has Carl")