
""" ETB state for interpreted predicates

The global state for interpreted predicates. It stores tool wrappers,
but also which goals have been interpreted.

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

import os, threading, sys, traceback
import terms, wrapper
import logging, inspect

from datalog import model

class InterpretState(object):
    """
    The state for interpretation of predicates.

    It depends on an ETB instance to add claims after a predicate has
    been interpreted, and because some tool wrappers may need
    this ETB instance.
    """

    def __init__(self, etb):
        "initializes the state"
        self.log = logging.getLogger('etb.interpret_state')
        self.etb = etb

        # handler that interpret predicates
        self._handlers = {}
        self._being_interpreted = {}

        # predicates already interpreted somewhere -> set of result
        self.results = {}

        # concurrency mechanisms
        self._rlock = threading.RLock()
        
    def __enter__(self):
        self._rlock.acquire()

    def __exit__(self, t, v, tb):
        self._rlock.release()

    def __repr__(self):
        return '  Interpreted predicates:\n' + '\n'.join(
            ['    ' + str(k) +
                ('(*)' if k.is_volatile() else '')
                for k in self._handlers])

    def _import_wrapper(self, wrapper_name):
        "import one wrapper and register it"
        try:
            mod = __import__(wrapper_name, fromlist=['register'])
            self.log.info("Registering tool wrapper {0}".format(wrapper_name))
            # call the "register" function of the module with the ETB instance as argument
            getattr(mod, 'register')(self.etb)
        except Exception as e:
            self.log.error("error while importing wrapper {0}: {1}" . \
                           format(wrapper_name, e))
            traceback.print_exc()

    def _get_handler(self, goal, default=None):
        """Get the handler that should be used to interpret
        the given goal."""
        symbol = goal.first_symbol()
        handler = self._handlers.get(symbol, default)
        return handler

    def _validate_fileref(self, arg, pred, argname):
        if arg.is_ground():
            try:
                fileref = terms.get_fileref(arg)
                if fileref is None:
                    raise TypeError('validating fileref: None returned for {0}: {1}'
                                    .format(arg, type(arg)))
            except Exception as e:
                self.log.debug('validate_fileref error: {0}'.format(e))
                raise Exception("Invalid file reference: '{0}' for arg '{1}' of interpreted predicate '{2}'".format(arg, argname, pred))
            if not self.etb.git.is_local(fileref):
                self.etb.get_file_from_somewhere(fileref)
            return fileref
        else:
            return arg

    def _validate_handle(self, arg):
        if arg.is_ground():
            try:
                handle = { 'etb' : str(arg.get_args()[terms.mk_stringconst('etb')]),
                           'tool' : str(arg.get_args()[terms.mk_stringconst('tool')]),
                           'session' : arg.get_args()[terms.mk_stringconst('session')],
                           'timestamp':arg.get_args()[terms.mk_stringconst('timestamp')]}
            except Exception as e :
                self.log.error('Invalid handle: %s' % arg)
                raise e
            return handle
        else:
            return arg


    def is_valid(self, goal):
        """
        Checks that goal predicate is defined by wrappers, and the args
        satisfy the arity and mode constraint for the corresponding wrapper. 
        """
        try:
            if goal is not None:
                pred = goal.first_symbol()
                val = str(pred.val)
                if val in self.predicates():
                    self._validate_args(goal)
            return True
        except Exception as e:
            if goal is not None:
                handler = self._get_handler(goal)
                if handler is not None:
                    cls = handler.im_class
                    mod = cls.__module__
                    self.log.error('Goal %s is interpreted (in wrapper %s) but invalid with error: "%s"'
                                   % (goal, mod, e))
                else:
                    self.log.error('Goal %s is interpreted but invalid with error: "%s"'
                                   % (goal, e))
            #traceback.print_exc()
            return False

    def _validate_args(self, goal):
        pred = goal.first_symbol()
        argspecstr = self.predicates()[str(pred.val)]
        argspecs = wrapper.ArgSpec.parse(argspecstr)

        goal_args = goal.get_args()
        
        if len(argspecs) != len(goal_args):
            self.log.error('Invalid number of arguments')
            raise Exception('Invalid number of arguments to %s' % pred)

        args = []
        for argspec, arg in zip(argspecs,goal_args):
            if arg.is_var():
                if argspec.mode == '+':
                    error_string = 'Argument %s should be a value, not variable "%s"' % (argspec, arg)
                    self.log.error(error_string)
                    raise TypeError(error_string)
                else:
                    args.append(arg)
            else:
                if argspec.mode == '-':
                    error_string = 'Argument %s should be a variable, not "%s"' % (argspec, arg)
                    self.log.error(error_string)
                    raise TypeError(error_string)

                elif argspec.kind == 'file':
                    args.append(self._validate_fileref(arg, pred, argspec.name))

                # files is a list of filerefs or (recursively) files
                elif argspec.kind == 'files':
                    args.append(self._validate_files_args(arg, pred, argspec.name))
                
                elif argspec.kind == 'handle':
                    args.append(self._validate_handle(arg))

                else :
                    args.append(arg)

        return args

    def _validate_files_args(self, arg, pred, argname):
        if arg.is_ground():
            self.log.debug('files: validating arg {0} {1}'.format(arg, type(arg)))
            if arg.is_array():
                arglist = arg.get_args()
                return [ self._validate_files_args(a, pred, argname) for a in arglist ]
            else:
                return self._validate_fileref(arg, pred, argname)

    def _interpret(self, goal, internal_goal, handler):
        """
        Actually interpret the goal using the handler. Results are
        added to the engine. The goal will be interpreted only if
        it is volatile or has not yet been interpreted.
        """
        self.log.debug('Interpreter: %s', goal.first_symbol())

        if goal in self.results and not goal.first_symbol().is_volatile():
            claims = tuple(self.results[goal])
            # Need this, or interpreted goal never completed
            self.etb.engine.add_claims(claims)
            self.add_results(goal, claims)
            # This is ill-formed
            # self.etb.engine.inference_state.logical_state.db_move_stuck_goal_to_goal(goal)
            return
        try:
            args = self._validate_args(goal)
        except Exception as e:
            self.log.info('e = %s' % e)
            self.add_results(goal, [])
            return

        try:
            self.log.debug('Interpreting predicate {0}({1})'.format(goal.first_symbol(), args))

            # This is where wrappers are invoked
            output = handler(*args)

        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            self.log.error('While interpreting {0}, error {1}'.format(goal, e))
            output = { 'claims' : 'error("%s", "%s")' % (goal.first_symbol(), e)}

        if output is None:
            self.log.error('Nothing returned for goal {0}'.format(goal))
            self.log.error('Did you forget to return an output?')
            output = { 'claims' : 'error("%s", "%s")' % 
                       (goal.first_symbol(), 'Nothing returned for goal')}

        self.log.debug('interpret: {0}: {1}'.format(output, type(output)))

        if isinstance(output, wrapper.Result):  # includes Errors
            self._handle_output_new_api(goal, internal_goal, output)
        elif isinstance(output, list) or isinstance(output, dict):
            self._process_output(goal, output)
        else:
            self.log.error('ETB wrapper returned {0}: only return (lists of) substitutions'.format(type(output)))
            raise Exception('ETB wrappers only return (lists of) substitutions')

    def _handle_output_new_api(self, goal, internal_goal, output):
        self.log.debug('_handle_output_new_api: output {0}'.format(output))
        rules = output.get_pending_rules(goal)
        self.log.debug('_handle_output_new_api: rules {0}'.format(rules))
        self.etb.engine.inference_state.logical_state.db_move_stuck_goal_to_goal(internal_goal)
        if not rules:
            claims = output.get_claims(goal)
            self.log.debug('_handle_output_new_api: claims {0}'.format(claims))
            if not claims:
                self.etb.engine.push_no_solutions(goal)
            else: 
                self.log.debug('_handle_output_new_api: adding claims {0}'.format(claims))
                if isinstance(output, wrapper.Errors):
                    self.etb.engine.add_errors(goal, claims)
                    self.etb.engine.push_no_solutions(goal)
                else:
                    self.etb.engine.add_claims(claims)
            self.add_results(goal, claims)
        else:
            for r in rules : 
                self.log.debug('Adding new rule: {0} with goal {1}'.format(r, goal))
                self.etb.engine.add_pending_rule(r, goal, internal_goal)
            self.add_results(goal, [])

    def _process_output(self, goal, output):
        self.log.debug('_process_output: goal = %s output = %s' % (goal, output))
        if not output:
            self.etb.engine.push_no_solutions(goal)
        else:
            for obj in output:
                self.log.debug('_process_output: obj %s of type %s' % (obj, type(obj)))
                if isinstance(obj, terms.Claim):
                    pred = obj.literal.get_pred()
                    if pred == terms.IdConst('error'):
                        self.etb.engine.add_errors(goal, [obj])
                    else:
                        claim = terms.Claim(obj.literal, obj.reason)
                        self.etb.engine.add_claim(claim)
                else:
                    if isinstance(obj, dict):
                        obj = terms.Subst(obj)
                        fact = obj(goal)
                        self.log.debug('fact: {0}'.format(fact))
                        # we add the ground goal to the claims of the engine
                        claim = terms.Claim(fact, model.create_external_explanation())
                        self.etb.engine.add_claim(claim)

    #  --------- API -------
    
    def reset(self):
        """Reset the state of the component."""
        with self._rlock:
            self.results.clear()

    # result cacheing
    def add_results(self, goal, claims):
        """
        Update the state: goal -> claims is asserted (maybe from a
        remote node). If goal already has registered results, this
        will do nothing.
        """
        if not goal.first_symbol().is_volatile() and len(claims) > 0:
            self.results[goal] = list(claims)

    def add_goal_results(self, goal_results):
        """
        Add a set of goal results (e.g., from logic_file)
        """
        self.results = goal_results

    def get_goal_results(self):
        """
        Returns the (internal) goal to (internal) claims mapping
        """
        return self.results

    def add_tool(self, tool):
        """Add the handlers contained in the tool to self."""
        for name, obj in inspect.getmembers(tool):
            # _argspec and _predicate_name are set by Tool.predicate decorator
            if getattr(obj, '_argspec', False):
                name = getattr(obj, '_predicate_name', name)
                symbol = terms.IdConst(name)
                self.set_handler(symbol, obj)
                if getattr(obj, '_volatile', False):
                    symbol.set_volatile()

    def set_handler(self, symbol, handler):
        """Add a handler for the given symbol"""
        assert symbol.is_const(), 'The symbol %s is not constant; set_handler unhappy' % symbol
        with self:
            assert symbol not in self._handlers, 'symbol %s already defined, set_handler unhappy' % symbol
            self._handlers[symbol] = handler
            self.log.debug('  predicate %s now interpreted by \'%s\'',
                              symbol, handler)

    def load_wrappers(self):
        """
        Load all wrappers from the 'wrappers' directory, and add the
        handlers they contain to self.

        We try to load all .py, except if they start with '__'.
        
        
        .. todo::
            Not loading rules yet!

        """
        # First load builtins
        self.log.info('Loading builtin wrappers')
        self._import_wrapper('etb.wrappers.builtins')
        wrapper_dir = os.path.abspath('wrappers')
        if os.path.isdir(wrapper_dir):
            self.log.info("Loading wrappers from directory '{0}'"
                          .format(wrapper_dir))
            sys.path.insert(0,wrapper_dir)
            files = os.listdir(wrapper_dir)
            for f in files:
                if f.startswith('__') or not f.endswith('.py'):
                    continue
                mod_name, _ = os.path.splitext(f)
                self._import_wrapper(mod_name)
        else:
            self.log.info('No wrapper directory specified')

    def is_interpreted(self, goal):
        """Checks whether the goal is interpreted."""
        assert isinstance(goal, terms.Literal), 'is_interpreted: goal {0}: {1} not a Literal'.format(goal, type(goal))
        self.log.debug('is_interpreted: %s', goal)
        pred = goal.first_symbol()
        
        is_interp = pred in self._handlers or \
                    self.etb.networking.neighbors_able_to_interpret(pred) or \
                    self.etb.networking.links_able_to_interpret(pred)
        if not is_interp:
            self.log.debug('The predicate for goal {0} is not currently interpreted'.format(goal))
        return is_interp

    def predicates(self):
        """Dict of predicate name -> argspec of the predicate"""
        preds = {}
        with self:
            for k,v in self._handlers.iteritems():
                preds[str(k.val)] = v._argspec
        return preds
    
    def has_been_interpreted(self, goal):
        """Checks whether this goal has already been interpreted."""
        if goal.first_symbol().is_volatile():
            return False
        return goal in self.results

    def handler_is_async(self, goal):
        method = self._get_handler(goal)
        return getattr(method, '_async', True)

    def interpret_goal_somewhere(self, goal, internal_goal, engine):
        """
        The engine doesn't know about the etb node, so we pass on the request for it.
        The engine argument is ignored.
        """
        self.etb.interpret_goal_somewhere(goal, internal_goal)

    def interpret(self, goal, internal_goal, sync=False):
        """Schedule goal to be interpreted, either now or later."""
        self.log.debug('interpreted: %s', goal)
        handler = self._get_handler(goal)
        # This check is in _interpret
        if False: #self.has_been_interpreted(goal):
            self.log.debug('interpret: has_been_interpreted')
            claims = tuple(self.results[goal])
            self.add_results(goal, claims)
        else:
            # the interpret_state should unstuck the below again: make it stuck
            # before you interpret!
            # First need the internal form
            # internal_goal = self.etb.engine.term_factory.mk_literal(goal)
            # self.log.info('interpret: add_stuck_goal {0}'.format(internal_goal))
            # self.etb.engine.inference_state.logical_state.db_add_stuck_goal(internal_goal)
            
            if self.handler_is_async(goal):
                def task(etb, goal=goal, handler=handler):
                    self._interpret(goal, internal_goal, handler)
                self.etb.long_pool.schedule(task)
            else:
                self._interpret(goal, internal_goal, handler)

    def interpreted_predicates(self):
        """Fresh list of which predicates (symbols) are interpreted
        by this component."""
        with self:
            preds = []
            for name, handler in self._handlers.iteritems():
                cls = handler.im_class
                mod = cls.__module__
                item = '{0}({1}): {2}'.format(name, handler._argspec, mod)
                preds.append(item)
            #ans = self._handlers.keys()
            return preds
    
