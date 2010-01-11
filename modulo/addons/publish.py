# -*- coding: iso-8859-1 -*-

'''Actions related to content publication, syndication, etc.'''

import datetime
import modulo.database
from elixir import session, setup_all
from elixir import Boolean, DateTime, Entity, Field, ManyToOne, ManyToMany, OneToMany, String, Unicode, UnicodeText
from modulo.actions import Action, all_of, any_of
from modulo.actions.standard import ContentTypeAction
from modulo.addons.users import User
from modulo.utilities import compact, uri_path
from HTMLParser import HTMLParser
from sqlalchemy.exceptions import SQLError
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import BadRequest, NotFound

#---------------------------------------------------------------------------
# Database models
#---------------------------------------------------------------------------
class Post(Entity):
    title = Field(Unicode(128))
    draft = Field(Boolean)
    date = Field(DateTime)
    edit_date = Field(DateTime)
    category = Field(String(32))
    markup_mode = Field(String(32))
    summary_src = Field(UnicodeText)
    summary = Field(UnicodeText)
    text_src = Field(UnicodeText)
    text = Field(UnicodeText)

    user = ManyToOne('User')
    comments = OneToMany('Comment')
    tags = ManyToMany('Tag')

class Comment(Entity):
    subject = Field(Unicode(128))
    date = Field(DateTime)
    text = Field(UnicodeText)

    post = ManyToOne('Post')
    user = ManyToOne('User')

class Tag(Entity):
    name = Field(Unicode(128), primary_key=True)

    posts = ManyToMany('Post')

class Linkback(Entity):
    local_host = Field(Unicode(128))
    local_uri = Field(Unicode(1024))
    remote_url = Field(Unicode(1024))
    remote_title = Field(Unicode(256))
    remote_excerpt = Field(UnicodeText)
    remote_name = Field(Unicode(256))

setup_all()

#---------------------------------------------------------------------------
# General stuff
#---------------------------------------------------------------------------

class TransactionID(Action):
    def generate(self, rsp):
        if 'transaction_id' in self.req.values:
            return {'transaction_id': self.req.values['transaction_id']}
        else:
            return {'transaction_id': '%016x' % random.randint(0, 2**64 - 1)}

#---------------------------------------------------------------------------
# Posts
#---------------------------------------------------------------------------

class PostDisplay(Action):
    def generate(self, rsp, post_id):
        try:
            post = Post.query.filter(Post.id==post_id).one()
        except NoResultFound:
            raise NotFound
        return compact('post')

class MultiPostDisplay(Action):
    def generate(self, rsp, post_category=None, tag_name=None, user_id=None):
        pquery = Post.query
        if post_category:
            pquery = pquery.filter(Post.category==post_category)
        if tag_name:
            pquery = pquery.filter(Post.tags.any(name=tag_name))
        if user_id:
            pquery = pquery.filter(Post.user.has(id=user_id))
        posts = pquery.all()
        return compact('posts')

class PostSubmitAggregator(Action):
    def generate(self, rsp):
        post = Post()
        post.title = self.req.form['post_title']
        post.text = post.text_src = self.req.form['post_text_src']
        if post.title and post.text_src:
            post.date = datetime.datetime.now()
            post.tags = self.req.form.getlist('post_tags')
            post.draft = bool(self.req.form.get('post_draft', False))
            post.category = self.req.form.get('post_category', None)
            post.markup_mode = self.req.form.get('post_markup_mode', None)
            post.summary = post.summary_src = self.req.form.get('post_summary_src', None)
        return compact('post')

class PostMarkupParser(Action):
    def generate(self, rsp, post):
        post.text = markup.process_source(post.text_src, post.markup_mode)
        if post.summary_src:
            post.summary = markup.process_source(post.summary_src, post.markup_mode)
        else:
            post.summary = summarize.summarize(post.text)

class PostCommit(Action):
    def generate(self, rsp):
        session.commit()
        rsp.status_code = 201

#---------------------------------------------------------------------------
# Comments
#---------------------------------------------------------------------------

class CommentDisplay(Action):
    def generate(self, rsp, comment_id):
        comment = Comment.query.filter(Comment.id==comment_id).one()
        return compact('comment')

class CommentForPostDisplay(Action):
    def generate(self, rsp, post):
        post_comments = Comment.query.filter(Comment.post==post).all()
        return compact('post_comments')

class CommentSubmitAggregator(Action):
    def generate(self, rsp, user=None):
        comment = Comment()
        comment.text_src = comment.text = self.req.form.get('comment_text', '')
        comment.subject = self.req.form.get('comment_subject', '')
        if comment.text_src and comment.subject:
            comment.date = datetime.datetime.now()
            comment.post = Post.query.filter(Post.id==self.req.form['post_id']).one()
            comment.user = user
        return compact('comment')

class CommentMarkupParser(Action):
    def generate(self, rsp, comment):
        comment.text = markup.process_markdown_safe(comment.text_src)

class CommentCommit(Action):
    def generate(self, rsp):
        session.commit()
        rsp.status_code = 201

#---------------------------------------------------------------------------
# Tags
#---------------------------------------------------------------------------

