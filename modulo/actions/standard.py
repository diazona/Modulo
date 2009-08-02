#!/usr/bin/python

'''Standard action that are useful for the operation of a web server.'''

import dircache
import hashlib
import mimetypes
import os.path
import time
from datetime import datetime
from modulo.actions import Action
from modulo.utilities import func_update
from os.path import isdir, isfile
from stat import ST_MTIME
from werkzeug import Template
from werkzeug.utils import http_date, wrap_file

class FileResource(Action):
    '''A base class for an action that reads the contents of a file.

    There are a couple of things that subclasses need to override. First, of
    course, the filename() class method, which returns the name of the file.
    Note that this method is actually run once when an instance of FileResource
    is constructed, and the return value is cached, so the filename computed
    for a given request doesn't change mid-processing. By default, filename()
    joins the document root (or, failing that, the current directory) to
    the URL path, the same way a static file server does.

    The other thing to override is generate() which specifies what to actually
    do with the file. The default implementation just sets the response
    to a file wrapper (of PEP 333's "Optional Platform-Specific File Handling")
    so that the file's contents will be sent as the response body. Note that
    you'll almost *never* actually want to do this in a subclass. If there is
    any other resource after FileResource in the chain that sets the response
    body, the file wrapper (and thus the open filehandle) will be lost! Typically
    a subclass would read the contents of the file and incorporate it into
    the response somehow.

    The point of the defaults being set up as they are is that FileResource by
    itself can be used as a static file server (albeit an inefficient one).'''
    @classmethod
    def derive(cls, filename):
        if isinstance(filename, (str, unicode)):
            return super(FileResource, cls).derive(filename=classmethod(lambda cls, req: filename))
        else:
            return super(FileResource, cls).derive(filename=filename)

    @classmethod
    def filename(cls, req):
        return cls.request_filename(req)

    @staticmethod
    def request_filename(req):
        if 'DOCUMENT_ROOT' in req.environ:
            docroot = req.environ['DOCUMENT_ROOT']
        else:
            docroot = os.getcwd()
        return os.path.join(docroot, req.path.lstrip('/'))

    @classmethod
    def handles(cls, req):
        return isfile(cls.filename(req))

    def __init__(self, req):
        super(FileResource, self).__init__(req)
        self.filename = self.filename(req)

    def last_modified(self):
        return datetime.utcfromtimestamp(os.stat(self.filename)[ST_MTIME])

    def generate(self, rsp):
        rsp.response = wrap_file(self.req.environ, open(self.filename))

class DirectoryResource(Action):
    '''A base class for an action that returns a directory listing.

    As with FileResource, there are two things for subclasses to override.
    There's the dirname() class method, which returns the name of the directory.
    Like FileResource, the value is cached when an instance is constructed.

    The other thing to override is generate() which specifies what to do with
    the directory listing. The default implementation just sets the data attribute
    of the response to an HTML page listing the directory contents. You might want
    to override this to assign the file names and properties to the template data
    structure, and provide a template (in your system of choice) to display the
    directory contents.'''
    @classmethod
    def dirname(cls, req):
        return cls.request_dirname(req)

    @staticmethod
    def request_dirname(req):
        if 'DOCUMENT_ROOT' in req.environ:
            docroot = req.environ['DOCUMENT_ROOT']
        else:
            docroot = os.getcwd()
        return os.path.join(docroot, req.path.lstrip('/'))

    @classmethod
    def handles(cls, req):
        return isdir(cls.dirname(req))

    def __init__(self, req):
        super(DirectoryResource, self).__init__(req)
        self.dirname = self.dirname(req) # slight optimization

    def last_modified(self):
        return datetime.utcfromtimestamp(os.stat(self.dirname)[ST_MTIME])

    def generate(self, rsp):
        contents = dircache.listdir(self.dirname)[:]
        dircache.annotate(self.dirname, contents)
        rsp.data = Template('<html><head><title>Listing of ${dirname}</title></head>'
                            '<body><h1>Listing of <tt>${dirname}</tt></h1><ul><% for d in contents %><li><a href="${d}">${d}</a></li><% endfor %></ul></body></html>'
                            ).render(dirname=self.dirname, contents=contents)

class NoCacheAction(Action):
    '''An action which sets the headers to disable caching by clients.'''
    def generate(self, rsp):
        '''Sets this resource to be uncached.'''
        # smart HTTP/1.1 compatibility
        rsp.cache_control = 'no-cache'
        # stupid HTTP/1.1 (Firefox?) compatibility
        rsp.expires = 0
        # HTTP/1.0 compatibility
        rsp.headers['Pragma'] = 'no-cache'

class DateAction(Action):
    '''An action which assigns the Date header to the response.

    This should probably be chained at the beginning of the handler tree, as
    it's required by HTTP/1.1 unless the server doesn't have a working clock.'''
    def generate(self, rsp):
        rsp.date = datetime.utcnow()

