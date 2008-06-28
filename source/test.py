from pyparsing import Word, alphas, alphanums, nums, ZeroOrMore, Literal,Forward,delimitedList, OneOrMore,NotAny, Combine

def what(s, loc, tok):
    return "not the shit"

lparen = Literal("(").suppress()
rparen = Literal(")").suppress()
shit = ZeroOrMore(Word(alphanums + " !@#$%^&*(){}|\\][?+=/_S-sZVWwvz~`")
tag = Combine(NotAny(r"\\") + Literal("%") + OneOrMore(Word(alphas)) + Literal("%")).setParseAction(what)
#identifier = ZeroOrMore("\$") + Word(alphas, alphanums + "_ ()")
#integer  = Word( nums )
#functor =  Word("$" + alphanums + "_")
#arg = identifier | integer
#args = arg + ZeroOrMore("," + arg)
##expression = functor + lparen + args + rparen

content = Forward()
shot = shit + tag + shit
content << shot #This is not the shit
#expression = functor + lparen + delimitedList(content) + rparen
#content << (expression | identifier | integer)
parsedContent = tag.scanString("\aoe %what%.eaou %stahoeu%")
for z in parsedContent:
    print z
