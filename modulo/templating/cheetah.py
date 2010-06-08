# -*- coding: iso-8859-1 -*-

from __future__ import absolute_import

from Cheetah.Template import Template
from modulo.actions import Action
from modulo.actions.standard import FileResource
from os.path import join

class CheetahStringTemplate(Action):
    namespace = '*'
    def generate(self, rsp, **kwargs):
        rsp.data = str(Template(source=self.template, searchList=[self.req.environ, kwargs]))

class CheetahFilesystemTemplate(FileResource):
    namespace = '*'
    def generate(self, rsp, **kwargs):
        # Cheetah is not Unicode-aware, apparently, so we need to str(self.filename)
        rsp.data = str(Template(file=str(self.filename), searchList=[self.req.environ, kwargs]))

class CheetahCompiledTemplate(Action):
    '''Represents a compiled Cheetah template.'''
    namespace = '*'
    @classmethod
    def derive(cls, template, module=None, package=None, **kwargs):
        '''Return an Action corresponding to the given compiled template. This method
        requires one argument, 'template', which can be given as a keyword or positional
        argument. It can be either the compiled subclass of Template, or the name of the
        class as a string. Basically you can either import the template class yourself
        and pass it in, or let this class do the importing for you.
        
        If 'template' is a string, and the full qualified name of the module to import is
        the same string, then you're set. Otherwise, you need an additional argument, which
        could be given in various ways:
        -Pass the imported module that contains the template class as 'module'
        -Pass the full qualified name of the module that contains the template class as 'module',
         and this method will import it
        -If the unqualified name of the module is the same as the name of the class (which is
         the way Cheetah templates are compiled), you can pass the package name, a string, in
         the 'package' argument (and don't pass 'module'), and this class will import
         'package'.'template' and then import the template class from that
        -If you somehow managed to create a template with a class name that isn't the same as
         its module name, you can pass both 'package' and 'module' and this class will import
         the 'template' class from 'package'.'module'
        '''
        if isinstance(template, (str, unicode)):
            if isinstance(module, ModuleType):
                template = getattr(module, template)
            else:
                if module is None:
                    module = package + '.' + template
                elif package is not None:
                    module = package + '.' + module
                template = __import__(module, {}, {}, template)
        return super(CheetahCompiledTemplate, cls).derive(template=template, **kwargs)

    def generate(self, rsp, **kwargs):
        rsp.data = str(self.template(searchList=[self.req.environ, kwargs]))
