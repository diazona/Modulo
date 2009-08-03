#!/usr/bin/python

from collections import defaultdict
from modulo.session import session_store
from logging import Logger, StreamHandler
from werkzeug import Request as WerkzeugRequest, Response as WerkzeugResponse
from werkzeug import cached_property

class LoggerMixin(object):
    def __init__(self):
        local.error_stream = self.environ['wsgi.errors']

class LazyCopy(object):
    def __init__(self, parent):
        self.__parent = parent

    def __str__(self):
        return str(self.__parent) + ' [LazyCopy]'

    def __getattr__(self, name):
        return getattr(self.__parent, name)

class BranchMixin(object):
    def __copy__(self):
        return LazyCopy(self)

class SessionMixin(object):
    @cached_property
    def session(self):
        sid = self.cookie.get('sessionid')
        if sid:
            return session_store.get(sid)
        else:
            return session_store.new()

class ModuloRequest(WerkzeugRequest, LoggerMixin, BranchMixin, SessionMixin):
    def __init__(self, environ):
        WerkzeugRequest.__init__(self, environ)
        LoggerMixin.__init__(self)
        local.request = self

Request = ModuloRequest
Response = WerkzeugResponse

from modulo import local
