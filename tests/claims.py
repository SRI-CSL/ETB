
from etb.terms import mk_claim, mk_idconst, mk_literal, mk_stringconst

from etb_manager import ETBNetwork
from etb_tests import ETBTest, etb_test


class ClaimTest(ETBTest):

    @etb_test
    def tool_error(self):
        q = self.etb.etb().query('bad_predicate(2,3)')
        print('tool_error: q = {0}'.format(q))
        self.etb.etb().query_wait(q)
        return(self.etb.all_claims(),
               [mk_claim(mk_literal(mk_idconst('error'),
                                    [mk_stringconst("Tests"),
                                     mk_stringconst("in tool wrapper Tests: failed to start the external tool non_existing_command")]),
                         "bad_predicate(2,3)")])
    
def main():
    with ETBNetwork('single node ETB',
                    { 'port': 26532, 'wrappers': ['test_wrappers']}) as etb:
        ClaimTest(etb).run()

    with ETBNetwork('two nodes ETB',
                    { 'port': 26532 },
                    { 'port': 26533, 'wrappers': ['test_wrappers']}) as etb:
        ClaimTest(etb).run()

if __name__ == '__main__':
    main()
