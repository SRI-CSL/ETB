#!/usr/bin/env python

import os, argparse, ConfigParser, socket

class MetaServerConfig():

    DEFAULT_CONFIG_FILE = 'etb_metaserver.ini'

    #two types of processes use this puppy (the proxy, and the spawner)
    def __init__(self, config_file):
        if(config_file is None):
            self.argparse()
            self.config_file = self.args.config
        else: 
            self.config_file = config_file
        self.config_file_reader()
        self.sanity_check()

    def argparse(self):
        parser = argparse.ArgumentParser(description='Grokking the user\'s desires')
        parser.add_argument('--config', '-cf',
                            default=self.DEFAULT_CONFIG_FILE,
                            help='choose config file')
        self.args = parser.parse_args()



    def config_file_reader(self):
        if self.config_file and os.path.exists(self.config_file):
            cp = ConfigParser.ConfigParser()
            cp.read(self.config_file)
            assert cp.has_section('etb_metaserver')
            self.config = dict(cp.items('etb_metaserver'))
            # remember the file location for the spawning process (it has to read it too)
            self.config['config_file'] = self.config_file
        else:
            self.config = None
            
            
    def sanity_check(self):
        self.ok = False
        #better have at least some chance
        if self.config is None:
            self.complaint = "No configuration file"
            return
        required_keys = (
            'metaserver_name_or_ip',
            'metaserver_listening_port',
            'database_path',
            'mail_server_name',
            'mail_server_port',
            'mail_sender',
            'server_farm_path',
            'etb_daemon_path',
            )
        for key in required_keys:
            if not self.config.get(key, None):
                self.complaint = "no {0} value configured".format(key)
                return
            
        if self.config['metaserver_name_or_ip'] == 'localhost':
            self.config['metaserver_name_or_ip'] = socket.gethostbyname(socket.gethostname())
        self.ok = True
