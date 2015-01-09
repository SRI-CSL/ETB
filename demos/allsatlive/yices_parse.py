#Defines grammar for reading yices files; used in the include <file> api for yices.
from pyparsing import *

#Grammar for s-expressions which is used to parse Yices expressions
token = Word(alphanums + "-./_:*+=!<>")

LPAR = "("
RPAR = ")"

#Yices comments are ignored; parentheses are retained since Yices expressions are printed back
#as strings for the Yices api
lispStyleComment = Group(";" + restOfLine)

sexp = Forward()

sexpList = ZeroOrMore(sexp)
sexpList.ignore(lispStyleComment)

sexpGroup =  Group(LPAR + sexpList + RPAR)

sexp << (token | sexpGroup)

#Grammar for Yices commands

#_LPAR = Suppress(LPAR)
#_RPAR = Suppress(RPAR)

#The command names are enumerated

yDefine = Literal("define")
yAssert = Literal("assert")
yAssertPlus = Literal("assert+")
yRetract = Literal("retract")
yCheck = Literal("check")
yMaxSat = Literal("maxsat")
ySetEvidence = Literal("set-evidence!")
ySetVerbosity = Literal("set-verbosity")
ySetArithOnly = Literal("set-arith-only")
yPush = Literal("push")
yPop = Literal("pop")
yEcho = Literal("echo")
yReset = Literal("reset")

yCommandName = yDefine + yAssert + yAssertPlus + yRetract + yCheck + yMaxSat + ySetEvidence + ySetVerbosity + ySetArithOnly + yPush + yPop + yEcho + yReset

#name is word without colons
name = Word(alphanums + "-./_*+=!<>")
colons = Suppress("::")

#Define commands are treated differently since we have to parse out the '::'
yDefineCommand = Group(yDefine + name + colons + sexp + sexpList)

yOtherCommandName = yAssert | yAssertPlus | yRetract | yCheck | yMaxSat | ySetEvidence | ySetVerbosity | ySetArithOnly | yPush | yPop | yEcho | yReset

yOtherCommand = Group(yOtherCommandName + sexpList)

yCommandBody = yDefineCommand | yOtherCommand

yCommand = Group(LPAR +  yCommandBody + RPAR)

yCommandList = ZeroOrMore(yCommand)

yCommandList.ignore(lispStyleComment)


# no longer used: defineName = Group(name + colons + sexp + sexpList)

lparPrint = " ("
rparPrint = ") "

def printSexp(parsedSexp):
    if parsedSexp == LPAR:
        return lparPrint
    elif parsedSexp == RPAR:
        return rparPrint
    elif type(parsedSexp) == str:
        return parsedSexp
    elif parsedSexp == []:
        return ''
    else:
        print(parsedSexp)
        first = printSexp(parsedSexp[0])
        rest = printSexp(parsedSexp[1:])
        print('first = %s' % first)
        print('rest = %s' % rest)
        if (first == lparPrint) or (first == rparPrint) or (rest == rparPrint):
            return '%s%s' % (first, rest)
        else: 
            return '%s %s' % (first, rest)

test1 = """(define a::bool)"""
test2 = """(define b ::bool)"""
test3 = """(define c :: bool)"""

            



