""" Datalog Inference

This module provides the main inference capability for the Datalog engine
defined in :class:`etb.datalog.engine.Engine` via the class
:class:`etb.datalog.inference.Inference`. Note that while the
:class:`etb.datalog.engine.Engine` class deals with external representations
(i.e., with :class:`etb.terms.Term`, :class:`etb.terms.Claim`, and
:class:`etb.terms.Clause`), the inferencing only uses the internal
representation as defined by the :class:`etb.datalog.model.TermFactory`.

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

from . import model
from . import index
import logging
import time
from . import graph

class Inference(object):

    def __init__(self, logical_state, interpret_state, term_factory, engine):
        """
        Create an Inference object using a `logical_state` (see
        :class:`etb.datalog.model.LogicalState`), an `interpret_state` (see
        :class:`etb.interpret_state.InterpretState`), a `term_factory` (see
        :class:`etb.datalog.model.TermFactory`), and the `engine`
        :class:`etb.datalog.engine.Engine` containing
        this Inference object.

        :parameters:
            - `logical_state`: an instance of
              :class:`etb.datalog.model.LogicalState` that keeps track of the
              current state of reasoning (rules, claims, pending rules, goals,
              stuck goals, etc).
            - `interpret_state`: an instance of
              :class:`etb.interpret_state.InterpretState` that is used to
              determne whether predicates are interpreted and to subsequently
              take care of interpreting such interpreted queries.
            - `term_factory`: an instance of
              :class:`etb.datalog.model.TermFactory`). In principle, we only
              deal with internal representations of rules, claims, etc.
              However, we need the external representation to determine whether
              something is interpreted and to subsequently call the
              `InterpretState` with that interpreted query as an argument.
            - `engine`: an instance of :class:`etb.datalog.engine.Engine`. We
              assume the `InterpretState` needs this `Engine` to be able to add
              any claims back to the Engine (in practice, the `InterpretState`
              actually knows the `Engine` to add claims/pending rules, so this
              argument would not be strictly necessary).

        :members:
            The members correspond exactly to the arguments of the constructor.
        """
        # The state
        self.logical_state = logical_state
        # The structure maintaining the correspondence between the internal
        # representation and the symbols (we use this in case of interpreted
        # predicates which have to be transformed from their internal
        # representation to something InterpretState understands).
        self.term_factory = term_factory
        # The `InterpretState` for resolving interpreted/external predicates
        self.interpret_state = interpret_state
        # Keep a link to the Engine this Inference object belongs to
        self.engine = engine
        self.log = logging.getLogger('etb.datalog.inference')

    def clear(self):
        """
        Clear the :class:`etb.datalog.model.LogicalState` and the
        :class:`etb.datalog.model.TermFactory`. Note that we are *not*
        attempting to clear the `Engine` or `InterpretState` that is associated
        with this `Inference` object. They lie outside this object's authority.

        :returntype:
            `None`

        """
        self.logical_state.clear()
        self.term_factory.clear()

    def reset(self, keepRules=True):
        """
        A `reset` is intented to, by default, only clear claims. As such it is
        just a call to :func:`etb.datalog.model.LogicalState.reset`.

        :parameters:
            - `keepRules` (optional): `True` (the default) or `False`. If
              `True`, we only get rid of claims.

        :returntype:
            `None`
        """
        self.logical_state.reset()


    def lock(self):
        self.logical_state.goal_dependencies.inferencing_clear = False
        self.logical_state.goal_dependencies.condition.acquire()

    def unlock(self):
        self.logical_state.goal_dependencies.condition.notify_all()
        self.logical_state.goal_dependencies.inferencing_clear = True
        self.logical_state.goal_dependencies.condition.release()

    def notify(self):
        self.logical_state.goal_dependencies.condition.notify()


    def resolve_claim(self, prule, explanation):
        """
        We resolve a `claim` in 3 steps:
            - Collect all pending rules for which the first body literal is a
              generalization of this claim; resolve the rule with that claim
              (apply the substitution that unifies the claim and the first body
              literal to the rest of the pending rule). If that resolved
              pending rule is a fact, add it as a claim, otherwise add it as a
              new pending rule. We consider this a *bottom up* resolution.
            - Next, collect the stuck goals (a goal is stuck if it was sent off
              to an `InterpretState` for solving, but no solutions have
              returned yet), and check whether this claims matches with any of
              the stuck goals. This would mean the stuck goal is now no longer
              stuck.
            - Finally, the claim might also be a solution to a goal that is not
              stuck (note that subgoals get resolved via the pending rules they
              are necessarily part of, this is not the case for the top goal
              queries).

        :parameters:
            - `claim`: an internal representation of a claim, i.e., a list with
              one internal representation of a literal which is in turn again a
              list of integers.

        :returntype:
            `None`

        """
        self.log.debug('inference.resolve_claim: claim {0!s}'
                       .format(self.term_factory.close_literal(prule.clause[0])))
        self.notify()
        candidate_clauses = []
        #parents = self.logical_state.goal_dependencies.get_parents(prule)
        annotation_claim = self.logical_state.db_get_annotation(prule)
        self.log.debug('inference.resolve_claim: annotation_claim({0}) = {1}'
                       .format(prule, annotation_claim))
        if annotation_claim:
            claim_goal = annotation_claim.goal
            self.log.debug('inference.resolve_claim: claim_goal: {0}'.format(claim_goal))
            fgoal = model.freeze(claim_goal)
            self.logical_state.db_add_claim_to_goal(claim_goal, prule, explanation)
            candidate_clauses = self.logical_state.goal_dependencies.get_parents(fgoal)
            self.log.debug('inference.resolve_claim: candidate_clauses = {0}'.format(candidate_clauses))
        # else:
        #     candidate_clauses = index.get_candidate_generalizations(self.logical_state.db_get_pending_rules_index(), claim[0])
        self.log.debug('inference.resolve_claim: candidate_clauses = {0}'
                       .format(candidate_clauses))
        for candidate in candidate_clauses:
            self.propagate_claims(claim_goal, candidate)
            
    def propagate_claim_to_pending_clause(self, claim, claim_expl, candidate):
        """
        Propagation step from a claim for a subgoal for a pending rule (candidate)
        to the generate a new pending rule. 
        """
        clause = claim.clause if isinstance(claim, graph.PendingRule) else claim
        self.log.debug('inference.propagate_claim_to_pending_clause: claim = {0}, candidate = {1}'
                      .format(self.term_factory.close_literals(clause),
                              self.term_factory.close_literals(candidate.clause)))
        subst = model.get_unification_l(clause[0],candidate.clause[1])
        self.log.debug('inference.resolve_claim: candidate {0!s}: {1}'
                      .format([str(c) for c in self.term_factory.close_literals(candidate.clause)], subst))
        if model.is_substitution(subst):
            new_clause = model.remove_first_body_literal(candidate.clause, subst, self.term_factory)
            cand_expl = self.logical_state.db_get_explanation(candidate)
            assert cand_expl[0] != "None"
            #claim_expl = self.logical_state.db_get_explanation(claim)
            assert claim_expl[0] != "None"
            explanation = model.create_resolution_bottom_up_explanation(candidate, claim, claim_expl)
            # NSH: db_add_claim_to_goal has already been done above
            # update the subgoal (candidate[1]) with the found claim
            # self.logical_state.db_add_claim_to_goal(candidate[1], claim)
            self.increase_subgoalindex(candidate)
            candidate_annotation = self.logical_state.db_get_annotation(candidate)
            parent_goal = candidate_annotation.goal
            self.add_pending_rule(new_clause, explanation, parent_goal)
            #self.move_stuck_goal_to_goal(candidate.clause[1])
            
    #NSH: This is deadcode - it's no longer called from anywhere.
    #It needs to be revised if it is ever used.  
    def resolve_pending_rule(self, rule):
        """
        This is symmetrical to a part of what
        :func:`etb.datalog.inference.Inference.resolve_claim` does: when adding
        a pending rule, we try to resolve any existing claims with the first
        body literal of that pending rule, and you add a new pending rule (or
        claim if the resulting pending rule became a fact).

        :parameters:
            - `rule`: an internal representation of a rule, i.e., a list of
              literals (which are lists of integers). The first element of the
              list is the head of the rule.

        :returntype:
            `None`
        """
        self.log.debug('inference.resolve_pending_rule {0}'
                      .format([str(c) for c in self.term_factory.close_literals(rule)]))
        self.notify()
        candidate_claims = index.get_candidate_specializations(self.logical_state.db_get_claims_index(), rule[1])

        for candidate in candidate_claims:
            subst = model.get_unification_l(candidate[0], rule[1])
            # self.log.debug('inference.resolve_pending_rule candidate {0}'
            #               .format([str(c) for c in self.term_factory.close_literals(candidate)]))
            # self.log.debug('inference.resolve_pending_rule subst {0}'
            #               .format(dict([(self.term_factory.get_symbol(v),
            #                              str(self.term_factory.get_symbol(a))) for v, a in subst.items()])))
            if model.is_substitution(subst):
                new_clause = model.remove_first_body_literal(rule,subst, self.term_factory)
                rule_expl = self.logical_state.db_get_explanation(rule)
                assert rule_expl[0] != "None"
                cand_expl = self.logical_state.db_get_explanation(candidate)
                assert cand_expl[0] != "None"
                explanation = model.create_resolution_bottom_up_explanation(rule, candidate)
                # self.log.debug('inference.resolve_pending_rule new_clause {0}: {1}'
                #                      .format(new_clause, explanation))
                self.logical_state.db_add_claim_to_goal(rule[1], candidate, explanation)
                if model.is_fact(new_clause):
                    self.add_claim(new_clause, explanation)
                    # increase the propogation index also for claims (not only
                    # for pending rules)
                    self.increase_subgoalindex(rule)
                else:
                    self.add_pending_rule(new_clause, explanation)



    def resolve_goal(self, goal):
        """
        When adding a `goal`, we do 2 things:
            - we check the Datalog rules (the KB rules  -- *not* the pending
              rules but the rules and facts that make up the actual KB), and
              introduce any pending rules if we find rules for which the head
              matches the goal. Note that
              :func:`etb.datalog.inference.Inference.add_pending_rule` will
              introduce a new goal consisting of its first body literal (thus
              obtaining a top-down push of goals).
            - we check whether any existing claims match this goal via
              :func:`etb.datalog.inference.Inference.resolve_goal_with_existing_claims`.

        :parameters:
            - `goal`: a goal is an internal representation of a literal, i.e.,
              a list of integers.

        :returntype:
            `True` if the function managed to resolve the goal with any pending
            rule or any claim; `False` otherwise

        """
        self.log.debug('inference.resolve_goal: goal {0}'.format(self.term_factory.close_literal(goal)))
        self.notify()
        result = False
        # Try to resolve with Rules
        candidate_rules = index.get_candidate_matchings(self.logical_state.db_get_rules_index(), goal)
        for candidate in candidate_rules:
            # self.log.debug('inference.resolve_goal: candidate {0}'
            #                      .format([str(c) for c in self.term_factory.close_literals(candidate)]))
            off = model.offset(candidate)
            disjoint_goal = model.shift_literal(goal, off)
            
            subst = model.get_unification_l(candidate[0], disjoint_goal)
            self.log.debug('inference.resolve_goal: subst {0}'
                          .format(dict([(self.term_factory.get_symbol(v),
                                         str(self.term_factory.get_symbol(a))) for v, a in list(subst.items())])))
            if model.is_substitution(subst):
                result = True
                pending_rule = model.apply_substitution_c(subst, candidate, self.term_factory)
                self.log.info('unify goal {1}\n  with rule {2}\n  yields pending rule {0}'
                              .format([str(c) for c in
                                       self.term_factory.close_literals(pending_rule)],
                                      self.term_factory.close_literal(goal),
                                      [str(c) for c in
                                       self.term_factory.close_literals(candidate)]))
                explanation = model.create_resolution_top_down_explanation(candidate, goal)
                self.add_pending_rule(pending_rule, explanation, goal)

        # Try to resolve with Claims
        resolved_with_claims = True #self.resolve_goal_with_existing_claims(goal)
        if resolved_with_claims:
            result = True

        # when we try to resolve we set it as RESOLVED
        # self.log.debug('inference.resolve_goal: setting {0}: RESOLVED'
        #                      .format(self.term_factory.close_literal(goal)))
        self.set_goal_to_resolved(goal)

        return result

    def resolve_goal_with_rule(self, goal, rule):
        """
        This is a specialization of
        :func:`etb.datalog.inference.Inference.resolve_goal` where we have a
        fixed rule that we examine (does the head of that rule match the goal,
        if so, we add a pending rule). This is used in
        :func:`etb.datalog.inference.Inference.add_rule`.

        :parameters:
            - `goal`: a goal is an internal representation of a literal, i.e.,
              a list of integers.
            - `rule`: a rule is an internal representation of a rule, i.e., a
              list of literals (each literal is a list of integers).

        :returntype:
            `True` if the function managed to match the `goal` with the head of
            the `rule`; `False` otherwise

        """
        self.notify()
        result = False
        off = model.offset(rule)
        disjoint_candidate = model.shift_literal(goal, off)
        subst = model.get_unification_l(disjoint_candidate, rule[0])
        if model.is_substitution(subst):
            result = True
            new_clause = model.apply_substitution_c(subst, rule, self.term_factory)
            self.add_pending_rule(new_clause, model.create_resolution_top_down_explanation(rule, goal), goal)

        self.log.debug('inference.resolve_goal_with_rule: setting {0}: RESOLVED'
                       .format(goal))
        self.set_goal_to_resolved(goal)
        
        return result

    def resolve_goal_with_existing_claims(self, goal):
        """
        Try to resolve a `goal` with any existing claims. In other words, verify
        whether the `goal` can be solved by any existing claims`.

        :parameters:
            - `goal`: a goal is an internal representation of a literal, i.e.,
              a list of integers.

        :returntype:
            - `True` if at least one claim was found to be a solution for the
              `goal`; `False` otherwise.

        """
        self.notify()
        result = False
        candidate_claims = index.get_candidate_matchings(self.logical_state.db_get_claims_index(), goal)
        for candidate in candidate_claims:
            subst = model.get_unification_l(candidate.clause[0], goal)
            if model.is_substitution(subst):
                self.logical_state.db_add_claim_to_goal(goal, candidate)
                result = True
        return result



    def push_no_solutions(self, goal):
        """
        Indicate to the Inference object that this `goal` has no solutions.
        This effectively just calls :func:`move_stuck_goal_to_goal` in
        order to declare the goal unstuck.

        :parameters:
            - `goal`: a goal is an internal representation of a literal, i.e.,
              a list of integers.

        :returntype:
            `None`
        """
        self.move_stuck_goal_to_goal(goal)
        self.notify()

    def add_goal(self, goal):
        """
        We add a goal to the `Inference` state if no renaming of that goal is
        already present (if such a renaming is present we return without doing
        aything). Otherwise, adding a goal triggers resolution as
        follows:

            - if the `goal` is interpreted (according to the
              `interpret_state`), then we declare the goal as stuck and call
              :func:`etb.interpret_state.interpret_goal_somewhere` to let the
              `InterpretState` interpret the external representation of this
              goal. We make sure that in any case this goal (even though it is
              interpreted) is resolved against existing claims as some
              `InterpretState` might have delivered matching claims for this
              goal earlier in the process (we use
              :func:`etb.datalog.inference.Inference.resolve_goal_with_existing_claims`
              to that purpose).
            - if the `goal` is not interpreted, we set out to resolve the goal
              using :func:`etb.datalog.inference.Inference.resolve_goal`.

        :parameters:
            - `goal`: a goal is an internal representation of a literal, i.e.,
              a list of integers.

        :returntype:
            `None`

        """
        if self.engine.SLOW_MODE:
            self.engine.log.debug('Adding Goal %s:', self.term_factory.close_literal(goal))
            time.sleep(self.engine.SLOW_MODE)
        self.log.debug('inference.add_goal: {0}'.format(self.term_factory.close_literal(goal)))

        # If the goal is already present
        if self.logical_state.is_renaming_present_of_goal(goal):
            self.log.debug('Renaming of goal {0} is present.'
                           .format(self.term_factory.close_literal(goal)))
            # Do nothing, is_renaming_present_of_goal is checked also in
            # is_completed and get_claims_matching_goal
            return
        # Add the goal to the goal dependencies here
        self.logical_state.goal_dependencies.add_goal(goal)

        # Check whether the goal is valid if it is interpreted
        external_goal = self.term_factory.close_literal(goal)
        if (self.interpret_state and
            self.interpret_state.is_interpreted(external_goal) and
            not self.interpret_state.is_valid(external_goal)):
            self.log.info("Inference.add_goal: the goal %s is interpreted but is not valid. Engine is not adding it." % external_goal)
            return

        # Check whether the goal is interpreted:
        if self.interpret_state and self.interpret_state.is_interpreted(external_goal):
            # the interpret_state should unstuck the below again: make it stuck
            # before you interpret!
            self.log.debug('stuck goal {0!s}'.format(external_goal))
            self.logical_state.db_add_stuck_goal(goal)

            self.interpret_state.interpret_goal_somewhere(external_goal, goal, self.engine)
            # Set it as resolved (means we've dealt with it)
            # make sure to also interpret it against existing claims (something
            # might already have been added in the past by external
            # machineries)
            #self.resolve_goal_with_existing_claims(goal)
            # self.log.debug('inference.add_goal: setting {0!s}: RESOLVED'
            #                      .format(external_goal))
            if not self.engine.is_stuck_goal(external_goal):
                self.set_goal_to_resolved(goal)

        else:
            self.log.info('goal {0!s}'.format(external_goal))
            self.logical_state.db_add_goal(goal)
            # self.log.debug('inference.add_goal: resolve_goal({0!s})'
            #                      .format(external_goal))
            self.resolve_goal(goal)
        # removed below: goals that are false are not stuck (only interpreted
        # ones can be stuck)
        #if not result:
        #    # Goal is considered stuck
        #    self.logical_state.db_move_goal_to_stuck(goal)

        if self.engine.CLOSE_DURING_INFERENCING:
            self.engine.close()



    def add_errors(self, goal, errors):
        """
        Adding a list `errors` for a `goal` to the engine. Note that we cannot
        reuse :func:`etb.datalog.inference.Inference.add_claims` as an error claim
        does not necessarily match a goal (for example, it would have a
        predicate name *error*). We therefore manually force the errors to be part of the
        claims of the goal.

        :parameters:
            - `goal`: a list of integers representing the internal
              representation of a goal
            - `errors`: a list of pairs, where the first item of the pair is a
              list containing 1 internal representation of a literal (i.e., it
              is a list containing a list of positive integers), and the second
              item of the pair is the reason for the error).

        :returntype:
            `None`
        """

        for error in errors:
            self.add_error(goal, error[0], error[1])

    def add_claims(self, claims):
        """
        We add the `claims` atomatically to the `Inference` object. The fact
        that this atomatically ensures that any closing or completing algorithm
        does not conclude too early that the goal is completed (we want all
        claims to already have arrived at the subgoal). Each claim gets added
        using :func:`etb.datalog.inference.Inference.add_claim`.

        :parameters:
            - `claims`: a list of claims, where each claim is a list consisting
              of 1 literal (a list of integers).

        :returntype:
            `None`
        """
        for item in claims:
            self.add_claim(item[0], item[1])

    def add_error(self, goal, error, explanation):
        """
        Add an error claim to the goal.

        :parameters:
            - `goal`: an internal representation of a goal
            - `error`: an internal representation of a literal representing the
              error
            - `explanation`: the explanation for the claim

        :returntype:
            `None`
        """
        if not self.logical_state.db_mem_claim(error):
            self.logical_state.db_add_clause(error, explanation)
            self.logical_state.db_add_claim(error)
            self.logical_state.db_add_claim_to_goal(goal, error)
            self.move_stuck_goal_to_goal(goal)

    def add_claim(self, prule, explanation, quiet=False):
        """
        Adding a `claim` with a certain `explanation` for that claim involves
        adding it to the general DB of clauses (to store the explanation) using
        :func:`etb.datalog.model.LogicalState.db_add_clause`, to the DB of
        claims using :func:`etb.datalog.model.LogicalState.db_add_claim`. We
        subsequently try to resolve the claim using
        :func:`etb.datalog.inference.Inference.resolve_claim`.

        :parameters:
            - `prule`: an internal representation of a claim, i.e., a list with
              one internal representation of a literal which is in turn again a
              list of integers.
            - `explanation`: created using
              :func:`etb.datalog.model.create_resolution_bottom_up_explanation`,
              :func:`etb.datalog.model.create_resolution_top_down_explanation`,
              :func:`etb.datalog.model.create_axiom_explanation`,
              :func:`etb.datalog.model.create_external_explanation`, or just a
              :class:`etb.terms.Term` (in the latter case, we will not be able
              to use to derive an explanation tree from the claim).

        :returntype:
            `None`

        .. todo::
            Check code such explanations can always be also
            :class:`etb.terms.Term`.

        """
        if self.engine.SLOW_MODE:
            # self.log.debug('Adding Claim %s:', self.term_factory.close_literal(claim[0]))
            time.sleep(self.engine.SLOW_MODE)

        assert(isinstance(prule, graph.PendingRule))

        # Only add when the claim was not added yet
        if True: #not self.logical_state.db_mem_claim(claim):
            claimlit = self.term_factory.close_literal(prule.clause[0])
            self.log.debug('inference.add_claim: not added yet: {0!s}'.format(claimlit))
            self.log.debug('Adding Claim {0}'.format(claimlit))
            self.log.debug('Reason {0}'
                           .format(self.term_factory.close_explanation(explanation)))
            if not quiet:
                self.engine.log.debug("Inference determined that internal claim %s is not yet present", prule.clause[0])
            # Then first add it to the set of all things for which explanations
            # need to be stored (`db_all` -- note that `db_all` is not used for
            # reasoning)
            self.logical_state.db_add_clause(prule, explanation)
            # and add it to the DB of claims
            self.logical_state.db_add_claim(prule)
        # Then resolve the claim against the pending rules (this might in
        # turn add new pending rules)
        self.log.debug('inference.add_claim: before resolve_claim {0!s}'
                       .format(self.term_factory.close_literals(prule.clause)))
        self.resolve_claim(prule, explanation)
        # self.log.debug('inference.add_claim: after resolve_claim {0!s}'
        #               .format(self.term_factory.close_literal(claim[0])))

        # if self.engine.CLOSE_DURING_INFERENCING:
        #     self.engine.close()
        # self.log.debug('inference.add_claim: done {0!s}'
        #               .format(self.term_factory.close_literal(claim[0])))


    def add_rule(self, rule, explanation):
        """
        We add a new KB rule (as appearing in for example a file containing a
        Datalog program) -- not a pending rule. This distinguishes between
        rules that are facts (just a head literal) and others. The former are
        treated as claims, the latter as full-fledged rules.

        :parameters:
            - `rule`: an internal representation of a rule (a list of literals
              -- each literal is a list of integers)
            - `explanation`: the same as in
              :func:`etb.datalog.inference.Inference.add_claim`.

        :returntype:
            `None`

        """
        if not self.logical_state.db_mem(rule):
            self.logical_state.db_add_clause(rule, explanation)

            # if model.is_fact(rule):
            #    self.logical_state.db_add_claim(rule)
            #    self.resolve_claim(rule)

            # else:
            self.logical_state.db_add_rule(rule)
            # Check goals (done or stuck) to verify with this new rule now
            # resolves any of the goals
            # First from the done goals:
            clause = rule.clause if isinstance(rule, graph.PendingRule) else rule
            candidate_goals = index.get_candidate_matchings(self.logical_state.db_goals, clause[0])
            for candidate in candidate_goals:
                self.resolve_goal_with_rule(candidate, clause)
                # Now the stuck goals
                candidate_goals = index.get_candidate_matchings(self.logical_state.db_stuck_goals, clause[0])
            for candidate in candidate_goals:
                result = self.resolve_goal_with_rule(candidate, rule)
                if result:
                    self.move_stuck_goal_to_goal(candidate)

    def move_stuck_goal_to_goal(self, goal):
        self.logical_state.db_move_stuck_goal_to_goal(goal)
        self.set_goal_to_resolved(goal)
        annot = self.logical_state.db_get_annotation(goal)
        assert annot and annot.status == graph.Annotation.RESOLVED

    def add_pending_rule(self, rule, explanation, parent_goal):
        """
        Add a pending rule for reasoning. We appropriately update the goal
        dependency graph depending on whether the explanation is a top down
        explanation or a bottom up resolution. In all cases, we push the first
        body literal of the `rule` to the Inference object using
        :func:`etb.datalog.inference.Inference.add_goal`.

        :parameters:
            - `rule`: an internal rule (a list of lists of integers)
            - `explanation`: see
              :func:`etb.datalog.inference.Inference.add_claim`.

        :returntype:
            `None` or `graph.PendingRule`
        """

        #if self.engine.SLOW_MODE:
        #    self.log.debug('Engine 3 Adding Pending Clause %s:', self.term_factory.close_literals(rule))
        #    time.sleep(self.engine.SLOW_MODE)

        # Add it to all clauses (for its explanation)
        self.log.debug('inference.add_pending_rule: rule {0}'
                       .format([str(c) for c in self.term_factory.close_literals(rule)]))
        self.log.debug('inference.add_pending_rule: explanation {0}'.format(explanation))
        parent_goal_claims = self.get_claims_matching_goal(parent_goal)
        self.log.debug('inference.add_pending_rule: parent_goal_claims {0}'.format(parent_goal_claims))
        parent_goal_claim_literals = parent_goal_claims
        
        if model.is_ground(rule[0]) and rule[0] in parent_goal_claim_literals:
            #do nothing if pending rule has a ground head that is already a claim
            self.log.debug('inference.add_pending_rule: pending rule subsumed by existing claim')
            return None
        # Add it to the db of pending rules (important for for example
        # `add_claim` which uses that db to resolve pending rules against claims)
        prule = self.logical_state.db_add_pending_rule(rule)
        assert isinstance(prule, graph.PendingRule)
        assert self.logical_state.db_get_annotation(prule)
        self.logical_state.db_add_clause(prule, explanation)
        # the subgoal to be added (rule[1] or a renaming if it already exists)
        new_subgoal = False
        if not model.is_fact(rule):
            subgoal = self.logical_state.is_renaming_present_of_goal(rule[1])
            if not subgoal:
                # it's new:
                subgoal = rule[1]
                new_subgoal = True

        self.log.debug('inference.add_pending_rule: explanation = {0}'
                       .format(explanation))
        # Add the goal dependency if the pending rule originates from a goal
        if explanation and model.is_top_down_explanation(explanation):
            original_goal = model.get_goal_from_explanation(explanation)
            assert isinstance(prule, graph.PendingRule)
            self.logical_state.db_add_goal_to_pending_rule(original_goal, prule)
            # update goal of rule to be the original_goal
            self.log.debug('inference.add_pending_rule: calling update_goal top_down: {0}'.format(original_goal))
            self.update_goal(prule, original_goal)
        if explanation and model.is_bottom_up_explanation(explanation):
            originating_rule = model.get_rule_from_explanation(explanation)
            self.logical_state.db_add_pending_rule_to_pending_rule(originating_rule, prule)
            # goal these pending clauses all originate from
            originating_rule_annotation = self.logical_state.db_get_annotation(originating_rule)
            if originating_rule_annotation:
                goal_of_originating_rule = originating_rule_annotation.goal
                self.log.debug('inference.add_pending_rule: calling update_goal bottom_up: {0}'.format(goal_of_originating_rule))
                self.update_goal(prule, goal_of_originating_rule)
            # this means we found a solution to the subgoal (first body
            # literal) of model.get_rule_from_explanation(explanation); so we
            # update subgoalindex of that rule with 1 (one solution propagated)
            # This is already being done in propagate_claim_to_pending_clause
            # self.increase_subgoalindex(originating_rule)
            if not model.is_fact(rule):
                self.updategT(subgoal, rule)
        if self.engine.SLOW_MODE:
            self.log.debug('Slowing down before updating goal dependencies by adding pending rule to subgoal edge.')
            time.sleep(self.engine.SLOW_MODE)


        # Further add the first literal of the pending rule to the goals (in
        # the Inference engine, so this potentially triggers further
        # deduction)
        if model.is_fact(rule):
            self.add_claim(prule, explanation)
        else:  #then subgoal must be set
            self.log.debug('inference:subgoal: {0} from pending rule: {1}'.format(subgoal, rule))
            self.logical_state.db_add_pending_rule_to_goal(prule, subgoal)
            fsubgoal = model.freeze(subgoal)
            self.updategT(subgoal, prule)

            # The goal dependencies graph has been updated at this point: unlock
            
            # and continue by adding this goal
            if new_subgoal:
                self.add_goal(subgoal)
            else:
                self.log.debug('inference.add_pending_rule with known subgoal: {0}'
                               .format(self.term_factory.close_literal(subgoal)))
                self.propagate_claims(subgoal, prule)

            # # Try to resolve it with existing claims (this is missing in the
            # # original engine3 description and breaks for example
            # # test_simple_program in test_engine.py)
            # self.resolve_pending_rule(rule)

        if self.engine.CLOSE_DURING_INFERENCING:
            self.engine.close()
        return prule

    def propagate_claims(self, subgoal, prule):
        """
        Applies the propagate rule to propagate any existing claims from an
        already extant subgoal to the rule to create new pending rules. 
        """
        self.log.debug('inference.propagate_claims: subgoal: {0}'
                      .format(self.term_factory.close_literal(subgoal)))
        self.log.debug('inference.propagate_claims: rule: {0}'
                      .format(self.term_factory.close_literals(prule.clause)))
        fsubgoal = model.freeze(subgoal)
        annotation_subgoal = self.logical_state.db_get_annotation(fsubgoal)
        fclause = prule.clause
        subgoal_index = self.logical_state.goal_dependencies.get_subgoal_index(prule)
        self.log.debug('inference.propagate_claims: annotation_subgoal = {0}, subgoal_index = {1}'.format(annotation_subgoal, subgoal_index))
        if annotation_subgoal:
            subgoal_claims = annotation_subgoal.claims
            subgoal_explanations = annotation_subgoal.explanations
            max_subgoal_claims = len(subgoal_claims)
            assert len(subgoal_explanations) == max_subgoal_claims, 'length mismatch: {0} != {1}'.format(max_subgoal_claims, len(subgoal_explanations))
            self.log.debug('inference.propagate_claims: subgoal_claims = {}'
                           .format([self.term_factory.close_literals(
                               sc.clause if isinstance(sc, graph.PendingRule) else sc)
                                    for sc in subgoal_claims]))
            self.log.debug('inference.propagate_claims: max_subgoal_claims = {}'.format(max_subgoal_claims))
            for i in range(subgoal_index, max_subgoal_claims):
                self.propagate_claim_to_pending_clause(subgoal_claims[i], subgoal_explanations[i], prule)
            
    def check_stuck_goals(self, newpreds):
        """
        Force the inferencing to look at the stuck goals to see if any of the
        newpreds can be run against them.

        .. seealso::
            :func:`etb.datalog.inference.Inference.add_goal`

        :returntype:
            `None`

        """
        stuck_goals = self.logical_state.db_get_all_stuck_goals()
        for goal in stuck_goals:

            external_goal = self.term_factory.close_literal(goal)

            if (external_goal.first_symbol() in newpreds and
                self.interpret_state and
                self.interpret_state.is_interpreted(external_goal)):
                self.interpret_state.interpret_goal_somewhere(external_goal, goal, self.engine)
                # no need to put on stuck as it is already stuck
                # self.resolve_goal_with_existing_claims(goal)
                # self.log.debug('inference.check_stuck_goals: setting {0}: RESOLVED'
                #               .format(goal))
                self.set_goal_to_resolved(goal)

            # self.log.debug('inference.check_stuck_goals: resolve_goal({0})'
            #                      .format(goal))
            result = self.resolve_goal(goal)
            if result:
                # Goal can be unstuck
                self.move_stuck_goal_to_goal(goal)



    def increase_subgoalindex(self, pending_rule):
        """
        Convenience function that increases the field `subgoalindex` of the
        annotation corresponding to the `pending_rule`.

        :parameter:
            - `pending_rule`: an internal representation of a rule

        :returntype:
            `None`
        """
        annotation = self.logical_state.db_get_annotation(pending_rule)
        #NSH: This should not happen. The function should only be called on registered pending rules
        # if not annotation:
        #     self.logical_state.goal_dependencies.add_pending_rule(pending_rule)
        #     annotation = self.logical_state.db_get_annotation(pending_rule)
        if annotation:
            annotation.inc_subgoalindex()

    def set_goal_to_resolved(self, goal):
        self.set_status_goal(goal, graph.Annotation.RESOLVED)

    def set_status_goal(self, goal, status):
        """
        Convenience function that sets the field `status` of the
        annotation corresponding to the `goal`.

        :parameter:
            - `goal`: an internal representation of a rule
            - `status`: one of `Annotation.OPEN`, `Annotation.CLOSED`,
              `Annotation.RESOLVED`, or `Annotation.COMPLETED`.

        :returntype:
            `None`
        """
        annotation = self.logical_state.db_get_annotation(goal)
        if annotation:
            annotation.status = status
        else:
            self.log.info('{0} has no annotation'.format(goal))

    def updategT(self, subgoal, clause):
        """
        Add `clause` to the `gT` of `clause.Goal` with key `subgoal`.

        .. seealso::
            Closing algorithm specification

        """
        annotation_clause = self.logical_state.db_get_annotation(clause)
        if annotation_clause:
            goal = annotation_clause.goal
            if goal:
                annotation = self.logical_state.db_get_annotation(goal)
                if annotation:
                    key = model.freeze(subgoal)
                    if not key in annotation.gT:
                        annotation.gT[key] = []
                    annotation.gT[key].append(clause)

    def update_goal(self, pending_clause, goal):
        """
        Convenience function that sets the field `goal` of the
        annotation corresponding to the `pending_clause`.

        :parameter:
            - `goal`: an internal representation of a goal
            - `pending_clause`: an internal representation of a rule

        :returntype:
            `None`
        """
        assert isinstance(pending_clause, graph.PendingRule)
        annotation_pending = self.logical_state.db_get_annotation(pending_clause)
        self.log.debug('inference.update_goal: clause: {0}, goal: {1}, annotation: {2}'
                       .format(pending_clause, goal, annotation_pending))
        if True: #annotation_pending:
            annotation_pending.goal = goal


    # == Showing Current State of the Inferencing ==

    def get_claims(self):
        """
        Get currently known claims. Relays to
        :func:`etb.datalog.model.LogicalState.db_get_all_claims`.

        :returntype:
            a list of internal representations of claims (a claim is a list of
            a list of integers)
        """
        return self.logical_state.db_get_all_claims()

    def get_stuck_goals(self):
        """
        Get currently known stuck goals. Relays to
        :func:`etb.datalog.model.LogicalState.db_get_all_stuck_goals`.

        :returntype:
            a list of internal representations of goals (a goal is a list of
            integers)
        """
        return self.logical_state.db_get_all_stuck_goals()

    def is_stuck_goal(self, goal):
        """
        Tells whether a goal is stuck. Relays to
        :func:`etb.datalog.model.LogicalState.is_stuck_goal`.

        :parameters:
            - `goal`: an internal representation of a goal

        :returntype:
            `True` or `False`
        """
        return self.logical_state.is_stuck_goal(goal)

    def no_stuck_subgoals(self, goal):
        """
        Determines whether there are no stuck subgoals for a `goal`. Relays to
        :func:`etb.datalog.model.LogicalState.no_stuck_subgoals`.

        :parameters:
            - `goal`: an internal representation of a goal

        :returntype:
            - `True` if there are no stuck subgoals; `False` otherwise

        """
        return self.logical_state.no_stuck_subgoals(goal)

    def get_goals(self):
        """
        Get the list of goals currently known to Inference object.

        :returntype:
            a list of goals
        """
        return self.logical_state.db_get_all_goals()

    def get_rules(self):
        """
        Get the list of rules currently known to Inference object.

        :returntype:
            a list of rules
        """
        return self.logical_state.db_get_rules()

    def get_pending_rules(self):
        """
        Get the list of pending rules currently known to Inference object.

        :returntype:
            a list of pending rules
        """
        return self.logical_state.db_get_pending_rules()

    def close(self):
        """
        The Closing Algorithm. Relays to
        :func:`etb.datalog.model.LogicalState.close`.

        :returntype:
            `None`
        """
        self.logical_state.close()

    def complete(self):
        """
        The Completing Algorithm. Relays to
        :func:`etb.datalog.model.LogicalState.complete`.

        :returntype:
            `None`
        """
        self.logical_state.complete()

    def is_completed(self, goal):
        """
        Determines whether the `goal` is completed.

        :parameters:
            - `goal`: an internal representation of a goal

        :returntype:
            - `True` if the goal is completed; `False` otherwise

        """
        return self.logical_state.is_completed(goal)


    def get_claims_matching_goal(self, goal):
        """
        Get the claims matching a goal. We get this directly from the
        annotation corresponding to the goal (we kept those annotations up to
        date, to contain the matching claims).

        :parameters:
            -`goal`: an internal representation of a `goal`.

        :returntype:
            - a list of internal representations of claims
        """
        with self.logical_state.goal_dependencies:
            pgoal = self.logical_state.is_renaming_present_of_goal(goal)
            if pgoal:
                annotation = self.logical_state.db_get_annotation(pgoal)
                pannotation = self.logical_state.db_get_annotation(goal)
            else:
                annotation = self.logical_state.db_get_annotation(goal)
            if annotation:
                self.log.debug('Found Annotation for Goal {0} rename {1} with claims {2}'
                              .format(self.term_factory.close_literal(goal),
                                      self.term_factory.close_literal(pgoal) if pgoal else None,
                                      annotation.claims))
                return annotation.claims, annotation.explanations
            else:
                self.log.info('No annotation for Goal {0}'
                              .format(self.term_factory.close_literal(goal)))
                return []

    def is_entailed(self, goal):
        """
        Check whether goal is entailed or not.

        .. warning::
            Used only for unit tests
        """
        candidate_claims = index.get_candidate_specializations(self.logical_state.db_claims, goal)
        for claim in candidate_claims:
            if model.is_substitution( model.get_unification_l(claim.clause[0], goal)):
                return True
        return False
