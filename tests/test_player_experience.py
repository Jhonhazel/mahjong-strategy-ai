"""Player pages hide implementation metadata while retaining real API/history contracts."""
from html.parser import HTMLParser
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from tests.phase4_support import phase4_client,postgres_engine,postgres_url,web_settings
from tests.test_phase3_http import csrf,game
from tests.test_phase4_pages import Markup

ROOT=Path(__file__).resolve().parents[1]
class PublicText(HTMLParser):
    def __init__(self,html):super().__init__();self.parts=[];self.feed(html)
    def handle_data(self,data):self.parts.append(data)
def text(html):return ' '.join(PublicText(html).parts)

@pytest.mark.parametrize('path',['/','/model','/game','/history','/contact'])
def test_five_player_routes_have_consistent_order_and_active_page(phase4_client,path):
    response=phase4_client.get(path);assert response.status_code==200
    nav=response.text.split('<nav class="main-nav"')[1].split('</nav>')[0]
    links=[a for tag,a in Markup(nav).tags if tag=='a']
    assert [a['href'] for a in links]==['/','/game','/history','/contact','/model']
    assert [a['href'] for a in links if a.get('aria-current')=='page']==[path]
    assert 'Game with AI' not in response.text

def test_home_introduces_mahjong_with_a_sourced_history_and_no_research_dashboard(phase4_client):
    html=phase4_client.get('/').text;public=text(html)
    assert 'abad ke-19' in public and 'https://ukmahjong.co.uk/index.php/what-is-mahjong/' in html
    assert 'Play, Predict' in public and '/static/tiles.svg#tile-W5' in html
    assert 'Ambil tempat Anda' in public and 'empat pemain' in public
    for word in ('86.55','86,55','64.35','Top-1','preprocessing','checkpoint','1,946,122','fold','387,746','MLP v3'):
        assert word not in public

def test_model_explains_six_steps_and_percentage_only_statistics(phase4_client):
    html=phase4_client.get('/model').text;assert html
    public=text(html);tags=Markup(html).tags
    ids={a.get('id') for _,a in tags}
    assert {'model-source','model-prepare','model-state','model-build','model-train','model-evaluate'}<=ids
    meta=json.loads((ROOT/'artifacts/models/mahjong_discard_mlp_v3.metadata.json').read_text())
    assert f"{meta['test_evaluation']['metrics']['top3']*100:.2f}".replace('.',',')+'%' in public
    assert 'Ketepatan tiga rekomendasi' in public and 'retrospektif' in public
    assert 'Bobot saran saat bermain' in public and 'di antara pilihan membuang yang diizinkan' in public
    assert 'prediksi kelas utama' in public and 'sekitar 80/20' in public and 'sekitar 80/10/10' in public
    for value in ('ReLU','AdamW','256','128','34','41','49','60','8','1368'):
        assert value in public
    for hidden in ('Top-1','64.35','64,35','MLP v3','V3','v3','discard_mlp_flexible','SHA','checkpoint','fold','seed','E3_f0','historical_test','Historical test lama','1,400,549','1,946,122','Tabel numerik','Provenance'):
        assert hidden not in html,hidden
    bars=[a for t,a in tags if t=='rect' and a.get('class')=='class-bar'];assert len(bars)==34
    from app.web.pages import research_context
    research=research_context(meta)
    assert [a['data-tile'] for a in bars]==meta['tile_order']
    assert [int(a['data-percent-units']) for a in bars]==[r['percent_units'] for r in research['classes']]
    assert not any('data-count' in a for _,a in tags)
    assert all(a.get('aria-labelledby') for t,a in tags if t=='svg' and a.get('role')=='img')
    for source in ('huggingface.co/datasets/Dannibal/ijcai-mahjong-round2','pypi.org/project/PyMahjongGB'):
        assert source in html

def test_game_guide_precedes_setup_and_removed_controls_have_no_placeholders(phase4_client):
    html=phase4_client.get('/game').text;tags=Markup(html).tags;ids={a.get('id') for _,a in tags}
    assert html.index('id="game-guide"')<html.index('id="game-setup"')
    assert {'new-game','human-seat','prevalent-wind','include-flowers','human-hand','claim-actions','submit-action','skip-animation'}<=ids
    assert not {'game-seed','seed-help','legal-action','playback-speed','game-id','public-state'}&ids
    assert not any(t=='select' and a.get('id') not in ('human-seat','prevalent-wind') for t,a in tags)
    assert all(word in text(html) for word in ('konfirmasi','claim','History','Saran','pilihan'))
    assert 'model-badge' not in html and 'Identitas' not in html and 'Seed' not in html

def test_history_hides_debug_text_but_preserves_saved_record_and_protected_delete(phase4_client):
    client=phase4_client;headers=csrf(client);view=game(client,headers)
    response=client.post('/api/games/'+view['game_id']+'/predict',json={'expected_turn_number':view['turn_number']},headers=headers);assert response.status_code==201
    saved=response.json();path='/api/predictions/'+saved['prediction_id'];before=client.get(path).json()
    for route in ('/history','/history/'+saved['prediction_id']):
        html=client.get(route).text;public=text(html)
        for hidden in (saved['prediction_id'],view['game_id'],saved['model_version'],saved['encoder_version'],'SELF_TURN','JSON','Konteks prediksi','Checksum','UNTUK PENELUSURAN','legal_discard_mask'):
            assert hidden not in public,hidden
        assert all('/static/tiles.svg#tile-'+row['tile'] in html for row in saved['recommendations']['suggestions'])
        assert 'delete-confirmation' in html and 'Ya, hapus' in html
    assert client.get(path).json()==before
    assert client.post('/history/'+saved['prediction_id']+'/delete',data={},follow_redirects=False).status_code==403
    assert client.get(path).status_code==200
    assert client.post('/history/'+saved['prediction_id']+'/delete',data={'csrf_token':headers['X-CSRF-Token']},follow_redirects=False).status_code==303
    assert client.get(path).status_code==404

def test_contact_hides_roles_without_inventing_incomplete_identity(phase4_client,web_settings,postgres_engine,tmp_path):
    roster=json.loads((ROOT/'config/contact_members.public.json').read_text());html=phase4_client.get('/contact').text
    for member in roster['members']:
        assert all(member[k] in html for k in ('name','student_id','email'))
        assert member['role'] not in text(html)
    assert not any(word in text(html) for word in ('Peran','Pembagian Tugas','persentase kontribusi','belum dikonfirmasi'))
    roster['members'][0].pop('role');path=tmp_path/'roster.json';path.write_text(json.dumps(roster))
    from app.main import create_app
    with TestClient(create_app(web_settings.model_copy(update={'contact_members_path':path}))) as client:
        assert 'belum dikonfirmasi' not in text(client.get('/contact').text)

def test_model_template_is_in_runtime_allowlist():
    path='app/templates/model.html';allow=json.loads((ROOT/'packaging/runtime_allowlist.json').read_text())
    assert allow.get(path)==path

@pytest.mark.parametrize('identifier,status',[('00000000-0000-0000-0000-000000000000',404),('bukan-id-valid',422)])
def test_unavailable_history_is_a_player_notice_while_api_errors_stay_json(phase4_client,identifier,status):
    response=phase4_client.get('/history/'+identifier)
    assert response.status_code==status
    assert response.headers['content-type'].startswith('text/html')
    assert 'Saran tidak tersedia' in response.text and 'Kembali ke History' in response.text
    assert 'not_found' not in response.text and 'validation_error' not in response.text
    api=phase4_client.get('/api/predictions/'+identifier)
    assert api.status_code==status and api.headers['content-type'].startswith('application/json')
