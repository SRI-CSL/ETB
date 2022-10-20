
import os

from etb.terms import mk_map, mk_stringconst, mk_subst

from etb_manager import ETBNetwork
from etb_tests import ETBTest, etb_test


class FileTest(ETBTest):

    @etb_test
    def find_thms(self):
        file = self.etb.put_file(os.path.abspath('short.sal'), 'short.sal')
        q = 'find_theorems(%s, ThmFile)' % file
        query = self.etb.etb().query(q)
        self.etb.etb().query_wait(query)
        return(self.etb.query_answers(query),
               [mk_subst(ThmFile = mk_map({"file": mk_stringconst("theorems"), "sha1": mk_stringconst("263cfc9907a248d65f98e9b0e3020e2045d4eccb")}))])

def main():
    with ETBNetwork('single node ETB',
                    { 'port': 26532, 'wrappers': ['test_wrappers']}) as etb:
        FileTest(etb).run()

    with ETBNetwork('two nodes ETB',
                    { 'port': 26532 },
                    { 'port': 26533, 'wrappers': ['test_wrappers']}) as etb:
        FileTest(etb).run()

if __name__ == '__main__':
    main()
