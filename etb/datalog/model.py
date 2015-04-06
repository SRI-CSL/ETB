""" Maintaining the Logical State

This module provides the :class:`etb.datalog.model.TermFactory` that maintains
the internal representation of :class:`etb.terms.Term`s and symbols used in
terms. The class :class:`etb.datalog.model.LogicalState` keeps track of rules,
pending rules, claims, goals, stuck goals, goal dependencies used by the
Datalog engine.

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

import index
import graph
#from .. import terms
from etb import terms
from collections import deque
import threading
import logging



class TermFactory(object):
    def __init__(self):
        """
        This class provides mappings from :class:`etb.terms.Term` to integers
        and vice versa, as well as from :class:`etb.terms.Term` to the internal
        representation (a list of integers).
        """

        # Integer to Term dictionary for storing the corresponding Term (constant
        # or variable) associated with an integer.
        self.__i_to_s = {}

        # Term to integer dictionary for storing the integer corresponding to a
        # symbol or variable.
        self.__s_to_i = {}

        # Keeping track of which integer to use for representing symbols.
        self.__const_count = 1
        self.__var_count = -1

        # Shortcutting the correspondence between Literals and Internal
        # representation (2 dictionaries: 1 from hashcons of Literal to Internal
        # Terms and 1 from tuple of Internal representation to Literal).
        # Note that we still need __i_to_s and __s_to_i as we want reuse
        # integers when seeing new Terms.
        self.__literal_to_internal = {}
        self.__internal_to_literal = {}
        self.log = logging.getLogger('etb.datalog.termfactory')

    def show_index(self):
        print "s to i", self.__s_to_i
        print "i to s", self.__i_to_s

    def clear(self):
        """
        Clears the symbol dictionaries (the mapping of integers to symbols and
        variables and vice versa). Resets the counts to determine which integers
        are still up for use.

        :returntype:
            `None`

        """
        self.__i_to_s.clear()
        self.__s_to_i.clear()
        self.__literal_to_internal.clear()
        self.__internal_to_literal.clear()
        self.__const_count = 1
        self.__var_count = -1

    def get_int(self, term):
        """
        Get the corresponding integer for a :class:`etb.terms.Term`.

        :parameters:
            - `term`: a :class:`etb.terms.Term` instance

        :returntype:
            - an integer or `None` if the term is not known by the TermFactory
        """
        if term in self.__s_to_i:
            return self.__s_to_i[term]
        else:
            return None

    def get_symbol(self, integer):
        """
        Get the corresponding :class:`etb.terms.Term` for an integer.

        :parameters:
            - an integer known to the TermFactory; if it is not known, we will
              consider this integer a byproduct of creating new internal
              variables (negative integers) and create a variable `Xi` for the
              integer `i`.

        :returntype:
            :class:`etb.terms.Term`

        """
        assert isinstance(integer, int), '{0} should be an int'.format(integer)
        if integer in self.__i_to_s:
            return self.__i_to_s[integer]
        else: # if the integer is not there (eg from making new internal
            # variables)
            return terms.mk_var("X" + str(integer))

    def add_const(self, symbol):
        """
        Add a constant symbol (a :class:`etb.terms.Term` that is a constant)
        and its corresponding integer to the `__i_to_s` and `__s_to_i`
        dictionaries.  Constant symbols will be identified with positive
        integers.

        :parameters:
            - `symbol`: a :class:`etb.terms.Term` instance

        :returntype:
            - a positive integer
        """
        if not self.__s_to_i.has_key(symbol):
            self.__s_to_i[symbol] = self.__const_count
            self.__i_to_s[self.__const_count] = symbol
            self.__const_count += 1

    def add_var(self, symbol):
        """
        Add a variable (a :class:`etb.terms.Term` that is a variable) and its
        corresponding integer to the `__i_to_s` and `__s_to_i` dictionaries.
        Variables will be identified with negative
        integers.

        :parameters:
            - `symbol`: a :class:`etb.terms.Term` instance

        :returntype:
            - a negative integer
        """
        if not self.__s_to_i.has_key(symbol):
            self.__s_to_i[symbol] = self.__var_count
            self.__i_to_s[self.__var_count] = symbol
            self.__var_count -= 1

    def create_fresh_var_or_const(self, term):
        """
        From a :class:`etb.terms.Term` `term` make sure a new constant or
        variable is created (where created means added to the relevant
        dictionaries of the TermFactory for future reuse).

        :parameters:
            - `term`: a :class:`etb.terms.Term`

        :returntype:
            `None`
        """
        assert isinstance(term, terms.Term), 'term is not a terms.Term in create_fresh_var_or_const'
        if term.is_var():
            self.add_var(term)
        else:
            self.add_const(term)

    def create_fresh_literal(self, lit):
        """
        Given a :class:`etb.terms.Literal` literal `lit`, we know that the literal is not
        yet seen as a whole by the TermFactory (but parts of it may be) -- we
        try to add the necessary symbols to `__i_to_s` and `__s_to_i` and
        return the new internal representation.

        :parameters:
            - `lit`: a :class:`etb.terms.Literal`

        :returntype:
            a list of integers (an *internal* literal)

        """
        assert isinstance(lit, terms.Literal), 'lit is not a terms.Literal in create_fresh_literal'

        predicate = lit.pred
        # a tuple of arguments
        arguments = lit.args

        # predicate should be a const
        assert isinstance(predicate, (terms.StringConst, terms.IdConst)),\
            'predicate {0} (type {1}) is not a terms.StringConst in create_fresh_literal'\
                .format(predicate, type(predicate))
        self.add_const(predicate)
        internal_predicate = self.get_int(predicate)

        internal_literal = [internal_predicate]
        # add each of the arguments (note that "add" means only add when not
        # present yet)
        for arg in arguments:
            if arg.is_var():
                self.add_var(arg)
            if arg.is_const():
                self.add_const(arg)
            else: # in all other cases treat the argument as a constant symbol
                # (also lists for example)
                self.add_const(arg)
            internal_literal += [self.get_int(arg)]

        return internal_literal

    def mk_literal(self, lit):
        """
        Make an internal literal out of `lit`. We first check whether the
        `TermFactory` already knows about this literal. If it does, we look up the
        internal representation. If it doesn't, we create it using
        :func:`etb.datalog.model.TermFactory.create_fresh_literal`.

        :parameters:
            - `lit`: a :class:`etb.terms.Literal`

        :returntype:
            - a list of integers (an *internal* literal)

        """
        assert isinstance(lit, terms.Literal), 'lit is not a terms.Literal in TermFactory.mk_literal'
        internal_literal = self.__literal_to_internal.get(lit.hashcons())
        #self.log.debug('model.mk_literal: external_literal: {0}, internal_literal0: {1}'.format(lit, internal_literal))
        # if the literal was not seen before, it's new
        if not internal_literal:
            internal_literal = self.create_fresh_literal(lit)
            self.__literal_to_internal[lit.hashcons()] = internal_literal
            self.__internal_to_literal[tuple(internal_literal)] = lit
        return internal_literal

    def mk_clause(self, clause):
        """
        Create an internal representation for a :class:`etb.terms.Clause`. We
        call :func:`etb.datalog.model.TermFactory.mk_literal` on the head of
        the clause as well as on the body literals of the clause.

        :parameters:
            - `clause`: a :class:`etb.terms.Clause`

        :returntype:
            a list of internal literals (i.e., a list of lists of integers)

        """
        assert isinstance(clause, terms.Clause), 'clause is not a terms.Clause in mk_clause'
        internal_clause = [self.mk_literal(clause.head)]
        for body_literal in clause.body:
            internal_clause += [self.mk_literal(body_literal)]
        return internal_clause

    def open_literal(self, term):
        """
        For a :class:`etb.terms.Term` `term` that we know to exist, we return
        the internal representation.

        :parameters:
            - `term`: a :class:`etb.terms.Term`

        :returntype:
            a list of integers
        """
        return self.__literal_to_internal.get(term.hashcons())


    def close_literal(self,internal_literal):
        """
        Get the external term representation of the internal literal
        `internal_literal`.

        :parameters:
            - `internal_literal`

        :returntype:
            :class:`etb.terms.Literal`
        """
        t = self.__internal_to_literal.get(tuple(internal_literal))
        # if the internal_literal was newly created during the algorithm
        if not t:
            internal_predicate = internal_literal[0]
            internal_args = internal_literal[1:]
            external_predicate = self.get_symbol(internal_predicate)
            external_args = [self.get_symbol(a) for a in internal_args]
            try:
                t = terms.mk_literal(external_predicate, external_args)
            except Exception as e:
                raise
            return t

    def close_literals(self, internal_literals):
        """
        Call :func:`etb.datalog.model.TermFactory.close_literal` on each
        literal in `internal_literals`.

        :parameters:
            - `internal_literals`: a list of internal literals (i.e., a list of
              lists of integers)

        :returntype:
            a list of :class:`etb.terms.Term` instances
        """
        return map(lambda literal: self.close_literal(literal), internal_literals)

    def readable_clause(self, internal_literals):
        """
        Based on the `internal_literals` a list of lists of integers, return a
        string formed as a clause (i.e., the head/first item of the list is followed by the `:-`
        symbol, followed by the rest of the list/the body).

        :parameters:
            - `internal_literals`: a list of internal literals (i.e., a list of
              lists of integers)

        :returntype:
            a string

        """
        if isinstance(internal_literals, graph.PendingRule):
            internal_literals = internal_literals.clause
        if internal_literals is None:
            return "None"
        list_of_terms = self.close_literals(internal_literals)
        if len(list_of_terms) == 1:
            return str(list_of_terms[0]) + "."
        else:
            return str(list_of_terms[0]) +  " :- " + ",".join(map(lambda literal: str(literal), list_of_terms[1:]))

    def close_explanation(self, internal_explanation):
        """
        Provide the external representation of an internal explanation.

        :parameters:
            - `internal_explanation`: created using
              :func:`etb.datalog.model.create_resolution_bottom_up_explanation`,
              :func:`etb.datalog.model.create_resolution_top_down_explanation`,
              :func:`etb.datalog.model.create_axiom_explanation`,
              :func:`etb.datalog.model.create_external_explanation`, or just a
              :class:`etb.terms.Term`

        :returntype:
            a string
        """
        if isinstance(internal_explanation, basestring):
            return internal_explanation
        elif isinstance(internal_explanation, (terms.Term, terms.Literal)):
            return internal_explanation
        elif isinstance(internal_explanation, tuple) and len(internal_explanation) >= 1:
            type_explanation = internal_explanation[0]
            if type_explanation == "Axiom" or type_explanation == "External" or type_explanation == "None":
                return type_explanation
            elif type_explanation == "ResolutionBottomUp":
                return type_explanation + " with " + self.readable_clause(internal_explanation[1]) + " and " + self.readable_clause(internal_explanation[2])
            elif type_explanation == "ResolutionTopDown":
                return type_explanation + " with " + self.readable_clause(internal_explanation[1]) + " and " + self.readable_clause([internal_explanation[2]])
        else:
            return None

def mk_clause(head, body):
    """
    Out of a `head` literal and a list of `body` literals, we create a clause
    (just an append of `head` and `body`). As such that first element of a list is
    always assumed to be the head of the clause. The rest of the list is the
    body.

    :parameters:
        - `head`: an internal representation of a literal, i.e., a list of
          integers
        - `body`: a list of internal representations of literals

    :returntype:
        a list of internal representations of literals
    """
    return [head] + body

def is_internal_literal(obj):
    return (isinstance(obj, (list, tuple)) and
            all(isinstance(x, int) for x in obj))

def is_internal_clause(obj):
    return (isinstance(obj, (list, tuple)) and
            all(is_internal_literal(x) for x in obj))

def is_fact(clause):
    """
    Check whether a `clause` is a fact (empty body): a `clause` is a fact if
    the length of clause is `1`.

    :parameters:
        - `clause`: a list of internal representations of literals

    :returntype:
        `True` or `False`
    """
    return len(clause) == 1

def is_ground(literal):
    """
    Determine whether a `literal` is ground. Recall that a literal is ground
    when it does not contain any variables, or, in this implementation, when
    all the integers making up the literal list are positive.

    :parameters:
        - `literal`: a list of integers

    :returntype:
        `True` or `False`
    """
    return all( map(lambda x: x > 0, literal) )


def offset(clause):
    """
    The offset of a `clause` is the lowest of all negative integers in a
    clause. If there are no negative integers, it is 0.

    :parameters:
        - `clause`: a list of lists of integers

    :returntype:
        - a positive integer (>= 0)

    Example input and output: ::

        In [18]: c
        Out[18]: [[1, -1], [1, -2, -3]]
        In [19]: offset(c)
        Out[19]: -3
    """
    minimum = min([term for literal in clause for term in literal])
    if minimum < 0:
        return minimum
    else:
        return 0

def shift_literal(literal, offset):
    """
    Shift the `literal` with an `offset`. Shifting only shifts variables (i.e.,
    negative integers).

    :parameters:
        - `literal`: a list or tuple of integers
        - `offset`: a negative integer (or 0)

    :returntype:
        a list or tuple of integers (list or tuple depends on the input
        `literal`)

    Example input and output: ::

        In [30]: shift_literal([1,-1],-3)
        Out[30]: [1, -4]
    """
    if isinstance(literal, list):
        return [ term + offset if term < 0 else term for term in literal]
    elif isinstance(literal, tuple):
        return tuple([ term + offset if term < 0 else term for term in literal])


def find_first_variable_difference(l1, l2):
    """
    Go through both lists `l1` and `l2` and as soon as a variable on position
    `i` in `l1` is met
    that is different from the corresponding variable on position `i` in `l2`; return the
    difference. This will serve as an offset to judge whether 2 literals can be
    made equal by just shifting them with a certain offset.
    We assume `l1` and `l2` have the same length.

    :parameters:
        - `l1`: a list of integers
        - `l2`: a list of integers

    :returntype:
        an integer
    """
    if len(l1) == 0:
        return 0
    elif l1[0] > 0:
        return find_first_variable_difference(l1[1:], l2[1:])
    elif l2[0] > 0:
        return find_first_variable_difference(l1[1:], l2[1:])
    elif l1[0] == l2[0]:
        return find_first_variable_difference(l1[1:], l2[1:])
    else:
        if l1[0] > l2[0]:
            return l1[0] - l2[0]
        else:
            return l2[0] - l1[0]

def get_unification_l(l1,l2):
    """
    Unify a literal `l1`  with another literal `l2`. Note that we assume that the
    variables in both literals are disjoint (or in particular, that the set of
    negative integers in `l1` and `l2` are disjoint). This function returns an
    empty list if no substitution exists otherwise it returns the substitution
    that unifies `l1` and `l2`.

    :parameters:
        - `l1`: a list of integers
        - `l2`: a list of integers

    :returntype:
        a *dict* mapping negative integers to integers to indicate how
        replacing those negative integers results in equal literals

    Example input/output: ::
        In [110]: get_unification_l([1,-1,-2],[1,-3,4])
        Out[110]: {-2: 4, -1: -3}

        In [111]: get_unification_l([1,-1,-1],[1,-2,3])
        Out[111]: {-2: 3, -1: 3}

    """

    def replace_first_by_second(tuples,first,second):
        result = []
        for (a,b) in tuples:
            if a == first:
                result.append((second,b))
            elif b == first:
                result.append((a,second))
            else:
                result.append((a,b))
        return result

    # The predicate symbols are different or the literals have different
    # length: immediate reason for failure.
    if l1[0] != l2[0] or len(l1) != len(l2):
        return None
    else:
        # We are implementing a variation of the algorithm as in
        # [http://artint.info/html/ArtInt_287.html](http://artint.info/html/ArtInt_287.html)
        equality_statements = [(l1[i], l2[i]) for i in range(1,len(l1))]
        substitution = []
        while equality_statements:
            selected = equality_statements.pop()
            first = selected[0]
            second = selected[1]
            if first != second:
                if first >= 0 and second >= 0:
                    return None
                elif first < 0:
                    equality_statements = replace_first_by_second(equality_statements, first, second)
                    substitution = replace_first_by_second(substitution, first, second)
                    substitution.append((first,second))
                elif second < 0:
                    equality_statements = replace_first_by_second(equality_statements, second, first)
                    substitution = replace_first_by_second(substitution, second, first)
                    substitution.append((second,first))
        subst_dict = {}
        for (a,b) in substitution:
            subst_dict[a] = b
        return subst_dict

def is_substitution(subst):
    """
    Unification failed if the substitution returned by
    :func:`etb.datalog.model.get_unification_l` is `None`.

    Example input/output: ::
        In [105]: is_substitution( get_unification_l([1,-1,-1],[4,-2,3]) )
        Out[105]: False

        In [106]: is_substitution( get_unification_l([1,-1,-1],[1,-2,3]) )
        Out[106]: True
    """
    return subst is not None


def substitute(subst, i, term_factory):
    """
    For an integer representing a constant, a list, or a variable, apply the
    substitution (care needs to be takein in case of list terms which are also just
    represented by positive integerst i.

    :parameters:
        - `i`: an integer
        - `subst`: a *dict* mapping negative integers to integers to indicate
          how replacing those negative integers results in equal literals
        - `term_factory`: a :class:`etb.datalog.model.TermFactory` instance to
          properly take care of integers `i` that represent list terms (we need
          to apply that substitution to the list term represented by `i`).

    :returntype:
        - a list of integers

    """
    return_value = i
    if i < 0 and i in subst:
        # a variable
        return_value = subst[i]

    ## Now check for lists!
    if return_value > 0:
        # using terms.py to check whether what we stored for i is actually a
        # list.and get_symbol(i).is_array():
        term = term_factory.get_symbol(return_value)
        if term.is_array():
            new_substituted_integer_list = []
            for list_element in term.get_args():
                # always check whether this list element in itself was also
                # already added
                term_factory.create_fresh_var_or_const(list_element)
                j = term_factory.get_int(list_element)
                if j < 0 and j in subst:
                    new_substituted_integer_list.append( subst[j] )
                else:
                    new_substituted_integer_list.append(j)

            new_args = [ term_factory.get_symbol(si) for si in new_substituted_integer_list ]
            new_term = terms.mk_array(new_args)
            term_factory.add_const(new_term)
            return term_factory.get_int(new_term)
        else:
            return return_value
    else:
        return return_value



def apply_substitution_l(subst,literal, term_factory):
    """
    Apply a substitution to a literal.

    .. seealso::
        :func:`etb.datalog.model.substitute`

    Example input/output: ::

        In [167]: subst = get_unification_l([1,-1,-1,5],[1,-2,3,-5])
        In [168]: subst
        Out[168]: {-5: 5, -2: 3, -1: 3}
        In [169]: apply_substitution_l(subst, [6,-1,-5])
        Out[169]: [6, 3, 5]
    """
    return [ substitute(subst, i, term_factory) for i in literal]

def apply_substitution_c(subst,clause, term_factory):
    """
    Apply a substitution to a clause.

    .. seealso::
        :func:`etb.datalog.model.apply_substitution_l`

    Example input/output: ::

        In [174]: subst
        Out[174]: {-5: 5, -2: 3, -1: 3}

        In [175]: c
        Out[175]: [[1, -1], [1, -2, -3]]

        In [176]: apply_substitution_c(subst, c)
        Out[176]: [[1, 3], [1, 3, -3]]
    """
    return [ apply_substitution_l(subst, literal, term_factory) for literal in clause ]

def remove_first_body_literal(clause,subst, term_factory):
    """
    Apply the substitution `subst` to the `clause` and remove the first body
    literal of `clause`.

    :parameters:
        - `clause`: a list of lists of integers
        - `subst`: a substitution as defined in
          :func:`etb.datalog.model.substitute`.
        - `term_factory`: an instance of :class:`etb.datalog.model.TermFactory`.

    :returntype:
        a list of lists of integers (length one less than `clause`)
    """
    # Make a copy,
    new_clause = list(clause)
    # and remove the first body literal.
    new_clause.pop(1)
    for i in range(len(new_clause)):
        new_clause[i] = apply_substitution_l(subst,new_clause[i], term_factory)
    return new_clause

def create_resolution_bottom_up_explanation(from_clause, from_claim, claim_expl):
    """
    Create a tuple that represents a resolution using `from_clause` and a claim
    `from_claim`. We use the resulting structures as explanations for
    reasoning.

    :parameters:
        - `from_clause`: the clause (a list of lists of integers) for which the
          first body literal was resolved away with `from_claim`
        - `from_claim`: the claim that resolved away the first body literal of
          `from_clause`.

    :returntype:
        a triple where the first element is the string `ResolutionBottomUp`.
        Use that to detect the type of explanation.

    """
    assert isinstance(from_clause, graph.PendingRule), 'from_clause {0}: {1}'.format(from_clause, type(from_clause))
    assert is_internal_clause(from_claim), 'from_claim {0}: {1}'.format(from_claim, type(from_claim))
    assert isinstance(claim_expl, tuple), 'bad claim_expl: {0}'.format(claim_expl)
    assert isinstance(claim_expl[0], basestring), 'bad claim_expl: {0}'.format(claim_expl)
    assert claim_expl[0] != "None", 'bad claim_expl: {0}'.format(claim_expl)
                                                                                                     
    # engine.get_rule_and_facts_explanation calls generate_children recursively on
    # from_clause and from_claim to get their explanations, which uses db_get_explanation,
    # which only returns meaningful explanations for PendingRules and goals.
    return ("ResolutionBottomUp", from_clause, from_claim, claim_expl)

def create_resolution_top_down_explanation(from_clause, from_goal):
    """
    Create a tuple that represents a resolution using `from_clause` and a goal
    `from_goal`.  We use the resulting structures as explanations for
    reasoning.

    :parameters:
        - `from_clause`: the clause (a list of lists of integers) for which the
          head matched with `from_goal`
        - `from_goal`: the goal that matched the head of `from_clause`.

    :returntype:
        a triple where the first element is the string `ResolutionTopDown`.
        Use that to detect the type of explanation.
    """
    assert is_internal_clause(from_clause) or from_clause is None, 'from_clause {0}'.format(from_clause)
    assert is_internal_literal(from_goal), 'from_goal {0}'.format(from_goal)
    return ("ResolutionTopDown", from_clause, from_goal)



def create_axiom_explanation():
    """
    Create a tuple that represents an Axiom.
    We add a dummy argument `None` as Python refuses to recognize ("Axiom") as an
    instance of a tuple with 1 element.

    :returntype:
        a tuple where the first element is the string `Axiom`.
        Use that to detect the type of explanation.
    """
    return ("Axiom",)

def create_external_explanation():
    """
    Create a 1-element tuple that represents an external explanation.

    :returntype:
        a tuple where the first element is the string `External`.
        Use that to detect the type of explanation.
    """
    return ("External",)


def is_top_down_explanation(internal_explanation):
    """
    Detect whether a tuple `internal_explanation` is a top down explanation.

    :parameters:
        - `internal_explanation`: a triple

    :returntype:
        `True` in case the first element of `internal_explanation` is
        `ResolutionTopDown`.
    """
    type_explanation = internal_explanation[0]
    return type_explanation == "ResolutionTopDown"

def is_bottom_up_explanation(internal_explanation):
    """
    Detect whether a tuple `internal_explanation` is a top down explanation.

    :parameters:
        - `internal_explanation`: a triple

    :returntype:
        `True` in case the first element of `internal_explanation` is
        `ResolutionBottomUp`; otherwise `False`
    """
    type_explanation = internal_explanation[0]
    return type_explanation == "ResolutionBottomUp"

def get_rule_from_explanation(internal_explanation):
    """
    Get the second argument of the `internal_explanation` if it is a bottom up
    explanation.

    :parameters:
        - `internal_explanation`: a triple

    :returntype:
        - a list of lists of integers
    """
    assert is_bottom_up_explanation(internal_explanation), 'internal explanation is not a bottom up explanation in get_rule_from_explanation'
    return internal_explanation[1]

def get_goal_from_explanation(internal_explanation):
    """
    Get the third argument of the `internal_explanation` if it is a top down
    explanation.

    :parameters:
        - `internal_explanation`: a triple

    :returntype:
        - a list of lists of integers
    """
    assert is_top_down_explanation(internal_explanation), 'internal_explanation is not a top down explanation in get_goal_from_explanation'
    return internal_explanation[2]

def freeze_clause(clause):
    """
    Freeze the `clause` to be able to use it as keys in dictionaries, for example
    in `db_all`.

    :parameters:
        - `clause`: is a list of lists of integers

    :returntype:
        a tuple of tuples of integers (and as such usable as keys in a
        dictionary)
    """
    return tuple([tuple(clause[i]) for i in range(len(clause))])

def freeze(something):
    """
    Can be used to freeze lists or lists of lists.

    .. seealso::
        :func:`etb.datalog.model.freeze_clause`

    :parameters:
        - `something`: a list of integers or a list of lists of integers

    :returntype:
        In case `something` is a list of integers, we return a tuple of
        integers; if `something` is a list of a list of integers, we return a
        tuple of tuples of integers.

    """
    if frozen(something):
        return something
    elif any(isinstance(el, list) for el in something):
        return freeze_clause(something)
    else:
        return tuple(something)

def frozen(something):
    """
    Check whether `something` is an instance of `tuple`.

    :parameters:
        - `something`: anything really

    :returntype:
        `True` or `False`

    """
    return isinstance(something, tuple)


def min_index(index1, index2):
    """
    Calculate the minimum of `index1` and `index2` where `None` is always
    bigger than anything else.

    :parameters:
        - `index1` and `index2`: integers or `None`

    :returntype:
        returns `None` if both `index1` and `index2` are `None`, otherwise an
        integer (either `index1` or `index2`).
    """
    if index1 is None and index2 is None:
        return None
    elif index2 is None:
        return index1
    elif index1 is None:
        return index2
    elif index1 <= index2:
        return index1
    else:
        return index2

def min_indices(ind, inds):
    """
    Calculate the minimum of an item `ind` and a list of items `inds` using
    :func:`etb.datalog.model.min_index` as the comparison operator.

    :parameters:
        - `ind`: an integer or `None`
        - `inds`: a list of (integers or `None`)

    :returntype:
        `None` or an integer
    """
    if inds:
        full_list = list(inds)
        full_list.append(ind)
        return reduce(min_index, full_list)
    else:
        return ind

class LogicalState(object):

    def __init__(self, engine):
        """
        Create a `LogicalState` object. This object provides basic data
        structures for claims, indices on the heads of KB rules, on the
        selected first body literal of pending rules, on goals, on stuck
        goals, and finally for storing the goal dependencies (a graph of goals
        and pending nodes to determine for example when a goal is completed).

        :members:
            - `db_all`: Store all clauses in dictionary with key the clause and
              value an explanation.
            - `db_claims`: Index of only the claims
            - `db_selected`:  Index on clauses with first body literal as key.
              Here we will store the Pending Rules
            - `db_heads`: Index on clauses with head literal as key.  Only used
              for Rules and Facts in the KB and for Goal resolution (not used
              for the bottom up reasoning). In other words, we do not store
              Pending rules here.
            - `db_goals`: Index on goals
            - `db_stuck_goals`: Index on stuck goals
            - `log`: a `Logger`
            - `goal_dependencies`: a :class:`etb.datalog.graph.DependencyGraph`
              object for storing the graph of dependencies between goals and
              pending rules.
            - `global_time`: A global timer associated with the Engine this
              LogicalState is part of. Each engine keeps his own time (starting
              at 0). This is used in :class:`etb.datalog.graph.Annotation` to
              put a time on different nodes in the goal dependencies graph.
            - `SLOW_MODE`: One can ask to slow down and log the adding/removing
              of things to the logical state (`SLOW_MODE` is the number of
              seconds to delay these operations).

        """
        self.engine = engine
        self.db_all = {}
        self.db_claims = {}
        self.db_selected = {}
        self.db_heads = {}
        self.db_goals = {}
        self.db_stuck_goals = {}
        self.log = logging.getLogger('etb.datalog.model')
        self.goal_dependencies = graph.DependencyGraph(self)
        self.global_time = 0
        self.SLOW_MODE = 0
        self.rlock = threading.RLock()

    def __enter__(self):
        self.rlock.acquire()

    def __exit__(self, t, v, tb):
        self.rlock.release()


    def get_global_time(self):
        """
        Get the global timer.

        :returntype:
            a positive integer

        """
        return self.global_time

    def inc_global_time(self):
        """
        Increase the global timer by 1.

        :returntype:
            `None`
        """
        with self:
            self.global_time += 1

    def go_slow(self, speed):
        """
        Set the delay between different updates of the LogicalState to `speed`.

        :parameters:
            - `speed`: a positive integer

        :returntype"
            `None`
        """
        self.SLOW_MODE = speed

    def go_normal(self):
        """
        Set the delay between different updates of the LogicalState back to
        `0`.

        :returntype:
            `None`
        """
        self.SLOW_MODE = 0

    def clear(self):
        """
        Clear all DBs. Typically done when reading a fresh Datalog program.

        :returntype:
            `None`
        """
        with self:
            self.db_all.clear()
            self.db_claims.clear()
            self.db_selected.clear()
            self.db_heads.clear()
            self.db_goals.clear()
            self.db_stuck_goals.clear()
            self.global_time = 0

    def reset(self, keepRules=True):
        """
        Reset currently resets `db_claims`; and thus always keeps KB rules.

        :parameters:
            - `keepRules` (optional, default is `True`): indicates whether to
              keep rules (not reset them), currently always the case

        :returntype:
            `None`

        .. todo::
            Decide whether we want to relay `keepRules=False` to a simple
            :func:`etb.datalog.model.LogicalState.clear`.
        """
        with self:
            self.db_claims.clear()


    def db_mem(self,rule):
        """
        Check whether the `clause` is already present in `db_all`.

        :parameters:
            `clause`: an list of lists of integers

        :returntype:
            `True` or `False`
        """
        c = rule.clause if isinstance(rule, graph.PendingRule) else freeze_clause(rule)
        return c in self.db_all

    def db_mem_claim(self, prule):
        """
        Check whether the `graph.PendingRule` is already present in `db_claims`.

        :parameters:
            `prule`: a `graph.PendingRule` instance

        :returntype:
            `bool`
        """
        assert(isinstance(prule, graph.PendingRule))
        return index.in_index(self.db_claims, prule.clause[0], prule)

    def db_add_clause(self, prule, explanation):
        """
        Add a `clause` to the DB. The `explanation` is of the form
        `(Axiom,0)` or `(ResolutionBottomUp, clause', fact)` or
        `(ResolutionTopDown, clause', goal)`  or `(External, 0)` or a
        :class:`etb.terms.Literal`. This function will be used to store
        anything for which we need to store an explanation (including
        rules) -- we will however not reason with those clauses. We can use the
        explanations (in all cases except :class:`etb.terms.Term`) to construct
        an explanation tree for claims using :func:`etb.datalog.engine.to_png`.

        :parameters:
            - `prule`: a `graph.PendingRule`
            - `explanation`: `(Axiom,0)` or `(ResolutionBottomUp, clause',
              fact)` or `(ResolutionTopDown, clause', goal)`  or `(External,
              0)` or a :class:`etb.terms.Term`

        :returntype:
            `None`

        """
        assert isinstance(prule, (list, tuple, graph.PendingRule))
        key = freeze(prule) if isinstance(prule, (list, tuple)) else prule
        with self:
            if not explanation is None:
                self.db_all[key] = explanation
            else:
                self.db_all[key] = ()

    def db_add_claim(self,prule):
        """
        Add a `prule` to the `db_claims` index.

        :parameters:
            - `prule`: a list of 1 list of integers or a graph.PendingRule
        """
        with self:
            assert(isinstance(prule, graph.PendingRule))
            claim = freeze_clause(prule.clause if isinstance(prule, graph.PendingRule) else prule)
            if not index.in_index(self.db_claims, claim[0], prule):
                index.add_to_index(self.db_claims, claim[0], prule)
                assert(self.db_mem_claim(prule))

    def db_add_goal(self, goal):
        """
        Add a `goal` (a literal) to the DB. This causes the goal to be added to
        the `db_goals` index and to the dependency graph `goal_dependencies`.

        :parameter:
            -`goal`: a list of integers (an internal literal)

        :returntype:
            `None`
        """
        assert isinstance(goal, (list, tuple)), 'goal {0} should be a list or tuple'.format(goal)
        assert all(isinstance(x, int) for x in goal), 'goal {0} should be a list of ints'.format(goal)
        with self:
            if not index.in_index(self.db_goals,goal,goal):
                index.add_to_index(self.db_goals,goal,goal)
            # Also add it to the Goal Dependencies graph
            self.goal_dependencies.add_goal(goal)

    def db_add_goal_to_pending_rule(self, goal, rule):
        """
        Add `goal` as a successor of `rule` to the `goal_dependencies`.

        :parameters:
            As in :func:`etb.datalog.graph.DependencyGraph.add_goal_to_pending_rule`.

        :returntype:
            `None`
        """
        self.goal_dependencies.add_goal_to_pending_rule(goal, rule)

    def db_add_pending_rule_to_goal(self, rule, goal):
        """
        Add `rule` as a successor of `goal` to the `goal_dependencies`.

        :parameters:
            As in
            :func:`etb.datalog.graph.DependencyGraph.add_pending_rule_to_goal`.

        :returntype:
            `None`
        """
        self.goal_dependencies.add_pending_rule_to_goal(rule, goal)

    def db_add_pending_rule_to_pending_rule(self, rule1, rule2):
        """
        Add `rule1` as a successor of `rule2` to the `goal_dependencies`.

        :parameters:
            As in
            :func:`etb.datalog.graph.DependencyGraph.add_pending_rule_to_pending_rule`.

        :returntype:
            `None`
        """
        self.goal_dependencies.add_pending_rule_to_pending_rule(rule1, rule2)

    def db_add_claim_to_goal(self, goal, claim, explanation):
        """
        Add a `claim` directly to the `goal` in the `goal_dependencies`.

        :parameters:
            As in :func:`etb.datalog.graph.DependencyGraph.add_claim`

        :returntype:
            `None`
        """
        self.goal_dependencies.add_claim(goal, claim, explanation)

    def db_get_goal_dependencies(self):
        """
        Get the dependency graph from the LogicalState.

        :returntype:
            a :class:`etb.datalog.graph.DependencyGraph`
        """
        return self.goal_dependencies

    def db_get_annotation(self, item):
        """
        Get the annotation of an item: we first freeze the item (which should
        be an internal goal or an internal clause).

        :parameters:
            - `item`: list of lists of integers or a list of integers

        :returntype:
            a :class:`etb.datalog.graph.Annotation`

        """
        if isinstance(item, (list, tuple)):
            frozen = freeze(item)
            return self.goal_dependencies.get_annotation(frozen)
        else:
            return self.goal_dependencies.get_annotation(item)

    def close(self):
        """
        The Closing Algorithm. Relays to
        :func:`etb.datalog.graph.DependencyGraph.close`.

        :returntype:
            `None`
        """
        self.goal_dependencies.close()

    def complete(self):
        """
        The Completing Algorithm. Relays to
        :func:`etb.datalog.graph.DependencyGraph.complete`.

        :returntype:
            `None`
        """
        self.goal_dependencies.complete()

    def is_completed(self, goal):
        """
        Determines whether the `goal` is completed.

        :parameters:
            - `goal`: an internal representation of a goal

        :returntype:
            - `True` if the goal is completed; `False` otherwise

        """
        pgoal = self.is_renaming_present_of_goal(goal)
        if pgoal:
            return self.goal_dependencies.is_completed(pgoal)
        else:
            return self.goal_dependencies.is_completed(goal)

    def db_add_stuck_goal(self,goal):
        """
        Add a stuck `goal` (a literal) to the `db_stuck_goals` index.

        :parameters:
            - `goal`: a list of integers

        :returntype:
            `None`
        """
        with self:
            if not index.in_index(self.db_stuck_goals, goal, goal):
                index.add_to_index(self.db_stuck_goals,goal,goal)

    def db_remove_stuck_goal(self,goal):
        """
        Remove a stuck goal from the `db_stuck_goals` index.

        :parameters:
            - `goal`: a list of integers

        :returntype:
            `None`

        """
        with self:
            index.remove_from_index(self.db_stuck_goals, goal, goal)

    def db_remove_goal(self,goal):
        """
        Remove a goal from the `db_goals` index.
        """
        with self:
            index.remove_from_index(self.db_goals, goal, goal)

    def db_move_goal_to_stuck(self, goal):
        """
        Remove it from the goals and add it to the stuck goals.

        :parameters:
            - `goal`: a list of integers

        :returntype:
            `None`

        """
        with self:
            self.db_remove_goal(goal)
            self.db_add_stuck_goal(goal)

    def db_move_stuck_goal_to_goal(self, goal):
        """
        Make a goal unstuck (move it from `db_stuck_goals` to `db_goals`.

        :parameters:
            - `goal`: a list of integers

        :returntype:
            `None`

        """
        with self:
            if index.in_index(self.db_stuck_goals, goal, goal):
                self.db_remove_stuck_goal(goal)
                self.db_add_goal(goal)

    def db_get_claims_index(self):
        """
        Return the `db_claims` index.

        :returntype:
            a *dict* that represents an index as in :mod:`etb.datalog.index`
        """
        return self.db_claims

    def db_get_all_claims(self):
        """
        Extract all claims from the `db_claims` index.

        :returntype:
            a list of claims (an internal claim is a list of 1 list of
            integers)
        """
        with self:
            if self.db_claims:
                return index.traverse(self.db_claims)
            else:
                return []

    def db_get_all_closed_claims(self, termfactory):
        """
        Extract all claims from the `db_claims` index and close them (get their symbol
        representation) using
        :func:`etb.datalog.model.close_literal`.

        :parameters:
            - `termfactory`: the :class:`etb.datalog.model.TermFactory` used
              for closing the literals
        :returntype:
            a list of :class:`etb.terms.Term` instances

        """
        return map(lambda claim: termfactory.close_literal(claim[0]), self.db_get_all_claims())

    def db_get_goals_index(self):
        """
        Return the `db_goals` index.

        :returntype:
            a *dict* that represents an index as in :mod:`etb.datalog.index`

        """
        return self.db_goals

    def db_get_all_goals(self):
        """
        Extract all goals from the `db_goals` index.

        :returntype:
           a list of goals (a goal is a list of integers)
        """
        if self.db_goals:
            return index.traverse(self.db_goals)
        else:
            return []

    def db_get_stuck_goals_index(self):
        """
        Return the `db_stuck_goals` index.

        :returntype:
            a *dict* that represents an index as in :mod:`etb.datalog.index`

        """
        return self.db_stuck_goals

    def db_get_all_stuck_goals(self):
        """
        Extract all stuck goals from the `db_stuck_goals` index.

        :returntype:
           a list of goals (a goal is a list of integers)
        """
        if self.db_stuck_goals:
           return index.traverse(self.db_stuck_goals)
        else:
            return []

    def is_stuck_goal(self, goal):
        """
        Verify that `goal` is present in the `db_stuck_goals` index.

        :parameters:
            - `goal`: a list of integers

        :returntype:
            `True` or `False`
        """
        return index.in_index(self.db_stuck_goals, goal, goal)

    def is_goal(self, goal):
        """
        Verify that `goal` is present in the `db_goals` index.

        :parameters:
            - `goal`: a list of integers

        :returntype:
            `True` or `False`
        """
        return index.in_index(self.db_goals, goal, goal)

    def no_stuck_subgoals(self, goal):
        """
        A goal has no stuck subgoals if no subgoals are stuck or (if there are
        no subgoals) the goal is not a stuck goal.

        :parameters:
            - `goal`: a list of integers

        :returntype:
            `True` or `False`
        """
        def keep_only_bigger_children(children, node):
            annotation_node = self.db_get_annotation(node)
            if annotation_node:
                i = annotation_node.index
                new_list = []
                for child in children:
                    child_annotation = self.db_get_annotation(child)
                    if child_annotation:
                        j = child_annotation.index
                        if j > i:
                            new_list.append(child)
                    else:
                        new_list.append(child)
                return new_list
            else:
                return children

        g = goal.clause if isinstance(goal, graph.PendingRule) else freeze(goal)
        children = self.goal_dependencies.get_children(g)
        bigger_children = keep_only_bigger_children(children, g)
        if bigger_children:
            return all(self.no_stuck_subgoals(child) for child in bigger_children)
        elif self.is_stuck_goal(list(g)):
            return False
        elif self.is_goal(list(g)):
            return True
        else:
            # We can have nodes that are pending rules (not goals) and that
            # have for example only children with indices lower than the
            # current index. Encountering such a pending rule (and stopping the
            # check for stuck subgoal as such -- that's handled elsewhere by
            # the check) we consider this OK (and thus have to return True
            # instead of False)
            return True


    def db_add_clause_head(self, rule):
        """
        Add a `clause` to the `db_heads` index. We can use this to store the KB
        rules: they will be matched against goals using the heads of rules, so
        it makes to speed that matching by using an index.

        :parameters:
            - `rule`: a list of list of integers representing a rule, or a
              `graph.PendingRule`
        """
        assert(isinstance(rule, (list, graph.PendingRule)))
        clause = rule.clause if isinstance(rule, graph.PendingRule) else rule
        with self:
            index.add_to_index(self.db_heads, clause[0], clause)

    def db_add_clause_selected(self,selected_literal, clause):
        """
        Add a `selected_literal` of the `clause` to the index. We can use this
        to the first body literal (for example) of the clause to the index to
        quickly matches for resolving that first body literal away against
        claims.

        :parameters:
            - `selected_literal`: a list of integers that is present in clause
            - `clause`: a list of list of integers representing a rule
        """
        with self:
            index.add_to_index(self.db_selected, selected_literal, clause)

    def db_add_rule(self, clause):
        """
        Shortcut for :func:`etb.datalog.model.LogicalState.db_add_clause_head`:
        we add the rules to the `db_heads` index.

        .. seealso::
            :func:`etb.datalog.model.LogicalState.db_add_clause_head`
        """
        with self:
            self.db_add_clause_head(clause)

    def db_get_rules_index(self):
        """
        Get the rules index, aka `db_heads`.

        :returntype:
            a *dict* that represents an index as in :mod:`etb.datalog.index`
        """
        return self.db_heads

    def db_get_rules(self):
        """
        Get the rules (all rules in the `db_heads` index)

        :returntype:
            a list of clauses
        """
        if self.db_heads:
            return index.traverse(self.db_heads)
        else:
            return []


    def db_add_pending_rule(self, clause):
        """
        Shortcut for :func:`etb.datalog.model.LogicalState.db_add_clause_head`:
        we add the clause to `db_selected`
        (with index on first body literal of clause). Should only be called for
        clauses that are not facts.

        :returntype:
            `None`
        """
        if len(clause) > 1:
            self.db_add_clause_selected(clause[1], clause)
            # also add it to the goal dependency graph (we want the pending
            # rules in between the goals in the graph)
        return self.goal_dependencies.add_pending_rule(clause)

    def db_get_pending_rules_index(self):
        """
        Get the pending rules index, aka `db_selected` (for example for resolution)

        :returntype:
            a *dict* that represents an index as in :mod:`etb.datalog.index`
        """
        return self.db_selected

    def db_get_pending_rules(self):
        """
        Get the pending rules (all rules in the `db_selected` index).

        :returntype:
            a list of all the rules in the `db_selected` index
        """
        if self.db_selected:
            return index.traverse(self.db_selected)
        else:
            return []


    def is_renaming(self,literal1, literal2):
        """
        Check whether `literal1` is a renaming of `literal2`.

        :parameters:
            - `literal1` and `literal2` are lists of integers

        :returntype
            `True` or `False`
        """
        if len(literal1) != len(literal2):
            return False
        offset = find_first_variable_difference(literal1,literal2)
        return (shift_literal(literal1,offset) == literal2 or literal1 == shift_literal(literal2,offset))

    def is_renaming_present_of_goal(self, goal):
        """
        Check in `db_goals` and in 'db_stuck_goals' whether that index contains
        a renaming for the `goal`.

        :parameters:
            - `goal`: a list of integers

        :returntype:
            `goal` or None
        """
        candidate_renamings = index.get_candidate_renamings(self.db_goals, goal)
        for candidate in candidate_renamings:
            if self.is_renaming(goal,candidate):
                return candidate
        candidate_renamings_stuck = index.get_candidate_renamings(self.db_stuck_goals, goal)
        for candidate in candidate_renamings_stuck:
            if self.is_renaming(goal, candidate):
                return candidate
        return None


    def db_get_explanation(self, clause):
        """
        Returns the explanation of the `clause` directly stored in `db_all` (not
        recursive!).

        :parameters:
            - `clause`: a list of lists of integers

        :returntype:
            `(Axiom,0)` or `(ResolutionBottomUp, clause', fact)` or
            `(ResolutionTopDown, clause', goal)`  or `(External, 0)` or a
            :class:`etb.terms.Term`
        """
        c = freeze_clause(clause) if isinstance(clause, list) else clause
        if c in self.db_all:
            return self.db_all[c]
        else:
            self.log.info('db_get_explanation has no explanation for {0}'.format(clause))
            return ("None",)
