#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# The setup code to create a new Modulo site...
# kind of equivalent to Django's django-admin.py

from __future__ import with_statement

import logging
import os.path
import random
import re
import shutil
import time
import webbrowser
import wsgiref.simple_server
from elixir import setup_all
from threading import Event, Thread
from werkzeug.templates import Template

from modulo import WSGIModuloApp, all_of, any_of
from modulo.actions import Action
from modulo.actions.filters import URIFilter
from modulo.actions.standard import ContentTypeAction, DateAction, FileResource
from modulo.templating.minitmpl import MiniTemplate
from modulo.utilities import compact

def in_thisd(filename):
    return os.path.join(os.path.dirname(__file__), filename)

def in_skeld(filename):
    return os.path.join(os.path.dirname(__file__), 'skeleton', filename)

def in_cwd(filename):
    return os.path.join(os.getcwd(), filename)

setting_defaults = [
    'admin_name',
    'admin_email',
    'database_url',
    'timezone',
    'email_from',
    'smtp_host',
    'smtp_port',
    'smtp_user',
    'smtp_pass',
    'smtp_use_tls',
    'sendmail_path',
    'sendmail_user',
    'sendmail_pass',
    'debug'
]

# Totally fake session management.
# We store the "session" variable, the settings dictionary, as a module-level
# variable; because this is a single-use, single-session server, a module
# variable is functionally the same as a session variable.
settings = {}

# create event to wait on
event = Event()

class DatabaseConfigurator(Action):
    def generate(self, rsp):
        global settings
        try:
            database_system = self.req.form['database_system']
            database_name = self.req.form['database_name']
            if database_system == 'sqlite':
                if database_name:
                    settings['database_url'] = '%s:///%s' % (database_system, database_name)
                else:
                    settings['database_url'] = '%s://' % (database_system)
            else:
                database_host = self.req.form['database_host']
                database_port = self.req.form.get('database_port', '')
                database_username = self.req.form['database_username']
                database_password = self.req.form['database_password']
                if database_port:
                    settings['database_url'] = '%s:///%s:%s@%s:%s/%s' % (database_system, database_username, database_password, database_host, database_port, database_name)
                else:
                    settings['database_url'] = '%s:///%s:%s@%s/%s' % (database_system, database_username, database_password, database_host, database_name)
        except KeyError:
            pass # just leave database_url unset if one of the necessary parameters isn't passed

class ConfigLoader(Action):
    def generate(self, rsp):
        global settings
        settings.update((name, self.req.form[name]) for name in setting_defaults if name in self.req.form)

class CheckExists(Action):
    @classmethod
    def handles(cls, req):
        return os.path.isfile(in_cwd('settings.py'))

    def generate(self, rsp):
        return {'filename': in_cwd('settings.py')}

class SkeletonWriter(Action):
    def generate(self, rsp, **kwargs):
        global settings
        kwargs['cfg_line'] = lambda s, d=None: s + ' = ' + repr(settings.get(s, d))
        for filename in ('launch.wsgi', 'app.py', 'settings.py', 'manage.py'):
            with open(in_cwd(filename), 'w') as f:
                # Template strips off trailing whitespace...
                f.write(Template.from_file(in_skeld(filename + '.tmpl')).render(**kwargs) + '\n')
        os.chmod(in_cwd('manage.py'), 0755)

class EventTrigger(Action):
    def generate(self, rsp):
        event.set()

def main(host='localhost'):
    logging.disable(logging.WARN)
    # create app
    app = WSGIModuloApp(all_of(
        DateAction,
        any_of(
            URIFilter(r'^/settings\.py$') & FileResource(in_cwd('settings.py')) & ContentTypeAction('text/x-python'),
            any_of(
                URIFilter(r'^/configure\.html$') & FileResource(in_thisd('configure.html')),
                URIFilter(r'^/reallyconfigurate$') & SkeletonWriter & FileResource(in_thisd('configured.html')) & EventTrigger,
                URIFilter(r'^/configurate$') & ConfigLoader & DatabaseConfigurator & any_of(
                    CheckExists & MiniTemplate(in_thisd('fileexists.html')),
                    SkeletonWriter & FileResource(in_thisd('configured.html')) & EventTrigger
                ),
                URIFilter(r'^/dontconfigurate$') & EventTrigger
            ) & ContentTypeAction('text/html'),
            ContentTypeAction & any_of(
                URIFilter(r'^/modulo_setup\.css$') & FileResource(in_thisd('modulo_setup.css')),
            )
        )
    ), raise_exceptions=True)
    # start server (TODO: make this an SSL server)
    port = random.randint(10000,60000)
    server = wsgiref.simple_server.make_server('localhost', port, app)
    thread = Thread(target=server.serve_forever)
    thread.setDaemon(True)
    thread.start()
    # start browser
    webbrowser.open('http://%s:%d/configure.html' % (host, port))
    # wait
    try:
        event.wait(1800)
    except KeyboardInterrupt:
        pass
    else:
        # make sure the server has the chance to handle the last request
        time.sleep(1)

__all__ = ['main']
