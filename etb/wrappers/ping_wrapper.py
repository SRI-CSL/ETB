from etb.wrapper import Tool, Lemmata, Substitutions, Success, Failure

import etb.parser

class Ping(Tool):

    @Tool.predicate('+n: value')
    def ping(self, n):
        n = int(n.val)
        if n == 0 :
            return Success(self)
        else :
            # either for should work:
            #return Queries(self, [{}], [ 'pong(%s)' % str(n-1) ] )
            return Lemmata(self, [{}], [ etb.parser.parse('pong({0})'.format(n-1), 'literal') ] )

def register(etb):
    "Register the tool"
    etb.add_tool(Ping(etb))

