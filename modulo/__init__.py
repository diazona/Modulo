# -*- coding: iso-8859-1 -*-

'''Basic components of Modulo.'''

import logging
import sys
import time
from collections import defaultdict
from werkzeug import Local, LocalManager
from werkzeug.exceptions import HTTPException, InternalServerError, NotFound, _ProxyException

# fragment taken from timeit module
if sys.platform == "win32":
    # On Windows, the best timer is time.clock()
    timer = time.clock
else:
    # On most other platforms the best timer is time.time()
    timer = time.time

local = Local()
local_manager = LocalManager([local])
logging.basicConfig(stream=local('error_stream'))
local.error_stream = sys.stderr

# prevent the werkzeug logger from propagating messages because it has its own output scheme
#logging.getLogger('werkzeug').propagate = False

from modulo.actions import all_of, any_of, opt
from modulo.wrappers import Request, Response

def run_everything(tree, request):
    t0 = timer()
    handler = tree.handle(request, defaultdict(dict)) # This is where the parameter list gets constructed
    if handler is None:
        raise NotFound()
    logging.getLogger('modulo.actions').debug('\n'+str(handler))
    response = Response()
    request.handler = handler
    handler.generate(response)
    t1 = timer()
    logging.getLogger('modulo.timer').debug('processed in ' + str(t1 - t0) + ' seconds')
    return response

def WSGIModuloApp(action_tree, error_tree=None, raise_exceptions=False):
    @Request.application
    def modulo_application(request):
        return run_everything(action_tree, request)

    if raise_exceptions:
        def simple_middleware(environ, start_response):
            try:
                return modulo_application(environ, start_response)
            except NotFound, e:
                logging.getLogger('modulo').debug('Page not found')
                return _wsgi(e, environ, start_response)
            except (HTTPException, _ProxyException), e:
                return _wsgi(e, environ, start_response)
        return simple_middleware
    elif error_tree is None:
        def exception_middleware(environ, start_response):
            try:
                return modulo_application(environ, start_response)
            except NotFound, e:
                logging.getLogger('modulo').debug('Page not found')
                return _wsgi(e, environ, start_response)
            except (HTTPException, _ProxyException), e:
                return _wsgi(e, environ, start_response)
            except Exception, e:
                logging.getLogger('modulo').exception(e.__class__.__name__ + ': ' + e.message)
                return _wsgi(e, environ, start_response)
        return exception_middleware
    else:
        @Request.application
        def modulo_exception(request):
            return run_everything(error_tree, request)
        def nice_exception_middleware(environ, start_response):
            try:
                return modulo_application(environ, start_response)
            except (HTTPException, _ProxyException), e:
                return _wsgi(e, environ, start_response)
            except NotFound, e:
                logging.getLogger('modulo').debug('Page not found')
            except Exception, e:
                logging.getLogger('modulo').exception(e.__class__.__name__ + ': ' + e.message)
            try:
                return modulo_exception(environ, start_response)
            except (HTTPException, _ProxyException), e: #TODO: maybe HTTPExceptions from the error tree should be reraised as 500s
                return _wsgi(e, environ, start_response)
            except NotFound, e:
                logging.getLogger('modulo').error('Page not found in exception handler')
                return _wsgi(e, environ, start_response)
            except Exception, e:
                logging.getLogger('modulo').exception(e.__class__.__name__ + ': ' + e.message)
                return _wsgi(e, environ, start_response)
        return nice_exception_middleware

def _wsgi(e, environ, start_response):
    if not isinstance(e, HTTPException):
        logging.getLogger('modulo').debug('Creating InternalServerError')
        e = InternalServerError(e.message)
    return e.get_response(environ)(environ, start_response)

__all__ = ['WSGIModuloApp', 'all_of', 'any_of', 'opt']
