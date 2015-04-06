from .. import graph
from .. import model
from .. import engine
import unittest
import os

class TestGraph(unittest.TestCase):
        
    def setUp(self):
        self.interpret_state = engine.InterpretStateLessThan()
        self.engine = engine.Engine(self.interpret_state)
        self.logical_state = model.LogicalState(self.engine)
        #self.logical_state = model.LogicalState()
        self.graph = graph.DependencyGraph(self.logical_state)

    def test_add_goal_get_annotation(self):
        self.graph.clear()
        goal = [1,2,3]
        self.graph.add_goal(goal)
        annotation = self.graph.get_annotation(model.freeze(goal))
        self.assertEqual(annotation.kind, graph.Annotation.GOAL)

    def test_add_pending_rule_get_annotation(self):
        self.graph.clear()
        rule = self.graph.add_pending_rule([[1,2,3], [3,4,5]])
        annotation = self.graph.get_annotation(rule)
        self.assertEqual(annotation.kind, graph.Annotation.PENDING_CLAUSE)

    def test_global_time(self):
        self.assertEqual(self.graph.state.get_global_time(), 0)
        self.graph.state.inc_global_time()
        self.graph.state.inc_global_time()
        self.assertEqual(self.graph.state.get_global_time(), 2)

    def test_get_annotations_of_children(self):
        node1 = [1,2,4]
        annotation1 = graph.Annotation(model.freeze(node1),graph.Annotation.GOAL, self.logical_state)

        pending1 = self.graph.add_pending_rule([[1,2,-1],[2,3,5]])
        pending2 = self.graph.add_pending_rule([[1,2,-1],[7,8]])
        self.graph.add_goal_to_pending_rule(node1, pending1)
        self.graph.add_goal_to_pending_rule(node1, pending2)

        children = self.graph.get_annotations_of_children(model.freeze(node1))
        self.assertTrue(len(children)==2)
        self.assertEqual(children[0].item.clause, pending1.clause)
        self.assertEqual(children[1].item.clause, pending2.clause)

    def test_has_subgoal(self):
        pending1 = self.graph.add_pending_rule([[1,2,-1],[2,3,5]])
        pending2 = self.graph.add_pending_rule([[1,2,-1],[7,8]])
        node1 = [2,3,5]
        self.graph.add_goal(node1)
        self.graph.add_pending_rule_to_goal(pending1, node1)
        self.assertTrue(self.graph.has_subgoal(pending1))
        self.assertFalse(self.graph.has_subgoal(pending2))

    def test_can_close_to_goal_be_applied1(self):
        node1 = [1,2,4]
        annotation1 = graph.Annotation(model.freeze(node1),graph.Annotation.GOAL, self.logical_state)
        self.assertFalse(self.graph.can_close_to_goal_be_applied(model.freeze(node1), annotation1))

    def test_can_close_to_goal_be_applied2(self):
        node1 = [1,2,4]
        annotation1 = graph.Annotation(model.freeze(node1),graph.Annotation.GOAL, self.logical_state)
        annotation1.status = graph.Annotation.RESOLVED

        pending = self.graph.add_pending_rule([[1,2,-1],[2,3,5]])
        self.graph.add_goal_to_pending_rule(node1, pending)

        # no subgoal present for that pending rule though so should not be
        # applicable for closing
        self.assertFalse(self.graph.can_close_to_goal_be_applied(model.freeze(node1), annotation1))

    def test_can_close_to_goal_be_applied3(self):
        node = [1,2,4]
        annotation_node = graph.Annotation(model.freeze(node),graph.Annotation.GOAL, self.logical_state)
        annotation_node.status = graph.Annotation.RESOLVED

        # ensure that gTh is not None
        h1 = [2,4,5]
        clause = [[4,5,6],[7,8,9]]
        self.graph.add_goal(h1)
        h_annotation = self.graph.get_annotation(model.freeze(h1))
        annotation_node.gT[model.freeze(h1)] = []
        annotation_node.gT[model.freeze(h1)].append(clause)

        # ensure index_h_smaller_than_code is false
        h_annotation.index = annotation_node.index + 1

        # ensure that h_closed is false
        h_annotation.status = graph.Annotation.OPEN

        self.assertFalse(self.graph.can_close_to_goal_be_applied(model.freeze(node), annotation_node))




        





if __name__ == '__main__':
    unittest.main()
