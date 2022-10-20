#!/usr/bin/env python

from twisted.internet import reactor
from twisted.web import proxy, server
from twisted.web.resource import NoResource, Resource


class ETBMiddleman(Resource):
    isLeaf = False
    
    allowedMethods = ("GET","POST")

    def getChild(self, name, request):
        print("getChild called with name:'%s' and request: %s from host: %s" % (name, request, request.getHost()))
        if name == "etb1":
            print("proxy on etb1")
            return proxy.ReverseProxyResource('130.107.98.46', 8085, "/")
        elif  name == "etb2":
            print("proxy on etb2")
            return proxy.ReverseProxyResource('130.107.98.48', 8086, "/")
        else:
            NoResource()

simple = ETBMiddleman()

site = server.Site(simple)

reactor.listenTCP(8000, site)
reactor.run()
