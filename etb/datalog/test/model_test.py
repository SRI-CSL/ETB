import unittest

from etb import parser, terms
from etb.datalog import engine, graph, index, model


class TestModel(unittest.TestCase):
        
    def setUp(self):
        self.tf = model.TermFactory()
        self.interpret_state = engine.InterpretStateLessThan()
        self.engine = engine.Engine(self.interpret_state)
        self.logical_state = model.LogicalState(self.engine)
        #self.interpret_state = engine.InterpretStateLessThan()
        #self.engine = engine.Engine(self.interpret_state)

    def test_get_int(self):
        self.tf.clear()
        X = terms.mk_var("X")
        term1 = parser.parse_literal('p(a, X)')
        self.tf.mk_literal(term1)
        arguments_as_terms = term1.args
        a = arguments_as_terms[0]
        # predicate p
        self.assertEqual(1, self.tf.get_int(term1.pred))
        # arguments
        self.assertEqual(2, self.tf.get_int(a))
        self.assertEqual(-1, self.tf.get_int(X))

    def test_get_symbol(self):
        self.tf.clear()
        X = terms.mk_var("X")
        term1 = parser.parse_literal('p(a, X)')
        self.tf.mk_literal(term1)
        arguments_as_terms = term1.args
        a = arguments_as_terms[0]
        # predicate p
        self.assertEqual(term1.pred, self.tf.get_symbol(1))
        # arguments
        self.assertEqual(a, self.tf.get_symbol(2))
        self.assertEqual(X, self.tf.get_symbol(-1))

    def test_add_const(self):
        self.tf.clear()
        a = terms.StringConst("a")
        b = terms.StringConst("b")
        i = self.tf.get_int(a)
        self.assertFalse(i)
        self.tf.add_const(a)
        self.tf.add_const(b)
        i = self.tf.get_int(a)
        j = self.tf.get_int(b)
        self.assertEqual(i, 1)
        self.assertEqual(j, 2)
        self.assertEqual(a, self.tf.get_symbol(i))
        self.assertEqual(b, self.tf.get_symbol(j))

    def test_add_var(self):
        self.tf.clear()
        X = terms.mk_var("X")
        Y = terms.mk_var("Y")
        i = self.tf.get_int(X)
        self.assertFalse(i)
        self.tf.add_var(X)
        self.tf.add_var(Y)
        i = self.tf.get_int(X)
        j = self.tf.get_int(Y)
        self.assertEqual(i, -1)
        self.assertEqual(j, -2)
        self.assertEqual(X, self.tf.get_symbol(i))
        self.assertEqual(Y, self.tf.get_symbol(j))

    def test_create_fresh_var_or_const(self):
        self.tf.clear()
        X = terms.mk_var("X")
        a = terms.StringConst("a")
        self.tf.create_fresh_var_or_const(X)
        self.tf.create_fresh_var_or_const(a)
        i = self.tf.get_int(X)
        j = self.tf.get_int(a)
        self.assertEqual(i, -1)
        self.assertEqual(j, 1)

    def test_mk_literal(self):
        self.tf.clear()
        X = terms.mk_var("X")
        term1 = parser.parse_literal('p(a, X)')
        internal_literal = self.tf.mk_literal(term1)
        self.assertEqual([1,2,-1], internal_literal)
        internal_literal2 = self.tf.mk_literal(term1)
        # should not be added twice
        self.assertEqual(internal_literal2, internal_literal)

    def test_mk_clause(self):
        self.tf.clear()

        X = terms.mk_var("X")
        Y = terms.mk_var("Y")
        qab = parser.parse_literal('q(a, b)')
        pXY = parser.parse_literal('p(X, Y)')
        iXb = parser.parse_literal('i(X, b)')
        clause = terms.Clause(qab, [pXY, iXb])

        internal_clause = self.tf.mk_clause(clause)
        self.assertEqual([[1, 2, 3], [4, -1, -2], [5, -1, 3]], internal_clause)

    def test_open_literal(self):
        self.tf.clear()
        X = terms.mk_var("X")
        term1 = parser.parse_literal('p(a, X)')
        internal_literal = self.tf.mk_literal(term1)
        opened_literal = self.tf.open_literal(term1)
        self.assertEqual(internal_literal, opened_literal)

    def test_close_literal(self):
        self.tf.clear()
        X = terms.mk_var("X")
        term1 = parser.parse_literal('p(a, X)')
        internal_literal = self.tf.mk_literal(term1)
        closed_literal = self.tf.close_literal(internal_literal)
        self.assertEqual(closed_literal, term1)

    def test_close_literals(self):
        self.tf.clear()
        X = terms.mk_var("X")
        term1 = parser.parse_literal('p(a, X)')
        term2 = parser.parse_literal('q(b, X)')
        internal_literal = self.tf.mk_literal(term1)
        internal_literal2 = self.tf.mk_literal(term2)
        closed_literals = self.tf.close_literals([internal_literal,
            internal_literal2])
        self.assertCountEqual(closed_literals, [term1, term2])

    def test_readable_clause(self):
        self.tf.clear()
        X = terms.mk_var("X")
        Y = terms.mk_var("Y")
        qab = parser.parse_literal('q(a, b)')
        pXY = parser.parse_literal('p(X, Y)')
        iXb = parser.parse_literal('i(X, b)')
        clause = terms.Clause(qab, [pXY, iXb])
        internals = self.tf.mk_clause(clause)
        self.assertEqual("q(a, b) :- p(X, Y),i(X, b)", self.tf.readable_clause(internals))

    def test_close_explanation(self):
        X = terms.mk_var("X")
        Y = terms.mk_var("Y")
        qab = parser.parse_literal('q(a, b)')
        pab = parser.parse_literal('p(a, b)')
        pXY = parser.parse_literal('p(X, Y)')
        iXb = parser.parse_literal('i(X, b)')
        iab = parser.parse_literal('i(a, b)')

        clause = terms.Clause(qab, [pXY, iXb])
        internal_clause = self.tf.mk_clause(clause)
        prule = graph.PendingRule(internal_clause)
        
        resolved_clause = terms.Clause(qab, [iab])
        internal_resolved_clause = self.tf.mk_clause(resolved_clause)
        claim_expl = model.create_axiom_explanation()

        # note that in explanation1 the 2nd argument is a claim (a list of a # list of integers)
        explanation1 = model.create_resolution_bottom_up_explanation(prule, [self.tf.mk_literal(pab)], claim_expl)
        explanation2 = model.create_resolution_top_down_explanation(internal_clause, self.tf.mk_literal(pab))
        explanation3 = model.create_external_explanation()
        explanation4 = model.create_axiom_explanation()

        term_explanation = pab

        self.assertEqual("ResolutionBottomUp with q(a, b) :- p(X, Y),i(X, b) and p(a, b).", self.tf.close_explanation(explanation1))
        self.assertEqual("ResolutionTopDown with q(a, b) :- p(X, Y),i(X, b) and p(a, b).", self.tf.close_explanation(explanation2))
        self.assertEqual("External", self.tf.close_explanation(explanation3))
        self.assertEqual("Axiom", self.tf.close_explanation(explanation4))
        self.assertEqual(pab, self.tf.close_explanation(term_explanation))
        self.assertEqual(None, self.tf.close_explanation(None))
        self.assertEqual("some string", self.tf.close_explanation("some string"))
 
    def test_is_fact(self):
        self.tf.clear()
        qab = parser.parse_literal('q(a, b)')
        pac = parser.parse_literal('p(a, c)')
        clause1 = terms.Clause(qab, [pac])
        clause2 = terms.Clause(qab, [])
 
        i_clause1 = self.tf.mk_clause(clause1)
        i_clause2 = self.tf.mk_clause(clause2)
        self.assertFalse(model.is_fact(i_clause1))
        self.assertTrue(model.is_fact(i_clause2))

    def test_is_ground(self):
        self.tf.clear()
        qab = parser.parse_literal('q(a, b)')
        paX = parser.parse_literal('p(a, X)')
        self.assertTrue(model.is_ground(self.tf.mk_literal(qab)))
        self.assertFalse(model.is_ground(self.tf.mk_literal(paX)))

    def test_offset_and_shiftliteral(self):
        c = [[1, -1], [1, -2, -3]]
        self.assertEqual(model.offset(c),-3)
        self.assertEqual(model.shift_literal([1,-1],-3), [1,-4])

    def test_offset_positive_only(self):
        c = [[1,3], [2, 4, 5]]
        # offset has to be 0 for rules not containing constants
        self.assertEqual(model.offset(c),0)
    
    def test_find_first_variable_difference(self):
        self.tf.clear()
        term1 = parser.parse_literal('q(a, X, b, Z)')
        term2 = parser.parse_literal('p(a, X, b, U)')
        lit1 = self.tf.mk_literal(term1)
        lit2 = self.tf.mk_literal(term2)
        self.assertEqual(1, model.find_first_variable_difference(lit1, lit2))

    def test_get_unification_l(self):
        result1 = model.get_unification_l([1,-1,-2],[1,-3,4])
        expected_result1 = {-2: 4, -1: -3}
        result2 = model.get_unification_l([1,-1,-1],[1,-2,3])
        expected_result2 = {-2: 3, -1: 3}
        self.assertEqual(result2, expected_result2)

    def test_substitute(self):
        self.tf.clear()
        X = terms.mk_var("X")
        Y = terms.mk_var("Y")
        L = terms.mk_array([terms.IdConst("a"), X])
        term1 = parser.parse_literal('q(X, [a, X])')
        term2 = parser.parse_literal('q(b, Y)')

        lit1 = self.tf.mk_literal(term1)
        lit2 = self.tf.mk_literal(term2)

        subst = model.get_unification_l(lit1, lit2)
        self.assertTrue(model.is_substitution(subst))

        x = self.tf.get_int(X)
        y = self.tf.get_int(Y)
        q = self.tf.get_int(terms.mk_idconst("q"))
        a = self.tf.get_int(terms.mk_idconst("a"))
        b = self.tf.get_int(terms.mk_idconst("b"))
        l = self.tf.get_int(L)

        expected_subst = { x : b, y: l }
        self.assertEqual(expected_subst, subst)
    
        # result will be an integer
        result = model.substitute(subst, l, self.tf)
        # note that only after substitute, a becomes not None
        a = self.tf.get_int(terms.mk_idconst("a"))
        expected_result = terms.mk_array([terms.mk_idconst("a"), terms.mk_idconst("b")])
        result = self.tf.get_symbol(result)
        self.assertEqual(expected_result, result)

    def test_substitute_with_list(self):
        self.tf.clear()
        X = terms.mk_var("X")
        Y = terms.mk_var("Y")
        L = terms.mk_array([terms.mk_idconst("a"), X])
        term1 = parser.parse_literal('q(X, [a, X])')
        term2 = parser.parse_literal('q(b, Y)')

        lit1 = self.tf.mk_literal(term1)
        lit2 = self.tf.mk_literal(term2)

        subst = model.get_unification_l(lit1, lit2)

        result = model.substitute(subst, lit2[2], self.tf)
        result_array = terms.mk_array([terms.mk_idconst("a"), terms.mk_idconst("b")])
        internal = self.tf.get_int(result_array)
        self.assertEqual(result, internal)

    def test_apply_substitution(self):
        self.tf.clear()
        subst = {-5: 5, -2: 3, -1: 3}
        clause = [[1, -1], [1, -2, -3]]
        result1 = model.apply_substitution_c(subst,clause, self.tf)
        expected_result1 = [[1, 3], [1, 3, -3]]
        self.assertEqual(result1, expected_result1)

    def test_apply_substitute_with_list(self):
        self.tf.clear()
        X = terms.mk_var("X")
        Y = terms.mk_var("Y")
        L = terms.mk_array([terms.mk_idconst("a"), X])
        term1 = parser.parse_literal('q(X, [a, X])')
        term2 = parser.parse_literal('q(b, Y)')

        lit1 = self.tf.mk_literal(term1)
        lit2 = self.tf.mk_literal(term2)

        subst = model.get_unification_l(lit1, lit2)
        result1 = model.apply_substitution_l(subst, lit2, self.tf)
        result2 = model.apply_substitution_l(subst, lit1, self.tf)

        result_array = terms.mk_array([terms.mk_idconst("a"), terms.mk_idconst("b")])
        internal = self.tf.get_int(result_array)
        q = self.tf.get_int(terms.mk_idconst("q"))
        b = self.tf.get_int(terms.mk_idconst("b"))
        self.assertEqual([q, b, internal], result2)
        self.assertEqual([q, b, internal], result1)


    def test_remove_first_body_literal(self):
        self.tf.clear()
        pathXY = parser.parse_literal('path(X, Y)')
        pathXZ = parser.parse_literal('path(X, Z)')
        pathXa = parser.parse_literal('path(X, a)')
        edgeZY = parser.parse_literal('edge(Z, Y)')
        edgeaY = parser.parse_literal('edge(a, Y)')
        rule = terms.Clause(pathXY, [pathXZ, edgeZY])
        internal_rule = self.tf.mk_clause(rule)
        x = self.tf.get_int(terms.mk_var("X"))
        y = self.tf.get_int(terms.mk_var("Y"))
        z = self.tf.get_int(terms.mk_var("Z"))

        self.tf.add_const(terms.mk_idconst("a"))
        a = self.tf.get_int(terms.mk_idconst("a"))
        
        subst = {z: a}
        new_clause = model.remove_first_body_literal(internal_rule, subst, self.tf)
        expected_clause = [self.tf.open_literal(pathXY), self.tf.mk_literal(edgeaY)]
        self.assertEqual(expected_clause, new_clause)

    def test_create_resolution_bottom_up_explanation(self):
        from_clause = graph.PendingRule([[1,2,4],[1,3,5]])
        from_claim = [[1,3,5]]
        claim_expl = model.create_axiom_explanation()
        explanation = model.create_resolution_bottom_up_explanation(from_clause, from_claim, claim_expl)
        self.assertEqual(explanation, ("ResolutionBottomUp", from_clause, from_claim, claim_expl))

    def test_create_resolution_top_down_explanation(self):
        from_clause = [[1,2,4],[1,3,5]]
        from_goal = [1,3,5]
        explanation = model.create_resolution_top_down_explanation(from_clause, from_goal)
        self.assertEqual(explanation, ("ResolutionTopDown", from_clause, from_goal))

    def test_create_axiom_explanation(self):
        explanation = model.create_axiom_explanation()
        self.assertEqual(explanation, ("Axiom",))

    def test_create_external_explanation(self):
        explanation = model.create_external_explanation()
        self.assertEqual(explanation, ("External",))


    def test_is_bottom_up_explanation(self):
        from_clause = graph.PendingRule([[1,2,4],[1,3,5]])
        from_claim = [[1,3,5]]
        claim_expl = model.create_axiom_explanation()
        explanation = model.create_resolution_bottom_up_explanation(from_clause, from_claim, claim_expl)
        self.assertTrue(model.is_bottom_up_explanation(explanation))

    def test_is_top_down_explanation(self):
        from_clause = ((1,2,4),(1,3,5))
        from_goal = [1,3,5]
        explanation = model.create_resolution_top_down_explanation(from_clause, from_goal)
        self.assertTrue(model.is_top_down_explanation(explanation))

    def test_get_rule_from_explanation(self):
        from_clause = graph.PendingRule([[1,2,4],[1,3,5]])
        from_claim = [[1,3,5]]
        claim_expl = model.create_axiom_explanation()
        explanation = model.create_resolution_bottom_up_explanation(from_clause, from_claim, claim_expl)
        self.assertEqual(from_clause, model.get_rule_from_explanation(explanation))

    def test_get_goal_from_explanation(self):
        from_clause = [[1,2,4],[1,3,5]]
        from_goal = [1,3,5]
        explanation = model.create_resolution_top_down_explanation(from_clause, from_goal)
        self.assertEqual(from_goal, model.get_goal_from_explanation(explanation))

    def test_freeze_clause(self):
        clause = [[1,3,5],[5,6,7]]
        expected = ((1,3,5),(5,6,7))
        self.assertEqual(expected, model.freeze_clause(clause))

    def test_freeze(self):
        clause = [[1,3,5],[5,6,7]]
        literal = [1,4,6]
        self.assertEqual((1,4,6), model.freeze(literal))
        self.assertEqual(((1,3,5),(5,6,7)), model.freeze(clause))

    def test_frozen(self):
        a = (1,2,3)
        b = [1,2,3]
        self.assertTrue(model.frozen(a))
        self.assertFalse(model.frozen(b))

    def test_min_index(self):
        self.assertEqual(1, model.min_index(None,1))
        self.assertEqual(1, model.min_index(1, None))
        self.assertEqual(None, model.min_index(None,None))
        self.assertEqual(4, model.min_index(6,4))

    def test_min_indices(self):
        self.assertEqual(None, model.min_indices(None, []))
        self.assertEqual(None, model.min_indices(None, [None]))
        self.assertEqual(None, model.min_indices(None, [None, None]))
        self.assertEqual(1, model.min_indices(None, [None, 1]))
        self.assertEqual(1, model.min_indices(2, [None, 1]))
        self.assertEqual(1, model.min_indices(1, [None, 2]))
        self.assertEqual(1, model.min_indices(1, [None, 2, None]))

    def test_db_mem_and_db_add_clause(self):
        self.logical_state.clear()
        qab = parser.parse_literal('q(a, b)')
        q2ab = parser.parse_literal('q2(a, b)')
        pac = parser.parse_literal('p(a, c)')
        clause1 = terms.Clause(qab, [pac])
        clause2 = terms.Clause(qab, [])
        clause3 = terms.Clause(q2ab, [pac])
        i_clause1 = self.tf.mk_clause(clause1)
        i_clause3 = self.tf.mk_clause(clause3)
        self.logical_state.db_add_clause(i_clause3, "no explanation")
        self.assertTrue(not self.logical_state.db_mem(i_clause1))
        self.assertTrue(self.logical_state.db_mem(i_clause3))

    def test_db_mem_claim_and_db_add_claim(self):
        self.logical_state.clear()
        qab = parser.parse_literal('q(a, b)')
        internal_claim = [self.tf.mk_literal(qab)]
        prule = self.logical_state.db_add_pending_rule(internal_claim)
        self.assertFalse(self.logical_state.db_mem_claim(prule))
        self.logical_state.db_add_claim(prule)
        self.assertTrue(self.logical_state.db_mem_claim(prule))

    def test_add_claim(self):
        qab = parser.parse_literal('q(a, b)')
        clause2 = terms.Clause(qab, [])
        i_clause2 = self.tf.mk_clause(clause2)
        qab_test = parser.parse_literal('q(a, b)')
        internal_literal = model.freeze(self.tf.mk_literal(qab_test))
        prule = self.logical_state.db_add_pending_rule(i_clause2)
        self.logical_state.db_add_claim(prule)
        specializations = [prule.clause for prule in index.get_candidate_specializations(self.logical_state.db_claims,internal_literal)]
        print(('internal_literal = {0}'.format(internal_literal)))
        print(('specials = {0}'.format(specializations)))
        self.assertTrue((internal_literal,) in specializations)

    def test_db_add_goal(self):
        qab = parser.parse_literal('q(a, b)')
        internal_literal = self.tf.mk_literal(qab)
        self.logical_state.db_add_goal(internal_literal)
        self.assertTrue(internal_literal in index.get_candidate_specializations(self.logical_state.db_goals,internal_literal))
        frozen = model.freeze(internal_literal)
        self.assertTrue(frozen in self.logical_state.goal_dependencies.nodes_to_annotations)

    def test_db_add_goal_to_pending_rule(self):
        qab = parser.parse_literal('q(a, b)')
        pab = parser.parse_literal('p(a, b)')
        int1 = self.tf.mk_literal(qab)
        int2 = self.tf.mk_literal(pab)
        pending = self.logical_state.goal_dependencies.add_pending_rule([int1, int2])
        self.logical_state.db_add_goal_to_pending_rule(int1, pending)
        self.assertTrue(model.freeze(int1) in self.logical_state.goal_dependencies.nodes_to_annotations)
        self.assertTrue(pending in self.logical_state.goal_dependencies.graph[model.freeze(int1)])

    def test_db_add_pending_rule_to_goal(self):
        qab = parser.parse_literal('q(a, b)')
        pab = parser.parse_literal('p(a, b)')
        int1 = self.tf.mk_literal(qab)
        int2 = self.tf.mk_literal(pab)
        pending = self.logical_state.goal_dependencies.add_pending_rule([int1, int2])
        self.logical_state.db_add_pending_rule_to_goal(pending, int1)
        self.assertTrue(model.freeze(int1) in self.logical_state.goal_dependencies.nodes_to_annotations)
        self.assertTrue(model.freeze(int1) in self.logical_state.goal_dependencies.graph[pending])

    def test_db_add_pending_rule_to_pending_rule(self):
        qab = parser.parse_literal('q(a, b)')
        pab = parser.parse_literal('p(a, b)')
        int1 = self.tf.mk_literal(qab)
        int2 = self.tf.mk_literal(pab)
        pending1 = self.logical_state.goal_dependencies.add_pending_rule([int1, int2])
        pending2 = self.logical_state.goal_dependencies.add_pending_rule([int2, int1])
        self.logical_state.db_add_pending_rule_to_pending_rule(pending1, pending2)
        self.assertTrue(pending2 in self.logical_state.goal_dependencies.graph[pending1])
        self.assertFalse(pending1 in self.logical_state.goal_dependencies.graph[pending2])
        self.logical_state.db_add_pending_rule_to_pending_rule(pending2, pending1)
        self.assertTrue(pending2 in self.logical_state.goal_dependencies.graph[pending1])
        self.assertTrue(pending1 in self.logical_state.goal_dependencies.graph[pending2])

    def test_add_clause_head(self):
        qab = parser.parse_literal('q(a, b)')
        pac = parser.parse_literal('p(a, c)')
        clause1 = terms.Clause(qab, [pac])
        i_clause1 = self.tf.mk_clause(clause1)
        qab_test = parser.parse_literal('q(a, b)')
        internal1 = self.tf.mk_literal(qab_test)
        pac_test = parser.parse_literal('p(a, c)')
        internal2 = self.tf.mk_literal(pac_test)
        self.logical_state.db_add_clause_head(i_clause1)
        self.assertTrue([internal1, internal2] in index.get_candidate_specializations(self.logical_state.db_heads,internal1))   

    def test_add_clause_selected(self):
        qab = parser.parse_literal('q(a, b)')
        pac = parser.parse_literal('p(a, c)')
        clause1 = terms.Clause(qab, [pac])
        i_clause1 = self.tf.mk_clause(clause1)
        qab_test = parser.parse_literal('q(a, b)')
        internal1 = self.tf.mk_literal(qab_test)
        pac_test = parser.parse_literal('p(a, c)')
        internal2 = self.tf.mk_literal(pac_test)
        self.logical_state.db_add_clause_selected(i_clause1[1], i_clause1)
        self.assertTrue([internal1, internal2] in index.get_candidate_specializations(self.logical_state.db_selected,internal2))


    def test_db_get_explanation(self):
        X = terms.mk_var("X")
        Y = terms.mk_var("Y")
        qab = parser.parse_literal('q(a, b)')
        pab = parser.parse_literal('p(a, b)')
        pXY = parser.parse_literal('p(X, Y)')
        iXb = parser.parse_literal('i(X, b)')
        iab = parser.parse_literal('i(a, b)')

        clause = terms.Clause(qab, [pXY, iXb])
        internal_clause = self.tf.mk_clause(clause)
        prule = graph.PendingRule(internal_clause)

        claim = self.tf.mk_clause(terms.Clause(pab, []))
        
        resolved_clause = terms.Clause(qab, [iab])
        internal_resolved_clause = self.tf.mk_clause(resolved_clause)

        claim_expl = model.create_axiom_explanation()
        explanation = model.create_resolution_bottom_up_explanation(prule, claim, claim_expl)
        self.logical_state.db_add_clause(internal_resolved_clause, explanation)
        self.assertEqual(explanation, self.logical_state.db_get_explanation(internal_resolved_clause))

    def test_no_stuck_subgoals(self):
        self.logical_state.clear()
        pong1 = self.tf.mk_literal(parser.parse_literal('pong(1)'))
        ping0 = self.tf.mk_literal(parser.parse_literal('ping(0)'))
        pending = self.logical_state.goal_dependencies.add_pending_rule([pong1, ping0])

        self.logical_state.db_add_goal_to_pending_rule(pong1, pending)
        self.logical_state.db_add_pending_rule_to_goal(pending, ping0)
        self.logical_state.db_move_goal_to_stuck(pong1)
        self.logical_state.db_move_goal_to_stuck(ping0)

        #self.assertFalse(self.logical_state.no_stuck_subgoals(pending))
        self.assertFalse(self.logical_state.no_stuck_subgoals(pong1))
        self.assertFalse(self.logical_state.no_stuck_subgoals(ping0))



        


 



if __name__ == '__main__':
    unittest.main()
