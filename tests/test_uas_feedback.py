"""Academic presentation facts are tied to the promoted model, not placeholders."""
import copy
import importlib
import importlib.util
import json
from pathlib import Path
import re

from fastapi.testclient import TestClient
import pytest

from tests.phase4_support import phase4_client,postgres_engine,postgres_url,web_settings
from tests.test_phase3_http import csrf,game
from tests.test_phase4_pages import Markup
from tests.test_phase4_1 import MEMBERS

ROOT=Path(__file__).resolve().parents[1]


def summary():
    path=ROOT/'config/home_research.public.json'
    assert path.is_file(),'Missing validated offline research summary'
    return json.loads(path.read_text())


def metadata():return json.loads((ROOT/'artifacts/models/mahjong_discard_mlp_v3.metadata.json').read_text())


def test_summary_is_reproducible_from_frozen_ground_truth_supports():
    assert importlib.util.find_spec('scripts.build_home_research_summary'),'Missing offline summary reproduction'
    build=importlib.import_module('scripts.build_home_research_summary')
    data=summary();assert build.build_summary(ROOT)==data
    history=json.loads((ROOT/'artifacts/phase2_2/training_history.json').read_text())
    rows=data['class_counts'];assert len(rows)==34
    assert [r['class_index'] for r in rows]==list(range(34))
    assert [r['tile'] for r in rows]==metadata()['tile_order']
    assert [r['count'] for r in rows]==[r['support'] for r in history['selected_train_metrics']['per_class']]
    assert all(type(r['count']) is int and r['count']>=0 for r in rows)
    assert sum(r['count'] for r in rows)==1_400_549
    assert sum(r['samples'] for r in data['partitions'])==1_946_122
    assert data['training_cohort']['experiment']=='E3_f0_s2026'
    assert data['corpus']=={'json_games':44420,'matches':38250,'samples':1946122,'player_uids':581}
    assert data['provenance'] and data['training_history_sha256']==metadata()['development']['history_sha256']


def test_runtime_packages_include_the_public_chart_summary():
    path='config/home_research.public.json'
    allowlist=json.loads((ROOT/'packaging/runtime_allowlist.json').read_text())
    assert allowlist[path]==path
    assert '!'+path in (ROOT/'.dockerignore').read_text().splitlines()
    copies=[line.split() for line in (ROOT/'Dockerfile').read_text().splitlines() if line.startswith('COPY ')]
    assert any((path in line[1:-1] or 'config/' in line[1:-1]) and line[-1]=='./config/' for line in copies)


@pytest.mark.parametrize('damage',['negative','boolean','duplicate','missing','wrong_total','wrong_contract','wrong_history','wrong_fold'])
def test_corrupt_summary_is_rejected_without_inventing_statistics(damage):
    from app.web import pages
    data=copy.deepcopy(summary())
    if damage=='negative':data['class_counts'][0]['count']=-1
    elif damage=='boolean':data['class_counts'][0]['count']=True
    elif damage=='duplicate':data['class_counts'][1]['tile']='W1'
    elif damage=='missing':data['class_counts'].pop()
    elif damage=='wrong_total':data['class_counts'][0]['count']+=1
    elif damage=='wrong_contract':data['contract_sha256']='0'*64
    elif damage=='wrong_history':data['training_history_sha256']='0'*64
    else:data['training_cohort']['fold']=1
    with pytest.raises(ValueError):pages.validate_home_summary(data,metadata())


def test_charts_derive_families_and_controlled_percentages_from_same_counts():
    from app.web.pages import research_context
    context=research_context(metadata());assert context
    assert [r['label'] for r in context['families']]==['Karakter','Bambu','Lingkaran','Angin','Naga']
    assert [r['count'] for r in context['families']]==[sum(r['count'] for r in summary()['class_counts'][a:b]) for a,b in ((0,9),(9,18),(18,27),(27,31),(31,34))]
    for key in ('classes','families','partitions'):
        assert sum(r['percent_units'] for r in context[key])==100000
    assert context['dominant']['tile']=='F4' and context['minority']['tile']=='B6'


def test_home_exposes_correct_cohorts_pipeline_charts_and_preserves_game_identity(phase4_client):
    response=phase4_client.get('/');assert response.status_code==200
    text=response.text
    for value in ('64.35%','86.55%','0.622','1.086','100%','194,388','1,946,122','1,400,549','350,917',
                  'MLP v3','387,746','ReLU','AdamW','expanded_strict_v2','Dannibal/ijcai-mahjong-round2',
                  '1368','235','34','retrospektif','bukan probabilitas menang','preprocessing'):
        assert value in text,value
    assert 'Play, Predict' in text and 'how-it-works' in text and 'Ambil tempat Anda' in text
    assert '/static/tiles.svg#tile-W5' in text
    tags=Markup(text).tags
    charts={a.get('id'):a for t,a in tags if t=='figure'}
    assert {'partition-distribution','class-distribution','family-distribution'}<=charts.keys()
    bars=[a for t,a in tags if t=='rect' and a.get('class')=='class-bar']
    assert [(int(a['data-class-index']),a['data-tile'],int(a['data-count'])) for a in bars]==[(r['class_index'],r['tile'],r['count']) for r in summary()['class_counts']]
    assert all(a.get('aria-labelledby') for t,a in tags if t=='svg' and a.get('role')=='img')
    assert not any(key.lower().startswith('on') or key=='style' for _,attrs in tags for key in attrs)
    config=phase4_client.app.state.settings
    assert config.session_secret.get_secret_value() not in text
    assert config.database_url.get_secret_value() not in text


