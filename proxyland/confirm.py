
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET

from twisted.internet import threads

from utils import Utils

import subprocess, threading

from spawn import ETBSpawner


class Confirm(Resource):

    isLeaf = False
    
    allowedMethods = ("GET","POST")
    
    
    def __init__(self, state):
        Resource.__init__(self)
        self.state = state
        

    def getChild(self, name, request):
        return ConfirmChild(name, self.state);


class ConfirmChild(Resource):

    isLeaf = True
    
    allowedMethods = ("GET","POST")
    
    
    def __init__(self, name, state):
        Resource.__init__(self)
        self.name = name
        self.state = state
        self.id = Utils.uuid()
        self.server_ip =  self.state.config['metaserver_name_or_ip']
        self.server_port = self.state.config['metaserver_listening_port']

        
    def render(self, request): 
        self.request = request
        d = self.getUser(self.name)
        d.addCallback(self._launchInThread)
        return NOT_DONE_YET

    def getUser(self, name):
        return self.state.dbpool.runQuery("SELECT email, host, port FROM users WHERE confirmation = ?", (name, ))

    def _launchInThread(self, results):
        dt = threads.deferToThread(self._launchETB, results)
        dt.addCallback(self._delayedRender)


    def _launchETB(self, results):
        #print "Launch: {0}".format(threading.current_thread())
        if not results:
            return results
        else:
            row = results[0]
            remote = ( Utils.uuid(), row[1], row[2] )
            success, cause = ETBSpawner(self.id, self.state, remote).spawn()
            return { 'user' : row[0],  'success' : success, 'cause' : cause }
        
    
    def _delayedRender(self, results):
        #print 'Rendering: %s' % results
        yada = ''
        if not results:
            yada = '<html><body>Something went awry, sorry :-(</body></html>'
        elif results and not results['success']:
            yada = '<html><body>Your spawning failed because {0}, sorry :-(</body></html>'.format(results['cause'])
        else:
            response = (
                '<html><body>'
                '<p>Good, welcome back {0}</p>'
                '<p>You can view your remote server\'s logs <a href="{1}">here</a></p>'
                '</body></html>'
                )
            loguri = 'http://{0}:{1}/log/{2}'.format(self.server_ip, self.server_port, self.id)
            yada = response.format(results['user'], loguri) 
        self.request.write(yada)
        self.request.finish()

