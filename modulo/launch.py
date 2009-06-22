#!/usr/bin/python

'''The actual WSGI web application for Modulo'''

#import cgi
#import datetime
#import sys
#from modulo.utilities import hash_iterable
#from urllib import quote
from werkzeug import Request, Response
from werkzeug.exceptions import HTTPException, InternalServerError, NotFound

__all__ = ['ModuloApplication']

def ModuloApplication(response_tree, error_tree=None):
    @Request.application
    def application(self, request):
        def run_everything(tree):
            root_resource = tree(request)
            if root_resource is None:
                raise NotFound()
            response = Response()
            request.root_resource = root_resource
            root_resource.generate(response)
            return response

        try:
            # First try to generate a normal response
            return run_everything(response_tree)
        except Exception, e:
            # If that fails, generate an error response
            if error_tree is None:
                return wrap_raise(e)
            else:
                return run_everything(error_tree)
    return application

def wrap_raise(e):
    if isinstance(e, HTTPException):
        return e
    else:
        return InternalServerError(e.message)
