from __future__ import with_statement
import os
import sys

import ctypes
import tempfile
import re

if sys.platform == 'darwin':
    libext = ".dylib" #set DYLD_LIBRARY_PATH to point to the directory with libyices.dylib
else: libext = ".so"  #set LD_LIBRARY_PATH to point to the directory with libyices.so

libyices = ctypes.CDLL('libyices%s' % libext)

libyices.yices_version.restype = ctypes.c_char_p
libyices.yices_mk_context.restype = ctypes.c_void_p
libyices.yices_get_last_error_message.restype = ctypes.c_char_p
libyices.yices_enable_log_file.argtypes = [ctypes.c_char_p]
libyices.yices_parse_command.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
libyices.yices_del_context.argtypes = [ctypes.c_void_p]
libyices.yices_inconsistent.argtypes = [ctypes.c_void_p]
libyices.yices_set_verbosity.argtypes = [ctypes.c_int]
libyices.yices_get_lite_context.argtypes = [ctypes.c_void_p]
libyices.yices_get_lite_context.restype = ctypes.c_void_p
libyices.yices_mk_bool_var.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
libyices.yices_mk_bool_var.restype = ctypes.c_void_p
libyices.yices_assert.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
libyices.yices_assert_retractable.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
libyices.yices_get_var_decl_from_name.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
libyices.yices_get_var_decl_from_name.restype = ctypes.c_void_p
libyices.yices_get_value.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
libyices.yices_get_model.argtypes = [ctypes.c_void_p]
libyices.yices_get_model.restype = ctypes.c_void_p
libyices.yices_parse_expression.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
libyices.yices_parse_expression.restype = ctypes.c_void_p
libyices.yices_get_unsat_core_size.argtypes = [ctypes.c_void_p]
libyices.yices_get_unsat_core_size.restype = ctypes.c_uint
libyices.yices_get_unsat_core.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
libyices.yices_get_unsat_core.restype = ctypes.c_uint
libyices.yices_check.argtypes = [ctypes.c_void_p]
libyices.yices_get_arith_value_as_string.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
libyices.yices_free_string.argtypes = [ctypes.c_void_p]
libyices.yices_evaluate_in_model.argtypes = [ctypes.c_void_p, ctypes.c_void_p]#model, bool_expr
libyices.yices_evaluate_in_model.restypes = ctypes.c_int #returns -1(false), 0 (undef), 1 (true)

# Nice output formatting for functions returning lbool in C API
yices_lbool_results = ['unsat', 'unknown', 'sat']
yices_lbool_model_vals = ['false', 'dont care', 'true']

class counter:
    def __init__(self):
        self.count = 0

    def new(self):
        self.count += 1
        return self.count

class srec_t(ctypes.Structure):
    ''' Python correspondence to the srec_t C structure used by yices to return
    string representations of numerical values.'''
    _fields_ = [("flag",ctypes.c_int),("str",ctypes.c_char_p)]
        
def yices_enable_type_checker(flag):
    ''' Enable or disable the type checker of yices.'''
    if flag:
        libyices.yices_enable_type_checker(1)
    else:
        libyices.yices_enable_type_checker(0)

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
        first = printSexp(parsedSexp[0])
        rest = printSexp(parsedSexp[1:])
        if (first == lparPrint) or (first == rparPrint) or (rest == rparPrint):
            return '%s%s' % (first, rest)
        else: 
            return '%s %s' % (first, rest)

