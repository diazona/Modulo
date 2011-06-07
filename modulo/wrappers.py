# -*- coding: iso-8859-1 -*-

'''This module defines the request and response classes as subclasses of
those from Werkzeug. Normally there is no need to use this module except
perhaps to import ``Request`` and ``Response``.'''

import logging
from collections import defaultdict
from logging import Logger, StreamHandler
from werkzeug import Request as WerkzeugRequest, Response as WerkzeugResponse
from werkzeug import cached_property

class LoggerMixin(object):
    def __init__(self):
        local.error_stream = self.environ['wsgi.errors']

class SessionMixin(object):
    # Designed so that the session subsystem is only initialized if req.session is accessed
    @cached_property
    def session(self):
        from modulo.session import session_store
        sid = self.cookies.get('sessionid', None)
        if sid:
            logging.getLogger('modulo.session').debug('restoring session')
            return session_store.get(sid)
        else:
            logging.getLogger('modulo.session').debug('initializing session')
            return session_store.new()

class ModuloRequest(WerkzeugRequest, LoggerMixin, SessionMixin):
    '''A subclass of ``WerkzeugRequest`` that adds logging and session management.'''
    def __init__(self, environ):
        WerkzeugRequest.__init__(self, environ)
        LoggerMixin.__init__(self)
        local.request = self

Request = ModuloRequest
Response = WerkzeugResponse

from modulo import local
