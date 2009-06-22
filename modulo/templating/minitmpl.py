#!/usr/bin/python

from werkzeug.resources import FileResource
from werkzeug.templates import Template

class MiniTemplate(FileResource):
    def generate(self, rsp):
        rsp.data = Template.from_file(self.filename).render(self.req.environ)
        return True