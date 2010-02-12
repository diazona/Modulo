#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

from distutils.core import setup

setup(
    name='Modulo',
    version='0.1.0a1',
    description='Python Web Development Framework',
    author='David Zaslavsky',
    author_email='diazona@ellipsix.net',
    url='http://www.ellipsix.net/modulo',
    packages=['modulo', 'modulo.actions', 'modulo.addons', 'modulo.setup', 'modulo.templating'],
    package_data={'modulo.setup': ['*.html', '*.css', 'skeleton/*.tmpl']},
    scripts=['modulo-setup.py'],
    classifiers=[
        'Development Status :: 1 - Planning',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
        'Topic :: Software Development :: Libraries :: Application Frameworks'
    ]
)