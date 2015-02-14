""" Client library for the Evidential Tool Bus (ETB)

This library can be used to write client tools for the ETB.

The class ETBClient provides a command line parser that recognizes
standard ETB client options such as ETB host and ETB port. It also
provides a method to get a proxy to the ETB.

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

import os, re
try: 
    import readline
except:
    import pyreadline
#import argparse
import xmlrpclib
import codecs, base64
import json
import terms

def wrap_xmlrpcfault(method):
    '''
    Decorator used around method that do xmlrpc calls to catch ETB
    errors and emit them as such.
    '''
    def wrapper(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except xmlrpclib.Fault as e:
            raise Exception (e.faultString.split(':', 1)[1])
    return wrapper

def is_filehandle(obj):
    if isinstance(obj, dict):
        return type(obj) == dict and 'file' in obj and 'sha1' in obj
    else:
        return terms.is_fileref(obj)

class ETBClient(object):
    '''
    Basic ETB client objects.

    Offers high-level operations to interact with an ETB server:
    - the etb method gives a proxy to the server.
    - the put_file and get_file methods take regular filenames.
    - put_file can put a directory, and returns a list of filerefs
    '''

    def __init__(self):
        self._url = None

    def set_url(self, host, port, name=None):
        if name is None:
            self._url = 'http://{0}:{1}'.format(host, port)
        else:
            self._url = 'http://{0}:{1}/{2}'.format(host, port, name)

    @wrap_xmlrpcfault
    def etb(self):
        '''Proxy to the ETB server.'''
        if self._url == None:
            raise Exception('Error: no ETB server configured.')
        try:
            proxy = xmlrpclib.ServerProxy(self._url)
            proxy.test()
        except:
            raise Exception('Error: cannot connect to the ETB at %s.' % self._url)
        return proxy

    @wrap_xmlrpcfault
    def query_answers(self, query):
        '''Loads the JSON result of the query_answers method'''
        answers = self.etb().query_answers(query)
        if answers:
            return terms.loads(answers)
    
    @wrap_xmlrpcfault
    def query_claims(self, query):
        '''Loads the JSON result of the query_claims method'''
        claims = self.etb().query_claims(query)
        return terms.loads(claims)

    @wrap_xmlrpcfault
    def all_claims(self):
        '''Loads the JSON result of the all_claims method'''
        claims = self.etb().all_claims()
        return sorted(terms.loads(claims))

    @wrap_xmlrpcfault
    def put_file(self, src, dst=None):
        '''
        High-level API over the ETB put_file RPC call:
        src and dst are filenames, dst can be omitted, src can be a directory.
        src is relative to the current shell directory, unless dst is given.
        '''
        src = os.path.expanduser(src.strip('"').strip('\''))
        if dst is None:
            if os.path.isabs(src):
                print 'error: put_file(<src>), <src> should be relative, or use put_file(<src>, <dst).'
                return
            if src.find('..') != -1:
                print 'error: put_file(<src>), <src> should be below the current working directory.'
                return
            else:
                dst = src
        src = os.path.abspath(src)
        if not os.path.exists(src):
            print 'error: file not found %s' % src
            return

        if os.path.isdir(src):
            return self.put_all_files({}, src, dst, '')
        else:
            return self.put_file_content(src, dst)
        
    def put_file_content(self, src, dst):
        with codecs.open(src, mode='rb', errors='ignore') as fd:
            contents = fd.read()
        return self.etb().put_file(base64.b64encode(contents), dst)
        
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

    @wrap_xmlrpcfault
    def get_file(self, src, dst=None):
        '''
        gets the file from the ETB

        src is a file handle
        '''
        if is_filehandle(src):
            if dst is None:
                dst = src['file']
            if isinstance(dst, terms.Const):
                dst = dst.val
            dst = dst.strip('"\'') # Get rid of outer quote marks
            jsrc = terms.dumps(src)
            contents = self.etb().get_file(jsrc)
            ndir = os.path.dirname(dst)
            if ndir != '' and not os.path.isdir(ndir):
                os.makedirs(ndir)
            with codecs.open(dst, mode='wb', errors='ignore') as fd:
                fd.write(base64.b64decode(contents))
        elif isinstance(src, basestring):
            # Just get whatever version is in the working (Git) directory
            shandle = self.etb().get_filehandle(src)
            handle = json.loads(shandle)
            if is_filehandle(handle):
                return self.get_file(handle, dst)
        else:
            raise TypeError('get_file: string or filehandle expected: {0}: {1}'
                            .format(src, type(src)))

    @wrap_xmlrpcfault
    def get_filehandle(self, path):
        if path  is None:
            print 'warning: cannot get file handle to None'
            return
        handle  = self.etb().get_filehandle(path)
        return handle

    
# class ETBClientArgParser(argparse.ArgumentParser):
#     def __init__(self, descr):
#         argparse.ArgumentParser.__init__(self, description=descr)
#         self.add_argument('--host', default='localhost', help='etb host')
#         self.add_argument('--port', '-p', default='26532', help='etb port')
#         self.add_argument('--name', '-n', default=None, help='etb name (used in proxying)')

class ETBClientArg(ETBClient):
    '''
    Basic ETB client with a command line parser and standard arguments
    for hostname and port.
    '''
    def __init__(self, descr):
        ETBClient.__init__(self)
        #self._parser = ETBClientArgParser(descr)
        self._root_dir = os.path.dirname(os.getcwd())
        self._base_dir = os.path.basename(os.getcwd())

    # def parse_args(self):
    #     self._args = self._parser.parse_args()
    #     self.set_url(self._args.host, self._args.port, self._args.name)

    # def args(self):
    #     if self._args is None:
    #         self.parse_args()
    #     return self._args

    # def parser(self):
    #     return self._parser

    def raise_on_error_claims(self, answers, msg_map):
        msg = None
        if answers['claims'] :
            for c in answers['claims']:
                m = re.search('error\(\'(.*)\'\)', c)
                if m:
                    if m.group(1) in msg_map:
                        msg = 'Error: %s.' % msg_map[m.group(1)]
                    else:
                        msg = 'Error: %s.' % m.group(1)
                    break
        if msg :
            raise Exception(msg)

class History(object):
    def __init__(self, history_file):
        self._file = history_file
        readline.set_history_length(50)
        if os.path.exists(self._file):
            readline.read_history_file(self._file)

    def save(self, history_file=None):
        if history_file is None:
            history_file = self._file
        readline.write_history_file(history_file)

class Completion(object):
    def __init__(self, commands):
        self._commands = commands
        readline.parse_and_bind('tab: complete')
        readline.set_completer(self.complete)

    def complete(self, text, state):
        candidates = []
        for c in self._commands:
            if c.startswith(text.strip()):
                candidates.append(c)
        if not candidates:
            candidates = [None]
        return candidates[state]

class ETBCmdLineClient(ETBClientArg):
    '''
    Basic client with command line argument parsing, readline history
    and completion.
    '''
    def __init__(self, descr, history_file, completion_list):
        ETBClientArg.__init__(self, descr)
        self.set_url(self.config.host, self.config.port, self.config.name)
        self._history = History(history_file)
        self._completion = Completion(completion_list)
