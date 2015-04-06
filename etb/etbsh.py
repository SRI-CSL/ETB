#!/usr/bin/env python

""" ETB shell

This module sets up an ETB client to interact with an ETB node (see :mod:`etb.etbd`)
It is normally invoked with ``etbsh --etb``.



..
   Copyright (C) 2013 SRI International

   This program is free software: you can redistribute it
   and/or modify it under the terms of the GNU General Public License as
   published by the Free Software Foundation, either version 3 of the
   License, or (at your option) any later version. This program is
   distributed in the hope that it will be useful, but WITHOUT ANY
   WARRANTY; without even the implied warranty of MERCHANTABILITY or
   FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
   for more details.  You should have received a copy of the GNU General
   Public License along with this program.  If not, see
   <http://www.gnu.org/licenses/>.
"""

import os, shutil, sys, signal, platform, traceback
import json
import subprocess
import pprint
import re
import xmlrpclib
import readline
import fcntl
import termios
import struct
import time
from string import Template
from functools import wraps
import threading
import colorama
from colorama import Fore, Back, Style

colorama.init()
sys.path.append(os.path.abspath(os.path.join(__file__, '..')))

import terms
import parser
from etbconfig import ETBSHConfig, ETBConfig
from etbclientlib import ETBClient, ETBCmdLineClient

# def print_star_args(*args):
#     for count, thing in enumerate(args):
#         print '{0}. {1}'.format(count, thing)

# class ETBReader(threading.Thread):
#     '''
#     Helper class to implement asynchronous reading of a file descriptor
#     in a separate thread. Pushes read lines on a queue for the shell
#     '''
#     def __init__(self, fd, queue):
#         assert isinstance(queue, Queue.Queue)
#         assert callable(fd.readline)
#         threading.Thread.__init__(self)
#         self._fd = fd
#         self._queue = queue
 
#     def run(self):
#         '''The body of the tread: read lines and put them on the queue.'''
#         for line in iter(self._fd.readline, ''):
#             self._queue.put(line)
 
#     def eof(self):
#         '''Check whether there is no more content to expect.'''
#         return not self.is_alive() and self._queue.empty()

class ETBShTemplate(Template):
    """ Subclass of string.Template that allows identifiers of form `x[1][a][0]`
    Used to do substitution so that if `$x` is an ETB Term, then `$x[1][a][0]`
    is reduced, or an error is raised.
    """
    idpattern = r'[_a-z][_a-z0-9]*(\[[_a-z0-9]+\])*'

    def substitute(self, *args, **kws):
        if len(args) > 1:
            raise TypeError('Too many positional arguments')
        if not args:
            mapping = kws
        elif kws:
            mapping = _multimap(kws, args[0])
        else:
            mapping = args[0]
        # Helper function for .sub()
        def convert(mo):
            # Check the most common path first.
            named = mo.group('named') or mo.group('braced')
            if named is not None:
                bkidx = named.find('[')
                if bkidx == -1:
                    # No args indices - just do subst
                    if named in mapping:
                        val = mapping[named]
                    else:
                        raise TypeError('${0} not set'.format(named))
                    return '%s' % (val,)
                else:
                    # else we need to reduce
                    id = named[0:bkidx]
                    argsd = named[bkidx:]
                    val = mapping[id]
                    if isinstance(val, basestring):
                        # We use this idiom instead of str() because the latter will
                        # fail if val is a Unicode containing non-ASCII characters.
                        fullstr = '%s%s' % (val, argsd)
                        red = '%s' % (parser.parse_term(fullstr),)
                    else:
                        arglist = [s[:-1] for s in argsd.split('[')[1:]]
                        while arglist != []:
                            arg = arglist.pop(0)
                            arg = int(arg) if arg.isdigit() else arg
                            if isinstance(val, terms.Term):
                                if isinstance(arg, int):
                                    arg = terms.mk_numberconst(arg)
                                else:
                                    arg = terms.mk_stringconst(arg)
                                val = val.reduce_access(arg)
                            elif isinstance(val, terms.Subst):
                                arg = terms.mk_var(arg)
                                val = val(arg)
                            elif isinstance(val, list):
                                if isinstance(arg, int) and arg < len(val):
                                    val = val[arg]
                                else:
                                    raise ValueError('varsubst: invalid index {0} for list {1}'
                                                     .format(arg, val))
                            elif isinstance(val, dict):
                                if arg in val:
                                    val = val[arg]
                                else:
                                    raise ValueError('varsubst: invalid key {0} for dict {1}'
                                                     .format(arg, val))
                            else:
                                raise ValueError('varsubst: invalid access {0} for {1} {2}'
                                                 .format(arg, type(val), val))
                        red = '%s' % val
                    return red
            if mo.group('escaped') is not None:
                return self.delimiter
            if mo.group('invalid') is not None:
                self._invalid(mo)
            raise ValueError('Unrecognized named group in pattern',
                             self.pattern)
        return self.pattern.sub(convert, self.template)

