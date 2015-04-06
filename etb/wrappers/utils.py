# A library of util functions, without any tool invocation

from etb.wrapper import Tool, Substitutions, Lemmata, Success, Failure

import etb.terms

class Utils(Tool):
    """Library of util functions, without tool invocation"""

    @Tool.sync
    @Tool.predicate("+low: value, +up: value, result: value")
    def in_range(self, low, up, result):
        """Result in [low, up] range."""
        low = int(low.val)
        up = int(up.val)
        if low > up:
            return Failure(self)
        if result.is_var():
            return Substitutions(self, [self.bindResult(result, i) for i in range(low, up+1)])
            #return Substitutions(self, [{result : etb.terms.mk_const(i)} for i in range(low, up+1)])
        else:
            result = int(result.val)
            if low <= result <= up:
                return Success(self)
            else:
                return Failure(self)
    @Tool.predicate("+low: value, +up: value, result: value")
    def in_range_async(self, low, up, result):
        """Result in [low, up] range."""
        low = int(low.val)
        up = int(up.val)
        if low >= up:
            return Failure(self)
        if result.is_var():
            # result iterate from low to up
            return Substitutions(self, [ self.bindResult(result, i) for i in range(low, up+1)])
            #return Substitutions(self, [{result : etb.terms.mk_const(i)} for i in range(low, up+1)])
        else:
            result = int(result.get_val())
            if low <= result <= up:
                return Success(self)
            else:
                return Failure(self)
            
    @Tool.sync
    @Tool.predicate('+low:value, +high:value, +v:value')
    def between(self, low, high, v):
        '''Use Yices to check that v is within [low, high]'''

        with open('between.yices', 'w') as yices_file:
            yices_file.write('(assert (<= %s %s))' % (low, v))
            yices_file.write('(assert (<= %s %s))' % (v, high))
            yices_file.write('(check)')
        yices_file_ref = self.fs.put_file('between.yices')
        return Lemmata(self, [{}], [ 'yices(%s, "sat")' % yices_file_ref ])

    # Two dummy predicates used for testing
    
    @Tool.predicate('+n: value')
    def dummy(self, n):
        n = int(n.val)
        if n == 0 :
            return Success(self)
        else :
            return Lemmata(self, [{}], [ 'dummy(%s)' % str(n-1) ] )

    @Tool.predicate('+n: value')
    def bad_dummy(self, n):
        n = int(n.val)
        if n == 0 :
            return Failure(self)
        else :
            return Lemmata(self, [{}], [ 'bad_dummy(%s)' % str(n-1) ])

def register(etb):
    "Register the tool"
    etb.add_tool(Utils(etb))

