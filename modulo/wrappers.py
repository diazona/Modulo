#!/usr/bin/python

from collections import defaultdict
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

class LazyCopyDict(dict):
    def __init__(self, parent, **kwargs):
        super(LazyCopyDict, self).__init__(**kwargs)
        self.__parent = parent

    def __str__(self):
        return str(self.__parent) + ' [LazyCopyDict]'

    def __missing__(self, key):
        return self.__parent[key]

class BranchMixin(object):
    def __copy__(self):
        copy = LazyCopy(self)
        copy.environ = LazyCopyDict(self.environ)
        return copy

class SessionMixin(object):
    # Designed so that the session subsystem is only initialized if req.session is accessed
    @cached_property
    def session(self):
        from modulo.session import session_store
        sid = self.cookie.get('sessionid')
        if sid:
            logging.getLogger('modulo.session').debug('restoring session')
            return session_store.get(sid)
        else:
            logging.getLogger('modulo.session').debug('initializing session')
            return session_store.new()

class ModuloRequest(WerkzeugRequest, LoggerMixin, BranchMixin, SessionMixin):
    def __init__(self, environ):
        WerkzeugRequest.__init__(self, environ)
        LoggerMixin.__init__(self)
        local.request = self

Request = ModuloRequest
Response = WerkzeugResponse

from modulo import local
