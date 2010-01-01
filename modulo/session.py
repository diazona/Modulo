# -*- coding: iso-8859-1 -*-

from werkzeug.contrib.sessions import FilesystemSessionStore
from modulo.actions import Action

session_store = FilesystemSessionStore()

class SessionSaver(Action):
    def generate(self, rsp):
        if self.req.session.should_save:
            session_store.save(self.req.session)
