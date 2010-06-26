# -*- coding: utf-8 -*-

'''Linkback handling.'''

import datetime
import modulo.database
from elixir import session
from elixir import Entity, Field, Unicode, UnicodeText
from modulo.actions import Action, all_of, any_of
from modulo.actions.standard import ContentTypeAction
from modulo.utilities import compact
from HTMLParser import HTMLParser
from sqlalchemy.exceptions import SQLError
from werkzeug.exceptions import BadRequest

#---------------------------------------------------------------------------
# Database models
#---------------------------------------------------------------------------
class Linkback(Entity):
    local_host = Field(Unicode(128))
    local_uri = Field(Unicode(1024))
    remote_url = Field(Unicode(1024))
    remote_title = Field(Unicode(256))
    remote_excerpt = Field(UnicodeText)
    remote_name = Field(Unicode(256))

#---------------------------------------------------------------------------
# Linkback handling
#---------------------------------------------------------------------------
class LinkbackHTMLParser(HTMLParser):
    '''A parser that extracts information from the page at the target of a link.'''
    def __init__(self, targetURI):
        HTMLParser.__init__(self)
        self.targetURI = targetURI
        self.grabtitle = False
        self.linkpos = 0
        self.title = ''

    def handle_starttag(self, tag, attrs):
        if tag == 'title':
            self.grabtitle = True
        elif tag == 'a' and not self.linkpos and ('href', self.targetURI) in attrs:
            self.linkpos = self.getpos()

    def handle_endtag(self, tag):
        if self.grabtitle and tag == 'title':
            self.grabtitle = False

    def handle_data(self, data):
        if self.grabtitle:
            self.title += data

    def handle_charref(self, name):
        if self.grabtitle:
            self.title += '&#' + name + ';'

    def handle_entityref(self, name):
        if self.grabtitle:
            self.title += '&' + name + ';'

class TrackbackAssembler(Action):
    '''Assembles the data submitted in a request for a trackback.'''
    def generate(self, rsp, canonical_uri, url=None, title=None, excerpt=None, blog_name=None):
        linkback = Linkback()
        linkback.local_uri = canonical_uri
        linkback.remote_url = url
        if not linkback.local_uri:
            linkback_error = 'No target URL specified'
        elif not linkback.remote_url:
            linkback_error = 'No linking URL specified'
        elif self.req.method != 'POST':
            linkback_error = 'HTTP POST method not used'
        else:
            linkback.local_host = self.req.host
            linkback.remote_title = title
            linkback.remote_excerpt = excerpt
            linkback.remote_name = blog_name
        return compact('linkback')

class PingbackURIAssembler(Action):
    '''Assembles the data submitted in a request for a pingback.'''
    def generate(self, rsp):
        xml_request = self.req.read()
        try:
            (source_uri, target_uri), method = xmlrpclib.loads(xml_request)
        except ExpatError:
            raise BadRequest('Expecting XML-RPC request')
        if method != 'pingback.ping':
            return {'fault': Fault(-32601, 'Method %s not supported' % method)}
        linkback = Linkback()
        linkback.local_host = self.req.host
        linkback.local_uri = urlparse.urlsplit(canonicalize(target_uri)).path
        linkback.remote_url = source_uri
        return compact('linkback')

class LinkbackFetcher(Action):
    '''Fetches the content of the source page of a linkback request and verifies that
    it does actually contain a link to your site.'''
    @classmethod
    def derive(cls, set_title=False):
        return super(LinkbackFetcher, cls).derive(set_title=set_title)
        
    def generate(self, rsp, linkback, fault=None):
        if fault:
            return
        # fetch the source uri
        source_uri = linkback.remote_url
        urlf = None
        try:
            urlf = urllib.urlopen()
            content = urlf.read()
            ctype = urlf.info().gettype()
        except IOError:
            return {'fault': Fault(16, 'Could not open source URI %s' % sourceURI)}
        finally:
            if urlf:
                urlf.close()
        if ctype in ('text/html', 'application/xhtml+xml', 'text/xml'):
            hp = PingbackHTMLParser(targetURI)
            hp.feed(content)
            if hp.linkpos != 0:
                # this title-parsing bit from Hixie's pingback-to-trackback proxy
                # http://software.hixie.ch/utilities/cgi/pingback-proxy/pingback-to-trackback.pl
                t_match = re.match(r'(.+)\s*(?:\s\-|:)\s+(.+)', hp.title)
                #linkback_remote_excerpt = summarize.summarize(...)
                if t_match:
                    linkback.remote_name = t_match.group(1)
                    linkback.remote_title = t_match.group(2)
                else:
                    linkback.remote_title = hp.title
            else:
                return {'fault': Fault(17, 'No link to target URI %s found in source URI %s' % (targetURI, sourceURI))}

class LinkbackCommit(Action):
    '''Commits a linkback request to the database.'''
    def generate(self, rsp, fault=None):
        if fault:
            return
        try:
            session.commit()
        except SQLError, e:
            if e.orig[0] == 1062:
                return {'fault': Fault(48, 'Linkback already registered')}
            else:
                return {'fault': Fault(0, 'Internal server error')}

class TrackbackResponse(Action):
    '''Prepares a response to a trackback request.'''
    def generate(self, rsp, fault=None):
        if fault:
            rsp.data = '<?xml version="1.0" encoding="utf-8"?><response><error>1</error><message>%s</message></response>' % fault.message
        else:
            rsp.data = '<?xml version="1.0" encoding="utf-8"?><response><error>0</error></response>'

class PingbackResponse(Action):
    '''Prepares a response to a pingback request.'''
    def generate(self, rsp, linkback, fault=None):
        if fault:
            self.req.data = xmlrpclib.dumps(fault, methodresponse = True)
        # for other errors:
        #   logging.getLogger('modulo.addons.blog').exception('Failure during handler processing')
        #   self.req.data = xmlrpclib.dumps(Fault(0, 'Internal server error'), methodresponse = True)
        else:
            self.req.data = xmlrpclib.dumps(('Successful ping to %s' % linkback.local_uri,), methodresponse = True)

# Recommended chains
TrackbackProcessor = all_of(ContentTypeAction('text/xml', 'utf-8'), TrackbackAssembler, LinkbackFetcher, LinkbackCommit, TrackbackResponse)
PingbackProcessor = all_of(ContentTypeAction('text/xml', 'utf-8'), PingbackURIAssembler, LinkbackFetcher(True), LinkbackCommit, PingbackResponse)

class EnableTrackback(Action):
    '''Inserts the key trackback_url into the dictionary.'''
    @classmethod
    def derive(cls, trackback_prefix):
        return super(EnableTrackback, cls).derive(trackback_prefix=trackback_prefix)

    def generate(self, rsp, canonical_uri):
        return {'trackback_url': 'http://' + self.req.host + self.trackback_prefix + canonical_uri}

class EnablePingback(Action):
    '''Inserts the key pingback_url into the dictionary, and also sets the X-Pingback header.'''
    @classmethod
    def derive(cls, pingback_url):
        return super(EnablePingback, cls).derive(pingback_url=pingback_url)

    def generate(self, rsp):
        rsp.headers['X-Pingback'] = self.pingback_url
        return {'pingback_url': self.pingback_url}

class LinkbackDisplay(Action):
    '''Selects all linkback requests submitted for the current page.'''
    def generate(self, rsp, canonical_uri):
        return {'linkbacks': Linkback.query.filter(Linkback.local_uri==canonical_uri).all()}
