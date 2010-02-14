# -*- coding: iso-8859-1 -*-

from __future__ import absolute_import

from genshi.template import TemplateLoader
from modulo.actions import Action
from modulo.actions.standard import FileResource
from os.path import join

class GenshiFilesystemTemplate(FileResource):
    @classmethod
    def derive(cls, search_path, filename=None, **kwargs):
        loader = TemplateLoader(search_path)
        return super(GenshiFilesystemTemplate, cls).derive(search_path=search_path, loader=loader, filename=filename, **kwargs)

    def generate(self, rsp, **kwargs):
        # Because Genshi handles the search path internally, we have to strip it off here
        template = self.filename
        if template.startswith(self.search_path):
            template = template[len(self.search_path):].lstrip('/')
        template_data = self.req.environ.copy()
        template_data.update(kwargs)
        rsp.response = self.loader.load(template).generate(**template_data).render('html', doctype='html')
