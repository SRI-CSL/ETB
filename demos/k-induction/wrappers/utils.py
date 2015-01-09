# A library of util functions, without any tool invocation

from etb.wrapper import Tool

import etb.terms

class Utils(Tool):
    """Library of util functions, without tool invocation"""

    @Tool.sync
    @Tool.predicate("+left: value, +right: value")
    def equal(self, left, right):
        if left == right:
            return [{}]
        else:
            return []

    @Tool.sync
    @Tool.predicate("+left: value, +right: value")
    def lte(self, left, right):
        if int(left.val) <= int(right.val):
            return [{}]
        else:
            return []
        
    @Tool.sync
    @Tool.predicate("+n: value, -pn: value")
    def pred(self, n, pn):
        '''Predecessor - we stop at 1 (that is what we need here)'''
        n = int(n.val)
        if n > 1:
            return [self.bindResult(pn, n-1)]
        else:
            return []

    @Tool.sync
    @Tool.predicate("+n: value, -sn: value")
    def succ(self, n, sn):
        n = int(n.val)
        return [self.bindResult(sn, n+1)]
        
    @Tool.sync
    @Tool.predicate("+low: value, +up: value, -result: value")
    def in_range(self, low, up, result):
        """Result in [low, up] range."""
        low = int(low.val)
        up = int(up.val)
        if low > up:
            return []
        if result.is_var():
            return [{result : etb.terms.mk_const(i)} for i in range(low, up+1) ]
        else:
            result = int(result.val)
            if low <= result <= up:
                return [{}]
            else:
                return []

def register(etb):
    etb.add_tool(Utils(etb))

