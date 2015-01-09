#!/usr/bin/env python

from twisted.internet import reactor
from twisted.web import proxy
from twisted.web.resource import Resource, NoResource

from twisted.web.server import NOT_DONE_YET

class ETBResource(Resource):

    isLeaf = True

    def __init__(self, name, state):
        Resource.__init__(self)
        self.name = name
        self.state = state

        
    def getAddress(self, name):
        return self.state.dbpool.runQuery("SELECT host, port FROM servers WHERE name = ?", (name, ))


    def render(self, request): 
        self.request = request
        d = self.getAddress(self.name)
        d.addCallback(self.proxyRender)
        return NOT_DONE_YET
    
    def proxyRender(self, results):
        #print 'getAddress results: {0}'.format(results)
        if not results:
            self.request.write('<html><body>Unknown Request. Sorry.</body></html>')
            self.request.finish()
        else:
            host = str(results[0][0])  #can't be unicode
            port =  results[0][1]
            #print "proxy.ReverseProxyResource(%s, %s)" % (host, port)
            return proxy.ReverseProxyResource(host, port, "/").render(self.request)
            
