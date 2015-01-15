import re
from etb.wrapper import Tool, BatchTool

class Yices_batch(BatchTool):
    '''
    ETB wrapper for Yices invoked as a batch tool.
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
        
    @Tool.predicate("+problem: file, result: value")
    def yices(self, problem, result):
        '''
        Call yices on a single problem stated fully in an input file.
        Returns 'sat', 'unsat' or 'unknown'.
        '''
        self.log.info('yices: result {0}: {1}'.format(result, type(result)))
        return self.run(result, 'yices', problem['file'])

def register(etb):
    "Register the tool"
    etb.add_tool(Yices_batch(etb))