class MultiTagDisplay(Action):
    def generate(self, rsp):
        tags = Tag.query.all()
        return compact('tags')

class TagForPostDisplay(Action):
    def generate(self, rsp, post):
        post_tags = Tag.query.filter(Tag.posts.any(post=post)).all()
        return compact('post_tags')

class TagSubmit(Action):
    def generate(self, rsp):
        try:
            tag = Tag.query.filter(Tag.name==self.req.args['tag_name']).one()
        except:
            tag = Tag()
            tag.name = self.req.args['tag_name']
            session.commit(tag)
        return compact('tag')

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
    def generate(self, rsp, canonical_uri):
        linkback = Linkback()
        linkback.local_uri = canonical_uri
        linkback.remote_url = self.req.args.get('url', None)
        if not linkback.local_uri:
            linkback_error = 'No target URL specified'
        elif not linkback.remote_url:
            linkback_error = 'No linking URL specified'
        elif self.req.method != 'POST':
            linkback_error = 'HTTP POST method not used'
        else:
            linkback.local_host = self.req.host
            linkback.remote_title = self.req.args.get('title', '')
            linkback.remote_excerpt = self.req.args.get('excerpt', '')
            linkback.remote_name = self.req.args.get('blog_name', '')
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
        return super(EnablePingback, cls).derive(pingback_url)

    def generate(self, rsp):
        rsp.headers['X-Pingback'] = self.pingback_url
        return {'pingback_url': pingback_url}

class LinkbackDisplay(Action):
    '''Selects all linkback requests submitted for the current page.'''
    def generate(self, rsp, canonical_uri):
        return {'linkbacks': Linkback.query.select_by(local_uri=canonical_uri)}

class LinkbackAutodiscoveryParser(HTMLParser):
    '''Parses some content, like a blog post, and sends linkback requests to all 
    linkback-capable pages which are linked from the parsed content.'''
    def __init__(self, sourceURI, sourceTitle, blog_name=None):
        HTMLParser.__init__(self)
        self.sourceURI = sourceURI
        self.sourceTitle = sourceTitle
        self.blog_name = blog_name

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for name, targetURI in attrs:
                if name == 'href':
                    # check the URL for pingback capability
                    remote = urlparse.urlsplit(targetURI)
                    if remote.scheme == 'http':
                        Connection = httplib.HTTPConnection
                    elif remote.scheme == 'https':
                        Connection = httplib.HTTPSConnection
                    # TODO: else:
                    rconn = Connection(remote.hostname, remote.port)
                    try:
                        rconn.request('HEAD', remote.path)
                        response = rconn.getresponse()
                        pingback_server = response.getheader('X-Pingback', None)
                        try:
                            response.read() # read nothing... this line is problematic for some reason
                        except ValueError:
                            pass
                        if pingback_server:
                            # do pingback
                            ServerProxy(pingback_server).pingback.ping(self.sourceURI, targetURI)
                            return
                        rconn.request('GET', remote.path)
                        response = rconn.getresponse()
                        content = response.read()
                        pingback_match = re.search('<link rel="pingback" href="([^"]+)" ?/?>', content)
                        if pingback_match:
                            pingback_server = pingback_match.group(1)
                            # ahhh copy-and-paste from above!!! But not to fear, this will become a library someday
                            ServerProxy(pingback_server).pingback.ping(self.sourceURI, targetURI)
                            # whahuh? that was easy...
                            return
                        trackback_match = re.search('trackback:ping="(.*?)"', content) # regex from Matt Croydon's tblib
                        if trackback_match:
                            trackback_server = trackback_match.group(1)
                            # the rest of this is sorta lifted from tblib... I'll write my own someday
                            params = {'title': self.sourceTitle, 'url': self.sourceURI}
                            if self.blog_name:
                                params['blog_name'] = self.blog_name
                            params = urllib.urlencode(params)
                            headers = ({"Content-type": "application/x-www-form-urlencoded"})
                            tb_remote = urlparse.urlsplit(trackback_server)
                            if tb_remote.scheme == 'http':
                                TBConnection = httplib.HTTPConnection
                            elif tb_remote.scheme == 'https':
                                TBConnection = httplib.HTTPSConnection
                            uconn = TBConnection(tb_remote.hostname, tb_remote.port)
                            uconn.request("POST", tb_remote.path, params, headers)
                            xml_response = uconn.getresponse().read()
                            uconn.close()
                            # ignore errors for now, but we'll keep the parsing code here for the future
                            err_match = re.search('<error>(.*?)</error>', xml_response)
                            if err_match:
                                errcode = err_match.group(1)
                                if errcode == 1:
                                    errmsg_match = re.search('<message>(.*?)</message>', xml_response)
                                    if errmsg_match:
                                        errmsg = errmsg_match.group(1)
                            return
                    finally:
                        rconn.close()

class LinkbackAutodiscovery(Action):
    '''Runs a blog post through linkback autodiscovery'''
    @classmethod
    def derive(cls, blog_name=None):
        return super(LinkbackAutodiscovery, cls).derive(blog_name=blog_name)

    def generate(self, rsp, post):
        if not post.draft:
            LinkbackAutodiscoveryParser(post.title, self.blog_name).feed(post.text)
