"""Builtin predicates"""

import uuid
import time
import logging
import subprocess
from etb import terms
from etb.wrapper import Tool, Substitutions, Success, Failure, Errors

class Builtins(Tool):
    """Some builtin predicates.
    >>> b = Builtins()
    >>> b.different(terms.mk_term('a'), terms.mk_term('b'))
    [subst()]
    >>> b.different(terms.mk_term('a'), terms.mk_term('a'))
    []
    """

    @Tool.sync
    @Tool.volatile
    @Tool.predicate('+a: value, +b: value')
    def different(self, a, b):
        """Are the two terms different?"""
        if a != b:
            return Success(self)
        else:
            return Failure(self)

    @Tool.sync
    @Tool.volatile
    @Tool.predicate('-a: value, +b: value')
    def equal(self, a, b):
        """Unify the two terms"""
        subst = a.unify(b)
        return Failure(self) if subst is None else Substitutions(self, [subst])

    @Tool.sync
    @Tool.volatile
    @Tool.predicate('a: value, b: value, sum: value')
    def plus(self, a, b, sum):
        """Like Prolog sum; at most one argument may be a variable,
        if none are checks whether sum=a+b, else binds the variable
        accordingly.
        """
        if (a.is_var() and (b.is_var() or sum.is_var())) or (b.is_var() and sum.is_var()):
            return Errors(self, ["Only one variable allowed in plus."])
        if ((not (a.is_var() or a.is_numconst()))
            or (not (b.is_var() or b.is_numconst()))
            or (not (sum.is_var() or sum.is_numconst()))):
            return Errors(self, ["plus expects numbers"])
        if a.is_var():
            return Substitutions(self, [self.bindResult(a, sum.num - b.num)])
        elif b.is_var():
            return Substitutions(self, [self.bindResult(b, sum.num - a.num)])
        elif sum.is_var():
            return Substitutions(self, [self.bindResult(sum, a.num + b.num)])
        else:
            res = sum.num == a.num + b.num
            return Success(self) if res else Failure(self)

    @Tool.sync
    @Tool.volatile
    @Tool.predicate('-token: Value')
    def new(self, tok):
        """Bind the argument to a fresh, unique symbol."""
        if tok.is_var():
            return Substitutions(self, [{tok: terms.StringConst(uuid.uuid4())}])
        else:
            return Failure(self)  # always fails with a const argument

    @Tool.volatile
    @Tool.predicate('-token: Value')
    def now(self, tok):
        """Binds the argument to the current unix timestamp
        (of this computer)"""
        if tok.is_var():
            return Substitutions(self, [{tok: terms.StringConst(time.time())}])
        else:
            return Failure(self)

    @Tool.predicate('+cmd: Value, -result: Value')
    def popen(self, cmd, result):
        """Runs a shell command and get the (text) result back."""
        if not cmd.is_array():
            return Failure(self)  # TODO error claims
        cmd = list(unicode(x) for x in cmd.get_args())
        try:
            shell_res = subprocess.check_output(cmd)
            return Substitutions(self, [{result: terms.StringConst(shell_res)}])
        except subprocess.CalledProcessError as e:
            return Failure(self)  # TODO error claims

    @Tool.predicate('+cmd: Value, +timestamp, -result: Value')
    def popen_at(self, cmd, timestamp, result):
        """Runs a shell command and get the (text) result back.  The timestamp
        can be anything, its purpose is to repeat an action that would
        otherwise be cached (like several printf of the same string)
        """
        if not cmd.is_array():
            return Failure(self)  # TODO error claims
        cmd = list(unicode(x) for x in cmd.get_args())
        try:
            shell_res = subprocess.check_output(cmd)
            return Substitutions(self, [{result: terms.StringConst(shell_res)}])
        except subprocess.CalledProcessError as e:
            return Failure(self)  # TODO error claims

    @Tool.volatile
    @Tool.predicate('+goal: value')
    def delete_claim(self, literal):
        """Delete all claims backing the given literal from the claim table."""
        assert literal.is_ground()
        with self._etb.logic_state:
            claims = list(self._etb.logic_state.match_claims_against(literal))
            logging.getLogger('etb.builtins').info(
                'remove %d claims matching %s', len(claims), literal)
            self._etb.logic_state.delete_claims(claims)
        return Substitutions(self, [terms.Subst()])

    @Tool.sync
    @Tool.volatile
    @Tool.predicate('+literal: value, +reason: value')
    def assert_claim(self, literal, reason):
        """Add the claim 'literal because reason' to the claim table"""
        assert literal.is_ground()
        with self._etb.logic_state:
            claim = terms.Claim(literal, reason)
            self._etb.logic_state.add_claim(claim)
        return Success(self)

    @Tool.sync
    @Tool.volatile
    @Tool.predicate('+goal: value, -facts: value')
    def match_facts(self, goal, facts):
        """Put in facts the sorted list of facts that match goal."""
        # get the actual list of facts (sorted)
        print goal, facts
        _, goal = goal.negative_rename()  # avoid collisions
        with self._etb.logic_state:
            found_facts = list(subst(goal) for subst in \
                               self._etb.logic_state.match_facts_against(goal))
        print found_facts
        found_facts.sort()
        found_facts = terms.Array(found_facts)
        # bind/check
        if facts.is_var():
            return Substitutions(self, [{ facts: found_facts}])
        elif facts == found_facts:
            return Success(self)
        else:
            return Failure(self)

    @Tool.sync
    @Tool.predicate('+pred: value')
    def volatile(self, pred):
        """Set the predicate volatile."""
        if not isinstance(pred, terms.Scalar):
            self.fail('%s should be a Scalar' % pred)
        pred.set_volatile()
        return Success(self)

def register(etb):
    etb.add_tool(Builtins(etb))
