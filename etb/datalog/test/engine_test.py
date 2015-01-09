# this is the etb parser
from ... import parser

# these are the etb terms
from ... import terms

# datalogv2 stuff
from .. import model
from .. import index
from .. import inference
from .. import engine
import unittest
import os

# for threading test
import threading
import time

import logging

class NullHandler(logging.Handler):
    def emit(self, record):
        pass

class TestEngine(unittest.TestCase):
        
    def setUp(self):
        # The etb argument does not do anything in these tests (we are testing
        # the datalog engine)
        h = NullHandler()
        logging.getLogger("etb").addHandler(h)

        self.interpret_state = engine.InterpretStateLessThan()
        self.engine = engine.Engine(self.interpret_state)

        X = terms.mk_var("X")
        Y = terms.mk_var("Y")
        Z = terms.mk_var("Z")

        self.eXY = parser.parse_literal('e(X, Y)')
        self.eab = parser.parse_literal('e(a, b)')
        self.iXb = parser.parse_literal('i(X, b)')
        self.iab = parser.parse_literal('i(a, b)')
        self.lt_2_4 = parser.parse_literal('lt(2, 4)')
        self.lt_4_2 = parser.parse_literal('lt(4, 2)')
        self.gt_4_2 = parser.parse_literal('gt(4, 2)')
        self.gt_5_2 = parser.parse_literal('gt(5, 2)')
        self.pXY = parser.parse_literal('p(X, Y)')
        self.pXb = parser.parse_literal('p(X, b)')
        self.paY = parser.parse_literal('p(a, Y)')
        self.pab = parser.parse_literal('p(a, b)')
        self.qXY = parser.parse_literal('q(X, Y)')
        self.qXb = parser.parse_literal('q(X, b)')
        self.qab = parser.parse_literal('q(a, b)')


        self.edgeXY = parser.parse_literal('edge(X, Y)')
        self.edgeZY = parser.parse_literal('edge(Z, Y)')
        self.edgeXb = parser.parse_literal('edge(X, b)')
        self.edgeXc = parser.parse_literal('edge(X, c)')
        self.edgeXZ = parser.parse_literal('edge(X, Z)')
        self.edgeab = parser.parse_literal('edge(a, b)')
        self.edgeac = parser.parse_literal('edge(a, c)')
        self.edgebc = parser.parse_literal('edge(b, c)')
        self.pathXY = parser.parse_literal('path(X, Y)')
        self.pathXa = parser.parse_literal('path(X, a)')
        self.pathaX = parser.parse_literal('path(a, X)')
        self.pathZY = parser.parse_literal('path(Z, Y)')
        self.pathXZ = parser.parse_literal('path(X, Z)')
        self.pathab = parser.parse_literal('path(a, b)')
        self.pathac = parser.parse_literal('path(a, c)')
        self.pathca = parser.parse_literal('path(c, a)')
        self.pathbc = parser.parse_literal('path(b, c)')

        self.graph_name = ""

    def test_add_and_get_claims(self):
        self.engine.clear()
        # note that the second argument of Claim is a reason (which could be a
        # Clause, here it is just some structured object)
        claim = terms.Claim(self.pab, model.create_external_explanation())
        returned_claim = terms.Claim(self.pab, self.engine.get_rule_and_facts_explanation(claim))
        self.engine.add_claim(claim)
        self.assertItemsEqual([returned_claim], self.engine.get_claims())

    def test_add_goal(self):
        self.engine.clear()
        self.engine.add_goal(self.gt_4_2)
        self.assertItemsEqual([self.gt_4_2], self.engine.get_stuck_goals())

        claim = terms.Claim(self.gt_4_2, model.create_external_explanation())
        self.engine.add_claim(claim)
        # self.engine.inference_state.interpret_state.add_results(goal, [claim])
        import time
        time.sleep(5)
        # claim solves previously added goal, which should now become unstuck
        self.assertItemsEqual([self.gt_4_2], self.engine.get_goals())
        self.assertItemsEqual([], self.engine.get_stuck_goals())

    def test_is_stuck_goal(self):
        self.engine.clear()
        self.engine.add_goal(self.gt_4_2)
        self.assertTrue(self.engine.is_stuck_goal(self.gt_4_2))
        # Something has to push it to check whether now solutions have arrived
        self.engine.push_no_solutions(self.gt_4_2)
        self.assertFalse(self.engine.is_stuck_goal(self.gt_4_2))


    def test_add_rule(self):
        self.engine.clear()
        self.engine.add_goal(self.qab)
        self.engine.add_rule(terms.Clause(self.qXb, [self.pXY, self.iXb]), None)

        claim1 = terms.Claim(self.pab, model.create_external_explanation())
        claim2 = terms.Claim(self.iab, model.create_external_explanation())
        self.engine.add_claim(claim1)
        self.engine.add_claim(claim2)
        self.assertItemsEqual([self.pab, self.iab, self.qab], map(lambda claim: claim.literal, self.engine.get_claims()))

    def test_add_pending_rule(self):
        self.engine.clear()
        self.engine.add_goal(self.qab)
        pending_rule = terms.Clause(self.qab, [self.paY, self.iab])
        self.engine.add_pending_rule(pending_rule, self.qab)
        claim1 = terms.Claim(self.pab, model.create_external_explanation())
        claim2 = terms.Claim(self.iab, model.create_external_explanation())
        self.engine.add_claim(claim1)
        self.engine.add_claim(claim2)
        self.assertItemsEqual([self.pab, self.iab, self.qab], map(lambda claim: claim.literal, self.engine.get_claims()))

    def test_add_pending_rule_that_is_a_claim(self):
        self.engine.clear()
        pending_rule = terms.Clause(self.qab, [])
        self.engine.add_pending_rule(pending_rule)
        self.assertItemsEqual([self.qab], map(lambda claim: claim.literal, self.engine.get_claims()))



    def test_interpret(self):
        self.engine.clear()
        self.engine.add_goal(self.lt_2_4)
        self.engine.add_goal(self.lt_4_2)
        self.assertItemsEqual([self.lt_2_4], map(lambda claim: claim.literal, self.engine.get_claims()))

    def test_simple_program(self):
        self.engine.clear()
        rule1 = terms.Clause(self.pXY, [self.eXY])
        rule2 = terms.Clause(self.eab, [])
        self.engine.add_rule(rule1, None)
        self.engine.add_rule(rule2, None)
        self.engine.add_goal(self.pXY)
        self.assertItemsEqual([self.pab, self.eab], map(lambda claim: claim.literal, self.engine.get_claims()))

    def test_path1(self):
        self.engine.clear()
        rule1 = terms.Clause(self.pathXY, [self.edgeXY])
        rule2 = terms.Clause(self.pathXY, [self.edgeXZ, self.pathZY])
        rule3 = terms.Clause(self.edgeab, [])
        rule4 = terms.Clause(self.edgebc, [])
        self.engine.add_rule(rule1, None)
        self.engine.add_rule(rule2, None)
        self.engine.add_rule(rule3, None)
        self.engine.add_rule(rule4, None)
        self.engine.add_goal(self.pathXY)
        self.assertItemsEqual([self.pathab, self.pathac, self.pathbc, self.edgeab, self.edgebc], map(lambda claim:claim.literal, self.engine.get_claims()))

    def test_is_renaming(self):
        self.engine.clear()
        rule = terms.Clause(self.pXY, [self.pXY])
        self.engine.add_rule(rule, None)
        self.engine.add_goal(self.pXY)
        # No asserts here; let's just ensure this does not loop

    def test_get_claims_matching_goal(self):
        self.engine.clear()
        self.engine.term_factory.clear()
        self.engine.load_rules('./etb/datalog/test/logic_programs/clique10.lp')
        goal = parser.parse_literal('same_clique(1, X)')
        cl1 = parser.parse_literal('same_clique(1, 0)')
        cl2 = parser.parse_literal('same_clique(1, 1)')
        cl3 = parser.parse_literal('same_clique(1, 2)')
        cl4 = parser.parse_literal('same_clique(1, 3)')
        cl5 = parser.parse_literal('same_clique(1, 4)')
        cl6 = parser.parse_literal('same_clique(1, 5)')
        self.engine.add_goal(goal)
        self.assertItemsEqual([cl1, cl2, cl3, cl4, cl5, cl6], map(lambda claim: claim.literal, self.engine.get_claims_matching_goal(goal)))

    def test_get_substitutions(self):
        self.engine.clear()
        self.engine.term_factory.clear()
        self.engine.load_rules('./etb/datalog/test/logic_programs/program2.lp')
        self.engine.add_goal(self.pathXY)
        # solutions are a,b; b,c; and a,c
        X = terms.mk_var("X")
        Y = terms.mk_var("Y")
        subst1 = parser.parse('subst(X = a, Y = b)', 'subst')
        subst2 = parser.parse('subst(X = b, Y = c)', 'subst')
        subst3 = parser.parse('subst(X = a, Y = c)', 'subst')
        self.assertItemsEqual([subst1, subst2, subst3], self.engine.get_substitutions(self.pathXY))

    def test_entailed_program2_groundliterals(self):
        self.engine.clear()
        self.engine.load_rules('./etb/datalog/test/logic_programs/program2.lp')
        self.engine.add_goal(self.pathXY)
        self.assertTrue(self.engine.is_entailed(self.edgeab))
        self.assertFalse(self.engine.is_entailed(self.edgeac))
        self.assertTrue(self.engine.is_entailed(self.pathac))
        self.assertFalse(self.engine.is_entailed(self.pathca))

    def test_entailed_program2_ungroundliterals(self):
        self.engine.clear()
        self.engine.load_rules('./etb/datalog/test/logic_programs/program2.lp')
        self.engine.add_goal(self.pathXY)
        self.assertTrue(self.engine.is_entailed(self.edgeXb))
        self.assertTrue(self.engine.is_entailed(self.edgeXc))
        self.assertFalse(self.engine.is_entailed(self.pathXa))
        self.assertTrue(self.engine.is_entailed(self.pathXY))

    def test_entailed_program3(self):
        self.engine.clear()
        X = terms.mk_var("X")
        Y = terms.mk_var("Y")
        self.engine.load_rules('./etb/datalog/test/logic_programs/program3.lp')
        q1 = parser.parse_literal('q1(X, Y)')
        q1_13 = parser.parse_literal('q1(1, 3)')
        q1_53 = parser.parse_literal('q1(5, 3)')
        q2 = parser.parse_literal('q2(X, Y)')
        q2_53 = parser.parse_literal('q2(5, 3)')
        q2_31 = parser.parse_literal('q2(3, 1)')
        self.engine.add_goal(q1)
        self.engine.add_goal(q2)
        self.assertTrue(self.engine.is_entailed(q1_13))
        self.assertTrue(self.engine.is_entailed(q2_53))
        self.assertFalse(self.engine.is_entailed(q1_53))
        self.assertFalse(self.engine.is_entailed(q2_31))


    def test_unification_of_goal_bug(self):
        self.engine.clear()
        self.engine.load_rules('./etb/datalog/test/logic_programs/program3.lp')
        X = terms.mk_var("X")
        pX2 = parser.parse_literal('p(X, 2)')
        self.engine.add_goal(pX2)
        self.assertTrue(self.engine.is_entailed(pX2))

    def test_query_ocaml1(self):
        self.engine.clear()
        X = terms.mk_var("X")
        self.engine.load_rules('./etb/datalog/test/logic_programs/graph10.lp')
        goal = parser.parse_literal('increasing(3, X)')
        inc1 = parser.parse_literal('increasing(3,4)')
        inc2 = parser.parse_literal('increasing(3,5)')
        inc3 = parser.parse_literal('increasing(3,6)')
        inc4 = parser.parse_literal('increasing(3,7)')
        inc5 = parser.parse_literal('increasing(3,8)')
        inc6 = parser.parse_literal('increasing(3,9)')
        inc7 = parser.parse_literal('increasing(3,10)')
        self.engine.add_goal(goal)
        desired_results = [inc1, inc2, inc3, inc4, inc5, inc6, inc7]
        self.assertItemsEqual(desired_results, map(lambda claim: claim.literal, self.engine.get_claims_matching_goal(goal)))

    def test_check_stuck_goals(self):
        self.engine.clear()
        self.engine.add_goal(self.gt_4_2)
        self.assertItemsEqual([self.gt_4_2], self.engine.get_stuck_goals())
        # manually add a rule (if we add it via engine.add_rule, the goal would become
        # automatically unstuck; to test this we want to avoid that)
        rule = terms.Clause(self.gt_4_2, [self.qXY])
        internal_rule = self.engine.term_factory.mk_clause(rule)
        self.engine.inference_state.logical_state.db_add_rule(internal_rule)
        # now check that this indeed still kept the goal stuck
        self.assertItemsEqual([self.gt_4_2], self.engine.get_stuck_goals())
        # force the engine to check its stuck goals
        self.engine.check_stuck_goals()
        # and check that goal is indeed no longer stuck (cause there is a rule
        # that matches)
        stuck_goals = self.engine.get_stuck_goals()
        self.assertItemsEqual([], self.engine.get_stuck_goals())

    def test_generate_png(self):
        self.engine.clear()
        goal = parser.parse_literal('q1(1,3)')
        self.engine.load_rules('./etb/datalog/test/logic_programs/program3.lp')
        self.engine.add_goal(goal)
        answer = self.engine.is_entailed(goal)
        claim = terms.Claim(goal,None)
        if answer:
            filenames = self.engine.to_png(claim)
            if filenames:
                os.remove(filenames[0])

    def test_list(self):
        self.engine.clear()
        goal = parser.parse_literal('p(1,2)')
        self.engine.load_rules('./etb/datalog/test/logic_programs/program5.lp')
        self.engine.add_goal(goal)
        claim = terms.Claim(goal,None)
        answer = self.engine.is_entailed(goal)
        self.assertTrue(answer)

    def test_goal_dependencies_png(self):
        self.engine.clear()
        goal = parser.parse_literal('q1(1,3)')
        self.engine.load_rules('./etb/datalog/test/logic_programs/program3.lp')
        self.engine.add_goal(goal)
        answer = self.engine.is_entailed(goal)
        claim = terms.Claim(goal,None)
        if answer:
            file = self.engine.goal_deps_to_png(goal)
            if file:
                os.remove(file)

    # Claims no longer trigger - should be a goal
    # def test_no_stuck_subgoals(self):
    #     self.engine.clear()
    #     self.engine.add_goal(self.gt_4_2)
    #     self.assertFalse(self.engine.no_stuck_subgoals(self.gt_4_2))
    #     claim = terms.Claim(self.gt_4_2, model.create_external_explanation())
    #     self.engine.add_claim(claim)
    #     self.assertTrue(self.engine.no_stuck_subgoals(self.gt_4_2))

    def test_push_no_solutions(self):
        self.engine.clear()
        self.engine.add_goal(self.gt_4_2)
        self.assertTrue(self.engine.is_stuck_goal(self.gt_4_2))
        self.engine.push_no_solutions(self.gt_4_2)
        self.assertFalse(self.engine.is_stuck_goal(self.gt_4_2))


    def test_subgoal_index(self):
        self.engine.clear()
        rule1 = terms.Clause(self.pathXY, [self.edgeXY])
        rule2 = terms.Clause(self.pathXY, [self.pathXZ, self.edgeZY])
        rule3 = terms.Clause(self.edgeab, [])
        rule4 = terms.Clause(self.edgebc, [])
        self.engine.add_rule(rule1, None)
        self.engine.add_rule(rule2, None)
        self.engine.add_rule(rule3, None)
        self.engine.add_rule(rule4, None)
        self.engine.add_goal(self.pathaX)

        children_goal = self.engine.inference_state.logical_state.goal_dependencies.get_children(model.freeze(self.engine.term_factory.open_literal(self.pathaX)))
        nd_child = children_goal[1]
        annotation = self.engine.inference_state.logical_state.goal_dependencies.get_annotation(nd_child)
        self.assertEqual(annotation.subgoalindex, 2)


    def test_index(self):
        self.engine.clear()
        rule1 = terms.Clause(self.pathXY, [self.edgeXY])
        rule2 = terms.Clause(self.pathXY, [self.pathXZ, self.edgeZY])
        rule3 = terms.Clause(self.edgeab, [])
        rule4 = terms.Clause(self.edgebc, [])
        self.engine.add_rule(rule1, None)
        self.engine.add_rule(rule2, None)
        self.engine.add_rule(rule3, None)
        self.engine.add_rule(rule4, None)
        self.engine.add_goal(self.pathaX)

        annotation_goal = self.engine.inference_state.logical_state.db_get_annotation(self.engine.term_factory.open_literal(self.pathaX))
        children_goal = self.engine.inference_state.logical_state.goal_dependencies.get_children(model.freeze(self.engine.term_factory.open_literal(self.pathaX)))
        second_child = children_goal[1]
        second_child_annotation = self.engine.inference_state.logical_state.goal_dependencies.get_annotation(second_child)
        children_second_child = self.engine.inference_state.logical_state.goal_dependencies.get_children(second_child)
        last_child = children_second_child[2]
        last_child_annotation = self.engine.inference_state.logical_state.goal_dependencies.get_annotation(last_child)
        children_last_child = self.engine.inference_state.logical_state.goal_dependencies.get_children(last_child)
        final_node = children_last_child[0]
        final_node_annotation = self.engine.inference_state.logical_state.goal_dependencies.get_annotation(final_node)
        
        self.assertEqual(annotation_goal.index, 1)
        self.assertEqual(second_child_annotation.index, 4)
        self.assertEqual(last_child_annotation.index, 8)
        self.assertEqual(final_node_annotation.index, 9)

    def test_engine_close(self):
        self.engine.clear()
        rule1 = terms.Clause(self.pathXY, [self.edgeXY])
        rule2 = terms.Clause(self.pathXY, [self.pathXZ, self.edgeZY])
        rule3 = terms.Clause(self.edgeab, [])
        rule4 = terms.Clause(self.edgebc, [])
        self.engine.add_rule(rule1, None)
        self.engine.add_rule(rule2, None)
        self.engine.add_rule(rule3, None)
        self.engine.add_rule(rule4, None)
        self.engine.add_goal(self.pathaX)

        self.engine.close()

    def test_engine_complete(self):
        self.engine.clear()

        rule1 = terms.Clause(self.pathXY, [self.edgeXY])
        rule2 = terms.Clause(self.pathXY, [self.pathXZ, self.edgeZY])
        rule3 = terms.Clause(self.edgeab, [])
        rule4 = terms.Clause(self.edgebc, [])
        self.engine.add_rule(rule1, None)
        self.engine.add_rule(rule2, None)
        self.engine.add_rule(rule3, None)
        self.engine.add_rule(rule4, None)
        self.engine.add_goal(self.pathaX)

        self.engine.close()
        self.engine.complete()


    def test_engine_is_completed(self):
        self.engine.clear()

        rule1 = terms.Clause(self.pathXY, [self.edgeXY])
        rule2 = terms.Clause(self.pathXY, [self.pathXZ, self.edgeZY])
        rule3 = terms.Clause(self.edgeab, [])
        rule4 = terms.Clause(self.edgebc, [])
        self.engine.add_rule(rule1, None)
        self.engine.add_rule(rule2, None)
        self.engine.add_rule(rule3, None)
        self.engine.add_rule(rule4, None)
        self.engine.add_goal(self.pathaX)

        self.engine.close()
        self.engine.complete()
        self.assertTrue(self.engine.is_completed(self.pathaX))


    def test_path_close(self):
        self.engine.clear()

        rule1 = terms.Clause(self.pathXY, [self.edgeXY])
        rule2 = terms.Clause(self.pathXY, [self.pathXZ, self.edgeZY])
        rule3 = terms.Clause(self.edgeab, [])
        rule4 = terms.Clause(self.edgebc, [])
        self.engine.add_rule(rule1, None)
        self.engine.add_rule(rule2, None)
        self.engine.add_rule(rule3, None)
        self.engine.add_rule(rule4, None)

        goal_thread = threading.Thread(target = self.engine.add_goal, args=(self.pathaX,))
        goal_thread.start()

        while not self.engine.is_completed(self.pathaX):
            #filename = self.engine.goal_deps_to_png(self.pathaX)
            #os.rename(filename, "path_step" + str(number) + ".png")
            self.engine.close()
            self.engine.complete()

        goal_thread.join()

    def test_reset(self):
        self.engine.clear()
        p1 = parser.parse_literal('p(1)')
        p2 = parser.parse_literal('p(2)')
        claim1 = terms.Claim(p1, model.create_external_explanation())
        claim2 = terms.Claim(p2, model.create_external_explanation())

        goal1 = parser.parse_literal('p(1)')
        X = terms.mk_var("X")
        goal2 = parser.parse_literal('p(X)')

        self.engine.add_claim(claim1)
        self.engine.add_claim(claim2)

        self.engine.add_goal(goal1)
        self.assertItemsEqual([p1], map(lambda claim: claim.literal, self.engine.get_claims_matching_goal(goal1)))


        self.engine.reset()
        self.engine.add_claim(claim1)
        self.engine.add_claim(claim2)
        self.engine.add_goal(goal2)
        self.assertItemsEqual([p1, p2], map(lambda claim: claim.literal, self.engine.get_claims_matching_goal(goal2)))
 
    def test_offset(self):
        # rules containing only constants do not seem to work properly (because
        # of offset: offset should be 0 when only constants
        self.engine.clear()
        X = terms.mk_var("X")
        self.engine.load_rules('./etb/datalog/test/logic_programs/offset1.lp')
        goal = parser.parse_literal('p(X)')
        res1 = parser.parse_literal('p(1)')
        res2 = parser.parse_literal('p(2)')
        self.engine.add_goal(goal)
        desired_results = [res1, res2]
        self.assertItemsEqual(desired_results, map(lambda claim: claim.literal, self.engine.get_claims_matching_goal(goal)))


    def test_add_pending_rule_with_completion_interference(self):
        self.engine.clear()
        pong1 = parser.parse_literal('pong(1)')
        ping0 = parser.parse_literal('ping(0)')

        rule = terms.Clause(pong1, [ping0])
        self.engine.add_goal(pong1)
        self.engine.add_claim(terms.Claim(ping0, model.create_external_explanation()))


        # We'll add the pending rule pong(1) :- ping(0) but slow it down; if
        # locking is not properly done in Engine.add_pending_rule (remove the
        # current locks for example); the below close/completion code will
        # interfere.
        goal_thread = threading.Thread(target = self.engine.add_pending_rule, args=(rule,pong1))
        # self.engine.go_slow(1)
        goal_thread.start()

        self.engine.close()
        self.engine.complete()
        result = self.engine.is_completed(pong1)

        self.assertTrue(result)

        # self.engine.go_normal()

    def test_add_pending_rule_with_completion_interference3(self):
        # As test_add_pending_rule_with_completion_interference, but without
        # adding claims and using a standard external predicate (that does not
        # return anything in our tests)
        self.engine.clear()
        pong1 = parser.parse_literal('pong(1)')
        gt = parser.parse_literal('gt(0, 2)')

        rule = terms.Clause(pong1, [gt])
        self.engine.add_goal(pong1)

        goal_thread = threading.Thread(target = self.engine.add_pending_rule, args=(rule,pong1))
        self.engine.go_slow(0.2)
        goal_thread.start()

       
        # sleep a bit to ensure that we at least have properly started the
        # add_pending_rule (otherwise is_stuck_goal would be false; which is
        # fine but not the purpose of this test)
        time.sleep(0.1)
        self.engine.close()
        self.engine.complete()
        result = self.engine.is_stuck_goal(gt)
        self.assertTrue(result)
        result = self.engine.is_completed(pong1)
        self.assertFalse(result)

        # Do the same but after joining the thread (this should be the easy
        # part)
        goal_thread.join()
        result = self.engine.is_stuck_goal(gt)
        self.assertTrue(result)
        self.engine.close()
        self.engine.complete()
        result = self.engine.is_completed(pong1)
        # not completed as still stuck goal
        self.assertFalse(result)



        self.engine.go_normal()




    def tearDown(self):
        # removing file introduced in test_generate_png
        if os.path.exists(self.graph_name):
            os.remove(self.graph_name)

    

if __name__ == '__main__':
    unittest.main()
