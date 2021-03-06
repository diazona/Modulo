# -*- coding: utf-8 -*-

'''Core components of Modulo, including the WSGI application wrapper.

This module also imports :func:`all_of`, :func:`any_of`, and :func:`opt`
from :mod:`modulo.actions` and exports those names for convenience,
so you can write ::

    from modulo import all_of, any_of, opt

if you like.'''

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
    logging.getLogger('modulo.timer').info('processed in ' + str(t1 - t0) + ' seconds')
    return response

def WSGIModuloApp(action_tree, error_tree=None, raise_exceptions=False):
    '''A wrapper that creates a WSGI application from a Modulo action.

    ``action_tree`` is the action itself. It can be any subclass of
    :class:`modulo.actions.Action`. Typically it'll be a tree built up using the
    functions :func:`~modulo.all_of`, :func:`~modulo.any_of`, and :func:`~modulo.opt`,
    but you could use a single action if you want.

    The other arguments are optional, and both govern what happens if an uncaught
    exception is raised while the ``action_tree`` is being processed.
    If ``raise_exceptions`` is true, the exception will just be allowed to propagate
    up. This is useful when you want to use the web server's exception handling
    facilities, or if you're wrapping the WSGI application in some middleware that
    handles exceptions. For example, if you run the development server using
    ``manage.py runserver`` with the ``--debugger`` option, you'll need to set
    ``raise_exceptions=True``.

    .. todo:: Currently you can only do this by editing the source code to hard-code
        the parameter ``raise_exceptions=True`` into the call to ``WSGIModuloApp``.
        Sometime in the future there'll be a way to specify the value of
        ``raise_exceptions`` in the local settings file.

    If ``raise_exceptions`` is false, you can pass in an alternate action as
    ``error_tree``, and it will be used as an error handler. If an uncaught exception
    is raised during processing of ``action_tree``, the WSGI application will try using
    ``error_tree`` to process the request before falling back to the default behavior
    (which is provided by Werkzeug). The intent is that you can use this to display
    debugging information.

    .. todo:: There isn't actually any way to pass information about the error that
        occurred to the ``error_tree`` yet.
    '''
    @Request.application
    def modulo_application(request):
        '''A basic WSGI wrapper for the ``action_tree``.'''
        return run_everything(action_tree, request)

    if raise_exceptions:
        def simple_middleware(environ, start_response):
            '''A WSGI wrapper for the ``action_tree`` that traps certain exceptions
            which don't actually signal errors, and raises the rest.'''
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
            '''A WSGI wrapper for the ``action_tree`` that traps all exceptions.'''
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
            '''A basic WSGI wrapper for the ``error_tree``.'''
            return run_everything(error_tree, request)
        def nice_exception_middleware(environ, start_response):
            '''A WSGI wrapper for the ``action_tree`` that uses the ``error_tree`` to
            handle uncaught exceptions.'''
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
    '''Wraps the given exception ``e`` in a WSGI application and calls it
    with the given ``environ`` and ``start_response``.
    
    If the exception is a subclass of ``HTTPException`` it will be used
    as-is; otherwise its message gets extracted and wrapped in an
    ``InternalServerError``.'''
    if not isinstance(e, HTTPException):
        logging.getLogger('modulo').debug('Creating InternalServerError')
        e = InternalServerError(e.message)
    return e.get_response(environ)(environ, start_response)

__all__ = ['WSGIModuloApp', 'all_of', 'any_of', 'opt']
