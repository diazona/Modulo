#!/usr/bin/python

from modulo.actions.standard import FileResource
from werkzeug.templates import Template

class MiniTemplate(FileResource):
    def generate(self, rsp):
        rsp.data = Template.from_file(self.filename).render(self.req.environ)
        return True