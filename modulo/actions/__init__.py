# -*- coding: utf-8 -*-

'''Infrastructure for the action architecture.

"Action architecture" reflects the fact that in a dynamic web application,
a single page is typically generated by putting together several different sources
of information: database queries, template files, static data files, maybe some
information from a cache, or something wacky and completely application-specific.
Different properties combine in different ways - for instance, the modification
time of a page is the latest modification time of any of the resources involved
in creating it, the credentials required to access a protected page should
be the union of the credentials required to access each resource, etc. etc. etc.
Most web programming environments don't seem to be designed with this architecture
in mind; you can still see remnants (sometimes strong remnants) of the old
static-file approach, where all the content and metadata come from one source,
either a static file or a CGI script. In contrast, the action architecture
lets you specify the content and properties of each resource individually,
and the system takes care of putting them together.'''

import logging
import os
import random
import re
import time
import urlparse
import weakref
from copy import copy
from modulo.utilities import check_params, hash_iterable, attribute_dict, wrap_dict
from modulo.wrappers import Request
from os.path import dirname, isfile, join, splitext
from stat import ST_MTIME
from werkzeug import validate_arguments
from werkzeug import ArgumentValidationError, BaseRequest
from werkzeug.exceptions import InternalServerError, NotFound

__all__ = ['all_of', 'any_of', 'opt', 'Action']

def all_of(*cls):
    '''Creates an ``Action`` subclass that passes requests to all given classes.

    The returned subclass is a dynamically created subclass of :class:`AllActions`
    called ``AllActions_<hash value>``, where ``<hash value>`` is a deterministic
    function of the arguments provided to this function. The subclass delegates calls
    to :meth:`~Action.handles` to its constituent classes (the parameters given in
    ``cls``) such that the ``AllActions`` subclass only accepts the request if *all*
    its constituent classes individually accept the request. When an instance of
    ``AllActions_<hash value>`` is created in the second phase of processing, it
    internally also creates instances of all its constituent classes to which it
    will delegate calls to instance methods like :meth:`update_mtime` and
    :meth:`generate`.

    If one of the parameters to this method is itself a subclass of ``AllActions``,
    its list of constituent classes, rather than the parameter class itself, will
    be copied into the new ``AllActions``. This reduces the total number of instances
    of ``AllActions`` necessary.'''
    handler_classes = []
    for n in cls:
        if not issubclass(n, Action):
            return NotImplemented
        if issubclass(n, AllActions):
            handler_classes.extend(n.handler_classes)
        else:
            handler_classes.append(n)
    # Use the metaclass to create a dynamic subclass of AllActions
    # with our list of handler classes.
    return ActionMetaclass('AllActions_%s' % hash_iterable(handler_classes), (AllActions,), {'handler_classes': handler_classes})

def any_of(*cls, **kwargs):
    '''Creates an ``Action`` subclass that passes requests to one of the given classes.

    The returned subclass is called AnyAction_<hash value>, where <hash value> is
    a deterministic function of the arguments. It delegates calls to handles() to
    its constituent classes (the parameters given in cls) such that it accepts the
    request (returns True) if *any* of the constituent classes individually accept
    the request. Instances of AnyAction are never actually created; when you
    construct a AnyAction for a given request, what you actually get is an
    instance of the first constituent class which has agreed to handle the request.

    If one of the parameters to this method is itself a subclass of AnyAction,
    its list of constituent classes, rather than the parameter class itself, will
    be copied into the new AnyAction. This reduces the total number of instances
    of AnyAction necessary.'''
    handler_classes = []
    for n in cls:
        if not issubclass(n, Action):
            return NotImplemented
        if issubclass(n, AnyAction):
            handler_classes.extend(n.handler_classes)
        else:
            handler_classes.append([0,n])
    return type('AnyAction_%s' % hash_iterable(handler_classes), (AnyAction,), {'handler_classes': handler_classes, '_count': 8, '_sortable': kwargs.get('sortable', False)})

def opt(cls):
    '''Creates an Action subclass that wraps a given handler class to make it optional.

    The returned subclass is called OptAction_<hash value>, where <hash value> is a
    deterministic function of the argument. It returns True from handles(req) for all
    requests, but if its constituent class (the parameter given in cls) doesn't actually
    handle the request, attempting to create an instance of OptAction returns a NoopHandler
    (which does nothing) instead. If the constituent class does handle the request, than an
    instance of it itself is created and returned.

    If the parameter to this method is itself a subclass of OptAction, then it will be
    returned itself, rather than a new OptAction being created to wrap it.'''
    if not issubclass(cls, Action):
        return NotImplemented
    elif cls.__name__.startswith('OptAction'):
        return cls
    else:
        return type('OptAction_%s' % hash_iterable([cls]), (OptAction,), {'handler_class': cls})

