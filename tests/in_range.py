
from etb_manager import ETBNetwork
from etb_tests import etb_test, ETBTest
from etb.terms import mk_subst, mk_numberconst, mk_literal, mk_idconst

import json

class InRangeTest(ETBTest):

    @etb_test
    def multiple_substs(self):
        query = self.etb.etb().query('in_range(1,4,X)')
        self.etb.etb().query_wait(query)
        return (self.etb.query_answers(query),
                [mk_subst(X = mk_numberconst(1)),
                 mk_subst(X = mk_numberconst(2)),
                 mk_subst(X = mk_numberconst(3)),
                 mk_subst(X = mk_numberconst(4))])

    @etb_test
    def multiple_claims(self):
        query = self.etb.etb().query('in_range(1,4,X)')
        self.etb.etb().query_wait(query)
        return (self.etb.query_claims(query),
                [mk_literal(mk_idconst('in_range'),
                            [mk_numberconst(1),mk_numberconst(4),mk_numberconst(1)]),
                 mk_literal(mk_idconst('in_range'),
                            [mk_numberconst(1),mk_numberconst(4),mk_numberconst(2)]),
                 mk_literal(mk_idconst('in_range'),
                            [mk_numberconst(1),mk_numberconst(4),mk_numberconst(3)]),
                 mk_literal(mk_idconst('in_range'),
                            [mk_numberconst(1),mk_numberconst(4),mk_numberconst(4)])])
    
    @etb_test
    def valid_claim(self):
        q = self.etb.etb().query('in_range(1,4,2)')
        self.etb.etb().query_wait(q)
        return (self.etb.query_answers(q), [mk_subst()])
    
    @etb_test
    def invalid_claim(self):
        query = self.etb.etb().query('in_range(1,4,12)')
        self.etb.etb().query_wait(query)
        return (self.etb.query_answers(query), [])

    @etb_test
    def multiple_substs_async(self):
        query = self.etb.etb().query('in_range_async(1,4,X)')
        self.etb.etb().query_wait(query)
        return (self.etb.query_answers(query),
                [mk_subst(X = mk_numberconst(1)),
                 mk_subst(X = mk_numberconst(2)),
                 mk_subst(X = mk_numberconst(3)),
                 mk_subst(X = mk_numberconst(4))])

    @etb_test
    def multiple_claims_async(self):
        query = self.etb.etb().query('in_range_async(1,4,X)')
        self.etb.etb().query_wait(query)
        return (self.etb.query_claims(query),
                [mk_literal(mk_idconst('in_range_async'),
                            [mk_numberconst(1),mk_numberconst(4),mk_numberconst(1)]),
                 mk_literal(mk_idconst('in_range_async'),
                            [mk_numberconst(1),mk_numberconst(4),mk_numberconst(2)]),
                 mk_literal(mk_idconst('in_range_async'),
                            [mk_numberconst(1),mk_numberconst(4),mk_numberconst(3)]),
                 mk_literal(mk_idconst('in_range_async'),
                            [mk_numberconst(1),mk_numberconst(4),mk_numberconst(4)])])
    
    @etb_test
    def valid_claim_async(self):
        query = self.etb.etb().query('in_range_async(1,4,2)')
        self.etb.etb().query_wait(query)
        return (self.etb.query_claims(query),
                [mk_literal(mk_idconst('in_range_async'),
                            [mk_numberconst(1),mk_numberconst(4),mk_numberconst(2)])])
    
    @etb_test
    def invalid_claim_async(self):
        query = self.etb.etb().query('in_range_async(1,4,12)')
        self.etb.etb().query_wait(query)
        return (self.etb.query_answers(query), [])
    
def main():
    
    with ETBNetwork('single node ETB',
                    { 'port': 26532, 'wrappers': ['utils', 'test_wrappers']}) as etb:
        InRangeTest(etb).run()

    with ETBNetwork('two nodes ETB',
                    { 'port': 26532 },
                    { 'port': 26533, 'wrappers': ['utils', 'test_wrappers']}) as etb:
        InRangeTest(etb).run()

if __name__ == '__main__':
    main()
