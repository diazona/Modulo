# -*- coding: utf-8 -*-

from string import Template

from modulo.actions import Action

class EmptyTemplateError(Exception):
    '''An exception to be raised when a template object is empty and produces no output.'''
    pass

class PythonTemplate(Action):
    namespace='*'
    @classmethod
    def derive(cls, template, **kwargs):
        if isinstance(template, basestring):
            template = Template(template)
        return super(PythonTemplate, cls).derive(template=template)
    def generate(self, rsp, **kwargs):
        rsp.data = self.template.substitute(kwargs)