class ContentTypeAction(Action):
    '''A handler which guesses and/or assigns a value for the Content-Type header.

    The guess is performed by the content_type class method. By default it uses
    the mimetypes module but it can be overridden by subclasses to do anything,
    even just returning a specific content type independent of the URL.'''
    @classmethod
    def content_type(cls, req):
        return mimetypes.guess_type(req.url)

    @classmethod
    def derive(cls, content_type, content_encoding=''):
        return super(ContentTypeAction, cls).derive(content_type=lambda s, r: (content_type, content_encoding))

    def __init__(self, req):
        super(ContentTypeAction, self).__init__(req)
        self.content_type, self.content_encoding = self.content_type(req) # slight optimization

    def generate(self, rsp):
        if self.content_type:
            rsp.mimetype = self.content_type
        if self.content_encoding:
            rsp.content_encoding = self.content_encoding

class CacheControl(Action):
    '''An Action which checks whether it's appropriate to raise a NotModified exception.'''
    def generate(self, rsp):
        # checks etag
        rsp.make_conditional(self.req)
        #mtime = self.req.root_resource.last_modified()
        #etag = self.req.root_resource.resource_id()
        #if 'If-Modified-Since' in self.req.request_headers:
            #if mtime <= http_date(self.req.request_headers['If-Modified-Since']):
                #raise NotModified
        #if 'If-Unmodified-Since' in self.req.request_headers:
            #if mtime > http_date(self.req.request_headers['If-Unmodified-Since']):
                #raise PreconditionFailed
        #if 'If-None-Match' in self.req.request_headers:
            #if etag == self.req.request_headers['If-None-Match']:
                #if self.req.method in ('GET', 'HEAD'):
                    #raise NotModified
                #else:
                    #raise PreconditionFailed
        #if 'If-Match' in self.req.request_headers:
            #if etag != self.req.request_headers['If-Match']:
                #raise PreconditionFailed
        #if 'If-Range' in self.req.request_headers:
            #try:
                #range_date = http_date(self.req.request_headers['If-Range'])
            #except ValueError:
                #range_etag = self.req.request_headers['If-Range'].strip('"')
                ##if etag == range_etag:
                    ## send partial content
                ## else send full content
            #else:
                #if mtime <= range_date:
                    #raise NotModified
        #self.req.response_headers['Last-Modified'] = http_date(mtime)
        #self.req.response_headers['ETag'] = '"%s"' % self.req.resource_root.resource_id()

class ContentLengthAction(Action):
    '''An Action to set the Content-Length header.

    By default, this just computes the length of the 'data' attribute of
    the response, though you can override this by setting the content_length
    attribute (of an instance or subclass) to a particular number.

    If you don't set the content_length class property, this resource should *only*
    be chained after a resource which sets rsp.data to the content to be sent
    back to the client, otherwise the Content-Length header will be set to an
    incorrect value, probably 0. If your method of delivery is to set
    rsp.response to an iterator instead of setting rsp.data directly, this
    resource will *not* read the elements of the iterator to figure out what
    the length of the generated content is. Keep in mind that it's generally
    better to send no Content-Length header than to send one with the wrong
    value.'''
    @classmethod
    def derive(cls, content_length):
        super(ContentLengthAction, cls).derive(content_length=content_length)

    def generate(self, rsp):
        if hasattr(self, content_length):
            rsp.content_length = self.content_length
        else:
            rsp.content_length = len(rsp.data)

class ContentMD5Action(Action):
    '''An action to set the Content-MD5 header.

    By default, this just computes the hash of the 'data' attribute of
    the response, though you can override this by setting the content_md5
    attribute (of an instance or subclass) to a particular number.

    If you don't set the content_md5 attribute, this resource should *only*
    be chained after a resource which sets rsp.data to the content to be sent
    back to the client, otherwise the Content-MD5 header will be set to an
    incorrect value. If your method of delivery is to set rsp.response to an
    iterator instead of setting rsp.data directly, this resource will *not*
    read the elements of the iterator to figure out what the length of the
    generated content is.'''
    @classmethod
    def derive(cls, content_md5):
        super(ContentMD5Action, cls).derive(content_md5=content_md5)

    def generate(self, rsp):
        if hasattr(self, content_length):
            rsp.content_md5 = self.content_md5
        else:
            rsp.content_md5 = hashlib.md5(rsp.data).hexdigest()

class WerkzeugCanonicalizer(Action):
    '''Sets the canonical URL based on a MapAdapter produced by a previous Werkzeug router.

    This needs to be chained after a WerkzeugMapFilter.'''
    def generate(self, rsp, map_adapter, canonicalize=None):
        def werkzeug_canonicalize(url, method='GET'):
            c_endpoint, c_args = map_adapter.match(url, method)
            return map_adapter.build(c_endpoint, c_args, method)
        canonicalize = func_update(werkzeug_canonicalize, canonicalize)
        return {'canonicalize': canonicalize, 'canonical_uri': canonicalize(self.req.path)}

class NoopCanonicalizer(Action):
    '''Sets the canonical URL based on the actual URL.'''
    def generate(self, rsp, canonicalize=None):
        def noop_canonicalize(url, method='GET'):
            return url
        canonicalize = func_update(noop_canonicalize, canonicalize)
        return {'canonicalize': canonicalize, 'canonical_uri': canonicalize(self.req.path)}

from modulo.session import session_store

class SessionSaver(Action):
    def generate(self, rsp):
        if self.req.session.should_save:
            session_store.save(self.req.session)
