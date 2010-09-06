#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os.path

from distutils.core import setup

cmdclass = {}
command_options = {}

# The distribution build script git-dist.sh depends on having this exact line
# in the file. Don't change it! (Except to update the version number)
version='0.1.3'

try:
    from sphinx.setup_command import BuildDoc
except ImportError:
    pass
else:
    cmdclass['build_sphinx'] = BuildDoc
    command_options['build_sphinx'] = {
        'version': ('setup.py', version),
        'release': ('setup.py', version),
        'build_dir': ('setup.py', os.path.abspath('build/share/docs')),
        'config_dir': ('setup.py', os.path.abspath('docs'))
    }

long_description = None
try:
    with open('README.txt') as f:
        long_description = f.read()
except IOError:
    pass

setup(
    name='Modulo',
    version=version,
    description='A Python web framework which constructs websites from reusable code snippets.',
    long_description=long_description,
    author='David Zaslavsky',
    author_email='diazona@ellipsix.net',
    url='http://www.ellipsix.net/devweb/modulo/index.html',
    packages=['modulo', 'modulo.actions', 'modulo.addons', 'modulo.setup', 'modulo.templating', 'modulo.utilities'],
    package_data={'modulo.setup': ['*.html', '*.css', 'skeleton/*.tmpl']},
    scripts=['modulo-setup.py'],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Internet :: WWW/HTTP :: WSGI',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    cmdclass=cmdclass,
    command_options=command_options
)
