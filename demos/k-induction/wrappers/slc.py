# ETB wrapper for slc - our simple language compiler.
#
# slc -m bmc -k k <file.sl> -- generates a yices bmc formula to depth k for the file
# slc -m induction -k k <file.sl> -- generates a yices k-induction step formula for the file
# slc -m check <file.sl> -- checks that the file can be parsed correctly

import os

from etb.wrapper import Tool, BatchTool

class SLC(BatchTool):

    @Tool.predicate("+modelFile: file")
    def transitionSystem(self, modelFile):
        """
        Check that the input file is a valid SL transition system.
        """
        return self.run('checked.\n', '../slc', '-m', 'check', modelFile['file'])

    @Tool.predicate("+modelFile: file, +prop: value, +k: value, -formula: file")
    def yicesBmcFormula(self, modelFile, prop, k, formula):
        """
        Generate a BMC formula to depth k for the property in the model.
        The result is a yices file.
        """
        out = os.path.splitext(modelFile['file'])[0] + '_bmc_%s.ys' % str(k)
        (ret, _, e) = self.callTool('../slc', '-m', 'bmc', '-k', str(k),
                                        '-p', str(prop), '-o', out, modelFile['file'])
        if ret != 0:
            self.log.error(e)
            return { 'claims': ['error("yicesBmcFormula", "%s")' % e] }
        
        outref = self.fs.put_file(out)
        return [ self.bindResult(formula, outref)]

    @Tool.predicate("modelFile: file, +prop: value, +k: value, -formula: file")
    def yicesInductionFormula(self, modelFile, prop, k, formula):
        """
        Generate an k-induction step formula for the property in the model.
        The result is a yices file.
        """
        out = os.path.splitext(modelFile['file'])[0] + '_induction_%s.ys' % str(k)
        (ret, _, e) = self.callTool('../slc', '-m', 'induction', '-k', str(k),
                                        '-p', str(prop), '-o', out, modelFile['file'])
        if ret != 0:
            self.log.error(e)
            return { 'claims': ['error("yicesInductionFormula", "%s")' % e] }
        
        outref = self.fs.put_file(out)
        return [ self.bindResult(formula, outref)]

def register(etb):
    etb.add_tool(SLC(etb))