class ActionMetaclass(type):
    '''A metaclass that grants composition methods to the Action class itself.'''
    __and__ = all_of
    __or__ = any_of
    __invert__ = opt

    # Python voodoo ;-) make Action() call Action.derive() and Action.handle() call Action()
    def __call__(self, *args, **kwargs):
        # create a subclass
        d = self.derive(*args, **kwargs)
        assert d is not None, str(self) + '.derive() returned None (perhaps the programmer forgot a return statement)'
        return d

    def __str__(self):
        if len(self.__name__) > 33 and self.__name__[-33] == '_':
            # it's a derived subclass
            return '%-22s  [%s]' % (self.__name__[:-33], self.__name__[-32:])
        else:
            return '%-22s   <standard>' % (self.__name__)

    def handle(self, req, params):
        # construct a new Action
        h = super(ActionMetaclass, self).__call__(req, params)
        return h

class Action(object):
    '''Represents an action that can be taken by the server.

    A web application is created by constructing a tree of these objects. Each time a
    request comes in, it is passed to each one in turn to give that handler a chance
    to do whatever it needs to do with the request. Note that this allows multiple
    handlers to run, each modifying the request in some manner, so typically the
    response that winds up being returned to the client is a composite thing put
    together from different parts provided by different handlers.'''
    __metaclass__ = ActionMetaclass
    
    # This attribute is a bit of a hack: when set to true, it tells AllActions to
    # catch and ignore any NotFound exception raised by the generate() method.
    # This is because some actions indicate that their required resource is not
    # available by raising NotFound from generate() instead of returning False
    # from handles(), but we need to have a way to skip them when they're optional.
    _opt = False

    @classmethod
    def derive(cls, **kwargs):
        '''Returns a subclass of this class with selected class variables set.

        You can think of ``derive()`` as a constructor of sorts. Normally, of course,
        a constructor takes a class and some values and creates an instance
        of the class based on those values. This method works similarly, except
        that instead of creating an instance, it creates a subclass. By default,
        each keyword argument passed to ``derive()`` will be copied over to a 
        corresponding class variable of that subclass. For example,
        ``Action.derive(foo='bar')`` returns a subclass of ``Action`` with a class
        variable ``foo`` that has a default value of ``bar``. Another way
        to get the same effect would be ::
        
            class RandomActionSubclass(Action):
                foo = 'bar'
        
        Some subclasses of Action override ``derive()`` to do something more
        complicated with the given values, but they generally wind up as
        class variables in some form.
        
        The subclass returned by ``derive()`` will have a name of the form
        ``<class name>_<hash value>``, where ``<class name>` is the name of the base
        class, and ``<hash value>`` is some deterministic function of the keys and
        values passed in as keyword arguments. (The specific hash function used
        is purposely undocumented and may change; in practice it should probably
        never be necessary to know the hash generated.)

        If you write a subclass of Action that requires this sort of customization,
        and you don't have default values for the custom class variables, you can
        override ``derive()`` as follows to specify which properties your class
        requires::

            def derive(cls, <property1>, <property2>, ..., **kwargs):
                return super(<class>, cls).derive(<property1>=<property1>, <property2>=<property2>, ..., **kwargs)

        Just replace ``property1``, ``property2``, etc. in all three spots with the name of
        each property, and ``<class>`` with the name of the class. Make sure to leave the
        ``**kwargs`` in at the end, because your class might be subclassed yet again and
        the subsubclass might want to have additional custom properties. It's boilerplate
        code but I haven't found a way to reduce it further than this. If you have sensible
        defaults for all your properties, you can just set those defaults as class variables
        and then you don't have to override ``derive()`` at all.
        
        In any case, you really should document which variables ``derive()`` accepts or
        requires for your class, if any.'''
        return type('%s_%s' % (cls.__name__, hash_iterable(kwargs)), (cls,), kwargs)

    def __new__(cls, req, params):
        '''Creates an instance of an ``Action`` subclass ``cls``, if the class handles
        the request.
        
        If the :meth:`~Action.handles` method of ``cls`` returns true when called
        with ``req`` and ``params``, this method will act like a normal constructor and
        return an instance of the class, customized to handle the given request. However,
        if ``cls`` doesn't handle the request, this will return ``None``.'''
        if cls.handles(req, params):
            return super(Action, cls).__new__(cls, req, params)
        else:
            return None

    @classmethod
    def handles(cls, req, params):
        '''Indicates whether this handler can handle the given request.

        If this method returns False, all operations on this handler for this
        request will be skipped. This includes computation of the last modified date.

        This is the very first thing to be called on a handler for a given request.
        It should not have any side effects.

        The default behavior is to return True, so handlers will accept all requests
        by default.'''
        return True

    def __init__(self, req, params):
        '''Initializes the handler.
        
        Generally if this is overridden in a subclass, it should only be used to
        initialize the subclass's instance variables. ``req`` and ``params`` should
        be considered effectively read-only, i.e. don't modify them in ``__init__()``
        unless you know what you're doing.
        
        If you do need to make changes to the request, for example to alter the value
        of some WSGI environment variable, do it in :meth:`transform`, not here.'''
        super(Action, self).__init__()
        if self.__class__.transform.im_func is not Action.transform.im_func:
            environ = req.environ.copy()
            self.transform(environ)
            self.req = req.__class__(environ)
        else:
            self.req = req
        if self.__class__.parameters.im_func is not Action.parameters.im_func:
            p = self.parameters()
            if p is not None:
                assert isinstance(p, dict)
                ns = getattr(self, 'namespace', '')
                assert ns != '*', 'Need to implement namespace \'*\''
                ns_params = params[ns].copy()
                self.params = params.copy()
                self.params[ns] = ns_params
                ns_params.update(p)
            else:
                self.params = params
        else:
            self.params = params

    def transform(self, environ):
        '''An opportunity for this Action to transform the request. If this method is
        overridden, it will be called with a copy of the current WSGI environ as a
        parameter. It can make any changes to the environ variables, and the resulting
        environment will be used when asking further actions to handle the request.
        This can be used to implement things like consuming path components.

        Changes can be made in place to the environ parameter, it's not necessary to
        return the new environment from this method.

        By default this method just does nothing.'''
        pass

    def parameters(self):
        '''Sets the values of any parameters that need to be added to the parameter set
        by this action. This is called in the first phase of processing, when it's still
        undetermined which actions exactly are going to be handling the request. So this
        method shouldn't do anything expensive and shouldn't have any side effects.
        (Operations with side effects belong in :meth:`generate`.)

        A subclass's ``__new__`` method can also set its parameters manually by assigning to
        the instance variable ``self.params``.'''
        pass

    def authorized(self):
        '''Return true if the user on the other end of the current request is authorized
        to access this action, or false if not.
        
        This should be overridden if you're writing an action that represents some resource
        which should have restricted access. Just implement this method to return true or
        false depending on ``self.req`` and/or ``self.params``. Modulo calls the ``authorized()``
        methods of all ``Action`` instances created for a given request, and if any of them
        returns false, it denies access. This way, as long as this method is implemented
        correctly, you can be sure that nobody will be able to access the resource
        without having passed the proper identification checks.
        
        .. todo:: Make sure that ``authorized()`` does actually get called at the right time
        
        By default, this method returns ``True``.'''
        return True

    def last_modified(self):
        '''Return the last modification time of the resource as a ``datetime`` object.
        This is mostly useful for things like files that have a modification time. You
        could use it for database records as well.
        
        The modification time of the generated page will be set to the latest modification
        time of any resource involved in creating it.
        
        By default, this method returns ``0``. This is a special case in which the return
        value doesn't have to be a ``datetime`` object. The ``0`` will be interpreted to
        mean that it doesn't make sense to define a modification time for whatever this
        action represents.'''
        return 0

    def action_id(self):
        '''Return a deterministic ID for the current action, used in generating the
        Etag. The ID should reflect the content generated by the action (i.e. if the
        action generates different content for two different requests, it should
        provide a different ID for each).'''
        return 0

    def generate(self, rsp, *args, **kwargs):
        '''Generates the portion of the response, or generally takes whatever action
        is necessary for this action.

        This method is supposed to include any expensive content generation procedure
        that should be skipped if, for example, the client already has the response
        cached. So if this method is called at all for a given request, it's an
        indication that the Last-Modified header has been computed and checked against
        any If-Modified-Since sent by the client, and it's been determined that we
        do need to create and send a new response. This method can and should access
        its data from a cache if appropriate, rather than automatically running some
        expensive database access or such every time.

        generate() may return a dictionary which will be added to the parameter set.

        If this method throws any exception it will be trapped and a 500 error page
        will be generated.'''
        pass

    def __str__(self):
        cls = self.__class__
        if len(cls.__name__) > 33 and cls.__name__[-33] == '_':
            # it's a derived subclass
            return '%s [%s]' % (cls.__name__[:-33], cls.__name__[-32:])
        else:
            return '%s  <standard>' % (cls.__name__)

