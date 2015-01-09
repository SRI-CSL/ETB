#!/usr/bin/env python

""" ETB daemon

This is the module that starts up an ETB node.  It uses the
:mod:`etb.etbconfig` module to read command-line arguments and the ETB
config file, then creates an instance of :class:`etb.etb.ETB`

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

import os, sys
sys.path.append(os.path.abspath(os.path.join(__file__, '..')))

import logging
import signal
import time

from etb import ETB, debug_level_value
from etbconfig import ETBConfig

def setup_logger(debugLevel, logFile):
    """
    Sets up the logger for the ETB node.

    :parameters:
        - `debuglevel`: the debug level for the ETB; one of `debug`,
          `info`, `warning`, `error`, or `critical`
        - `logFile`: the path to the log file

    :returntype:
        :class:`logging.Logger`

    .. note::
        Many modules set up their own logger that inherit from this one; we
        should provide a way to indicate different levels for different modules;
        e.g., debug level for etb.wrappers, but info for all others.
    """
    logger = logging.getLogger('etb')
    logger.setLevel(debug_level_value(debugLevel))

    #logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s %(process)d/%(threadName)s: %(message)s")

    # formatter = logging.Formatter("%(asctime)s:%(levelname)s: %(message)s",
    #                               "%Y-%m-%d %H:%M:%S")
    formatter = logging.Formatter("%(levelname)s: %(message)s")
    
    if logFile is None:
        h = logging.StreamHandler()
    else:
        h = logging.FileHandler(logFile, mode='w')
        
    h.setLevel(debug_level_value(debugLevel))
    h.setFormatter(formatter)
    logger.addHandler(h)
    
    return logger

class FlushFile(object):
    """Write-only flushing wrapper for file-type objects."""
    def __init__(self, f):
        self.f = f
    def write(self, x):
        self.f.write(x)
        self.f.flush()

def main():
    '''
    The main function. It is called when the program is
    executed. It interprets the command line, starts logging,
    and creates the toolbus.
    '''
    # Add current directory to sys.path
    sys.path.insert(0,"")

    # Replace stdout with an automatically flushing version
    sys.stdout = FlushFile(sys.__stdout__)

    # Get the command line and config file arguments
    etbconf = ETBConfig()

    logger = setup_logger(etbconf.debuglevel, etbconf.logfile)

    ETB(etbconf)
    # The main thread continues here - is this the best way to do it?
    while True:
        time.sleep(5)

if __name__ == '__main__':
    main()
