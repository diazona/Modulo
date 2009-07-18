#!/usr/bin/python

'''Basic components of Modulo.'''

from modulo.actions import all_of, any_of, opt
from modulo.utilities import check_params
from modulo.wrappers import Request, Response
from werkzeug.exceptions import HTTPException, InternalServerError, NotFound

__all__ = ['WSGIModuloApp', 'all_of', 'any_of', 'opt']

def run_everything(tree, request):
    handler = tree.handle(request)
    if handler is None:
        raise NotFound()
    request.loggers['modulo'].debug('\n'+str(handler))
    response = Response()
    request.handler = handler
    args, kwargs = check_params(params = handler.parameters())
    handler.generate(response, *args, **kwargs)
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
