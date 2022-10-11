""" ETB terms

Implementation of terms with embedded JSON, and hashconsing.  Also,
implementation of substitutions.

There are two ways to create terms: parsing, or using the functions
mk_var(), mk_fresh_var(), mk_idconst(), mk_stringconst, mk_numberconst,
mk_array(), mk_map(), mk_literal, mk_subst

Run unit tests using
python -m doctest -v terms.py 

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

from __future__ import unicode_literals

import sys
import re
import weakref
import collections
import itertools
import json
import parser

# ----------------------------------------------------------------------
# terms
# ----------------------------------------------------------------------

def id_match(id):
    """Check if id is a valid id string, used to decide whether to use
    IdConst or StringConst"""
    return re.match(r"[^][(){}=:`'\".,~?% \\0-9][^][(){}=:`'\".,~?% \\]*$", id)

def mk_idconst(val):
    """
    Make an id constant term out of the given string value.
    :parameters:
    - `val`: a basestring or an IdConst
    :returntype:
    - a hashconsed `IdConst` instance
    """
    if isinstance(val, IdConst):
        return val.hashcons()
    else:
        t = IdConst(val)
        return t.hashcons()

def mk_stringconst(val):
    """
    Make a string constant term out of the given value
    :parameters:
    - `val`: a basestring or a StringConst
    :returntype:
    - a hashconsed `StringConst` instance
    """
    if isinstance(val, StringConst):
        return val.hashcons()
    else:
        t = StringConst(val)
        return t.hashcons()

def mk_boolconst(val):
    """
    Make a boolean constant term out of the given value
    :parameters:
    - `val`: a bool, basestring or a BoolConst
    :returntype:
    - a hashconsed `BoolConst` instance
    """
    if isinstance(val, BoolConst):
        return val.hashcons()
    else:
        t = BoolConst(val)
        return t.hashcons()
    

def mk_numberconst(val):
    """
    Make a number constant term out of the given value
    :parameters:
    - `val`: a basestring or a NumberConst
    :returntype:
    - a hashconsed `NumberConst` instance
    """
    if isinstance(val, NumberConst):
        return val.hashcons()
    else:
        t = NumberConst(val)
        return t.hashcons()

def mk_var(val):
    """
    Make a variable term.
    :parameters:
    - `val`: a basestring or Var
    :returntype:
    - a hashconsed `Var` instance
    """
    if isinstance(val, Var):
        return val.hashcons()
    else:
        t = Var(val)
        return t.hashcons()

def mk_array(elems):
    """
    Make an array from the given Term elements.
    """
    if isinstance(elems, Array):
        return elems.hashcons()
    else:
        t = Array(elems)
        return t.hashcons()

def mk_map(entries):
    """
    Make a map from the given pairs. Pairs are converted to
    pairs of terms if needed.
    """
    if isinstance(entries, Map):
        return entries.hashcons()
    else:
        t = Map(entries)
        return t.hashcons()

def mk_literal(pred, args):
    """
    Makes a literal from pred (a string) and args (a list or tuple of terms)
    """
    l = Literal(pred, args)
    return l.hashcons()

_count = 0

def mk_fresh_var():
    """
    Create a new variable.

    >>> mk_fresh_var() != mk_fresh_var()
    True
    """
    global _count
    v = mk_var(_count)
    _count += 1
    return v

def _occur_check(var, t):
    """
    Checks whether var occurs in t.
    """
    return var in t.free_vars()

def is_fileref(term):
    """
    Checks if term is a valid fileref, meaning it is a Map with
    `file` and `sha1` slots.
    """
    if term.is_map():
        fileterm = mk_stringconst("file")
        sha1term = mk_stringconst("sha1")
        items = term.get_args()
        valid = (fileterm in items and sha1term in items)
        return valid
    else:
        return False

def is_filerefs(term):
    """
    Checks if term is a fileref, or an array of (array of) filerefs
    """
    return term.is_array() and all(is_fileref(x) or is_filerefs(x)
                                   for x in term.get_args())

def get_fileref(term):
    """
    Checks if term is a fileref (a map with 'file' and 'sha1' fields)
    and returns a dict fileref in that case, or None if not.
    Note that a fileref may have other fields - these are (will be) simply
    carried along.
    """
    if is_fileref(term):
        fileterm = mk_stringconst('file')
        sha1term = mk_stringconst('sha1')
        filestr = term.get_args()[fileterm].val
        sha1 = term.get_args()[sha1term].val
        fref = { 'file'.encode('utf8') : filestr, 'sha1'.encode('utf8') : sha1 }
        return fref
    else:
        return None

def get_filerefs(term):
    """
    Checks if term is (recursively) a list of filerefs (maps
    with 'file' and 'sha1' fields)  and returns a Python array of the
    same form, with dict filerefs at the leaves.  Returns None otherwise.
    Note that a fileref may have other fields - these are (will be) simply
    carried along.
    """
    if is_filerefs(term):
        return [get_filerefs(x) for x in term.get_args()]
    elif is_fileref(term):
        return get_fileref(term)
    else:
        return None

def mk_term(obj):
    """Converts a mix of python and Term to Term
    Deals with arrays, tuples, dicts, strings, and Terms.
    This is useful in wrappers, where it is convenient to build up Maps and Arrays
    using dicts and lists (or tuples) in Python.
    This will try to guess what to do with strings, but it's probably best to construct
    the corresponding terms or call the parser directly.
    """
    if isinstance(obj, Term):
        return obj
    elif isinstance(obj, (list, tuple)):
        return mk_array(map(lambda x: mk_term(x), obj))
    elif isinstance(obj, dict):
        return mk_map(map(lambda (x, y): (mk_stringconst(x), mk_term(y)), obj.items()))
    elif isinstance(obj, bool):
        return mk_boolconst(obj)
    elif isinstance(obj, (int, float)):
        return mk_numberconst(obj)
    elif isinstance(obj, basestring):
        if obj == '':
            return mk_stringconst(obj)
        try:
            float(obj)
            return mk_numberconst(obj)
        except:
            pass
        idmatch = id_match(obj)
        if idmatch:
            if obj[0].isupper():
                return mk_var(obj)
            else:
                return mk_idconst(obj)
        else:
            sobj = obj.strip()
            if sobj == '':
                return mk_stringconst(obj)
            elif ((sobj[0] == '[' and sobj[-1] == ']') or
                  (sobj[0] == '{' and sobj[-1] == '}')):
                return parser.parse_term(sobj)
            else:
                return mk_stringconst(obj)

class Term(object):
    """
    A datalog+JSON term, with hashconsing
    Note that Term instances should not be created directly, instead use
    IdConst, StringConst, BoolConst, NumberConst, Var, Array, or Map
    """
    
    # hashconsing of terms
    __terms = weakref.WeakValueDictionary()

    # chars to escape
    escapestr = re.compile("""[\\\n\t:[]{} ]""")

    __slots__ = ['val', 'args', '_hash', '_fvars',
                 '_volatile', '_normal_form', '__weakref__']

    def __lt__(self, other):
        """
        Arbitrary order (with hash...)
        """
        # TODO a better (total?) ordering
        return self != other and hash(self) < hash(other)

    def __init__(self):
        """
        Initialize the term.
        """
        self._hash = None
        self._fvars = None
        self._normal_form = None
        self._volatile = False
        
    def __nonzero__(self):
        """
        Checks if term is nonzero, e.g., empty Array or Map, nonzero NumberConst
        """
        # Overridden below for some term subclasses
        return False

    def hashcons(self):
        """
        Returns the term that is representative for the equivalence
        class of terms that are equal to self.

        >>> t = mk_stringconst('foo')
        >>> t.hashcons() == t
        True
        >>> t.hashcons() is mk_stringconst('foo').hashcons()
        True
        """
        return Term.__terms.setdefault(self, self)

    def is_var(self):
        """Check whether the term is a variable."""
        return isinstance(self, Var)

    def is_const(self):
        """Check whether the term is a constant."""
        return isinstance(self, Const)
    def is_idconst(self):
        """Check whether the term is an id constant."""
        return isinstance(self, IdConst)
    def is_stringconst(self):
        """Check whether the term is a string constant."""
        return isinstance(self, StringConst)
    def is_boolconst(self):
        """Check whether the term is a boolean constant."""
        return isinstance(self, BoolConst)
    def is_numconst(self):
        """Check whether the term is a numeric constant."""
        return isinstance(self, NumberConst)

    def is_map(self):
        """Check whether the term is a map."""
        return isinstance(self, Map)

    def is_array(self):
        """Check whether the term is an array."""
        return isinstance(self, Array)

    @staticmethod
    def all_terms():
        """
        Iterate through all current terms.
        """
        for t in Term.__terms.itervalues():
            yield t

    def unify(self, other):
        """
        Unify this term against the other. In case of success,
        returns a substitution (even empty), in case of failure, returns None.

        >>> mk_var(1).unify(mk_idconst('p'))
        subst(X1 = p)
        >>> mk_idconst('p').unify(mk_idconst('q'))
        >>> mk_array([mk_idconst('p'), mk_idconst('a'), mk_idconst('b'), mk_var(1)]).unify(
        ...   mk_array([mk_idconst('p'), mk_idconst('a'), mk_idconst('b'), mk_idconst('c')]))
        subst(X1 = c)
        >>> mk_array([mk_idconst('p'), mk_map({ mk_stringconst('a'): mk_idconst('b'), mk_stringconst('c'): mk_var(1) })]).unify(
        ...       mk_array([mk_idconst('p'), mk_map({ mk_stringconst('a'): mk_idconst('b'), mk_stringconst('c'): mk_idconst('d')})]))
        subst(X1 = d)
        """
        assert isinstance(other, Term), 'Unify only works for terms'
        assert not self.free_vars().intersection(other.free_vars()), 'Unify unhappy with the free vars'
        # create a substitution
        bindings = Subst()
        # create a stack of pairs of terms to unify 
        stack = [ (self, other) ]
        while stack:
            left, right = stack.pop()

            # apply the substitution to terms
            left = bindings(left)
            right = bindings(right)

            if left == right:
                continue
            elif left.is_var():
                if _occur_check(left, right):
                    return None
                bindings.bind(left, right)
            elif right.is_var():
                if _occur_check(right, left):
                    return None
                bindings.bind(right, left)
            # elif left.is_apply() and right.is_apply():
            #     if len(left.args) != len(right.args):
            #         return None  # failure
            #     # otherwise, just unify preds and arguments pairwise
            #     stack.append( (left.val, right.val) )
            #     for l, r in itertools.izip(left.args, right.args):
            #         stack.append( (l, r) )
            elif left.is_array() and right.is_array() and \
                    len(left.elems) == len(right.elems):
                for l, r in itertools.izip(left.elems, right.elems):
                    stack.append( (l, r) )
            elif left.is_map() and right.is_map():
                # most interesting case: unify keys pairwise
                # only ground keys are authorized.
                if not left.items.viewkeys() == right.items.viewkeys():
                    return None
                for k, v in left.items.iteritems():
                    assert k.is_ground(), 'k is not ground; unify unhappy'
                    stack.append( (v, right.items[k]) )
            else:
                return None  # failure
        return bindings

    def is_volatile(self):
        """
        Check whether the term is volatile
        """
        return self._volatile

    def set_volatile(self):
        """
        Mark the symbol as volatile.
        """
        self._volatile = True

    def rename(self, offset=None):
        """
        Performs an alpha-renaming of this term, obtained by replacing
        all variables in it by fresh variables.

        Returns (renaming, renamed_term)

        >>> t = mk_array([mk_idconst("p"), mk_var(1),
        ...     mk_map( { mk_stringconst("foo"): mk_var(2) } ) ] )
        >>> t
        [p, X1, {"foo": X2}]
        >>> t.free_vars() == frozenset((mk_var(1), mk_var(2)))
        True
        >>> renaming, t2 = t.rename()
        >>> t == t2
        False
        >>> t.unify(t2).is_renaming()
        True
        """
        free_vars = self.free_vars()
        if offset is None:
            offset = max(v.val for v in free_vars if isinstance(v.val, int)) + 1
        renaming = Subst()
        for i, v in enumerate(free_vars):
            renaming.bind(v, mk_var(i + offset))
        assert renaming.is_renaming(), 'renaming not a renaming; rename unhappy'
        return (renaming, renaming(self))

    def negative_rename(self):
        """
        Performs an alpha-renaming of the term, using
        only negative variables.

        >>> t = mk_array([mk_idconst("p"), mk_var(1), mk_map({mk_stringconst("foo"): mk_var(2)})])
        >>> t
        [p, X1, {"foo": X2}]
        >>> t.negative_rename()[1]
        [p, X-3, {"foo": X-2}]
        """
        free_vars = self.free_vars()
        offset = max(v.val for v in free_vars if isinstance(v.val, int)) + 1
        return self.rename(offset=-offset)

    def is_ground(self):
        """
        Checks whether the term is ground.

        >>> t = mk_array([mk_idconst('p'), mk_var(1), mk_idconst('q')] )
        >>> t.is_ground()
        False
        >>> mk_array([mk_idconst("p"), mk_stringconst("q"), mk_map({mk_stringconst("foo"): mk_numberconst(42) })]).is_ground()
        True
        """
        return not self.free_vars()

    def free_vars(self):
        """Returns the set of free variables of this term.
        """
        if self._fvars is None:
            vars = set()
            self._compute_free_vars(vars)
            self._fvars = frozenset(vars)
        return self._fvars

    def _compute_free_vars(self, vars):
        """
        Adds the free vars of the term to vars
        """
        if self.is_var():
            vars.add(self)
            return
        elif self.is_const():
            return
        if self.is_array():
            for t in self.elems:
                t._compute_free_vars(vars)
        elif self.is_map():
            for k, v in self.items.iteritems():
                k._compute_free_vars(vars)
                v._compute_free_vars(vars)

    def normalize(self):
        """
        Returns a normalized version of the term. Variables in it
        are replaced by X0...Xn-1) where n is the number of free
        variables in the term.

        Returns (renaming, term) where renaming is used to normalize.

        >>> t = mk_array([mk_idconst("p"), mk_var(3),
        ...                         mk_map({ mk_stringconst("foo"): mk_var(2) })] )
        >>> t
        [p, X3, {"foo": X2}]
        >>> t.normalize()[1]
        [p, X0, {"foo": X1}]
        >>> t = mk_array([mk_idconst("p"), mk_var(2),
        ...                         mk_map( { mk_stringconst("foo"): mk_var(1)} )] )
        >>> t
        [p, X2, {"foo": X1}]
        >>> t.normalize()
        (subst(X2 = X0), [p, X0, {"foo": X1}])
        """
        if self.is_ground():
            return (Subst(), self)
        fvars = self.ordered_free_vars()
        renaming = Subst(dict( (v, mk_var(i)) for \
            i, v in enumerate(fvars) ))
        return (renaming, renaming(self))

    def is_normalized(self):
        """
        Checks whether the term is normalized
        """
        if self._normal_form is None:
            self._normal_form = self.normalize()[1]
        return self._normal_form == self

    def ordered_free_vars(self, l=None):
        """
        Returns the list of variables in the term, by order of prefix
        traversal. Free vars may occur several times in the list
        """
        if l is None:
            l = []
        if self.is_var():
            if self not in l:  # avoid duplicates
                l.append(self)
        # elif self.is_apply():
        #     for t in self.args:
        #         t.ordered_free_vars(l)
        elif self.is_array():
            for t in self.elems:
                t.ordered_free_vars(l)
        elif self.is_map():
            for k, v in self.items.iteritems():
                k.ordered_free_vars(l)
                v.ordered_free_vars(l)
        return l

    def first_symbol(self):
        """
        Finds the first symbol in the object

        >>> mk_idconst('a').first_symbol()
        a
        >>> mk_array([ mk_idconst('a'), mk_idconst('b')]).first_symbol()
        a
        """
        if self.is_const() or self.is_var():
            return self
        elif self.is_array():
            return self.elems[0].first_symbol()
        elif self.is_map():
            raise AssertionError('map term has no first symbol')
        else:
            raise ValueError('unhandled case for first_symbol: ' + \
                             repr(self))
            
    def reduce_access(self, access):
        if not isinstance(access, list):
            raise ValueError('Illegal access: {0}: {1} should be a list'
                             .format(access, type(access)))
        if access:
            raise ValueError('Illegal access: {0}: {1} should be a map or array'
                             .format(self, type(self)))
        else:
            return self

# Term subclasses: Const, Var, Map, Array

class Const(Term):
    """
    Constant terms, e.g., ids, strings and numbers
    """
    def to_python(self):
        '''Convert ground terms to python'''
        return self.val
    def __nonzero__(self):
        return bool(self.val)
    def get_val(self):
        return self.val

class IdConst(Const):
    """
    Id consts.  Like StringConsts, the val is a string, but must not start
    with a capital letter, and is printed without string quotes.
    Note that IdConst("foo") != StringConst("foo") (e.g., foo != "foo")
    """
    def __init__(self, idstr):
        """
        Initialize an IdConst with idstr
        """
        if not isinstance(idstr, basestring):
            raise ValueError('IdConst: string expected for {0} of type {1}'
                             .format(idstr, type(idstr)))
        if idstr[0].isupper():
            raise ValueError('IdConst: {0} must not start with an uppercase char'
                             .format(idstr))
        if idstr[0].isdigit():
            raise ValueError('IdConst: {0} must not start with a digit'
                             .format(idstr))
        Term.__init__(self)
        self.val = idstr.encode('utf8')
    def __eq__(self, other):
        if isinstance(other, IdConst):
            return hash(self) == hash(other) and self.val == other.val
        elif isinstance(other, basestring):
            return self.val == other
        else:
            return False
    def __lt__(self, other):
        if isinstance(other, IdConst):
            return self.val < other.val
        else:
            return not (isinstance(other, Var) or isinstance(other, NumberConst))
    def __repr__(self):
        return '{0}'.format(self.val.encode('utf8'))
    def __hash__(self):
        self._hash = hash(self.val)
        return self._hash
    def to_dot(self):
        return str(self.val)

class StringConst(Const):
    """String consts"""
    def __init__(self, text):
        if text == u"dummy":
            raise ValueError(text)
        Term.__init__(self)
        self.val = text.encode('utf8')
    def __eq__(self, other):
        if isinstance(other, StringConst):
            return hash(self) == hash(other) and self.val == other.val
        elif isinstance(other, basestring):
            return self.val == other
        else:
            return False
    def __lt__(self, other):
        if isinstance(other, StringConst):
            return self.val < other.val
        else:
            return isinstance(other, Array) or isinstance(other, Map)
    def __repr__(self):
        return '"{0}"'.format(self.val.encode('utf8'))
    def __hash__(self):
        self._hash = hash(self.val)
        return self._hash
    def to_dot(self):
        return str(self.val)

class BoolConst(Const):
    """Boolean Consts"""
    def __init__(self, val):
        Term.__init__(self)
        if isinstance(val, basestring):
            if val == 'true':
                val = True
            elif val == 'false':
                val = False
        if isinstance(val, bool):
            self.val = val
        else:
            raise TypeError('Boolean (or string "true"/"false" expected for BoolConst')
    def __eq__(self, other):
        return (isinstance(other, BoolConst)
                and hash(self) == hash(other)
                and self.val == other.val)
    def __lt__(self, other):
        if isinstance(other, BoolConst):
            return self.val < other.val
        else:
            return not isinstance(other, Var)
    def __repr__(self):
        return '{0}'.format('true' if self.val else 'false')
    def __hash__(self):
        self._hash = hash(self.val)
        return self._hash
    def to_dot(self):
        return 'true' if self.val else 'false'
        
class NumberConst(Const):
    """Number consts"""
    def __init__(self, val):
        Term.__init__(self)
        if isinstance(val, int) or isinstance(val, float):
            self.val = str(val)
            self.num = val
        elif isinstance(val, basestring):
            self.val = val
            if any(i in '\.eE' for i in val):
                self.num = float(val)
            else:
                self.num = int(val)
        else:
            raise TypeError('Number or string expected for NumberConst')
    def __eq__(self, other):
        return (isinstance(other, NumberConst)
                and hash(self) == hash(other)
                and self.val == other.val)
    def __lt__(self, other):
        if isinstance(other, NumberConst):
            return self.num < other.num
        else:
            return not isinstance(other, Var)
    def __repr__(self):
        return '{0}'.format(self.val)
    def __hash__(self):
        self._hash = hash(self.val)
        return self._hash
    def to_dot(self):
        return str(self.val)

class Var(Term):
    """Variable terms, start with capital letter; integer also possible
    >>> Var('Foo')
    Foo
    >>> Var(1)
    X1
    """
    def __init__(self, val):
        Term.__init__(self)
        assert isinstance(val, (basestring, int)),\
            'Var must be a string or int: {0}: {1}'.format(val, type(val))
        self.val = val
    def __eq__(self, other):
        """See if the self var is eq to the other Term
        >>> Var('X') == Var('X')
        True
        >>> Var(3) == Var(3)
        True
        >>> Var('X') == Var(3)
        False
        """
        return (isinstance(other, Var)
                and hash(self) == hash(other)
                and self.val == other.val)
    def __lt__(self, other):
        if isinstance(other, Var):
            return self.val < other.val
        else:
            return False
    def __hash__(self):
        self._hash = hash(self.val)
        return self._hash
    def __repr__(self):
        return "X%d" % self.val if isinstance(self.val, int) else unicode(self.val)
    def to_python(self):
        '''Convert ground terms to python'''
        return self.val
    def to_dot(self):
        return "X%d" % self.val if isinstance(self.val, int) else unicode(self.val)
    def get_val(self):
        return self.val

class Array(Term):
    """Array (list) terms"""
    def __init__(self, elems):
        Term.__init__(self)
        if isinstance(elems, Term):
            elems = (elems,)
        assert all(isinstance(e, Term) for e in elems),\
            'Array: elems {0} should be a Term or Terms'.format(elems)
        self.elems = tuple(elems)
    def __eq__(self, other):
        return (isinstance(other, Array)
                and hash(self) == hash(other)
                and self.elems == other.elems)
    def __lt__(self, other):
        if isinstance(other, Array):
            return self.elems < other.elems
        else:
            return isinstance(other, Map)
    def __hash__(self):
        self._hash = hash(self.elems)
        return self._hash
    def __repr__(self):
        return repr(list(self.elems))
    # def __str__(self):
    #     return "{0}".format([str(x) for x in list(self.elems)])
    def __getitem__(self, index):
        if isinstance(index, NumberConst):
            return self.elems[index.num]
        else:
            return self.elems[index]
    def to_python(self):
        '''Convert ground terms to python'''
        return [a.to_python() for a in self.elems]
    def to_dot(self):
        return "[%s]" % ', '.join(a.to_dot() for a in self.elems)
    def __nonzero__(self):
        return bool(self.elems)
    def get_args(self):
        return self.elems
    def reduce_access(self, access):
        if isinstance(access, Term):
            access = [access]
        elif not isinstance(access, list):
            raise ValueError('Illegal access: {0}: {1} should be a list'
                             .format(access, type(access)))
        if access:
            if isinstance(access[0], int):
                idx = access[0]
            elif isinstance(access[0], NumberConst):
                idx = access[0].num
            else:
                raise ValueError('Illegal access for term {0}: {1} should be a number'
                                 .format(self, access))
            if 0 <= idx and idx < len(self.elems):
                return self.elems[idx].reduce_access(access[1:])
            else:
                raise ValueError('Illegal access for term {0}: {1} should be between 0 and {2}'
                                 .format(self, access[0], len(self.elems)))
        else:
            return self

class Map(Term):
    """Map (dict) terms"""
    def __init__(self, items):
        """items is a list of tuple pairs (or something with an iteritems method)"""
        if not isinstance(items, (dict, tuple, list)):
            raise TypeError('terms.Map needs a dict, tuple, or list, given {0} of type {1}'
                            .format(items, type(items)))
        if isinstance(items, dict):
            litems = items.items()
        else:
            if not all(isinstance(x, (tuple, list)) and len(x) == 2 for x in items):
                raise TypeError('terms.Map items must be lists or tuples of length 2, given {0}'
                                .format(items))
            litems = items
        if not all(isinstance(k, (Const, basestring)) and isinstance(v, (Term, basestring))
                   for k, v in litems):
            raise TypeError('terms.Map: items {0} should be a list of (Const, Term) tuples'
                            .format(items))
        sitems = [(mk_stringconst(k.val.encode('utf8') if isinstance(k, Const) else k.encode('utf8')),
                   mk_stringconst(v if isinstance(v, basestring) else v.val) \
                   if isinstance(v, (basestring, Const)) else v)
                  for k, v in litems]
        Term.__init__(self)
        # Only allow stringconst keys; easier to ensure equality
        self.items = collections.OrderedDict(sorted(sitems))
    def __eq__(self, other):
        return (isinstance(other, Map)
                and hash(self) == hash(other)
                and self.items == other.items)
    def __lt__(self, other):
        return (isinstance(other, Map)
                and self.items < other.items)
    def __hash__(self):
        self._hash = hash(tuple(self.items.iteritems()))
        return self._hash
    def __repr__(self):
        return "{" + ", ".join('%r: %r' % (key, self.items[key]) for key in sorted(self.items)) + "}"
    # def __str__(self):
    #     if is_fileref(self) and False:
    #         fstr = mk_stringconst("file")
    #         file = self.get_args()[fstr]
    #         filestr = file.val
    #         return "FH:" + filestr
    #     else:
    #         return "{" + ", ".join('%s: %s' % (key, self.items[key]) for key in sorted(self.items)) + "}"
    def __getitem__(self, key):
        if isinstance(key, basestring):
            key = mk_stringconst(key)
        if key in self.items:
            return self.items[key]
    def __contains__(self, key):
        if isinstance(key, basestring):
            key = mk_stringconst(key)
        return key in self.items
    def to_python(self):
        '''Convert ground terms to python'''
        return dict([(k.to_python(), v.to_python())
                     for k, v in self.items.iteritems()])
    def to_dot(self):
        if mk_stringconst('file') in self.items:
            return str(self.items[mk_stringconst('file')])
        return "[%s]" % ', '.join(
            '%s: %s' % (k, v) for k, v in self.items.iteritems())
    def __nonzero__(self):
        return bool(self.items)
    def get_args(self):
        return self.items

    def reduce_access(self, access):
        if isinstance(access, Term):
            access = [access]
        elif not isinstance(access, list):
            raise ValueError('Illegal access: {0}: {1} should be a list'
                             .format(access, type(access)))
        if access:
            if isinstance(access[0], basestring):
                key = mk_stringconst(access[0])
            elif isinstance(access[0], StringConst):
                key = access[0]
            elif isinstance(access[0], IdConst):
                key = mk_stringconst(access[0].val)
            else:
                raise ValueError('Illegal access for term {0}: {1} should be a string'
                                 .format(self, access[0]))
            if key in self.items:
                return self.items[key].reduce_access(access[1:])
            else:
                raise ValueError('Illegal access for term {0}: {1} not a valid key'
                                 .format(self, access[0]))
        else:
            return self


# literals

class Literal(object):
    """
    Literals, e.g., ``'p(\"this\", 3, V)'``
    """
    
    # hashconsing of Literals
    __lits = weakref.WeakValueDictionary()
    
    __slots__ = ['pred', 'args', '_hash', '_fvars',
                 '_volatile', '_normal_form', '__weakref__']
    
    def __init__(self, pred, args):
        """
        Create a Literal object from a `pred` and `args`.
        :parameters:
        - `pred`: an instance of :class:`IdConst` or :class:`StringConst`
        - `args`: a list or tuple of :class:`Terms`
        """
        assert isinstance(pred, (IdConst, StringConst, basestring)),\
            'mk_literal: pred must be an id or string'
        if isinstance(pred, basestring):
            if id_match(pred):
                if pred[0].isupper():
                    raise ValueError('Literal predicate ids must start with lower case: {0}'
                                     .format(pred))
                else:
                    pred = mk_idconst(pred)
            else:
                pred = mk_stringconst(pred)
        self.pred = pred
        self.args = tuple([mk_term(a) for a in args])
        self._hash = None
        self._fvars = None
        self._normal_form = None
        self._volatile = False
        
    def __eq__(self, other):
        return self is other or self._equal(other)
    def _equal(self, other):
        return (isinstance(other, Literal)
                and hash(self) == hash(other)
                and self.pred == other.pred
                and self.args == other.args)
    def __lt__(self, other):
        """Arbitrary order (with hash...)"""
        # TODO a better (total?) ordering
        return self != other and hash(self) < hash(other)
    def __nonzero__(self):
        return False
    def __repr__(self):
        if self.args:
            return '{0}({1})'.format(self.pred, ', '.join(map(repr, self.args)))
        else:
            return '{0}'.format(self.pred)
    # def __str__(self):
    #     if self.args:
    #         return '{0}({1})'.format(self.pred, ', '.join(map(str, self.args)))
    #     else:
    #         return '{0}'.format(self.pred)
    def to_python(self):
        return {'pred': self.pred.to_python(),
                'args': [a.to_python() for a in self.args]}
    def to_dot(self):
        return "%s(%s)".format(self.pred, ', '.join(a.to_dot() for a in self.args))
    def __hash__(self):
        self._hash = hash((self.pred, self.args))
        return self._hash
    def hashcons(self):
        """Returns the literal that is representative for the equivalence
        class of literals that are equal to self.
        >>> t = mk_literal(mk_idconst('p'), [mk_stringconst("foo")])
        >>> t.hashcons() == t
        True
        >>> t.hashcons() is mk_literal(mk_idconst('p'), [mk_stringconst("foo")]).hashcons()
        True
        """
        return Literal.__lits.setdefault(self, self)
    def unify(self, other):
        if (isinstance(other, Literal)
            and self.pred == other.pred
            and len(self.args) == len(other.args)):
            if len(self.args) == 0:
                return Subst()
            elif len(self.args) == 1:
                return self.args[0].unify(other.args[0])
            else:
                left = Array(self.args)
                right = Array(other.args)
                return left.unify(right)
    def is_volatile(self):
        """Check whether the literal is volatile"""
        return self._volatile
    def set_volatile(self):
        """Mark the symbol as volatile."""
        self._volatile = True
    def get_pred(self):
        return self.pred
    def is_ground(self):
        return not self.free_vars()
    def free_vars(self):
        """Returns the set of free variables of this literal.
        """
        if self._fvars is None:
            vars = set()
            self._compute_free_vars(vars)
            self._fvars = frozenset(vars)
        return self._fvars
    def _compute_free_vars(self, vars):
        """Adds the free vars of the literal to vars"""
        for t in self.args:
            t._compute_free_vars(vars)
    def normalize(self):
        if self.is_ground():
            return (Subst(), self)
        fvars = self.ordered_free_vars()
        renaming = Subst(dict( (v, mk_var(i)) for \
            i, v in enumerate(fvars) ))
        return (renaming, renaming(self))
    def is_normalized(self):
        """Checks whether the term is normalized"""
        if self._normal_form is None:
            self._normal_form = self.normalize()[1]
        return self._normal_form == self
    def ordered_free_vars(self, l=None):
        """Returns the list of variables in the term, by order of prefix
        traversal. Free vars may occur several times in the list
        """
        if l is None:
            l = []
        else:
            for t in self.args:
                t.ordered_free_vars(l)
    def first_symbol(self):
        return self.pred.first_symbol()
    def get_args(self):
        return self.args
        

class InfixLiteral(Literal):
    """Class for <, etc."""
    def __repr__(self):
        return '{0} {1} {2}'.format(self.args[0], self.pred, self.args[1])

# ----------------------------------------------------------------------
# clauses
# ----------------------------------------------------------------------

def mk_clause(head, body):
    """Constructor for clauses"""
    return Clause(head, body)

class Clause(object):
    """A Horn clause, with a head and a (possibly empty) body.

    >>> Clause(mk_literal(mk_idconst('p'), []), [])
    p.
    >>> Clause(mk_literal(mk_idconst('p'), []), [mk_var(1), mk_map({mk_stringconst('foo'): mk_numberconst('42')})])
    p :- X1, {"foo": 42}.
    """
    def __init__(self, head, body, temp=False):
        self.head = head
        self.body = tuple(body)
        # compute the free variables (used to be local to the non temp case)
        self._free_vars = frozenset([]).union(* (x.free_vars() for x in body))
        # check that the clause is well-formed: all variables in the head are
        # bound in the body
        if not temp:
            if not (head.free_vars() <= self._free_vars):
                print >>sys.stderr, head
                for b in body:
                    print >>sys.stderr, b
                print >>sys.stderr, head.free_vars()
                print >>sys.stderr, self._free_vars
                assert False, 'datalog restriction fails! Clause __init__ unhappy'
        self._is_ground = head.is_ground() and all(x.is_ground() for x in body)
        self._done = True  # freeze

    def __setattr__(self, attr, val):
        if getattr(self, '_done', False):
            raise ValueError('immutable term')
        super(Clause, self).__setattr__(attr, val)

    def __hash__(self):
        h = hash(self.head)
        for x in self.body:
            h = hash( (h, x) )
        return h

    def __eq__(self, other):
        return (isinstance(other, Clause)
                and self.head == other.head
                and self.body == other.body)

    def __repr__(self):
        if self.body:
            return '{0} :- {1}.'.format(self.head,
                ', '.join(repr(x) for x in self.body))
        else:
            return '{0}.'.format(self.head)

    # def __str__(self):
    #     if self.body:
    #         return '{0!s} :- {1}.'.format(self.head,
    #                                     ', '.join(str(x) for x in self.body))
    #     else:
    #         return '{0!s}.'.format(self.head)

    def is_ground(self):
        """Checks whether the clause contains no variables"""
        return self._is_ground

    def free_vars(self):
        """Free variables of the clause (equivalent to the free variables
        of the body of the clause).
        """
        return self._free_vars

    def rename(self, offset=None):
        """Perform a renaming of the variables in the clause, using
        variables that do not occur in the clause.

        If an offset is provided, it will be used instead of finding one
        that ensures the absence of variables collisions.

        Returns (renaming, renamed_clause)

        >>> c = Clause(mk_var(1), [mk_var(1), mk_var('X')])
        >>> _, c2 = c.rename()
        >>> c2.free_vars().intersection(c.free_vars())
        frozenset([])
        >>> c2.head.free_vars() <= c2.free_vars()
        True
        >>> c.rename(offset=4)
        (subst(X1 = X4, X = X5), X4 :- X4, X5.)
        """
        fvars = self.free_vars()
        if not fvars:
            return [], self
        elif offset is None:
            # compute an offset: by adding this number to the variables,
            # we are sure never to collide with fvars
            offset = max(v.get_val() for v in fvars if isinstance(v.get_val(), int)) + 1
        renaming = Subst()
        for i, v in enumerate(fvars):
            renaming.bind(v, mk_var(i + offset))
        assert renaming.is_renaming(), 'renaming no a renaming; rename unhappy'
        return (renaming, renaming(self))

def mk_fact_rule(head):
    """Constructor for FactRules"""
    return FactRule(head)

def mk_derivation_rule(head, body):
    """Constructor for DerivationRules"""
    return DerivationRule(head, body)

def mk_inference_rule(head, body):
    """Constructor for InferenceRules"""
    return InferenceRule(head, body)

class FactRule(Clause):
    def __init__(self, head, temp=False):
        Clause.__init__(self, head, [], temp)

class DerivationRule(Clause):
    def __init__(self, head, body, temp=False):
        Clause.__init__(self, head, body, temp)
    
class InferenceRule(Clause):
    def __init__(self, head, body, temp=False):
        assert isinstance(head, Literal), 'Bad head: {0}: {1}'.format(head, type(head))
        assert all(isinstance(b, Literal) for b in body), 'Bad body: {0}'.format(body)
        Clause.__init__(self, head, body, temp)
        
# ----------------------------------------------------------------------
# claims
# ----------------------------------------------------------------------

def mk_claim(lit, reason):
    """Constructor for claims"""
    return Claim(lit, reason)

class Claim(object):
    """
    A claim is a pair of a ground literal and an explanation.

    The explanation can be a derivation rule, an inference rule, or an
    application of an interpreted predicate.
    """
    def __init__(self, literal, reason):
        """Create the claim. reason can be a string or a Clause."""
        assert isinstance(literal, Literal), 'Literal expected'
        assert literal.is_ground(), 'Non-ground claim {0}, free_vars {1}'.format(literal, literal.free_vars())
        self.literal = literal
        if isinstance(reason, Clause):
            self.subst = reason.head.unify(literal)
        self.reason = reason
        self._hash = hash((self.literal, self.reason))

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        return (isinstance(other, self.__class__)
                and other.literal == self.literal
                and self.reason == other.reason)

    def __lt__(self, other):
        return self != other and self.literal < other.literal

    def __repr__(self):
        if isinstance(self.reason, basestring):
            reason = '"' + self.reason + '"'
        else:
            reason = self.reason
        return 'claim({0}, reason={1})'.format(self.literal, reason)
    
    # def __str__(self):
    #     return 'claim({0}, reason=NP)'.format(self.literal)

def mk_derived_claim(lit, reason):
    """Makes a DerivedClaim"""
    return DerivedClaim(lit, reason)

class DerivedClaim(Claim):
    '''
    Claim establised by derivation.
    '''
    def __init__(self, literal, reason):
        assert isinstance(reason, DerivationRule), 'reason not a DerivationRule, DerivedClaim __init__ unhappy.'
        Claim.__init__(self, literal, reason)        
        
    def __repr__(self):
        return 'derivedClaim({0}, reason={1})'.format(self.literal, self.reason)

def mk_proved_claim(lit, reason):
    """Makes a DerivedClaim"""
    return ProvedClaim(lit, reason)
        
class ProvedClaim(Claim):
    '''
    Claim establised by inference.
    '''
    def __init__(self, literal, reason):
        assert isinstance(reason, InferenceRule), 'reason not a InferenceRule, ProvedClaim __init__ unhappy.'
        Claim.__init__(self, literal, reason)        

    def __repr__(self):
        return 'provedClaim({0}, reason={1})'.format(self.literal, self.reason)

def mk_interpreted_claim(lit, reason):
    """Makes a InterpretedClaim"""
    return InterpretedClaim(lit, reason)
        
class InterpretedClaim(Claim):
    '''
    Claim established by an interpretation.
    '''
    def __init__(self, literal, reason):
        Claim.__init__(self, literal, reason)

    def __repr__(self):
        return 'interpretedClaim({0}, reason={1})'.format(self.literal, self.reason)
        
# ----------------------------------------------------------------------
# substitutions and renamings
# ----------------------------------------------------------------------

def mk_subst(**bindings):
    """Named arguments constructor for substitutions. It builds
    terms from its named arguments.

    >>> mk_subst(X=mk_numberconst(42), Y=mk_array([mk_numberconst(1),mk_numberconst(2),mk_numberconst(3)]))
    subst(X = 42, Y = [1, 2, 3])
    """
    term_bindings = dict((mk_var(k), v) for k, v in bindings.iteritems())
    return Subst(term_bindings)

class Subst(object):
    """A substitution.

    >>> s = Subst( { mk_var(1): mk_stringconst('p'),
    ...         mk_var(2): mk_stringconst('u') } )
    >>> s
    subst(X1 = "p", X2 = "u")
    >>> sorted(s.domain())
    [X1, X2]
    >>> sorted(s.range())
    ["p", "u"]
    >>> s.is_empty()
    False
    >>> len(s)
    2
    >>> s.restrict( [mk_var(1)] )
    subst(X1 = "p")
    """

    __slots__ = ['_bindings', '_hash', '_introduced',
                 '_timestamp', '_introduced_timestamp', '__weakref__']

    def __init__(self, bindings=None):
        """Initialize the substitution"""
        self._bindings = []
        self._hash = None
        self._timestamp = 0  # modification timestamp
        self._introduced_timestamp = 0  # last update of introduced
        self._introduced = set()  # set of introduced variables
        if bindings is not None:
            if isinstance(bindings, dict):
                for k, v in bindings.iteritems():
                    self.bind(k, v)
            elif isinstance(bindings, list) or isinstance(bindings, tuple):
                for k, v in bindings:
                    self.bind(k, v)
            else:
                assert False, 'unknown kind of substitution'

    def __eq__(self, other):
        """Equality between substitutions."""
        return isinstance(other, Subst) and self._bindings == other._bindings

    def __hash__(self):
        return hash(frozenset(self._bindings))
    
    def __repr__(self):
        """Representation of the subst"""
        return "subst(%s)" % ', '.join(
            '%s = %s' % (k, v) for k, v in self._bindings)

    def __lt__(self, other):
        """Lexicographic order on the sorted bindings"""
        return self._bindings < other._bindings

    def __len__(self):
        """Number of bindings in the subst."""
        return len(self._bindings)

    def __getitem__(self, t):
        """Apply a substitution to a term"""
        if isinstance(t, basestring):
            t = mk_var(t)
        return self.__call__(t)

    def __call__(self, t):
        """Apply the substitution to a term.

        >>> s = Subst( {mk_var(1): mk_stringconst('foo')} )
        >>> s
        subst(X1 = "foo")
        >>> s(mk_var(1))
        "foo"
        >>> s(mk_var(2))
        X2
        >>> t = mk_array( [mk_stringconst("foo"), mk_numberconst('42'), mk_map({mk_stringconst("bar"): mk_var(1)}) ] )
        >>> t.is_ground()
        False
        >>> t
        ["foo", 42, {"bar": X1}]
        >>> s(t)
        ["foo", 42, {"bar": "foo"}]
        >>> s(t) != t
        True
        """
        if isinstance(t, Term):
            if t.is_ground():
                return t
            elif t.is_var():
                for i in xrange(len(self._bindings)):
                    if self._bindings[i][0] == t:
                        return self._bindings[i][1]
                return t
            elif t.is_const():
                return t
            # elif t.is_apply():
            #     return mk_apply(self(t.val), map(self, t.args))
            elif t.is_array():
                return mk_array(map(self, t.elems))
            elif t.is_map():
                return mk_map(dict((self(k), self(v)) for k, v in \
                              t.items.iteritems()))
            else:
                assert False, 'unknown kind of term in __call__'
        elif isinstance(t, Literal):
            return t.__class__(self(t.pred), map(self, t.args))
        elif isinstance(t, Clause):
            return t.__class__(self(t.head), map(self, t.body))
        else:
            print t.__class__
            print t
            assert False, 'bad arg %s of class %s; __call__ unhappy' % (t, t.__class__)
        
    def __nonzero__(self):
        """A substitution, even empty, is to be considered as a true value"""
        return True

    def __contains__(self, var):
        """Checks whether var is bound by the substitution

        >>> s = Subst({ mk_var(1): mk_numberconst(42)})
        >>> mk_var(1) in s
        True
        >>> mk_var(2) in s
        False
        """
        assert var.is_var(), 'var ain\'t a var; __contains__ unhappy'
        for k, _ in self._bindings:
            if k == var:
                return True
        return False

    def get(self, str):
        t = self(mk_var(str))
        return dumps(t)
    
    def get_bindings(self):
        return self._bindings
    
    def clone(self):
        """Return a copy of the substitution."""
        s = Subst()
        for k, v in self._bindings:
            s.bind(k, v)
        return s

    def bind(self, var, t):
        """Bind var to t in the substitution. Var must not
        be already bound.
        """
        assert var.is_var(), 'var ain\'t a var; bind unhappy'
        assert isinstance(t, Term), '{0}: {1} not a term; bind unhappy'.format(t, type(t))
        if var == t:
            return  # no-op
        assert self(var) == var, 'var not bound; bind unhappy'
        self._bindings.append( (var, t) )
        self._bindings.sort()
        self._timestamp += 1  # update timestamp

    def is_empty(self):
        """Checks whether the substitution is empty."""
        return not self._bindings

    def range(self):
        """Values of the substitution"""
        for _, v in self._bindings:
            yield v

    def domain(self):
        """Variables bound by the substitution"""
        for k, _ in self._bindings:
            yield k

    def introduced(self):
        """Variables introduced by the substitution (iterator)"""
        if self._timestamp > self._introduced_timestamp:
            # must update the set of introduced variables
            self._introduced.clear()
            for t in self.range():
                self._introduced.update(t.free_vars())
            self._introduced_timestamp = self._timestamp
        for var in self._introduced:
            yield var  # yield content of the set

    def compose(self, other):
        """Composes the two substitutions,  self o other.
        The resulting substitution
        is { x -> other(self(x)) } for x in
        domain(self) union domain(other)

        be careful that this is backward w.r.t. function composition,
        since t \sigma \theta = t (\sigma o \theta)

        >>> s = Subst({mk_var(1): mk_var(3)})
        >>> t = Subst({mk_var(2): mk_array([mk_idconst('p'), mk_var(1)]),
        ...     mk_var(3): mk_idconst('b')})
        >>> s.compose(t) == Subst({mk_var(1): mk_idconst('b'),
        ...     mk_var(2): mk_array([mk_idconst('p'), mk_var(1)]),
        ...     mk_var(3): mk_idconst('b')})
        True
        >>> s.compose(s) == s
        True
        """
        assert isinstance(other, Subst)
        s = Subst()
        for var in self.domain():
            s.bind(var, other(self(var)))
        for var in other.domain():
            if var not in self:
                s.bind(var, other(var))
        return s

    def join(self, other):
        """Take the join of the two substitutions, self . other,
        the resulting substitution is::

        { x -> other(self(x)) for x in domain(self) } union
        { x -> other(x) } for x in domain(other) vars(range(self)).

        >>> s = Subst({mk_var(1): mk_var(3)})
        >>> t = Subst({mk_var(2): mk_array([mk_idconst('p'), mk_var(1)]),
        ...            mk_var(3): mk_idconst('b')})
        >>> s.join(t) == Subst({mk_var(1): mk_idconst('b'),
        ...     mk_var(2): mk_array([mk_idconst('p'), mk_var(1)]) })
        True
        """
        assert isinstance(other, Subst)
        s = Subst()
        for var, t in self._bindings:
            s.bind(var, other(t))
        for var in other.domain():
            if var not in self.introduced():
                s.bind(var, other(var))
        return s

    def is_renaming(self):
        """Checks whether the substitution is a renaming.

        >>> Subst( { mk_var(1): mk_stringconst("a") } ).is_renaming()
        False
        >>> Subst( { mk_var(1): mk_var(2) } ).is_renaming()
        True
        """
        return all(x.is_var() for x in self.range()) and \
            len(list(self.domain())) == len(list(self.range()))

    def restrict(self, domain):
        """Returns a new substitution, which is the same but
        restricted to the given domain.

        >>> s = Subst({mk_var(2): mk_array([mk_idconst('p'), mk_var(1)]),
        ...            mk_var(3): mk_idconst('b')})
        >>> s.restrict([mk_var(2)])
        subst(X2 = [p, X1])
        """
        s = Subst()
        for var, t in self._bindings:
            if var in domain:
                s.bind(var, t)
        return s

# ----------------------------------------------------------------------
# json parsing and printing
# ----------------------------------------------------------------------

class TermJSONEncoder(json.JSONEncoder):
    """Custom encoder in JSON. It deals with terms, clauses,
    substitutions and claims.
    """
    def default(self, o):
        "try to encode terms"
        if 'to_json' in dir(o):
            return o.to_json()
        elif isinstance(o, Term):
            if o.is_var():
                return { '__Var': o.get_val() }
            elif o.is_stringconst():
                return { '__StringConst': o.get_val() }
            elif o.is_idconst():
                return { '__IdConst': o.get_val() }
            elif o.is_boolconst():
                return { '__BoolConst': o.get_val() }
            elif o.is_numconst():
                return { '__NumberConst': o.get_val() }
            elif o.is_array():
                return { '__Array': list(o.get_args()) }
            elif o.is_map():
                return { '__Map': dict((k.val, v) for k, v in o.get_args().iteritems()) }
        elif isinstance(o, Literal):
            return {'__Literal': [o.pred] + list(o.args)}
        elif isinstance(o, Clause):
            return {'__Clause': [o.head] + list(o.body)}
        elif isinstance(o, Subst):
            return {'__Subst': list(o.get_bindings())}
        elif isinstance(o, Claim):
            return {'__Claim': o.literal,
                    '__Reason': o.reason }
        print 'Should have to_json defined for {0}'.format(o.__class__)
        return json.JSONEncoder.default(self, o)  # defer to default

class TermReadableJSONEncoder(json.JSONEncoder):
    """Custom encoder in JSON. It deals with terms, clauses,
    substitutions and claims, but prints them more readably for clients.
    """
    def default(self, o):
        "try to encode terms"
        if isinstance(o, Term):
            if o.is_var():
                return {'name': o.get_val()}
            elif o.is_const():
                return o.get_val()
            # elif o.is_apply():
            #     return {'pred': o.get_pred(), 'args': list(o.get_args())}
            elif o.is_array():
                return list(o.get_args())
            elif o.is_map():
                return dict((repr(k), v) for k, v in o.get_args().iteritems())
        elif isinstance(o, Literal):
            return {'pred': o.pred, 'args': list(o.args)}
        elif isinstance(o, Clause):
            return {'head': o.head, 'body': list(o.body)}
        elif isinstance(o, Subst):
            return {'__Subst': list(o.get_bindings())}
        elif isinstance(o, Literal):
            return {'__Literal': o.pred, 'args': list(o.args)}
        elif isinstance(o, Claim):
            return {'__Claim': o.literal,
                    '__Reason': o.reason }
        return json.JSONEncoder.default(self, o)  # defer to default

def term_object_hook(o):
    """Given the JSON object o (a dict), tries to parse terms,
    claims, clauses and substs from it.
    """
    # detect special kinds of maps
    if '__Var' in o:
        return mk_var(o['__Var'])
    elif '__IdConst' in o:
        l = o['__IdConst']
        return mk_idconst(l)
    elif '__StringConst' in o:
        l = o['__StringConst']
        return mk_stringconst(l)
    elif '__BoolConst' in o:
        l = o['__BoolConst']
        return mk_boolconst(l)
    elif '__NumberConst' in o:
        l = o['__NumberConst']
        return mk_numberconst(l)
    elif '__Array' in o:
        l = o['__Array']
        return Array(l)
    elif '__Map' in o:
        l = o['__Map']
        return Map(dict([(mk_stringconst(k), v) for k, v in l.iteritems()]))
    elif '__Clause' in o:
        l = o['__Clause']
        assert len(l) >= 1
        return Clause(l[0], l[1:])
    elif '__Subst' in o:
        l = o['__Subst']
        return Subst( [(k, v) for k, v in l] )
    elif '__Literal' in o:
        l = o['__Literal']
        return Literal(l[0], l[1:])
    elif '__Claim' in o and '__Reason' in o:
        lit = o['__Claim']
        reason = o['__Reason']
        return Claim(lit, reason=reason)
    elif '__Subst' in o:
        bindings = o['__Subst']
        return Subst( [(mk_term(k), mk_term(v)) for k, v in bindings] )
    # default choice: just return the object
    return o


def remove_unicode(input):
    """json.loads will read in strings as unicode, hence creates u'foo' forms,
    which are difficult to work with.  This function rebuilds the structures as
    plain utf8 strings"""
    if isinstance(input, dict):
        return {remove_unicode(key): remove_unicode(value) for key, value in input.iteritems()}
    elif isinstance(input, list):
        return [remove_unicode(element) for element in input]
    elif isinstance(input, unicode):
        return input.encode('utf-8')
    else:
        return input

# The dump functions convert obj to JSON, load converts JSON to obj
# Thus we should have load(dump(obj) == obj and dump(load(json)) == json
# For any obj in terms, and any legitimate json string

def dump(obj, filedesc, *args, **kwargs):
    """Print the object in JSON on the given file descriptor."""
    json.dump(obj, filedesc, cls=TermJSONEncoder, *args, **kwargs)

def dumps(obj, *args, **kwargs):
    """Print the object in JSON into a string"""
    return json.dumps(obj, cls=TermJSONEncoder, *args, **kwargs)

def dumps_readably(obj, *args, **kwargs):
    """Print the object in JSON into a string, old form of term
    """
    return json.dumps(obj, cls=TermReadableJSONEncoder, *args, **kwargs)

def load(filedesc, *args, **kwargs):
    """Print the object in JSON on the given file descriptor.
    """
    return json.load(filedesc, object_hook=term_object_hook, *args, **kwargs)

def loads(s, *args, **kwargs):
    """Converts a JSON string to term classes

    >>> pid = mk_idconst('p')
    >>> loads(dumps(pid)) == pid
    True
    >>> dumps(loads('{"__IdConst": "p"}')) == '{"__IdConst": "p"}'
    True

    >>> arr = mk_array([mk_idconst('a'), mk_var('V'), mk_var(1), mk_numberconst(3)])
    >>> loads(dumps(arr)) == arr
    True
    >>> arstr = '{"__Array": [{"__IdConst": "a"}, {"__Var": "V"}, {"__Var": 1}, {"__NumberConst": "3"}]}'
    >>> dumps(loads(arstr)) == arstr
    True
    
    >>> fref = mk_map({mk_stringconst('file'): mk_stringconst('doc.pdf'),
    ...                mk_stringconst('sha1'): mk_stringconst("9af")})
    >>> loads(dumps(fref)) == fref
    True
    >>> fstr = '{"__Map": {"sha1": {"__StringConst": "9af"}, "file": {"__StringConst": "doc.pdf"}}}'
    >>> dumps(loads(fstr)) == fstr
    True

    >>> lit = mk_literal(mk_idconst('p'), [mk_idconst('a'), mk_var('V'), mk_var(1), mk_numberconst(3)])
    >>> loads(dumps(lit)) == lit
    True
    >>> litstr = '{"__Literal": [{"__IdConst": "p"}, {"__IdConst": "a"}, {"__Var": "V"}, {"__Var": 1}, {"__NumberConst": "3"}]}'
    >>> dumps(loads(litstr)) == litstr
    True

    >>> cls = Clause(mk_literal(mk_idconst('p'), []), [])
    >>> loads(dumps(cls)) == cls
    True
    >>> clstr = '{"__Clause": [{"__Literal": [{"__IdConst": "p"}]}]}'
    >>> dumps(loads(clstr)) == clstr
    True
    >>> cls2 = Clause(mk_literal(mk_idconst('p'), []), [mk_var(1), mk_map({mk_stringconst('foo'): mk_numberconst('42')})])
    >>> loads(dumps(cls2)) == cls2
    True
    >>> clstr2 = '{"__Clause": [{"__Literal": [{"__IdConst": "p"}]}, {"__Var": 1}, {"__Map": {"foo": {"__NumberConst": "42"}}}]}'
    >>> dumps(loads(clstr2)) == clstr2
    True

    >>> sbst = Subst( { mk_var(1): mk_stringconst('p'),
    ...                 mk_var(2): mk_stringconst('u') } )
    >>> loads(dumps(sbst)) == sbst
    True
    >>> sbstr = '{"__Subst": [[{"__Var": 1}, {"__StringConst": "p"}], [{"__Var": 2}, {"__StringConst": "u"}]]}'
    >>> dumps(loads(sbstr)) == sbstr
    True
    """
    return remove_unicode(json.loads(s, object_hook=term_object_hook, *args, **kwargs))
