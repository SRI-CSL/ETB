# ETB wrapper around SALsim

import os

from etb.wrapper import Tool, SubprocessTool, Substitutions, Errors, Success, Failure

class SALsim(SubprocessTool) :
    """ETB wrapper around SALsim."""

    @Tool.volatile
    @Tool.predicate("+Model: file, +Module: value, -Session: handle")
    def salsim_start(self, model, module, session) :
        (ctx, ext) = os.path.splitext(model['file'])
        try:
            s = self.connect('sal-sim')
            self.log.info('salsim_start: connected')
            self.write(s, '(import! "%s")\n' % ctx)
            self.write(s, '(start-simulation! "%s")\n' % module)
            return Substitutions(self, [ self.bindResult(session, s) ])
        except Exception as msg:
            self.log.info('salsim_start: error {0}'.format(msg))
            return Errors(self, [ msg ])

    @Tool.predicate("+Session: handle")
    def salsim_help(self, session) :
        self.write(session, '(help)\n')
        return Failure(self)

    @Tool.predicate("+Session: handle, -States: value")
    def salsim_current_states(self, session, states) :
        out = self.write(session, '(display-curr-states)\n')
        return Substitutions(self, [ self.bindResult(states, out) ])

    @Tool.predicate("+SessionIn: handle, -SessionOut: handle")
    def salsim_step(self, sessionIn, sessionOut) :
        self.write(sessionIn, '(step!)\n', noRead=True)
        return Substitutions(self, [ self.bindResult(sessionOut, self.updateSession(sessionIn)) ])

    @Tool.predicate("+Session: handle")
    def salsim_close_session(self, session) :
        self.write(session, '(exit)\n')
        return Failure(self)

def register(etb) :
    """Register SALsim"""
    etb.add_tool(SALsim(etb))
