"""Module for parsing functions,or in simple language
    This module takes a function specified like so $num(args)
    and then runs that function from the functions module
    
    E.g say you want to run the num function, you'll have
    $num(%track%,2) which would take the track number and
    append two zeroes to the front of it."""
import ply.lex as lex
import functions

# List of token names.   This is always required
tokens = (
   'NUMBER',
   'STRING',
   'STARTFUNC',
#   'EXTRA',

)

# Regular expression rules for simple tokens
literals=r"+-*/=&\(\),-"
#t_STRING=r'\(.*'
#t_STRING=r'(\\[\(,\)]).*[\(,\)]'
t_STARTFUNC= r"\$\w*\("
t_STRING=r'(%s|%s)' % (r'"(\\"|[^"])*"',r"'(\\'|[^'])*'")


# A regular expression rule with some action code
def t_NUMBER(t):
    r'\d+'
    try:
        t.value = int(t.value)    
    except ValueError:
        print "Line %d: Number %s is too large!" % (t.lineno,t.value)
        t.value = 0
    return t

#def t_STRING(t):
#    r'(.*\)'
    #t.value=t.value[1:-1]
#    return t

# Define a rule so we can track line numbers
def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

# A string containing ignored characters (spaces and tabs)
t_ignore  = ' \t'

#t_EXTRA=".+"
# Error handling rule
def t_error(t):
#    print "Illegal character '%s'" % t.value[0]
    t.lexer.skip(1)
    

# Build the lexer
lex.lex()
#lex.input('$what(shit)')
#while 1:
#    tok = lex.token()
#    if not tok: break      # No more input
#    print tok

import ply.yacc as yacc

precedence = (
    ('left','STARTFUNC'),
    ('left','UMINUS'),
    ('left','STRING'),
    )


def p_expression(p):
    """expression : expression expression
                        | func
                        | NUMBER
                        | STRING
                        """
    #print "expression "
    p[0] = " ".join(map(str,p[1:]))
    #print p[0]

def p_expression_uminus(p):
    "expression : '-' expression %prec UMINUS"
    if str(p[2])==int(p[2]): p[0] = -p[2]
    #print p[1]
    #pass
    
def p_arglist(p):
    """arglist : arglist "," expression
                | expression"""
    y=[]
    for z in p[1:]:
        
        if z==",":pass
        else: 
            #print "z is " + str(z)
            if type(z)==list:y.extend(z)
            #elif type(z)==str:y.append(z[1:-1])
            else: y.append(z)
    p[0]=y

def p_expression_func(p):
    """func : STARTFUNC arglist ')'"""
    args=[]
    for z in p[2]:
        if type(z)==str and z[0]=='"' and z[-1]=='"': 
            z=z[1:-1]
            args.append(z)
        elif str(long(z))==z:
            args.append(long(z))
        else:
            args.append(z)
    args=tuple(args)
    #print args
    p[0]=getattr(functions,p[1][1:-1])(*args)
    #print p[0]
  
def p_error(p):
    p[0] ="Syntax error at %s" % p.value

def parsefunc(functext):
    yacc.yacc()
    try:
        return yacc.parse(functext)
    except TypeError:
        return functext

