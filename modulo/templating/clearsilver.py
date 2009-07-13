#!/usr/bin/python

import neo_cgi
import neo_cs
import neo_util
import re
import time
from modulo.actions import Action
from modulo.actions.standard import FileResource
from modulo.templating import EmptyTemplateError
from modulo.utilities import environ_next

class ClearsilverDataFile(FileResource):
    def generate(self, rsp):
        if not hasattr(self.req, 'hdf'):
            self.req.hdf = neo_util.HDF()
        self.req.hdf.readFile(self.filename)

    @classmethod
    def ext_request_filename(cls, req):
        return cls.request_filename(req) + '.hdf'

class ClearsilverTemplate(FileResource):
    def generate(self, rsp):
        if not hasattr(self.req, 'hdf'):
            self.req.hdf = neo_util.HDF()
        if not hasattr(self.req, 'cs'):
            self.req.cs = neo_cs.CS(self.req.hdf)
        self.req.cs.parseFile(self.filename)

    @classmethod
    def ext_request_filename(cls, req):
        return cls.request_filename(req) + '.cst'

obj_re = re.compile(r'^<\w+ object at 0x[0-9a-f]{8}>|<type \'\w+\'>$')
debug = False # TODO: set this based on something

class ClearsilverRendering(Action):
    def generate(self, rsp):
        if not hasattr(self.req, 'hdf'):
            self.req.hdf = neo_util.HDF()
        hdf = self.req.hdf
        try:
            cs = self.req.cs
        except KeyError:
            raise EmptyTemplateError, 'No Clearsilver template objects defined'
        # emulate the Clearsilver CGI kit
        load_hdf_cgi_vars(self.req)
        load_hdf_cookie_vars(self.req)
        load_hdf_session_vars(self.req)
        load_hdf_common_vars(self.req)
        output = self.req.cs.render()
        if not output:
            raise EmptyTemplateError, 'Clearsilver template produced no output'
        rsp.data = output
        return True

