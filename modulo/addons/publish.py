# -*- coding: iso-8859-1 -*-

'''Actions related to content publication, syndication, etc.'''

import datetime
import logging
import modulo.database
from elixir import session, setup_all
from elixir import Boolean, DateTime, Entity, Field, ManyToOne, ManyToMany, OneToMany, String, Unicode, UnicodeText
from modulo.actions import Action
from modulo.actions.standard import ContentTypeAction
from modulo.addons.users import User
from modulo.utilities import compact, markup, summarize, uri_path
from HTMLParser import HTMLParser
from sqlalchemy.exceptions import SQLError
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import BadRequest, NotFound

#---------------------------------------------------------------------------
# Database models
#---------------------------------------------------------------------------
class Tag(Entity):
    name = Field(Unicode(128), primary_key=True)

class BaseComment(Entity):
    title = Field(Unicode(128))
    date = Field(DateTime)
    draft = Field(Boolean)
    text = Field(UnicodeText)

    comments = OneToMany('Comment')

class Post(BaseComment):
    slug = Field(Unicode(128))
    category = Field(String(32))
    summary = Field(UnicodeText)

    tags = ManyToMany('Tag')
    user = ManyToOne('User')

class EditablePost(Post):
    edit_date = Field(DateTime)
    markup_mode = Field(String(32))
    summary_src = Field(UnicodeText)
    text_src = Field(UnicodeText)

class Comment(BaseComment):
    parent = ManyToOne('BaseComment')
    # TODO: go back to having a Commentable class or some equivalent, so that Comments
    # can be attached to generic Entities, not just those that inherit from BaseComment.
    # This will require some sort of polymorphism, possibly the AssociationProxy pattern.

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

class PostSubmitAggregator(Action):
    def generate(self, rsp, user, title, text_src, tags=list(), draft=False, category=None, markup_mode=None, summary_src=None):
        post = Post()
        post.title = title
        post.text = post.text_src = text_src
        if post.title and post.text_src:
            post.date = datetime.datetime.now()
            if tags == u'':
                tags = list()
            post.tags = tags
            post.draft = bool(draft)
            post.category = category
            post.markup_mode = markup_mode
            post.summary = post.summary_src = summary_src
            post.user = user
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

class CommentSubmitAggregator(Action):
    def generate(self, rsp, comment_text_src, post_id, user=None, comment_subject=None):
        comment = Comment()
        comment.text_src = comment.text = comment_text_src
        if comment.text_src:
            comment.subject = comment_subject
            comment.date = datetime.datetime.now()
            comment.post = Post.query.filter(Post.id==post_id).one()
            comment.user = user
            return compact('comment')
        else:
            comment.delete()

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

class TagIDSelector(Action):
    def generate(self, rsp, query, id):
        return {'query': query.filter(Taggable.tags.any(id==id))}
class TagNameSelector(Action):
    def generate(self, rsp, query, name):
        return {'query': query.filter(Taggable.tags.any(name=name))}

class TagSubmit(Action):
    def generate(self, rsp, name):
        return {'tag': Tag(name=name)}

#---------------------------------------------------------------------------
# Linkback autodiscovery
#---------------------------------------------------------------------------

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
    '''Runs a blog post through linkback autodiscovery.
    
    This is designed to work with the modulo.addons.publish.Post class, so if you
    are using this class but not the modulo.addons.publish actions, you're probably
    doing something wrong.'''
    blog_name = None

    def generate(self, rsp, post):
        if not post.draft:
            LinkbackAutodiscoveryParser(post.title, self.blog_name).feed(post.text)
