from __future__ import annotations
from app.storage.repository import InMemoryRepository
from app.storage.sqlite_repository import SqliteRepository

def build_repository(database_url: str):
    if database_url.startswith('postgresql'):
        from app.storage.postgres_repository import PostgresRepository
        return PostgresRepository(database_url)
    if database_url.startswith('sqlite:///'):
        return SqliteRepository(database_url.removeprefix('sqlite:///'))
    if database_url == 'memory://':
        return InMemoryRepository()
    raise RuntimeError('NEXVORY_DATABASE_URL_NAO_SUPORTADA')