class Command(object):
    '''
    A class for ETB-shell commands.
    It includes the pyparsing parser used to parse the command line.
    '''
    def __init__(self, cmd, *args):
        self.cmd = cmd
        self.args = args

    @staticmethod
    def fromParser(self, loc, toks):
        return Command(*toks.asList())

    @staticmethod
    def expand_binding(bindings, args):
        res = []
        for a in args:
            field_access = re.match('(.+)\.(.+)', a)
            if field_access:
                field = field_access.group(2)
                fv = field_access.group(1)
                if fv in bindings:
                    try:
                        na = bindings[fv].get(field)
                    except:
                        na = a
                else:
                    na = a
            elif a in bindings:
                na = bindings[a]
            else:
                na = a
            res.append(na)
        return res

# The *_command decorator are used to organize the online help in categories
    
def etb_command(method):
    method._etb_command = True
    return method

def client_command(method):
    method._client_command = True
    return method

def query_command(method):
    method._query_command = True
    return method

def file_command(method):
    method._file_command = True
    return method

class ETBShell(ETBCmdLineClient):

    def __init__(self, descr):
        self.config = ETBSHConfig()
        self._root_dir = os.getcwd()
        self._base_dir = '.'
        self._bindings = {}
        self._queries = {}
        #,  'query', 'prove'
        self._etb_cmds = set(['put_file', 'get_file', 'get_filehandle', 'predicates', 'rules', 'facts'])
        
        self._remote_etb_cmds = set(['find_claims', 'all_claims', 'wait_query',
                                     'answers'])
        
        self._remote_admin_cmds = set(['connect', 'link', 'tunnel', 'proxylink'])
        ETBCmdLineClient.__init__(self, descr,
                                  os.path.join(os.getcwd(), ".etb-shell-history"),
                                  list(self.client_commands) + list(self.etb_commands) +
                                  list(self._remote_etb_cmds) + list(self._remote_admin_cmds))


    @property
    def etb_commands(self):
        """List of etb commands"""
        all_methods = self.__class__.__dict__.values()
        return self._etb_cmds.union(set(m.__name__ for \
                                            m in all_methods if hasattr(m, '_etb_command')))

    @property
    def client_commands(self):
        all_methods = self.__class__.__dict__.values()
        return set(m.__name__ for \
                         m in all_methods if hasattr(m, '_client_command'))

    @property
    def query_commands(self):
        all_methods = self.__class__.__dict__.values()
        return set(m.__name__ for \
                         m in all_methods if hasattr(m, '_query_command'))

    @property
    def file_commands(self):
        all_methods = self.__class__.__dict__.values()
        return set(m.__name__ for \
                         m in all_methods if hasattr(m, '_file_command'))
    
    @property
    def remote_commands(self):
        """List of remote ETB commands"""
        return list(self.etb().system.listMethods())

    def valid_command(self, cmd):
        return (cmd in self.remote_commands or
                cmd in self.client_commands or
                cmd in self.etb_commands or
                cmd in self.query_commands or
                cmd in self.file_commands)

    def sort_commands(self):
        verbose = False
        current_etb_cmds = []
        current_admin_cmds = []
        for remote_fun in self.remote_commands:
            if remote_fun in self._remote_etb_cmds:
                if verbose: 
                    print("Found %s in _remote_etb_cmds\n" % remote_fun)
                current_etb_cmds.append(remote_fun)
            elif remote_fun in self._remote_admin_cmds:
                if verbose:
                    print("Found %s in _remote_admin_cmds\n" % remote_fun)
                current_admin_cmds.append(remote_fun)
            else:
                if verbose:
                    print("Didn't find %s\n" % remote_fun)
                pass
        return (current_etb_cmds, current_admin_cmds)

    @client_command
    def help(self, *args):
        '''help for ETB shell commands

        With no arguments, gives help summary.  Otherwise provides help for the given command.
        '''
        if len(args) == 0:
            self.help_summary()
        else:
            #print('remote_commands = {0}'.format(self.remote_commands))
            if self.valid_command(args[0]):
                docs = getattr(self,args[0]).__doc__
                #doclines = doc.splitlines()
                print('{0}: {1}'.format(args[0], docs))
            else:
                print('{0} not found'.format(args[0]))

    def help_summary(self):
        (etb_cmds, admin_cmds) = self.sort_commands()
        
        print('\nAvailable commands')
        print('==================\n')
        
        print('Client commands')
        print('---------------')
        for f in sorted(self.client_commands):
            fun = self.__getattribute__(f)
            doc = getattr(fun, '__doc__', '').splitlines()[0]
            if doc:
                print("{0:<25} {1}".format(f, doc))
                
        print('\nETB commands')
        print('---------------')
        for f in sorted(self.etb_commands):
            fun = self.__getattribute__(f)
            doc = getattr(fun, '__doc__', '').splitlines()[0]
            if doc:
                print("{0:<25} {1}".format(f, doc))

        print('\nQuery commands')
        print('--------------')
        for f in sorted(self.query_commands):
            fun = self.__getattribute__(f)
            print("{0:<25} {1}".format(f, getattr(fun, '__doc__', '').splitlines()[0]))

        print('\nFile commands')
        print('-------------')
        for f in sorted(self.file_commands):
            fun = self.__getattribute__(f)
            print("{0:<25} {1}".format(f, getattr(fun, '__doc__', '').splitlines()[0]))
            
        print('\nAdmin commands')
        print('--------------')
        for remote_fun in sorted(admin_cmds):
            hlp = self.etb().system.methodHelp(remote_fun)
            hlp = str(hlp).splitlines()[0]
            print("{0:<25} {1}".format(remote_fun, hlp))

        print('')

    @client_command
    def quit(self, code=0):
        """Quit the ETB shell."""
        print('')
        self._history.save()
        self.kill_etb()
        try:
            sys.exit(code)
        except SystemExit as e:
            os._exit(code)

    @client_command
    def load(self, file):
        '''Load and execute an ETB script'''
        if os.path.exists(file):
            self.process_script(file, displayOutput=False)
            print('Finished loading {0}'.format(file))
        else:
            print("No such file '{0}' in directory {1}".format(file, os.path.abspath('.')))

    @client_command
    def echo(self, *args, **kwargs):
        '''Print its arguments'''
        if len(args) == 1:
            print('%s' % args[0])
            return args[0]
        else:
            print(' '.join([str(a) for a in args]))
            return args

    @client_command
    def vars(self, *args):
        '''Print all ETB shell variables'''
        if self._bindings:
            for var, val in self._bindings.iteritems():
                print('{0} = {1}'.format(var, val))
        else:
            print('No ETB shell variables')

    @client_command
    def eval(self, form):
        '''Evaluate a string in Python, print and return the result'''
        val = eval(form)
        print(val)
        return val
        
    ####### File commands

    @file_command
    def put_file(self, src, dst=None):
        '''Put a file on the ETB
        
        Copies the file/dir to the ETB Git working directory, and adds it,
        returning the file handle.
        '''
        fref = ETBClient.put_file(self, src, dst)
        return fref

    @file_command
    def get_file(self, src, dst=None):
        '''Get a file from the ETB'''
        if isinstance(src, basestring):
            src = parser.parse_term(src)
        if isinstance(dst, basestring):
            dst = parser.parse_term(dst)
        return ETBClient.get_file(self, src, dst)

    @file_command
    def get_filehandle(self, path):
        '''Get a handle to a file on the ETB, path is relative'''
        return ETBClient.get_filehandle(self, path)
    
    @file_command
    def lpwd(self):
        '''Print the local (shell) working directory'''
        print(os.getcwd())

    @file_command
    def lcd(self, *args):
        '''Change the local (shell) working directory - e.g. lcd(/home/user)'''
        if len(args) == 1 and isinstance(args[0], basestring): # Fails in Python 3
            os.chdir(args[0])
            self._root_dir = os.getcwd()
        else:
            print('usage: lcd <dir>')

    @file_command
    def lls(self):
        '''List files in the local (shell) working directory'''
        ls = os.listdir(os.getcwd())
        for f in ls:
            if os.path.isdir(f):
                print('%s/' % f)
            else:
                print(f)

    @file_command
    def pwd(self):
        '''Print the current ETB (server) working directory'''
        print(self.config.git_dir)

    # @file_command
    # def cd(self, path):
    #     '''Change the ETB (server) working directory'''
    #     p = os.path.normpath(os.path.join(self.config.git_dir, path))
    #     if self.etb().ls('.' + p):
    #         self.config.git_dir = p
    #     else:
    #         print('Invalid path: %s' % p)

    @etb_command
    def ls(self):
        '''List files in the ETB (server) working directory'''
        output = self.etb().ls('.')
        # output is [dirs, uptodate, outdated, notingit]
        for d in output[0]:
            print(d)
        for f in output[1]:
            print(f)
        for f in output[2]:
            print(f)
        for f in output[3]:
            print(f)

    @etb_command
    def predicates(self, all=False):
        '''List predicates defined in wrappers'''
        if all:
            preds = self.etb().get_all_tool_predicates()
        else:
            preds = self.etb().get_tool_predicates()
        for pstr in sorted(preds):
            print(pstr)

    @etb_command
    def rules(self):
        '''List the rules'''
        rules_dict = terms.loads(self.etb().get_rules())
        for file, rules in rules_dict.iteritems():
            print('Rules from file {0}:\n---------'.format(file))
            for rule in rules:
                print('{0}'.format(rule))

    @etb_command
    def facts(self, all=False):
        '''List the facts'''
        facts_dict = terms.loads(self.etb().get_facts())
        print('facts_dict = {0}'.format(facts_dict))
        for file, facts in facts_dict.iteritems():
            print('Facts from file {0}:\n---------'.format(file))
            for fact in facts:
                print('{0}.'.format(fact))


    ########## Query commands
        
    @query_command
    def query(self, query):
        '''Create a new derivation query'''
        #print('Trying to create query {0}: {1}'.format(query, type(query)))
        qid = self.etb().query(query)
        self._queries[qid] = 'query(%s)' % query
        return qid
    
