[![PyPI version](https://badge.fury.io/py/EvidentialToolBus.svg)](https://badge.fury.io/py/EvidentialToolBus)


Evidential Tool Bus (ETB)
=========================

The Evidential Tool Bus provides 

See the file INSTALL for installation instruction, in particular
external dependencies required to get ETB running.

The demos/ directory contains demos of ETB: 

*  allsat/ implements an ALLSAT solver using the ETB on top of the
     yices SMT solver.

*   allsat2/ implements an ALLSAT solver using the ETB on top of the
      yices2 SMT solver.
  
*   make/ shows how to use the ETB to implement a distributed make
      tools that keeps track of all dependencies between source and
      objects files.

*   k-induction/ shows two ways to implement a simple k-induction
      procedure on top of the ETB. It shows how derivation rules can
      be used to establish a fact, and inference rules can be used
      to extract a proof of that fact.

*   hybridSal/ shows how to integrate separate tools in a 
      complete workflow.

*   vc/ shows a demo of a wrapper that dynamically creates lemmata (generated clauses)

*   blackwhite/ shows a demo of the pure Datalog with recursion but without any wrappers

doc contains the documentation, including reference manuals

src contains the source code (see the README there for more details)

tests contains test scripts
