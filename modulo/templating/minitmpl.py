# -*- coding: iso-8859-1 -*-

from modulo.actions import Action
from modulo.actions.standard import FileResource
from string import Template

class MiniTemplate(FileResource):
    namespace = '*'
    def generate(self, rsp, **kwargs):
        template_data = self.req.environ.copy()
        template_data.update(kwargs)
        rsp.data = Template.from_file(self.filename).render(template_data)
        
class MiniStringTemplate(Action):
    namespace = '*'
    @classmethod
    def derive(cls, template, **kwargs):
        return super(MiniStringTemplate, cls).derive(template=template, **kwargs)
    def generate(self, rsp, **kwargs):
        template_data = self.req.environ.copy()
        template_data.update(kwargs)
        rsp.data = Template(self.template).render(template_data)
        