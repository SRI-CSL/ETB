import json
import os

from etb.terms import loads

from etb_manager import ETBNetwork
from etb_tests import ETBTest, etb_test


class HandleTest(ETBTest):

    @etb_test
    def simple_handle(self):
        f = self.etb.put_file(os.path.abspath('short.sal'), 'short.sal')
        q = self.etb.etb().query('salsim_start(%s, "main", S)' % f)
        self.etb.etb().query_wait(q)
        a = self.etb.etb().query_answers(q)
        print("a = %s" % a)
        if a  == "[]":
            #sal might not be installed
            return ['{}', loads('{}')]
        pa = [ loads(s) for s in loads(a) ][0]
        print("pa = %s" % pa)
        q = self.etb.etb().query('salsim_current_states(%s, States)' % pa.get('S'))
        self.etb.etb().query_wait(q)
        q = self.etb.etb().query('salsim_step(%s, S)' % pa.get('S'))
        self.etb.etb().query_wait(q)
        c = self.etb.etb().query_answers(q)
        pc = [ loads(s) for s in loads(c) ][0]
        return (json.dumps(loads(pc.get('S'))['session'] - loads(pa.get('S'))['session'] > 0),
                True)
    
def main():
    with ETBNetwork('single node ETB',
                    { 'port': 26532, 'wrappers': ['salsim']}) as etb:
        HandleTest(etb).run()

if __name__ == '__main__':
    main()
