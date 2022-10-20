
def etb_test(method):
    method.etb_test = True
    return method

class ETBTest(object):

    # be a bit more attentive to the user
    debug = True
    # dump the logs even on success (useful for watching whats going on)
    dump = False

    def __init__(self, etb_network):
        '''
        A test takes an ETB as argument: it will run on this ETB
        '''
        self.etb_network = etb_network
        self.etb = etb_network.etb

    def run(self):
        '''
        Run all the method of the class that are decorated with
        etb_test.
        '''
        if self.etb_network.hasErrors:
            return
        
        for m in list(self.__class__.__dict__.values()):
            if hasattr(m, 'etb_test'):
                indent = ''
                if ETBTest.debug:
                    indent = '\t'
                    print(('>  %s.%s on %s' % (self.__class__.__name__, m.__name__, self.etb_network.name)))
                self.etb.etb().clear_claim_table()
                claims = self.etb.etb().get_all_claims()
                assert claims == '[]', "Claims not empty, resetting failed?"
                (output, expected) = m(self)
                #output = json.loads(out)
                if isinstance(output, list) and len(output) > 1 and isinstance(expected, list):
                    # we need to sort the lists
                    output.sort()
                    expected.sort()
                if output != expected:
                    print(('%s--FAILURE: %s.%s on %s' %
                           (indent,
                            self.__class__.__name__,
                            m.__name__,
                            self.etb_network.name)))
                    if expected and output and \
                       isinstance(expected, list) and isinstance(output, list):
                        print(('type(expected) : list(%s)' % type(expected[0])))
                        print(('type(output) : list(%s)' % type(output[0])))
                    else:
                        print(('type(expected) : %s' % type(expected)))
                        print(('type(output) : %s' % type(output)))
                    print(('  expected: %s' % expected))
                    print(('  output  : %s' % str(output)))
                    print((self.etb_network.dump()))
                else:
                    print(('%s++PASSED: %s.%s on %s' %
                           (indent,
                            self.__class__.__name__,
                            m.__name__,
                            self.etb_network.name)))
                    if(ETBTest.dump): self.etb_network.dump()
                if ETBTest.debug: print(('<   %s.%s' % (self.__class__.__name__, m.__name__)))