class YicesContextManager(object):
    """  A context manager for Yices that encapsulates the operations on a context.  """

    def __init__(self):
        """
        Creates a fresh context.
        """
        self.libyices = libyices
        self.context = self.libyices.yices_mk_context()
        self.allvars = []
        self.allvars_stack = []
        self.commands = []
        self.commands_stack = []
        self.last_error_msg = ''
        self.model = {}

    def __del__(self):
        """ Deletes the context and manager object. 
        """
        # Note that __del__ could be called more than once, but
        # yices_del_context will segment fault if called a second time.
        if self.context is not None:
            self.libyices.yices_del_context(self.context)
            self.context = None

    def yices_command(self, command):
        """Manager utility for executing a command. """
        return self.libyices.yices_parse_command(self.context, command)

    def yices_set_last_error_msg(self, msg):
        """The field last_error_msg records the last error message."""
        self.last_error_msg = msg
        print(msg)

    def yices_get_last_error_msg(self):
        """Method for accessing the last error message. """
        return self.last_error_msg
        
    def yices_define(self, var, type, body=None):
        """Method for adding a definition of var of type with optional body.
        The command is appended to command, and var is appended to allvars."""
        if body:
            command = '(define %s::%s %s)' % (var, type, body)
        else:
            command = '(define %s::%s)' % (var, type)
        result = self.libyices.yices_parse_command(self.context, command)
        if result == 0:
            self.yices_set_last_error_msg(self.libyices.yices_get_last_error_message())
        else:
            self.commands.append(command)
            if type in ['bool', 'int', 'nat', 'real']:
                self.allvars.append((var, type))
        return result

    def version(self):
        ''' Return the version of yices.  Not used anywhere.'''
        return libyices.yices_version()

    def yices_assert_plus(self, formula):
        """retractable assertion of formula.  (No support for retraction yet.)"""
        yicesexpr = libyices.yices_parse_expression(self.context,yformula);
        if yicesexpr:
            result = self.libyices.yices_assert_retractable(self.context, yicesexpr)
            if result == 0:
                self.yices_set_last_error_msg(self.libyices.yices_get_last_error_message())
                return result
            else:
                self.commands.append('(assert+ %s)' % formula)
                return result
        else:
            return 0

    def yices_include_define(self, parseDefineBody):
        """Utility for parsing and adding a definition from an included file.
        """
        #print('parseDefineBody = %s' % parseDefineBody)
        
        if (len(parseDefineBody) < 3):
            result = self.yices_define(parseDefineBody[0], parseDefineBody[1])
            return result
        else:
            result = self.yices_define(parseDefineBody[0], parseDefineBody[1],
                                       printSexp(parseDefineBody[2]))
            return result
        


    def yices_include(self, file):
        '''Executes an (include <file>) command by parsing the individual commands.
        The commands define, push, and pop need special treatment since they affect the
        context.  The other commands are processed by yices_command.  '''
        #print('file = %s' % file)
        parsedFile = yCommandList.parseFile(file)
        for parseIn in parsedFile:
            #print('parseIn = %s' % parseIn)
            body = parseIn[1]
            action = body[0]  #action is the second element following lparen
            if action == 'define':
                self.yices_include_define(body[1:]) #-1 removes last paren
            elif action == 'push':
                self.yices_push()
            elif action == 'pop':
                self.yices_pop()
            else: 
                command = printSexp(parseIn)
                result = self.yices_command(command)
                if result == 0:
                    self.yices_set_last_error_msg(self.libyices.yices_get_last_error_message())
                    return result
                else:
                    self.commands.append(command)
                    return result

    def yices_push(self):
        ''' Utility for pushing the scope in a context.'''
        result = self.libyices.yices_parse_command(self.context, '(push)')
        if result == 0:
            self.yices_set_last_error_msg(self.libyices.yices_get_last_error_message())
            return result
        else:
            self.commands_stack.append(self.commands.length())
            self.allvars_stack.append(self.allvars.length())
            return result

    def yices_pop(self):
        """Method for applying the pop command and updating the commands field."""
        if self.commands_stack.length() == 0:
            result = self.libyices.yices_parse_command(self.context, '(pop)')
            if result == 0:
                self.yices_set_last_error_msg(self.libyices.yices_get_last_error_message())
                return result
            else:
                top = self.commands_stack.pop()
                self.commands = self.commands[:top]
                return result
        else:
            self.yices_set_last_error_msg('No corresponding push.')
            return 0
            

    def yices_reset(self):
        '''Applies (reset) command to the yices context and local fields.'''
        result = self.libyices.yices_parse_command(self.context, '(reset)')
        if result == 0:
            self.yices_set_last_error_msg(self.libyices.yices_get_last_error_message())
            return result
        else: #clear the context
            self.commands = []
            self.commands_stack = []
            self.allvars = []
            self.allvars_stack = []
            return result

    def yices_check(self):
        """Method for checking consistency. Returns sat, unsat, or unknown."""
        result = self.libyices.yices_check(self.context)
        return yices_lbool_results[result + 1]

    def yices_inconsistent(self):
        ''' Returns true if the context is inconsistent (but this
        might need a preceding check).  This method does not perform a
        satisfiability check.'''
        return libyices.yices_inconsistent(self.context) != 0

    def yices_assignment(self, varlist = []):
        ''' If inconsistent, clear assignment.  Otherwise, if a model
        is available, retrieve the values for atomic variables.'''
        assignment = {}
        if not self.yices_inconsistent():
            ymodel = self.libyices.yices_get_model(self.context)
            print('allvars: %s' % self.allvars)
            if ymodel != None:
                for variable, type in self.allvars:
                    if (varlist == []) | (variable in varlist):
                        vdecl = self.libyices.yices_get_var_decl_from_name(self.context, variable)
                        if type == 'bool' :
                            val = self.libyices.yices_get_value(ymodel, vdecl)
                            if val != 0:
                                assignment[variable] = yices_lbool_model_vals[val + 1] #turns val into an lbool
                        else:
                            val = srec_t();
                            self.libyices.yices_get_arith_value_as_string(ymodel,vdecl,ctypes.byref(val))
                            if val.flag != 0:
                                assignment[variable] = val.str;
                                self.libyices.yices_free_string(ctypes.byref(val))
            else:
                self.yices_set_last_error_msg('No model available. Call check() first')
        else:
            self.yices_set_last_error_msg( 'Context is inconsistent and there is no assignment')
        return assignment

