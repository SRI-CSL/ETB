
import os

from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET


class Log(Resource):

    isLeaf = False
    
    allowedMethods = ("GET","POST")
    
    
    def __init__(self, state):
        Resource.__init__(self)
        self.state = state
        

    def getChild(self, name, request):
        print("Confirm.getChild called with name:'%s' and request: %s from host: %s" % (name, request, request.getHost()))
        return LogChild(name, self.state);



class LogChild(Resource):

    isLeaf = True
    
    allowedMethods = ("GET","POST")
    
    
    def __init__(self, name, state):
        Resource.__init__(self)
        self.name = name
        self.state = state
        
        
    def render(self, request): 
        self.request = request
        d = self.getServer(self.name)
        d.addCallback(self._delayedRender)
        return NOT_DONE_YET
    
    def getServer(self, name):
        return self.state.dbpool.runQuery("SELECT name TEXT, host TEXT, port INT FROM servers WHERE name = ?", (name, ))
    
    
    def _delayedRender(self, results):
        print('Rendering: %s' % results)
        yada = ''
        if not results:
            yada = '<html><body>Unknown request sorry :-(</body></html>'
        else:
            server_farm_path  = self.state.config['server_farm_path']
            logfile = os.path.join(server_farm_path, self.name, 'logfile.txt')
            yada = open(logfile, 'r').read()
            print('Opening  %s' % logfile)

            yada = '<html><body><pre>{0}</pre></body></html>'.format(yada) 
        self.request.write(yada)
        self.request.finish()

