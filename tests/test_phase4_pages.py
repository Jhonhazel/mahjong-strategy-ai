import re
from html.parser import HTMLParser

import pytest

from tests.phase4_support import phase4_client, postgres_engine, postgres_url, web_settings
from tests.test_phase3_http import csrf, game

pytestmark = pytest.mark.integration


class Markup(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


@pytest.mark.parametrize('path', ['/', '/game', '/history', '/contact'])
def test_phase4_shared_navigation_accessibility_and_local_assets(phase4_client, path):
    response = phase4_client.get(path)
    assert response.status_code == 200
    tags = Markup(response.text).tags
    assert ('a', {'class': 'skip-link', 'href': '#main-content'}) in tags
    assert any(tag == 'main' and attrs.get('id') == 'main-content' for tag, attrs in tags)
    assert sum(tag == 'a' and attrs.get('aria-current') == 'page' for tag, attrs in tags) == 1
    scripts = [attrs for tag, attrs in tags if tag == 'script']
    assert scripts and all(item.get('type') == 'module' and item.get('src', '').endswith('/static/phase3.js') for item in scripts)
    assert not any(name.lower().startswith('on') for _, attrs in tags for name in attrs)
    assert 'script-src \'self\'' in response.headers['content-security-policy']


def test_phase4_home_model_metrics_and_original_art_are_honest(phase4_client):
    response = phase4_client.get('/')
    assert all(value in response.text for value in ('64.35%', '86.55%', '1,946,122', '256', '128'))
    assert '/static/tiles.svg#tile-W5' in response.text
    assert 'ilustrasi' in response.text.lower()
    assert 'retrospektif' in response.text.lower() and 'bukan probabilitas menang' in response.text.lower()
    assert 'Play, Predict' in response.text


def test_phase4_game_settings_and_stable_accessible_controls(phase4_client):
    response = phase4_client.get('/game')
    tags = Markup(response.text).tags
    by_id = {attrs['id']: (tag, attrs) for tag, attrs in tags if 'id' in attrs}
    for name in ('legal-action', 'new-game', 'human-seat', 'prevalent-wind', 'game-seed', 'include-flowers',
                 'game-message', 'game-state', 'mahjong-table', 'human-hand', 'action-form', 'submit-action',
                 'predict-button', 'refresh-button', 'prediction', 'round-result'):
        assert name in by_id, name
    assert by_id['game-seed'][1]['inputmode'] == 'numeric'
    assert by_id['game-message'][1]['role'] == 'status'
    assert '9007199254740991' in response.text
    assert 'Jalankan' in response.text and 'otomatis' in response.text


def test_phase4_history_tiles_confirmed_delete_and_folded_complete_snapshots(phase4_client):
    headers = csrf(phase4_client)
    view = game(phase4_client, headers)
    saved = phase4_client.post('/api/games/' + view['game_id'] + '/predict',
                              json={'expected_turn_number': view['turn_number']}, headers=headers).json()
    listing = phase4_client.get('/history?limit=1')
    assert saved['prediction_id'] in listing.text
    assert '/static/tiles.svg#tile-' + saved['recommended_tile'] in listing.text
    assert 'history-top3-summary' in listing.text
    for suggestion in saved['top3']:
        assert '/static/tiles.svg#tile-' + suggestion['tile'] in listing.text
    assert 'delete-confirmation' in listing.text and 'Ya, hapus' in listing.text
    detail = phase4_client.get('/history/' + saved['prediction_id'])
    assert detail.status_code == 200
    assert 'Top 3' in detail.text and 'bobot rekomendasi' in detail.text
    assert detail.text.count('class="snapshot-details"') == 2
    assert 'legal_discard_mask' in detail.text and 'scores' in detail.text
    assert 'open' not in re.search(r'<details class="snapshot-details"[^>]*>', detail.text).group(0)
    assert 'checkpoint' in detail.text.lower()
    detail_tags = Markup(detail.text).tags
    assert any(tag == 'table' and 'history-top3' in attrs.get('class', '') for tag, attrs in detail_tags)
    assert sum(tag == 'th' and attrs.get('scope') == 'col' for tag, attrs in detail_tags) == 4
    assert phase4_client.get('/api/games/' + view['game_id']).json() == view
    assert phase4_client.delete('/api/predictions/' + saved['prediction_id'], headers=headers).status_code == 204


def test_phase4_contact_keeps_unverified_group_explicit(phase4_client):
    response = phase4_client.get('/contact')
    assert response.text.count('class="member-card"')==5
    assert 's32240016@student.ubm.ac.id' in response.text
    assert 'contact-incomplete' not in response.text and 'belum dikonfirmasi' in response.text


def test_phase4_game_labels_have_explicit_control_associations(phase4_client):
    tags = Markup(phase4_client.get('/game').text).tags
    labels = {attrs.get('for') for tag, attrs in tags if tag == 'label'}
    assert {'human-seat', 'prevalent-wind', 'game-seed', 'include-flowers', 'legal-action'} <= labels
