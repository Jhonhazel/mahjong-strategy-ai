import pytest
from fastapi.testclient import TestClient

from tests.phase3_support import postgres_engine,postgres_url,web_settings


@pytest.fixture
def phase4_client(web_settings,postgres_engine):
    from app.main import create_app
    with TestClient(create_app(web_settings),raise_server_exceptions=False) as client:
        yield client
