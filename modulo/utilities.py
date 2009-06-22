#!/usr/bin/python

'''A dumping ground for all the random crap that accumulates in the course of development ;-)'''

import datetime
import hashlib

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
