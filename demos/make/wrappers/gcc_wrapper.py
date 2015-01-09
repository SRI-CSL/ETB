# Wrapper for gcc
#
# The names of the predicate is generated at load-time using the
# current platform. For example, on a Linux x86 64bits machine, the
# two predicates are 'gcc_compile_Linux_x86_64' and
# 'gcc_link_Linux_x86_64'.
#
# We execute gcc in an environment where LC_ALL and LANG are set to C,
# as Python has issues with UTF8 strings and gcc can emit UTF8 error
# messages.
#
# Errors are caught and returned as error claims.

import os.path
import platform
from etb.wrapper import Tool, BatchTool, Substitutions, Errors


class Gcc(BatchTool):

    @Tool.predicate("+src: file, +dependencies: files, -obj: file",
                    name='gcc_compile_%s_%s' % (platform.system(), platform.machine()))
    def gcc_compile(self, src, deps, obj):
        dst = os.path.splitext(src['file'])[0] + '.o'
        env = os.environ
        env['LC_ALL'] = 'C'
        env['LANG'] = 'C'
        (ret, _, err) = self.callTool('gcc', '-c', '-o', dst, src['file'], env=env)
        if ret != 0:
            self.log.error(err)
            return Errors(self,  [ err ] )
        objref = self.fs.put_file(dst)
        return Substitutions(self, [ self.bindResult(obj, objref) ])

    @Tool.predicate("+ofiles: files, +exename: value, -exe: file",
                    name='gcc_link_%s_%s' % (platform.system(), platform.machine()))
    def gcc_link(self, ofiles, exename, exe):
        filenames = [ r['file'] for r in ofiles ]
        args = [ 'gcc', '-o', exename.val ] + filenames
        env = os.environ
        env['LC_ALL'] = 'C'
        env['LANG'] = 'C'
        (ret, _, err) = self.callTool(*args, env=env)
        if ret != 0:
            self.log.error(err)
            return Errors(self,  [ err ] ) 
        exeref = self.fs.put_file(exename.val)
        return Substitutions(self, [ self.bindResult(exe, exeref) ])
    
def register(etb):
    etb.add_tool(Gcc(etb))
