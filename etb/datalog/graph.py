"""Graph Maintaining Dependencies Between Goals and Pending Rules

This module defines an :class:`etb.datalog.graph.Annotation` class that stores
meta-information for goals and pending rules (e.g., whether a goal is `OPEN`
or `CLOSED`; or when the goal has been created via its `index`).

We further have a :class:`etb.datalog.graph.DependencyGraph` class in this
module. This module stores the dependencies between goals and pending rules,
and can be used to find out explanations for claims, or whether goals are
closed/complete or not.

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


import model

# Logging
import logging
import time

# Locking
import threading

class Annotation(object):

    # Type of item this Annotation object is storing information for
    GOAL = 0
    PENDING_CLAUSE = 1

    # Types of state allowed:

    OPEN = 0
    CLOSED = 1
    RESOLVED = 2
    COMPLETED = 3

    def __init__(self, item, kind, state):
        """
        Create an `Annotation` object using a particular `item` (a goal or a
        pending clause, indicated by `kind`) and a `state` mainly keep track of
        the global time.

        :parameters:
            - `item`: a particular item this `Annotation` provides
              meta-information for. We assume that the item can be used as a
              key (e.g., a tuple).
            - `kind`: currently used with
              :attr:`etb.datalog.graph.Annotation.GOAL` or
              :attr:`etb.datalog.graph.Annotation.PENDING_CLAUSE`.
            - `state`: An object that understands `get_global_time` and
              `inc_global_time` as well as `no_stuck_subgoals()`. We will
              use :class:`etb.datalog.model.LogicalState`.

        :class types:
            - `GOAL`: the annotation annotations a goal
            - `PENDING_CLAUSE`: the annotation annotates a goal
            - `OPEN`: an open goal (not processed in any way)
            - `RESOLVED`: resolution on the goal took place
            - `CLOSED`: the closing algorithm
              :func:`etb.datalog.graph.DependencyGraph.close` determined that
              this goal is ready for completion
            - `COMPLETED`: the completion algorithm
              :func:`etb.datalog.graph.DependencyGraph.complete` determined
              that this goal is completed

        :members:
            - `item`: the item this annotation annotates
            - `state`: the global state (for getting the current global time
              for example). We use this with a
              :class:`etb.datalog.model.LogicalState`.
            - `kind`: the kind of object this annotation refers to, either a
              :attr:`etb.datalog.graph.Annotation.GOAL` or a
              :attr:`etb.datalog.graph.Annotation.PENDING_CLAUSE`
            - `index`: an integer representing the time this annotation was
              created
            - `subgoalindex`: the number of claims that were propagated by the
              subgoal of the rule (in case this is a `PENDING_CLAUSE`)
            - `claims`: if the annotation refers to a `GOAL`, the `claims`
              member collects the current claims that match that goal.
            - `status`: one of `OPEN`, `RESOLVED`, `CLOSED`, `COMPLETED`. By
              default, it is `OPEN`.
            - `goal`: the goal this `PENDING_CLAUSE` is depending on.
            - `gT`: used by the closing algorithm; see closing algorithm
              specification.
            - `gD`: used by the closing algorithm; see closing algorithm
              specification.
            - `gUnclosed`: used by the closing algorithm; see closing algorithm
              specification.

        .. todo::
            Add links to closing algorithm specification.

        """
        # the item this Annotation object describes
        self.item = item
        # state is any object that understands get_global_time()
        self.state = state
        # the kind: GOAL or PENDING_CLAUSE
        self.kind = kind
        # the time the associated object was created
        self.index = self.state.get_global_time() + 1
        # subgoal index
        self.subgoalindex = 0
        # the claims matching this goal
        self.claims = []
        # status
        self.status = Annotation.OPEN

        # the goal this annotation object is a direct subgoal of (if this is a
        # pending clause) -- i.e., the first goal you encounter if you move up
        # the pending clauses chain:
        self.goal = None

        # increase global time by 1
        self.state.inc_global_time()


        # new
        self.gT = {}
        self.gD = {}
        self.gUnclosed = None

    def is_goal(self):
        """
        Determines whether this annotation refers to a goal.

        :returntype:
            - `True` or `False`
        """
        return self.kind == Annotation.GOAL

    def is_pending_clause(self):
        """
        Determines whether this annotation refers to a pending clause.

        :returntype:
            - `True` or `False`
        """
        return self.kind == Annotation.PENDING_CLAUSE

    def inc_subgoalindex(self):
        """
        Increase :attr:`etb.datalog.graph.Annotation.subgoalindex` by 1.

        :returntype:
            - `None`
        """
        self.subgoalindex += 1

    def nr_of_claims(self):
        """
        Return the number of claims this annotation matches with (if it is a
        goal).

        :returntype:
            - a positive integer (`0` if no claims are matching or the
              annotation is not a goal)
        """
        return len(self.claims)

    def print_status(self):
        """
        String representation of the annotation.

        :returntype:
            - string

        """
        if self.status == Annotation.OPEN:
            return "OPEN"
        elif self.status == Annotation.CLOSED:
            return "CLOSED"
        elif self.status == Annotation.RESOLVED:
            return "RESOLVED"
        elif self.status == Annotation.COMPLETED:
            return "COMPLETED"
        else:
            return "UNKNOWN"

    def print_gT(self, term_factory):
        """
        Get something that can be easily printed from
        :attr:`etb.datalog.graph.Annotation.gT`.

        :parameters:
            - `term_factory`: a :class:`etb.datalog.model.TermFactory` instance
              that allows for externalizing internal representations

        :returntype:
            - a dictionary where each key is now an external representation and
              each value is a list of external representations of clauses.
        """
        closed_gT = {}
        for subgoal in self.gT:
            closed_subgoal = term_factory.close_literal(subgoal)
            closed_clauses = map(lambda clause: term_factory.readable_clause(clause), self.gT[subgoal])
            closed_gT[closed_subgoal] = closed_clauses
        return closed_gT

    def print_gD(self, term_factory):
        """
        Get something that can be easily printed from
        :attr:`etb.datalog.graph.Annotation.gD`.

        :parameters:
            - `term_factory`: a :class:`etb.datalog.model.TermFactory` instance
              that allows for externalizing internal representations

        :returntype:
            - a dictionary where each key is now an external representation and
              each value is an integer
        """
        closed_gD = {}
        for subgoal in self.gD:
            closed_subgoal = term_factory.close_literal(subgoal)
            closed_gD[closed_subgoal] = self.gD[subgoal]
        return closed_gD


class DependencyGraph(object):
    def __init__(self, state):
        """
        Create a dependency graph object to store dependencies from goal to
        subgoals and pending rules. This is used to provide PNGs of goal
        dependencies as in :func:`etb.datalog.engine.goal_deps_to_png` or by
        the closing algorithm to determine whether a goal is completed
        (:func:`etb.datalog.engine.is_completed`).

        :parameters:
            - `state`: an object that can be used to initialize the state in
              :class:`etb.datalog.graph.Annotation` instances.

        :members:
            - `graph`: the actual graph is a dict where keys are the nodes in
              the graph and the value for each key/node is a list of other
              nodes/keys (the outgoing edges).
            - `state`: stores the state. We use
              :class:`etb.datalog.model.LogicalState`.
            - `nodes_to_annotations`: a dictionary mapping items in the graph to
              their corresponding annotation.
            - `tau`: used by the closing algorithm; see closing algorithm
              specification.

        """
        # the graph is a dict with keys are the nodes and the value of each
        # key/node is a list of nodes
        self.graph = {}
        # need parent edges, particularly from goal to the clauses that generated the goal
        self.parents = {}
        # state is the logical state that can return the global time
        self.state = state
        # todo: the mappings from goals and clauses (nodes) to Annotation
        # objects
        self.nodes_to_annotations = {}
        # Log object
        self.log = logging.getLogger('etb.datalog.graph')
        # the partial map tau of of goals to a map of goal indices to propagation indices
        self.tau = {}

        # lock associated with this graph
        self.rlock = threading.RLock()
        self.condition = threading.Condition(self.rlock)
        self.inferencing_clear = True

    def __enter__(self):
        self.condition.acquire()

    def __exit__(self, t, v, tb):
        self.condition.release()

    def clear(self):
        """
        Clear the dependency graph by clearing `self.graph`,
        `self.nodes_to_annotations`, and `self.tau`.
        """
        self.graph.clear()
        self.parents.clear()
        self.nodes_to_annotations.clear()
        self.tau.clear()

    def add_annotation(self, frozen_goal, annotation):
        self.nodes_to_annotations[frozen_goal] = annotation

    def add_goal(self, goal):
        """
        Add a goal to the dependency graph and create a matching annotation
        that describes that goal.

        :parameters:
            - `goal`: an internal representation of a goal (i.e., a list of
              integers)

        :returntype:
            `None`
        """
        frozen_goal = model.freeze(goal)
        if not self.__node_is_present(frozen_goal):
            # add node to graph
            self.add_node(frozen_goal)
            annotation_goal = Annotation(frozen_goal, Annotation.GOAL, self.state)
            # self.log.info('graph.add_goal: Adding {0}: {1}'
            #               .format(self.state.engine.term_factory.close_literal(frozen_goal),
            #                       annotation_goal.print_status()))
            self.nodes_to_annotations[frozen_goal] = annotation_goal

    def add_pending_rule(self, clause):
        """
        Add a pending rule to the dependency graph and create a matching annotation
        that describes it.

        :parameters:
            - `clause`: an internal representation of a clause

        :returntype:
            `None`
        """
        frozen_clause = model.freeze(clause)
        if not self.__node_is_present(frozen_clause):
            # add node to graph
            self.add_node(frozen_clause)
            annotation_clause = Annotation(frozen_clause, Annotation.PENDING_CLAUSE, self.state)
            self.nodes_to_annotations[frozen_clause] = annotation_clause

    def add_goal_to_pending_rule(self, goal, rule):
        """
        Add an dependency from a pending rule to a goal (a subgoal of theat
        pending rule) to the dependency graph.

        :parameters:
            - `goal`: an internal representation of a goal
            - `rule`: an internal representation of a clause

        :returntype:
            `None`
        """
        self.add_goal(goal)
        self.add_pending_rule(rule)
        self.graph[model.freeze(goal)].append(model.freeze(rule))
        self.parents[model.freeze(rule)].append(model.freeze(goal))

    def add_pending_rule_to_pending_rule(self, rule1, rule2):
        """
        Add a dependency from a pending rule to another pending rule to the dependency graph.

        :parameters:
            - `rule1`: an internal representation of a *from* clause
            - `rule2`: an internal representation of a *to* clause

        :returntype:
            `None`
        """
        self.add_pending_rule(rule1)
        self.add_pending_rule(rule2)
        self.graph[model.freeze(rule1)].append(model.freeze(rule2))
        self.parents[model.freeze(rule2)].append(model.freeze(rule1))

    def add_pending_rule_to_goal(self, rule, goal):
        """
        Add a dependency from a pending rule to a goal to the dependency graph.

        :parameters:
            - `rule`: an internal representation of a clause
            - `goal`: an internal representation of a goal

        :returntype:
            `None`
        """
        self.add_goal(goal)
        self.add_pending_rule(rule)
        self.graph[model.freeze(rule)].append(model.freeze(goal))
        self.parents[model.freeze(goal)].append(model.freeze(rule))        

    def get_annotation(self, item):
        """
        Get the annotation for a item.

        :parameters:
            - `item`: an item that was stored in `self.nodes_to_annotations`;
              will be a frozen goal or a frozen pending clause.

        :returntype:
            returns a :class:`etb.datalog.graph.Annotation`
        """
        if item in self.nodes_to_annotations:
            return self.nodes_to_annotations[item]
        else:
            return None

    def get_annotations_of_children(self, item):
        """
        Get a list of the annotations of the children of this item (1
        annotation per child).

        :parameters:
            - `item`: an item that was stored in `self.nodes_to_annotations`;
              will be a frozen goal or a frozen pending clause.

        :returntype:
            a list of :class:`etb.datalog.graph.Annotation` instances

        """
        children = self.get_children(item)
        annotations = map(self.get_annotation, children)
        return annotations

    def get_annotations_of_parents(self, item):
        """
        Get a list of the annotations of the parents of this item (1
        annotation per parent).

        :parameters:
            - `item`: an item that was stored in `self.nodes_to_annotations`;
              will be a frozen goal or a frozen pending clause.

        :returntype:
            a list of :class:`etb.datalog.graph.Annotation` instances

        """
        parents = self.get_parents(item)
        annotations = map(self.get_annotation, parents)
        return annotations
        

    def get_subgoal_annotation(self, node):
        """
        Each node in the dependency graph has at most 1 child that is a goal.
        This function returns the annotation for that child goal of node.

        :parameters:
            - `node`: a node in the graph (an frozen internal representation of
              a goal or a pending rule)

        :returntype:
            a :class:`etb.datalog.graph.Annotation` or `None` if the node does
            not have a child that is a goal.
        """
        annotations_children = self.get_annotations_of_children(node)
        for child in annotations_children:
            if child.is_goal(self):
                return child
        return None

    def get_subgoal_index(self, node):
        """
        Get the `subgoalindex` field of the
        :class:`etb.datalog.graph.Annotation` corresponding to the `node`.

        :parameters:
            - `node`: the node in the graph for which we want the
              `subgoalindex`.

        :returntype:
            a positive integer or `None` when there is no corresponding
            annotation for the `node` parameter
        """
        goal_annotation = self.get_annotation(node)
        if goal_annotation:
            return goal_annotation.subgoalindex
        else:
            return None

    def update_tau(self, node, node_annotation):
        """
        Updates the `tau` dictionary for the `node`. Defined as in the closing
        algorithm specification.
        """
        if node not in self.tau:
            self.tau[node] = {}
        for h, h_annot in self.nodes_to_annotations.iteritems():
            if h_annot and h_annot.is_goal() and h_annot.index <= node_annotation.index:
                tau_g_h = None
                for h_prime in node_annotation.gT:
                    h_prime_annotation = self.get_annotation(h_prime)
                    if (h_prime_annotation and
                        (h_prime_annotation.status == Annotation.CLOSED or h_prime_annotation.status == Annotation.COMPLETED) and
                        node_annotation.gT[h_prime] and
                        h in h_prime_annotation.gD and
                        h_prime_annotation.gD[h] is not None):
                        if tau_g_h is None:
                            tau_g_h = h_prime_annotation.gD[h]
                        else:
                            tau_g_h = min(tau_g_h, h_prime_annotation.gD[h])

                self.tau[node][h] = tau_g_h

    def has_subgoal(self, node):
        """Determine whether the node has a subgoal (whether a child of a node
        is a goal).

        :parameters:
            - `node`: the node in the graph for which we want to know whether
              it has a child that is a goal

        :returntype:
            `True` or `False`
        """
        annotations_children = self.get_annotations_of_children(node)
        for sub in annotations_children:
            if sub.is_goal():
                return True
        return False


    def can_close_to_goal_be_applied(self, node, annotation_node):
        """
        Determines whether the closing operation can be applied to this `node`.
        Defined as in the closing algorithm specification.

        :parameters:
            - `node`: the node for which you want to know whether you can
              apply the closing operation to it
            - `annotation_node`: the corresponding
              :class:`etb.datalog.graph.Annotation` of that node

        :returntype:
            `True` or `False`
        """

        # 1:
        if not annotation_node.status == Annotation.RESOLVED and not annotation_node.status == Annotation.CLOSED and not annotation_node.status == Annotation.COMPLETED:
            
            return False

        annotations_children = self.get_annotations_of_children(node)
        # subgoal has been set:
        for j in annotations_children:
            if len(j.item) > 1 and not self.has_subgoal(j.item):
                return False
        # 2
        for h, h_annotation in self.nodes_to_annotations.iteritems():
            gTh = []
            if h in annotation_node.gT:
                gTh = annotation_node.gT[h]

            index_h_smaller_than_node = False
            if h_annotation.index <= annotation_node.index:
                index_h_smaller_than_node = True

            h_closed = False
            if h_annotation.status == Annotation.COMPLETED or (h_annotation.status == Annotation.CLOSED and ((not h_annotation.gUnclosed) or h_annotation.gUnclosed <= annotation_node.index)):
                h_closed = True

            if gTh and not index_h_smaller_than_node and not h_closed:
                return False

            #if index_h_smaller_than_node and h_closed:
            for j in gTh:
                frozen_j = model.freeze(j)
                annotation_j = self.get_annotation(frozen_j)
                if annotation_j:
                    if not annotation_j.subgoalindex == len(h_annotation.claims):
                        return False
                    children_j = self.get_annotations_of_children(frozen_j)
                    for j_prime in children_j:
                        if j_prime.is_pending_clause():
                            if not len(j_prime.item) == 1 and not self.has_subgoal(j_prime.item):
                                return False
                else:
                    return False
        return True

    def recompute_unclosed(self, node, annotation_node):
        """
        Recomputes the set of unclosed goals.
        Defined as in the closing algorithm specification.

        :parameters:
            - `node`: the node for which you want to recompute the `Unclosed`
              set
            - `annotation_node`: the corresponding
              :class:`etb.datalog.graph.Annotation` of that node

        :returntype:
            `None`

        """
        max_h_so_far = None
        gD = annotation_node.gD
        for h in gD:
            gDh = gD[h]
            h_annot = self.get_annotation(h)
            if gDh:
                if (not max_h_so_far) or max_h_so_far.index < h_annot.index:
                    max_h_so_far = h_annot.index
        annotation_node.gUnclosed = max_h_so_far


    def close_goal(self, node, annotation_node):
        """
        Try to close the goal `node`.
        Defined as in the closing algorithm specification.

        :parameters:
            - `node`: the node you want to close
            - `annotation_node`: the corresponding
              :class:`etb.datalog.graph.Annotation` of that node

        :returntype:
            `None`

        """
        if self.can_close_to_goal_be_applied(node, annotation_node):
            self.update_tau(node, annotation_node)

            if node in self.tau and node in self.tau[node] and (not self.tau[node][node] or self.tau[node][node] == len(annotation_node.claims)):
                # self.log.info('graph.close_goal 1: setting {0}: CLOSED'
                #               .format(self.state.engine.term_factory.close_literal(node)))
                annotation_node.status = Annotation.CLOSED
                if self.state.SLOW_MODE:
                    self.log.debug('Closed goal with index %s as tau(g)(g) is empty', annotation_node.index)
                    time.sleep(self.state.SLOW_MODE)
                self.close_node(node, annotation_node)
            else:
                annotation_node.status = Annotation.RESOLVED

    def close_node(self, node, annotation_node):
        gd_everywhere_undefined = True
        
        for h, h_annot in self.nodes_to_annotations.iteritems():
            if h_annot and h_annot.is_goal() and h_annot.index < annotation_node.index:
                if h in annotation_node.gT and annotation_node.gT[h] and not (h_annot.status == Annotation.CLOSED or h_annot.status == Annotation.COMPLETED):
                    if self.tau[node][h] is None:
                        annotation_node.gD[h] = len(h_annot.claims)
                    else:
                        annotation_node.gD[h] = min(len(h_annot.claims), self.tau[node][h])
                    gd_everywhere_undefined = False
                else:
                    if h in self.tau[node] and self.tau[node][h]:
                        if not (h_annot.status == Annotation.CLOSED or h_annot.status == Annotation.COMPLETED):
                            annotation_node.gD[h] = self.tau[node][h]
                            gd_everywhere_undefined = False
                        else:
                            annotation_node.gD[h] = None
                    else:
                        annotation_node.gD[h] = None
        if gd_everywhere_undefined:
            self.transitively_complete(node, annotation_node)
        else:
            self.recompute_unclosed(node, annotation_node)

    def transitively_complete(self, node, annotation_node):
        annotation_node.status = Annotation.COMPLETED
        for h in annotation_node.gT:
            h_annot = self.get_annotation(h)
            if not h_annot.status == Annotation.COMPLETED:
                self.transitively_complete(h, h_annot)

    def close(self):
        """
        Sweep through all nodes in the graph (from highest to lowest index),
        and perform close rule.  Defined as in the closing algorithm
        specification.

        :returntype:
            `None`
        """
        with self:
            if not self.inferencing_clear:
                self.condition.wait(30)
            goal_nodes = [n for n in self.nodes_to_annotations.items() if isinstance(n[0][0], int)]
            sorted_highest_index_first = sorted(goal_nodes, key=lambda item: item[1].index, reverse=True)
            for item in sorted_highest_index_first:
                node = item[0]
                self.close_goal(node, item[1])

    def is_immediate_subgoal(self, node1_annotation, node2_annotation):
        """
        Test whether `node1_annotation` is the annotation of an immediate
        subgoal of the node described by `node2_annotation`.

        :parameters:
            - `node1_annotation`: the annotation of the presumed goal child of the
              node corresponding to `node2_annotation`.
            - `node2_annotation`: the annotation of the presumed parent of the
              node corresponding to `node1_annotation`.

        :returntype:
            `True` or `False`

        """
        children = self.get_annotations_of_children(node2_annotation.item)
        if not children:
            return False
        else:
            for child in children:
                children_child = self.get_annotations_of_children(child)
                if not children_child:
                    continue
                else:
                    for c in children_child:
                        if c.is_goal():
                            if c == node1_annotation.item:
                                return True
                            else:
                                break
            return False

    def complete(self):
        """
        Mark nodes as complete.  Defined as in the closing algorithm
        specification.

        :returntype:
            `None`
        """
        with self:
            if not self.inferencing_clear:
                self.condition.wait(4)
            self.log.debug("Engine completion called, {0} nodes"
                           .format(len(self.nodes_to_annotations)))
            for node, annotation in self.nodes_to_annotations.iteritems():
                if not self.state.no_stuck_subgoals(node):
                    continue
                if annotation.status == Annotation.CLOSED:
                    everywhere_undefined = True
                    for h in self.nodes_to_annotations:
                        if h in annotation.gD and annotation.gD[h]:
                            everywhere_undefined =  False
                            break
                    if everywhere_undefined:
                        # self.log.info('graph.complete 1: {0} COMPLETED'
                        #               .format(self.state.engine.term_factory.close_literal(node)))
                        annotation.status = Annotation.COMPLETED
                        self.log.debug('Considering node with index %s COMPLETE', annotation.index)
                        if self.state.SLOW_MODE:
                            self.log.debug('Completed goal with index %s as g.D(h) is undefined everywhere', annotation.index)
                            time.sleep(self.state.SLOW_MODE)
                        continue

                    for h, h_annot in self.nodes_to_annotations.iteritems():
                        if h_annot and self.is_immediate_subgoal(annotation, h_annot) and h_annot.status == Annotation.COMPLETED:
                            # self.log.info('graph.complete 2: {0} COMPLETED'
                            #               .format(self.state.engine.term_factory.close_literal(h)))
                            annotation.status = Annotation.COMPLETED
                            self.log.debug('Considering node with index %s COMPLETE', annotation.index)
                            if self.state.SLOW_MODE:
                                self.log.debug('Completed goal with index %s as it has a completed immediate supergoal', annotation.index)
                                time.sleep(self.state.SLOW_MODE)
                            continue

            self.log.debug("Engine completion done")

    def close_and_complete(self):
        """
        First close then complete.

        .. seealso::
            - :func:`etb.datalog.graph.DependencyGraph.close`
            - :func:`etb.datalog.graph.DependencyGraph.complete`
        """
        self.close()
        self.complete()

    def is_completed(self, goal):
        """
        Verify whether the `goal` is completed; this assumes at least 1 run of
        both

            - :func:`etb.datalog.graph.DependencyGraph.close`, and
            - :func:`etb.datalog.graph.DependencyGraph.complete`

        :parameters:
            - `goal`: an internal goal representation

        :returntype:
            `True` or `False`

        """
        frozen = model.freeze(goal)
        annotation = self.get_annotation(frozen)
        if annotation:
            return annotation.status == Annotation.COMPLETED
        else:
            return False

    def add_claim(self, goal, claim):
        """
        Add a claim to the goal in the graph. This updates the `claims` field
        for an :class:`etb.datalog.graph.Annotation` corresponding to `goal
        This updates the `claims` field for an
        :class:`etb.datalog.graph.Annotation` corresponding to `goal`.

        :parameters:
            - `goal`: the internal representation of the goal to which the
              matching claim should be added
            - `claim`: the internal representation of a claim literal that
              should be added to the `goal`

        :returntype:
            `None`
        """
        frozen = model.freeze(goal)
        annotation_goal = self.get_annotation(frozen)
        if not annotation_goal:
            # create annotation if not existing yet
            self.add_goal(goal)
            annotation_goal = self.get_annotation(frozen)

        if claim not in annotation_goal.claims:
            if False: #goal == [1, -1, -2, 3]:
                import traceback
                traceback.print_stack()
            annotation_goal.claims.append(claim)


    def __node_is_present(self, node):
        return node in self.nodes_to_annotations

    def add_node(self, node):
        """
        Add a node to the graph.

        :parameters:
            - `node`: a node in the dependency graph

        :returntype:
            `None`


        """
        if not node in self.graph:
            self.graph[node] = []
            self.parents[node] = []

    def add_edge(self, from_node, to_node):
        """
        Add an edge to the graph.

        :parameters:
            - `from_node`: a node in the dependency graph (the start of the
              edge)
            - `to_node`: a node in the dependency graph (the end of the
              edge)

        :returntype:
            `None`
        """
        self.add_node(from_node)
        self.add_node(to_node)
        self.graph[from_node].append(to_node)
        self.parents[to_node].append(from_node)

    def get_children(self, node):
        """
        Return the children of `node`.

        :parameters:
            - `node`: a node in the dependency graph

        :returntype:
            - a list of nodes

        """
        if node in self.graph:
            return self.graph[node]
        else:
            return []

    def get_parents(self, node):
        """
        Return the parents of `node`.

        :parameters:
            - `node`: a node in the dependency graph

        :returntype:
            - a list of parent nodes

        """
        if node in self.parents:
            return self.parents[node]
        else:
            return []
            
    def external_form(self, node):
        """
        Gets the external form of node, mostly for debugging printouts.
        """
        if isinstance(node[0], int):
            return self.state.engine.term_factory.close_literal(node)
        else:
            return self.state.engine.term_factory.close_literals(node)
            
