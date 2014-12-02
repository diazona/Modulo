# -*- coding: utf-8 -*-
'''Provides a rudimentary bug-tracking system.'''

import datetime
import logging
import modulo.database
from modulo.actions import Action
from modulo.actions.standard import ContentTypeAction
from modulo.addons.publish import Post
from modulo.addons.users import User
from modulo.database import Session
from modulo.utilities import compact, markup, summarize, uri_path
from sqlalchemy import desc, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import BadRequest, NotFound

#---------------------------------------------------------------------------
# Database models
#---------------------------------------------------------------------------
class Report(Post):
    __tablename__ = 'report'
    __mapper_args__ = {'polymorphic_identity': 'report'}

    post_basecomment_id = Column(Integer, ForeignKey(Post.basecomment_id), primary_key=True)
    status = Column(String(30))
    resolution = Column(String(30))
    version = Column(String(15))
    platform = Column(String(15))
    system = Column(String(15))
    priority = Column(Integer)
    severity = Column(Integer)

    assignee = relationship('User')

#---------------------------------------------------------------------------
# General stuff
#---------------------------------------------------------------------------

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
    def generate(self, rsp, user, title, category, text, tags=list()):
        report = Report()
        report.title = title
        report.text = text
        if report.title and report.text:
            report.date = datetime.datetime.now()
            if tags == u'':
                tags = list()
            report.tags = tags
            report.category = category
            report.status = 'NEW'
            report.user = user
        return compact('report')

class ReportResolve(Action):
    new_status = 'RESOLVED'
    def generate(self, rsp, report):
        report.status = self.new_status

class ReportCommit(Action):
    def generate(self, rsp):
        Session.commit()
        rsp.status_code = 201

