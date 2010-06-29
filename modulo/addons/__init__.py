# -*- coding: utf-8 -*-

from modulo.actions import Action
from modulo.utilities import compact
from sqlalchemy import desc
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import NotFound

class Query(Action):
    @classmethod
    def derive(cls, model, **kwargs):
        return super(Query, cls).derive(model=model, **kwargs)
    def generate(self, rsp):
        return {'query': self.model.query, 'model': self.model}

class ValueSelector(Action):
    @classmethod
    def derive(cls, field, **kwargs):
        return super(ValueSelector, cls).derive(field=field, **kwargs)
    def generate(self, rsp, query, model, **kwargs):
        try:
            value = kwargs[self.field]
        except KeyError:
            value = getattr(self, self.field)
        return {'query': query.filter(getattr(model, self.field)==value)}
class MemberSelector(Action):
    @classmethod
    def derive(cls, field, association, **kwargs):
        return super(MemberSelector, cls).derive(field=field, association=association, **kwargs)
    def generate(self, rsp, query, model, **kwargs):
        try:
            value = kwargs[self.field]
        except KeyError:
            value = getattr(self, self.field)
        return {'query': query.filter(getattr(model, self.association).any(getattr(model, self.field)==value))}
class RangeSelector(Action):
    @classmethod
    def derive(cls, field, **kwargs):
        return super(RangeSelector, cls).derive(field=field, **kwargs)
    def generate(self, rsp, query, model, range_min, range_max):
        return {'query': query.filter(range_min <= getattr(model, self.field) <= range_max)}
class YearMonthDaySelector(Action):
    def generate(self, rsp, query, model, year, month=None, day=None):
        if month is None:
            date_min = datetime.datetime(year, 1, 1)
            date_max = datetime.datetime(year + 1, 1, 1)
        elif day is None:
            date_min = datetime.datetime(year, month, 1)
            if month == 12:
                date_max = datetime.datetime(year + 1, 1, 1)
            else:
                date_max = datetime.datetime(year, month + 1, 1)
        else:
            date_min = datetime.datetime(year, month, day)
            date_max = date_min + datetime.timedelta(days=1)
        return {'query': query.filter(date_min <= model.date <= date_max)}

class DateOrdering(Action):
    ascending = False # I figure False is a reasonable default
    @classmethod
    def derive(cls, field, ascending=False, **kwargs):
        return super(DateOrdering, cls).derive(field=field, ascending=ascending, **kwargs)
    def generate(self, rsp, query, model):
        if self.ascending:
            return {'query': query.order_by(getattr(model, self.field))}
        else:
            return {'query': query.order_by(desc(getattr(model, self.field)))}


class Paginator(Action):
    page_size = 10
    @classmethod
    def derive(cls, page_size=10, **kwargs):
        return super(Paginator, cls).derive(page_size=page_size, **kwargs)

    def generate(self, rsp, query, model, page=None, page_size=None):
        if page_size is None:
            page_size = self.page_size
        if page is None:
            page = 1
        else:
            page = int(page)
            logging.getLogger('modulo.addons.publish').debug('Displaying page ' + str(page))
        count = query.count()
        pages = max(0, count - 1) // page_size + 1 # this is ceil(post_count / page_size)
        query = query.offset((page - 1) * page_size).limit(page_size)
        d = compact('query', 'page_size', 'page', 'pages', 'count')
        if page < pages:
            d['page_next'] = page + 1
        if page > 1:
            d['page_prev'] = page - 1
        return d

class FetchOne(Action):
    def generate(self, rsp, query):
        try:
            record = query.one()
        except NoResultFound:
            raise NotFound
        finally:
            try:
                d = self.params[self.namespace]
            except AttributeError:
                d = self.params['']
            del d['query']
        return compact('record')

class FetchAll(Action):
    raise_not_found = True
    def generate(self, rsp, query):
        records = query.all()
        try:
            d = self.params[self.namespace]
        except AttributeError:
            d = self.params['']
        del d['query']
        if self.raise_not_found and len(records) == 0:
            raise NotFound
        return compact('records')

class ValueMutator(Action):
    @classmethod
    def derive(cls, field, **kwargs):
        return super(ValueMutator, cls).derive(field=field, **kwargs)
    def generate(self, rsp, record, **kwargs):
        try:
            value = kwargs[self.field]
        except KeyError:
            value = getattr(self, self.field)
        setattr(record, self.field, value)

class MemberMutator(Action):
    @classmethod
    def derive(cls, field, **kwargs):
        return super(MemberMutator, cls).derive(field=field, **kwargs)
    def generate(self, rsp, record, **kwargs):
        try:
            value = kwargs[self.field]
        except KeyError:
            value = getattr(self, self.field)
        getattr(record, self.field).append(value)
