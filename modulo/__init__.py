#!/usr/bin/python

'''Basic components of Modulo.'''

from collections import defaultdict
from logging import Logger, StreamHandler
from modulo.actions import all_of, any_of, opt
from werkzeug import Request, Response
from werkzeug.exceptions import HTTPException, InternalServerError, NotFound

__all__ = ['WSGIModuloApp', 'all_of', 'any_of', 'opt']

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

def run_everything(tree, request):
    if not hasattr(request, 'logger_handler'):
        request.logger_handler = StreamHandler(request.environ['wsgi.errors'])
    if not hasattr(request, 'loggers'):
        request.loggers = LoggerDict(request)
    handler = tree.handle(request)
    if handler is None:
        raise NotFound()
    request.loggers['modulo'].debug(str(handler))
    response = Response()
    request.handler = handler
    handler.generate(response)
    return response

def WSGIModuloApp(action_tree, error_tree=None, raise_exceptions=False):
    @Request.application
    def modulo_application(request):
        # First try to generate a normal response
        return run_everything(action_tree, request)

    if raise_exceptions:
        def simple_middleware(environ, start_response):
            return modulo_application(environ, start_response)
        return simple_middleware
    elif error_tree is None:
        def exception_middleware(environ, start_response):
            try:
                return modulo_application(environ, start_response)
            except Exception, e:
                return _wsgi(e)(environ, start_response)
        return exception_middleware
    else:
        # Otherwise create a nice error page
        @Request.application
        def modulo_exception(request):
            return run_everything(error_tree, request)
        def nice_exception_middleware(environ, start_response):
            try:
                return modulo_application(environ, start_response)
            except Exception, e:
                try:
                    return modulo_exception(environ, start_response)
                except NotFound:
                    return _wsgi(e)
        return nice_exception_middleware

def _wsgi(e):
    if isinstance(e, HTTPException):
        return e
    else:
        return InternalServerError(e.message)
