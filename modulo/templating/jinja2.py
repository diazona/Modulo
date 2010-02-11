# -*- coding: iso-8859-1 -*-

from __future__ import absolute_import

from jinja2 import Environment, FileSystemLoader
from modulo.actions import Action
from modulo.actions.standard import FileResource
from os.path import join

class JinjaEnvironment(Action):
    @classmethod
    def derive(cls, env=None, loader=None, bytecode_cache=None, **kwargs):
        if env is None:
            env = Environment(loader=loader, bytecode_cache=bytecode_cache)
        return super(JinjaEnvironment, cls).derive(env=env, **kwargs)
    def parameters(self):
        return {'env': self.env}

class JinjaTemplate(Action):
    def generate(self, rsp, env, **kwargs):
        template_data = self.req.environ.copy()
        template_data.update(kwargs)
        rsp.response = self.env.get_template(self.template_name).generate(template_data)

class JinjaFilesystemTemplate(FileResource):
    @classmethod
    def derive(cls, search_path, template_name=None, **kwargs):
        if template_name:
            # Don't call FileResource.derive, instead call (superclass of FileResource).derive
            # because we have filename() implemented as a proper class method, we don't need
            # to pass it in to derive()
            return super(FileResource, cls).derive(env=Environment(loader=FileSystemLoader(search_path)), search_path=search_path, template_name=template_name)
        else:
            return super(FileResource, cls).derive(env=Environment(loader=FileSystemLoader(search_path)), search_path=search_path)

    @classmethod
    def filename(cls, req, params):
        if callable(cls.template_name):
            return join(cls.search_path, cls.template_name(req, params))
        else:
            return join(cls.search_path, cls.template_name)
            
    @classmethod
    def template_name(cls, req, params):
        return req.path.lstrip('/')
        
    def __init__(self, req, params):
        super(JinjaFilesystemTemplate, self).__init__(req, params)
        self.template_name = self.template_name(req, params)

    def generate(self, rsp, **kwargs):
        template_data = self.req.environ.copy()
        template_data.update(kwargs)
        rsp.response = self.env.get_template(self.template_name).generate(template_data)
