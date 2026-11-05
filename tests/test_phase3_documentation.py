import base64
import hashlib
import re

import pytest
from fastapi.testclient import TestClient

from tests.phase3_support import postgres_engine,postgres_url,web_settings

pytestmark=pytest.mark.integration


@pytest.mark.parametrize('path',['/docs','/redoc'])
def test_generated_api_docs_csp_permits_its_own_resources(web_settings,postgres_engine,path):
    from app.main import create_app
    with TestClient(create_app(web_settings)) as client:
        response=client.get(path);assert response.status_code==200
        policy=response.headers['content-security-policy']
        directives={part.strip().split()[0]:part.strip().split()[1:] for part in policy.split(';') if part.strip()}
        assert 'https://cdn.jsdelivr.net' in directives['script-src']
        scripts=re.findall(r'<script\b[^>]*>(.*?)</script>',response.text,re.S)
        assert scripts
        assert len(response.headers.get_list('content-security-policy'))==1
        for script in scripts:
            if script.strip():
                digest=base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
                assert f"'sha256-{digest}'" in directives['script-src']
        assert "'unsafe-inline'" not in directives['script-src']
        regular=client.get('/game').headers['content-security-policy']
        assert 'cdn.jsdelivr.net' not in regular and "'unsafe-inline'" not in regular


def test_openapi_exposes_the_cookie_and_csrf_contract_without_changing_error_semantics(web_settings,postgres_engine):
    from app.main import create_app
    with TestClient(create_app(web_settings)) as client:
        schema=client.get('/openapi.json').json()
        for path,method in [('/api/games','post'),('/api/games/{game_id}/actions','post'),
                            ('/api/games/{game_id}/predict','post'),('/api/predictions/{prediction_id}','delete')]:
            parameters=schema['paths'][path][method].get('parameters',[])
            assert any(p['in']=='header' and p['name']=='X-CSRF-Token' for p in parameters)
            assert any(p['in']=='cookie' and p['name']=='mahjong_visitor' for p in parameters)
        assert client.post('/api/games',json={}).status_code==401
        assert client.get('/api/session').status_code==200
        assert client.post('/api/games',json={}).status_code==403
