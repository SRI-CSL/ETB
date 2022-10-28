
from etb.parser import parse_literal
from etb.terms import mk_claim, mk_subst

from etb_manager import ETBNetwork
from etb_tests import ETBTest, etb_test


class RemoteTest(ETBTest):

    @etb_test
    def invalid(self):
        query = self.etb.etb().query('between(1,4,12)')
        self.etb.etb().query_wait(query)
        return (self.etb.query_answers(query), [])

    @etb_test
    def invalid_claims(self):
        query = self.etb.etb().query('between(1,4,12)')
        self.etb.etb().query_wait(query)
        return (self.etb.query_claims(query), [])
    
    @etb_test
    def valid(self):
        query = self.etb.etb().query('between(1,4,3)')
        self.etb.etb().query_wait(query)
        return (self.etb.query_answers(query), [mk_subst()])
    
    @etb_test
    def valid_claims(self):
        query = self.etb.etb().query('between(1,4,2)')
        self.etb.etb().query_wait(query)
        return (self.etb.all_claims(),
                [mk_claim(parse_literal('between(1,4,2)'),
                          'from rule between(1,4,2) :- yices({"file": "between.yices", "sha1": "99d4cf6b60c327ca84c809fce0c236c13fcc6845"},"sat") with facts: yices({"file": "between.yices", "sha1": "99d4cf6b60c327ca84c809fce0c236c13fcc6845"},"sat")'),
                 mk_claim(parse_literal('yices({"file": "between.yices", "sha1": "99d4cf6b60c327ca84c809fce0c236c13fcc6845"},"sat")'), 'yices({"file": "between.yices", "sha1": "99d4cf6b60c327ca84c809fce0c236c13fcc6845"},"sat")')])
    
def main():
    with ETBNetwork('single node ETB',
                    { 'port': 26532, 'wrappers': ['utils', 'yices_batch']}) as etb:
        RemoteTest(etb).run()

    with ETBNetwork('two nodes ETB',
                    { 'port': 26532, 'wrappers': ['yices_batch'] },
                    { 'port': 26533, 'wrappers': ['utils']}) as etb:
        RemoteTest(etb).run()

if __name__ == '__main__':
    main()
