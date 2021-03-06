# -*- coding: utf-8 -*-

'''Standard actions that are useful for the operation of a web server.'''

import dircache
import hashlib
import logging
import mimetypes
import os.path
import time
import warnings
from datetime import datetime
from modulo.actions import Action
from modulo.utilities import func_update
from os.path import isabs, isdir, isfile
from stat import ST_MTIME
from werkzeug import Template
from werkzeug import wrap_file
try:
    from werkzeug.http import http_date # Werkzeug 0.7
except ImportError:
    from werkzeug.utils import http_date # Werkzeug 0.6

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
    def derive(cls, filename=None, search_path=None, **kwargs):
        # search_path can be any iterable of strings, or a plain string
        if filename is None:
            return super(FileResource, cls).derive(search_path=search_path, **kwargs)
        elif isinstance(filename, basestring):
            if isabs(filename):
                # In this case the filename is completely specified so we can replace the builtin filename() method
                return super(FileResource, cls).derive(filename=classmethod(lambda cls, req, params: filename), search_path=search_path, **kwargs)
            else:
                # filename is a relative path, so don't replace the builtin filename
                return super(FileResource, cls).derive(rel_filename=filename, search_path=search_path, **kwargs)
        else:
            # Presumably filename is a callable which should replace the builtin filename() method
            return super(FileResource, cls).derive(filename=filename, search_path=search_path, **kwargs)

    @classmethod
    def filename(cls, req, params):
        search_path = getattr(cls, 'search_path', None)
        fn = getattr(cls, 'rel_filename', req.path.lstrip('/'))
        if isinstance(search_path, basestring):
            return cls.__filename(search_path, fn, req)
        else:
            try:
                for sp in search_path:
                    fnfull = cls.__filename(sp, fn, req)
                    if cls.__accept(fnfull):
                        return fnfull
            except TypeError:
                return cls.__filename(search_path, fn, req)
            return cls.__filename(None, fn, req)

    @staticmethod
    def __filename(sp, fn, req):
        if sp is None:
            if 'DOCUMENT_ROOT' in req.environ:
                sp = req.environ['DOCUMENT_ROOT']
            else:
                sp = os.getcwd()
        f= os.path.join(sp, fn)
        return f

    @classmethod
    def handles(cls, req, params):
        filename = cls.filename(req, params)
        logging.getLogger('modulo.actions.standard').debug('Checking file: ' + filename)
        return cls.__accept(filename)
        
    __accept = staticmethod(os.path.isfile)

    def __init__(self, req, params):
        super(FileResource, self).__init__(req, params)
        self.filename = self.filename(req, params)

    def last_modified(self):
        return datetime.utcfromtimestamp(os.stat(self.filename)[ST_MTIME])

    def generate(self, rsp):
        rsp.response = wrap_file(self.req.environ, open(self.filename))

class DirectoryResource(FileResource):
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
    def derive(cls, dirname=None, search_path=None, **kwargs):
        return super(DirectoryResource, cls).derive(filename=dirname, search_path=search_path, **kwargs)

    __accept = staticmethod(os.path.isdir)

    def generate(self, rsp):
        contents = dircache.listdir(self.filename)[:]
        dircache.annotate(self.filename, contents)
        rsp.data = Template('<html><head><title>Listing of ${dirname}</title></head>'
                            '<body><h1>Listing of <tt>${dirname}</tt></h1><ul><% for d in contents %><li><a href="${d}">${d}</a></li><% endfor %></ul></body></html>'
                            ).render(dirname=self.filename, contents=contents)

class DirectoryIndex(Action):
    '''An action that alters the environment to insert a filename at the end of
    the requested path.'''
    index='index.html'
    
    @classmethod
    def derive(cls, index):
        return super(DirectoryIndex, cls).derive(index=index)
        
    @classmethod
    def handles(cls, req, params):
        return req.environ['PATH_INFO'].endswith('/')
        
    def transform(self, environ):
        environ['PATH_INFO'] += self.index

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

    WSGI-compliant servers will add this header if it's not provided by the
    application, so it shouldn't really be necessary to use this action.'''
    def generate(self, rsp):
        rsp.date = datetime.utcnow()

class ContentTypeAction(Action):
    '''A handler which guesses and/or assigns a value for the Content-Type header.

    The guess is performed by the content_type class method. By default it uses
    the mimetypes module but it can be overridden by subclasses to do anything,
    even just returning a specific content type independent of the URL.'''
    @classmethod
    def content_type(cls, req):
        type_enc = mimetypes.guess_type(req.base_url)
        type_string = str(type_enc[0])
        if type_enc[1]:
            type_string += ' (encoding=' + type_enc[1] + ')'
        logging.getLogger('modulo.actions.standard').debug('Guessing content type ' + type_string)
        return type_enc

    @classmethod
    def derive(cls, content_type, content_encoding=''):
        return super(ContentTypeAction, cls).derive(content_type=lambda s, r: (content_type, content_encoding))

    def __init__(self, req, params):
        super(ContentTypeAction, self).__init__(req, params)
        self.content_type, self.content_encoding = self.content_type(req) # slight optimization

    def generate(self, rsp):
        if self.content_type:
            rsp.mimetype = self.content_type
        if self.content_encoding:
            rsp.content_encoding = self.content_encoding

