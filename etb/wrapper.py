""" Wrapper API

This module defines an API for writing tool wrappers.

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

import os, subprocess
import inspect
import terms
import copy
import parser
import logging

import pyparsing

class ArgSpec(object):
    """
    Defines the signature of predicates, as indicated in the argument
    to the Tool.predicate decorator.
    """
    
    def __init__(self, mode, name, kind):
        self.mode = mode
        self.name = name
        self.kind = kind
        
    def __repr__(self):
        return '{0}{1}:{2}' . format(self.mode, self.name, self.kind)

    @staticmethod
    def fromParser(_, toks):
        return ArgSpec(*toks.asList())

    @staticmethod
    def parse(s):
        name = pyparsing.Word(pyparsing.alphas,
                              pyparsing.alphanums+'!#$&*+-/;<>@\\^_`|')
        argmode = pyparsing.oneOf(['', '+', '-'])
        argkind = pyparsing.oneOf(['file', 'files', 'value', 'handle'])
        argspec = argmode + name + pyparsing.Literal(':').suppress() + argkind
        argspec.setParseAction(ArgSpec.fromParser)
        argspecs = pyparsing.delimitedList(argspec)
        return argspecs.parseString(s).asList()

class ETBClaims(object):
    """
    Interface to the claims table for wrappers.
    """
    def __init__(self, etb):
        self._etb = etb

    def find_claims(self, pattern, reasons=False):
        return self._etb.find_claims(pattern, reasons)

class ETBFS(object):
    """
    Interface to the git repository for wrappers.
    """

    def __init__(self, etb):
        self._etb = etb

    def put_file(self, src, dst=None):
        self._etb.log.debug('put_file src = {0}: {1}, file_path = {2}'
                            .format(src, type(src),
                                    self._etb.config.etb_file_path))
        if dst is None:
            if os.path.isabs(src):
                self._etb.log.error('put_file(<src>) -- <src> should be a relative path.')
                raise
            else:
                dst = src
                if not os.path.exists(src):
                    for p in self._etb.config.etb_file_path:
                        nsrc = os.path.join(p, src)
                        self._etb.log.debug('put_file trying {0}'.format(nsrc))
                        if os.path.exists(nsrc):
                            self._etb.log.debug('put_file found {0}'.format(nsrc))
                            src = nsrc
                            break
                        nsrc = None
                    if nsrc is None:
                        self._etb.log.error('put_file: src {0} not found'.format(src))
                        raise
                    else:
                        src = nsrc
                else:
                    src = os.path.abspath(src)
        return terms.Map(self._etb.git.put(src, dst))

class Tool(object):
    """
    Any tool to interpret predicates. Each predicate the tool can deal
    with should be a method with the same name as the predicate
    itself, annotated with @Tool.predicate(argspec).

    Calling the method should return a list of substitutions that are
    answers to the goal, and bind all the variables in it.

    the async() method should return False if the tool is very fast to
    call, True otherwise, in which case it is run in a background
    thread.
    """

    def __init__(self, etb):
        """Initialize the Tool with the given ETB instance.
        """
        self.etb = etb
        self.log = logging.getLogger('etb.wrapper')
        self.fs = ETBFS(etb)
        self.clms = ETBClaims(etb)
        self.path = os.path.abspath(inspect.getmodule(self).__file__) # pylint: disable=E1103

    def __repr__(self):
        return self.__class__.__name__

    @staticmethod
    def predicate(argspec, name=None):
        """Decorator which, given an instance, exports the function.
        """
        def decorator(fun):
            fun._argspec = argspec
            if name is not None:
                fun._predicate_name = name
            return fun
        return decorator

    @staticmethod
    def volatile(fun):
        """Mark the function (hence the predicate) as volatile."""
        fun._volatile = True
        return fun

    @staticmethod
    def sync(fun):
        """Mark the function as sync, i.e. it will be interpreted
        directly.
        """
        fun._async = False
        return fun

    @staticmethod
    def extern(fun):
        """Mark the function as external, i.e., it will be available
        to remote ETB nodes.
        """
        fun._extern = True
        return fun

    def fail(self, reason):
        """Report of failure of interpretation of the given goal,
        e.g. because of wrong types, bad instantiation scheme,
        non present tool, etc.
        """
        msg = "in tool wrapper {0}: {1}".format(self, reason)
        raise Exception(msg)

    def bindResult(self, result, resultValue, current=None) :
        """bind result to resultValue"""
        if current is None:
            current = {}
        if current == []:
            return []
        result = terms.mk_var(result)
        resultValue = terms.mk_term(resultValue)
        if result.is_var():
            current[result] = resultValue
            return current
        elif result == resultValue :
            return current
        else :
            return []

class BatchTool(Tool) :
    """
    Batch tool.
    """

    def callTool(self, *args, **kwargs) :
        try :
            p = subprocess.Popen(args,
                                 shell=False,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 env=kwargs.get('env', None))
            (out, err) = p.communicate()
            return (p.returncode, out, err)
        except Exception as msg:
            self.log.error(msg)
            self.fail('failed to start the external tool %s' % args[0])

    def parseResult(self, (stdout, _stderr)) :
        return stdout

    def run(self, result, *args) :
        """
        Run an external command, parse the result, and binds it to the
        result variable, or check that we get the result we are
        expecting.
        """
        try:
            (ret, out, err) = self.callTool(*args)
            if ret != 0:
                self.log.error(err)
                return  Errors(self,  [ err ] )
            parsed = self.parseResult((out, err))
            if result.is_var():
                return Substitutions(self, [ self.bindResult(result, parsed) ])
            elif result.val == parsed:
                return Success(self)
            else:
                return Failure(self)
        except Exception as msg :
            self.log.exception('wrapper.run: exception msg {0}'.format(str(msg)))
            return Errors(self,  [ str(msg) ] ) 

class InteractiveTool(Tool):
    """
    Interactive tools.

    The tool maintains a map of active session id and the
    corresponding process/timestamp session entry.
    """
    def __init__(self, etb):
        """
        Initially, there are no sessions and the next id is 0
        """
        print('Initializing InteractiveTool')
        Tool.__init__(self, etb)
        self._sessions = {}
        self._id = 0

    def session(self, sid) :
        """session(sid) returns the session for sid, if it is defined,
           and an error, otherwise.
        """
        sid = int(sid)
        if sid in self._sessions :
            return self._sessions[sid]
        else :
            self.fail('Error: invalid handle')

    def add_session(self, tool, s_entry) :
        """
        A new session s_entry is added with tool and timestamp
        """
        new_id = self._id
        self.log.debug('add_session: new_id {0}'.format(new_id))
        self._sessions[new_id] = s_entry
        self._id = self._id + 1
        retval = { 'etb': self.etb.id,
                 'tool': tool,
                 'session': new_id,
                 'timestamp': 0}
        print('add_session: retval: %s' % retval)
        return retval

    def del_session(self, sid):
        """
        Deleting a session entry
        """
        print('In del_session')
        if sid in self._sessions:
            print('before del')
            self._sessions.pop(sid)
            print('deleted session number %s' % sid)
        else:
            self.fail('Error: invalid handle')
    
    def session_id(self, session):
        """
        Check the validity (non-staleness) of a session handle against the session table.
        """
        print('session_id: session: %s' % session)
	print('sessions: %s' % self._sessions)
        sid = session['session']
        print('sid: %s' % sid)
        if int(sid.val) in self._sessions:
            s_entry = self._sessions[int(sid.val)]
            print('session_id: s_entry: %s' % s_entry)
            if (terms.StringConst(s_entry['timestamp']) == session['timestamp']):
                return int(sid.val)
            else :
                self.fail('Error: invalid handle') #because timestamp is wrong
        else :
            self.fail('Error: invalid handle') # no such session

    def tick(self, sessionIn):
        """
        Adds a tick to the time stamp of sessionIn and the corresponding s_entry in _sessions.
        """
        sid = self.session_id(sessionIn)
        s_entry = self._sessions[sid]
        s_entry['timestamp'] += 1
        sessionOut = copy.copy(sessionIn)
        sessionOut['timestamp'] = s_entry['timestamp']
        return sessionOut


class SubprocessTool(InteractiveTool):
    """
    Subprocess.

    Encapsulates an interactive tool that is invoked as a subprocess with a prompt.
    """

    def connect(self, toolname, *args):
        self.log.debug('connect toolname {0}, {1}'.format(toolname, args))
        call = list(args)
        self.log.debug('connect call {0}'.format(call))
        call.insert(0, toolname)
        self.log.debug('connect call {0}'.format(call))
        process = subprocess.Popen(call,
                                   shell=False,
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE)
        session = self.add_session(self, {'process': process, 'timestamp': 0}, toolname)
        return session

    def write(self, session, str, noRead=False):
        if self.check_valid(session):
            s_entry = self.session(session['session'])
            process = s_entry['process']
            process.write(str)
            if noRead:
                return ''
            else:
                return self.read(session)
        else :
            self.fail('Error:invalid handle')

    def read(self, session):
        "Reading the output from a subprocess.  No check for session validity."
        s_entry = self.session(session['session'])
        process = s_entry['process']
        out = ''
        tmpread = process.read
        while not self.parse_stop(tmpread):
            error = self.parse_error(tmpread)
            if error is None:
                out = out + tmpread + '\n'
                tmpread = process.read
            else:
                self.fail(error)
        return self.parse_output(out)

    def parse_stop(self, s):
        "This will be redefined by the actual tool subclass"
        return s == ''

    def parse_error(self, _s):
        "This will be redefined by the actual tool subclass"
        return None

    def parse_output(self, s):
        "This will be redefined by the actual tool subclass"
        return s


#classes to wrap wrapper results in (to spot old API returns etc)


class Result(object):
    """
    The parent class of all results returned by a wrapper.

    This little hiearchy is to isolate the new wrapper API and 
    enable easy error detection. If a wrapper returns something 
    that does not subclass this class, then presumably it is using
    the old API and needs to be updated.

    Also no wrapper should return this class, but rather a specialized subclass.

    """
    def __init__(self, tool):
        self.tool = tool
        self.etb = tool.etb
        self.log = tool.log

    
    def get_claims(self, goal):
        """
        Old engine fail safe method
        """
        self.log.warning('Base result method called for goal: %s' % goal)
        return []

    def get_pending_rules(self, goal):
        """
        New engine fail safe method
        """
        self.log.warning('Base result method called for goal: %s' % goal)
        return []

        
class Success(Result):

    def __init__(self, tool):
        Result.__init__(self, tool)

    def get_claims(self, goal):
        return [terms.InterpretedClaim(goal, reason=goal)]

    def get_pending_rules(self, goal):
        """ Success should also return a pending clause. 
        """
        pending_rules = [terms.InferenceRule(goal, [], temp=True)]
        return pending_rules



class Failure(Result):

    def __init__(self, tool):
        Result.__init__(self, tool)

    def get_claims(self, goal):
        return []

    def get_pending_rules(self, goal):
        return []


class Errors(Result):
    """
    Used to produce error claims, or whatever we end up wanting in this case.

    The argument 'reasons' should be a list of strings. Not really sure why we would
    need more than one, but ...

    """ 
    def __init__(self, tool, reasons):
        Result.__init__(self, tool)
        self.reasons = []
        if not isinstance(reasons, list):
            reasons = [reasons]
        for r in reasons:
            if isinstance(r, basestring):
                err = 'error("{0}", "{1}")'.format(repr(tool),  r)
                self.log.info('Errors: err {0}: {1}'.format(err, type(err)))
                lit = parser.parse_literal(err)
                self.reasons.append(lit)
            else:
                self.log.warning('Unhandled error argument: %s' % r)
                self.log.warning('typeof(r) = %s' % type(r))
   
    def get_claims(self, goal):
        claims = []
        self.log.debug('wrapper.get_claims: reasons {0}: {1}'
                          .format(self.reasons, type(self.reasons)))
        for error in self.reasons:
            claims.append(terms.InterpretedClaim(error, reason=goal))
        return claims

    def get_pending_rules(self, goal):
        return []

class Substitutions(Result):
    """
    The simple common case when the wrapper returns a list of substitutions

    """
    def __init__(self, tool, substitutions):
        Result.__init__(self, tool)
        self.log.debug('Substitutions working on %s' % substitutions)
        substitution_list = []
        if isinstance(substitutions, list) or isinstance(substitutions, tuple) :
            for obj in substitutions:
                self.log.debug('Substitutions: obj =  %s : %s' % (obj, type(obj)))
                if isinstance(obj, dict):
                    obj = terms.Subst(obj)
                if isinstance(obj, terms.Subst):
                    substitution_list.append(obj)
                else:
                    msg = 'Substitutions: {0}:{1} is not a dict or a Subst'.format(obj, type(obj))
                    self.log.error(msg)
                    raise Exception(msg)
        elif isinstance(substitutions, dict):
            self.log.debug('Substitutions: obj =  %s : %s' % (substitutions, type(substitutions)))
            substitution_list.append(terms.Subst(substitutions))
        elif isinstance(substitutions, terms.Subst):
            self.log.debug('Substitutions: obj =  %s : %s' % (substitutions, type(substitutions)))
            substitution_list.append(substitutions)
        else:
            msg = 'Substitutions: {0}:{1} is not a tuple, list, or dict'.format(substitutions,type(substitutions))
            self.log.warning(msg)
            raise Exception(msg)
        assert isinstance(substitution_list, list)
        assert all(isinstance(l, terms.Subst) for l in substitution_list)
        self.substitutions = substitution_list
    def __repr__(self):
        return 'Substitutions({0})'.format(self.substitutions)
 
    def get_claims(self, goal):
        claims = []
        for s in self.substitutions:
            fact = s(goal)
            reason = s(goal)
            self.etb.fetch_support(s)
            claims.append(terms.InterpretedClaim(fact, reason=reason))
        return claims
 
    def get_pending_rules(self, goal):
        """ Added this for Substitutions so they behave like lemmata with empty bodies. 
        """
        pending_rules = []
        adder = lambda s: pending_rules.append(terms.InferenceRule(s(goal), [], temp=True))
        map(adder, self.substitutions)
        return pending_rules

def parselemma(q): 
    if isinstance(q, terms.Literal):
        return q
    else:
        t = parser.parse(q, 'literal')
        assert isinstance(t, terms.Literal), '{0} is not a Literal'.format(t)
        return t

def parselemmata(l):
    if isinstance(l, list):
        return [ parselemma(q) for q in l ] 
    else:
        return []

# class Queries(Substitutions):
#     """
#     The old api way of returning queries. Note that returning queries
#     precludes returning claims. From a goal G we can return

