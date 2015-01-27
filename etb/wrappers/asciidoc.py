# Batch wrapper for Asciidoc

import os.path
from etb.wrapper import Tool, BatchTool, Substitutions

class AsciiDoc(BatchTool):
    """Batch wrapper for Asciidoc"""

    @Tool.predicate("+options:value, +src:file, -result:file")
    def asciidoc(self, options, src, result) :
        """Calls asciidoc on the source file."""
        self.run(result, 'asciidoc', src)
        (base, _) = os.path.splitext(src)
        output = base + '.html'
        return Substitutions(self, [{ result: output }])

def register(etb):
    "Register the tool"
    etb.add_tool(AsciiDoc(etb))