def load_hdf_cgi_vars(req):
    '''Load request data into the HDF as is done by the CGI kit.

    This method loads the HTTP headers and CGI environment variables.'''
    def transfer_to_hdf(cgi_name, hdf_name):
        if cgi_name in req.environ:
            req.hdf.setValue(hdf_name, str(req.environ[cgi_name]))
    # this list is copied right out of Clearsilver's cgi/cgi.c
    transfer_to_hdf('AUTH_TYPE', 'CGI.AuthType')
    transfer_to_hdf('CONTENT_TYPE', 'CGI.ContentType')
    transfer_to_hdf('CONTENT_LENGTH', 'CGI.ContentLength')
    transfer_to_hdf('DOCUMENT_ROOT', 'CGI.DocumentRoot')
    transfer_to_hdf('GATEWAY_INTERFACE', 'CGI.GatewayInterface')
    transfer_to_hdf('PATH_INFO', 'CGI.PathInfo')
    transfer_to_hdf('PATH_TRANSLATED', 'CGI.PathTranslated')
    transfer_to_hdf('QUERY_STRING', 'CGI.QueryString')
    transfer_to_hdf('REDIRECT_REQUEST', 'CGI.RedirectRequest')
    transfer_to_hdf('REDIRECT_QUERY_STRING', 'CGI.RedirectQueryString')
    transfer_to_hdf('REDIRECT_STATUS', 'CGI.RedirectStatus')
    transfer_to_hdf('REDIRECT_URL', 'CGI.RedirectURL')
    transfer_to_hdf('REMOTE_ADDR', 'CGI.RemoteAddress')
    transfer_to_hdf('REMOTE_HOST', 'CGI.RemoteHost')
    transfer_to_hdf('REMOTE_IDENT', 'CGI.RemoteIdent')
    transfer_to_hdf('REMOTE_PORT', 'CGI.RemotePort')
    transfer_to_hdf('REMOTE_USER', 'CGI.RemoteUser')
    transfer_to_hdf('REMOTE_GROUP', 'CGI.RemoteGroup')
    transfer_to_hdf('REQUEST_METHOD', 'CGI.RequestMethod')
    transfer_to_hdf('REQUEST_URI', 'CGI.RequestURI')
    transfer_to_hdf('SCRIPT_FILENAME', 'CGI.ScriptFilename')
    transfer_to_hdf('SCRIPT_NAME', 'CGI.ScriptName')
    transfer_to_hdf('SERVER_ADDR', 'CGI.ServerAddress')
    transfer_to_hdf('SERVER_ADMIN', 'CGI.ServerAdmin')
    transfer_to_hdf('SERVER_NAME', 'CGI.ServerName')
    transfer_to_hdf('SERVER_PORT', 'CGI.ServerPort')
    transfer_to_hdf('SERVER_ROOT', 'CGI.ServerRoot')
    transfer_to_hdf('SERVER_PROTOCOL', 'CGI.ServerProtocol')
    transfer_to_hdf('SERVER_SOFTWARE', 'CGI.ServerSoftware')
    # SSL Vars from mod_ssl
    transfer_to_hdf('HTTPS', 'CGI.HTTPS')
    transfer_to_hdf('SSL_PROTOCOL', 'CGI.SSL.Protocol')
    transfer_to_hdf('SSL_SESSION_ID', 'CGI.SSL.SessionID')
    transfer_to_hdf('SSL_CIPHER', 'CGI.SSL.Cipher')
    transfer_to_hdf('SSL_CIPHER_EXPORT', 'CGI.SSL.Cipher.Export')
    transfer_to_hdf('SSL_CIPHER_USEKEYSIZE', 'CGI.SSL.Cipher.UseKeySize')
    transfer_to_hdf('SSL_CIPHER_ALGKEYSIZE', 'CGI.SSL.Cipher.AlgKeySize')
    transfer_to_hdf('SSL_VERSION_INTERFACE', 'CGI.SSL.Version.Interface')
    transfer_to_hdf('SSL_VERSION_LIBRARY', 'CGI.SSL.Version.Library')
    transfer_to_hdf('SSL_CLIENT_M_VERSION', 'CGI.SSL.Client.M.Version')
    transfer_to_hdf('SSL_CLIENT_M_SERIAL', 'CGI.SSL.Client.M.Serial')
    transfer_to_hdf('SSL_CLIENT_S_DN', 'CGI.SSL.Client.S.DN')
    transfer_to_hdf('SSL_CLIENT_S_DN_x509', 'CGI.SSL.Client.S.DN.x509')
    transfer_to_hdf('SSL_CLIENT_I_DN', 'CGI.SSL.Client.I.DN')
    transfer_to_hdf('SSL_CLIENT_I_DN_x509', 'CGI.SSL.Client.I.DN.x509')
    transfer_to_hdf('SSL_CLIENT_V_START', 'CGI.SSL.Client.V.Start')
    transfer_to_hdf('SSL_CLIENT_V_END', 'CGI.SSL.Client.V.End')
    transfer_to_hdf('SSL_CLIENT_A_SIG', 'CGI.SSL.Client.A.SIG')
    transfer_to_hdf('SSL_CLIENT_A_KEY', 'CGI.SSL.Client.A.KEY')
    transfer_to_hdf('SSL_CLIENT_CERT', 'CGI.SSL.Client.CERT')
    transfer_to_hdf('SSL_CLIENT_CERT_CHAINn', 'CGI.SSL.Client.CERT.CHAINn')
    transfer_to_hdf('SSL_CLIENT_VERIFY', 'CGI.SSL.Client.Verify')
    transfer_to_hdf('SSL_SERVER_M_VERSION', 'CGI.SSL.Server.M.Version')
    transfer_to_hdf('SSL_SERVER_M_SERIAL', 'CGI.SSL.Server.M.Serial')
    transfer_to_hdf('SSL_SERVER_S_DN', 'CGI.SSL.Server.S.DN')
    transfer_to_hdf('SSL_SERVER_S_DN_x509', 'CGI.SSL.Server.S.DN.x509')
    transfer_to_hdf('SSL_SERVER_S_DN_CN', 'CGI.SSL.Server.S.DN.CN')
    transfer_to_hdf('SSL_SERVER_S_DN_EMAIL', 'CGI.SSL.Server.S.DN.Email')
    transfer_to_hdf('SSL_SERVER_S_DN_O', 'CGI.SSL.Server.S.DN.O')
    transfer_to_hdf('SSL_SERVER_S_DN_OU', 'CGI.SSL.Server.S.DN.OU')
    transfer_to_hdf('SSL_SERVER_S_DN_C', 'CGI.SSL.Server.S.DN.C')
    transfer_to_hdf('SSL_SERVER_S_DN_SP', 'CGI.SSL.Server.S.DN.SP')
    transfer_to_hdf('SSL_SERVER_S_DN_L', 'CGI.SSL.Server.S.DN.L')
    transfer_to_hdf('SSL_SERVER_I_DN', 'CGI.SSL.Server.I.DN')
    transfer_to_hdf('SSL_SERVER_I_DN_x509', 'CGI.SSL.Server.I.DN.x509')
    transfer_to_hdf('SSL_SERVER_I_DN_CN', 'CGI.SSL.Server.I.DN.CN')
    transfer_to_hdf('SSL_SERVER_I_DN_EMAIL', 'CGI.SSL.Server.I.DN.Email')
    transfer_to_hdf('SSL_SERVER_I_DN_O', 'CGI.SSL.Server.I.DN.O')
    transfer_to_hdf('SSL_SERVER_I_DN_OU', 'CGI.SSL.Server.I.DN.OU')
    transfer_to_hdf('SSL_SERVER_I_DN_C', 'CGI.SSL.Server.I.DN.C')
    transfer_to_hdf('SSL_SERVER_I_DN_SP', 'CGI.SSL.Server.I.DN.SP')
    transfer_to_hdf('SSL_SERVER_I_DN_L', 'CGI.SSL.Server.I.DN.L')
    transfer_to_hdf('SSL_SERVER_V_START', 'CGI.SSL.Server.V.Start')
    transfer_to_hdf('SSL_SERVER_V_END', 'CGI.SSL.Server.V.End')
    transfer_to_hdf('SSL_SERVER_A_SIG', 'CGI.SSL.Server.A.SIG')
    transfer_to_hdf('SSL_SERVER_A_KEY', 'CGI.SSL.Server.A.KEY')
    transfer_to_hdf('SSL_SERVER_CERT', 'CGI.SSL.Server.CERT')
    # SSL Vars mapped from others
    # if we're running under mod_ssl w/ +CompatEnvVars, we set these twice...
    transfer_to_hdf('SSL_PROTOCOL_VERSION', 'CGI.SSL.Protocol')
    transfer_to_hdf('SSLEAY_VERSION', 'CGI.SSL.Version.Library')
    transfer_to_hdf('HTTPS_CIPHER', 'CGI.SSL.Cipher')
    transfer_to_hdf('HTTPS_EXPORT', 'CGI.SSL.Cipher.Export')
    transfer_to_hdf('HTTPS_SECRETKEYSIZE', 'CGI.SSL.Cipher.UseKeySize')
    transfer_to_hdf('HTTPS_KEYSIZE', 'CGI.SSL.Cipher.AlgKeySize')
    transfer_to_hdf('SSL_SERVER_KEY_SIZE', 'CGI.SSL.Cipher.AlgKeySize')
    transfer_to_hdf('SSL_SERVER_CERTIFICATE', 'CGI.SSL.Server.CERT')
    transfer_to_hdf('SSL_SERVER_CERT_START', 'CGI.SSL.Server.V.Start')
    transfer_to_hdf('SSL_SERVER_CERT_END', 'CGI.SSL.Server.V.End')
    transfer_to_hdf('SSL_SERVER_CERT_SERIAL', 'CGI.SSL.Server.M.Serial')
    transfer_to_hdf('SSL_SERVER_SIGNATURE_ALGORITHM', 'CGI.SSL.Server.A.SIG')
    transfer_to_hdf('SSL_SERVER_DN', 'CGI.SSL.Server.S.DN')
    transfer_to_hdf('SSL_SERVER_CN', 'CGI.SSL.Server.S.DN.CN')
    transfer_to_hdf('SSL_SERVER_EMAIL', 'CGI.SSL.Server.S.DN.Email')
    transfer_to_hdf('SSL_SERVER_O', 'CGI.SSL.Server.S.DN.O')
    transfer_to_hdf('SSL_SERVER_OU', 'CGI.SSL.Server.S.DN.OU')
    transfer_to_hdf('SSL_SERVER_C', 'CGI.SSL.Server.S.DN.C')
    transfer_to_hdf('SSL_SERVER_SP', 'CGI.SSL.Server.S.DN.SP')
    transfer_to_hdf('SSL_SERVER_L', 'CGI.SSL.Server.S.DN.L')
    transfer_to_hdf('SSL_SERVER_IDN', 'CGI.SSL.Server.I.DN')
    transfer_to_hdf('SSL_SERVER_ICN', 'CGI.SSL.Server.I.DN.CN')
    transfer_to_hdf('SSL_SERVER_IEMAIL', 'CGI.SSL.Server.I.DN.Email')
    transfer_to_hdf('SSL_SERVER_IO', 'CGI.SSL.Server.I.DN.O')
    transfer_to_hdf('SSL_SERVER_IOU', 'CGI.SSL.Server.I.DN.OU')
    transfer_to_hdf('SSL_SERVER_IC', 'CGI.SSL.Server.I.DN.C')
    transfer_to_hdf('SSL_SERVER_ISP', 'CGI.SSL.Server.I.DN.SP')
    transfer_to_hdf('SSL_SERVER_IL', 'CGI.SSL.Server.I.DN.L')
    transfer_to_hdf('SSL_CLIENT_CERTIFICATE', 'CGI.SSL.Client.CERT')
    transfer_to_hdf('SSL_CLIENT_CERT_START', 'CGI.SSL.Client.V.Start')
    transfer_to_hdf('SSL_CLIENT_CERT_END', 'CGI.SSL.Client.V.End')
    transfer_to_hdf('SSL_CLIENT_CERT_SERIAL', 'CGI.SSL.Client.M.Serial')
    transfer_to_hdf('SSL_CLIENT_SIGNATURE_ALGORITHM', 'CGI.SSL.Client.A.SIG')
    transfer_to_hdf('SSL_CLIENT_DN', 'CGI.SSL.Client.S.DN')
    transfer_to_hdf('SSL_CLIENT_CN', 'CGI.SSL.Client.S.DN.CN')
    transfer_to_hdf('SSL_CLIENT_EMAIL', 'CGI.SSL.Client.S.DN.Email')
    transfer_to_hdf('SSL_CLIENT_O', 'CGI.SSL.Client.S.DN.O')
    transfer_to_hdf('SSL_CLIENT_OU', 'CGI.SSL.Client.S.DN.OU')
    transfer_to_hdf('SSL_CLIENT_C', 'CGI.SSL.Client.S.DN.C')
    transfer_to_hdf('SSL_CLIENT_SP', 'CGI.SSL.Client.S.DN.SP')
    transfer_to_hdf('SSL_CLIENT_L', 'CGI.SSL.Client.S.DN.L')
    transfer_to_hdf('SSL_CLIENT_IDN', 'CGI.SSL.Client.I.DN')
    transfer_to_hdf('SSL_CLIENT_ICN', 'CGI.SSL.Client.I.DN.CN')
    transfer_to_hdf('SSL_CLIENT_IEMAIL', 'CGI.SSL.Client.I.DN.Email')
    transfer_to_hdf('SSL_CLIENT_IO', 'CGI.SSL.Client.I.DN.O')
    transfer_to_hdf('SSL_CLIENT_IOU', 'CGI.SSL.Client.I.DN.OU')
    transfer_to_hdf('SSL_CLIENT_IC', 'CGI.SSL.Client.I.DN.C')
    transfer_to_hdf('SSL_CLIENT_ISP', 'CGI.SSL.Client.I.DN.SP')
    transfer_to_hdf('SSL_CLIENT_IL', 'CGI.SSL.Client.I.DN.L')
    transfer_to_hdf('SSL_EXPORT', 'CGI.SSL.Cipher.Export')
    transfer_to_hdf('SSL_KEYSIZE', 'CGI.SSL.Cipher.AlgKeySize')
    transfer_to_hdf('SSL_SECKEYSIZE', 'CGI.SSL.Cipher.UseKeySize')
    transfer_to_hdf('SSL_SSLEAY_VERSION', 'CGI.SSL.Version.Library')
    transfer_to_hdf('SSL_STRONG_CRYPTO', 'CGI.SSL.Strong.Crypto')
    transfer_to_hdf('SSL_SERVER_KEY_EXP', 'CGI.SSL.Server.Key.Exp')
    transfer_to_hdf('SSL_SERVER_KEY_ALGORITHM', 'CGI.SSL.Server.Key.Algorithm')
    transfer_to_hdf('SSL_SERVER_KEY_SIZE', 'CGI.SSL.Server.Key.Size')
    transfer_to_hdf('SSL_SERVER_SESSIONDIR', 'CGI.SSL.Server.SessionDir')
    transfer_to_hdf('SSL_SERVER_CERTIFICATELOGDIR', 'CGI.SSL.Server.CertificateLogDir')
    transfer_to_hdf('SSL_SERVER_CERTFILE', 'CGI.SSL.Server.CertFile')
    transfer_to_hdf('SSL_SERVER_KEYFILE', 'CGI.SSL.Server.KeyFile')
    transfer_to_hdf('SSL_SERVER_KEYFILETYPE', 'CGI.SSL.Server.KeyFileType')
    transfer_to_hdf('SSL_CLIENT_KEY_EXP', 'CGI.SSL.Client.Key.Exp')
    transfer_to_hdf('SSL_CLIENT_KEY_ALGORITHM', 'CGI.SSL.Client.Key.Algorithm')
    transfer_to_hdf('SSL_CLIENT_KEY_SIZE', 'CGI.SSL.Client.Key.Size')
    # HTTP vars
    transfer_to_hdf('HTTP_ACCEPT', 'HTTP.Accept')
    transfer_to_hdf('HTTP_ACCEPT_CHARSET', 'HTTP.AcceptCharset')
    transfer_to_hdf('HTTP_ACCEPT_ENCODING', 'HTTP.AcceptEncoding')
    transfer_to_hdf('HTTP_ACCEPT_LANGUAGE', 'HTTP.AcceptLanguage')
    transfer_to_hdf('HTTP_COOKIE', 'HTTP.Cookie')
    transfer_to_hdf('HTTP_HOST', 'HTTP.Host')
    transfer_to_hdf('HTTP_USER_AGENT', 'HTTP.UserAgent')
    transfer_to_hdf('HTTP_IF_MODIFIED_SINCE', 'HTTP.IfModifiedSince')
    transfer_to_hdf('HTTP_REFERER', 'HTTP.Referer')
    transfer_to_hdf('HTTP_VIA', 'HTTP.Via')
    # SOAP
    transfer_to_hdf('HTTP_SOAPACTION', 'HTTP.Soap.Action')

def load_hdf_cookie_vars(req):
    '''Copies data from the cookies into the HDF object.'''
    cookies = getattr(req, 'cookies', None) or {}
    for key in cookies.keys():
        req.hdf.setValue('Cookie.' + key, cookies[key])

def load_hdf_session_vars(req):
    '''Initializes the session and loads its data into the HDF object.'''
    session = getattr(req, 'session', None) or {}
    for key in session.keys():
        req.hdf.setValue('Session.' + key, req.session[key])

def load_hdf_common_vars(req):
    '''Load the HDF with values common to every page'''
    req.hdf.setValue('common.currentyear', time.strftime('%Y'))
