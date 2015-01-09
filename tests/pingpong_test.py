
from etb_manager import ETBNetwork
from etb_tests import etb_test, ETBTest

import etb.terms

import json

class PingPongTest(ETBTest):

    @etb_test
    def pingpong(self):
        query = self.etb.etb().query('ping(10)')
        self.etb.etb().query_wait(query)
        return (self.etb.query_answers(query),
                [etb.terms.mk_subst()])

def main():

    with ETBNetwork('two nodes ETB',
                    { 'port': 26532, 'wrappers': ['ping_wrapper'] },
                    { 'port': 26533, 'wrappers': ['pong_wrapper'] }) as etb:
        PingPongTest(etb).run()

if __name__ == '__main__':
    main()
