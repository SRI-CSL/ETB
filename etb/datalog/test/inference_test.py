import unittest

from etb import parser, terms
from etb.datalog import engine, inference, model


class TestInference(unittest.TestCase):
        
    def setUp(self):
        self.tf = model.TermFactory()
        self.interpret_state = engine.InterpretStateLessThan()
        self.engine = engine.Engine(self.interpret_state)
        self.logical_state = model.LogicalState(self.engine)
        # self.logical_state = model.LogicalState()
        # ETB does not do anything here (the InterpretState expects it though)
        #self.interpret_state = engine.InterpretStateLessThan()
        #self.engine = engine.Engine(self.interpret_state)
        self.inference = inference.Inference(self.logical_state, self.interpret_state, self.tf, self.engine)

        pab = parser.parse_literal('p(a, b)')
        qab = parser.parse_literal('q(a, b)')
        qXb = parser.parse_literal('q(X, b)')
        pXY = parser.parse_literal('p(X, Y)')
        paY = parser.parse_literal('p(a, Y)')
        iXb = parser.parse_literal('i(X, b)')
        iab = parser.parse_literal('i(a, b)')

        candidate_pending = terms.Clause(qab, [pXY, iXb])
        resolved_clause = terms.Clause(qab, [iab])
        fact = terms.Clause(pab, [])
        rule1 = terms.Clause(qXb, [pXY, iXb])
        rule2 = terms.Clause(qab, [paY, iab])

        self.i_claim = model.freeze(self.tf.mk_literal(pab))
        self.i_goal = self.tf.mk_literal(pXY)
        self.i_goal2 = self.tf.mk_literal(qab)
        self.i_goal3 = self.tf.mk_literal(paY)
        self.i_goal4 = self.tf.mk_literal(pab)
        self.i_candidate_pending = self.tf.mk_clause(candidate_pending)
        self.i_resolved_clause = self.tf.mk_clause(resolved_clause)
        self.i_fact = self.logical_state.db_add_pending_rule(self.tf.mk_clause(fact))
        self.inference.update_goal(self.i_fact, self.i_goal4)
        self.i_rule1 = self.logical_state.db_add_pending_rule(self.tf.mk_clause(rule1))
        self.inference.update_goal(self.i_rule1, self.i_goal2)
        self.i_rule2 = self.logical_state.db_add_pending_rule(self.tf.mk_clause(rule2))
        self.inference.update_goal(self.i_rule2, self.i_goal2)

    # def test_resolve_claim(self):
    #     self.logical_state.db_add_pending_rule(self.i_candidate_pending)
    #     self.inference.lock()
    #     self.inference.resolve_claim(self.i_claim)
    #     self.inference.unlock()
    #     self.assertItemsEqual([self.i_candidate_pending, self.i_resolved_clause], self.logical_state.db_get_pending_rules())

    # Claims should not be added directly, only goals
    # def test_add_claim(self):
    #     self.logical_state.clear()
    #     self.logical_state.db_add_pending_rule(self.i_candidate_pending)
    #     self.inference.lock()
    #     self.inference.add_claim(self.i_claim,model.create_external_explanation())
    #     self.inference.unlock()
    #     # resolution was triggered
    #     print 'self.i_candidate_pending {0}'.format(self.i_candidate_pending)
    #     print 'self.i_resolved_clause {0}'.format(self.i_resolved_clause)
    #     print 'self.logical_state.db_get_pending_rules()'.format(self.logical_state.db_get_pending_rules())
    #     self.assertItemsEqual([self.i_candidate_pending, self.i_resolved_clause],
    #                           self.logical_state.db_get_pending_rules())
    #     # was it added to the claims
    #     self.assertItemsEqual([self.i_claim], self.inference.get_claims())

    def test_add_claim2(self):
        # only added once
        self.logical_state.clear()
        self.inference.lock()
        self.inference.add_claim(self.i_fact, None)
        self.inference.add_claim(self.i_fact, None)
        self.inference.unlock()
        claims = list({iclaim.clause[0] for iclaim in self.inference.get_claims()})
        self.assertCountEqual([self.i_claim], claims)

    def test_add_pending_rule(self):
        self.logical_state.clear()
        self.inference.lock()
        self.inference.add_pending_rule(self.i_candidate_pending, None, self.i_goal)
        self.inference.unlock()
        self.assertCountEqual([self.i_goal], self.logical_state.db_get_all_goals())

    def test_resolve_goal(self):
        self.logical_state.clear()
        goal = self.i_goal2
        kb_rule = self.i_rule1
        new_pending_rule = self.i_rule2
        self.logical_state.db_add_rule(kb_rule)
        self.inference.lock()
        result = self.inference.resolve_goal(goal)
        self.inference.unlock()

        self.assertTrue(result)
        self.assertCountEqual([new_pending_rule.clause], [model.freeze_clause(c) for c in self.logical_state.db_get_pending_rules()])

    def test_is_stuck_goal(self):
        self.inference.clear()
        lt = parser.parse_literal('lt(1, 3)')
        goal = self.tf.mk_literal(lt)
        self.inference.lock()
        self.inference.add_goal(goal)
        self.assertTrue(self.inference.is_stuck_goal(goal))
        # Something has to push it to check whether now solutions have arrived
        clause = terms.Clause(lt, [])
        rule = self.tf.mk_clause(clause)
        explanation = model.create_external_explanation()
        prule = self.inference.logical_state.db_add_pending_rule(rule)
        #self.inference.add_claim(prule, model.create_external_explanation())
        self.inference.check_stuck_goals(['lt'])
        self.inference.unlock()
        self.assertFalse(self.inference.is_stuck_goal(goal))

    def test_add_goal(self):
        self.logical_state.clear()
        goal = self.i_goal2
        kb_rule = self.i_rule1
        new_pending_rule = self.i_rule2
        self.logical_state.db_add_rule(kb_rule)
        self.inference.lock()
        self.inference.add_goal(goal)
        self.inference.unlock()

        self.assertCountEqual([new_pending_rule.clause],
                              [model.freeze_clause(c) for c in self.logical_state.db_get_pending_rules()])
        self.assertCountEqual([model.freeze(goal), new_pending_rule.clause[1]],
                              [model.freeze(g) for g in self.logical_state.db_get_all_goals()])


    def test_add_rule(self):
        self.logical_state.clear()
        goal = self.i_goal2
        kb_rule = self.i_rule1
        resolved_rule = self.i_rule2
        self.inference.lock()
        self.inference.add_goal(goal)
        # now add the kb rule
        self.inference.add_rule(kb_rule, None)
        self.inference.unlock()
        # resolved kb rule should be pending
        self.assertCountEqual([resolved_rule.clause], list(map(model.freeze_clause, self.logical_state.db_get_pending_rules())))
        # and the goal should done
        self.assertCountEqual([goal, list(resolved_rule.clause[1])], self.logical_state.db_get_all_goals())

#    def test_entailment_with_proof1(self):
#        """
#        Bug executing 'python control.py --entailed "p(X,2)" --with_proof
#        test/program4.lp'.
#        """
#        self.inference.clear()
#        self.inference.entailed_with_proof("p(X,2)", "./program4.lp")
#        os.remove("./p(1, 2)_graph.png")


if __name__ == '__main__':
    unittest.main()
