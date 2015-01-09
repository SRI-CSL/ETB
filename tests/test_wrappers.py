
from etb.wrapper import Tool, BatchTool, Substitutions, Success, Failure
import etb.terms
import os, os.path

class Tests(BatchTool):

    @Tool.sync
    @Tool.predicate("+sal_file: file, -thm_file: file")
    def find_theorems(self, sal_file, thm_file):
        self.log.info('find_theorems: sal_file = {0}'.format(sal_file))
        (s, out, err) = self.callTool('grep', 'theorem', sal_file['file'])
        with open('theorems', 'w') as f :
            f.write(out)
        thm_file_ref = self.fs.put_file('theorems')
        self.log.info('find_theorems: thm_file = {0}: {1}'.format(thm_file_ref, type(thm_file_ref)))
        return Substitutions(self, [ self.bindResult(thm_file, thm_file_ref) ])

    @Tool.predicate("+input: value, -output: value")
    def bad_predicate(self, input, output):
        return self.run(output, 'non_existing_command', str(input.val))

def register(etb):
    etb.add_tool(Tests(etb))