#     Queries(tool, slist, qlist)

#     where:

#     slist should be a substitution list:
    
#     [s0, s1, ... , sN]
    
#     - the substitution can either be a dict or a terms.Subst object, whichever is more 
#     convenient.

#     qlist should be a list of terms: 

#     [q0, q1, ... , qM]
    
#     - terms can either be string representations, or actual term objects, whichever is more 
#     convenient.
    
#     This has the effect of adding the N x M rules:

#     si(G) :- si(qj)
    
#     for each i in 0 ... N and j in 0 ... M.
    
#     """
#     def __init__(self, tool, substitutions, queries):
#         Substitutions.__init__(self, tool, substitutions)
#         self.queries = queries
        
#     def get_claims(self, goal):
#         return []
 
#     def get_pending_rules(self, goal):
#         pending_rules = []
#         for q in self.queries :
#             q = parselemma(q)
#             for s in self.substitutions :
#                 pending_rules.append(terms.InferenceRule(s(goal), [s(q)], temp=True))
#         return pending_rules
     


class Lemmata(Substitutions):

    def __init__(self, tool, substitutions, lemmatas):
        """
        Create a Lemmata instance.  From a goal G we can return
        ``Lemmata(tool, substitutions, lemmatas)``

        :parameters:
            - `substitutions`: a list of :class:`etb.terms.Subst` substitutions,
              or a list of dicts, which will be converted to substitution terms
            - `lemmatas`: a list of lemmata ``[l0, l1, ... , lN]``, where:
                - the lists should be the same length
                - each ``li`` is itself a list: ``[qi0, qi1, ... qiM]`` where each
                  ``qi0`` is either a :class:`etb.terms.Term` or a string.
        
        This has the effect of adding the N rules:

        ``si(G) :- si(q0i), ..., si(qMi)``

        to the system for i in 0 ... N.
    """
        Substitutions.__init__(self, tool, substitutions)
        if not isinstance(lemmatas, list):
            raise Exception('Lemmata: lemmatas MUST be a list')
        if isinstance(substitutions, dict):
            lemmata_list = [parselemmata(lemmatas)]
        else:
            if len(substitutions) != len(lemmatas):
                raise Exception('Lemmata: substitutions and lemmatas should be of the same length')
            lemmata_list = [parselemmata(l) for l in lemmatas]
        assert isinstance(lemmata_list, list)
        assert all(isinstance(l, list) for l in lemmata_list)
        assert all((isinstance(t, terms.Term) for t in l) for l in lemmata_list)
        self.lemmatas = lemmata_list
        
    def get_claims(self, goal):
        return []
 
    def get_pending_rules(self, goal):
        pending_rules = []
        adder = lambda s, ll: pending_rules.append(terms.InferenceRule(s(goal), [ s(q) for q in ll], temp=True))
        map(adder, self.substitutions, self.lemmatas)
        return pending_rules
