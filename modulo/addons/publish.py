# -*- coding: utf-8 -*-

'''Actions related to content publication, syndication, etc.'''

import datetime
import httplib
import logging
import modulo.database
import os, os.path
import random
import re
import urlparse
from elixir import session, using_options
from elixir import Boolean, DateTime, Entity, Field, ManyToOne, ManyToMany, OneToMany, String, Unicode, UnicodeText
try:
    from elixir import LargeBinary #SQLAlchemy 0.6
except ImportError:
    from elixir import Binary as LargeBinary # SQLAlchemy 0.5
from modulo.actions import Action
from modulo.actions.standard import ContentTypeAction
from modulo.addons.users import User
from modulo.utilities import compact, markup, summarize, uri_path
from HTMLParser import HTMLParser
from sqlalchemy.exceptions import SQLError
from sqlalchemy.orm.exc import NoResultFound
from werkzeug import secure_filename
from werkzeug.exceptions import BadRequest, NotFound

#---------------------------------------------------------------------------
# Database models
#---------------------------------------------------------------------------
class Tag(Entity):
    name = Field(Unicode(128), unique=True)

class BaseComment(Entity):
    using_options(inheritance='multi')

    title = Field(Unicode(128))
    date = Field(DateTime)
    draft = Field(Boolean)
    text = Field(UnicodeText)

    comments = OneToMany('Comment')
    user = ManyToOne('User')

class Post(BaseComment):
    using_options(inheritance='multi')
    
    slug = Field(Unicode(128))
    category = Field(String(32))
    summary = Field(UnicodeText)

    tags = ManyToMany('Tag')
    attachments = ManyToMany('Attachment')

class EditablePost(Post):
    using_options(inheritance='multi')

    edit_date = Field(DateTime)
    markup_mode = Field(String(32))
    summary_src = Field(UnicodeText)
    text_src = Field(UnicodeText)

class Postlet(BaseComment):
    pass

class Comment(BaseComment):
    using_options(inheritance='multi')

    parent = ManyToOne('BaseComment')
    # TODO: go back to having a Commentable class or some equivalent, so that Comments
    # can be attached to generic Entities, not just those that inherit from BaseComment.
    # This will require some sort of polymorphism, possibly the AssociationProxy pattern.

class Attachment(Entity):
    mime_type = Field(String(44)) # the MIME type
    filename = Field(String(124)) # the file on disk that holds the attachment's content

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
    editable = False
    def generate(self, rsp, user, title, text_src, tags=list(), draft=False, category=None, markup_mode=None, summary_src=None, attachments=list(), id=None):
        editing = False
        if self.editable:
            if id:
                try:
                    post = EditablePost.query.filter(EditablePost.id==id).one()
                except NoResultFound:
                    post = EditablePost()
                else:
                    editing = True
            else:
                post = EditablePost()
        else:
            post = Post()
        post.title = title
        post.text = text_src
        if post.title and post.text:
            if editing and not draft:
                post.edit_date = datetime.datetime.now()
            else:
                post.date = datetime.datetime.now()
            if tags == u'':
                tags = list()
            post.tags = tags
            post.category = category
            post.summary = summary_src
            if self.editable:
                post.draft = bool(draft)
                post.markup_mode = markup_mode
                post.summary_src = summary_src
                post.text_src = text_src
            post.user = user
            post.attachments = attachments
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
    def generate(self, rsp, text_src, parent_id, user=None, subject=None):
        comment = Comment()
        comment.text_src = comment.text = text_src
        if comment.text_src:
            comment.subject = subject
            comment.date = datetime.datetime.now()
            comment.parent = BaseComment.query.filter(BaseComment.id==parent_id).one()
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
# Postlets
#---------------------------------------------------------------------------

class PostletSubmitAggregator(Action):
    def generate(self, rsp, text_src, user=None, subject=None):
        postlet = Postlet()
        postlet.text_src = postlet.text = text_src
        if postlet.text_src:
            postlet.subject = subject
            postlet.date = datetime.datetime.now()
            postlet.user = user
            return compact('postlet')
        else:
            postlet.delete()

class PostletMarkupParser(Action):
    def generate(self, rsp, postlet):
        postlet.text = markup.process_markdown_safe(postlet.text_src)

class PostletCommit(Action):
    def generate(self, rsp):
        session.commit()
        rsp.status_code = 201

#---------------------------------------------------------------------------
# Tags
#---------------------------------------------------------------------------

class TagSplitter(Action):
    '''Used when tags are submitted as a comma-separated list'''
    delimiter = ','
    @staticmethod
    def get_tag(t):
        try:
            return Tag.query.filter(Tag.name==t).one()
        except NoResultFound:
            return Tag(name=t)
    def generate(self, rsp, tags):
        if tags:
            return {'tags': [self.get_tag(t) for t in tags.split(self.delimiter)]}

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
                    else:
                        return
                    rconn = Connection(remote.hostname, remote.port)
                    try:
                        rconn.request('HEAD', remote.path)
                        response = rconn.getresponse()
                        try:
                            pingback_server = response.getheader('X-Pingback', None)
                            try:
                                response.read() # read nothing... this line is problematic for some reason
                            except ValueError:
                                pass
                        finally:
                            response.close()
                        if pingback_server:
                            # do pingback
                            ServerProxy(pingback_server).pingback.ping(self.sourceURI, targetURI)
                            return
                        rconn.request('GET', remote.path)
                        response = rconn.getresponse()
                        try:
                            content = response.read()
                        finally:
                            response.close()
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
                            try:
                                uconn.request("POST", tb_remote.path, params, headers)
                                xml_response = uconn.getresponse().read()
                            finally:
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

#---------------------------------------------------------------------------
# Attachments
#---------------------------------------------------------------------------

def gen_chars(n):
    '''Produces a set of n random word characters'''
    return "".join(random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_') for i in xrange(n))

def make_file(suggested):
    import settings
    name = suggested and secure_filename(suggested) or gen_chars(16) # intentional non-use of ...if...else...
    subdirs = os.listdir(settings.upload_dir)
    random.shuffle(subdirs)
    # potential for race conditions here, but they're unlikely... ignore for now
    for subdir in subdirs:
        path = os.path.join(settings.upload_dir, subdir, name)
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0644)
        except OSError:
            pass
        else:
            file_obj = os.fdopen(fd, 'w')
            break
    else: # omg it's actually useful here
        subdir = gen_chars(4)
        # Possible, but very unlikely, that this could fail
        os.mkdir(os.path.join(settings.upload_dir, subdir))
        path = os.path.join(settings.upload_dir, subdir, name)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0644)
        file_obj = os.fdopen(fd, 'w')
    return file_obj, subdir, name, path

class AttachmentSubmitAggregator(Action):
    @classmethod
    def handles(cls, req, params):
        return len(req.files) > 0
    def generate(self, rsp):
        attachments = []
        for name, upload in self.req.files.iteritems():
            if upload.filename is None:
                continue
            file_obj, subdir, name, path = make_file(upload.filename)
            with file_obj:
                upload.save(file_obj)
            attachments.append(Attachment(mime_type=upload.content_type, filename=path))
        return compact('attachments')
