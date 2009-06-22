#!/usr/bin/python

import sys
from os.path import abspath, dirname

basedir = dirname(dirname(dirname(abspath(__file__))))
if basedir not in sys.path:
    sys.path.append(basedir)

from modulo import *
from modulo.resources.filters import *
from modulo.resources.standard import *
from modulo.templating.clearsilver import *
from modulo.test.hello import HelloWorldResource
from werkzeug import script
from werkzeug.routing import Map, Rule

def make_app():
    resource_tree = all_of(
        DateHeader,
        ContentTypeHeader,
        WerkzeugMapFilter.derive(wzmap = Map([
            Rule('/hello', endpoint=HelloWorldResource),
            Rule('/hello<anything>', endpoint=HelloWorldResource)
        ])) | all_of(
            any_of(
                all_of(
                    ClearsilverTemplate.derive(filename=classmethod(lambda cls, req: cls.request_filename(req) + '.cst')),
                    ClearsilverDataFile.derive(filename=classmethod(lambda cls, req: cls.request_filename(req) + '.hdf'))
                ),
                ClearsilverTemplate.derive(filename=classmethod(lambda cls, req: cls.request_filename(req) + '.cst')),
                ClearsilverDataFile.derive(filename=classmethod(lambda cls, req: cls.request_filename(req) + '.hdf'))
            ),
            ClearsilverRendering
        ) | FileResource
    )
    return WSGIModuloApp(resource_tree, raise_exceptions=True)

action_runserver = script.make_runserver(make_app, use_reloader=True, use_debugger=True)
action_shell = script.make_shell(lambda: {'app': make_app()})

if __name__ == '__main__':
    script.run()
