
from etb_manager import ETBNetwork
from etb_tests import etb_test, ETBTest
from etb.terms import mk_subst, mk_numberconst, mk_literal, mk_idconst

import json

class UtilsTest(ETBTest):

    @etb_test
    def dummy(self):
        query = self.etb.etb().query('dummy(0)')
        self.etb.etb().query_wait(query)
        answers = self.etb.query_answers(query)
        return (answers, [mk_subst()])

    #@etb_test
    def bad_dummy(self):
        query = self.etb.etb().query('bad_dummy(4)')
        self.etb.etb().query_wait(query)
        return (self.etb.etb().query_answers(query),
                [])

    
def main():
    if False:
        with ETBNetwork('single node ETB',
                        { 'port': 26532, 'wrappers': ['utils']}) as etb:
            UtilsTest(etb).run()
            
    with ETBNetwork('two nodes ETB',
                    { 'port': 26532 },
                    { 'port': 26533, 'wrappers': ['utils']}) as etb:
        UtilsTest(etb).run()

if __name__ == '__main__':
    main()