#    @query_command
#    def prove(self, query):
#        '''Create a new proof query'''
#        qid = self.etb().proof(query)
#        self._queries[qid] = 'prove(%s)' % query
#        return qid

       
#    @query_command
#    def query_view(self, query):
#        '''Display the current state of the query'''
#        dot_file = os.path.abspath('_etb_shell_query.dot')
#        self.etb().query_dot_file(query, dot_file)
#        os.system('dot -Tsvg -o _etb_shell_query.svg %s' % dot_file)
#        self.dot_open('_etb_shell_query.svg')

#    @query_command
#    def query_derivation(self, query):
#        '''Display a derivation produced by the query'''
#        dot_file = os.path.abspath('_etb_shell_derivation.dot')
#        out = self.etb().query_derivation(query, dot_file)
#        if out:
#            os.system('dot -Tsvg -o _etb_shell_derivation.svg %s' % dot_file)
#            self.dot_open('_etb_shell_derivation.svg')
#        else:
#            print('no derivation found for query.')

#    @query_command
#    def query_proof(self, query):
#        '''Display a proof produced by the query'''
#        dot_file = os.path.abspath('_etb_shell_proof.dot')
#        out = self.etb().query_proof(query, dot_file)
#        if out:
#            os.system('dot -Tsvg -o _etb_shell_proof.svg %s' % dot_file)
#            self.dot_open('_etb_shell_proof.svg')
#        else:
#            print('no proof found.')

        
    @query_command
    def queries(self):
        """queries: print the id and status of all the queries on the ETB"""
        q_active = self.etb().active_queries()
        q_done = self.etb().done_queries()
        print('\nQueries')
        print('=======')
        if q_active:
            print('\nActive')
            print('------')
            for q in q_active:
                if q in self._queries:
                    print('  %s    %s' % (q, self._queries[q]))
                else:
                    print('  %s' % q)
        if q_done:
            print('\nCompleted')
            print('---------')
            for q in q_done:
                if q in self._queries:
                    print('  %s    %s' % (q, self._queries[q]))
                else:
                    print('  %s' % q)
        print('')
        
    def translate_answers(self, output):
        # print('translate_answers: output = %s of type %s' % (output, type(output))))
        substs = terms.loads(output)
        return substs
        
    @query_command
    def answers(self, q):
        '''answers($q): print the answers to a query q'''
        output = self.etb().query_answers(q)
        if output:
            answers = terms.loads(output)
            print('\nAnswers for query %s' % q)
            print('==================================================')
            if answers:
                for s in answers:
                    print(s)
            else:
                print('(no answer)')
            print('')
            return self.translate_answers(output)
            

    def print_claims(self, claims, title):
        if len(claims) == 1:
            title = '\n1 Claim {0}'.format(title)
        else:
            title = '\n{1} Claims {0}'.format(title, len(claims))
        subtitle = '=' * (len(title)-1)
        print('%s\n%s' % (title, subtitle))
        for c in claims:
            print('  %s' % c)
        print('')
        

    ## Ian beeds to fix these so that they 1. Replace the old by the new 2. Make sure they get documented by "help"
    ## Stijn: BEGIN checked commands for new engine3
    @query_command
    def claims(self, q):
        '''claims($q): show claims established by query q'''
        cs = terms.loads(self.etb().query_claims(q))
        self.print_claims(cs, 'established by query %s' % q)
        if len(cs) == 1:
            return terms.dumps(cs[0])
        else:
            return [ terms.dumps(c) for c in cs ]
        
    @query_command
    def find_claims(self, pattern, reasons=False):
        """find_claims: Find claims matching pattern"""
        cs = terms.loads(self.etb().find_claims(pattern, reasons))
        return cs

    @query_command
    def all_claims(self):
        """all_claims: Print all the claims established so far

        Prints a table listing all the claims established up to the present.
        This includes past sessions."""
        cs = terms.loads(self.etb().get_all_claims())
        self.print_claims(cs, 'established so far')

    @query_command
    def explanation(self, query):
        """explanation($q): show graphically the status of q"""
        files = self.etb().query_explanation(query)
        if files:
            for f in files: 
                self.dot_open(str("./etb_git/" + f))
        else:
            print('no explanations found.')

    @query_command
    def show(self, query):
        """show($q): show graphically the goal dependencies of q"""
        file = self.etb().query_show_goal_dependencies(query)
        if file:
            self.dot_open(str("./etb_git/" + file ))
        else:
            print('no goal dependencies found.')

    def dot_open(self, file):
        s = platform.system()
        if s == 'Linux':
            cmd = 'xdg-open'
        elif s == 'Darwin':
            cmd = 'open'
        else:
            print('Warning: don''t know how to view file on %s' % s)
            return        
        os.system('%s %s' % (cmd, file))

    @query_command
    def query_wait(self, q):
        '''query_wait($q): wait for the query q to complete and return
           a list of terms.Subst'''
        try:
            self.etb().query_wait(q)
        except KeyboardInterrupt:
            print("Caught KeyboardInterrupt!")
            self.etb().query_wait_interrupt(q)
        output = self.etb().query_answers(q)
        res = self.translate_answers(output)
        if res == []:
            self.errors(q)
        return res

    @query_command
    def errors(self, q):
        '''errors($q): print error claims of query q

        If a query generates an error, e.g., a wrapper throws an exception,
        then a special error claim is created.  This command lists just the
        error claims, if any, for query q.
        '''
        output = self.etb().query_claims(q)
        if output:
            answers = terms.loads(output)
            answers = [ a for a in answers
                        if isinstance(a, terms.Literal)
                        and a.first_symbol() == terms.mk_idconst('error') ]
            if len(answers) > 0:
                print('\nErrors:')
                print('======')
                for a in answers:
                    print(a)
            else:
                print('No errors')

    @etb_command
    def close(self):
        '''Closes a given query'''
        return self.etb().query_close()

    @etb_command
    def complete(self):
        '''Completes a given query'''
        return self.etb().query_complete()

    @etb_command
    def is_completed(self, query):
        '''Checks if query is complete'''
        return self.etb().query_is_completed(query)


    @etb_command
    def wait_for_claims(self, query):
        '''Waits for query to complete'''
        start = time.time()
        self.etb().query_wait(query)
        end = time.time()
        diff = end - start
        print("Claims calculated in ", diff, " seconds...")
        self.claims(query)

       
    ## Stijn: END checked commands for new engine3

