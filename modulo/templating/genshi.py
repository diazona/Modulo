# -*- coding: iso-8859-1 -*-

from __future__ import absolute_import

from genshi.template import TemplateLoader
from modulo.actions import Action
from modulo.actions.standard import FileResource
from os.path import isfile, join

# Used for loading templates specified by filename when no
# custom loader is provided
_loader = None

class GenshiFilesystemTemplate(FileResource):
    @classmethod
    def derive(cls, filename=None, search_path=None, loader=None, **kwargs):
        if filename is None:
            # Creating a dynamically loading action
            if loader is None:
                loader = TemplateLoader(search_path)
            search_path = loader.search_path
            return super(GenshiFilesystemTemplate, cls).derive(search_path=search_path, loader=loader, **kwargs)
        else:
            # Creating a single-template action
            return super(GenshiFilesystemTemplate, cls).derive(filename=filename, **kwargs)

    def generate(self, rsp, **kwargs):
        global _loader
        template_data = self.req.environ.copy()
        template_data.update(kwargs)
        try:
            loader = self.loader
        except AttributeError:
            if _loader is None:
                _loader = TemplateLoader()
            loader = _loader
        template = loader.load(self.filename)
        rsp.response = template.generate(**template_data).render(getattr(self, 'mode', 'html'), doctype=getattr(self, 'doctype', 'html'))
