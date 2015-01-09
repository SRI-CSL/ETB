from .. import externals
import unittest

class TestExternals(unittest.TestCase):
        
    def test_less_than(self):
        self.assertTrue(externals.less_than("3","10"))
        self.assertFalse(externals.less_than("10","3"))
    
if __name__ == '__main__':
    unittest.main()
