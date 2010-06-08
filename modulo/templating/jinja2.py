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
    namespace = '*'
    def generate(self, rsp, env, **kwargs):
        template_data = self.req.environ.copy()
        template_data.update(kwargs)
        rsp.response = self.env.get_template(self.template_name).generate(template_data)

class JinjaFilesystemTemplate(FileResource):
    namespace = '*'
    @classmethod
    def derive(cls, search_path, **kwargs):
        return super(JinjaFilesystemTemplate, cls).derive(env=Environment(loader=FileSystemLoader(search_path)), search_path=search_path, **kwargs)

    def generate(self, rsp, **kwargs):
        # Because Jinja handles the search path internally, we have to strip it off here
        template = self.filename
        if template.startswith(self.search_path):
            template = template[len(self.search_path):].lstrip('/')
        template_data = self.req.environ.copy()
        template_data.update(kwargs)
        rsp.response = self.env.get_template(template).generate(template_data)
