"""One PostgreSQL table and explicit, non-destructive schema bootstrap."""
from datetime import datetime
import json
import re
import uuid

from sqlalchemy import CheckConstraint, Column, DateTime, Index, String, UniqueConstraint, func, inspect, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Field, SQLModel, create_engine

from app.settings import Settings


class DatabaseUnavailable(RuntimeError):
    pass


class PredictionResult(SQLModel, table=True):
    __tablename__ = 'prediction_results'
    __table_args__ = (
        UniqueConstraint('owner_key', 'game_id', 'turn_number', 'model_version', 'state_digest', name='uq_prediction_snapshot'),
        Index('ix_prediction_owner_created', 'owner_key', text('created_at DESC'), text('id DESC')),
        CheckConstraint('turn_number >= 0', name='ck_prediction_turn'),
        CheckConstraint("turn_phase IN ('SELF_TURN','POST_MELD_DISCARD')", name='ck_prediction_phase'),
        CheckConstraint('length(state_digest) = 64 AND length(checkpoint_sha256) = 64', name='ck_prediction_digests'),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_key: str = Field(sa_column=Column(String(64), nullable=False))
    game_id: uuid.UUID
    turn_number: int
    turn_phase: str = Field(sa_column=Column(String(32), nullable=False))
    input_snapshot: dict = Field(sa_column=Column(JSONB, nullable=False))
    output_snapshot: dict = Field(sa_column=Column(JSONB, nullable=False))
    model_version: str = Field(sa_column=Column(String(128), nullable=False))
    encoder_version: str = Field(sa_column=Column(String(64), nullable=False))
    checkpoint_sha256: str = Field(sa_column=Column(String(64), nullable=False))
    state_digest: str = Field(sa_column=Column(String(64), nullable=False))
    created_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()))


def create_db_engine(settings: Settings):
    timeout = settings.database_timeout_seconds
    return create_engine(settings.database_url.get_secret_value(), pool_pre_ping=True,
                         pool_size=5, max_overflow=5, pool_timeout=timeout,
                         hide_parameters=True, echo=False,
                         json_serializer=lambda value: json.dumps(value, allow_nan=False),
                         connect_args={'connect_timeout':timeout,
                                       'options':f'-c timezone=UTC -c statement_timeout={timeout*1000} -c lock_timeout={timeout*1000}'})


def initialize_schema(engine):
    try:
        PredictionResult.metadata.create_all(engine, tables=[PredictionResult.__table__])
        return check_schema(engine)
    except SQLAlchemyError:
        raise DatabaseUnavailable('PostgreSQL schema initialization failed') from None


def check_schema(engine):
    try:
        with engine.connect() as connection:
            if engine.dialect.name != 'postgresql':
                raise DatabaseUnavailable('Real PostgreSQL is required')
            if connection.execute(text('SHOW transaction_read_only')).scalar_one()!='off':
                raise DatabaseUnavailable('Prediction history requires a writable PostgreSQL connection')
            inspector = inspect(connection)
            if not inspector.has_table('prediction_results'):
                raise DatabaseUnavailable('Prediction history schema is missing; run explicit schema initialization')
            columns = {item['name']:item for item in inspector.get_columns('prediction_results')}
            if set(PredictionResult.__table__.columns.keys())!=set(columns):
                raise DatabaseUnavailable('Prediction history schema is incompatible')
            permitted=connection.execute(text("""
                SELECT bool_and(has_table_privilege(current_user,'prediction_results',privilege))
                FROM unnest(ARRAY['SELECT','INSERT','DELETE','UPDATE']) AS required(privilege)
            """)).scalar_one()
            if not permitted:
                raise DatabaseUnavailable('Prediction history requires read, insert, delete and row-lock privileges')
            for column in PredictionResult.__table__.columns:
                observed=columns[column.name]
                expected_type=column.type.compile(dialect=engine.dialect)
                actual_type=observed['type'].compile(dialect=engine.dialect)
                if actual_type!=expected_type or observed['nullable']!=column.nullable:
                    raise DatabaseUnavailable('Prediction history column types or nullability are incompatible')
            if inspector.get_pk_constraint('prediction_results')['constrained_columns']!=['id']:
                raise DatabaseUnavailable('Prediction history identity or timestamp default is incompatible')
            timestamp_default=re.sub(r'\s+','',columns['created_at']['default'] or '').lower()
            if timestamp_default not in ('now()','pg_catalog.now()','current_timestamp','transaction_timestamp()'):
                raise DatabaseUnavailable('Prediction history requires a current transaction timestamp default')
            if any(not isinstance(columns[name]['type'], JSONB) for name in ('input_snapshot','output_snapshot')):
                raise DatabaseUnavailable('Prediction snapshots require PostgreSQL JSONB')
            if not getattr(columns['created_at']['type'], 'timezone', False):
                raise DatabaseUnavailable('History timestamps require timezone-aware PostgreSQL values')
            unique = inspector.get_unique_constraints('prediction_results')
            expected = ['owner_key','game_id','turn_number','model_version','state_digest']
            if not any(item['name']=='uq_prediction_snapshot' and item['column_names']==expected for item in unique):
                raise DatabaseUnavailable('Prediction identity constraint is missing')
            indexes = inspector.get_indexes('prediction_results')
            if not any(item['name']=='ix_prediction_owner_created' and item['column_names']==['owner_key','created_at','id'] for item in indexes):
                raise DatabaseUnavailable('Prediction history lookup index is missing')
            expected_checks={
                'ck_prediction_turn':'turn_number>=0',
                'ck_prediction_phase':"turn_phase=ANYARRAY['SELF_TURN','POST_MELD_DISCARD']",
                'ck_prediction_digests':'lengthstate_digest=64ANDlengthcheckpoint_sha256=64',
            }
            checks={item['name']:item['sqltext'] for item in inspector.get_check_constraints('prediction_results')}
            for name,expected_expression in expected_checks.items():
                expression=re.sub(r'::(?:character varying|text)(?:\[\])?','',checks.get(name,''))
                expression=re.sub(r'\s+','',expression).replace('(','').replace(')','')
                if expression!=expected_expression:
                    raise DatabaseUnavailable('Prediction history validation constraint semantics are incompatible')
            constraints=connection.execute(text("""
                SELECT c.conname,c.convalidated,c.condeferrable,c.contype,
                       i.indisvalid,i.indisready
                FROM pg_constraint AS c
                LEFT JOIN pg_index AS i ON i.indexrelid=c.conindid
                WHERE c.conrelid=to_regclass('prediction_results')
            """)).mappings().all()
            by_name={item['conname']:item for item in constraints}
            for name in (*expected_checks,'uq_prediction_snapshot'):
                item=by_name.get(name)
                if not item or not item['convalidated'] or item['condeferrable']:
                    raise DatabaseUnavailable('Prediction history constraints must be validated and immediate')
            identity=by_name['uq_prediction_snapshot']
            if identity['contype']!='u' or not identity['indisvalid'] or not identity['indisready']:
                raise DatabaseUnavailable('Prediction history requires a valid immediate uniqueness index')
            return {'status':'PASS','dialect':'postgresql','table':'prediction_results',
                    'columns':sorted(columns),'jsonb':['input_snapshot','output_snapshot'],
                    'unique_constraint':'uq_prediction_snapshot','indexes':[item['name'] for item in indexes]}
    except SQLAlchemyError:
        raise DatabaseUnavailable('PostgreSQL or prediction history schema is unavailable') from None
