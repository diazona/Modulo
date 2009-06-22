#!/usr/bin/python

'''Basic components of Modulo.'''

from modulo.resources import all_of, any_of, opt
from werkzeug import Request, Response
from werkzeug.exceptions import HTTPException, InternalServerError, NotFound

__all__ = ['WSGIModuloApp', 'all_of', 'any_of', 'opt']

def WSGIModuloApp(response_tree, error_tree=None, raise_exceptions=False):
    @Request.application
    def modulo_application(request):
        # First try to generate a normal response
        root_resource = response_tree(request)
        if root_resource is None:
            raise NotFound
        response = Response()
        root_resource.generate(response)
        return response

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
            root_resource = error_tree(request)
            if root_resource is None:
                return _wsgi(e)
            response = Response()
            root_resource.generate(response)
            return response
        def nice_exception_middleware(environ, start_response):
            try:
                return modulo_application(environ, start_response)
            except:
                return modulo_exception(environ, start_response)
        return nice_exception_middleware

def _wsgi(e):
    if isinstance(e, HTTPException):
        return e
    else:
        return InternalServerError(e.message)
