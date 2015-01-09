''' Git interface for ETB.

The ETB uses Git to keep track of evidence for claims.
This module defines the interface.

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
'''

import os, sys, shutil, subprocess, codecs, threading
import logging
import dirsync


class ETBGIT(object):
    '''
    Class for the ETB git-related methods.
    '''

    def __init__(self, git_dir):
        '''
        The git repository is created and maintained in git_dir.
        logger should be a logging.Logger object.
        '''
        self.log = logging.getLogger('etb.git_interface')
        # Create a dirsync logger, else it generates confusing messages
        # This is passed in to dirsync.sync invocations.
        self.dirsync_log = logging.getLogger('dirsync')
        self.dirsync_log.setLevel(logging.DEBUG)
        self.dirsync_log.addHandler(logging.NullHandler())
        self.git_dir = os.path.abspath(git_dir)
        self._rlock = threading.RLock()

        self.gitwtarg = '--work-tree={0}' . format(self.git_dir)
        self.gitdirarg = '--git-dir={0}/.git' . format(self.git_dir)
        self._init_git_dir()

    # ian added a bunch of error checks, to prevent this failing quietly, due to error such as:
    # fatal: Unable to create '.../etb/src/etb_git/.git/index.lock': File exists.
    def _git_call(self, *args):
        with self._rlock:
            call_args = ['git', self.gitdirarg, self.gitwtarg] + list(args)
            process = subprocess.Popen(call_args,
                                       shell=False,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
            process.wait()
            if  process.returncode != 0:
                complaint = process.communicate()
                if complaint[0]:
                    raise Exception(complaint[0])
                elif complaint[1]:
                    raise Exception(complaint[1])
                else:
                    raise Exception("Git failed, but said nothing: ask Linus")
            return  process.returncode

    def _git_commit(self):
        # Git commit generates an error if nothing needs to be done
        # git commit --allow-empty   generates empty commits
        # git diff --quiet --exit-code --cached
        #   exitcode 0 nothing to commit
        #            1 can commit
        # We bypass _git_call because we don't want to raise an exception
        with self._rlock:
            call_args = ['git', self.gitdirarg, self.gitwtarg, 'diff',
                         '--quiet', '--exit-code', '--cached']
            process = subprocess.Popen(call_args,
                                       shell=False,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
            process.wait()
            if process.returncode != 0:
                self.log.debug('_git_commit: doing commit')
                return self._git_call('commit', '-m', 'ETB commit')
            else:
                self.log.debug('_git_commit: nothing to commit')
                return 0

    def _git_check_output(self, *args):
        with self._rlock:
            call_args = ['git', self.gitdirarg, self.gitwtarg] + list(args)
            return subprocess.check_output(call_args, stderr=subprocess.STDOUT)

    def _git_get_sha1(self, filepath):
        file_info = self._git_check_output('ls-files', '-s', filepath)
        return file_info.split(' ')[1]

    def _git_get_executable_p(self, sha1):
        files_info = self._git_check_output('ls-files', '-sz').split('\0')
        for finfo in files_info:
            if finfo != '':
                fspl = finfo.split()
                if fspl[1] == sha1 and (int(fspl[0], 8) & 0o100) > 0:
                    return True
        return False

    def _init_git_dir(self):
        '''
        Creates and initializes the etb_git directory if it is not there
        '''
        if os.path.exists(self.git_dir):
            if not os.path.isdir(self.git_dir):
                sys.exit("git_dir {0} is not a directory".format(self.git_dir))
        else:
            os.makedirs(self.git_dir)
        if not os.path.exists(os.path.join(self.git_dir, '.git')):
            retcode = self._git_call('init')
            if retcode != 0:
                sys.exit("Problem in git init")
        # Now add the .gitattributes file, which causes Git to treat all files as
        # binary, ensuring that the SHA1 is consistent across *nix and Windows.
        with open(os.path.join(self.git_dir, '.gitattributes'), 'w') as af:
            af.write('* binary\n')

    def get_filehandle(self, filepath):
        sha1 = self._git_get_sha1(filepath)
        if sha1 is None :
            error = 'File not found: %s' % filepath
            self.log.error(error)
            raise Exception(error)
        return { 'file': filepath, 'sha1': sha1 }
                
    def has_blob(self, sha1):
        '''
        Checks that we have the contents associated with a sha1.
        '''
        try:
            self._git_check_output('cat-file', 'blob', sha1)
            return True
        except subprocess.CalledProcessError:
            return False
        
    def get_blob(self, sha1):
        '''
        Gets the blob contents associated with a sha1 and a boolean executable flag
        '''
        try:
            git_type = self._git_check_output('cat-file', '-t', sha1).strip()
            if git_type != 'blob':
                self.log.debug('get_blob: not a blob?')
                raise err
            execp = self._git_get_executable_p(sha1)
            contents = self._git_check_output('cat-file', 'blob', sha1)
            return (contents, execp)
        except subprocess.CalledProcessError as err:
            self.log.error('Unable to get contents for {0}: {1}' . format(sha1, err))
            raise err

    def is_local(self, fileref):
        '''
        Returns True is the given fileref has a corresponding file in the
        repository.
        '''
        filepath = fileref['file']
        sha1 = fileref['sha1']
        git_file = self._make_local_path(filepath)
        return os.path.exists(git_file) and self._git_get_sha1(filepath) == sha1

    def _make_local_path(self, etb_path):
        '''
        Make a local path from an ETB path.
        ETB paths are supposed to be absolute path on the ETB file system,
        that is relative local path from the root of the git repo.
        '''
        return os.path.join(self.git_dir, etb_path)

    def put(self, src, dst):
        '''
        Add src to the repo under dst. src and dst should be absolute
        paths, src in the local filesystem, dst in the ETB filesystem

        Return the fileref of the newly created file.
        '''

        if not os.path.exists(src):
            error = 'File not found: %s' % src
            self.log.error(error)
            raise Exception(error)

        gitfile = self._make_local_path(dst)
        if src != gitfile :
            (gdir, _) = os.path.split(gitfile)
            try:
                os.makedirs(gdir)
            except OSError:
                pass
            if not (os.path.exists(gitfile)
                    and shutil._samefile(src, gitfile)):
                shutil.copy2(src, gitfile)

        return self.register(dst)

    def register(self, dst):
        gitfile = self._make_local_path(dst)
        try:
            self._git_call('add', dst)
            # This causes problems if a file is already there
            # self._git_call('commit', '-m', 'ETB commit')
            self._git_commit()
            sha1 = self._git_get_sha1(dst)
            osha1 = self._git_check_output('hash-object', gitfile).strip()
            assert sha1 == osha1, "Sha1's don't match -%s- vs. -%s-" % (sha1, osha1)
            return { 'file': dst, 'sha1': sha1 }
        except Exception as err:
            self.log.error("Unable to add {0} to repo: {1}" . format(dst, err))

    def get(self, src, dst=None):
        '''
        Get a file from the repo into the local file system.

        This is a bit tricky: the version we are asking for might not
        be the one currently in the file system.
        '''
        src_file = self._make_local_path(src['file'])
        
        if dst is None :
            if self._git_get_sha1(src_file) != src['sha1']:
                self.log.warning('Need to checkout the correct version of the file')
                self.log.warning(src['sha1'])
            return src_file
        
        (path, _) = os.path.split(dst)
        try:
            os.makedirs(path)
        except OSError:
            pass

        with codecs.open(dst, mode='wb', errors='ignore') as fd:
            # ignore the execp flag, it should already be correct
            blob, _ = self.get_blob(src['sha1'])
            fd.write(blob)

        return dst

    def put_dir(self, src, dst=None):
        '''
        Puts the src directory under the dst directory
        If dst is not specificed, defaults to the base name in src
        exclude is a set of glob patterns
        '''
        if not os.path.isdir(src):
            error = 'Directory not found : %s' % src
            self.log.error(error)
            raise Exception(error)
        src = os.path.abspath(src)
        if dst is None:
            dst = os.path.basename(src)
        else:
            if os.path.isabs(dst):
                error = 'Directory dst should not be absolute : %s' % dst
                self.log.error(error)
                raise Exception(error)
        if os.path.exists(dst):
            if not os.path.isdir(dst):
                error = 'Directory is a file : %s' % dst
                self.log.error(error)
                raise Exception(error)
        else:
            os.makedirs(dst)
        # dirsync is like rsync, copies changed files from src to dst, and purges
        # those not in src that are in dst, excluding some patterns.
        dirsync.sync(src, dst, 'sync', purge=True, logger=self.dirsync_log,
                     ignore=['.*\\.pyc$'],
                     exclude=['.*~$', '\\.git'])
        self._git_call('add', dst)
        git_stat = self._git_call('status', '-z', '--porcelain')
        if git_stat == 0:
            return False
        else:
            self._git_commit()
            return True

    def clear_dir(self, path):
        '''Clears out the specified path, which must be a relative path for
        the ETB Git repository.  Empties it, and commits.  Note that it will
        still be in the Git history.
        '''
        if os.path.exists(path):
            self._git_call('rm', '-r', path)
            git_stat = self._git_call('status', '-z', '--porcelain')
            if git_stat == 0:
                return False
            else:
                self._git_commit()
                return True
        else:
            return False

    def ls(self, path):
        '''
        List all files in a given path, relative to the git repo,
        with their status (up-to-date, not up-to-date, not in the repo).
        '''
        l = self._git_check_output('ls-files', '-t', '-o', '-c', '-m', path)
        return l.strip('\n').split('\n')
