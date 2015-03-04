""" Module for networking using xml-rpc

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

from __future__ import unicode_literals

import socket
import SocketServer
import SimpleXMLRPCServer
import base64
import os
import logging
import threading
import time
import uuid
import xmlrpclib
import weakref
import codecs, base64
import re
from functools import wraps
import traceback

import terms
import parser

# frequency (in seconds) of 'ping' messages (iam: currently also the period of poke messages)
# PING_FREQUENCY = 25   # set in etbconf.py

# a node becomes invalid after a certain number of failed 'ping'; ditto with links
# NODE_TIMEOUT = 20 * PING_FREQUENCY

def fetch_neighbors(etb):
    """
    Get the list of neighbors of every node, and add them to my own
    list of neighbors.
    """
    for neighbor in list(etb.networking.neighbors):
        def task(etb, neighbor=neighbor):
            """Fetch neighbors task"""
            proxy = neighbor.proxy
            if proxy is not None:
                neighbors = proxy.get_neighbors()
                # parse it as a list
                neighbors = terms.loads(neighbors)
                for nid, hosts, port, timestamp in neighbors:
                    if time.time() - timestamp < etb.config.node_timeout:
                        # the neighbor has been seen recently by someone, it
                        # makes sense to add it (if it's not already known)
                        etb.networking.add_neighbor(nid, port)
                    nbr = etb.networking.neighbor(nid)
                    if nbr:
                        nbr.add_hosts(hosts)
                        # trust the remote node, and use its timestamp
                        nbr.timestamp = timestamp
        etb.short_pool.schedule(task)

def ping_task(etb, neighbor):
    def task(etb, neighbor=neighbor):
        #etb.networking.log.debug('PING')
        if neighbor.proxy is not None:
            predicates = etb.interpret_state.predicates()
            payload = { 'load': etb.load
                      , 'predicates': predicates
                      , 'subscriptions': list(etb.subscriptions)
                      , 'to_hosts': list(neighbor.hosts)
                      , 'tasks': [] #list(etb.active_queries())
                      }
            neighbor.proxy.ping(etb.id, etb.networking.port,
                                neighbor.id, terms.dumps(payload))
    return task

def ping_neighbor(etb, neighbor):
    etb.short_pool.schedule(ping_task(etb, neighbor))

def ping_neighbors(etb):
    """The task of pinging all neighbors."""
    etb.networking.clean_neighbors()
    for neighbor in list(etb.networking.neighbors):
        ping_neighbor(etb, neighbor)

def fetch_new_ids(etb):
    """Get the current ID of all neighbors (may have changed)"""
    for neighbor in list(etb.networking.neighbors):
        def task(etb, neighbor=neighbor):
            proxy = neighbor.proxy
            if proxy is not None:
                nid = proxy.get_id()
                etb.networking.add_neighbor(nid, neighbor.port)
        etb.short_pool.schedule(task)

def poke_link(etb, link):
    etb.short_pool.schedule(poke_task(etb, link))

def poke_links(etb):
    """The task of poking all links."""
    etb.networking.clean_links()
    for link in list(etb.networking.links):
        poke_link(etb, link)

#iam: may need to add accoutrements as desired
def poke_task(etb, link):
    def task(etb, link=link):
        #etb.networking.log.debug('POKE')
        if link.proxy is not None:
            predicates = etb.networking.link_predicates()
            if link.remote_name is None:
                link.proxy.poke(etb.id, link.port, link.my_port, link.id, predicates)
            else:
                link.proxy.proxypoke(etb.id, link.proxy_host, link.port, link.local_name, link.remote_name, link.id, predicates)
    return task


class ETBNode(object):
    """Stub representing another ETB node over the network."""

    def __init__(self, logger, nid, port, timeout):
        self.id = nid
        self.log = logger
        self.hosts = set(())
        self.port = port
        self.my_port = None # Allow specific port to be used (e.g. for tunnelling)

        self.proxy_host = None  #used with proxying (unique rather than a list); 
        self.remote_name = None #used with proxying; essentially a url path
        self.local_name = None  #used with proxying; essentially a url path

        self._rlock = threading.RLock()

        self.load = 0
        self.predicates = set()
        self.subscriptions = set()
        self._proxy = None
        self._timestamp = time.time() - 2 * timeout  # expect it to be old

    def __eq__(self, other):
        return isinstance(other, ETBNode) and self.id == other.id

    def __repr__(self):
        with self._rlock:
            hosts = ';' . join(repr(host) for host in self.hosts)
        return "ETBNode(id={0}, hosts={1}, port={2}, my_port={3})" . \
            format(self.id, hosts, self.port, self.my_port)

    def __hash__(self):
        return hash(self.id)

    @property
    def timestamp(self):
        """Return the timestamp"""
        with self._rlock:
            return self._timestamp

    @timestamp.setter
    def timestamp(self, tme):
        """Set the timestamp"""
        with self._rlock:
            self._timestamp = max(tme, self._timestamp)

    @property
    def has_timeout(self):
        """
        Is the last time we had contact with this server too far in the past?
        """
        with self._rlock:
            return time.time() - self._timestamp >= NODE_TIMEOUT

    def add_host(self, host):
        """Add an IP (or hostname) corresponding to this node"""
        with self._rlock:
            self.hosts.add(host)

    def add_hosts(self, hosts):
        """Add several IP to this node"""
        with self._rlock:
            self.hosts.update(hosts)

    def touch(self):
        """we just had contact with this node, refresh timestamp"""
        with self._rlock:
            self._timestamp = time.time()

    def increment_load(self):
        """Increment the (estimate) load of the node, e.g.
        just after we schedule a goal interpretation on this node.
        """
        with self._rlock:
            self.load += 1

    @property
    def proxy(self):
        """Get a proxy of this host, to call methods via XML-RPC."""
        retval = None
        with self._rlock:
            hosts = tuple(self.hosts)
        for host in hosts:
            try:
                if self.remote_name is None:
                    uri = "http://{host}:{port}" . format(host=host, port=self.port)
                else:
                    uri = "http://{host}:{port}/{name}" . format(host=host, port=self.port, name=self.remote_name)
                proxy = xmlrpclib.ServerProxy(uri)
                proxy.test()
                if proxy.get_id() == self.id:
                    retval = proxy
                    break
                else:
                    pass
            except Exception as e:
                pass
        if retval is None:
            if self.remote_name is None:
                self.log.warning('Could not connect to host (%s):%s',
                                 ', '.join(self.hosts), self.port)
            else:
                self.log.warning('Could not connect to host (%s):%s/%s',
                                 ', '.join(self.hosts), self.port, self.remote_name)


        return retval 


class WithIpHandler(SimpleXMLRPCServer.SimpleXMLRPCRequestHandler):
    """Handler that put the incoming IP in the thread local storage"""
    def __init__(self, request, client_address, server):
        threading.current_thread().ip = client_address[0]
        SimpleXMLRPCServer.SimpleXMLRPCRequestHandler.__init__(
            self, request, client_address, server)

# def _export(method):
#     """Decorator for functions that are exported through xmlrpc."""
#     method._etb_export = True
#     return method

def _export(method):
    """Decorator for functions that are exported through xmlrpc."""
    method._etb_export = True
    @wraps(method)
    def _method(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except:
            traceback.print_exc()
            raise
    return _method

class Networking(SocketServer.ThreadingMixIn,
                 SimpleXMLRPCServer.SimpleXMLRPCServer):
    """
    XMLRPC server part of the ETB. This component is responsible for
    managing connexions with peers, and exposing an RPC interface.
    """
    def __init__(self, etb, port):
        self.etb = etb
        self.log = logging.getLogger('etb.networking')

        self.port = int(port)
        self._id = uuid.uuid4().get_hex()
        self._hosts = set(()) # list of IPs
        self._neighbors = {}
        #new two way links
        self._links = {}

        self._rlock = threading.RLock()

        try:
            SimpleXMLRPCServer.SimpleXMLRPCServer.__init__(
                self, ("", self.port),
                requestHandler=WithIpHandler, logRequests=False)
        except socket.error as e:
            self.log.error('Error: port {0} is already in use'.format(self.port))
            os._exit(1)

        self.log.info('ETB node with ID %s', self.id)
        self.log.info('    listening on port %s', self.port)

        self.register_introspection_functions()
        for fun in self.public_functions:
            self.register_function(fun)

        self.etb.cron.onIteration.add_handler(ping_neighbors)
# iam: needs to be implemented
        self.etb.cron.onIteration.add_handler(poke_links)
        self.etb.cron.onIteration.add_handler(fetch_neighbors)
        self.etb.cron.onIteration.add_handler(fetch_new_ids)

        self.on_new_claim = weakref.WeakSet()

        self.thread = threading.Thread(target=self.serve_forever)
        self.thread.daemon = True
        self.thread.start()

        self.ping(self._id, self.port, self._id)

    def stop(self):
        """Stops the component."""
        self.shutdown()

    @property
    def id(self):
        """Returns this node's ID"""
        return self._id

    @property
    def public_functions(self):
        """List of public functions, exposed on the network via XML-RPC"""
        all_methods = self.__class__.__dict__.values()
        return [ getattr(self,m.__name__)
                 for m in all_methods if getattr(m,'_etb_export', False) ]

    def _get_incoming_ip(self):
        """Reads the incoming IP using thread local storage"""
        return getattr(threading.current_thread(), 'ip', 'localhost')
    
    @_export
    def test(self):
        """Just used to test a connection (returns True)"""
        return True
    
    ##### Neighbors operations
    
    def add_neighbor(self, nid, port):
        """Add this node as a new neighbor."""
        new_node = False
        with self._rlock:
            if nid not in self._neighbors:
                node = ETBNode(self.log, nid, port, self.etb.config.node_timeout)
                self._neighbors[nid] = node
                new_node = True
            else:
                node = self._neighbors[nid]
            assert node is not None, 'node is None in add_neighbor'
        if new_node:
            self.log.info('Connected to ETB node: %s' % nid)
            ping_neighbor(self.etb, node)

    def is_neighbor(self, nid):
        """Checks whether this id corresponds to a known neighbor."""
        with self._rlock:
            return nid in self._neighbors and not self._neighbors[nid].has_timeout

    def neighbor(self, id, default=None):
        """Get the neighbor by its id"""
        with self._rlock:
            return self._neighbors.get(id, default)

    def neighbors_able_to_interpret(self, pred):
        """Return the list of neighbors that have expressed
        that they are able to interpret these kind of goals
        (based on the predicate symbol)
        """
        with self._rlock:
            neighbors = self._neighbors.values()
        return [n for n in neighbors if str(pred.val) in n.predicates]

    def load_of(self, id):
        """Get the (estimate) load of the node with given ID."""
        if id == self.id:
            return self.etb.load
        with self._rlock:
            node = self.neighbor(id)
            assert node, 'Node is bad in load_of'
            return node.load

    def clean_neighbors(self):
        """Remove from the neighbors table all the ones that are too
        old by their timestamp."""
        with self._rlock:
            alive_nodes = [node for node in self.neighbors \
                if not node.has_timeout]
            timeouted = set(self.neighbors) - set(alive_nodes)
            self._neighbors = dict((node.id, node) for node in alive_nodes)
        for id in timeouted:
            self.log.debug('Timeout contacting neighbor {0}' . format(id))

    @property
    def neighbors(self):
        "get the current list of neighbors"
        with self._rlock:
            return list(self._neighbors.values())

    #### new link operations (iam: TODO -- fair bit of code duplication b/w link code and neigbor code,
    ####  refactor maybe once they get settled)

    def add_link(self, nid, to_port, my_port, predicates):
        """Add this node as a new tunnel link."""
        new_node = False
        with self._rlock:
            if nid not in self._links:
                node = ETBNode(self.log, nid, to_port)
                node.my_port = my_port
                node.add_host('localhost')
                node.predicates = terms.loads(predicates) if predicates else {}
                self._links[nid] = node
                new_node = True
            else:
                node = self._links[nid]
                assert node is not None, 'Node is None in add_link'
        if new_node:
            self.log.debug('Connected to tunnel ETB node: %s' % nid)
            self.log.debug('node = %s' % node)
            poke_link(self.etb, node)

    def add_proxy_link(self, nid, proxy_host, proxy_port, proxy_name, local_name, predicates):
        """Add this node as a new proxy link."""
        new_node = False
        with self._rlock:
            if nid not in self._links:
                node = ETBNode(self.log, nid, proxy_port)
                node.add_host(proxy_host)
                node.proxy_host = proxy_host
                node.remote_name = proxy_name
                node.local_name = local_name
                node.predicates = terms.loads(predicates) if predicates else {}
                self._links[nid] = node
                new_node = True
            else:
                node = self._links[nid]
                assert node is not None, 'Node is None in add_proxy_link'
        if new_node:
            self.log.debug('Connected to proxied ETB node: %s' % nid)
            self.log.debug('node = %s' % node)
            poke_link(self.etb, node)

    def clean_links(self):
        """Remove from the links table all the ones that are too
        old by their timestamp."""
        with self._rlock:
            alive_nodes = [node for node in self.links \
                if not node.has_timeout]
            timeouted = set(self.links) - set(alive_nodes)
            self._links = dict((node.id, node) for node in alive_nodes)
        for id in timeouted:
            self.log.debug('Timeout contacting link {0}' . format(id))

    @property
    def links(self):
        "get the current list of links"
        with self._rlock:
            return list(self._links.values())

        
    def is_link(self, nid):
        """Checks whether this id corresponds to a linked node."""
        with self._rlock:
            return nid in self._links and not self._links[nid].has_timeout

    def get_link(self, id, default=None):
        """Get the link by its id"""
        with self._rlock:
            return self._links.get(id, default)

    ##### Basic connectivity: connect <-> ping, tunnel <-> poke

    @_export
    def get_id(self):
        """Returns one's own id."""
        return self.id
    
    ### ping/connect
    
    @_export
    def ping(self, from_id, from_port, to_id, payload=None):
        """
        Called by a remote node to notify that it is still alive.
        Some additional data may be piggybacked in the payload.
        """
        self.add_neighbor(from_id, from_port)
        node = self.neighbor(from_id)
        payload = terms.loads(payload) if payload else {}
        if node:
            assert isinstance(node, ETBNode), 'node not an ETBNode'
            node.touch()
            ip = self._get_incoming_ip()
            if ip is None:
                return
            node.add_host(ip)
            assert node.port == from_port, "port should not change"
            with node._rlock:
                if 'load' in payload:
                    node.load = int(payload['load'])
                if 'predicates' in payload:
                    if node.predicates != payload['predicates']:
                        node.predicates.clear()
                        node.predicates = payload['predicates']
                        self.log.debug('Adding new predicates')
                        self.etb.update_predicates()
                if 'subscriptions' in payload:
                    node.subscriptions.clear()
                    node.subscriptions.update(payload['subscriptions'])
                if 'to_hosts' in payload:
                    with self._rlock:
                        self._hosts.update(payload['to_hosts'])
        return to_id == self.id

    @_export
    def connect(self, host, port):
        """Ask the node to connect to some (host,port)."""
        host = host.strip('"\'')
        port = port.strip('"\'')
        self.log.debug("Trying to connect to %s:%s", host, port)
        def task(etb, host=host, port=port):
            url = "http://{0}:{1}".format(host, port)
            proxy = xmlrpclib.ServerProxy(url)
            try:
                nid = proxy.get_id()
                proxy.ping(etb.id, self.port, nid)
            except Exception as msg:
                self.log.error('Failed to connect to %s' % url)
                self.log.error(msg)
        self.etb.short_pool.schedule(task)
        return True


    ### two way link via a proxy 

    @_export 
    def proxylink(self, proxy_host, proxy_port, local_name, remote_name):
        """Ask the node to setup a link using the proxy """
        proxy_host = proxy_host.strip('"\'')
        proxy_port = proxy_port.strip('"\'')
        #self.log.info('Trying to proxy through %s:%s   %s <--> %s' % (proxy_host, proxy_port, local_name, remote_name))
        def task(etb, proxy_host=proxy_host, proxy_port=proxy_port, local_name=local_name, remote_name=remote_name):
            self.log.debug('Proxying:  %s:%s   %s <--> %s' % (proxy_host, proxy_port, local_name, remote_name))
            url = "http://{0}:{1}/{2}".format(proxy_host, proxy_port, remote_name)
            proxy = xmlrpclib.ServerProxy(url)
            try:
                nid = proxy.get_id()
                predicates = self.link_predicates()
                proxy.proxypoke(etb.id, proxy_host, proxy_port, local_name, remote_name, nid, predicates)
            except Exception as msg:
                self.log.error('Failed to proxy through %s' % url)
                self.log.error(msg)
        self.etb.short_pool.schedule(task)
        return True
            
    @_export 
    def proxypoke(self, from_id, proxy_host, proxy_port, from_name, to_name, to_id, predicates):
        """Analogous to a ping for proxied links."""
        #self.log.debug("%s under the name of %s being proxypoked by %s with name %s and predicates:\n\t%s" % (self.id, to_name, from_id, from_name, predicates))
        self.add_proxy_link(from_id, proxy_host, proxy_port, from_name, to_name, predicates)
        node = self.get_link(from_id)
        if node is not None:
           node.touch()
        return True
        
        

    ###  two way link (i.e. tunnel) 

    @_export
    def tunnel(self, local_port, remote_port):
        """Ask the node to tunnel via the local_port, remote_port pair."""
        local_port = local_port.strip('"\'')
        remote_port = remote_port.strip('"\'')
        #self.log.info('Trying to tunnel to %s <--> %s' % (local_port, remote_port))
        def task(etb, local_port=local_port, remote_port = remote_port):
             self.log.debug('Tunneling: %s <===> %s' % (local_port, remote_port))
             url = "http://localhost:{0}".format(local_port)
             proxy = xmlrpclib.ServerProxy(url)
             try:
                 nid = proxy.get_id()
                 predicates = self.link_predicates()
                 proxy.poke(etb.id, local_port, remote_port, nid, predicates)
             except Exception as msg:
                 self.log.error('Failed to tunnel to %s' % url)
                 self.log.error(msg)
        self.etb.short_pool.schedule(task)
        return True


    @_export 
    def poke(self, from_id, local_port, remote_port, to_id, predicates):
        """Analogous to a ping for tunnels."""
        #self.log.debug("%s being poked by %s with predicates:\n\t%s" % (self.id, from_id, predicates))
        self.add_link(from_id, remote_port, local_port, predicates)
        node = self.get_link(from_id)
        if node is not None:
            node.touch()
        return True
       
    def link_predicates(self):
        """
        Reveals our ETB network capabilities. Passed as a payload in pokes.
        """
        predicates = self.etb.interpret_state.predicates()
        for n in list(self.neighbors):
            predicates.update(n.predicates)
        response = terms.dumps(predicates)
        #self.log.debug("link_predicates of %s are %s" % (self.id, response))
        return response
    
    def links_able_to_interpret(self, pred):
        """
        Return the list of links that have expressed that they are
        able to interpret this kind of goals (based on the predicate
        symbol)
        """
        with self._rlock:
            links = self._links.values()
        return [n for n in links if str(pred.val) in n.predicates]

    ##### ETB node-to-node communication
    
    @_export
    def answer_query(self, query_id, answer):
        """
        Add an answer to the query. The answer must be a JSON-encoded
        substitution.
        """
        try:
            self.log.debug('Received JSON answer {0}'.format(answer))
            answer = terms.loads(answer)
            self.log.debug('Received answer to %s' % query_id)
            self.log.debug('answer_query: answer = %s' % answer)
            with self.etb._rlock:
                if query_id in self.etb.active_remote_queries:
                    (goal, nid, argspecs, node) = self.etb.active_remote_queries[query_id]
                    self.log.debug('answer_query: goal = {0}: {1}'.format(goal, type(goal)))
                    self.etb.process_interpreted_goal_answer(argspecs, goal, node, answer)
                    del self.etb.active_remote_queries[query_id]
        except:
            return False
        return True

    @_export
    def interpret_goal(self, from_id, goals, query_id):
        """
        Given the goal (a JSON-encoded list of possibly interpret terms),
        schedule it to be interpreted by a tool wrapper and to send back the
        results to from_id.

        Returns True on success, False on failure.
        """
        goals = terms.loads(goals)
        self.log.debug('Asked by %s to interpret %s', from_id, goals)
        def task_interpret(etb, query_id=query_id, goals=goals):
            query = self.etb.create_query((goals,))
            self.query_wait(query)
            if False:
                filename = self.etb.engine.goal_deps_to_png(goals)
                os.rename(filename, "%s.png" % goals)
                self.log.debug("answering_png.png for %s dumped to %s" % (goals, os.getcwd()))
            ans = self.etb.query_answers(query)
            answer = terms.dumps(ans)
            self.log.debug('task_interpret: answer to query is: %s' % answer)
            def task(etb, query_id=query_id, answer=answer):
                if from_id in self._neighbors:
                    proxy = self.neighbor(from_id).proxy
                else:
                    proxy = None
                if proxy is not None:
                    self.log.debug('Sending query answer to %s', from_id)
                    # I don't know why, but at some point the following
                    # started raising the exception printing proxy:
                    #   method "__unicode__" is not supported
                    #self.log.info('proxy for %s is %s' % (from_id, proxy))
                    self.log.debug('_neighbors = %s' % self._neighbors)
                    proxy.answer_query(query_id, answer)
            etb.short_pool.schedule(task)
        self.etb.long_pool.schedule(task_interpret)
        return True

    @_export
    def interpret_goal_remotely(self, from_id, goals, query_id):
        """
        Goal interpretation through a tunnel.
        """
        goals = terms.loads(goals)
        self.log.debug('Remote query: %s for %s' % (goals, from_id))
        node = self.get_link(from_id)
        
        if node is None:
            self.log.error('Remote request unknown link node: %s' % from_id)
            return False
        
        self.log.debug('Remote node: %s', node)
        proxy = node.proxy
        if proxy is None:
            self.log.error('No proxy available for link node: %s' % from_id)
            return False
        self.etb.get_goals_dependencies(goals, proxy)
        def task_interpret(etb, query_id=query_id, goals=goals):
            query = self.etb.create_query((goals,))
            self.query_wait(query)
            answer = terms.dumps(self.etb.query_answers(query))
            def task(etb, query_id=query_id, answer=answer):
                proxy.answer_query(query_id, answer)
            etb.short_pool.schedule(task)
        self.etb.long_pool.schedule(task_interpret)
        return True

    ##### Client core API

    ### File access

    @_export
    def put_file(self, src, dst):
        """
        Put the file src on the ETB file system as dst.
        src should be a base64 encoded file content.
        Return a fileref to dst.
        """
        import json
        self.log.debug("Putting file %s" % dst)
        src = base64.b64decode(src)
        dst = dst.strip('\'').strip('"')
        cfile = self.etb.create_file(src, dst)
        self.log.debug('networking.put_file: cfile <{0}>: {1}'.format(cfile, type(cfile)))
        return json.dumps(cfile)

    @_export
    def put_filepath(self, src, dst):
        '''
        High-level API over the ETB put_file RPC call:
        src and dst are filenames, src can be a directory.
        src must be an absolute path, dst must be relative.
        '''
        esrc = os.path.expanduser(src.strip('"').strip('\''))
        if not os.path.isabs(esrc):
            self.log.error('put_filepath: src must be an absolute pathname:\n  {0}'
                           .format(src))
            return {}
        edst = os.path.expanduser(dst.strip('"').strip('\''))
        if os.path.isabs(edst):
            self.log.error('put_filepath: dst must be an relative pathname:\n  {0}'
                           .format(dst))
            return {}
        asrc = os.path.abspath(esrc)
        if not os.path.exists(asrc):
            self.log.error('put_filepath: file not found %s'.format(src))
            return {}
        self.log.info("Putting filepath {0} to {1}".format(src, dst))
        if os.path.isdir(asrc):
            return self.put_all_files({}, asrc, edst, '')
        else:
            return self.put_file_content(asrc, edst)
        
    def put_file_content(self, src, dst):
        with codecs.open(src, mode='rb', errors='ignore') as fd:
            contents = fd.read()
        return self.put_file(base64.b64encode(contents), dst)
        
    def put_all_files(self, refs, src, dst, subdir):
        d = os.path.join(src, subdir)
        for f in os.listdir(d):
            relpath = os.path.normpath(os.path.join(subdir, f))
            fullpath = os.path.join(d, f)
            if os.path.isdir(fullpath):
                if f != '.git':
                    self.put_all_files(refs, src, dst, relpath)
            else:
                dstpath = os.path.normpath(os.path.join(dst, relpath))
                ref = self.put_file_content(fullpath, dstpath)
                refs[relpath] = ref
        return refs

    @_export
    def get_file(self, ref):
        """
        Get the content of a file from the repo.
        """
        ref = ref.strip('"\'')
        ref = terms.loads(ref)
        return self.get_blob(ref['sha1'])[0]
 
    @_export
    def get_filehandle(self, path):
        """
        Get the handle to the current file from the repo.
        """
        import json
        path = path.strip('"\'')
        self.log.info('Getting handle to file %s' %  path)
        return json.dumps(self.etb.git.get_filehandle(path))

    ### Queries

    @_export
    def query(self, s):
        self.log.debug("New query: {0}".format(s))
        parsed_goals = parser.parse(s, 'literals')
        goals = tuple(parsed_goals)
        return self.etb.create_query(goals)

    @_export
    def proof(self, s):
        self.log.info("New proof query: %s", s)
        parsed_goals = parser.parse(s, 'literals')
        goals = tuple(parsed_goals)
        return self.etb.create_proof_query(goals)
    
    @_export
    def query_done(self, qid):
        """Returns the status of a running query."""
        return qid in self.etb.done_queries

    @_export
    def query_wait(self, qid):
        """Block until a query is complete."""
        goals = self.etb.get_query(qid)
        self.log.debug("query_wait called for: {0} {1} goal: {2}"
                       .format(qid, len(goals), goals))
        if not goals:
            self.log.error('Query id {0} not known'.format(qid))
            return True
        for goal in goals: #stjin: this is only 1 goal always I think, but it's a list..
            number = 0
            while number < 2 and not self.etb.engine.is_completed(goal):
                self.etb.engine.close()
                if False: #number > 100:
                    filename = self.etb.engine.goal_deps_to_png(goal)
                    os.rename(filename, "%s_%s.png" % (goal, number))
                    self.log.error('query_wait timeout')
                    return False
                number = number + 1
                self.log.debug("query_wait sleeping for query: %s" % qid)
                time.sleep(1)
        return True


    @_export
    def query_derivation(self, qid, filename):
        filename = filename.strip('\'"')
        return self.etb.query_derivation(qid, filename)

    @_export
    def query_proof(self, qid, filename):
        filename = filename.strip('\'"')
        return self.etb.query_proof(qid, filename)

    @_export
    def query_explanation(self, qid):
        #print "query_explanation(%s)" % qid
        goals = self.etb.get_query(qid)
        if not goals:
            self.log.error('Query id {0} not known'.format(qid))
            return []
        if len(goals) > 1:
            return []
        goal = goals[0]
        files = []
        claims = self.etb.engine.get_claims_matching_goal(goal) 
        for claim in claims:
            png = self.etb.engine.to_png(claim)
            files += png
        return files

    @_export
    def query_show_goal_dependencies(self, qid):
        goals = self.etb.get_query(qid)
        if not goals:
            self.log.error('Query id {0} not known'.format(qid))
            return []
        if len(goals) > 1:
            return []
        goal = goals[0]
        file = self.etb.engine.goal_deps_to_png(goal)
        return file

    @_export
    def query_close(self):
        self.etb.engine.close()
        return True

    @_export
    def query_complete(self):
        self.etb.engine.complete()
        return True

    @_export
    def query_is_completed(self, qid):
        goals = self.etb.get_query(qid)
        if goals:
            for goal in goals:
                if not self.etb.engine.is_completed(goal):
                    return False
        else:
            self.log.error('Query id {0} not known'.format(qid))
        return True

   
    ### Results

    @_export
    def query_answers(self, qid):
        """Given a query ID, returns a JSON-encoded list of all current answers
        (substitutions) to the query. The list may grow later, as new claims
        are added to the system.
        """
        answers = self.etb.query_answers(qid)
        if answers:
            return terms.dumps(answers['substs'])
        else:
            return ''

    @_export
    def query_claims(self, qid):
        """Returns the set of fact answers for this query. It returns a
        JSON-encoded list of lists of terms. Each 'fact' may have one or more
        claims to back it.

        Otherwise, returns False.
        """
        goals = self.etb.get_query(qid)
        if not goals:
            print('Invalid query id: {0}'.format(qid))
            return []
        answers = []
        for goal in goals:
            claims = self.etb.engine.get_claims_matching_goal(goal)
            for claim in claims:
                answers.append(claim.literal)
        return terms.dumps(answers)

    @_export
    def all_claims(self):
        self.log.debug('looking for all claims')
        claims = list(self.etb.all_claims())
        return terms.dumps(claims)

    @_export
    def find_claims(self, pattern, reasons=False):
        """Find and return claims that match the given pattern.
        See the Python re module for possible patterns."""
        claims = list(self.etb.find_claims(pattern))
        return terms.dumps(claims)

    @_export
    def get_interpreted_predicates(self) :
        """Get the list of interpreted predicates on this node"""
        return self.wrappers.keys()

    @_export
    def get_all_interpreted_predicates(self) :
        """Get the list of all interpreted predicates on the complete etb"""
        return list(self.etb.all_interpreted_predicates)

    #####

    # Anything below probably needs some cleanup

    @_export
    def get_neighbors(self):
        """Returns, over the network, a JSON list of current neighbors."""
        neighbors = list()
        neighbors = [((n.id, list(n.hosts), n.port, n.timestamp))
                     for n in self.neighbors]
        return terms.dumps(neighbors)
    