@pytest.mark.parametrize('contents',[None,'{"class_counts":[]}', '{'])
def test_missing_or_damaged_summary_keeps_home_and_game_available(phase4_client,tmp_path,monkeypatch,contents):
    from app.web import pages
    path=tmp_path/'summary.json'
    if contents is not None:path.write_text(contents)
    original=pages.research_context
    monkeypatch.setattr(pages,'research_context',lambda meta:original(meta,path=path))
    response=phase4_client.get('/');assert response.status_code==200
    assert 'Statistik distribusi belum tersedia' in response.text and '64.35%' in response.text
    assert 'class-bar' not in response.text
    assert phase4_client.get('/game').status_code==200


def test_repeated_home_requests_do_not_reload_corpus_or_checkpoint(phase4_client,monkeypatch):
    from app.web import pages
    import app.web.runtime
    pages.read_home_summary.cache_clear();original=Path.read_bytes;reads=[]
    def checked(path):
        assert path.suffix!='.npz' and path.name!='training_history.json'
        if path.name=='home_research.public.json':reads.append(path)
        return original(path)
    def forbidden(*args,**kwargs):pytest.fail('Homepage attempted another model initialization')
    monkeypatch.setattr(Path,'read_bytes',checked)
    monkeypatch.setattr(app.web.runtime,'load_runtime_model',forbidden)
    assert phase4_client.get('/').status_code==200 and phase4_client.get('/').status_code==200
    assert len(reads)==1


def test_all_five_official_members_have_equal_authorized_scope(phase4_client):
    from app.web.contact import ContactRoster
    roster=ContactRoster.from_path(ROOT/'config/contact_members.public.json')
    assert [(m.name,m.student_id,m.email) for m in roster.members]==MEMBERS
    roles=[m.role for m in roster.members]
    assert len(set(roles))==1 and roles[0] and len(roles[0])<=200
    for keyword in ('dataset','preprocessing','AI','game','web','testing','dokumentasi','presentasi'):
        assert keyword in roles[0]
    response=phase4_client.get('/contact');assert response.status_code==200
    assert response.text.count('class="member-card"')==5 and response.text.count(roles[0].replace('&','&amp;'))==5
    assert 'Pembagian Tugas Kelompok 1' in response.text
    assert 'belum dikonfirmasi' not in response.text and 'persentase kontribusi' in response.text


def test_verified_but_partial_roles_keep_truthful_notice(web_settings,postgres_engine,tmp_path):
    from app.main import create_app
    path=tmp_path/'partial.json';path.write_text(json.dumps({'verified':True,'members':[{'name':'TEST ONLY','role':None}]}))
    with TestClient(create_app(web_settings.model_copy(update={'contact_members_path':path}))) as client:
        response=client.get('/contact');assert response.status_code==200
        assert 'belum dikonfirmasi' in response.text
        assert 'Pembagian Tugas Kelompok 1' not in response.text


@pytest.mark.parametrize('roles',[['Testing'],['Testing']*4+['Dokumentasi'],['Testing']*5])
def test_alternate_roster_does_not_inherit_official_shared_scope(web_settings,postgres_engine,tmp_path,roles):
    from app.main import create_app
    path=tmp_path/'alternate.json'
    path.write_text(json.dumps({'verified':True,'members':[{'name':f'TEST MEMBER {i}','role':role} for i,role in enumerate(roles)]}))
    with TestClient(create_app(web_settings.model_copy(update={'contact_members_path':path}))) as client:
        response=client.get('/contact');assert response.status_code==200
        assert response.text.count('class="member-card"')==len(roles)
        assert 'Pembagian Tugas Kelompok 1' not in response.text
        assert 'belum dikonfirmasi' in response.text


def test_one_shared_group_footer_on_all_five_application_pages(phase4_client):
    headers=csrf(phase4_client);view=game(phase4_client,headers)
    prediction=phase4_client.post('/api/games/'+view['game_id']+'/predict',json={'expected_turn_number':view['turn_number']},headers=headers)
    assert prediction.status_code==201
    for path in ('/','/game','/history','/contact','/history/'+prediction.json()['prediction_id']):
        response=phase4_client.get(path);assert response.status_code==200
        assert response.text.count('<footer')==1
        footer=re.search(r'<footer\b[^>]*>(.*?)</footer>',response.text,re.S).group(1)
        assert all(value in footer for value in ('© 2026 Kelompok 1','Mahjong Strategy AI','Universitas Bunda Mulia'))
