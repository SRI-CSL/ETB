import re
from etb.wrapper import Tool, BatchTool

class Yices(BatchTool):
    '''
    ETB wrapper for Yices.
    '''
    
    def parseResult(self, (stdout, stderr)):
        '''
        Override the default result parser of the BatchTool class:
        returns 'sat', 'unsat' or 'unknown'
        '''
        if re.search('^sat', stdout):
            return 'sat'
        elif re.search('^unsat', stdout):
            return 'unsat'
        else:
            return 'unknown'

    ### The predicates
        
    @Tool.predicate("+problem: file, -result: value")
    def yices(self, problem, result):
        '''
        Call yices on a single problem stated fully in an input file.
        Returns 'sat', 'unsat' or 'unknown'.
        '''
        return self.run(result, 'yices', problem['file'])

def register(etb):
    "Register the tool"
    etb.add_tool(Yices(etb))
