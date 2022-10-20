#!/usr/bin/env python

import threading

from twisted.enterprise import adbapi
from twisted.internet import reactor
from twisted.web import server
from twisted.web.resource import Resource

from .config import MetaServerConfig
from .confirm import Confirm
from .log import Log
from .register import Register
from .resource import ETBResource


def main():
    state = MetaServerConfig(None)
    if not state.ok:
        print("I need to be configured properly before I'll run: {0}".format(state.complaint))
        return
    else:
        simple = ETBProxy(state)
        site = server.Site(simple)
        listening_port = int(state.config['metaserver_listening_port'])
        print("Looks good, listening on: {0}".format(listening_port))
        reactor.listenTCP(listening_port, site)
        reactor.run()


class ETBProxy(Resource):

    isLeaf = False
    
    allowedMethods = ("GET","POST")
    
    requestCounts = {}
    
    def __init__(self, state):
        Resource.__init__(self)
        self.state = state
        self.state.dbpool = adbapi.ConnectionPool('sqlite3', self.state.config['database_path'], check_same_thread=False)
        self.state.rlock = threading.RLock()

    def incrementCounter(self, name):
        if name not in self.requestCounts:
            self.requestCounts[name] = 0
        else:
            self.requestCounts[name] = self.requestCounts[name] + 1
        return self.requestCounts[name]

    def getChild(self, name, request):
        count = self.incrementCounter(name)
        print("request %s to %s" % (count, name))
        if name == "register":
            return Register(self.state);
        elif name == "confirm":
            return Confirm(self.state);
        elif name == "log":
            return Log(self.state);
        else:
            #print "ETBResource(%s, %s)" % (name, self.state)
            return ETBResource(name, self.state)


if __name__ == "__main__":
    main()

