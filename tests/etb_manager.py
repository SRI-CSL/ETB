import os, os.path
import subprocess, tempfile, time
import xmlrpclib

from etb.etbclientlib import ETBClient

class ETBNode(object):
    def __init__(self, spec, setupOnly=False):
        self._directory = spec.get('directory', None)
        self._wrappers = spec.get('wrappers', [])
        self._rules = spec.get('rules', [])
        self._port = spec.get('port', 26532)
        self._host = spec.get('host', 'localhost')
        self._setupOnly = setupOnly
        self._logFile = None
        self._logOutput = False
        self._process = None
        self._etb = None
        
    def validate_wrappers(self):
        for w in self._wrappers:
            src = '../etb/wrappers/' + w + '.py'
            if not os.path.exists(w + '.py') and not os.path.exists(src):
                raise (Exception ('Invalid wrapper: %s' % w))

    def link_wrappers(self):
        os.mkdir(self._directory + '/wrappers')
        open(self._directory + '/wrappers/__init__.py', 'w').close()
        for w in self._wrappers:
            src = w + '.py'
            if os.path.exists(src):
                src = os.path.abspath(src)
            else:
                src = os.path.abspath('../etb/wrappers/' + src)
            w = os.path.basename(src)
            dst = self._directory + '/wrappers/' + w
            os.symlink(src, dst)

    def link_rules(self):
        for r in self._rules:
            if os.path.exists(r):
                dst = os.path.join(self._directory, os.path.basename(r))
                os.symlink(r, dst)
            else:
                raise (Exception ('Invalid rules file: %s' % r))
            
    def generate_config(self):
        with open(self._directory + '/etb_conf.ini', 'w') as f:
            f.write('[etb]\n')
            f.write('port = %d\n' % self._port)
            f.write('wrappers_dir = wrappers\n')
            if self._rules:
                f.write('rule_files = %s\n' % ','.join(os.path.basename(r) for r in self._rules))

    def check_port(self):
        """
        We ping the port where we are going to set up our node
        to make sure there's no already running node there.
        """
        try:
            old_etb = xmlrpclib.ServerProxy('http://localhost:%d' % self._port)
            old_etb.test()
            fail = True
        except:
            fail = False
        if fail:
            print 'Error: port %d is already in use, the ETB cannot be set up correctly.' % self._port
            assert False

    def __enter__(self):
        self.validate_wrappers()
        if self._directory is None:
            self._directory = tempfile.mkdtemp()
        else:
            self._directory = os.path.abspath(self._directory)
            os.makedirs(self._directory)
        self.link_wrappers()
        self.link_rules()
        self.generate_config()
        if self._setupOnly:
            print 'ETB Node configured in: %s' % self._directory
            return None
        self._logFile = './%s.log' % os.path.basename(self._directory)
        print 'Logging into %s' % self._logFile
        of = open(self._logFile, 'w')
        
        self.check_port()
        self._process = subprocess.Popen(['etbd'],
                                         cwd=self._directory,
                                         shell=False,
                                         #stdout=of,
                                         stderr=subprocess.STDOUT)
        self._etb = ETBClient()
        self._etb.set_url('localhost', self._port)
        connected = False
        while not connected:
            try:
                if self._etb.etb() is not None:
                    connected = True
            except:
                time.sleep(0.1)
                pass
        return self._etb

    def dump(self):
        self._logOutput = True
        print 'Logged into: %s' % self._logFile

    def __exit__(self, _, value, tb):
        if self._setupOnly:
            return
        self._process.terminate()
        if False: #not self._logOutput :
            os.remove(self._logFile)

class ETBNetwork(object):
    def __init__(self, name, *args):
        self.name = name
        self._node_specs = args
        self._nodes = []
        self.etb = None
        self._setupOnly = False
        self.hasErrors = False

    def connect(self, spec):
        neighbors = self.etb.etb().get_neighbors()
        self.etb.etb().connect(spec.get('host', 'localhost'),
                               str(spec.get('port', 26532)))
        time.sleep(2)
        while neighbors == self.etb.etb().get_neighbors():
            time.sleep(0.1)
            pass

    def setupOnly(self):
        self._setupOnly = True

    def __enter__(self):
        try:
            for s in self._node_specs:
                node = ETBNode(s, setupOnly=self._setupOnly)
                if self.etb is None:
                    self.etb = node.__enter__()
                else:
                    node.__enter__()
                    self.connect(s)
                self._nodes.append(node)
        except Exception as msg:
            print msg
            self.hasErrors = True
        return self

    def __exit__(self, _, value, tb):
        for n in self._nodes:
            n.__exit__(None, None, None)

    def dump(self):
        for n in self._nodes:
            n.dump()
