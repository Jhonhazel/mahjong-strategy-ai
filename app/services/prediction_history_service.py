"""Owner-filtered persistence, short transactions, immutable snapshot upserts."""
from dataclasses import asdict
import uuid

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.db import PredictionResult
from app.domain.predictions import PredictionSnapshot


class HistoryUnavailable(RuntimeError):
    pass


class PredictionHistoryService:
    def __init__(self, engine):
        self.engine = engine

    @staticmethod
    def _identity(owner_key, snapshot):
        return (PredictionResult.owner_key == owner_key,
                PredictionResult.game_id == snapshot.game_id,
                PredictionResult.turn_number == snapshot.turn_number,
                PredictionResult.model_version == snapshot.model_version,
                PredictionResult.state_digest == snapshot.state_digest)

    def save(self, owner_key: str, snapshot: PredictionSnapshot):
        try:
            with Session(self.engine, expire_on_commit=False) as session:
                try:
                    values = dict(asdict(snapshot), id=uuid.uuid4(), owner_key=owner_key)
                    statement = insert(PredictionResult).values(**values).on_conflict_do_nothing(
                        constraint='uq_prediction_snapshot').returning(PredictionResult.id)
                    identity = session.execute(statement).scalar_one_or_none()
                    reused = identity is None
                    record = session.exec(select(PredictionResult).where(
                        *self._identity(owner_key,snapshot)).with_for_update()).one_or_none()
                    if record is None:
                        raise HistoryUnavailable('Prediction history changed concurrently; retry the same request')
                    session.commit()
                    return record, reused
                except BaseException:
                    session.rollback()
                    raise
        except SQLAlchemyError:
            raise HistoryUnavailable('Prediction history could not be saved; retry the same turn') from None

    def get(self, owner_key: str, prediction_id: uuid.UUID):
        try:
            with Session(self.engine) as session:
                return session.exec(select(PredictionResult).where(PredictionResult.id==prediction_id,
                                                                  PredictionResult.owner_key==owner_key)).one_or_none()
        except SQLAlchemyError:
            raise HistoryUnavailable('Prediction history is unavailable') from None

    def list(self, owner_key: str, limit=20, offset=0):
        if not 1 <= limit <= 100 or not 0 <= offset <= 100000:
            raise ValueError('History pagination is outside the allowed bounds')
        try:
            with Session(self.engine) as session:
                query = select(PredictionResult).where(PredictionResult.owner_key==owner_key)
                records = session.exec(query.order_by(PredictionResult.created_at.desc(),PredictionResult.id.desc()).limit(limit).offset(offset)).all()
                total = session.exec(select(func.count()).select_from(PredictionResult).where(PredictionResult.owner_key==owner_key)).one()
                return records, total
        except SQLAlchemyError:
            raise HistoryUnavailable('Prediction history is unavailable') from None

    def delete(self, owner_key: str, prediction_id: uuid.UUID):
        try:
            with Session(self.engine) as session:
                try:
                    result = session.execute(delete(PredictionResult).where(PredictionResult.id==prediction_id,
                                                                          PredictionResult.owner_key==owner_key))
                    removed = result.rowcount == 1
                    session.commit()
                    return removed
                except BaseException:
                    session.rollback()
                    raise
        except SQLAlchemyError:
            raise HistoryUnavailable('Prediction history could not be deleted') from None
