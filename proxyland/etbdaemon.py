#!/usr/bin/env python

import time, os, sys

from .daemon import Daemon

class ETBDaemon(Daemon):

    def __init__(self, etbd, logfile, pidfile, directory, port):
        Daemon.__init__(self, pidfile, stdin=logfile, stdout=logfile, stderr=logfile)
        self.etbd = etbd
        self.port = port
        self.directory = directory

    def run(self):
        try:
            os.chdir(self.directory)
            args = [self.etbd, '--log', 'logfile.txt', '--port', self.port, '--debug', 'debug'] 
            #gregiore uses Popen in the tests (etb_manager.py), so this might be better
            os.execvp(self.etbd, args)
        except Exception as err:
            sys.stderr.write("execvp exception: {0}".format(err))


