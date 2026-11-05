import os
import secrets

import pytest
from sqlalchemy.engine import make_url


@pytest.fixture(scope='session')
def postgres_url():
    url = os.environ.get('MAHJONG_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Real PostgreSQL NOT RUN: provide a dedicated MAHJONG_TEST_DATABASE_URL')
    parsed = make_url(url)
    if parsed.get_backend_name() != 'postgresql' or not parsed.database.endswith('_test'):
        pytest.fail('Refusing tests outside an explicitly named dedicated PostgreSQL _test database')
    return url


@pytest.fixture
def web_settings(postgres_url):
    from app.settings import Settings
    return Settings(_env_file=None, database_url=postgres_url,
                    session_secret=secrets.token_urlsafe(40), environment='test')


@pytest.fixture(scope='session')
def postgres_engine(postgres_url):
    from app.settings import Settings
    from app.db import create_db_engine, initialize_schema
    config = Settings(_env_file=None, database_url=postgres_url,
                      session_secret=secrets.token_urlsafe(40), environment='test')
    engine = create_db_engine(config)
    initialize_schema(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def local_postgres_controller(postgres_url):
    from scripts.phase3_db import LocalPostgres
    controller=LocalPostgres();url=make_url(postgres_url)
    if url.query.get('host')!=str(controller.socket) or url.database!='mahjong_phase3_test':
        pytest.skip('Isolated admin/export proof NOT RUN: use the marker-protected local project test cluster')
    controller._require_owned()
    return controller