#    @_export
#    def get_claims(self, goal):
#        """Answers with the JSON list of claims that match this goal."""
#        goal = parser.parse(s, 'iterm')
#        claim_entries = list(self.etb.engine.match_claims_against(goal))
#        return terms.dumps(claim_entries)
    
#    @_export
#    def get_readable_claims(self, goal):
#        """Answers with the JSON list of readable claims that match this goal."""
#        goal = parser.parse(s, 'iterm')
#        claim_entries = list(self.etb.engine.match_claims_against(goal))
#        str = terms.dumps_readably(claim_entries)
#        return terms.loads(str)

    @_export
    def get_all_claims(self):
        """Get all the claims known by this node, as a JSON list"""
        claims = list(self.etb.engine.get_claims())
        return terms.dumps(claims)
    
    @_export
    def active_queries(self):
        """Returns a list of active queries"""
        return self.etb.queries

    @_export
    def done_queries(self):
        """Returns a list of queries that are done."""
        return self.etb.done_queries
    
    @_export
    def query_dot_file(self, query, filename):
        """Exports the graph of the given query (assuming it's
        backward chaining) to the given file, in dot format.
        """
        q = self.etb.get_query(query)
        if q:
            q.to_dot(filename.strip('"').strip('\''))
            return True
        else:
            self.log.error('Query id {0} not known'.format(qid))
            return False

    @_export
    def get_contents_from_network(self, sha1, seen=None):
        self.log.debug('Being asked over the wire for %s' % sha1)
        contents = None
        execp = False
        #do I have it? 
        if self.etb.git.has_blob(sha1):
            contents = self.etb.git.get_blob(sha1)[0]
    
        if contents is not None and contents is not '':
            self.log.debug('I have %s!' % sha1)
            execp = False
        else:
            seen = terms.loads(seen) if seen else []
            contents, execp = self.get_contents_from_somewhere(sha1, seen)

        if contents is not None and contents is not '':
            b64_contents = base64.b64encode(contents)
        else:
            b64_contents = ''
        return b64_contents, execp

   
    def get_contents_from_somewhere(self, sha1, seen=[]):
        """
        Find the content corresponding to a sha1, don't b64encode it
        (its for local use).  Presupposes it isn't to be had
        locally. Tries each neighbor, then ask any remote link, taking
        care not to chase ones tail.
        """
        contents = None
        execp = False
        self.log.debug('Being asked for contents with sha1 %s' % sha1)
        #do my neighbours have it?
        for n in self.neighbors:
            if n.id != self.id:
                #self.log.debug('Asking for %s from neighbor: %s with proxy %s' % (sha1, n.id, n.proxy))
                self.log.debug('Asking for %s from neighbor: %s' % (sha1, n.id))
                with self._rlock:
                    try:
                        if n.proxy is not None:
                            b64_contents, execp = n.proxy.get_blob(sha1)
                            contents = base64.b64decode(b64_contents)
                            if contents is not None and contents is not '':
                                break
                    except Exception as e:
                        pass

        if contents is not None and contents is not '':
            self.log.debug('My neigbours had %s!' % sha1)
            return contents, execp

        self.log.debug('Not local, asking for %s from my links %s  (seen = %s)' % (sha1, self.links, seen))
        for n in self.links:
            with self._rlock:
                try:
                    if n.proxy is not None and n.id not in seen:
                        visited = list(seen)
                        visited.append(n.id)
                        visited = terms.dumps(visited)
                        self.log.debug('Asking for %s from link: %s with proxy %s (visited = %s)' % (sha1, n.id, n.proxy, visited))
                        b64_contents, execp = n.proxy.get_contents_from_network(sha1, visited)
                        contents = base64.b64decode(b64_contents)
                        if contents is not None and contents is not '':
                            break
                except Exception as e:
                    self.log.debug('Asking for %s from link: %s **THREW** %s'  % (sha1, n.id, e))
                    pass

        if contents is None:
            self.log.error('Could not find file %s', sha1)
        else: 
            self.log.debug('My links had %s!' % sha1)
        return contents, execp

        
    @_export
    def get_blob(self, sha1):
        """Sends the contents for the sha1 hash"""
        if isinstance(sha1, terms.Const):
            sha1 = sha1.val

        b64_contents = None
        execp = False

        if self.etb.git.has_blob(sha1):
            contents, execp = self.etb.git.get_blob(sha1)
            b64_contents = base64.b64encode(contents)
        else:
            b64_contents = ''
        return b64_contents, execp

    @_export
    def get_tool_predicates(self) :
        """Get the list of tool predicates available on this node (which is the
        same as the list of interpreted predicates)
        """
        tools = self.etb.interpret_state.interpreted_predicates()
        return [str(t) for t in tools]

    @_export
    def get_all_tool_predicates(self) :
        """Get the list of tools available on the complete etb.
           We might get stuck for a while if some neighbors don't
           answer.
        """
        all_tools = set(self.get_tool_predicates())
        for n in self.neighbors :
            if n.id != self.etb.id and n.proxy is not None:
                all_tools.update(n.proxy.get_tool_predicates())
        return list(all_tools)

    @_export
    def get_rules(self):
        """Get the list of rules on this node.
        This returns a more readable form of the rules."""
        return terms.dumps(self.etb.engine.rules)

    @_export
    def get_facts(self):
        """Get the list of facts on this node.
        This returns a more readable form of the facts."""
        return terms.dumps(self.etb.engine.facts)

    @_export
    def etb_dir(self):
        """Provide the etb_dir (the directory where etbd was started)"""
        return self.etb.etb_dir

    @_export
    def git_dir(self):
        """Provide the git_dir pathname"""
        return self.etb.git.git_dir

    @_export
    def ls(self, path):
        """List the content of path on the etb."""
        fullpath = os.path.join(self.etb.git.git_dir, path)
        if os.path.isdir(fullpath):
            all = os.listdir(fullpath)
            git_ls = self.etb.git.ls(path)
            directories = []
            uptodate = []
            outdated = []
            notingit = []
            for f in all:
                if f == '.git':
                    continue
                elif os.path.isdir(os.path.join(fullpath, f)):
                    directories.append(f)
                else:
                    p = os.path.join(path[2:], f)
                    for g in git_ls:
                        if g.endswith(p):
                            if g[0] == 'H':
                                uptodate.append(f)
                            elif g[0] == 'C':
                                outdated.append(f)
                            elif g[0] == '?':
                                notingit.append(f)
                            else:
                                raise 'Invalid status'
                            break
            return (directories, uptodate, outdated, notingit)
        else:
            return False

    @_export
    def stop_etb(self):
        """Stop the ETB, saving current claims"""
        try:
            self.etb.stop()
        except:
            import traceback
            traceback.print_exc()
            raise
        return True

    @_export
    def clear_claim_table(self):
        """Clear all the claims, rules and interpreted goals on this node.
        This operation is irreversible! Use with caution.
        Returns True on success.
        """
        self.etb.clear_claims_table()
        return True
