#!/usr/bin/python

'''A dumping ground for all the random crap that accumulates in the course of development ;-)'''

import datetime
import hashlib
import inspect

_rfc1123_fmt = '%a, %d %b %Y %H:%M:%S GMT'
_rfc850_fmt = '%A, %d-%b-%y %H:%M:%S GMT'
_asctime_fmt =  '%a %b %d %H:%M:%S %Y'

def http_date(thedate):
    '''Either parses or formats a date, depending on what kind of argument is passed to it'''
    if thedate is None:
        return None
    elif isinstance(thedate, (str, unicode)):
        try:
            return datetime.datetime.strptime(thedate, _rfc1123_fmt)
        except ValueError:
            try:
                return datetime.datetime.strptime(thedate, _rfc850_fmt)
            except ValueError:
                return datetime.datetime.strptime(thedate, _asctime_fmt)
    else:
        return thedate.strftime(_rfc1123_fmt)

def hash_iterable(iterable):
    '''Computes a hash of an iterable based on the elements in the iterable.'''
    if isinstance(iterable, dict):
        iterable = iterable.itervalues()
    return hashlib.md5('nx'.join([str(i) for i in iterable])).hexdigest()

def environ_next(environ, keyfmt, value=True):
    '''Given a key format containing a %d placeholder, looks for the lowest number
    such that the format string with that number substituted does not exist in the
    environment, and assigns the given value to that key.

    Example: given modulo.%d, if modulo.0, modulo.1 and modulo.2 are keys in the
    environment, but modulo.3 is not, this function returns 3 and sets
    environ['modulo.3'] = value'''
    for n in count():
        if keyfmt % n not in req.environ:
            req.environ[keyfmt % n] = value
            return n

def uri_path(environ):
    path = environ.get('REQUEST_URI', None)
    if not path:
        path = environ.get('SCRIPT_NAME', '').rstrip('/') + '/' + environ.get('PATH_INFO', '').lstrip('/')
    return path

dummy = object()

class wrap_dict(dict):
    def __init__(self, parent):
        self.__parent = parent

    def __getitem__(self, key):
        try:
            val = super(wrap_dict, self).__getitem__(key)
        except KeyError:
            return self.__parent[key]
        else:
            if val is dummy:
                raise KeyError(key)
            return val

    def __delitem__(self, key):
        try:
            super(wrap_dict, self).__delitem__(key)
        except KeyError:
            self[key] = dummy

    def __del__(self):
        del self.__parent

def check_params(params):
    '''Returns a tuple(list, dict) based on input params.

    If None is passed, return [], {}. If only a list is passed, return
    params, {}. If only a dict is passed, return [], params. And if a
    two-element tuple is passed, if the second element is a dict, return
    params as passed; otherwise return list(params), {}.'''
    if isinstance(params, tuple):
        if len(params) is 2:
            args, kwargs = params
            if not isinstance(args, list):
                args = [args]
            if not isinstance(kwargs, dict):
                args.append(kwargs)
                kwargs = {}
            return args, kwargs
        else:
            return list(params), {}
    elif isinstance(params, list):
        return params, {}
    elif isinstance(params, dict):
        return [], params
    else:
        return [], {}

def compact(*names):
    caller = inspect.stack()[1][0] # caller of compact()
    vars = {}
    for n in names:
        if n in caller.f_locals:
            vars[n] = caller.f_locals[n]
        elif n in caller.f_globals:
            vars[n] = caller.f_globals[n]
    return vars

def extract(vars):
    caller = inspect.stack()[1][0] # caller of extract()
    for n, v in vars.iteritems():
        caller.f_locals[n] = v   # NEVER DO THIS ;-)

def func_default(new_func, old_func):
    '''Creates a wrapper function that calls new_func, then if the return value
    evaluates to False, calls old_func and returns that.'''
    if not old_func:
        return new_func
    def f(*args, **kwargs):
        v = old_func(*args, **kwargs)
        if not v:
            v = new_func(*args, **kwargs)
        return v
    return f
