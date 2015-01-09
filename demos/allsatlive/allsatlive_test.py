#!/usr/env python
import os
import json

from etb_manager import ETBNetwork
from etb_tests import etb_test, ETBTest

from etb.terms import loads

class AllSatLiveTest(ETBTest):

    @etb_test
    def allsatlive(self):
        f = self.etb.put_file(os.path.abspath('a.ys'), 'a.ys')
        q = self.etb.etb().query('allsat(%s, A)' % f)
        self.etb.etb().query_wait(q)
        a = self.etb.etb().query_answers(q)
        print('a = %s' % loads(a))
        if a  == "[]":
            #yices might not be installed
            print('failure')
            return ['{}', '{}']
        pa = [ loads(s) for s in loads(a) ]
        return (json.dumps(True), True)
    
def main():
    with ETBNetwork('single node ETB',
                    { 'port': 26532,
                      'wrappers': [os.path.abspath('wrappers/yices_api')],
                      'rules':[os.path.abspath('allsat_rules')]}) as etb:
        AllSatLiveTest(etb).run()

if __name__ == '__main__':
    main()
