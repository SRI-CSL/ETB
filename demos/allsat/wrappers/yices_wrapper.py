import os, tempfile
from etb.wrapper import Tool, BatchTool, Substitutions, Success, Failure, Errors
from etb.terms import mk_term

class Yices_batch(BatchTool):
    '''
    Simple subprocess interface for one-shot invocations of yices.
    '''

    # @Tool.predicate("+left: value, +right: value")
    # def equal(self, left, right):
    #     if left == right:
    #         return [{}]
    #     else:
    #         return []

    @Tool.predicate("-out: value")
    def nil(self, v):
        if v.is_var():
            return Substitutions(self, [ {v: mk_term([])} ])
        else:
            return Errors(self, ["nil: checking not supported"])
    
    @Tool.predicate("+head: value, +tail: value, -out: value")
    def cons(self, head, tail, out):
        if tail.is_const() and tail.val is None:
            res = [head]
        else:
            res = [head.val] + list(tail.get_args())
        return Substitutions(self, [self.bindResult(out, res)])
    
    @Tool.predicate("+yices_file: file, +model: value, -out: file")
    def negateModel(self, yices_file, model, out):
        '''
        Create a new yices file containing the input yices files and
        asserting the negation of the model.
        '''
        with tempfile.NamedTemporaryFile(delete=False, dir='.') as oc:
            out_file = os.path.basename(oc.name)
            with open(yices_file['file'], 'r') as ic:
                for line in ic:
                    print >>oc, line
            print >>oc, '(assert (not (and %s)))' % str(model)
        outref = self.fs.put_file(out_file)
        return Substitutions(self, [self.bindResult(out, outref)])

    @Tool.predicate("+formula: file, -result: value, -model: value")
    def yices(self, formula, result, model):
        with tempfile.NamedTemporaryFile(delete=False, dir='.') as oc:
            new_file = os.path.basename(oc.name)
            print >>oc, '(include "%s")' % formula['file']
            print >>oc, '(check)'
        (ret, out, err) = self.callTool('yices', '-e', new_file)
        if ret != 0:
            self.log.error(err)
            return Errors(self, ['error("yices", "%s")' % err])
        output = out.split('\n')
        if output[0] == 'sat':
            s = self.bindResult(result, output[0])
            s = self.bindResult(model, ''.join(output[1:]), current=s)
        else:
            s = self.bindResult(result, output[0])
            s = self.bindResult(model, [], current=s)
        if s == []:
            return Failure(self)
        else:
            return Substitutions(self, [s])
    
def register(etb):
    "Register the tool"
    etb.add_tool(Yices_batch(etb))
