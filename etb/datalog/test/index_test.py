from .. import index
from .. import model
import unittest

class TestIndex(unittest.TestCase):
        
    def test_add_to_index(self):
        
        #becomes [2,-1,3,4,-1]
        literal1 = [2,-2,3,4,-2]
        #becomes [2,-1,3,4,-1] (the same as literal1) 
        literal2 = [2,-3,3,4,-2]
        literal3 = [2,4,3,4,-2]
        i = {}
        index.add_to_index(i, literal1, "a")
        self.assertEqual({2: {-1: {3: {4: {-1: ['a']}}}}}, i)
        index.add_to_index(i, literal2, "b")
        self.assertEqual({2: {-1: {3: {4: {-1: ['a', 'b']}}}}}, i)
        index.add_to_index(i, literal3, "b")
        self.assertEqual({2: {4: {3: {4: {-1: ['b']}}}, -1: {3: {4: {-1: ['a', 'b']}}}}}, i)

    def test_remove_from_index(self):
        literal1 = [2,-2,3,4,-2]
        literal2 = [2,-3,3,4,-2]
        literal3 = [2,4,3,4,-2]
        i = {}
        index.add_to_index(i, literal1, "a")
        index.add_to_index(i, literal2, "b")
        index.add_to_index(i, literal3, "b")
        self.assertEqual({2: {4: {3: {4: {-1: ['b']}}}, -1: {3: {4: {-1: ['a', 'b']}}}}}, i)
        index.remove_from_index(i, [2, -1, 3, 4, -1], 'b')
        self.assertEqual({2: {4: {3: {4: {-1: ['b']}}}, -1: {3: {4: {-1: ['a']}}}}}, i)

    def test_in_index(self):
        literal1 = [2,-2,3,4,-2]
        literal2 = [2,-3,3,4,-2]
        literal3 = [2,4,3,4,-2]
        i = {}
        index.add_to_index(i, literal1, "a")
        index.add_to_index(i, literal2, "b")
        index.add_to_index(i, literal3, "b")
        self.assertEqual({2: {4: {3: {4: {-1: ['b']}}}, -1: {3: {4: {-1: ['a', 'b']}}}}}, i)
        self.assertTrue(index.in_index(i, literal2, "b"))
        self.assertFalse(index.in_index(i, literal3, "a"))
        self.assertEqual({2: {4: {3: {4: {-1: ['b']}}}, -1: {3: {4: {-1: ['a', 'b']}}}}}, i)


    def test_traverse_index(self):
        #becomes [2,-1,3,4,-1]
        literal1 = [2,-2,3,4,-2]
        #becomes [2,-1,3,4,-1] (the same as literal1) 
        literal2 = [2,-3,3,4,-2]
        literal3 = [2,4,3,4,-2]
        i = {}
        index.add_to_index(i, literal1, "a")
        index.add_to_index(i, literal2, "b")
        index.add_to_index(i, literal3, "c")
        self.assertItemsEqual(["a", "b", "c"], index.traverse(i))


    def test_get_candidate_generalizations(self):
        i = {}
        index.add_to_index(i, [1,-2,-3],"b")
        index.add_to_index(i, [1,-2,3],"a")
        self.assertEqual(['b', 'a'], index.get_candidate_generalizations(i, [1,4,3]))
        self.assertEqual(['b'], index.get_candidate_generalizations(i, [1,-2,-5]))
        self.assertEqual(['b', 'a'], index.get_candidate_generalizations(i, [1,-2,3]))
        self.assertEqual([], index.get_candidate_generalizations(i, [3,-2,3]))

    def test_get_candidate_specializations(self):
        i = {}
        index.add_to_index(i, [1,4,2],"1")
        index.add_to_index(i, [1,3,2],"2")
        index.add_to_index(i, [1,-1,2],"3")
        index.add_to_index(i, [1,4,3],"4")
        self.assertEqual(['2', '1'], index.get_candidate_specializations(i, [1,-1,2]))
        self.assertEqual(['4'], index.get_candidate_specializations(i, [1,-1,3]))
        self.assertEqual([], index.get_candidate_specializations(i, [1,-1,5]))

    def test_get_candidate_matchings(self):
        i = {}
        index.add_to_index(i, [1,-2,2],"1")
        index.add_to_index(i, [1,3,4],"2")
        index.add_to_index(i, [1,3,-2],"3")
        self.assertItemsEqual(['1', '3'], index.get_candidate_matchings(i, [1,-1,2]))

    def test_get_candidate_renamings(self):
        i = {}
        index.add_to_index(i, [1,-3,3,-4],"1")
        index.add_to_index(i, [1,-3,2,-2],"2")
        index.add_to_index(i, [1,2,-1,-1],"3")
        self.assertItemsEqual(['2'], index.get_candidate_renamings(i, [1,-1,2,-2]))



if __name__ == '__main__':
    unittest.main()
