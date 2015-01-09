from etb.wrapper import Tool, Lemmata, Substitutions, Success, Failure

import etb.terms

class VeryComposite(Tool):

    @Tool.predicate('+n: value')
    def composite(self, n):
        n = abs(int(n.val))
        if isPrime(n):
            return Failure(self)
        else :
            return Success(self)
    
    
    @Tool.predicate('+n: value, +m: value')
    def verycomposite(self, n, m):
        n = abs(int(n.val))
        m = abs(int(m.val))
        termlist = [ "composite(%s)" % i  for i in range(n, n + m)]
        self.log.info("Lemmas: %s" % termlist)
        return Lemmata(self, [{}], [ termlist ])

    @Tool.predicate('+n: value, +m: value')
    def verycompositeT(self, n, m):
        n = abs(int(n.val))
        m = abs(int(m.val))
        lemmata = [ etb.terms.mk_apply("composite", [i])  for i in range(n, n + m)]
        self.log.info("Lemmata: %s" % lemmata)
        return Lemmata(self, [{}], [ lemmata ])


def isPrime(n):
    n = abs(int(n))
    if n < 2:
        return False
    if n == 2:
        return True
    if not n & 1:
        return False
    for x in range(3, int(n**0.5)+1, 2):
        if n % x == 0:
            return False
    return True
        
def register(etb):
    etb.add_tool(VeryComposite(etb))
