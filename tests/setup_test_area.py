
from etb_manager import ETBNetwork
import os

def setup():
    etb = ETBNetwork('two nodes ETB',
                     { 'directory': 'test/main', 'port': 26532 },
                     { 'directory': 'test/utils', 'port': 26533, 'wrappers': ['utils', 'test_wrappers']})
    etb.setupOnly()
    etb.__enter__()

def setup2():
    etb = ETBNetwork('One node ETB',
                     { 'directory': 'test/test', 'port': 26532, 'wrappers': ['utils', 'yices_batch']})
    etb.setupOnly()
    etb.__enter__()

def setup_make():
    etb = ETBNetwork('ETB node for make demo',
                     { 'port': 26532,
                       'wrappers': [os.path.abspath('../demos/make/wrapper/gcc_wrapper')],
                       'rules': [os.path.abspath('../demos/make/make_rules')]})
    etb.setupOnly()
    etb.__enter__()

def setup_claims():
    etb = ETBNetwork('Single node ETB',
                     { 'directory': 'test/claims', 'port': 26532, 'wrappers': ['test_wrappers']})
    etb.setupOnly()
    etb.__enter__()

def setup_link_test():
    etb = ETBNetwork('Two ETB networks - one with three nodes, one with two nodes',
                     { 'directory': 'link_test/net1-1', 'port': 43765, 'wrappers': ['utils'] },
                     { 'directory': 'link_test/net1-2', 'port': 43766, 'wrappers': ['sal_batch'] },
                     { 'directory': 'link_test/net1-3', 'port': 43767, 'wrappers': ['salsim'] },
                     { 'directory': 'link_test/net2-1', 'port': 43768, 'wrappers': ['utils'] },
                     { 'directory': 'link_test/net2-2', 'port': 43769, 'wrappers': ['yices_batch'] })
    etb.setupOnly()
    etb.__enter__()    
    
if __name__ == '__main__':
    setup_link_test()
