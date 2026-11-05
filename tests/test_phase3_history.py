from dataclasses import replace
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import secrets
import uuid

import pytest
from sqlalchemy import inspect

from tests.phase3_support import postgres_engine, postgres_url

pytestmark = pytest.mark.integration


def sample_snapshot(**changes):
    from app.domain.predictions import PredictionSnapshot
    values = dict(game_id=uuid.uuid4(), turn_number=1, turn_phase='SELF_TURN',
                  input_snapshot={'obs':[[[0]*9 for _ in range(4)] for _ in range(38)],
                                  'shape':[38,4,9],'legal_discard_mask':[True]+[False]*33},
                  output_snapshot={'recommended_tile':'W1','recommended_action_id':2,
                                   'top3':[{'tile':'W1','class_index':0,'action_id':2,'score':1.0}]},
                  model_version='unit-storage-fixture', encoder_version='ijcai2026_mcr_v1_strict',
                  checkpoint_sha256='a'*64, state_digest=secrets.token_hex(32))
    return PredictionSnapshot(**{**values,**changes})


def test_real_postgres_schema_jsonb_timezone_and_constraints(postgres_engine):
    from app.db import check_schema
    assert check_schema(postgres_engine)['status']=='PASS'
    columns={c['name']:c for c in inspect(postgres_engine).get_columns('prediction_results')}
    assert str(columns['input_snapshot']['type'])=='JSONB'
    assert str(columns['output_snapshot']['type'])=='JSONB'
    assert columns['created_at']['type'].timezone is True
    assert 'uq_prediction_snapshot' in {v['name'] for v in inspect(postgres_engine).get_unique_constraints('prediction_results')}


def test_real_postgres_create_read_delete_owner_isolation_and_utc(postgres_engine):
    from app.services.prediction_history_service import PredictionHistoryService
    store=PredictionHistoryService(postgres_engine);owner=secrets.token_hex(32);other=secrets.token_hex(32)
    snapshot=sample_snapshot();before=datetime.now(timezone.utc)
    record,reused=store.save(owner,snapshot)
    assert not reused and record.input_snapshot==snapshot.input_snapshot
    assert record.output_snapshot==snapshot.output_snapshot and record.model_version==snapshot.model_version
    assert record.created_at.tzinfo is not None and record.created_at>=before
    assert store.get(other,record.id) is None and not store.delete(other,record.id)
    assert store.get(owner,record.id).encoder_version==snapshot.encoder_version
    assert store.delete(owner,record.id) and store.get(owner,record.id) is None
    assert not store.delete(owner,record.id)


def test_real_postgres_pagination_and_service_restart_preserve_records(postgres_engine):
    from app.services.prediction_history_service import PredictionHistoryService
    store=PredictionHistoryService(postgres_engine);owner=secrets.token_hex(32)
    inserted=[store.save(owner,sample_snapshot())[0] for _ in range(4)]
    page,total=store.list(owner,limit=2,offset=0);next_page,total2=store.list(owner,limit=2,offset=2)
    assert total==total2==4 and len(page)==len(next_page)==2
    assert len({p.id for p in [*page,*next_page]})==4
    assert [(r.created_at,r.id) for r in page]==sorted([(r.created_at,r.id) for r in page],reverse=True)
    fresh=PredictionHistoryService(postgres_engine)
    assert fresh.get(owner,inserted[0].id).input_snapshot==inserted[0].input_snapshot
    with pytest.raises(ValueError):store.list(owner,limit=101,offset=0)


def test_real_postgres_same_snapshot_is_idempotent_and_original_is_immutable(postgres_engine):
    from app.services.prediction_history_service import PredictionHistoryService
    store=PredictionHistoryService(postgres_engine);owner=secrets.token_hex(32);snapshot=sample_snapshot()
    first,reused=store.save(owner,snapshot)
    second,reused2=store.save(owner,replace(snapshot,output_snapshot={'changed':True}))
    assert not reused and reused2 and first.id==second.id
    assert second.output_snapshot==snapshot.output_snapshot and store.list(owner)[1]==1


def test_real_postgres_duplicate_insert_race_has_one_identity(postgres_engine):
    from app.services.prediction_history_service import PredictionHistoryService
    store=PredictionHistoryService(postgres_engine);owner=secrets.token_hex(32);snapshot=sample_snapshot()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:store.save(owner,snapshot),range(4)))
    assert len({record.id for record,reused in results})==1
    assert sum(not reused for record,reused in results)==1 and store.list(owner)[1]==1


def test_real_postgres_failed_insert_rolls_back_and_next_transaction_works(postgres_engine):
    from app.services.prediction_history_service import PredictionHistoryService, HistoryUnavailable
    store=PredictionHistoryService(postgres_engine);owner=secrets.token_hex(32)
    with pytest.raises(HistoryUnavailable):store.save(owner,sample_snapshot(model_version='x'*300))
    assert store.list(owner)[1]==0
    assert store.save(owner,sample_snapshot())[0].id is not None


def test_owner_filter_is_parameterized_and_missing_id_is_safe(postgres_engine):
    from app.services.prediction_history_service import PredictionHistoryService
    store=PredictionHistoryService(postgres_engine);owner=secrets.token_hex(32)
    record,_=store.save(owner,sample_snapshot())
    assert store.list("' OR 1=1 --")[1]==0
    assert store.get(owner,uuid.uuid4()) is None and not store.delete(owner,uuid.uuid4())
    assert store.get(owner,record.id) is not None


def test_reused_prediction_is_locked_until_save_commits(postgres_engine,monkeypatch):
    from threading import Event
    from sqlmodel import Session
    from app.services import prediction_history_service as module
    store=module.PredictionHistoryService(postgres_engine);owner=secrets.token_hex(32);snapshot=sample_snapshot()
    original,_=store.save(owner,snapshot)
    selected=Event();release=Event();deleted=Event()
    class PausingSession(Session):
        def commit(self):
            if any(getattr(row,'id',None)==original.id for row in self.identity_map.values()):
                selected.set()
                assert release.wait(5)
            return super().commit()
    monkeypatch.setattr(module,'Session',PausingSession)
    def remove():
        result=store.delete(owner,original.id);deleted.set();return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        saved=pool.submit(store.save,owner,snapshot)
        assert selected.wait(5)
        removed=pool.submit(remove)
        try:
            assert not deleted.wait(.3), 'DELETE committed before the reused save transaction'
        finally:release.set()
        record,reused=saved.result(timeout=5)
        assert reused and record.id==original.id and removed.result(timeout=5)
    assert store.get(owner,original.id) is None