#
#
#    @query_command
#    def query_claims(self, q):
#        '''Print the claims established by query'''
#        return self.claims(q)
        
#    @etb_command
#    def query_all_claims(self, q):
#        return self.all_claims(q)



    #### The eval loop

    def find_unescaped(self, s, ch):
        '''Skips over escaped chars in string s'''
        i = 0
        while (i < len(s)):
            if s[i] == ch:
                break
            elif s[i] == '\\':
                i += 2
            elif s[i] in self.BRACKETS:
                i = self.bracketed_arg_end_pos(s, i)+1
            else:
                i += 1
        if i >= len(s):
            i = -1
        return i

    def bracketed_arg_end_pos(self, args, pos=0):
        sch = args[pos]
        ech = self.BRACKETS[sch]
        ctr = 1
        i = pos + 1
        while (i < len(args)):
            # Note we must check for ech first, because of " and ' 
            if args[i] == ech:
                ctr -= 1
                if ctr == 0:
                    break
            elif args[i] == sch:
                ctr += 1
            elif args[i] == '\\':
                # skip over backslash and following char
                i += 1
            i += 1
        if ctr == 0:
            return i
            return arg, rest
        else:
            raise SyntaxError('unbalanced {0} {1}'.format(sch, ech))

    BRACKETS = {'(': ')', '[': ']', '{': '}', '"': '"', "'": "'"}

    def parse_arguments(self, args):
        '''This parses (tokenizes) arguments to a args string, returns substrings

        First strips outer parens, if given, then looks for
        comma-separated set of arguments.  The difficulty here is
        to find useful commas, e.g., foo([1, 2, 3]) should just
        return one argument.  Does this by looking at the first
        non-whitespace character, and if it is a bracketing char,
        it finds the corresponding closing character and returns
        that substring.  If it is not a bracketing char, it simply
        returns up to the next comma, or end of string.
        '''
        if args and args[0] == '(':
            if args[-1] != ')':
                raise SyntaxError(args, 'No closing parentheses')
            args = args[1:-1].strip()
        # We stripped off the outer parens, if any, and the outer whitespace
        pargs = []
        while args:
            if args[0] in self.BRACKETS:
                epos = self.bracketed_arg_end_pos(args, 0)
                arg = args[0:epos+1]
                if epos+1 < len(args):
                    args = args[epos+1:].lstrip()
                else:
                    args = ''
                if args:
                    if args[0] == ',':
                        args = args[1:].lstrip()
                    else:
                        raise SyntaxError('comma expected at {0}'.format(0))
            else:
                idx = self.find_unescaped(args, ',')
                if idx == -1:
                    arg = args
                    args = ''
                else:
                    arg = args[0:idx]
                    args = args[idx+1:]
            targ = ETBShTemplate(arg)
            sarg = targ.substitute(self._bindings)
            pargs.append(sarg)
        return pargs
        
    def parse_cmd(self, command):
        """ Parses an etbsh command line

        If the command starts with *var =*, then the rest is processed, and
        the given local variable is set.  The rest should start with a valid
        command, and the arguments are separated by tokens and parsed.
        """
        has_binding = re.match('([a-zA-Z][a-zA-Z0-9_]*)[ ]*=(.*)$', command)
        if has_binding:
            binding = has_binding.group(1)
            command = has_binding.group(2).strip()
        else:
            binding = None
            command = command.strip()
        mcmd = re.match('([a-zA-Z][a-zA-Z0-9_]*)', command)
        if mcmd is not None:
            cmd = mcmd.group(1)
            if not self.valid_command(cmd):
                raise SyntaxError('Invalid command: {0}'.format(cmd))
            args = command[len(cmd):].lstrip()
        else:
            cmd = None
            args = command
        args = self.parse_arguments(args)
        # print('parse_cmd: ({0}, {1}, {2})'.format(binding, cmd, args))
        return (binding, cmd, args)

    def process(self, command, displayOutput=False): 
        if not command or command[0] == '#':
            return

        (binding, cmd, args) = self.parse_cmd(command)

        #print('\tbinding = %s\n\tcmd = %s\n\targs = %s' % (binding, cmd, args))

        if not cmd:
            arg = args[0] if len(args)==1 else args
            if binding:
                self._bindings[binding] = arg
            else:
                print(arg)
            return arg

        # if cmd == 'prove' or cmd == 'query' and len(args) == 1:
        #     (_, p, pargs) = self.parse_cmd(args[0])
        #     args = [ '%s(%s)' % (p, ', '.join(pargs)) ]

        if cmd in self.client_commands or cmd in self.etb_commands or cmd in self.query_commands or cmd in self.file_commands:
            output = self.__getattribute__(cmd)(*args)
            if binding is not None :
                self._bindings[binding] = output
            if displayOutput:
                print(output)
                
        elif cmd in self.remote_commands:
            try:
                print('process: getting fun for {0}'.format(cmd))
                fun = getattr(self.etb(), cmd, lambda *args: None)
                #print_star_args(*args)
                print('process: calling fun {0} {1}'.format(cmd, args))
                output = fun(*args)
                print('process: after fun')
                if binding is not None :
                    self._bindings[binding] = output
                elif displayOutput:
                    pprint.pprint(output)
            except Exception as e:
                print("Exception occured:", e)
                traceback.print_exc(file=sys.stderr)
        else:
            print('doing query: cmd = {0}'.format(cmd))
            if len(args) > 0:
                output = self.query('%s(%s)' % (cmd, ','.join([ str(a) for a in args])))
            else:
                output = self.query('%s' % cmd)
            if binding is not None :
                self._bindings[binding] = output
            elif displayOutput:
                print(output)
        
    def interact(self):
        global prompted
        while True:
            try:
                #self.read_from_etb()
                # Give ETB a chance to print.
                # sleep(.1)
                prompted = True
                command = raw_input(self.config.prompt_string).strip()
                self.process(command)
                #self.read_from_etb()
            except KeyboardInterrupt:
                print("Interrupted")
            except EOFError:
                self.quit()
            except xmlrpclib.Error as e:
                print("error:", e)
                traceback.print_exc(file=sys.stderr)
            except Exception as e:
                print('Error: {0}'.format(e))
                traceback.print_exc(file=sys.stderr)

    def process_script(self, scripts, displayOutput=False):
        if not isinstance(scripts, list):
            scripts = [scripts]
        for script in scripts:
            with open(script, 'r') as f:
                for line in f:
                    try:
                        command = line.strip('\n').strip()
                        self.process(command, displayOutput)
                    except EOFError:
                        print("")
                    except xmlrpclib.Error as e:
                        print("error:", e)
                    except Exception as e:
                        print("oops!", e)
                        traceback.print_exc(file=sys.stderr)
                    
    def start_etb(self, port, debuglevel):
        # print('Starting etbd, dir = {0}, port = {1}, debuglevel = {2}'.format(dir, port, debuglevel))
        self.etb_stdout_thread = threading.Thread(target=self.read_etb_stdout)
        #self.etb_stderr_thread = threading.Thread(target=self.read_etb_stderr)
        if platform.system() == 'Windows':
            self.etbproc = subprocess.Popen(['etbd', '--port', str(port),
                                             '--debuglevel', str(debuglevel)],
                                            #shell=True,
                                            #cwd=dir,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT)
        else:
            # Passing remaining arguments from argparse, as well as
            # configfile, port, and debuglevel.
            # print('args_for_etb: {0}'.format(self.config.args_for_etb))
            self.etbproc = subprocess.Popen(['etbd', '--port', str(port),
                                             '--debuglevel', debuglevel],
                                            #cwd=dir,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT)
        self.etb_stdout_thread.start()
        #self.etb_stderr_thread.start()

    def kill_etb(self):
        self.etb().stop_etb()
        if platform.system() == 'Windows':
            if self.etbproc is not None and self.etbproc.poll() is None:
                # Need to kill parent process as well - not easy in Windows
                # print('taskkill {0}'.format(self.etbproc.pid))
                #import win32api
                #win32api.TerminateProcess(int(self.etbproc._handle), -1)
                subprocess.call(['taskkill', '/F', '/T', '/PID',
                                 str(self.etbproc.pid)])
        else:
            if self.etbproc is not None and self.etbproc.poll() is None:
                self.etbproc.kill()
        self.etbproc = None

    def blank_current_readline(self):
        # Next line said to be reasonably portable for various Unixes
        (rows,cols) = struct.unpack('hh', fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ,'1234'))

        text_len = len(readline.get_line_buffer())+2

        # ANSI escape sequences (All VT100 except ESC[0G)
        sys.stdout.write('\x1b[2K')                         # Clear current line
        sys.stdout.write('\x1b[1A\x1b[2K'*(text_len/cols))  # Move cursor up and clear line
        sys.stdout.write('\x1b[0G')                         # Move to start of line

    def print_etb_output(self, output):
        global prompted
        if prompted:
            self.blank_current_readline()
        for line in output.splitlines(False):
            if re.search('INFO:', line):
                print(self.config.info_color + line + Style.RESET_ALL)
            elif re.search('WARNING:', line):
                print(self.config.warning_color + line + Style.RESET_ALL)
            elif re.search('ERROR:', line):
                print(self.config.error_color + line + Style.RESET_ALL)
            else:
                print(self.config.text_color + line + Style.RESET_ALL)
        if prompted:
            sys.stdout.write(self.config.prompt_string.translate(None, '\x01\x02')
                             + readline.get_line_buffer())
            sys.stdout.flush()

    def read_etb_stdout(self):
        out = self.etbproc.stdout
        # ofd = out.fileno()
        # ofl = fcntl.fcntl(ofd, fcntl.F_GETFL)
        # fcntl.fcntl(ofd, fcntl.F_SETFL, ofl | os.O_NONBLOCK)
        while self.etbproc is not None:
            output = ''
            try:
                output += out.readline().rstrip()
            except IOError as ioerr:
                pass
            except Exception as e:
                traceback.print_exc(file=sys.stderr)
            if output:
                # out.flush()
                self.print_etb_output(output)
            if self.etbproc is not None and self.etbproc.poll() is not None:
                #print('etbd is not running...exiting')
                #self.quit(1)
                pass

def main():
    try:
        s = ETBShell('ETB Shell')
        # shell argparse parser defined in etbclientlib.py,
        # extended here
        # Read the config file etbsh section
        # Has color schemes currently
        # config_file = s.args().config
        # if os.path.exists(config_file):
        #     cp = ConfigParser.ConfigParser()
        #     cp.read(config_file)
        #     if cp.has_section('etbsh'):
        #         s.config = {k: os.path.expandvars(v)
        #                   for k, v in dict(cp.items('etbsh')).iteritems()}
        #     else:
        #         s.config = {}
        if s.config.clean:
            # if os.path.exists('etb_logic_file'):
            #     print('Removing {0}'.format('etb_logic_file'))
            #     os.remove('etb_logic_file')
            if os.path.exists(s.config.git_dir):
                print('Removing {0}'.format(s.config.git_dir))
                shutil.rmtree(s.config.git_dir)
        s.etbproc = None
        if not s.config.noetb:
            s.start_etb(s.config.port, s.config.debuglevel)
        #time.sleep(2)
        if s.config.batch:
            if s.config.load:
                s.process(s.config.load, displayOutput=False)
            else:
                for line in sys.stdin:
                    s.process(line, displayOutput=False)
        elif s.config.load:
            s.process_script(s.config.load)
            s.interact()
        else:
            s.interact()

    except (KeyboardInterrupt):
        s._history.save()
        print('') # make sure we get a newline in there
    sys.exit(0)

if __name__ == '__main__':
    main()