class HashKey(object):
    '''A surrogate key for objects which are not themselves hashable'''
    def __new__(cls, req):
        try:
            hk = req.hashkey
        except AttributeError:
            hk = req.hashkey = super(HashKey, cls).__new__(cls, req)
        return hk

    def __init__(self, req):
        if not hasattr(self, 'hashcode'):
            self.hashcode = hash(random.getrandbits(32))

    def __hash__(self):
        return self.hashcode

accept_fmt = '%-60s accepting request %s'
reject_fmt = '%-60s rejecting request %s'

class AllActions(Action):
    @classmethod
    def handles(cls, req, params):
        # We override handles() so that we can use super(...).__new__(...)
        # in the constructor, instead of having to resort to object.__new__(...)
        return True

    def __new__(cls, req, params):
        handlers = []
        for hc in cls.handler_classes:
            h = hc.handle(req, params)
            if h is None:
                logging.getLogger('modulo.actions').debug(reject_fmt % (hc, req))
                del req
                return None
            elif isinstance(h, AllActions):
                logging.getLogger('modulo.actions').debug(accept_fmt % (hc, req))
                if h._opt:
                    for hndl in h.handlers:
                        hndl._opt = True
                handlers.extend(h.handlers)
                req = h.req
                params = h.params
                del h
            else:
                logging.getLogger('modulo.actions').debug(accept_fmt % (hc, req))
                handlers.append(h)
                req = h.req
                params = h.params
        if len(handlers) == 1:
            return handlers[0]
        elif len(handlers) == 0:
            return None
        else:
            instance = super(AllActions, cls).__new__(cls, req, params)
            for h in handlers:
                h.req = req
                h.params = params
            instance.req = req
            instance.params = params
            instance.handlers = handlers
            return instance

    def __init__(self, req, params):
        # it took a year to come up with this. don't ask.
        #
        # Seriously though: when an object is constructed, Python always calls __init__ with
        # the same parameters that were passed to __new__. But in this class, __new__ can
        # replace the req parameter with a new request object. So in order to make sure the
        # req field of an Action gets set with the new request object and not the original
        # one that was passed to __new__, we need to set instance.req = req manually in __new__
        # rather than putting that line here in __init__ where it would ordinarily go.
        #
        # Same for params.
        pass

    def __del__(self):
        del self.handlers

    def __str__(self):
        return '\n'.join(str(h) for h in self.handlers) + '\n'

    def authorized(self):
        return all(h.authorized() for h in self.handlers)

    def last_modified(self):
        return max(h.last_modified() for h in self.handlers)

    def action_id(self):
        return hash_iterable(filter(None, (h.action_id() for h in self.handlers)))

    def generate(self, rsp):
        for h in self.handlers:
            namespace = getattr(h, 'namespace', '')
            params = self.params[''].copy()
            if namespace == '*':
                for ns in self.params:
                    if ns:
                        for key in self.params[ns]:
                            params[ns] = attribute_dict(self.params[ns])
            else:
                if namespace:
                    params.update(self.params[namespace])
            try:
                hargs, hkwargs = validate_arguments(h.generate, [h, rsp], params, True)
            except ArgumentValidationError, e:
                logging.getLogger('modulo.actions').exception('Missing arguments in handler %s: %s', h, tuple(e.missing))
                raise
            try:
                p = h.generate(rsp, *(hargs[2:]), **hkwargs)
            except NotFound:
                if not h._opt:
                    raise
            hargs, hkwargs = check_params(p)
            if namespace not in ('','*'):
                self.params[namespace].update(hkwargs)
            else:
                self.params[''].update(hkwargs)

class AnyAction(Action):
    def __new__(cls, req, params):
        for hc in cls.handler_classes[:]:
            h = hc[1].handle(req, params)
            if h is None:
                logging.getLogger('modulo.actions').debug(reject_fmt % (hc[1], req))
            else:
                logging.getLogger('modulo.actions').debug(accept_fmt % (hc[1], req))
                hc[0] += 1
                if cls._sortable:
                    cls._count -= 1
                    if cls._count <= 0:
                        logging.getLogger('modulo.actions').debug(str(cls) + ' sorting actions: ' + ','.join(str(h[0]) for h in cls.handler_classes))
                        cls.handler_classes.sort(key=lambda h: h[0], reverse=True)
                        cls._count = sum(h[0] for h in cls.handler_classes)
                return h
        return None
        # Note that we never call super(...).__new__(...) here. So there is no
        # need to override handles().

class OptAction(Action):
    def __new__(cls, req, params):
        h = cls.handler_class.handle(req, params)
        if h is None:
            logging.getLogger('modulo.actions').debug(reject_fmt % (cls.handler_class, req))
            return Action.handle(req, params)
        else:
            logging.getLogger('modulo.actions').debug(accept_fmt % (cls.handler_class, req))
            h._opt = True
            return h
