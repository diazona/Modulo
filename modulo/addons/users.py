# -*- coding: iso-8859-1 -*-

import datetime
import logging
import random
from elixir import session, setup_all
from elixir import Binary, DateTime, Entity, Field, ManyToOne, ManyToMany, OneToMany, String, Unicode, UnicodeText
from hashlib import sha256
from hmac import HMAC
from modulo.actions import Action
from modulo.utilities import compact
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound
from werkzeug import redirect
from werkzeug.exceptions import InternalServerError, abort

def salt():
    '''Produces a 64-bit salt value'''
    return "".join(chr(random.randrange(256)) for i in xrange(8))

def hash_password(salt, password):
    result = password
    for i in xrange(1000): # 1000 iterations
        result = HMAC(salt, result, sha256).digest() # use HMAC to apply the salt
    return result

#---------------------------------------------------------------------------
# Database models
#---------------------------------------------------------------------------
class User(Entity):
    login = Field(Unicode(64))
    salt = Field(Binary(8))
    password_hash = Field(Binary(256))
    email = Field(Unicode(1024))
    status = Field(String(8))
    name = Field(Unicode(64))
    join_date = Field(DateTime)

    openids = OneToMany('OpenID')
    permissions = ManyToMany('Permission')

    def check_password(self, password):
        return str(self.password_hash) == hash_password(self.salt, password)

class OpenID(Entity):
    openid = Field(String(256))

    user = ManyToOne('User')

class Permission(Entity):
    permission = Field(String(32))

    user = ManyToMany('User')

class VerificationRequest(Entity):
    request_time = Field(DateTime)
    new_login = Field(Unicode(64))
    new_salt = Field(Binary(8))
    new_password_hash = Field(Binary(256))
    new_email = Field(Unicode(1024))
    new_status = Field(String(8))
    vcode = Field(String(64))

    user = ManyToOne('User')

    def check_password(self, password):
        return str(self.password_hash) == hash_password(self.salt, password)

    def verify(self, password, vcode):
        '''Attempts to put this request into effect.'''
        if self.vcode == vcode and self.check_password(password):
            if not self.user:
                self.user = User()
            u = self.user
            if self.new_login:
                u.login = self.new_login
            if self.new_password_hash and self.new_salt:
                u.password_hash = self.new_password_hash
                u.salt = self.new_salt
            if self.new_email:
                u.email = self.new_email
            if self.new_status:
                u.status = self.new_status
            u.save()
            return True
        else:
            return False

setup_all()

#---------------------------------------------------------------------------
# General stuff
#---------------------------------------------------------------------------

class UserDataAggregator(Action):
    def generate(self, rsp):
        d = {}
        for field in ('user_login', 'user_password', 'user_email', 'user_status', 'user_name'):
            if field in self.req.form:
                d[field] = self.req.form[field]
        return d

class CurrentUserCheck(Action):
    def generate(self, rsp):
        uid = self.req.session.get('user_id', None)
        try:
            u = User.query.filter_by(id=uid).one()
        except NoResultFound:
            pass
        else:
            return {'user': u}

#---------------------------------------------------------------------------
# User authentication
#---------------------------------------------------------------------------

class Authentication(Action):
    def generate(self, rsp, user_login, user_password):
        if user_login and user_password:
            try:
                u = User.query.filter_by(login=user_login).one()
            except MultipleResultsFound:
                # ahhhhh!
                logging.getLogger('modulo.addons.users').error('multiple users with same login ' + user_login)
                raise InternalServerError
            except NoResultFound:
                # no such user
                return
            else:
                if u.check_password(user_password):
                    logging.getLogger('modulo.addons.users').info('successful login attempt for user %s' % user_login)
                    self.req.session['user_id'] = u.id
                    return {'user': u}
                else:
                    logging.getLogger('modulo.addons.users').info('failed login attempt for user %s' % user_login)

class AuthenticationFailureRedirect(Action):
    def generate(self, rsp, user=None):
        if user is None:
            abort(redirect(self.failure_uri, 303))

class AuthenticationFailureForbidden(Action):
    def generate(self, rsp, user=None):
        if user is None:
            abort(403)

class LoginCookie(Action):
    persist_default = False

    def generate(self, rsp, user):
        if self.req.values.get('persist', self.persist_default):
            rsp.set_cookie('sessionid', self.req.session.sid, max_age=31536000) # 1 year
        else:
            rsp.set_cookie('sessionid', self.req.session.sid)

class LogoutProcessor(Action):
    def generate(self, rsp, user=None):
        if user:
            rsp.delete_cookie('sessionid')

#---------------------------------------------------------------------------
# User creation/modification
#---------------------------------------------------------------------------

class CreateUser(Action):
    def generate(self, rsp, user_login, user_password, user_email=None, user_status=None, user_name=None):
        u = User()
        u.login = user_login
        u.salt = salt()
        u.password_hash = hash_password(u.salt, user_password)
        u.email = user_email
        u.status = user_status
        u.name = user_name
        u.join_date = datetime.datetime.now()
        u.save()
        session.commit()
        return {'user': u}

class Verification(Action):
    @classmethod
    def handles(cls, req):
        return 'v' in req.form
    
    def generate(self, rsp, user_login, user_password):
        vcode = self.req.form['v']
        if user_login and user_password and vcode:
            # new user logging in, needs to be verified
            try:
                vreq = VerificationRequest.query.filter_by(new_login=user_login, vcode=vcode).one()
            except MultipleResultsFound:
                # ahhhhh!
                logging.getLogger('modulo.addons.users').error('multiple results with same vcode ' + vcode)
                raise InternalServerError
            except NoResultFound:
                # no such request
                return
            else:
                if vreq.verify(user_password, vcode):
                    logging.getLogger('modulo.addons.users').info('successfully activated new user %s' % user_login)
                    u = vreq.user
                    vreq.delete()
                    session.commit()
                    return {'user': u}
                else:
                    logging.getLogger('modulo.addons.users').info('failed activation for new user %s' % user_login)
