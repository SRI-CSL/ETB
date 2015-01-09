""" ETB configuration

This module takes care of configuration for the ETB.
It is used by both the ETB daemon :mod:`etb.etbd` and the ETB shell :mod:`etb.etbsh`.

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


import os, sys, platform
import argparse
import ConfigParser
import colorama
from colorama import Fore, Back, Style
colorama.init()

class ETBConfig:
  """Configuration for ETB, using argparse and ConfigParser"""
  
  DEFAULT_CONFIG_FILE = 'etb_conf.ini'
  DEFAULT_PORT = 26532
  DEFAULT_RULES_DIR = 'rules'
  DEFAULT_WRAPPERS_DIR = 'wrappers'
  DEFAULT_GIT_DIR = 'etb_git'
  #DEFAULT_LOGIC_FILE = 'etb_claims'
  # Period (in seconds) of 'ping' messages (iam: currently also the period of poke messages)
  DEFAULT_PING_PERIOD = 25
  
  def __init__(self):
      
    # This convoluted code first partially reads the command-line args to get the
    # config file, then loads the config file, and finally reads the rest of the args.
    # The point is to have the command line arguments override config file arguments.
    
    # We make the config file arg parser with add_help=False so that
    # it doesn't parse -h and print help.
    confparser = argparse.ArgumentParser(
      description=__doc__, # printed with -h/--help
      # Don't mess with format of description
      formatter_class=argparse.RawDescriptionHelpFormatter,
      # Turn off help, so we print all options in response to -h
      add_help=False
    )
    confparser.add_argument('--config', '-cf', help='choose config file')
    # At this point, only the config file is a known arg
    args, remaining_argv = confparser.parse_known_args()

    # Now we know which config file, we read it in
    self.config_file = args.config
    if args.config is None:
      if os.path.exists(ETBConfig.DEFAULT_CONFIG_FILE):
        self.config_file = ETBConfig.DEFAULT_CONFIG_FILE
    else:
      if not os.path.exists(self.config_file):
        print 'Config file {0} does not exist'.format(self.config_file)
        sys.exit(1)

    cp = ConfigParser.RawConfigParser()
    user_config_file = os.path.expanduser("~/etb_conf.ini")
    if os.path.exists(user_config_file):
      if self.config_file:
        cp.read([user_config_file, self.config_file])
      else:
        cp.read([user_config_file])
    else:
      if self.config_file:
        cp.read([self.config_file])
        
    if cp.has_section('etb'):
      config = {k: os.path.expandvars(v) for k, v in dict(cp.items('etb')).iteritems()}
    else:
      config = {}

    descr = 'Evidential Tool Bus'
    parser = argparse.ArgumentParser(
      description=descr,
      formatter_class=argparse.ArgumentDefaultsHelpFormatter,
      parents=[confparser])
    # Now add the rest of the arguments
    parser.add_argument('--debuglevel', '-d',
                        choices=['debug', 'info', 'warning', 'error', 'critical'],
                        default='info', help='debugging level')
    parser.add_argument('--log-file', default=None, help='send log to log-file')
    parser.add_argument('--port', '-p', default=ETBConfig.DEFAULT_PORT,
                        help='port to listen on')
    parser.add_argument('--rules-dir', '-rd', default=ETBConfig.DEFAULT_RULES_DIR,
                        help='rules directory')
    parser.add_argument('--wrappers-dir', '-wd', default=ETBConfig.DEFAULT_WRAPPERS_DIR,
                        help='wrappers directory')
    parser.add_argument('--git-working-dir', '-gd', default=ETBConfig.DEFAULT_GIT_DIR,
                        help='git working directory')
    parser.add_argument('--etb-file-path', '-fp', default=os.getcwd(),
                        help='(semi-)colon separated path for put_file searches from wrappers')
    # parser.add_argument('--logic-file', '-lf', default=ETBConfig.DEFAULT_LOGIC_FILE,
    #                     help='logic file for reading and saving claims')
    parser.add_argument('--ping-period', default=ETBConfig.DEFAULT_PING_PERIOD,
                        help='how often to ping other ETB nodes (seconds)')
    parser.add_argument('--node-timeout', default=20 * ETBConfig.DEFAULT_PING_PERIOD,
                        help='when to decide other ETB nodes are disconnected (seconds)')
    # Set the defaults from config, overriding the defaults above
    parser.set_defaults(**config)
    # Now parse remaining args
    args = parser.parse_args(remaining_argv)

    self.debuglevel = args.debuglevel
    self.logfile = args.log_file
    self.port = args.port
    self.rule_files = config.get('rule_files', None)
    if self.rule_files is not None:
      self.rule_files = [os.path.abspath(f) for f \
                         in self.rule_files.split(',')]
    self.etb_file_path = config.get('etb_file_path', os.getcwd()).split(os.pathsep)
    #self.logic_file = os.path.abspath(args.logic_file)
    self.wrappers_dir = os.path.abspath(args.wrappers_dir)
    self.rules_dir = os.path.abspath(args.rules_dir)
    self.git_dir = os.path.abspath(args.git_working_dir)
    self.cron_period = args.ping_period
    self.node_timeout = args.node_timeout
    
class ETBSHConfig:
  """Configuration for etbsh, using argparse and ConfigParser, see etbd.py"""
  
  DEFAULT_PROMPT_STRING = '%g > '
  if platform.system() == 'Windows':
    DEFAULT_COLOR_BG      = 'dark'
  else:
    DEFAULT_COLOR_BG      = 'light'

  def __init__(self):
    confparser = argparse.ArgumentParser(
      description=__doc__, # printed with -h/--help
      # Don't mess with format of description
      formatter_class=argparse.RawDescriptionHelpFormatter,
      # Turn off help, so we print all options in response to -h
      add_help=False
    )
    confparser.add_argument('--config', '-cf',
                            help='choose config file (default {0})'.format(ETBConfig.DEFAULT_CONFIG_FILE))
    args, remaining_argv = confparser.parse_known_args()
    self.config_file = args.config
    if args.config is None:
      self.config_file = ETBConfig.DEFAULT_CONFIG_FILE
    else:
      if not os.path.exists(self.config_file):
        print 'Config file {0} does not exist'.format(self.config_file)
        sys.exit(1)
    user_config_file = os.path.expanduser('~/' + ETBConfig.DEFAULT_CONFIG_FILE)
    cp = ConfigParser.RawConfigParser()
    cp.read([user_config_file, self.config_file])
    if cp.has_section('etb'):
      etbitems = dict(cp.items('etb')).iteritems()
      config = {k: os.path.expandvars(v) for k, v in etbitems}
    else:
      config = {}
    if cp.has_section('etbsh'):
      etbshitems = dict(cp.items('etbsh')).iteritems()
      config.update({k: os.path.expandvars(v) for k, v in etbshitems})
    # Now get the colorbg, to set the defaults for other colors
    cbgparser = argparse.ArgumentParser(parents=[confparser], add_help=False)
    cbgparser.add_argument('--colorbg', '-cbg', default=ETBSHConfig.DEFAULT_COLOR_BG,
                           help='select whether to assume "none", "dark", or "light" background (default %(default)s)')
    args, remaining_argv = cbgparser.parse_known_args(remaining_argv)
    # print 'cbgparser args = {0}'.format(args)
    self.set_colors_for_bg(args.colorbg)
    # print '        text color = {0}'.format(colorname(ETBSHConfig.DEFAULT_TEXT_COLOR))
    # print '        info color = {0}'.format(colorname(ETBSHConfig.DEFAULT_INFO_COLOR))
    # print '        debug color = {0}'.format(colorname(ETBSHConfig.DEFAULT_DEBUG_COLOR))
    # print '        warning color = {0}'.format(colorname(ETBSHConfig.DEFAULT_WARNING_COLOR))
    # print '        error color = {0}'.format(colorname(ETBSHConfig.DEFAULT_ERROR_COLOR))
    self.colorbg = args.colorbg
    # On to the rest of the args
    descr = 'Evidential Tool Bus Shell'
    parser = argparse.ArgumentParser(description=descr, parents=[cbgparser])
    # These (and --config) are shared with etbd;
    # anything not mentioned here is passed on to etbd
    parser.add_argument('--debuglevel', '-d',
                        choices=['debug', 'info', 'warning', 'Error', 'critical'],
                        default='info', help='debugging level (default: %(default)s)')
    parser.add_argument('--port', '-p', default=ETBConfig.DEFAULT_PORT,
                        help='port to listen on')
    # parser.add_argument('--logic-file', '-lf', default=ETBConfig.DEFAULT_LOGIC_FILE,
    #                     help='logic file for reading and saving claims')
    parser.add_argument('--git-working-dir', '-gd', default=ETBConfig.DEFAULT_GIT_DIR,
                        help='git working directory')
    parser.add_argument('--log', help='send log to LOG')
    # These are only for etbsh
    parser.add_argument('--clean', action='store_true', default=False,
                        help='Clear out earlier files (etb_claims and etb_git)')
    parser.add_argument('--load', '-l', action='append', help='load ETB shell script')
    parser.add_argument('--batch', action='store_true', default=False,
                        help='run in batch mode')
    parser.add_argument('--noetb', action='store_true', default=False,
                        help='Do not start etbd')
    parser.add_argument('--prompt-string', default=ETBSHConfig.DEFAULT_PROMPT_STRING,
                        help='etbsh prompt string'.format(ETBSHConfig.DEFAULT_PROMPT_STRING))
    parser.add_argument('--text-color', default=ETBSHConfig.DEFAULT_TEXT_COLOR,
                        help='plain text color {0}'.format(color_help_default(ETBSHConfig.DEFAULT_TEXT_COLOR)))
    parser.add_argument('--info-color', default=ETBSHConfig.DEFAULT_INFO_COLOR,
                        help='info message color {0}'.format(color_help_default(ETBSHConfig.DEFAULT_INFO_COLOR)))
    parser.add_argument('--debug-color', default=ETBSHConfig.DEFAULT_DEBUG_COLOR,
                        help='debug message color {0}'.format(color_help_default(ETBSHConfig.DEFAULT_DEBUG_COLOR)))
    parser.add_argument('--warning-color', default=ETBSHConfig.DEFAULT_WARNING_COLOR,
                        help='warning message color {0}'.format(color_help_default(ETBSHConfig.DEFAULT_WARNING_COLOR)))
    parser.add_argument('--error-color', default=ETBSHConfig.DEFAULT_ERROR_COLOR,
                        help='error message color {0}'.format(color_help_default(ETBSHConfig.DEFAULT_ERROR_COLOR)))
    parser.add_argument('--host', default='localhost', help='etb host')
    parser.add_argument('--name', '-n', default=None, help='etb name (used in proxying)')
    parser.set_defaults(**config)
    args, args_for_etb = parser.parse_known_args(remaining_argv)
    # print 'ETBSHConfig: args = {0}'.format(args)
    # print '     args_for_etb = {0}'.format(args)
    self.args_for_etb = args_for_etb
    #self.logic_file = os.path.abspath(args.logic_file)
    self.git_dir = os.path.abspath(args.git_working_dir)
    self.load = args.load
    self.debuglevel = args.debuglevel
    self.port = args.port
    self.log_file = args.log
    self.clean = args.clean
    self.batch = args.batch
    self.noetb = args.noetb
    self.host = args.host
    self.name = args.name
    self.text_color = args.text_color
    self.info_color = args.info_color
    self.debug_color = args.debug_color
    self.warning_color = args.warning_color
    self.error_color = args.error_color
    self.prompt_string = self.set_prompt(args.prompt_string)
    
  def set_prompt(self, prompt):
    """
    Sets the prompt string.  The string may have escapes:
    %p - port #
    %d - shell working directory
    %g - wrapper (Git) working directory
    %F(%f) - start/stop foreground color, e.g., %F{r}>%f
    %K(%k) - start/stop background color
    %S(%s) - start/stop color style, e.g., %S{b}bright%s
    Available colors: black(k), blue(b), cyan(c), green(g),
                      magenta(m), red(r), white(w), yellow(y)
    Available styles: normal(n), bright(b), dim(d)
    """
    if len(prompt) > 2:
      if ((prompt[0] == '"' and prompt[-1] == '"')
          or (prompt[0] == "'" and prompt[-1] == "'")):
        prompt = prompt[1:-1]
    prmpt = prompt.replace('%p', str(self.port))
    prmpt = prmpt.replace('%d', os.getcwd())
    prmpt = prmpt.replace('%g', self.git_dir)

    prmpt = prmpt.replace('%S{b}', '\x01' + Style.BRIGHT + '\x02')
    prmpt = prmpt.replace('%S{n}', '\x01' + Style.NORMAL + '\x02')
    prmpt = prmpt.replace('%S{d}', '\x01' + Style.DIM + '\x02')
    prmpt = prmpt.replace('%s', '\x01' + Style.RESET_ALL + '\x02')
    
    prmpt = prmpt.replace('%F{k}', '\x01' + Fore.BLACK + '\x02')
    prmpt = prmpt.replace('%F{b}', '\x01' + Fore.BLUE + '\x02')
    prmpt = prmpt.replace('%F{c}', '\x01' + Fore.CYAN + '\x02')
    prmpt = prmpt.replace('%F{g}', '\x01' + Fore.GREEN + '\x02')
    prmpt = prmpt.replace('%F{m}', '\x01' + Fore.MAGENTA + '\x02')
    prmpt = prmpt.replace('%F{r}', '\x01' + Fore.RED + '\x02')
    prmpt = prmpt.replace('%F{w}', '\x01' + Fore.WHITE + '\x02')
    prmpt = prmpt.replace('%F{y}', '\x01' + Fore.YELLOW + '\x02')
    prmpt = prmpt.replace('%f', '\x01' + Fore.RESET + '\x02')
    
    prmpt = prmpt.replace('%K{k}', '\x01' + Back.BLACK + '\x02')
    prmpt = prmpt.replace('%K{b}', '\x01' + Back.BLUE + '\x02')
    prmpt = prmpt.replace('%K{c}', '\x01' + Back.CYAN + '\x02')
    prmpt = prmpt.replace('%K{g}', '\x01' + Back.GREEN + '\x02')
    prmpt = prmpt.replace('%K{m}', '\x01' + Back.MAGENTA + '\x02')
    prmpt = prmpt.replace('%K{r}', '\x01' + Back.RED + '\x02')
    prmpt = prmpt.replace('%K{w}', '\x01' + Back.WHITE + '\x02')
    prmpt = prmpt.replace('%K{y}', '\x01' + Back.YELLOW + '\x02')
    prmpt = prmpt.replace('%k', '\x01' + Back.RESET + '\x02')
    return prmpt

  def set_colors_for_bg(self, bg):
    if bg == 'dark':
      # print 'setting dark colors'
      ETBSHConfig.DEFAULT_TEXT_COLOR    = Style.BRIGHT + Fore.WHITE
      ETBSHConfig.DEFAULT_INFO_COLOR    = Style.BRIGHT + Fore.YELLOW
      ETBSHConfig.DEFAULT_DEBUG_COLOR   = Style.BRIGHT + Fore.GREEN
      ETBSHConfig.DEFAULT_WARNING_COLOR = Style.BRIGHT + Fore.MAGENTA
      ETBSHConfig.DEFAULT_ERROR_COLOR   = Style.BRIGHT + Fore.RED
    elif bg == 'light':
      # print 'setting light colors'
      ETBSHConfig.DEFAULT_TEXT_COLOR    = Fore.BLACK
      ETBSHConfig.DEFAULT_INFO_COLOR    = Style.DIM + Fore.MAGENTA
      ETBSHConfig.DEFAULT_DEBUG_COLOR   = Style.DIM + Fore.GREEN
      ETBSHConfig.DEFAULT_WARNING_COLOR = Style.DIM + Fore.RED
      ETBSHConfig.DEFAULT_ERROR_COLOR   = Style.BRIGHT + Fore.RED
    elif bg != 'none':
      print '-cbg should be set to one of light, dark, or none - none assumed'

def color_help_default(colorstr):
  return '(default {0}, giving {1})'.format(colorstr.encode('string_escape'),
                                     colorstr + colorname(colorstr) + Style.RESET_ALL)

def colorname(str, name=''):
  if str.startswith(Style.BRIGHT):
    return colorname(str[4:], name + 'bright ')
  elif str.startswith(Style.DIM):
    return colorname(str[4:], name + 'dim ')
  elif str.startswith(Fore.BLACK):
    return colorname(str[5:], name + 'black foreground')
  elif str.startswith(Fore.BLUE):
    return colorname(str[5:], name + 'blue foreground')
  elif str.startswith(Fore.CYAN):
    return colorname(str[5:], name + 'cyan foreground')
  elif str.startswith(Fore.GREEN):
    return colorname(str[5:], name + 'green foreground')
  elif str.startswith(Fore.MAGENTA):
    return colorname(str[5:], name + 'magenta foreground')
  elif str.startswith(Fore.RED):
    return colorname(str[5:], name + 'red foreground')
  elif str.startswith(Fore.WHITE):
    return colorname(str[5:], name + 'white foreground')
  elif str.startswith(Fore.YELLOW):
    return colorname(str[5:], name + 'yellow foreground')
  elif str.startswith(Back.BLACK):
    return colorname(str[5:], name + 'black background')
  elif str.startswith(Back.BLUE):
    return colorname(str[5:], name + 'blue background')
  elif str.startswith(Back.CYAN):
    return colorname(str[5:], name + 'cyan background')
  elif str.startswith(Back.GREEN):
    return colorname(str[5:], name + 'green background')
  elif str.startswith(Back.MAGENTA):
    return colorname(str[5:], name + 'magenta background')
  elif str.startswith(Back.RED):
    return colorname(str[5:], name + 'red background')
  elif str.startswith(Back.WHITE):
    return colorname(str[5:], name + 'white background')
  elif str.startswith(Back.YELLOW):
    return colorname(str[5:], name + 'yellow background')
  else:
    return name
