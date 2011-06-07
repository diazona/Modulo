# -*- coding: utf-8 -*-

'''Currently this module just contains some initialization code having to do with
database access. It doesn't have any classes or useful variables. It may be
changed or moved in the future.'''

from elixir import metadata
from elixir.options import options_defaults

import settings

metadata.bind = settings.database_url

# MySQL has a 64-character table name length limit
options_defaults['shortnames'] = True
