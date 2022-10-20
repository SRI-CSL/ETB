# from distutils.core import setup
from setuptools import setup, find_packages
import os
import glob

# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
# def read(fname):
#     return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
  name='EvidentialToolBus',
  version='1.0',
  author='Simon Cruanes, Gregoire Hamon, Stijn Heymans, Ian Mason, Sam Owre, N. Shankar',
  author_email='owre@csl.sri.com',
  #include_package_data = True,
  #packages=find_packages(exclude=['dist']),
  packages=find_packages(),
  # package_data = {
  #   'etb': ['demos/*'],
  # },
  data_files=[
    ('etb/demos/make',
     ['demos/make/make_rules', 'demos/make/etb-make.in',
      'demos/make/etb_conf.ini', 'demos/make/README'] +
     glob.glob('demos/make/*.[ch]')),
    ('etb/demos/make/wrappers', glob.glob('demos/make/wrappers/*.py')),
    ('etb/demos/allsat2',
     ['demos/allsat2/README', 'demos/allsat2/a.ys', 'demos/allsat2/allsat_rules',
      'demos/allsat2/etb_conf.ini']),
    ('etb/demos/allsat2/wrappers', glob.glob('demos/allsat2/wrappers/*.py')),
  ],
  entry_points = {
    'console_scripts': [
      'etbd = etb.etbd:main',
      'etbsh = etb.etbsh:main',
    ],
  },
  url='http://pypi.python.org/pypi/ETB/',
  license='LICENSE',
  description='The Evidential Tool Bus.',
  long_description=open(os.path.join(os.path.dirname(__file__), 'README')).read(),
  install_requires=[
    "argparse >= 1.1",
    "parsimonious >= 0.5",
    "pyparsing >= 2.0.0",
    "six >= 1.8.0",
    "dirsync >= 2.1",
    "pydot2 >= 1.0.33",
    "graphviz >= 0.2.2",
    "colorama >= 0.2.7",
    "pyreadline",
    "Twisted",
  ],
  classifiers=[
    'Development Status :: 3 - Alpha',
    'Natural Language :: English',
    'License :: OSI Approved :: GNU General Public License (GPL)',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 2.6',
    'Programming Language :: Python :: 2.7',
  ],
)
