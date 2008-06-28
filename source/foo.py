import sre,audioinfo,os
from myparser import parsefunc

def foo(text):
    """getfunc(text)
    parses the functions it text and replaces
    them with their return value. The functions
    are defined in functions.py
    
    Function must be of the form $name(args)
    Returns None if unsuccesful"""
    pat = sre.compile(r'\$[a-z]+\(')
    
    start = 0
    funcs=[]
    #Get the functions
    while 1: 
        match = pat.search(text, start) 
        if match is None: break 
        idx = match.end(0) 
        num_brackets_open = 1
        try:
            while num_brackets_open > 0: 
                if text[idx] == ')': 
                    num_brackets_open -= 1 
                elif text[idx] == '(': 
                    num_brackets_open += 1
                idx += 1  # Check for end-of-text!
                if idx>len(text): break
        except IndexError:
            return text
        
        ##Replace a function with it's parsed text
        #text=text.replace(text[match.start(0):idx],
                          #parsefunc(text[match.start(0):idx]))
        start = idx + 1
        print text[match.start(0):idx]
    return text

foo("$num(123,23) aoetnsuh $shit(213,234)")
