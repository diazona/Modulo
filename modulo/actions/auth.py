#!/usr/bin/python

from modulo.actions import Action
from werkzeug.exceptions import Forbidden, HTTPException, Unauthorized

#######################################################################
# Authentication resources

class HTTPAuthentication(Action):
    '''Generic base class for HTTP basic/digest authentication.'''
    def generate(self):
        if not self.authenticate(self.req.authorization):
            raise Unauthorized()

    def authenticate(self, auth):
        '''Return True if the credentials are valid or False if not.

        This should be overridden in subclasses to check the
        authentication credentials. For basic authentication, check
        the username and password, available in auth.username and
        auth.password; for digest authentication, check the username
        and digest, available in auth.username and auth.response.'''
        return False

class BasicAuthentication(HTTPAuthentication):
    '''Handles HTTP basic authentication.

    This is meant to be subclassed.'''
    @classmethod
    def handles(cls, req):
        auth = req.authorization
        return auth is not None and auth.type == 'basic'

class DigestAuthentication(HTTPAuthentication):
    '''Handles HTTP digest authentication.

    This is meant to be subclassed.'''
    @classmethod
    def handles(cls, req):
        auth = req.authorization
        return auth is not None and auth.type == 'digest'

#######################################################################
# Authorization actions

class ForbiddenAuthorization(Action):
    '''An action which raises a 403 error if not authorized.'''
    def generate(self):
        if not self.req.root_action.authorized():
            raise Forbidden()

class LoginAuthorization(Action):
    '''A resource which redirects to a login page if not authorized.'''
    def generate(self):
        if not self.req.root_resource.authorized():
            raise LoginRedirect(self.login_url)
    login_url = None

class LoginRedirect(HTTPException):
    code = 303
    description = '<p>Login required</p>'

    def __init__(self, location):
        HTTPException.__init__(self)
        self.location = location

    def get_headers(self):
        return HTTPException.get_headers(self) + [('Location', self.location)]
