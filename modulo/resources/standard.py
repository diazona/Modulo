#!/usr/bin/python

'''Standard resources that are useful for the operation of a web server.'''

import hashlib
import mimetypes
import os.path
import time
from datetime import datetime
from modulo.resources import Resource
from os.path import isfile
from stat import ST_MTIME
from werkzeug.utils import http_date, wrap_file

class FileResource(Resource):
    '''A base class for a resource corresponding to a specific file.

    There are a couple of things that subclasses need to override. First, of
    course, the filename() class method, which returns the name of the file.
    Note that this method is actually run once when an instance of FileResource
    is constructed, and the return value is cached, so the filename computed
    for a given request can't change mid-processing. By default, filename()
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
        self.filename = self.filename(req) # slight optimization

    def last_modified(self):
        return datetime.utcfromtimestamp(os.stat(self.filename)[ST_MTIME])

    def generate(self, rsp):
        rsp.response = wrap_file(self.req.environ, open(self.filename))

class DynamicResource(Resource):
    '''A handler for "true dynamic" resources which should never be locally cached
    by clients.'''
    def generate(self, rsp):
        '''Sets this resource to be uncached.'''
        # smart HTTP/1.1 compatibility
        rsp.cache_control = 'no-cache'
        # stupid HTTP/1.1 (Firefox?) compatibility
        rsp.expires = 0
        # HTTP/1.0 compatibility
        rsp.headers['Pragma'] = 'no-cache'

class DateHeader(Resource):
    '''A handler which assigns the Date header to the request.

    This should probably be chained at the beginning of the handler tree, as
    it's required by HTTP/1.1 unless the server doesn't have a working clock.'''
    def generate(self, rsp):
        rsp.date = datetime.utcnow()

class ContentTypeHeader(Resource):
    '''A handler which guesses and/or assigns a value for the Content-Type header.

    The guess is performed by the content_type class method. By default it uses
    the mimetypes module but it can be overridden by subclasses to do anything,
    even just returning a specific content type independent of the URL.'''
    @classmethod
    def content_type(cls, req):
        return mimetypes.guess_type(req.url)

    def __init__(self, req):
        super(ContentTypeHeader, self).__init__(req)
        self.content_type, self.content_encoding = self.content_type(req) # slight optimization

    def generate(self, rsp):
        if self.content_type:
            rsp.mimetype = self.content_type
        if self.content_encoding:
            rsp.content_encoding = self.content_encoding

class CacheControl(Resource):
    '''A handler which checks whether it's appropriate to raise a NotModified exception.'''
    def generate(self, rsp):
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

class ContentLengthHeader(Resource):
    '''A resource to set the Content-Length header.

    By default, this just computes the length of the 'data' attribute of
    the response, though you can override this by setting the content_length
    attribute (of an instance or subclass) to a particular number.

    If you don't set the content_length attribute, this resource should *only*
    be chained after a resource which sets rsp.data to the content to be sent
    back to the client, otherwise the Content-Length header will be set to an
    incorrect value, probably 0. If your method of delivery is to set
    rsp.response to an iterator instead of setting rsp.data directly, this
    resource will *not* read the elements of the iterator to figure out what
    the length of the generated content is. Keep in mind that it's generally
    better to send no Content-Length header than to send one with the wrong
    value.'''
    def generate(self, rsp):
        if hasattr(self, content_length):
            rsp.content_length = self.content_length
        else:
            rsp.content_length = len(rsp.data)

class ContentMD5Header(Resource):
    '''A resource to set the Content-MD5 header.

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
    def generate(self, rsp):
        if hasattr(self, content_length):
            rsp.content_md5 = self.content_md5
        else:
            rsp.content_md5 = hashlib.md5(rsp.data).hexdigest()

# TODO: move this to a module somewhere
cache = None

class FullPageCache(Resource):
    '''A resource that pulls a full page from the cache, if it exists.'''
    def generate(self, rsp):
        c = cache.get('full_page' + self.req.root_resource.resource_id())
        if c:
            rsp.data = c
            return True