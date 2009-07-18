#!/usr/bin/python

from collections import defaultdict
from logging import Logger, StreamHandler
from werkzeug import Request as WerkzeugRequest, Response as WerkzeugResponse

class WSGILogger(Logger):
    def __init__(self, name, req): # DO NOT call logging.setLoggerClass() with this
        Logger.__init__(self, name)
        self.addHandler(req.logger_handler)

class LoggerDict(defaultdict):
    def __init__(self, req):
        super(LoggerDict, self).__init__(lambda x: None)
        self.req = req

    def __missing__(self, key):
        return WSGILogger(key, self.req)

class LoggerMixin(object):
    def __init__(self):
        self.logger_handler = StreamHandler(self.environ['wsgi.errors'])
        self.loggers = LoggerDict(self)

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

class ModuloRequest(WerkzeugRequest, LoggerMixin, BranchMixin):
    def __init__(self, environ):
        WerkzeugRequest.__init__(self, environ)
        LoggerMixin.__init__(self)

Request = ModuloRequest
Response = WerkzeugResponse