class Expires(Action):
    '''An Action which sets the Expires header.'''
    @classmethod
    def derive(cls, expires, **kwargs):
        return super(Expires, cls).derive(expires=expires, **kwargs)
    def generate(self, rsp):
        if isinstance(self.expires, datetime):
            rsp.expires = self.expires
        else:
            # assume it's a timedelta
            rsp.expires = datetime.now() + self.expires

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
    the response if it exists. You can override this behavior by setting
    the content_length attribute (of an instance or subclass) to a particular
    number, in which case neither rsp.response nor rsp.data will be accessed.
    
    If the 'buffer' property is set to True, and if rsp.data is unset or of
    zero length, the action will read the generator rsp.response and buffer
    its contents into rsp.data, then set the content length from that.

    If you don't set the content_length class property, this action should *only*
    be chained after an action which sets rsp.data to the content to be sent
    back to the client, or after an action which sets rsp.response to something
    that can be safely buffered (if you set buffer=True). If you use this action
    before the content is determined, the Content-Length header will be set to an
    incorrect value, probably 0. Keep in mind that it's generally better to send
    no Content-Length header than to send one with the wrong value.'''
    @classmethod
    def derive(cls, content_length, buffer=False):
        super(ContentLengthAction, cls).derive(content_length=content_length, buffer=buffer)

    def generate(self, rsp):
        if hasattr(self, 'content_length'):
            rsp.content_length = self.content_length
        else:
            if getattr(self, 'buffer', False) and (not hasattr(rsp, 'data') or not rsp.data):
                rsp.data = ''.join(s for s in rsp.response)
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

class Redirect(Action):
    PERMANENT = 301
    FOUND     = 302
    SEE_OTHER = 303
    USE_PROXY = 305
    TEMPORARY = 307

    namespace='*'

    @classmethod
    def derive(cls, location, status_code=303, **kwargs):
        if status_code not in (301, 302, 303, 305, 307):
            raise ValueError('status_code must be one of 301, 302, 303, 305, or 307 (got %d)' % status_code)
        return super(Redirect, cls).derive(status_code=status_code, location=location, **kwargs)

    def generate(self, rsp, **kwargs):
        warnings.warn('Python code functionality in string templates will be removed for security', FutureWarning)
        rsp.location = Template(self.location).render(kwargs) # TODO: create a more secure miniature template system
        rsp.status_code = self.status_code
        
def list_or_value(v):
    if len(v) == 1:
        return v[0]
    else:
        return v

class RequestDataAggregator(Action):
    '''Transfers parameters from the request's POST data and query string to the
    parameter list. This is also a common base class for the versions that take
    POST data or GET data individually.'''
    keys = None

    @classmethod
    def derive(cls, *args, **kwargs):
        return super(RequestDataAggregator, cls).derive(keys=args, **kwargs)

    @classmethod
    def handles(cls, req, params):
        dct = cls.get_dict(req)
        if getattr(cls, 'keys', None) is not None:
            return all(k in dct for k in cls.keys)
        else:
            return bool(len(dct))

    @classmethod
    def get_dict(cls, req):
        return req.values

    def generate(self, rsp):
        d = self.get_dict(self.req)
        if self.keys:
            return dict((k, list_or_value(d.getlist(k))) for k in self.keys if k in d)
        else:
            return dict((k, list_or_value(v)) for (k,v) in d.iterlists())

class PostDataAggregator(RequestDataAggregator):
    '''Collects HTTP POST data from the request and adds it to the parameter list.
    
    It's probably not a good idea to use this when a large file is being uploaded,
    since the whole file contents will be loaded into memory.'''
    @classmethod
    def handles(cls, req, params):
        return req.method == 'POST' and super(PostDataAggregator, cls).handles(req, params)

    @classmethod
    def get_dict(cls, req):
        return req.form

class GetDataAggregator(RequestDataAggregator):
    '''Collects query string parameters from the request and adds them to the parameter list.'''
    @classmethod
    def get_dict(cls, req):
        return req.args

class Statics(Action):
    '''Injects a set of static parameters into the parameter list.'''
    @classmethod
    def derive(cls, namespace=None, **kwargs):
        if namespace:
            return super(Statics, cls).derive(namespace=namespace, cparams=kwargs)
        else:
            return super(Statics, cls).derive(cparams=kwargs)
    
    def parameters(self):
        return self.cparams
        
class DocumentRoot(Action):
    @classmethod
    def derive(cls, docroot, **kwargs):
        return super(DocumentRoot, cls).derive(docroot=docroot, **kwargs)

    def transform(self, environ):
        environ['DOCUMENT_ROOT'] = self.docroot
