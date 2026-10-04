from app.storage.factory import build_repository
from app.storage.repository import InMemoryRepository
from app.storage.sqlite_repository import SqliteRepository

def test_memory_factory():
    assert isinstance(build_repository('memory://'),InMemoryRepository)

def test_sqlite_factory(tmp_path):
    r=build_repository('sqlite:///'+str(tmp_path/'x.db'))
    assert isinstance(r,SqliteRepository)
