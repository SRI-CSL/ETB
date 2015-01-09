"""
ETB Parser based on parsimonious.

The grammar is defined in the docstring, essentially EBNF, but
uses ``/`` (first match) instead of ``|``.  ``+``, ``*``, ``?`` have usual meaning
regex's start with ``~``.

The grammar.parse function generates parsimonious Nodes, which are
then translated to ETB terms using the visit method of ETBParser.

This is significantly faster than pyparsing, while still being easy to install.

..
   Copyright (C) 2013 SRI International

   This program is free software: you can redistribute it
   and/or modify it under the terms of the GNU General Public License as
   published by the Free Software Foundation, either version 3 of the
   License, or (at your option) any later version. This program is
   distributed in the hope that it will be useful, but WITHOUT ANY
   WARRANTY; without even the implied warranty of MERCHANTABILITY or
   FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
   for more details.  You should have received a copy of the GNU General
   Public License along with this program.  If not, see
   <http://www.gnu.org/licenses/>.
"""

import terms
import string
import re
from parsimonious.grammar import Grammar, NodeVisitor
from parsimonious.exceptions import ParseError, IncompleteParseError

grammar = Grammar(
  """
  statements = _ statement+
  statement  = fact / clause / inference_rule
  fact = literal pd
  # clause is same as derivation_rule?
  clause = literal ts literals pd
  inference_rule = literal infer literals pd

  claims = _ lk claim rest_claims* rk
  rest_claims = co claim
  claim = claim_type lp literal co "reason" _ eq reason rp
  claim_type = "claim" / "interpretedClaim" / "derivedClaim" / "provedClaim"
  reason = dstring / clause / inference_rule #/ derivation_rule
  
  literals = literal rest_lits*
  rest_lits = co literal
  literal = infix_lit / app_lit
  infix_lit = term binop term
  binop = eq / neq
  app_lit = pred args
  pred = id / string
  args = lp terms? rp
  
  substitutions = lk substs? rk
  substs = subst rest_substs*
  rest_substs = co subst
  subst = "subst" lp bindings? rp
  bindings = binding rest_bindings*
  rest_bindings = co binding
  binding = id eq term
  
  terms = term rest_terms*
  rest_terms = co term
  
  term = token / array / obj
  token = num / id / string
  array = lk terms? rk access*
  obj = lb objpairs? rb access*
  objpairs = objpair rest_objpair*
  rest_objpair = co objpair
  objpair = token cl term
  access = lk token rk
  string = dstring / sstring
  
  id = ~r"[^][(){}=:`'\\".,~?% \\\]+" _
  dstring = ~r'"([^"\\\\]*(?:\\\\.[^"\\\\]*)*)"' _
  sstring = ~r"'([^'\\\\]*(?:\\\\.[^'\\\\]*)*)'" _
  num = ~"[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?" _
  
  _ = whitespace*
  whitespace = ~"\s+" / comment
  comment = ~"%[^\\n\\r]*[\\n\\r]*"
  eq = "=" _
  neq = "!=" _
  ts = ":-" _
  infer = "<=" _
  lp = "(" _
  rp = ")" _
  lk = "[" _
  rk = "]" _
  lb = "{" _
  rb = "}" _
  cl = ":" _
  co = "," _
  pd = "." _
  """)