from etb.wrapper import Tool, InteractiveTool, Substitutions, Errors, Success
from etb.terms import mk_term
from etb.terms import Term

class YicesLibrary(InteractiveTool):
    """ETB wrapper for yices"""
    ''' The yices context.'''

    def __init__(self, etb, libyices):
        '''
        Create a dynamically linked library, bind it to library, and
        call the parent initialization method.
        '''
        print('Initializing YicesLibrary')
        InteractiveTool.__init__(self, etb)

    @Tool.volatile    
    @Tool.predicate("-Version:value")
    def yicesVersion(self, version):
        print('finding version')
        result = libyices.yices_version()
        print('found version')
        return Substitutions(self, [{version: mk_term(result)}])

    @Tool.predicate("-Session:handle")
    def yicesStart(self, session):
        """
        Creates a fresh Yices session with session_info initialized so that
        decls is the current list of declarations, unsatcore is the unsatisfiable
        core, assignment is the model, and stack is the length of the decls
        at the point of the more recently scoped push.  
        """
        print('yicesStart: entry')        
        sessionOut = self.add_session('yices', {'manager': YicesContextManager(), 'timestamp': 0})
        return Substitutions(self, [{session: mk_term(sessionOut)}])
    
    @Tool.predicate("+Session:handle")
    def yicesClose(self, session):
        sid = self.session_id(session)
        s_entry = self.session(sid)
        mgr = s_entry['manager']
        mgr.__del__()
        self.del_session(sid)
        return Success(self)
    
    def yices_command(self, sessionIn, command):
        '''
        Utility for proessing yices commands. The command is executed using
        yices_parse_command, and if the result is non-0, then update session_info,
        update the timestamp with tick, and return a new session handle.
        '''
        sid = self.session_id(sessionIn) #checks validity of sessionIn
        s_entry = self.session(sid)
        mgr = s_entry['manager']
        result = mgr.yices_command(command)
        if result == 0:  #yices_command can return 1 on type error, so this is wrong
            self.fail(mgr.yices_get_last_error_msg())
        else:
            sessionOut = self.tick(sessionIn)
            return sessionOut

    def yices_define(self, sessionIn, var, type, body = None):
        '''
        Utility for proessing yices define commands. The command is executed using
        yices_define, and if the result is non-0, then update session_info,
        update the timestamp with tick, and return a new session handle.
        '''
        sid = self.session_id(sessionIn) #checks validity of sessionIn
        s_entry = self.session(sid)
        libyices = self.library
        mgr = s_entry['manager']
        result = mgr.yices_define(var, type, body)
        if result == 0:
            self.fail(mgr.yices_get_last_error_msg())
        else:
            sessionOut = self.tick(sessionIn)
            return sessionOut
        

    @Tool.predicate("+SessionIn:handle, +Var:value, +Type:value, -SessionOut:handle")    
    def yicesDeclare(self, sessionIn, var, type, sessionOut):
        ''' Define a variable.  If "body is not "None" the variable
        will become a yices macro.  "var", "type" have to be in yices syntax.'''
        print('yicesDeclare: entry')        
        result = self.yices_define(sessionIn, var, type)
        return Substitutions(self, [{sessionOut: mk_term(result)}])

    @Tool.predicate("+SessionIn:handle, +Var:value, +Type:value, +Body:value, -SessionOut:handle")    
    def yicesDefine(self, sessionIn, var, type, body, sessionOut):
        ''' Define a variable.  "var", "type", and 
        "body" have to be in yices syntax.'''
        print('yicesDefine: entry')        
        result = self.yices_define(sessionIn, var, type, body)
        return Substitutions(self, [{sessionOut: mk_term(result)}])

    @Tool.predicate("+SessionIn:handle, +Formula:value, -SessionOut:handle")
    def yicesAssert(self, sessionIn, formula, sessionOut):
        ''' Assert formula into a logical context.  Input has to be in
        yices format.  '''
        print('yicesAssert: entry')
        command = '(assert %s)' % formula
        result = self.yices_command(sessionIn, command)
        return Substitutions(self, [{sessionOut: mk_term(result)}])

    @Tool.predicate("+SessionIn:handle, +Formula:value, -SessionOut:handle")
    def yicesAssertNegation(self, sessionIn, formula, sessionOut):
        ''' Assert formula into a logical context.  Input has to be in
        yices format.  '''
        print('yicesAssertNegation: entry')
        command = '(assert (not %s))' % formula
        print('command: %s' % command)
        result = self.yices_command(sessionIn, command)
        print('after yices_command')
        return Substitutions(self, [{sessionOut: mk_term(result)}])

    @Tool.predicate("+SessionIn:handle, +Formula:value, -SessionOut:handle")
    def yicesAssertPlus(self, sessionIn, formula, sessionOut):
        print('yicesAssertPlus: entry')        
        sid = self.session_id(sessionIn)
        s_entry = self.session(sid)
        mgr = s_entry['manager']
        yid = mgr.yices_assert_plus(formula)
        if yid != 0:
            session_out = self.tick(sessionIn)
            return [{sessionOut: mk_term(session_out)}]
        else:
            self.fail(mgr.yices_get_last_error_msg())

    @Tool.predicate("+SessionIn:handle, +File:file, -SessionOut:handle")
    def yicesIncludeFile(self, sessionIn, file, sessionOut):
        print('yicesIncludeFile: entry')
        sid = self.session_id(sessionIn)
        print('sid: %s' % sid)
        s_entry = self.session(sid)
        print('s_entry: %s' % s_entry)
        mgr = s_entry['manager']
        print('mgr: %s' % mgr)
        print('file: %s' % file)
        print('filename: %s' % file['file'])
        yid = mgr.yices_include(file['file'])
        print('yid: %s' % yid)
        if yid != 0:
            session_out = self.tick(sessionIn)
            return Substitutions(self, [{sessionOut: mk_term(session_out)}])
        else:
            self.fail(mgr.yices_get_last_error_msg())

    def yices_push(self, sessionIn):
        ''' Utility for proessing yices commands.  It extracts the session
        id sid from the sessionIn input, finds the session entry s_entry'''
        sid = self.session_id(sessionIn) #check validity of sessionIn
        s_entry = self.session(sid)
        mgr = s_entry['manager']
        result = mgr.yices_command('(push)')
        if result == 0:
            self.fail(mgr.yices_get_last_error_msg())
        else:
            sessionOut = self.tick(sessionIn)
            return sessionOut

    @Tool.predicate("+SessionIn:handle, -SessionOut:handle")
    def yicesPush(self, sessionIn, sessionOut):
        ''' Create a new level on the assertion stack.'''
        print('yicesPush: entry')        
        result = self.yices_push(sessionIn)
        return Substitutions(self, [{sessionOut: mk_term(result)}])

    def yices_pop(self, sessionIn):
        ''' Utility for processing yices commands'''
        sid = self.session_id(sessionIn) #check validity of sessionIn
        s_entry = self.session(sid)
        mgr = s_entry['manager']
        result = mgr.yices_pop()
        if (result == 0):
            self.fail(mgr.yices_get_last_error_msg())
        else:
            sessionOut = self.tick(sessionIn)
            return sessionOut
    
    @Tool.predicate("+SessionIn:handle, -SessionOut:handle")
    def yicesPop(sessionIn, sessionOut):
        ''' Remove the top level from the assertion stack.'''
        print('yicesPop: entry')        
        result = self.yices_pop(sessionIn)
        return Substitutions(self, [{sessionOut: mk_term(result)}])

    def yices_check(self, sessionIn):
        """ Checks sessionIn for consistency. """

    @Tool.predicate("+SessionIn:handle, -SessionOut:handle, -Result:value")
    def yicesCheck(self, sessionIn, sessionOut, result): 
        ''' Check consistency of the context.  This method performs a
        satisfiability check.  It returns the result as a string.'''
        print('yicesCheck: entry')        
        sid = self.session_id(sessionIn)
        s_entry = self.session(sid)
        mgr = s_entry['manager']
        out = mgr.yices_check()
        newSession = self.tick(sessionIn)
        return Substitutions(self, [{sessionOut: mk_term(newSession), result: mk_term(out)}])

    @Tool.predicate("+SessionIn:handle, Result:value")
    def yicesInconsistent(self, sessionIn, result): 
        ''' Passively checks consistency of the context.  Only makes sense
        when preceded by a call to yicesCheck.  It returns the result as a string.'''
        print('yicesInconsistent: entry')        
        sid = self.session_id(sessionIn)
        s_entry = self.session(sid)
        mgr = s_entry['manager']
        out = mgr.yices_inconsistent()
        return Substitutions(self, [{result: mk_term(out)}])

    @Tool.predicate("+SessionIn:handle, Model:value")
    def yicesModel(self, sessionIn, model):
        print('yicesModel: entry')        
        sid = self.session_id(sessionIn)
        s_entry = self.session(sid)
        mgr = s_entry['manager']
        assignment = mgr.yices_assignment()
        print('assignment: %s' % assignment)
        vars = [var for var in assignment]
        out = ''        
        for var in vars:
            out += '(= %s %s)' % (var, assignment[var])
        out = '(and %s)' % out
        print('model %s' % out)
        return Substitutions(self, [{model: mk_term(out)}])

    @Tool.predicate("+SessionIn:handle, -SessionOut:handle")    
    def yicesReset(self, sessionIn, sessionOut):
        ''' Reset the logical context.'''
        print('yicesReset: entry')        
        sid = self.session_id(sessionIn)
        s_entry = self.session(sid)
        mgr = s_entry['manager']
        result = mgr.yices_reset()
        if result == 0:
            self.fail(mgr.yices_get_last_error_msg())
        else:
            session_out = self.tick(sessionIn)
            return Substitutions(self, [{sessionOut: mk_term(session_out)}])

def register(etb) :
    """Register Yices"""
    etb.add_tool(YicesLibrary(etb, 'libyices.dylib'))
