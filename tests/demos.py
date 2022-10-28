# Running the ETB demos as part of the test suite
# make, allsat2, allsatlive
# for yices rather than yices 2 use allsat rather than allsat2 below
import os, platform

from etb_manager import ETBNetwork
from etb_tests import etb_test, ETBTest

import etb.terms


class MakeTest(ETBTest):

    @etb_test
    def make(self):
        arch = '%s_%s' % (platform.system(), platform.machine())
        h1 = self.etb.put_file('../demos/make/component1.h', 'component1.h')
        src1 = self.etb.put_file('../demos/make/component1.c', 'component1.c')
        h2 = self.etb.put_file('../demos/make/component2.h', 'component2.h')
        src2 = self.etb.put_file('../demos/make/component2.c', 'component2.c')
        srcMain = self.etb.put_file('../demos/make/main.c', 'main.c')
        q = self.etb.etb().query('main(%s)' %
                                 ', '.join(['"%s"' % arch, src1, h1, src2, h2,
                                           srcMain, '"main_%s"' % arch, 'Exe']))
        self.etb.etb().query_wait(q)
        r = self.etb.etb().query_answers(q)
        print('\nr = {0}: {1}\n'.format(r, type(r)))
        r = etb.terms.loads(r)[0]['Exe']
        print('\nr = {0}: {1}\n'.format(r, type(r)))
        self.etb.get_file(r, "main_%s" % arch)
        return ('true', True)

class AllSATTest(ETBTest):

    @etb_test
    def allsat(self):
        f = self.etb.put_file('../demos/allsat2/a.ys', 'a.ys')
        q = self.etb.etb().query('allsat(%s, Answers)' % f)
        self.etb.etb().query_wait(q)
        result = self.etb.etb().query_answers(q)
        return (result,
                ["{\"__Subst\": [[{\"__Var\": \"Answers\"}, [\"(= c false)(= a false)(= b false)\", \"(= c true)(= a false)(= b false)\", \"(= c true)(= a false)(= b true)\", \"(= c true)(= a true)(= b true)\"]]]}"])


class AllSATLive(ETBTest):
    @etb_test
    def allsatlive(self):
        f = self.etb.put_file('../demos/allsat2/a.ys', 'a.ys')
        q = self.etb.etb().query('allsat(%s, Answers)' % f)
        self.etb.etb().query_wait(q)
        result = self.etb.etb().query_answers(q)
        print('result = {0}: {1}'.format(result, type(result)))
        return (result,
                ["{\"__Subst\": [[{\"__Var\": \"Answers\"}, [\"(and (= a false)(= c false)(= b false))\", \"(and (= a false)(= c true)(= b false))\", \"(and (= a false)(= c true)(= b true))\", \"(and (= a true)(= c true)(= b true))\"]]]}"])
    
    
def main():
    with ETBNetwork('ETB node for make demo',
                    { 'port': 26532,
                      'wrappers': [os.path.abspath('../demos/make/new_wrapper/gcc_wrapper')],
                      'rules': [os.path.abspath('../demos/make/make_rules')]}) as etb:
        try:
            MakeTest(etb).run()
        except Exception:
            etb.dump()
            raise


    with ETBNetwork('ETB node for allsat2 demo',
                    { 'port': 26532,
                      'wrappers': [os.path.abspath('../demos/allsat2/new_wrappers/yices_wrapper')],
                      'rules': [os.path.abspath('../demos/allsat2/allsat_rules')]}) as etb:
        AllSATTest(etb).run()
  
    with ETBNetwork('ETB node for allsatlive demo',
                    { 'port': 26532,
                      'wrappers': [os.path.abspath('../demos/allsatlive/new_wrappers/yices_api'),
                                   os.path.abspath('../demos/allsatlive/new_wrappers/list_wrapper')],
                      'rules': [os.path.abspath('../demos/allsatlive/allsat_rules')]}) as etb:
        AllSATLive(etb).run()
        
if __name__ == '__main__':
    main()
