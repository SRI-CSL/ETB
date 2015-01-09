import os, tempfile
from etb.wrapper import Tool, BatchTool, Substitutions, Success, Failure
from etb.terms import mk_term

class List_batch(BatchTool):
    '''
    Simple utils.
    '''

    @Tool.predicate("+left: value, +right: value")
    def equal(self, left, right):
        if left == right:
            return Success(self)
        else:
            return Failure(self)

    @Tool.predicate("-out: value")
    def nil(self, v):
        if v.is_var():
            return Substitutions(self, [ {v: mk_term([])} ])
        else:
            return Errors(self,  [ "checking not supported" ] )
    
    @Tool.predicate("+head: value, +tail: value, -out: value")
    def cons(self, head, tail, out):
        if tail.is_const() and tail.val is None:
            res = [head]
        else:
            res = [head.val] + list(tail.get_args())
        return Substitutions(self, [self.bindResult(out, res)])
    
    
def register(etb):
    "Register the tool"
    etb.add_tool(List_batch(etb))
