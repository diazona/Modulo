# -*- coding: iso-8859-1 -*-

from elixir import metadata

try:
    import settings
    metadata.bind = settings.database_url
except (AttributeError, ImportError):
    metadata.bind = 'sqlite:///modulo.sqlite'