class ETBParser(NodeVisitor):
  """Visitor that turns a parse tree into ETB Terms
     See parsimonious.NodeVisitor docstring for more info
  """
  def visit(self, node):
    """Replaces NodeVisitor.visit, which wraps errors in an opaque way.
    In particular, parsing a file with an error generates pages of output
    that is meaningless to the user.
    This is actually the same as NodeVisitor.visit, but without try...except"""
    method = getattr(self, 'visit_' + node.expr_name, self.generic_visit)
    return method(node, [self.visit(n) for n in node])
    
  def visit_statements(self, node, (_, statements)):
    return statements
  
  def visit_statement(self, node, stmt):
    return stmt[0]

  def visit_fact(self, node, (term, _)):
    #print 'visit_fact: term {0}: {1}'.format(term, type(term))
    return term

  def visit_clause(self, node, (head, ts, tail, pd)):
    return terms.DerivationRule(head, tail)

  def visit_inference_rule(self, node, (head, inf, tail, pd)):
    return terms.InferenceRule(head, tail)

  def visit_claims(self, node, (_, lk, claim, rest_claims, rk)):
    if isinstance(rest_claims, list):
      return [claim] + rest_claims
    else:
      return [claim]

  def visit_rest_claims(self, node, (_, claim)):
    return claim

  def visit_claim(self, node, (ctype, lp, lit, co, re, _, eq, reason, rp)):
    if ctype == "interpretedClaim":
      return terms.InterpretedClaim(lit, reason)
    elif ctype == "derivedClaim":
      return terms.DerivedClaim(lit, reason)
    elif ctype == "provedClaim":
      return terms.ProvedClaim(lit, reason)
    else:
      return terms.Claim(lit, reason)

  def visit_reason(self, node, reason):
    return reason[0]

  def visit_literals(self, node, (first_lit, rest_lits)):
    #print 'visit_literals: first {0}: {1}, rest {2}: {3}'.format(first_lit, type(first_lit), rest_lits, type(rest_lits))
    if isinstance(rest_lits, list):
      return [first_lit] + rest_lits
    else:
      return [first_lit]

  def visit_rest_lits(self, node, (_, lit)):
    #print 'visit_rest_lits: lit {0}: {1}'.format(lit, type(lit))
    return lit

  def visit_literal(self, node, lit):
    #print 'visit_literal: lit {0}: {1}'.format(lit[0], type(lit[0]))
    return lit[0]

  def visit_infix_lit(self, node, (lhs, op, rhs)):
    #print 'visit_infix_lit: lhs {0}: {1}'.format(lhs, type(lhs))
    #print 'visit_infix_lit: op {0}: {1}'.format(op, type(op))
    #print 'visit_infix_lit: rhs {0}: {1}'.format(rhs, type(rhs))
    return terms.InfixLiteral(op, [lhs, rhs])

  def visit_binop(self, node, op):
    #print 'visit_binop: op {0}: {1}'.format(op[0], type(op[0]))
    binop = op[0]
    return binop

  def visit_eq(self, node, (eq, _)):
    #print 'visit_eq: eq {0}: {1}'.format(eq, type(eq))
    return '='

  def visit_neq(self, node, (neq, _)):
    #print 'visit_eq: eq {0}: {1}'.format(neq, type(neq))
    return '!='

  def visit_app_lit(self, node, (pred, args)):
    #print 'visit_app_lit: pred {0}: {1}, args {2}: {3}'.format(pred, type(pred), args, type(args))
    return terms.Literal(pred, args)

  def visit_pred(self, node, pred):
    #print 'visit_pred: node {0}'.format(node.children[0].expr_name)
    #print 'visit_pred: pred {0}: {1}'.format(pred, type(pred))
    if node.children[0].expr_name == 'string':
      return terms.StringConst(pred[0])
    else:
      return terms.IdConst(pred[0])

  def visit_args(self, node, (lp, terms, rp)):
    #print 'visit_args: terms = {0}, type {1}'.format(terms[0], type(terms[0]))
    if isinstance(terms, list):
      return terms[0]
    else:
      return []

  # Substitutions

  def visit_substitutions(self, node, (lk, substs, rk)):
    if isinstance(substs, list):
      return substs[0]
    else:
      return []

  def visit_substs(self, node, (subst, rest_substs)):
    if isinstance(rest_substs, list):
      return [subst] + rest_substs
    else:
      return [subst]

  def visit_rest_substs(self, node, (_, subst)):
    return subst

  def visit_subst(self, node, (_, lp, bindings, rp)):
    if isinstance(bindings, list):
      return terms.Subst(dict(bindings[0]))
    else:
      return terms.Subst(dict())

  def visit_bindings(self, node, (binding, rest_bindings)):
    if isinstance(rest_bindings, list):
      return [binding] + rest_bindings
    else:
      return [binding]

  def visit_rest_bindings(self, node, (_, binding)):
    return binding

  def visit_binding(self, node, (id, eq, term)):
    if not id[0].isupper():
      raise TypeError('Identifier expected to be variable (i.e., capitalized) here')
    return (terms.Var(id), term)

  # Terms

  def visit_terms(self, node, (term, rest_terms)):
    #print 'visit_terms: term {0}: {1}, rest_terms {0}: {1}'.format(term, type(term), rest_terms, type(rest_terms))
    if isinstance(rest_terms, list):
      return [term] + rest_terms
    else:
      return [term]

  def visit_rest_terms(self, node, (_, term)):
    #print 'visit_rest_terms: term {0}: {1}'.format(term, type(term))
    return term

  def visit_term(self, node, term):
    #print 'visit_term: node {0}: {1}'.format(node, type(node))
    #print 'visit_term: term {0}: {1}'.format(term[0], type(term[0]))
    return term[0]

  def visit_token(self, node, token):
    #print 'visit_token: token = {0}: {1}'.format(token, type(token))
    #print 'visit_token: node.children = {0}: {1}'.format(node.children, len(node.children))
    text = token[0]
    if node.children[0].expr_name == 'string':
      term = terms.mk_stringconst(text)
    elif node.children[0].expr_name == 'id':
      if text[0].isupper():
        term = terms.mk_var(text)
      else:
        term = terms.mk_idconst(text)
    else:
      term = terms.mk_numberconst(text)
    #print 'visit_const: {0}, type {1}'.format(term, type(term))
    return term

  def visit_array(self, node, (lk, elems, rk, accesses)):
    #print 'visit_array: elems {0}: {1}, {2}: {3}'.format(elems, type(elems), accesses, type(accesses))
    if isinstance(elems, list):
      array = terms.mk_array(elems[0])
    else:
      #print 'visit_array: empty array'
      array = terms.mk_array([])
    if isinstance(accesses, list):
      return array.reduce_access(accesses)
    else:
      #print 'visit_array: array = {0}, type {1}'.format(array, type(array))
      return array

  def visit_obj(self, node, (lb, objpairs, rb, accesses)):
    #print 'visit_obj: {0}: {1}, {2}: {3}'.format(objpairs, type(objpairs), accesses, type(accesses))
    if isinstance(objpairs, list):
      obj = terms.mk_map(objpairs[0])
    else:
      obj = terms.mk_map([])
    if isinstance(accesses, list):
      return obj.reduce_access(accesses)
    else:
      #print 'visit_array: array = {0}, type {1}'.format(array, type(array))
      return obj

  def visit_objpairs(self, node, (objpair, rest_objpair)):
    #print 'visit_objpairs: objpair {0}: {1}, other {2}: {3}'.format(objpair, type(objpair), rest_objpair, type(rest_objpair))
    #print 'visit_objpairs: objpair[1] {0}: {1}'.format(objpair[1], type(objpair[1]))
    if isinstance(rest_objpair, list):
      return dict([objpair] + rest_objpair)
    else:
      return dict([objpair])

  def visit_rest_objpair(self, node, (_, objpair)):
    #print 'visit_rest_objpair: {0}: {1}'.format(objpair, type(objpair))
    return objpair

  def visit_objpair(self, node, (token, cl, term)):
    #print 'visit_objpair: token {0}: {1}'.format(token, type(token))
    #print '                  term {0}: {1}'.format(term, type(term))
    if isinstance(token, terms.Var):
      raise TypeError('Identifier expected to be constant (i.e., not capitalized) here')
    return (token, term)

  def visit_access(self, node, (lk, token, rk)):
    #print 'visit_access: token {0}: {1}'.format(token, type(token))
    return token

  def visit_id(self, node, (id, _)):
    #print 'visit_id: {0}: {1}'.format(node, type(node))
    #print 'visit_id: {0}: {1}'.format(id.text, type(id.text))
    return id.text

  def visit_string(self, node, string):
    #print 'visit_string: {0}: {1}'.format(string[0], type(string[0]))
    return string[0]

  def visit_dstring(self, node, (string, _)):
    return string.text[1:-1]

  def visit_sstring(self, node, (string, _)):
    return string.text[1:-1]

  def visit_num(self, node, (num, _)):
    return num.text

  def generic_visit(self, node, visited_children):
    """Default visitor method
    """
    result = visited_children or node
    #print 'generic_visit: result = {0}: {1}'.format(result, type(result))
    return result

