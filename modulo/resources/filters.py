#!/usr/bin/python

import weakref
from modulo.resources import HashKey, Resource
from modulo.utilities import environ_next
from werkzeug.exceptions import NotFound

'''This module contains filter resources, which play no part in generating the response
except to limit which other resources respond to the request.'''

Filter = Resource

class URIFilter(Filter):
    '''A handler which only accepts requests that match a URI regular expression.

    This is primarily intended to be chained with other handlers to make them apply
    only to a particular URI path, not for subclassing.'''
    @classmethod
    def handles(cls, req):
        return bool(cls.__match(req.uri))

    @classmethod
    def __match(cls, string):
        if isinstance(cls.regex, (str, unicode)):
            cls.regex = re.compile(cls.regex)
        return cls.regex.match(string)

    def transform(self):
        match = self.__match(self.req.uri)
        if match.lastindex:
            for k, v in match.groupdict().iteritems():
                self.req.environ['modulo.urlparam.' + k] = v
            n = environ_next(self.req.environ, 'modulo.urlparam.%d')
            for i, v in enumerate(match.groups()):
                req.environ['modulo.urlparam.%d.%d' % (n, i)] = v

    regex = r'.*'

class URIPrefixFilter(Filter):
    '''A handler which only accepts requests with URIs starting with a string.

    This is a slightly optimized version of URIFilter for cases where the
    regular expression would just be a constant string matching at the beginning
    of the URI; this class uses str.startswith() instead of a regular expression.
    This is primarily intended to be chained with other handlers to make them apply
    only to a particular URI path, not for subclassing.'''
    @classmethod
    def handles(cls, req):
        if not req.uri.startswith(cls.prefix):
            return False
        uri_suffix = req.uri[len(cls.prefix):]
        return len(uri_suffix) == 0 or uri_suffix.startswith('/')

    prefix = ''

class URISuffixFilter(Filter):
    '''A handler which only accepts requests with URIs ending with a string.

    This is a slightly optimized version of URIFilter for cases where the
    regular expression would just be a constant string matching at the end
    of the URI; this class uses str.endswith() instead of a regular expression.
    This is primarily intended to be chained with other handlers to make them apply
    only to a particular URI path, not for subclassing.'''
    @classmethod
    def handles(cls, req):
        if not req.uri.endswith(cls.suffix):
            return False
        uri_prefix = req.uri[:len(cls.suffix)]
        return len(uri_prefix) == 0 or uri_suffix.endswith('/')

    suffix = ''

class URIPrefixConsumer(Filter):
    '''A handler which only accepts requests with URIs starting with a string.

    This is a slightly optimized version of URIFilter for cases where the
    regular expression would just be a constant string matching at the beginning
    of the URI; this class uses str.startswith() instead of a regular expression.
    This is primarily intended to be chained with other handlers to make them apply
    only to a particular URI path, not for subclassing.

    Unlike URIPrefixFilter, an instance of URIPrefixConsumer "consumes" the part
    of the URI that it matches, so that part of the URI will not be visible to
    other handlers down the line.'''
    @classmethod
    def handles(cls, req):
        if not req.uri.startswith(cls.prefix):
            return False
        uri_suffix = req.uri[len(cls.prefix):]
        if len(uri_suffix) == 0 or uri_suffix.startswith('/'):
            req.uri = uri_suffix
            return True
        else:
            return False

    prefix = ''

class WerkzeugMapFilter(Filter):
    '''A filter which acts like a Werkzeug routing map. The class expects to see
    an instance of werkzeug.routing.Map in the class variable wzmap (by default
    this is None, so you must create a subclass which has wzmap set to a meaningful
    value). The endpoints must be *resources*, not strings as Werkzeug recommends.
    This class works somewhat like an AnyResource where each subnode is a resource
    chain with a URIFilter. (The URIFilters correspond to Rules)

    Keep in mind that Werkzeug's routing algorithm always identifies exactly one
    endpoint (in this case, one resource), based on the URL alone. This is something
    to watch out for if you create a map where multiple rules can match a given URL:
    if the resource associated with the first rule doesn't handle the request, the
    WerkzeugMapFilter as a whole will reject the request. It won't backtrack and try
    the resources associated with the other matching rules. If this is a problem, use
    AnyResource with URIFilters, something like
        any_of(
            URIFilter.derive('/') & SomeResource,
            URIFilter.derive('/whatever') & OtherResource,
            URIFilter.derive('/foo') & BarResource
        )
    '''
    wzmap = None

    # Every handler class that gets added to the dictionary (in handles()) should eventually
    # be removed (in __call__()), but in case there's some leak by which that doesn't occur,
    # we don't want the dictionary to grow large. So we use weak references to the requests,
    # that way at the very latest, each dict entry will be deleted when the request is
    # finished processing.
    handler_cls_cache = weakref.WeakKeyDictionary()

    @classmethod
    def handles(cls, req):
        hk = HashKey(req)
        if hk in cls.handler_cls_cache:
            return True
        try:
            endpoint, arguments = cls.wzmap.bind_to_environ(req).match(req.path, req.method)
        except NotFound: # don't let this exception propagate because another resource might handle the request
            return False
        else:
            for k, v in arguments.iteritems():
                req.environ['modulo.urlparam.' + k] = v
            cls.handler_cls_cache[hk] = endpoint
            return True

    def __new__(cls, req):
        if cls.handles(req):
            return cls.handler_cls_cache.pop(HashKey(req))(req)
        else:
            return None
