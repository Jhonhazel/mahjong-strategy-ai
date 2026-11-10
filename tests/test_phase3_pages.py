import json
import re

import pytest
from fastapi.testclient import TestClient

from tests.phase3_support import postgres_engine, postgres_url, web_settings
from tests.test_phase3_http import client, csrf, game

pytestmark = pytest.mark.integration


def test_foundation_pages_show_real_model_and_incomplete_contact(client):
    home=client.get('/');assert home.status_code==200
    assert '64.35%' in home.text and '86.55%' in home.text and '1,946,122' in home.text
    assert 'retrospektif' in home.text.lower() and 'menang' in home.text.lower()
    assert '256' in home.text and '128' in home.text
    contact=client.get('/contact');assert contact.status_code==200
    assert contact.text.count('class="member-card"')==5
    assert 'Jhonhazel Lionel Tjokahn' in contact.text and '32240016' in contact.text
    assert 'Pembagian Tugas Kelompok 1' in contact.text and 'belum dikonfirmasi' not in contact.text
    page=client.get('/game');assert page.status_code==200
    assert '/static/phase3.js' in page.text and 'legal-action' in page.text
    assert client.get('/static/phase3.js').status_code==200
    assert client.get('/static/phase3.css').status_code==200


def test_history_pages_read_actual_postgres_and_protect_delete_form(client):
    headers=csrf(client);view=game(client,headers)
    saved=client.post('/api/games/'+view['game_id']+'/predict',json={'expected_turn_number':view['turn_number']},headers=headers).json()
    listing=client.get('/history');assert listing.status_code==200 and saved['prediction_id'] in listing.text
    detail=client.get('/history/'+saved['prediction_id']);assert detail.status_code==200
    assert saved['recommended_tile'] in detail.text and 'legal_discard_mask' in detail.text
    path='/history/'+saved['prediction_id']+'/delete'
    assert client.post(path,data={},follow_redirects=False).status_code==403
    deleted=client.post(path,data={'csrf_token':headers['X-CSRF-Token']},follow_redirects=False)
    assert deleted.status_code==303 and deleted.headers['location']=='/history'
    assert client.get('/api/predictions/'+saved['prediction_id']).status_code==404
    assert client.get('/api/games/'+view['game_id']).json()==view


def test_verified_contact_configuration_escapes_text_and_does_not_invent_fields(web_settings,postgres_engine,tmp_path):
    from app.main import create_app
    file=tmp_path/'members.json';file.write_text(json.dumps({'verified':True,'members':[{'name':'<script>test</script>','student_id':'TEST-ONLY','role':'<img src=x onerror=alert(1)>'}]}))
    config=web_settings.model_copy(update={'contact_members_path':file})
    with TestClient(create_app(config)) as browser:
        response=browser.get('/contact')
        assert response.status_code==200
        assert '&lt;script&gt;' in response.text and '<script>test</script>' not in response.text
        assert '<img src=x onerror' not in response.text and 'TEST-ONLY' in response.text


def test_html_expired_or_forged_identity_cannot_delete_owned_history(client):
    headers=csrf(client);view=game(client,headers)
    saved=client.post('/api/games/'+view['game_id']+'/predict',json={'expected_turn_number':view['turn_number']},headers=headers).json()
    other=TestClient(client.app,raise_server_exceptions=False)
    try:
        token=csrf(other)['X-CSRF-Token']
        assert other.post('/history/'+saved['prediction_id']+'/delete',data={'csrf_token':token},follow_redirects=False).status_code==404
        other.cookies.clear();other.cookies.set('mahjong_visitor','forged')
        assert other.post('/history/'+saved['prediction_id']+'/delete',data={'csrf_token':token},follow_redirects=False).status_code==401
    finally:other.close()
    assert client.get('/api/predictions/'+saved['prediction_id']).status_code==200
