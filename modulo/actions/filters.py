# -*- coding: iso-8859-1 -*-

import logging
import re
import weakref
from types import ClassType
from modulo.actions import Action, AllActions, HashKey
from modulo.actions import accept_fmt, reject_fmt
from modulo.utilities import environ_next, uri_path
from werkzeug import pop_path_info
from werkzeug.exceptions import NotFound

'''This module contains filter actions, which play no part in generating the response
except to limit which other actions respond to the request.'''

class URIFilter(Action):
    '''A handler which only accepts requests that match a URI regular expression.

    This is primarily intended to be chained with other handlers to make them apply
    only to a particular URI path, not for subclassing. In other words, the typical
    usage looks like ::
    
        all_of(
            URIFilter('/test/path.html'),
            other_action,
            another_action
        )
    '''
    @classmethod
    def handles(cls, req, params):
        return bool(cls.__match(req.environ['PATH_INFO']))

    @classmethod
    def __match(cls, string):
        if isinstance(cls.regex, (str, unicode)):
            cls.regex = re.compile(cls.regex)
        return cls.regex.match(string)

    @classmethod
    def derive(cls, regex):
        return super(URIFilter, cls).derive(regex=regex)

    def parameters(self):
        match = self.__match(self.req.environ['PATH_INFO'])
        if match.lastindex:
            return match.groupdict()

class URIPrefixFilter(Action):
    '''A handler which only accepts requests with URIs starting with a string.

    This is a slightly optimized version of URIFilter for cases where the
    regular expression would just be a constant string matching at the beginning
    of the URI; this class uses str.startswith() instead of a regular expression.
    This is primarily intended to be chained with other handlers to make them apply
    only to a particular URI path, not for subclassing.'''
    @classmethod
    def handles(cls, req, params):
        return cls.__prefix(req.environ['PATH_INFO']) != False
        
    @classmethod
    def __prefix(cls, path):
        for prefix in cls.prefixes:
            if path.startswith(prefix):
                if prefix.endswith('/'):
                    return prefix
                else:
                    url_prefix = path[len(prefix):]
                    if len(url_prefix) == 0 or url_prefix.startswith('/'):
                        return prefix
        return False

    def __init__(self, req, params):
        self.prefix = self.__prefix(req.environ['PATH_INFO'])
        super(URIPrefixFilter, self).__init__(req, params)

    @classmethod
    def derive(cls, *prefixes, **kwargs):
        return super(URIPrefixFilter, cls).derive(prefixes=prefixes, **kwargs)

class URISuffixFilter(Action):
    '''A handler which only accepts requests with URIs ending with a string.

    This is a slightly optimized version of URIFilter for cases where the
    regular expression would just be a constant string matching at the end
    of the URI; this class uses str.endswith() instead of a regular expression.
    This is primarily intended to be chained with other handlers to make them apply
    only to a particular URI path, not for subclassing.'''
    @classmethod
    def handles(cls, req, params):
        return cls.__suffix(req.environ['PATH_INFO']) != False
        
    @classmethod
    def __suffix(cls, path):
        for suffix in cls.suffixes:
            if path.endswith(suffix):
                if suffix.startswith('.') or suffix.startswith('/'):
                    return suffix
                else:
                    url_suffix = path[:-len(suffix)]
                    if len(url_suffix) == 0 or url_suffix.endswith('/'):
                        return suffix
        return False

    def __init__(self, req, params):
        self.suffix = self.__suffix(req.environ['PATH_INFO'])
        super(URISuffixFilter, self).__init__(req, params)

    @classmethod
    def derive(cls, *suffixes, **kwargs):
        return super(URISuffixFilter, cls).derive(suffixes=suffixes, **kwargs)

class URIPrefixConsumer(URIPrefixFilter):
    '''A handler which only accepts requests with URIs starting with a string.

    Unlike URIPrefixFilter, an instance of URIPrefixConsumer "consumes" the part
    of the URI that it matches, so that part of the URI will not be visible to
    other handlers down the line.'''
    def transform(self, environ):
        # kind of like Werkzeug's pop_path_info, but instead of moving one segment
        # over, we move over the entire matched prefix
        environ['PATH_INFO'] = environ['PATH_INFO'][len(self.prefix):]
        environ['SCRIPT_NAME'] += self.prefix

class URISuffixConsumer(URISuffixFilter):
    '''A handler which only accepts requests with URIs ending with a string.

    Unlike URISuffixFilter, an instance of URISuffixConsumer "consumes" the part
    of the URI that it matches, so that part of the URI will not be visible to
    other handlers down the line.
    
    Unlike URIPrefixFilter, the removed part of the path is NOT appended to
    req.environ['SCRIPT_NAME'].'''
    def transform(self, environ):
        # kind of like Werkzeug's pop_path_info, but instead of moving one segment
        # over, we move over the entire matched prefix
        environ['PATH_INFO'] = environ['PATH_INFO'][:-len(self.suffix)]

class WerkzeugMapFilter(Action):
    '''A filter which acts like a Werkzeug routing map.

    The class expects to see an instance of ``werkzeug.routing.Map`` in the class
    variable routing_map (i.e. passed to the constructor). The ``Map`` instance can
    have as its endpoints either Actions or strings (or a mixture of both). If
    any of the endpoints are strings, you need to provide an additional parameter,
    action_map, which is a dict mapping strings to Actions.

    Keep in mind that Werkzeug's routing algorithm always identifies exactly one
    endpoint (in this case, one resource), based on the URL alone. This is something
    to watch out for if you create a map where multiple rules can match a given URL:
    if the resource associated with the first rule doesn't handle the request, the
    WerkzeugMapFilter as a whole will reject the request. It won't backtrack and try
    the resources associated with the other matching rules. If this is a problem, use
    AnyAction with URIFilters, something like ::

        any_of(
            URIFilter('/') & SomeAction,
            URIFilter('/whatever') & OtherAction,
            URIFilter('/foo') & BarAction
        )
    '''
    @classmethod
    def handles(cls, req, params):
        return True

    def __new__(cls, req, params):
        try:
            map_adapter = cls.routing_map.bind_to_environ(req)
            endpoint, arguments = map_adapter.match(req.path, req.method)
        except NotFound: # don't let this exception propagate because another resource might handle the request
            return None
        else:
            logging.getLogger('modulo.actions.filters').debug('WerkzeugMapFilter got endpoint ' + repr(endpoint))
            if not isinstance(endpoint, ClassType) or not issubclass(endpoint, Action):
                endpoint = cls.action_map[endpoint]
            ns = getattr(cls, 'namespace', '') # namespace='*' is not implemented here
            if arguments:
                ns_params = params[ns].copy()
                params = params.copy()
                params[ns] = ns_params
                ns_params.update(arguments)
            else:
                ns_params = params[ns]
            h = endpoint.handle(req, params)
            if h is None:
                return None
            params[ns]['map_adapter'] = map_adapter
            h.params = params
            return h

    @classmethod
    def derive(cls, routing_map, action_map=None):
        return super(WerkzeugMapFilter, cls).derive(routing_map=routing_map, action_map=action_map)
