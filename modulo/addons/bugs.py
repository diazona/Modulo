# -*- coding: iso-8859-1 -*-
'''Provides a rudimentary bug-tracking system.'''

import datetime
import logging
import modulo.database
from elixir import session, setup_all
from elixir import Boolean, DateTime, Entity, Enum, Field, ManyToOne, ManyToMany, OneToMany, String, Unicode, UnicodeText
from modulo.actions import Action
from modulo.actions.standard import ContentTypeAction
from modulo.addons.users import User
from modulo.utilities import compact, markup, summarize, uri_path
from sqlalchemy import desc
from sqlalchemy.exceptions import SQLError
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import BadRequest, NotFound

#---------------------------------------------------------------------------
# Database models
#---------------------------------------------------------------------------
class Report(Entity):
    title = Field(Unicode(128))
    date = Field(DateTime)
    product = Field(String(32))
    text = Field(UnicodeText)
    status = Field(Enum('NEW', 'RESOLVED'))

    user = ManyToOne('User')
    comments = OneToMany('Comment')
    tags = ManyToMany('Tag')

class Comment(Entity):
    subject = Field(Unicode(128))
    date = Field(DateTime)
    text = Field(UnicodeText)

    report = ManyToOne('Report')
    user = ManyToOne('User')

class Tag(Entity):
    name = Field(Unicode(128), primary_key=True)

    report = ManyToMany('Report')

setup_all()

#---------------------------------------------------------------------------
# General stuff
#---------------------------------------------------------------------------

def _rquery(rquery=None):
    if rquery is None:
        return Report.query
    else:
        return rquery

class ReportIDSelector(Action):
    def generate(self, rsp, report_id, rquery=None):
        return {'rquery': _rquery(rquery).filter(Report.id==report_id)}
class ReportStatusSelector(Action):
    def generate(self, rsp, report_status, rquery=None):
        return {'rquery': _rquery(rquery).filter(Report.status==report_status)}
class ReportProductSelector(Action):
    def generate(self, rsp, report_product, rquery=None):
        return {'rquery': _rquery(rquery).filter(Report.product==report_product)}
class ReportDateSelector(Action):
    def generate(self, rsp, report_date_min, report_date_max, rquery=None):
        return {'rquery': _rquery(rquery).filter(report_date_min <= Report.date <= report_date_max)}
class ReportYearMonthDaySelector(Action):
    def generate(self, rsp, report_year, report_month=None, report_day=None, rquery=None):
        if report_month is None:
            report_date_min = datetime.datetime(report_year, 1, 1)
            report_date_max = datetime.datetime(report_year + 1, 1, 1)
        elif report_day is None:
            report_date_min = datetime.datetime(report_year, report_month, 1)
            if report_month == 12:
                report_date_max = datetime.datetime(report_year + 1, 1, 1)
            else:
                report_date_max = datetime.datetime(report_year, report_month + 1, 1)
        else:
            report_date_min = datetime.datetime(report_year, report_month, report_day)
            report_date_max = report_date_min + datetime.timedelta(days=1)
        return {'rquery': _rquery(rquery).filter(report_date_min <= Report.date <= report_date_max)}
class TagIDSelector(Action):
    def generate(self, rsp, tag_id, rquery=None):
        return {'rquery': _rquery(rquery).filter(Report.tags.any(id==tag_id))}
class TagNameSelector(Action):
    def generate(self, rsp, tag_name, rquery=None):
        return {'rquery': _rquery(rquery).filter(Report.tags.any(name=tag_name))}
class UserIDSelector(Action):
    def generate(self, rsp, user_id, rquery=None):
        return {'rquery': _rquery(rquery).filter(Report.user.has(id=user_id))}
class UserLoginSelector(Action):
    def generate(self, rsp, user_login, rquery=None):
        return {'rquery': _rquery(rquery).filter(Report.user.has(login=user_login))}

class ReportDateOrder(Action):
    ascending = False # I figure False is a reasonable default
    def generate(self, rsp, rquery=None):
        if self.ascending:
            return {'rquery': _rquery(rquery).order_by(Report.date)}
        else:
            return {'rquery': _rquery(rquery).order_by(desc(Report.date))}
        

class ReportPaginator(Action):
    page_size = 10
    @classmethod
    def derive(cls, page_size=10):
        return super(ReportPaginator, cls).derive(page_size=page_size)

    def generate(self, rsp, rquery=None, page=None, page_size=None):
        if page_size is None:
            page_size = self.page_size
        if page is None:
            page = 1
        else:
            page = int(page)
            logging.getLogger('modulo.addons.publish').debug('Displaying page ' + str(page))
        rquery = _rquery(rquery)
        report_count = rquery.count()
        return {'rquery': rquery.offset((page - 1) * page_size).limit(page_size), 'page_size': page_size, 'page': page, 'report_count': report_count}

class ReportPaginationData(Action):
    def generate(self, rsp, report_count, page_size, page=1):
        d = {}
        page = int(page)
        pages = max(0, report_count - 1) // page_size + 1 # this is ceil(report_count / page_size)
        d['pages'] = pages
        if page < pages:
            d['next_page'] = page + 1
        if page > 1:
            d['prev_page'] = page - 1
        return d

class ReportDisplay(Action):
    def generate(self, rsp, rquery):
        try:
            report = rquery.one()
        except NoResultFound:
            raise NotFound
        del rquery
        rquery = None
        return compact('report', 'rquery')

class MultiReportDisplay(Action):
    fail_if_empty = True

    def generate(self, rsp, rquery=None):
        rquery = _rquery(rquery)
        reports = rquery.all()
        if self.fail_if_empty and len(reports) == 0:
            raise NotFound
        del rquery # just a bit of premature optimization, for the fun of it
        rquery = None
        return compact('reports', 'rquery')

class ReportSubmitAggregator(Action):
    def generate(self, rsp, user, report_title, report_product, report_text, report_tags=list()):
        report = Report()
        report.title = report_title
        report.text = report_text
        if report.title and report.text:
            report.date = datetime.datetime.now()
            if report_tags == u'': # TODO: consider whether this sort of case should be handled in RequestDataAggregator
                report_tags = list()
            report.tags = report_tags
            report.product = report_product
            report.status = 'NEW'
            report.user = user
        return compact('report')

class ReportResolve(Action):
    new_status = 'RESOLVED'
    def generate(self, rsp, report):
        report.status = self.new_status

class ReportCommit(Action):
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

class CommentForReportDisplay(Action):
    def generate(self, rsp, report):
        comments = Comment.query.filter(Comment.report==report).all()
        return compact('comments')

class CommentSubmitAggregator(Action):
    def generate(self, rsp, comment_text, comment_subject, report_id, user=None):
        comment = Comment()
        comment.text = comment_text
        if comment.text:
            comment.subject = comment_subject
            comment.date = datetime.datetime.now()
            comment.report = Report.query.filter(Report.id==report_id).one()
            comment.user = user
            return compact('comment')
        else:
            comment.delete()

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

class TagForReportDisplay(Action):
    def generate(self, rsp, report):
        report_tags = Tag.query.filter(Tag.reports.any(report=report)).all()
        return compact('report_tags')

class TagSubmit(Action):
    def generate(self, rsp, tag_name):
        try:
            tag = Tag.query.filter(Tag.name==tag_name).one()
        except NoResultFound:
            tag = Tag()
            tag.name = tag_name
        return compact('tag')

