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
from sqlalchemy import desc
from sqlalchemy.exceptions import SQLError
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import BadRequest, NotFound

#---------------------------------------------------------------------------
# Database models
#---------------------------------------------------------------------------
class Post(Entity):
    title = Field(Unicode(128))
    slug = Field(Unicode(128))
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
    text_src = Field(UnicodeText)
    text = Field(UnicodeText)

    post = ManyToOne('Post')
    user = ManyToOne('User')

class Tag(Entity):
    name = Field(Unicode(128), primary_key=True)

    posts = ManyToMany('Post')

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

def _pquery(pquery=None):
    if pquery is None:
        return Post.query
    else:
        return pquery

class PostIDSelector(Action):
    def generate(self, rsp, post_id, pquery=None):
        return {'pquery': _pquery(pquery).filter(Post.id==post_id)}
class PostDateSelector(Action):
    def generate(self, rsp, post_date_min, post_date_max, pquery=None):
        return {'pquery': _pquery(pquery).filter(post_date_min <= Post.date <= post_date_max)}
class PostYearMonthDaySelector(Action):
    def generate(self, rsp, post_year, post_month=None, post_day=None, pquery=None):
        if post_month is None:
            post_date_min = datetime.datetime(post_year, 1, 1)
            post_date_max = datetime.datetime(post_year + 1, 1, 1)
        elif post_day is None:
            post_date_min = datetime.datetime(post_year, post_month, 1)
            if post_month == 12:
                post_date_max = datetime.datetime(post_year + 1, 1, 1)
            else:
                post_date_max = datetime.datetime(post_year, post_month + 1, 1)
        else:
            post_date_min = datetime.datetime(post_year, post_month, post_day)
            post_date_max = post_date_min + datetime.timedelta(days=1)
        return {'pquery': _pquery(pquery).filter(post_date_min <= Post.date <= post_date_max)}
class PostSlugSelector(Action):
    def generate(self, rsp, post_slug, pquery=None):
        return {'pquery': _pquery(pquery).filter(Post.slug==post_slug)}
class TagIDSelector(Action):
    def generate(self, rsp, tag_id, pquery=None):
        return {'pquery': _pquery(pquery).filter(Post.tags.any(id==tag_id))}
class TagNameSelector(Action):
    def generate(self, rsp, tag_name, pquery=None):
        return {'pquery': _pquery(pquery).filter(Post.tags.any(name=tag_name))}
class UserIDSelector(Action):
    def generate(self, rsp, user_id, pquery=None):
        return {'pquery': _pquery(pquery).filter(Post.user.has(id=user_id))}
class UserLoginSelector(Action):
    def generate(self, rsp, user_login, pquery=None):
        return {'pquery': _pquery(pquery).filter(Post.user.has(login=user_login))}

class PostDateOrder(Action):
    ascending = False # I figure False is a reasonable default
    def generate(self, rsp, pquery=None):
        if self.ascending:
            return {'pquery': _pquery(pquery).order_by(Post.date)}
        else:
            return {'pquery': _pquery(pquery).order_by(desc(Post.date))}
        

class PostPaginator(Action):
    page_size = 10
    @classmethod
    def derive(cls, page_size=10, **kwargs):
        return super(PostPaginator, cls).derive(page_size=page_size, **kwargs)

    def generate(self, rsp, pquery=None, page=None, page_size=None):
        if page_size is None:
            page_size = self.page_size
        if page is None:
            page = 1
        else:
            page = int(page)
            logging.getLogger('modulo.addons.publish').debug('Displaying page ' + str(page))
        pquery = _pquery(pquery)
        post_count = pquery.count()
        return {'pquery': pquery.offset((page - 1) * page_size).limit(page_size), 'page_size': page_size, 'page': page, 'post_count': post_count}

class PostPaginationData(Action):
    def generate(self, rsp, post_count, page_size, page=1):
        d = {}
        page = int(page)
        pages = max(0, post_count - 1) // page_size + 1 # this is ceil(post_count / page_size)
        d['pages'] = pages
        if page < pages:
            d['next_page'] = page + 1
        if page > 1:
            d['prev_page'] = page - 1
        return d

class PostDisplay(Action):
    def generate(self, rsp, pquery):
        try:
            post = pquery.one()
        except NoResultFound:
            raise NotFound
        del pquery
        pquery = None
        return compact('post', 'pquery')

class MultiPostDisplay(Action):
    def generate(self, rsp, pquery=None):
        pquery = _pquery(pquery)
        posts = pquery.all()
        if len(posts) == 0:
            raise NotFound
        del pquery # just a bit of premature optimization, for the fun of it
        pquery = None
        return compact('posts', 'pquery')

class PostSubmitAggregator(Action):
    def generate(self, rsp, user, post_title, post_text_src, post_tags=list(), post_draft=False, post_category=None, post_markup_mode=None, post_summary_src=None):
        post = Post()
        post.title = post_title
        post.text = post.text_src = post_text_src
        if post.title and post.text_src:
            post.date = datetime.datetime.now()
            if post_tags == u'': # TODO: consider whether this sort of case should be handled in RequestDataAggregator
                post_tags = list()
            post.tags = post_tags
            post.draft = bool(post_draft)
            post.category = post_category
            post.markup_mode = post_markup_mode
            post.summary = post.summary_src = post_summary_src
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

class CommentDisplay(Action):
    def generate(self, rsp, comment_id):
        comment = Comment.query.filter(Comment.id==comment_id).one()
        return compact('comment')

class CommentForPostDisplay(Action):
    def generate(self, rsp, post):
        comments = Comment.query.filter(Comment.post==post).all()
        return compact('comments')

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

class MultiTagDisplay(Action):
    def generate(self, rsp):
        tags = Tag.query.all()
        return compact('tags')

class TagForPostDisplay(Action):
    def generate(self, rsp, post):
        post_tags = Tag.query.filter(Tag.posts.any(post=post)).all()
        return compact('post_tags')

class TagSubmit(Action):
    def generate(self, rsp, tag_name):
        try:
            tag = Tag.query.filter(Tag.name==tag_name).one()
        except NoResultFound:
            tag = Tag()
            tag.name = tag_name
        return compact('tag')

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