def parse(text, nt='statements'):
  """Uses parsimonious to parse the ETB extended datalog language
  nt is the nonterminal.  The most useful ones are:
  statements, statement, literals, literal, and term.

  >>> type(parse('V', 'term'))
  <class 'terms.Var'>
  >>> type(parse('v', 'term'))
  <class 'terms.IdConst'>
  >>> type(parse('3', 'term'))
  <class 'terms.NumberConst'>
  >>> type(parse('3.14', 'term'))
  <class 'terms.NumberConst'>
  >>> type(parse('-3.14e-10', 'term'))
  <class 'terms.NumberConst'>
  >>> type(parse('"3 is a number"', 'term'))
  <class 'terms.StringConst'>
  >>> parse('3a', 'term')
  term has extra text: 'a' (line 1, column 2).
  """ 
  try:
    node = grammar[nt].parse(text.strip())
    return ETBParser().visit(node)
  except IncompleteParseError as iperr:
    print u"{0} has extra text: '{1}' (line {2}, column {3}).".format(
      iperr.expr.name, iperr.text[iperr.pos:iperr.pos + 20],
      iperr.line(), iperr.column())
  except ParseError as perr:
    rule_name = ((u"{0}".format(perr.expr.name)) if perr.expr.name else
                 unicode(perr.expr))
    raise ValueError(u"{0} expected at '{1}' (line {2}, column {3})."
                     .format(rule_name, perr.text[perr.pos:perr.pos + 20],
                             perr.line(), perr.column()))
  except TypeError as terr:
    print 'Parse error {1}: {0}'.format(terr, type(terr))
    print 'Parse error: done'
  except Exception as err:
    print 'Got an exception: {0}: {1}'.format(err, type(err))
    
def parse_term(text):
  return parse(text, 'term')

def parse_literal(text):
  lit = parse(text, 'literal')
  assert isinstance(lit, terms.Literal), 'parse_literal: text {2}, lit {0}: {1}'.format(lit, type(lit), text)
  return lit
  
def parse_file(file, nt='statements'):
  with open(file, 'rb') as fd:
    text = fd.read()
  return parse(text, nt)
