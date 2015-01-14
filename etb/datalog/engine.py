""" Datalog Engine Interface

This module and in particular the class :class:`etb.datalog.engine.Engine` is
the interface to the Datalog engine. This should be the only access point to
the engine from the :mod:`etb.etb` module.

For testing purposes, we also include the class
:class:`etb.datalog.engine.InterpretStateLessThan`. The ETB is responsible for
initializing the engine with an appropriate `InterpretState` (**not** the one
defined in this module).

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

# from the ETB:
from etb import terms
from etb import parser

# the datalog stuff
import model
import inference
import externals
import graph

# the dot generation
import pydot
import uuid

# logging
import logging

# saving state
import bz2
import os.path


class Engine(object):
    def __init__(self, interpret_state):
        """
        Create an Engine object using a `interpret_state` (see
        :class:`etb.interpret_state.InterpretState`).

        :parameters:
            - `interpret_state`: an instance of
              :class:`etb.interpret_state.InterpretState`. The engine will use
              `interpret_state` in 2 ways (and those are the only requirements
              on `interpret_state`):
        
              - It checks whether a predicate is intepreted (should be
                treated externally) using
                :func:`etb.interpret_state.InterpretState.is_interpreted`.
              - It asks the `interpret_state` to take care of solving a
                particular goal using
                :func:`etb.interpret_state.InterpretState.interpret`.

        :members:

            - `self.log`: the object used for logging Engine related messages
            - `self.facts`: the facts read from rules files, so they can be
               displayed by clients
            - `self.rules`: the rules read from rules files, so they can be
               displayed by clients
            - `self.term_factory`: a :class:`etb.datalog.model.TermFactory`
              object. This object takes care of bridging external
              :class:`etb.term` objects to the internal data format used by the
              Datalog engine (based on lists of integers).
            - `self.inference_state`: an
              :class:`etb.datalog.inference.Inference` object responsible for
              the reasoning with the internal structures. It gets initialized
              with :class:`etb.datalog.model.LogicalState`, `interpret_state`,
              `self.term_factory` and `self`. The `LogicalState` keeps track of
              rules, pending rules, claims, and dependencies. The
              `Inference` manipulates that state.
            - `self.SLOW_MODE`: is by default `False`; when `True` it causes
              the inferencing to pause between each step and to send extra info
              to the logger
            - `self.CLOSE_DURING_INFERENCING`: is by default `False`; when
              `True` the engine attempts to close each goal using
              :func:`etb.datalog.graph.DependencyGraph.close`. This is very
              expensive and it is advised any consumer of the Engine explicitly
              sends explicit requests to :func:`etb.datalog.engine.Engine.close` and
              :func:`etb.datalog.engine.Engine.complete`.

        .. note::

            We initialize the `Inference` with the engine object
            `self`. Indeed, reasoning sends the engine object to the
            `InterpretState` when the latter is responsible for solving a
            particular interpreted/external goal. The `InterpretState` thus
            can choose when to for example add claims to the Engine that
            requested that. As such, we decouple internal reasoning from
            how an `InterpretState` obtains its conclusions.

        A simple example of initializing an `Engine` using the dummy
        :class:`etb.datalog.engine.InterpretStateLessThan`: ::

            import engine

            interpret_state = engine.InterpretStateLessThan()
            eng = engine.Engine(interpret_state)

        """

        self.log = logging.getLogger('etb.datalog.engine')

        self.facts = {}
        self.rules = {}

        # The term_factory is used to figure out translations between
        # terms and the internal data structure.
        self.term_factory = model.TermFactory()

        # Note that we give this Engine as an argument to the
        # `inference_state`.
        self.inference_state = inference.Inference(model.LogicalState(self),
                                                   interpret_state,
                                                   self.term_factory,
                                                   self)
        self.log.debug('Engine Created')

        self.SLOW_MODE = False
        self.CLOSE_DURING_INFERENCING = False

        
    def add_claim(self, claim, quiet=False):
        """
        Adds a claim to the engine by transforming the claim to its internal
        representation (using :func:`etb.datalog.model.TermFactory.mk_literal`)
        and subsequently (using
        :func:`etb.datalog.inference.Inference.add_claim`) adding the
        internal claim for consideration by the inference algorithm.

        :parameters:
            - `claim`: is an instance of :class:`etb.terms.Claim`.

        :returntype:
            `None`

        For example: ::

            import engine
            import terms
            import model

            interpret_state = engine.InterpretStateLessThan()
            engine = engine.Engine(interpret_state)
            literal = terms.mk_apply("p", ["a", "b"])
            claim = terms.Claim(literal, model.create_external_explanation())
            engine.add_claim(claim)


        """
        assert isinstance(claim, terms.Claim), 'claim is not a terms.Claim in add_claim'
        self.log.debug("Engine is adding claim %s", claim)

        # Transform to Internal format
        assert isinstance(claim.literal, terms.Literal), 'Should be Literal'
        internal_claim = self.term_factory.mk_literal(claim.literal)

        # Ask Inference State to add this internal claim
        self.inference_state.lock()
        self.inference_state.add_claim([internal_claim], claim.reason, quiet=quiet)
        self.inference_state.unlock()

    def add_claims(self, claims):
        """
        Adding a list of `claims` to the engine. This is not just a loop
        through the list and calling
        :func:`etb.datalog.engine.Engine.add_claim` on each claim. Instead, it
        uses :func:`etb.datalog.inference.Inference.add_claims` which
        guarantees adding of the claims *atomically*.

        :parameters:
            - `claims`: is a list of :class:`etb.terms.Claim`.

        :returntype:
            `None`


        """
        internal_claims = []

        self.log.debug("Engine is adding claims %s", claims)

        for claim in claims:
            internal_c = self.term_factory.mk_literal(claim.literal)
            internal_claims.append(([internal_c], claim.reason))
        self.inference_state.lock()
        self.inference_state.add_claims(internal_claims)
        self.inference_state.unlock()

    def add_errors(self, goal, errors):
        """
        Adding a list `errors` for a `goal` to the engine. Note that we cannot
        reuse :func:`etb.datalog.engine.Engine.add_claims` as an error claim
        does not necessarily match a goal (for example, it would have a
        predicate name *error*). We therefore manually force the errors to be part of the
        claims of the goal.

        :parameters:
            - `goal`: a :class:`etb.terms.Term` instance representing the goal the
              errors should be added to as claims.
            - `error`: a list of :class:`etb.terms.Claim` instances
              representing errors.

        :returntype:
            `None`
        """

        internal_errors = []
        internal_goal = self.term_factory.mk_literal(goal)

        self.log.info("Engine has added errors %s", errors)

        for error in errors:
            internal_c = self.term_factory.mk_literal(error.literal)
            internal_errors.append(([internal_c], error.reason))
        self.inference_state.lock()
        self.inference_state.add_errors(internal_goal, internal_errors)
        self.inference_state.unlock()

    def add_goal_results(self, claims, goals, goal_results):
        """
        claims is a list of claims,
        goals is a list of goals,
        goal_results is a list corresponding to the goals list,
                        each element is a list of indices into claims
        Creates a results data structure in the interpret state.
        """
        gresults = dict(zip(goals, [[claims[i] for i in gr] for gr in goal_results]))
        self.inference_state.interpret_state.add_goal_results(dict(gresults))
        self.log.debug('add_goal_results: {0}'
                       .format(self.inference_state.interpret_state.results))

    def load_goals(self, claims, goals, annotations):
        """
        Restores goal annotations, and updates dependency graph
        """
        state = self.inference_state.logical_state
        def mk_annotation(frozen_goal, annot):
            """
            annot has the form
            {'kind': ann.kind, 'claims': aclaims, 'status': ann.status}
            """
            annotation = graph.Annotation(frozen_goal, annot['kind'], state)
            annotation.claims = [[self.term_factory.mk_literal(claims[i].literal)] for i in annot['claims']]
            annotation.status = annot['status']
            self.inference_state.logical_state.goal_dependencies.add_annotation(frozen_goal, annotation)
        for goal, annot in zip(goals, annotations):
            internal_goal = self.term_factory.mk_literal(goal)
            fgoal = model.freeze(internal_goal)
            self.inference_state.logical_state.db_add_goal(internal_goal)
            mk_annotation(fgoal, annot)

    def add_goal(self, goal):
        """
        Adds a goal to the engine by transforming the goal to its internal
        representation (using :func:`etb.datalog.model.TermFactory.mk_literal`)
        and subsequently (using
        :func:`etb.datalog.inference.Inference.add_goal`) adding the
        internal goal for consideration by the inference algorithm.

        :parameters:
            - `goal`: is an instance of :class:`etb.terms.Literal`.

        :returntype:
            `None`


        For example: ::

            import engine
            import terms

            interpret_state = engine.InterpretStateLessThan()
            engine = engine.Engine(interpret_state)
            literal = terms.mk_apply("p", ["a", "b"])
            engine.add_goal(literal)
        """

        assert isinstance(goal, terms.Literal),\
            'goal {0} of type {1} is not a terms.Literal in add_goal'\
                .format(goal, type(goal))
        # Transform to Internal format
        internal_goal = self.term_factory.mk_literal(goal)
        # And add to inference engine:
        self.inference_state.lock()
        self.inference_state.add_goal(internal_goal)
        self.inference_state.unlock()

    def push_no_solutions(self, goal):
        """
        Indicate to the engine that you do not have an solutions for the
        (interpreted) goal. This could be used from an
        :class:`etb.interpret_state.InterpretState` in a response to an
        Engine's calling of
        :func:`etb.interpret_state.InterpretState.interpret`. As the
        `InterpretState` answers to such a request asynchronously the Engine
        needs to be informed when the InterpretState is finished with
        calculating and it has not found any solutions; in case it would have
        found solutions it can add them with
        :func:`etb.datalog.engine.Engine.add_claim` which would signal the
        Engine that the goals matching those claims now have solutions. If no
        solutions are found, it would use this function (`push_no_solutions`)
        to inform the Engine that this particular goal is handled.

        This particular function just transforms the goal to its internal
        format and calls
        :func:`etb.datalog.inference.Inference.push_no_solutions`.

        :parameters:
            - `goal`: is an instance of :class:`etb.terms.Term`.

        :returntype:
            `None`


        For example: ::

            import engine
            import terms

            interpret_state = engine.InterpretStateLessThan()
            engine = engine.Engine(interpret_state)
            literal = terms.mk_apply("gt", [2, 4])
            # we will assume literal is interpreted and InterpretState
            # would indicate that 2 is not greater than 4
            engine.add_goal(literal)
            # Indicate the engine that there are no solutions:
            engine.push_no_solutions(literal)
        """

        assert isinstance(goal, terms.Literal), 'goal is not a Literal in push_no_solutions'
        assert self.inference_state.interpret_state.is_interpreted(goal), 'goal is not interpreted in push_no_solutions'
        internal_goal = self.term_factory.mk_literal(goal)
        self.inference_state.lock()
        self.inference_state.push_no_solutions(internal_goal)
        self.inference_state.unlock()



    def add_pending_rule(self, rule, external_goal=None, internal_goal=None):
        """
        We add a pending `rule` to the Engine based on a given `external_goal`. The
        intent of pending rule is that they are used by the Inference engine as
        such: they are temporary rules created as a result of reasoning (e.g.,
        by resolving away the first body literal of a KB rule).

        :parameters:
            - `rule`: is a :class:`etb.terms.Clause`
            - `external_goal` (optional): is an instance of
              :class:`etb.terms.Term` and represents the goal that caused the
              creation of this pending rule.

        :returntype:
            `None`


        .. note::
            If the rule is actually a claim, the `external_goal` can be `None`;
            we will call :func:`etb.datalog.engine.Engine.add_claim` in that
            case.

        """
        assert isinstance(rule, terms.Clause), 'rule is not a terms.Clause in add_pending_rule'
        if not rule.body: # then it is a fact, we are treating it as a claim:
            self.add_claim(terms.Claim(rule.head, model.create_external_explanation()))

        # otherwise it is a real rule:
        internal_rule = self.term_factory.mk_clause(rule)

        if not external_goal is None:
            if internal_goal is None:
                self.log.debug('Engine.add_pending_rule called with goal  %s and rule %s' %(external_goal, rule))
                internal_goal = self.term_factory.mk_literal(external_goal)
        else:
            self.log.debug('Engine.add_pending_rule called without goal.')
            return

        # Note that there is no from_clause here
        explanation = model.create_resolution_top_down_explanation(None, internal_goal)
        self.log.debug('engine.add_pending_rule: explanation: {0}, goal: {1}'.format(explanation, external_goal))
        self.inference_state.lock()
        self.inference_state.add_pending_rule(internal_rule, explanation, internal_goal)
        self.inference_state.unlock()
        # only interpretstate will call pending rulef for goals (which means
        # that goal becomes automatically unstuck)
        #self.inference_state.lock()
        #self.inference_state.logical_state.db_move_stuck_goal_to_goal(internal_goal)
        #self.inference_state.unlock()


    def add_rule(self, rule, explanation):
        """
        Adds a KB rule to the Engine. In this case a *KB rule* means a rule of
        which the head will be matched against any goals to produce pending
        rules as a consequence. As such, those KB rules are not used for
        resolution. This function transforms the external rule to the internal
        format using :func:`etb.datalog.model.TermFactory.mk_clause` and
        subsequently calls :func:`etb.datalog.inference.Inference.add_rule`.

        :parameters:
            - `rule`: is a :class:`etb.terms.Clause` or :class:`etb.terms.DerivationRule` or :class:`etb.terms.InferenceRule`
            - `explanation`: Gives a reason for this rule. Currently, tested
              with `None` or
              :func:`etb.datalog.model.create_axiom_explanation`. The latter
              indicates that this is a KB rule.

        :returntype:
            `None`


        For example: ::

            import engine
            import terms

            interpret_state = engine.InterpretStateLessThan()
            eng = engine.Engine(interpret_state)

            qXb = terms.mk_apply("q", [X, "b"])
            pXY = terms.mk_apply("p", [X, Y])
            iXb = terms.mk_apply("i", [X, "b"])
            engine.add_rule(terms.Clause(qXb, [pXY, iXb]), None)

        """
        assert isinstance(rule, terms.Clause) or isinstance(rule, terms.DerivationRule) or isinstance(rule, terms.InferenceRule), 'rule is not a terms.Clause, not a terms.DerivationRule, and not a terms.InferenceRule in add_rule'
        internal_rule = self.term_factory.mk_clause(rule)
        self.inference_state.lock()
        self.inference_state.add_rule(internal_rule, explanation)
        self.inference_state.unlock()

    def load_default_rules(self):
        """
        Load rules (and facts) from a file. We parse the file using
        :mod:`etb.parser` and then add each of the
        statements using :func:`etb.datalog.engine.Engine.add_claim` for facts
        or :func:`etb.datalog.engine.Engine.add_rule` for rules.

        :parameters:
            - `filename`: the file containing the rules and facts

        :returntype:
            `None`


        For example: ::

            # For engine an instance of Engine
            engine.load_rules('./etb/datalog/test/clique10.lp')

        """
        if os.path.isdir('rules'):
            for file in os.listdir('rules'):
                rule_file = 'rules/' + file
                self.log.debug('loading rules {0}'.format(rule_file))
                self.load_rules(rule_file)

    def load_rules(self, rule_file):
        self.log.debug('load rules from %s', rule_file)
        try:
            statements = parser.parse_file(rule_file)
        except IOError as e:
            self.log.error("IO error while reading %s: %s",
                           rule_file, e)
            return
        except Exception as e:
            self.log.error("parse error while reading %s: %s",
                           rule_file, e)
            return
        self.facts[rule_file] = []
        self.rules[rule_file] = []
        facts = [obj for obj in statements if isinstance(obj, terms.Literal)]
        # parse some facts
        axiom_num = 0
        for fact in facts:
            assert fact.is_ground(), 'fact is not ground in load_rules'
            assert isinstance(fact, terms.Literal), 'fact is not Literal'
            axiom_num += 1
            fact_rule = terms.mk_fact_rule(fact)
            self.facts[rule_file].append(fact)
            self.add_rule(fact_rule, model.create_axiom_explanation())
            # self.add_claim(terms.Claim(fact, model.create_axiom_explanation()))
        # parse some rules
        rules_num = 0
        rules = [obj for obj in statements if isinstance(obj, terms.DerivationRule)]
        for rule in rules:
            rules_num += 1
            self.rules[rule_file].append(rule)
            self.add_rule(rule, model.create_axiom_explanation())
        # parse some inference rules
        inf_rules_num = 0
        rules = [obj for obj in statements if isinstance(obj, terms.InferenceRule)]
        for rule in rules:
            inf_rules_num += 1
            self.rules[rule_file].append(rule)
            self.add_rule(rule, model.create_axiom_explanation())

        self.log.debug('Parsed rules file %s:', os.path.abspath(rule_file))
        if axiom_num > 0:
            self.log.info('  %d axioms', axiom_num)
        if rules_num > 0:
            self.log.info('  %d derivation rules', rules_num)
        if inf_rules_num > 0:
            self.log.info('  %d inference rules', inf_rules_num)

    def load_logic_file(self):
        """
        Load logic state (claims, goals, and annotations) from a JSON file.
        The changed flag indicates whether the rules or wrappers have chenged,
        in which case the file is not loaded.
        """
        filename = 'etb_logic_file'
        if os.path.exists(filename):
            self.log.debug("Loading logic state file {0}".format(filename))
            try:
                with bz2.BZ2File(filename, 'r') as f:
                    # file contents is a list [claims, goals, annotations]
                    # for claim in claims:
                    #     self.add_claim(claim, quiet=True)
                    # for goal in content[1]:
                    #     self.log.info('load_logic_file: add_goal_result {0!s}'
                    #                   .format([str(gr) for gr in gres]))
                    claims, goals, annotations = terms.load(f)
                    # print 'claims = {0}'.format(claims)
                    #print 'goals = {0}'.format(goals)
                    #print 'annotations = {0}'.format(annotations)
                    self.inference_state.lock()
                    self.add_claims(claims)
                    #self.add_goal_results(claims, goals, goal_results)
                    self.load_goals(claims, goals, annotations)
                    self.inference_state.unlock()
                    self.log.info('loaded %d claims and %d goals from %s',
                                  len(claims), len(goals), filename)
            except Exception as err:
                self.log.exception('unable to load logic state file {0}:\n {1}'
                                   .format(filename, err))

    def check_stuck_goals(self):
        """
        Force the engine to recheck its stuck goals (a stuck goal is a goal
        that the :class:`etb.datalog.inference.Inference` send off to an
        :class:`etb.interpret_state.InterpretState` but for which the Engine did not
        receive any matching claims back or did not receive a
        :func:`etb.datalog.engine.Engine.push_no_solutions`).

        :returntype:
            `None`


        .. note::

            It should not be necessssary for the
            :class:`etb.interpret_state.InterpretState` to ping the Engine this
            way. It can use :func:`etb.datalog.engine.Engine.add_claim`,
            :func:`etb.datalog.engine.Engine.add_claims`, or
            :func:`etb.datalog.engine.Engine.push_no_solutions` -- and if it
            did not use any of those, forcing to check whether stuck goals can be
            unstuck goals would not do anything useful.

        """
        self.inference_state.lock()
        self.inference_state.check_stuck_goals()
        self.inference_state.unlock()

    def close(self):
        """
        Ask the engine to close off goals. Relays directly to
        :func:`etb.datalog.inference.Inference.close`.

        :returntype:
            `None`

        """
        self.inference_state.close()

    def complete(self):
        """
        Ask the engine to complete goals. Relays directly to
        :func:`etb.datalog.inference.Inference.complete`.

        :returntype:
            `None`

        """
        self.inference_state.complete()

    def is_completed(self, goal):
        """
        Determine whether a goal is completed (no further processing of the
        Datalog engine on that goal on the way). The function creates an
        internal goal from `goal` and calls
        :func:`etb.datalog.inference_state.Inference.is_completed`.

        :parameters:
            - `goal`: an instance of :class:`etb.terms.Literal`

        :returntype:
            returns `True` or `False`

        Typical usage would be as a stopping condition in loop that
        periodically tries to close and complete the goals in the engine: ::

            # for engine an instance of Engine:
            while not engine.is_completed(goal):
                engine.close()
                engine.complete()
                time.sleep(.1)

        """
        internal_goal = self.term_factory.mk_literal(goal)
        return self.inference_state.is_completed(internal_goal)

    def get_claims(self):
        """
        Get all claims the engine currently knows about. Uses
        :func:`etb.datalog.inference.Inference.get_claims` to get the internal
        claims and uses :func:`etb.datalog.model.TermFactory.close_explanation`
        and :func:`etb.datalog.model.TermFactory.close_literal` to produce an
        external claim with :class:`etb.terms.Claim`.

        :returntype:
            returns a list of :class:`etb.terms.Claim` instances

        """
        internal_claims = self.inference_state.get_claims()
        def create_external_claim(internal_claim):
            external_literal = self.term_factory.close_literal(internal_claim[0])
            tmp_claim = terms.Claim(external_literal, None)
            expl = self.get_rule_and_facts_explanation(tmp_claim)
            external_claim = terms.Claim(external_literal, expl)
            return external_claim

        return map(lambda claim: create_external_claim(claim), internal_claims)

    def get_goal_results(self):
        """
        Get the goal results table (dictionary) from the global state for
        interpreted predicates.
        """
        return self.inference_state.interpret_state.get_goal_results()

    def get_goal_annotation(self, goal):
        internal_goal = self.term_factory.mk_literal(goal)
        rename_goal = self.inference_state.logical_state.is_renaming_present_of_goal(internal_goal)
        if rename_goal:
            fgoal = model.freeze(rename_goal)
        else:
            fgoal = model.freeze(goal)
        annot = self.inference_state.logical_state.goal_dependencies.get_annotation(fgoal)
        return annot

    def get_goal_annotations(self, goal_results):
        """
        Get the annotations associated with the goals in goal_results
        goal_results is a list of tuples mapping internal goals to internal claims
        """
        annots = [self.get_goal_annotation(g) for g, c in goal_results]
        return annots

    def get_rules(self):
        """
        Get the rules the engine currently knows about.  Uses
        :func:`etb.datalog.inference.Inference.get_rules` to get the internal
        rules and uses :func:`etb.datalog.model.TermFactory.close_literals` to
        produce an external clause with :class:`etb.terms.Clause`.

        :returntype:
            returns a list of :class:`etb.terms.Clause` instances

        """
        internal_rules = self.inference_state.get_rules()
        external_rules = []
        def transform_internal_rule_to_external_rule(internal):
            closed_literals = self.term_factory.close_literals(internal)
            return terms.Clause(closed_literals[0], closed_literals[1:])
        return map(lambda rule: transform_internal_rule_to_external_rule(rule), internal_rules)


    def get_stuck_goals(self):
        """
        Get all stuck goals. Anything using the engine might want to use that
        to see how the Engine is doing. We use
        :func:etb.datalog.inference.Inference.get_stuck_goals` to get the
        internal forms of the stuck goals and then produce the external
        versions using :func:`etb.datalog.model.TermFactory.close_literals`.

        :returntype:
            returns a list of :class:`etb.terms.Term` instances

        .. seealso::

            :func:`etb.datalog.engine.Engine.check_stuck_goals` for a
            definition of what a stuck goal is.

        """
        internal_stuck_goals = self.inference_state.get_stuck_goals()
        return self.term_factory.close_literals(internal_stuck_goals)

    def is_stuck_goal(self, goal):
        """
        Determine whether goal is stuck. This is verified, after creating the
        internal goal, by asking
        :func:`etb.datalog.inference.Inference.is_stuck_goal`.

        :parameters:
            - `goal`: an instance of :class:`etb.terms.Term`

        :returntype:
            returns `True` or `False`


        .. seealso::

            :func:`etb.datalog.engine.Engine.check_stuck_goals` for a
            definition of what a stuck goal is.

        """
        assert isinstance(goal, terms.Literal), 'goal is not a Literal in is_stuck_goal'
        internal_goal = self.term_factory.mk_literal(goal)
        return self.inference_state.is_stuck_goal(internal_goal)

    def no_stuck_subgoals(self, goal):
        """
        Determine whether `goal` has any stuck subgoals in the goal
        dependency graph :class:`etb.datalog.graph.DependencyGraph`. Relays to
        :func:`etb.datalog.inference.Inference.no_stuck_subgoals` after
        creating the internal version of `goal`.

        :parameters:
            - `goal`: of type :class:`etb.terms.Term`

        :returntype:
            returns `True` or `False`

        """
        assert isinstance(goal, terms.Literal), 'goal is not a Literal in no_stuck_subgoals'
        internal_goal = self.term_factory.mk_literal(goal)
        return self.inference_state.no_stuck_subgoals(internal_goal)


    def get_goals(self):
        """
        Get all goals. Relays to
        :func:`etb.datalog.inference.Inference.get_goals`.

        :returntype:
            returns a list of :class:`etb.terms.Term` instances

        """
        internal_goals = self.inference_state.get_goals()
        return self.term_factory.close_literals(internal_goals)

    def get_claims_matching_goal(self, goal):
        """
        Get all claims the engine knows about that are
        specializations/solutions to the `goal`. This can be used to get
        answers to a particular goal. Note that this does not *trigger*
        reasoning; it just picks up what it knows about that goal. To trigger
        reasoning you would have used
        :func:`etb.datalog.engine.Engine.add_goal`.

        It acts as a bridge with inferencing by turning the external `goal`
        into the internal representation and calling
        :func:`etb.datalog.inference.Inference.get_claims_matching_goal`.

        :parameters:
            - `goal`: of type :class:`etb.terms.Literal`

        :returntype:
            returns a list of :class:`etb.terms.Claim` instances


        """
        assert isinstance(goal, terms.Literal), 'goal is not a Literal in get_claims_matching_goal'
        internal_goal = self.term_factory.mk_literal(goal)
        internal_claims = self.inference_state.get_claims_matching_goal(internal_goal)
        def create_external_claim(internal_claim):
            external_literal = self.term_factory.close_literal(internal_claim[0])
            tmp_claim = terms.Claim(external_literal, None)
            external_claim = terms.Claim(external_literal, self.get_rule_and_facts_explanation(tmp_claim))
            return external_claim

        return map(lambda claim: create_external_claim(claim), internal_claims)

    def get_substitutions(self, goal):
        """
        Return a list of substitutions :class:`etb.terms.Subst` where each
        substitution is obtained by unifying the goal with each matching claim.
        The matching claims are obtained by
        :func:`etb.datalog.engine.Engine.get_claims_matching_goal` and unification is
        done using :func:`etb.terms.Term.unify` (see also the latter for the form of
        a substitution).

        :parameters:
            - `goal`: an instance of :class:`etb.terms.Term`

        :returntype:
            returns a list of :class:`etb.terms.Subst` instances


        .. seealso::
            :func:`etb.datalog.test.engine_test.TestEngine.test_get_substitutions`

        """
        matching_claims = self.get_claims_matching_goal(goal)
        self.log.debug('matching claims {0} for goal {1}'
                       .format(matching_claims, goal))
        substitutions = []
        for claim in matching_claims:
            subst = goal.unify(claim.literal)
            if subst is not None:
                substitutions.append(subst)
        return substitutions

    def all_claims(self, goal):
        """
        Synonym for :func:`etb.datalog.engine.Engine.get_claims_matching_goal`.

        :returntype:
            returns a list of :class:`etb.terms.Claim` instances

        """
        return self.get_claims_matching_goal(goal)

    def is_entailed(self, goal):
        """
        .. warning::
            **DEPRECATED**: There is no requirement on the current engine to
            support this function.

        Check whether the engine currently thinks this goal holds.
        """
        assert isinstance(goal, terms.Literal), 'goal is not a Literal in is_entailed'
        internal_goal = self.term_factory.mk_literal(goal)
        return self.inference_state.is_entailed(internal_goal)

    def clear(self):
        """
        Clear the Engine. Relays to
        :func:`etb.datalog.inference.Inference.clear`.

        :returntype:
            `None`

        """
        self.inference_state.clear()

    def reset(self, keepRules=True):
        self.inference_state.reset()

    def __readable_clause(self,list_of_terms):
        """
        Convenience function to produce a string out of a list of strings
        that is assumed to represent a rule.
        """
        if len(list_of_terms) == 1:
            return str(list_of_terms[0]) + "."
        else:
            return str(list_of_terms[0]) +  " :- " + ",".join(map(lambda literal: str(literal), list_of_terms[1:]))


    def get_rule_and_facts_explanation(self, claim):
        internal_fact = self.term_factory.mk_literal(claim.literal)

        # the facts and 1 rule to collect
        facts = []
        rule = [None]

        def generate_children(cl):
            explanation = self.inference_state.logical_state.db_get_explanation(cl)
            external_explanation = self.term_factory.close_explanation(explanation)
            if isinstance(explanation, tuple) and len(explanation) == 2: # an Axiom or External or None
                self.log.debug("get_rule_and_facts_explanation: claim %s has explanation %s and is External or Axiom or None" % (claim, external_explanation))
                facts.append(self.term_factory.close_literal(cl[0]))

            elif isinstance(explanation, tuple) and len(explanation) == 3 and explanation[0] == "ResolutionTopDown":
                self.log.debug("get_rule_and_facts_explanation: claim %s has explanation %s and is ResolutionTopDown" % (claim, external_explanation))
                rule[0] = self.__readable_clause(self.term_factory.close_literals(cl))

            elif isinstance(explanation, tuple) and len(explanation) == 3 and explanation[0] == "ResolutionBottomUp":
                self.log.debug("get_rule_and_facts_explanation: claim %s has explanation %s and is ResolutionBottomUp" % (claim, external_explanation))
                generate_children(explanation[1])
                generate_children(explanation[2])

            elif isinstance(explanation, (terms.Literal, unicode)):
                self.log.debug("get_rule_and_facts_explanation: claim %s has explanation %s and is TERM" % (claim, external_explanation))
                facts.append(external_explanation)

        generate_children([internal_fact])

        if rule[0] is not None:
            return "from rule " + rule[0] + " with facts: " + ", ".join(map(lambda literal: str(literal), facts))
        elif len(facts) == 1:
            return str(facts[0])
        else:
            return ", ".join(map(lambda literal: str(literal), facts))

    def to_png(self, claim):
        """
        Create a PNG image of a graph that explains how the engine deduced the
        `claim`.

        :parameters:
            - `claim`: an instance of :class:`etb.terms.Claim`

        :returntype:
            returns a singleton list containing 1 string that represents the
            filename of the PNG.

        The function returns a list `[filename]` where `filename` is the
        created PNG file.

        """
        internal_fact = self.term_factory.mk_literal(claim.literal)

        graph = pydot.Dot(graph_type='graph')

        def generate_children(cl):
            #print("generate_children(%s)" % repr(cl))
            explanation = self.inference_state.logical_state.db_get_explanation(cl)
            #print("explanation = %s" % repr(explanation))
            external_explanation = self.term_factory.close_explanation(explanation)
            #print("external_explanation = %s" % external_explanation)
            label_top_node = self.__readable_clause(self.term_factory.close_literals(cl))
            top_node = pydot.Node(str(cl),label=label_top_node)
            graph.add_node(top_node)
            #the isinstance stuff is a hack to prevent crashing
            if  isinstance(explanation, tuple) and len(explanation) == 2: # an Axiom or External or None
                axiom_node = pydot.Node(str(uuid.uuid4()), label=external_explanation)
                graph.add_node(axiom_node)
                edge = pydot.Edge(top_node, axiom_node )
                graph.add_edge(edge)
            elif isinstance(explanation, tuple) and len(explanation) == 3 and explanation[0] == "ResolutionTopDown":
                # Note that we do not recurse through the goal node
                goal_explanation = pydot.Node(str(explanation[2]), label=str(self.term_factory.close_literal(explanation[2])))
                goal_node_id = str(uuid.uuid4())
                goal_node = pydot.Node(goal_node_id, label="Goal")
                graph.add_node(goal_node)
                graph.add_node(goal_explanation)
                resolution_node = pydot.Node(str(uuid.uuid4()), label=explanation[0])
                graph.add_node(resolution_node)
                edge1 = pydot.Edge(top_node, resolution_node )
                edge2 = pydot.Edge(top_node, str(explanation[1]))
                edge3 = pydot.Edge(top_node, str(explanation[2]))
                edge4 = pydot.Edge(str(explanation[2]), goal_node_id)
                graph.add_edge(edge1)
                graph.add_edge(edge2)
                graph.add_edge(edge3)
                graph.add_edge(edge4)
                if explanation[1] is not None:
                    generate_children(explanation[1])

            elif isinstance(explanation, tuple) and len(explanation) == 3 and explanation[0] == "ResolutionBottomUp": # ResolutionBottomUp
                node = pydot.Node(str(uuid.uuid4()), label=explanation[0])
                graph.add_node(node)
                edge1 = pydot.Edge(top_node, node )
                edge2 = pydot.Edge(top_node, str(explanation[1]))
                edge3 = pydot.Edge(top_node, str(explanation[2]))
                graph.add_edge(edge1)
                graph.add_edge(edge2)
                graph.add_edge(edge3)
                generate_children(explanation[1])
                generate_children(explanation[2])

            elif isinstance(explanation, terms.Term):
                node = pydot.Node(str(uuid.uuid4()), label="External")
                graph.add_node(node)
                edge1 = pydot.Edge(top_node, node )
                graph.add_edge(edge1)
                # only add explanation if it's actually different from the
                # top_node's label
                # -1 cause there is a dot to end a clause
                if not str(explanation) == label_top_node[:-1]:
                    edge2 = pydot.Edge(top_node, str(explanation))
                    graph.add_edge(edge2)
            else:
               # just make a string out of the explanation and show it
                node = pydot.Node(str(uuid.uuid4()), label="Unknown")
                graph.add_node(node)
                edge1 = pydot.Edge(top_node, node )
                edge2 = pydot.Edge(top_node, str(explanation))
                graph.add_edge(edge1)
                graph.add_edge(edge2)

        generate_children([internal_fact])
        filename = str(uuid.uuid4()) + ".png"
        graph.write_png(filename)
        return [filename]

    def get_global_time(self):
        """
        Each engine is associated with a global time ticker maintained in
        :class:`etb.datalog.model.LogicalState` (each Engine has one and only
        one `LogicalState`). This is relayed to
        :func:`etb.datalog.inference.LogicalState.get_global_time` and returns
        a positive integer.

        :returntype:
            returns a positive integer

        """
        return self.inference_state.logical_state.get_global_time()

    def inc_global_time(self):
        """
        Increase the global time ticker of the engine with 1.

        :returntype:
            `None`

        .. seealso::
            :func:`etb.datalog.engine.Engine.get_global_time`

        """
        self.inference_state.logical_state.global_time += 1

    def go_slow(self, speed):
        """
        Force the engine to do slow(er) inferencing to take `speed` seconds
        between each inference step.

        :parameters:
            - `speed`: an integer representing seconds.

        :returntype:
            `None`
        """
        self.SLOW_MODE = speed
        self.inference_state.logical_state.go_slow(speed)

    def go_normal(self):
        """
        Undo the effects of :func:`etb.datalog.engine.Engine.go_slow`.

        :returntype:
            `None`

        .. seealso::
            :func:`etb.datalog.engine.Engine.go_slow`

        """
        self.SLOW_MODE = 0
        self.inference_state.logical_state.go_normal()

    def close_during_inferencing(self):
        """
        Attempt to close goals after each inferencing step using
        :func:`etb.graph.DependencyGraph.close`.

        :returntype:
            `None`

        .. warning::
            This causes slow reasoning; only use for debugging purposes (for
            example when you want to see the effect of intermediate close
            operations).

        """
        self.CLOSE_DURING_INFERENCING = True

    def stop_close_during_inferencing(self):
        """
        Undo the effects of :func:`etb.datalog.engine.Engine.close_during_inferencing`.

        :returntype:
            `None`

        .. seealso::
            :func:`etb.datalog.engine.Engine.close_during_inferencing`.

        """
        self.CLOSE_DURING_INFERENCING = False


    def goal_deps_to_png(self, goal):
        """
        Create a PNG image of a graph that shows the goal dependencies starting
        from `goal`.

        :parameters:
            - `goal`: an instance of :class:`etb.terms.Term`

        :returntype:
            returns a string `filename` where `filename` is the created PNG file.

        .. todo::
            Create prettier graphs (colors etc)

        """

        # first push goals to be reevaluated (stuck or not stuck?)
        # self.check_stuck_goals()
        self.inference_state.lock()

        internal_goal = self.term_factory.mk_literal(goal)
        internal_deps = self.inference_state.logical_state.db_get_goal_dependencies()

        pygraph = pydot.Dot(graph_type='graph')

        def generate_children(root, previous_index):

            annotation_root = self.inference_state.logical_state.db_get_annotation(root)
            if not annotation_root:
                return
            index_root = annotation_root.index

            if index_root < previous_index:
                return

            subgoalindex_root = annotation_root.subgoalindex
            claims_root = map(lambda claim: claim[0], annotation_root.claims)
            status_root = annotation_root.print_status()
            goal_root = annotation_root.goal
            if goal_root:
                pretty_print_goal = str("\n\t\t(goal: " + str(self.term_factory.close_literal(goal_root)) + " )")
            else:
                pretty_print_goal = ""
            pretty_print_subgoalindex = str("\n\t\t(prop: " + str(subgoalindex_root) + ")")
            pretty_print_claims = str("\n\t\t(claims: " + str(self.term_factory.close_literals(claims_root)) + " )")
            pretty_print_index = str("\n\t\t(index: " + str(index_root) + " )")
            pretty_print_status = str("\n\t\t(status: " + status_root + " )")
            #pretty_print_gT = "\n\t\t(g.T: " + str(annotation_root.print_gT(self.term_factory))
            #pretty_print_gD = "\n\t\t(g.D: " + str(annotation_root.print_gD(self.term_factory)) + " )"

            if any(isinstance(el, tuple) for el in root):
                self.log.info("png generation: %s", self.__readable_clause(self.term_factory.close_literals(root)))
                root_node = pydot.Node(str(root),
                        label=self.__readable_clause(self.term_factory.close_literals(root))
                        + pretty_print_subgoalindex +
                        pretty_print_goal +
                        pretty_print_index)
            else:
                self.log.info("png generation: %s", str(self.term_factory.close_literal(root)))
                root_node = pydot.Node(str(root),
                        label=str(self.term_factory.close_literal(root)) +
                        pretty_print_claims +
                        pretty_print_index +
                        #pretty_print_gT + pretty_print_gD +
                        pretty_print_status)

            if self.inference_state.is_stuck_goal(list(root)):
                 root_node.set("shape", 'box')

            pygraph.add_node(root_node)

            children = internal_deps.get_children(root)

            if children:
                for child in children:
                    pygraph.add_edge(pydot.Edge(root_node, str(child)))
                    generate_children(child, index_root)
            else:
                return

        generate_children(tuple(internal_goal), 0)
        filename = str(uuid.uuid4()) + ".png"
        pygraph.write_png(filename)
        self.inference_state.unlock()
        return filename

    def save_logic_file(self, *args, **kwargs):
        """
        Save the current logic state in the file.
        This is a list with four elements:
        claims the list of (external) claims
        goals the list of (external) goals (Literals)
        goal_results a list of lists of integers.  This corresponds to
          the goals list, and each element is a list of indices into the claims list
        annotations is a list of annotations, where the claims and 
        """
        filename = 'etb_logic_file'
        self.log.debug("Save logic state to file {0}".format(filename))
        # get_claims returns the list of (external) claims
        # get_goal_results returns the (external) goal to (external) claims dict
        # get_goal_annotations returns the annotations list corresponding to goal_results
        all_claims = self.get_claims()
        all_goals = self.get_goals()
        annotations = []
        for goal in all_goals:
            internal_goal = self.term_factory.mk_literal(goal)
            ann = self.get_goal_annotation(goal)
            # For now, only save completed goals
            if ann is None:
                self.log.error('goal {0} has no annotations'.format(goal))
            elif ann.status == graph.Annotation.COMPLETED:
                # graph.Annotation: not all members are saved.
                # Assumes completed Annotations for now.
                # goal and state will be restored when this is loaded
                # index, subgoalindex, gT, gD, and gUnclosed are not needed for completed
                aclaims = []
                for intclaim in ann.claims:
                    claim = self.term_factory.close_literal(intclaim[0])
                    fnd = False
                    for i in range(len(all_claims)):
                        ilit = all_claims[i].literal
                        if all_claims[i].literal == claim:
                            fnd = True
                            aclaims.append(i)
                    if not fnd:
                        self.log.error('save_logic_file: claim {0} from annotation for {1} not in all_claims'
                                       .format(claim, goal))
                annot = {'kind': ann.kind, 'claims': aclaims, 'status': ann.status}
                annotations.append(annot)
            else:
                self.log.error('save_logic_file: goal {0} is {1}, not completed'
                               .format(goal, ann.status))
        lstate = [all_claims, all_goals, annotations]
        # print 'save_logic_file: claims  {0}'.format(all_claims)
        #print 'save_logic_file: goals   {0}'.format(all_goals)
        #print 'save_logic_file: annots  {0}'.format(annotations)
        self.log.info('saved {0} claims and {1} goals in {2}'
                      .format(len(all_claims), len(all_goals), filename))
        kwargs['separators'] = (',',':')  # compact representation
        try:
            with bz2.BZ2File(filename, 'w') as f:
                terms.dump(lstate, f, *args, **kwargs)
        except Exception as err:
            self.log.exception('save_logic_file: unable to save file {0}'
                               .format(filename))

# The methods below represent the requirements on the InterpretState API from
# Datalog engine's perspective

class InterpretStateLessThan():
    """
    This is just an example of a particular `InterpretState` for testing
    purposes. It illustrates that :class:`etb.datalog.engine.Engine` expects
    any `InterpretState` to define 2
    methods: `is_interpreted` and `interpret`. This particular example treats
    `lt` as an external/interpreted predicate.
    """

    def is_interpreted(self, external_goal):
        """
        Decided whether this `external_goal` interpreted?

        .. warning::
            This function is for testing purposes only. Use
            :func:`etb.interpret_state.InterpretState.is_interpreted` instead.

        """
        # This is just an example of matching against some built-in lt (and any
        # other predicate starting with lt will also be matched, which is not
        # what we want). The actual InterpretState will be much much much more
        # involved of course.
        assert isinstance(external_goal, terms.Literal), 'external_goal is not a Literal in is_interpreted'
        predicate_name = external_goal.get_pred()
        return  predicate_name == terms.IdConst("lt") or predicate_name == terms.IdConst("gt")

    def is_valid(self, goal):
                return True

    def interpret_goal_somewhere(self, external_goal, internal_goal, engine):
        """
        Tell the `InterpretState` to add whatever it deems necessary to the
        engine via `add_claim`, `add_rule`, ..., based on the `external_goal`.

        .. warning:
            This function is for testing purposes only. Use
            :func:`etb.interpret_state.InterpretState.interpret` instead.

        """
        # This is just a dummy example of how the InterpretState would handle
        # less than...(this is just to make existing examples with less_than
        # working again but also illustrates how InterpretState sends stuff to
        # the Engine).
        assert isinstance(external_goal, terms.Literal), 'external_goal is not a Literal in interpret_goal_somewhere'
        assert isinstance(engine, Engine), 'engine is not a Engine in interpret_goal_somewhere'

        args = external_goal.get_args()
        if external_goal.get_pred() == terms.IdConst("lt") and externals.less_than(args[0].val, args[1].val):
            # we add the ground goal to the claims of the engine
            claim = terms.Claim(external_goal, model.create_external_explanation())
            engine.add_claim(claim)


    # Added for integration in etb
    def predicates(self):
        return {}
