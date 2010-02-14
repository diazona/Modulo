# -*- coding: iso-8859-1 -*-

from __future__ import absolute_import

from mako.template import Template
from modulo.actions import Action
from modulo.actions.standard import FileResource

class MakoStringTemplate(Action):
    def generate(self, rsp, **kwargs):
        template_data = self.req.environ.copy()
        template_data.update(kwargs)
        rsp.response = Template(self.template).render_unicode(**template_data)

class MakoFilesystemTemplate(FileResource):
    def generate(self, rsp, **kwargs):
        template_data = self.req.environ.copy()
        template_data.update(kwargs)
        rsp.data = Template(filename=self.filename).render_unicode(**template_data)
