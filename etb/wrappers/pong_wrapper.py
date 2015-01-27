from etb.wrapper import Tool, Lemmata, Substitutions, Success, Failure

import etb.parser

class Pong(Tool):

    @Tool.predicate('+n: value')
    def pong(self, n):
        n = int(n.val)
        if n == 0 :
            return Success(self)
        else :
            # either for should work:
            #return Queries(self, [{}], [ 'ping(%s)' % str(n-1) ] )
            return Lemmata(self, [{}], [ etb.parser.parse('ping({0})'.format(n-1), 'literal') ] )

def register(etb):
    "Register the tool"
    etb.add_tool(Pong(etb))

