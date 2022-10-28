#!/usr/bin/env python

import time, os, sys, xmlrpc.client, sqlite3

from .etbdaemon import ETBDaemon

from .utils import Utils

class ETBSpawner():

    def __init__(self, id, state, remote):
        self.id = id
        self.state = state
        self.remote = remote
        self.rules = None


    def spawn(self):
        try:
            #remember where we are
            current_working_directory = os.getcwd()
            with self.state.rlock:
                #<critical section>
                self.port = str(Utils.get_open_port())
                etbd = self.state.config['etb_daemon_path']
                server_ip = self.state.config['metaserver_name_or_ip']
                local = ( self.id, server_ip, self.port )
                self.prepare_for_launch()
                if not self.launch_etb(etbd):
                    return (False, 'launching the etbd failed')
                #</critical section>
                #return from whence we came
                os.chdir(current_working_directory)
                if not self.register_etbs(local):
                    return (False, 'registering the etbd failed')
                if not self.link_etbs(local):
                    return (False, 'linking the two etbds failed')
                return (True, '')
        except Exception as e:
            return (False, str(e))


    def prepare_for_launch(self):
        server_farm_path  = self.state.config['server_farm_path']
        self.directory = os.path.join(server_farm_path, self.id)
        os.mkdir(self.directory)
        os.chdir(self.directory)
        files = ('logfile.txt', 'errorfile.txt')
        for file in files:
            fh = open(file, 'w')
            fh.write('')
            fh.close()
        self.link_wrappers()
        self.link_rules()
        self.generate_config()
        return  True


    def launch_etb(self, etbd):
        pidfile = os.path.join(self.directory, 'pidfile')
        errorfile = os.path.join(self.directory, 'errorfile.txt')

        try: 
            pid = os.fork() 
            if pid == 0:
                ETBDaemon(etbd, errorfile, pidfile, self.directory, self.port).start()
        except OSError as e: 
            return False

        print('{0} Forked: {1} with pidfile {2}'.format(os.getpid(), pid, pidfile))

        retries_remaining = 10
        success = False
        while (retries_remaining >  0):
            if Utils.server_is_up('localhost', self.port):
                success = True
                break
            retries_remaining = retries_remaining - 1
            time.sleep(0.5)
        print('Success = {0} and the number of retries remaining: {1}'.format(success, retries_remaining))
        return success

    def register_etbs(self, local):
        db = self.state.config['database_path']
        con = sqlite3.connect(db)
        with con:
            servers = ( local, self.remote )
            cur = con.cursor()    
            cur.executemany('INSERT INTO servers (name, host, port) VALUES(?, ?, ?)', servers)
            return True
        return False

    def link_etbs(self, local):
        server_ip = self.state.config['metaserver_name_or_ip']
        server_port = self.state.config['metaserver_listening_port']
        remote_url = 'http://{0}:{1}'.format(self.remote[1], self.remote[2])
        print('Linking: {0} @ {1} with {2}'.format(local, server_ip, remote_url))
        remote_node = xmlrpc.client.Server(remote_url)
        print('proxylink({0}, {1}, {2}, {3})'.format(server_ip, server_port, self.remote[0], local[0]))
        remote_node.proxylink(server_ip, server_port, self.remote[0], local[0])
        return True

    def link_wrappers(self):
        wrappers = self.state.config['etb_wrappers']
        if wrappers and os.path.exists(wrappers):
            wrappers = os.path.abspath(wrappers)

            os.mkdir(self.directory + '/wrappers')
            open(self.directory + '/wrappers/__init__.py', 'w').close()

            wrapper_list = os.listdir(wrappers)

            for w in wrapper_list:
                if w.startswith('__') or not w.endswith('.py'):
                    continue
                src = wrappers + '/' +  w
                dst = self.directory + '/wrappers/' + w
                os.symlink(src, dst)

    def link_rules(self):
        rules = self.state.config['etb_rules']
        print('>rules = %s' % rules)
        if rules and os.path.exists(rules):
            src = os.path.abspath(rules)
            self.rules = os.path.basename(rules)
            dst = os.path.join(self.directory, self.rules)
            print('src = %s' % src)
            print('dst = %s' % dst)
            os.symlink(src, dst)
        print('<rules = %s' % rules)


    def generate_config(self):
        with open(self.directory + '/etb_conf.ini', 'w') as f:
            f.write('[etb]\n')
            f.write('port = %s\n' % self.port)
            f.write('wrappers_dir = wrappers\n')
            if self.rules:
                f.write('rule_files = %s\n' % self.rules)
