"""Creating and manipulating Indices

The Index is based on discrimation trees as for example "Experiments with
Discrimination-Tree Indexing and Path Indexing for Term Retrieval" by William
McCune.

This is a data structure that we use to store rules (an index on heads of
rules, on first body literals of rules, of rules with their explanations), and
of facts.

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
from functools import reduce

def add_to_index(index, key, value):
    """
    Adding a value at the key in the index.

    :parameters:
        - `index`: The index is a non-perfect discrimination tree implemented
          using a dictionary. Each key in the dictionary represents a node in
          the tree. If the value associated with that key is another
          dictionary, that dictionary reprents the subtree at that node. If the
          value associated with that key is not a dictionary, it is assumed to
          be a list of values. Each node in the tree is a positive integer (for
          non-variable symbols) or `-1` representing any variable. Indices will
          then for example have the form `{1 : { 2: { 3 : [], 4 : []}}}`.
        - `key`: a key is a list of integers (positive or negative). The key
          represents a path in the tree where each positive integer in the list
          is a node represented by itself and each negative integer will be a
          node represented by `-1` (we thus to not distinguish between
          different variables -- and hence there is a need for doing some
          postprocessing when using indices for finding matching/unifying
          items). For example, the value for key `[1,2,3]` will be reachable by
          going to the node `1`, that node's child `2`, that node's child `3`
          and checking the list of values stored at that leaf node.

        - `value`: This can be anything, it will be added to the list stored at
          leaf nodes in the discrimination tree.

    :returntype:
        `None`

    Adding a value to a key `[a,b,c,...,z]` involves then going through the index
    starting with node `a`, finding its child `b`, `b`'s child `c`, ..., and
    finally adding the value to the list stored at `z`. Any negative integers
    `d` in the key will be treated as `-1`.

    Some example output: ::

        In [42]: index = {}
        In [43]: add_to_index(index, [-1,3,4], "a")
        In [44]: index
        Out[44]: {-1: {3: {4: ['a']}}}
        In [45]: add_to_index(index, [-1,2,4], "b")
        In [46]: index
        Out[46]: {-1: {2: {4: ['b']}, 3: {4: ['a']}}}
        In [47]: add_to_index(index, [-1,3,4], "c")
        In [48]: index
        Out[48]: {-1: {2: {4: ['b']}, 3: {4: ['a', 'c']}}}

    """
    def ensure_node(d, k):
        # `k` is a list of integers (a partial literal), `d` is the current
        # dictionary node under consideration. We check whether there is
        # subnode `d[k[0]]` present. If not, we create it.
        if k[0] not in d:
            d[k[0]] = {}

    def ensure_leaf(d,k):
        # Similar as `ensure_node`, but we do not create a dictionary as a
        # subnode, but a list. That list will collect all values.
        if k[0] not in d:
            d[k[0]] = []

    def propagate_value(current_node, k):
        # We are at the last argument of the literal `k` (i.e., `k` is a list of
        # one integer), so store it in a leaf of
        # the discrimination tree.
        if len(k) == 1:
            ensure_leaf(current_node, k)
            current_node[k[0]].append(value)
        # If we are not at the last argument of the literal, create a new node
        # with as a key the current argument k[0] of literal k and recursively
        # continue.
        else:
            ensure_node(current_node, k)
            next_node = current_node[k[0]]
            k.pop(0)
            propagate_value(next_node,k)

    # Map all negative integers to -1 (we treat all variables the same).
    normalized_key = [ x if x >= 0 else -1 for x in key]
    # Put the value at the right place in the discrimination tree
    # Essentially for a literal `[1,-1,3,-1]`, we place the value at
    # `index[1][-1][3][-1]`. The leaf nodes have a list as value, the other nodes
    # have a dictionary as value (the subnodes).
    propagate_value(index, normalized_key)


def remove_from_index(index, key, value):
    """
    Remove all values `value` from the `key` in the `index`. We traverse
    through the index following the path as indicated by `key`, pick up the
    value list of the leaf node and remove all `values` from the list.
    Remove all values = value at key from the index.

    :parameters:
        - `index`: See :func:`etb.datalog.index.add_to_index`
        - `key`: See :func:`etb.datalog.index.add_to_index`
        - `value`: See :func:`etb.datalog.index.add_to_index`

    :returntype:
        `None`
    """
    def iter(node, k):
        # If `k` is empty, we reached the end so `node` has to be the value
        # list we are looking for. We remove from that list all value
        if len(k) == 0:
            node[:] = (el for el in node if el != value)
        else:
            f, rest = k[0], k[1:]
            if f in node:
                iter(node[f], rest)

    # Rewrite the key such that all variables map to `-1`
    normalized_key = [x if x >= 0 else -1 for x in key]
    predicate = normalized_key.pop(0)
    if predicate in index:
        iter(index[predicate],normalized_key)

def in_index(index, key, value):
    """
    Returns `True` if `value` is present at `key` in `index`; `False`
    otherwise.

    :parameters:
        - `index`: See :func:`etb.datalog.index.add_to_index`
        - `key`: See :func:`etb.datalog.index.add_to_index`
        - `value`: See :func:`etb.datalog.index.add_to_index`

    :returntype:
        `True` or `False`
    """
    def iter(node, k):
        if len(k) == 0:
            for el in node:
                if el == value:
                    return True
            return False
        else:
            f, rest = k[0], k[1:]
            if f in node:
                return iter(node[f], rest)
            else:
                return False

    # XXX: This is a hack to make the index work with tuples.
    # Python 2.7 is ok with using comparison operators with tuples, 
    # but Python 3.+ does not like it. It throw this type error:
    # TypeError: '>=' not supported between instances of 'tuple' and 'int'
    def normalize_x(x):
        # Map all negative integers to -1 (we treat all 
        # variables the same).
        if isinstance(x, int):
            return x if x>= 0 else -1
        elif isinstance(x, tuple):
            x_tpl = [xx if xx>= 0 else -1 for xx in x]
            return x_tpl
    # normalized_key = [x if x[0]>= 0 else -1 for x in key]
    normalized_key = [normalize_x(x) for x in key]
    predicate = normalized_key.pop(0)
    # XXX checking a list is in dict throw a type error:
    # TypeError: unhashable type: 'list'. Python 2.7 is ok with it.
    pred = tuple(predicate) if isinstance(predicate, list) else predicate
    if pred in index:
        return iter(index[pred], normalized_key)
    else:
        return False

def traverse(index):
    """
    Return a list of all values present in the index.

    :parameters:
        - `index`: See :func:`etb.datalog.index.add_to_index`
        - `key`: See :func:`etb.datalog.index.add_to_index`

    :returntype:
        a list of values (the type of the value is whatever was inserted in the
        index in the first place)
    """
    if isinstance(index, dict):
        return reduce(lambda x,y: x+y, [traverse(index[c]) for c in list(index.keys())])
    else:
        return index

def get_candidate_generalizations(index, key):
    """
    Given a `key` find all values in the `index` that are candidate
    generalizations of that key. Recall that a key is a list such as for
    example `[1,-2,3]` which would represent a literal `f(X,a)`. A candidate
    generalization is then `f(X,a)` itself but also `f(X,Y)` (say represented
    by a key `[1,-2,-4]`). One can see that we want all values that are located
    at keys that match `key` in that variables stay variables and constants can
    stay constants or be generalized to variables.

    .. warning::
        This function only makes sense if the index was constructed by assuming
        keys are integers that represent literals.

    :parameters:
        - `index`: See :func:`etb.datalog.index.add_to_index`
        - `key`: See :func:`etb.datalog.index.add_to_index`

    :returntype:
        a list of values

    Example Input/Output: ::

        In [38]: index = {}
        In [39]: add_to_index(index, [1,-2,-3],"b")
        In [40]: add_to_index(index, [1,-2,3],"a")
        In [41]: index
        Out[41]: {1: {-1: {-1: ['b'], 3: ['a']}}}
        In [42]: get_candidate_generalizations(index, [1,4,3])
        Out[42]: ['b', 'a']
    """


    # `iter` runs through the tree starting at `node` with `k` the rest of the
    # original `key` still to be processed.
    def iter(node, k):
        # If `k` is empty, we reached the end so `node` has to be the value
        # list we are looking for.
        if len(k) == 0:
            return node
        # If the first element of `k` is `-1` (a variable), the only thing more
        # general is another variable.
        elif k[0] == -1:
            # Copy the list before popping (other calls to `iter` would get
            # that modified `k` potentially)
            k2 = list(k)
            k2.pop(0)
            if -1 in node:
                return iter(node[-1],k2)
            else:
                return []
        # If the first element of `k` is a constant, the only thing more
        # general is a variable (`-1`) or the exact same constant.
        else:
            k2 = list(k)
            arg = k2.pop(0)
            if -1 in node and arg in node:
                return iter(node[-1],k2) + iter(node[arg],k2)
            elif -1 in node:
                return iter(node[-1],k2)
            elif arg in node:
                return iter(node[arg],k2)
            else:
                return []

    # Rewrite the key such that all variables map to `-1`
    normalized_key = [x if x >= 0 else -1 for x in key]
    predicate = normalized_key.pop(0)
    if predicate in index:
        return iter(index[predicate],normalized_key)
    else:
        return []


def get_candidate_specializations(index, key):
    """
    We get the values for keys in the `index` that are candidate
    specializations of `key` (a literal). A specialization of `f(X,a)` is for
    example `f(b,a)` or `f(c,a)`. We impose that all specializations are
    ground. Note that this is a pre-processing step in that bad specializations
    would still need to be filtered out. For example, `f(X,a,X)` would have as
    a specialization `f(b,a,c)` with the below code, which is not valid as `X`
    need to be specialized to the same value. The below code does not
    distinguish between different or the same variables though (recall that all
    variables get mapped to `-1` in the index).

    :parameters:
        - `index`: See :func:`etb.datalog.index.add_to_index`
        - `key`: See :func:`etb.datalog.index.add_to_index`

    :returntype:
        a list of values

    Example Input/Output: ::

        In [41]: index = {}
        In [42]: add_to_index(index, [1,4,2],"1")
        In [43]: add_to_index(index, [1,3,2],"2")
        In [44]: add_to_index(index, [1,-1,2],"3")
        In [45]: add_to_index(index, [1,4,3],"4")
        In [46]: get_candidate_specializations(index,[1,-1,2])
        Out[46]: ['2', '1']
        In [47]: get_candidate_specializations(index,[1,-1,3])
        Out[47]: ['4']
        In [48]: get_candidate_specializations(index,[1,-1,5])
        Out[48]: []
        In [49]:
    """
    def iter(node, k):
        if len(k) == 0:
            return node
        # The argument in the key is a variable (`-1`): more specific is any
        # constant.
        elif k[0] == -1:
            k2 = list(k)
            k2.pop(0)
            return reduce(lambda x,y: x+y, [iter(node[c],k2) for c in [constant for constant in node.keys() if constant > 0 ]])
        # The argument in the key is a constant: more specific is the same
        # constant.
        else:
            k2 = list(k)
            arg = k2.pop(0)
            if arg in node:
                return iter(node[arg],k2)
            else:
                return []

    normalized_key = [x if x >= 0 else -1 for x in key]
    predicate = normalized_key.pop(0)
    if predicate in index:
        return iter(index[predicate],normalized_key)
    else:
        return []

def get_candidate_matchings(index, key):
    """
    For a `key` (literal) we get all matching values in the `index`, where a
    literal matches an index key if the predicate of the literal is equal to
    the predicate of the index key, and for each argument `a`, when `a` is a
    constant, the corresponding argument in the key is `a`, and when `a` is a
    variable, the corresponding argument in the key is a variable or any
    constant. Note that we still need to filter these results to ensure we get
    unifiable results. For example, `f(X,a,X)` matches with index key
    `f(c,a,d)` as variables correspond to any constant.

    :parameters:
        - `index`: See :func:`etb.datalog.index.add_to_index`
        - `key`: See :func:`etb.datalog.index.add_to_index`

    :returntype:
        a list of values

    .. seealso:: :func:`etb.datalog.index.get_candidate_specializations`

    """
    def iter(node, k):
        if len(k) == 0:
            return node;
        # The argument in the key is variable: matching is any other variable
        # or constant.
        elif k[0] == -1:
            k2 = list(k)
            k2.pop(0)
            return reduce(lambda x,y: x+y, [iter(node[c], k2) for c in list(node.keys())])
        # The argument in the key is a constant: matching is only that constant
        # _or_ a variable.
        else:
            k2 = list(k)
            arg = k2.pop(0)
            mm = [iter(node[c],k2) for c in [d for d in list(node.keys()) if d == arg or d == -1]]
            return reduce(lambda x,y: x+y, mm, [])
    normalized_key = [x if x >= 0 else -1 for x in key]
    predicate = normalized_key.pop(0)
    if predicate in index:
        return iter(index[predicate], normalized_key)
    else:
        return []


def get_candidate_renamings(index, key):
    """
    Get all possible renamings of `key`: a renaming key is a key that
    coincides on the constants and their locations. Again note that this
    concludes too many possible renamings because of the generalization of
    variables to one symbol `-1`.

    :parameters:
        - `index`: See :func:`etb.datalog.index.add_to_index`
        - `key`: See :func:`etb.datalog.index.add_to_index`

    :returntype:
        a list of values

    .. seealso:: :func:`etb.datalog.index.get_candidate_specializations`

    """
    def iter(node, k):
        if len(k) == 0:
            return node;
        # They argument in the key is a variable: matching is any other variable
        elif k[0] == -1:
            k2 = list(k)
            k2.pop(0)
            if -1 in node:
                return iter(node[-1],k2)
            else:
                return []
        # The argument in the key is a constant: matching is only that
        # constant.
        else:
            k2 = list(k)
            arg = k2.pop(0)
            if arg in node:
                return iter(node[arg],k2)
            else:
                return []

    normalized_key = [x if x >= 0 else -1 for x in key]
    predicate = normalized_key.pop(0)
    if predicate in index:
        return iter(index[predicate], normalized_key)
    else:
        return []
