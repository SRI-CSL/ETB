
from etb_manager import ETBNetwork
from etb_tests import etb_test, ETBTest

class BuiltinsTest(ETBTest):

    @etb_test
    def different_yes(self):
        query = self.etb.etb().query('different(a, b)')
        self.etb.etb().query_wait(query)
        return(self.etb.etb().query_answers(query),
               ['{"__Subst": []}'])

    @etb_test
    def different_no(self):
        query = self.etb.etb().query('different(a, a)')
        self.etb.etb().query_wait(query)
        return(self.etb.etb().query_answers(query),
               [])

    @etb_test
    def plus_test(self):
        query = self.etb.etb().query('plus(1, 1, X)')
        self.etb.etb().query_wait(query)
        return(self.etb.etb().query_answers(query),
               [ '{"__Subst": [[{"__Var": "X"}, 2]]}' ])


def main():
    with ETBNetwork('single node ETB',
                    { 'port': 26532, 'wrappers': ['builtins']}) as etb:
        BuiltinsTest(etb).run()

    with ETBNetwork('two nodes ETB',
                    { 'port': 26532 },
                    { 'port': 26533, 'wrappers': ['builtins']}) as etb:
        BuiltinsTest(etb).run()

if __name__ == '__main__':
    main()
