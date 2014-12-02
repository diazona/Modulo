# -*- coding: utf-8 -*-

'''Currently this module just contains some initialization code having to do with
database access. It doesn't have any classes or useful variables. It may be
changed or moved in the future.'''

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker

import settings


engine = create_engine(settings.database_url)
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

# Replaces the old Elixir Entity; use the same name for convenience
Entity = declarative_base(bind=engine)

__all__ = ['Session', 'Entity']