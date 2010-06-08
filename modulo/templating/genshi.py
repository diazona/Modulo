# -*- coding: iso-8859-1 -*-

from __future__ import absolute_import

from genshi.template import TemplateLoader
from modulo.actions import Action
from modulo.actions.standard import FileResource
from os.path import isfile, join

# Used for loading templates specified by filename when no
# custom loader is provided
_loader_instance = None

def _loader():
    if _loader_instance is None:
        _loader_instance = TemplateLoader(auto_reload=True)
    return _loader_instance

class GenshiFilesystemTemplate(FileResource):
    namespace = '*'
    @classmethod
    def derive(cls, filename=None, search_path=None, loader=None, **kwargs):
        # Need to make sure the search_path parameter matches the loader's search path
        if search_path is None and loader is None:
            # Creating a single-template action
            return super(GenshiFilesystemTemplate, cls).derive(filename=filename, **kwargs)
        else:
            if loader is None:
                if search_path is None:
                    loader = _loader()
                else:
                    loader = TemplateLoader(search_path, auto_reload=True)
            search_path = loader.search_path
            if filename is None:
                # Creating a dynamically loading action
                return super(GenshiFilesystemTemplate, cls).derive(search_path=search_path, loader=loader, **kwargs)
            else:
                # Creating a single-template action
                return super(GenshiFilesystemTemplate, cls).derive(filename=filename, search_path=search_path, loader=loader, **kwargs)

    def generate(self, rsp, **kwargs):
        template_data = self.req.environ.copy()
        template_data.update(kwargs)
        try:
            loader = self.loader
        except AttributeError:
            loader = _loader()
        template = loader.load(self.filename)
        return {'stream': template.generate(**template_data)}

class GenshiFilter(Action):
    @classmethod
    def derive(cls, filter, **kwargs):
        return super(GenshiFilter, cls).derive(filter=filter, **kwargs)

    def generate(self, rsp, stream):
        return {'stream': stream.filter(self.filter)}

class GenshiStreamRenderer(Action):
    def generate(self, rsp, stream):
        rsp.data = stream.render(getattr(self, 'mode', 'html'), doctype=getattr(self, 'doctype', 'html'))
        del stream
        return {'stream': None}

