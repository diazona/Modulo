# -*- coding: utf-8 -*-

from elixir import metadata
from elixir.options import options_defaults

import settings

metadata.bind = settings.database_url

# MySQL has a 64-character table name length limit
options_defaults['shortnames'] = True
