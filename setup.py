#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distutils.core import setup

long_description = None
try:
    with open('README.txt') as f:
        long_description = f.read()
except IOError:
    pass

setup(
    name='Modulo',
    version='0.1.2',
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
    ]
)
