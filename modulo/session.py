# -*- coding: iso-8859-1 -*-

'''This module contains support code for HTTP sessions. It is built on the
``werkzeug.contrib.sessions`` module.'''

from werkzeug.contrib.sessions import FilesystemSessionStore
from modulo.actions import Action

session_store = FilesystemSessionStore()

class SessionSaver(Action):
    '''This :class:``Action`` causes the Werkzeug session object to save any
    data stored to it while processing the current request.'''
    def generate(self, rsp):
        if self.req.session.should_save:
            session_store.save(self.req.session)
