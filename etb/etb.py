""" Evidential Tool Bus (ETB)

This module defines the class :class:`etb.ETB`, instances of which are ETB
nodes.

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

import base64
import codecs
import logging
import os
import platform
import re
import threading
import traceback
import uuid
from queue import Empty, Queue

from . import git_interface, interpret_state, networking, terms, utils, wrapper
from .datalog import engine


class ETB(object) :
    '''
    An ETB node.

    We have:
    - Two pools of threads for running tasks
    - an event thread
    - a thread serving xmlrpc requests

    The node maintains:
    - a logic state (claims + rules)
    - an interpret state (tool wrappers)
    - a git repository
    '''

    def __init__(self, etbconfig):
        """
        Create an ETB node based on `etbconfig` (see :class:`etb.ETBConfig`)

        :parameters:
            - `etbconfig`: An instance of :class:`etb.ETBConfig`

        :members:
        
            - `self.config`: the etbconfig parameter
            - `self.log`: the object used for logging Engine related messages
            - `self.interpret_state`: an instance of :class:`etb.InterpretState`
            - `self.engine`: an instance of :class:`etb.datalog.engine.Engine`
            - `self.etb_dir`: the directory etbd was started in - used
               for `put_file` from wrappers
            - `self.git`: an instance of :class:`etb.git_interface.ETBGIT`
            - `self.cron`: an instance of :class:`etb.utils.CronJob`
            - `self.short_pool`: an instace of :class:`etb.utils.ThreadPool`
               for quick tasks
            - `self.long_pool`: an instace of :class:`etb.utils.ThreadPool`
               for potentially long tasks, e.g., wrappers
            - `self.task_worker`: an instance of :class:`etb.TaskWorker`,
               the main ETB thread for this node
            - `self.networking`: an instance of :class:`etb.networking.Networking`,
               providing the XML-RPC API
            - `self.subscriptions`: a set of goals this node is subscribed to
            - `self.active_local_queries`: the set of active local queries
            - `self.active_remote_queries`: the set of active remote queries
        """
        self.config = etbconfig
        #logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s %(process)d/%(threadName)s: %(message)s")
        self.log = logging.getLogger('etb')

        # Save the starting ETB directory (usually also the etbsh directory)
        # This is used by wrappers using get_file.
        self.etb_dir = os.getcwd()

        self._rlock = threading.RLock()

        # We set up the ETB filesystem and move to its root
        # Rules and wrappers will be imported, and read from the
        # Git working directory.
        self.git = git_interface.ETBGIT(self.config.git_dir)
        os.chdir(self.git.git_dir)

        # This will add/update the 'rules' and 'wrappers' directories in Git
        changed = self.add_rules_and_wrappers_to_git()

        # Create interpret_state
        self.interpret_state = interpret_state.InterpretState(self)
        self.interpret_state.load_wrappers()

        # Start the engine
        self.engine = engine.Engine(self.interpret_state)

        # to run tasks periodically (also used by networking)
        self.cron = utils.CronJob(self, period=self.config.cron_period)
        # self.cron.onIteration.add_handler(self.update_done_queries)

        # different threads/thread pools
        self.short_pool = utils.ThreadPool(self)     # for quick tasks
        self.long_pool = utils.ThreadPool(self)      # for long running tasks
        self.task_worker = TaskWorker(self, daemon=True)    # main etb thread

        # networking component using xml-rpc
        self.networking = networking.Networking(self, self.config.port)

        # goals we subscribed to
        self.subscriptions = set()

        self.engine.load_default_rules()

        # Now load the logic_file
        if not changed:
            self.engine.load_logic_file()

        # queries
        self._queries = {}
        self._done_queries = {}
        self.active_local_queries = set()
        self.active_remote_queries = {}

        import atexit
        atexit.register(self.stop)

    def add_rules_and_wrappers_to_git(self):
        """Adds the rules and wrappers to the Git repository.
        Returns True if the rules or wrappers are not the same as current
        """
        rules_dir = self.config.rules_dir
        wrappers_dir = self.config.wrappers_dir
            
        # Basically just want to copy from the rules_dir to the Git repo under rules
        # Which is where rules will be loaded from
        if os.path.exists(rules_dir):
            rchanged = self.git.put_dir(rules_dir, 'rules')
        else:
            rchanged = self.git.clear_dir('rules')
        # Similarly for wrappers
        if os.path.exists(wrappers_dir):
            wchanged = self.git.put_dir(wrappers_dir, 'wrappers')
        else:
            wchanged = self.git.clear_dir('wrappers')
        if rchanged:
            if wchanged:
                self.log.info('Rules and wrappers have changed, claims will be cleared')
            else:
                self.log.info('Rules have changed, claims will be cleared')
        elif wchanged:
            self.log.info('Wrappers have changed, claims will be cleared')
        return rchanged or wchanged

    def save_logic_file(self):
        self.engine.save_logic_file() 
        self.git.register('etb_logic_file')

    def stop(self):
        """Stop all components and all threads. May block if some
        thread does not stops gracefully.
        """
        self.log.info("stop ETB instance...")
        # save state
        self.log.debug("save ETB state")
        self.save_logic_file()
        # stop components
        self.log.debug("stop cron thread")
        self.cron.stop()
        self.log.debug("stop short tasks pool")
        self.short_pool.stop()
        self.log.debug("stop long tasks pool")
        self.long_pool.stop()
        self.log.debug("stop networking")
        self.networking.stop()
        self.log.debug("stop main ETB task worker")
        self.task_worker.stop()

    @property
    def id(self):
        return self.networking.id

    def __repr__(self):
        return "ETB(id={0})".format(self.id)

    def __enter__(self):
        """open lock context"""
        self._rlock.acquire()

    def __exit__(self, t, v, tb):
        """close lock context"""
        self._rlock.release()

    def __eq__(self, other):
        return isinstance(other, ETB) and self.id == other.id

    def __hash__(self):
        return hash(self.id)

    def add_tool(self, tool):
        self.interpret_state.add_tool(tool)

    def add_rule(self, rule):
        self.engine.add_rule(rule)

    def create_query(self, goals):
        '''
        Create a new query.
        '''
        query = goals                       
        qid = uuid.uuid4().get_hex()
        self.log.debug("create_query: %s %s" % (query, qid))
        with self:
            self._queries[qid] = query
            self.schedule_query(qid, query)
        return qid

    def create_proof_query(self, goals):
        '''
        Create a new proof query.
        '''
        query = goals
        qid = uuid.uuid4().get_hex()
        with self:
            self._queries[qid] = query
            self.schedule_query(qid, query)
        return qid
    
    def schedule_query(self, qid, query):
        def task(etb, qid=qid, query=query):
            for goal in query:
                self.engine.add_goal(goal) 
            with etb:
                etb._done_queries[qid] = query
                del etb._queries[qid]
        self.long_pool.schedule(task)

    def get_query(self, qid):
        """
        Get the query object associated with this query id. 
        Returns None if not found.
        """
        with self:
            return self._queries.get(qid, None) or \
                self._done_queries.get(qid, None)

#    #old version. needs a port to etb3
#    def query_derivation(self, qid, f):
#        self.log.info("in query_derivation")
#        query = self.get_query(qid)
#        if not query:
#            return False
#        claims = list(query.answer_facts())
#        return self.engine.claims_to_dot(claims, f)

#    #old version. needs a port to etb3
#    def query_proof(self, qid, f):
#        self.log.info("in query_proof")
#        query = self.get_query(qid)
#        if not query:
#            return False
#        claims = list(query.answer_facts())
#        return self.engine.claims_to_dot(claims, f, proof=True)

    #old version. needs a port to etb3
    def fact_explanation(self, fact, f):
        self.log.debug("in query_explanation of etb")
        # only deal with queries that contain 1 goal
        self.engine.to_dot(fact, f)

    def update_predicates(self, newpreds):
        self.engine.check_stuck_goals(newpreds)

    def clear_claims_table(self):
        """Totally clear the content of the engine and interpret_state.
        All rules, claims, and already interpreted goals are erased.
        This is NOT reversible.
        """
        self.log.info('reset ETB state')
        self.engine.reset()
        self.interpret_state.reset()

    @property
    def queries(self):
        return list(self._queries.keys())

    @property
    def done_queries(self):
        return list(self._done_queries.keys())
    
    def query_answers(self, qid):
        """Returns the current list of answers for the given query. (list
        of substitutions and ground claims).
        """
        query = self.get_query(qid)
        self.log.debug("in query_answers %s of type %s" % (query, type(query)))
        if query:
            goal = query[0]
            self.log.debug("goal: %s of type %s" % (goal, type(goal)))
            substs =  self.engine.get_substitutions(goal)
            self.log.debug("substitutions: %s" % substs)
            substs = sorted(substs)
            claims = self.engine.get_claims_matching_goal(goal)
            self.log.debug("claims: %s" % claims)
            claims = sorted(claims)
            return { 'substs' : substs,  'claims' : claims }
        else:
            self.log.error('No query found for {0}'.format(qid))

    def all_claims(self):
        self.log.debug("in all_claims")
        return self.engine.get_claims()

    def find_claims(self, test, reasons=False):
        """Find claims satisfying test.
        If test is a string, it is taken as an re pattern.
        Otherwise, it is expected to be a callable of """
        if isinstance(test, str):
            pat = test
            # If need to convert to raw, use pat.encode('string-escape')
            self.log.debug('find_claims: pat = {0}: {1}, {2}'.format(pat, type(pat), len(pat)))
            claims = self.all_claims()
            mclaims = []
            for claim in claims:
                match = re.search(pat, str(claim))
                if match is not None:
                    if reasons:
                        mclaims.append(claim)
                    else:
                        mclaims.append(claim.literal)
            #sorted(mclaims, key=str)
            return sorted(mclaims)
        elif callable(test):
            import inspect
            argspec = inspect.getargspec(test)
            if len(argspec.args) == 2:
                mclaims = []
                for claim in self.all_claims():
                    pred = claim.literal.val.to_python()
                    args = [a.to_python() for a in claim.literal.args]
                    if test(pred, args):
                        if reasons:
                            mclaims.append(claim)
                        else:
                            mclaims.append(claim.literal)
                return sorted(mclaims)
            else:
                raise Exception('find_claims: bad function, takes arguments (pred, args)')

#    #old version. needs a port to etb3
#    def proofs(self, qid):
#        query = self.get_query(qid)
#        query.proof()
        
    @property
    def load(self):
        """Estimate load of this node (length of long_pool.queue?)"""
        return 42

    def error(self, msg) :
        "log the error and then fail (raise an exception)"
        self.log.error(msg)
        assert False, msg

    def interpret_goal_somewhere(self, goal, internal_goal):
        """Interpret the goal on some node, possibly this one."""
        pred = goal.first_symbol()
        self.log.debug('Looking to interpret %s somewhere.' % pred)
        candidates = self.networking.neighbors_able_to_interpret(pred)
        link = False
        if not candidates:
            candidates = self.networking.links_able_to_interpret(pred)
            link = True
            if not candidates:
                self.error("no node able to interpret goal {0}".format(goal))

        argspecstr = candidates[0].predicates[str(pred.val)]
        argspecs = wrapper.ArgSpec.parse(argspecstr)
        if len(argspecs) != len(goal.args):
            self.error(
                "Have %d argspecs, expect %d" % (len(argspecs), len(goal.args)))

        handles = []
        for (spec, arg) in zip(argspecs, goal.args) :
            if spec.kind == 'handle':
                handles.append((spec, arg))

        candidates = self.filter_candidates(candidates, goal)
        if not candidates:
            self.error("no node able to interpret goal {0}".format(goal))

        best_node = min(candidates, key=lambda n: n.load)
        # adding internal goal: this needs to be added for remote evaluation
        if best_node.id == self.id :
            self.interpret_state.interpret(goal, internal_goal, sync=True)
            return

        argspecstr = best_node.predicates[str(goal.first_symbol().val)]
        argspecs = wrapper.ArgSpec.parse(argspecstr)
        new_id = uuid.uuid4().get_hex()
        self.active_remote_queries[new_id] = (goal, best_node, argspecs, goal)
        proxy = best_node.proxy
        
        if link:
            self.log.info('Sending %s to remote ETB on %s' % (goal.first_symbol(), best_node.id))
            proxy.interpret_goal_remotely(self.id, terms.dumps(goal), new_id)
        else:
            self.log.info('Asking {0} to interpret {1}.'
                          .format(best_node.id, goal.first_symbol()))
            proxy.interpret_goal(self.id, terms.dumps(goal), new_id)
        
        best_node.increment_load()

    def get_goals_dependencies(self, goal, remote_etb):
        for a in goal.get_args():
            if a.is_ground():
                try:
                    fileref = { 'file' : str(a.get_args()[terms.mk_stringconst('file')]),
                                'sha1' : str(a.get_args()[terms.mk_stringconst('sha1')]) }
                    content = remote_etb.get_file(terms.dumps(a))
                    if content:
                        content = base64.b64decode(content)
                        self.create_file(content, fileref['file'])
                    else:
                        self.log.error('Unable to get remote file: %s', fileref)
                except Exception as e:
                    # Non-fileref will go there
                    pass
            
    def process_interpreted_goal_answer(self, argspecs, goal, node, answer):
        output = []
        for subst in answer['substs']:
            assert isinstance(subst, terms.Subst),\
                'process_interpreted_goal_answer: should be a Subst, {0}: {1}'\
                    .format(subst, type(subst))
            output.append(subst)
        self.log.debug('process_interpreted_goal_answer: about to process claims {0}: {1}'
                       .format(answer['claims'], output))
        for c in answer['claims']:
            assert isinstance(c, terms.Claim),\
                'process_interpreted_goal_answer: should be a Claim, {0}: {1}'\
                    .format(c, type(c))
            output.append(c)
        self.interpret_state._process_output(goal, output)

    def filter_candidates(self, candidates, goal) :
        """Filter candidate nodes by handle information"""
        for arg in goal.args :
            if isinstance(arg, dict) and 'etb' in arg :
                candidates = [ c for c in candidates if c.id == arg['etb'] ]
        return candidates

    def get_file_from_somewhere(self, fileref):
        """
        Given a name and sha1 hash pair, which are not available locally,
        find the corresponding file and copy it to the current directory.
        """
        name = fileref['file']
        sha1 = fileref['sha1']
        contents, execp = self.networking.get_contents_from_somewhere(sha1)
        if contents is None:
            self.log.error('File [{0}, {1}] not found anywhere' . \
                                  format(name, sha1))
            raise
        self.create_file(contents, name, execp)

    #used when a wrapper returns a substitution to fetch the files mentioned there in
    def fetch_support(self, substitution):
        for _,v in substitution.get_bindings():
            if terms.is_fileref(v):
                fileref = terms.get_fileref(v)
                if not self.git.is_local(fileref):
                    self.get_file_from_somewhere(fileref)
            elif terms.is_filerefs(v):
                filerefs = terms.get_filerefs(v)
                for fileref in utils.flatten(filerefs):
                    if not self.git.is_local(fileref):
                        self.get_file_from_somewhere(fileref)

    def create_file(self, contents, filename, execp=False):
        git_name = self.git._make_local_path(filename)
        if platform.system() == 'Windows':
            git_name = '\\'.join(git_name.split('/'))
        else:
            git_name = '/'.join(git_name.split('\\'))
        ndir = os.path.dirname(git_name)
        if ndir != '' and not os.path.isdir(ndir):
            os.makedirs(ndir)
        self.log.debug('Creating %s' % git_name)
        with codecs.open(git_name, mode='wb', errors='ignore') as fd:
            fd.write(contents)
            fd.close()
        if execp:
            self.log.debug('Changing executable permission {}'.format(git_name))
            mode = os.stat(git_name).st_mode
            self.log.debug('Current mode is {}'.format(mode))
            #os.chmod(git_name, mode | stat.S_IXUSR)
            try:
                os.chmod(git_name, 0o755)
                self.log.debug('mode changed to {}'.format(0o755))
            except Error as err:
                self.log.debug('mode change problem {}'.format(err))
                raise err
        return self.git.register(filename)
        
def debug_level_value(value):
    LEVELS = {'debug': logging.DEBUG,
              'info': logging.INFO,
              'warning': logging.WARNING,
              'error': logging.ERROR,
              'critical': logging.CRITICAL}
    if value in LEVELS:
        return LEVELS[value]
    else:
        assert False, 'Invalid debug level: %s' % value

class TaskWorker(threading.Thread):
    """
    The single thread responsible for doing inferences
    and managing internal structures of ETB
    """
    def __init__(self, logger, daemon=True):
        threading.Thread.__init__(self)
        self._stop = False
        self.daemon = daemon
        self._queue = Queue()
        self.start()
        self.log = logging.getLogger('etb.taskworker')

    def run(self):
        """The main loop of processing tasks"""
        while not self._stop:
            try:
                task = self._queue.get(timeout=.2)
                task()
            except Empty:
                pass
            except Exception as e:
                self.log.warning('error in event thread: {0}'.format(e))
                traceback.print_exc()

    def stop(self):
        """Stop the thread and wait for it to terminate"""
        self._stop = True
        self.join()

    def schedule(self, task):
        """Schedule the task to be processed later."""
        self._queue.put(task)
