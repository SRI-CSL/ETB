""" Example External Predicates

A simple external predicate `less_than` that can be called from an `InterpretState`
(see dummy example in
:func:`etb.datalog.engine.InterpretStateLessThan.interpret`).

.. warning::
    This module is for simple tests only (used in the datalog engine's unit tests for
    example).

"""

def less_than(s1, s2):
    """
    Determine whether `s1` is smaller than `s2`. If they are not, a
    `ValueError` is thrown.

    :parameters:
        - `s1`: a string representing an integer
        - `s2`: a string representing an integer
    :returntype:
        `True` or `False`

    """
    try:
        sint1 = int(s1)
        sint2 = int(s2)
        return sint1 < sint2
    except ValueError:
        return False
