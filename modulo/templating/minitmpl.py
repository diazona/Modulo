# -*- coding: iso-8859-1 -*-

from modulo.actions.standard import FileResource
from werkzeug.templates import Template

class MiniTemplate(FileResource):
    namespace = '*'
    def generate(self, rsp, **kwargs):
        template_data = self.req.environ.copy()
        template_data.update(kwargs)
        rsp.data = Template.from_file(self.filename).render(template_data)