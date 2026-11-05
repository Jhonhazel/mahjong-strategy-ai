"""Single-worker FastAPI integration; importing this module loads no assets."""
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from app import db
from app.domain.exceptions import GameNotFoundError, GameAlreadyFinishedError, IllegalActionError, InvalidTurnStateError, SessionCapacityExceededError, ServiceShuttingDownError
from app.domain.predictions import PredictionInvariantError
from app.services.game_service import GameSessionService
from app.services.ai_prediction_service import InvalidPredictionStateError, PredictionUnavailableError
from app.services.prediction_history_service import PredictionHistoryService, HistoryUnavailable
from app.services.web_prediction_service import WebPredictionService
from app.settings import ROOT, Settings
from app.web.api import router
from app.web.errors import WebError
from app.web.games import OwnedGames
from app.web.runtime import load_runtime_model
from app.web.security import VisitorSessions, BoundedBodyMiddleware
from app.web.contact import ContactRoster
from app.web.pages import router as pages_router
from app.web.documentation import documentation_response


@dataclass
class Resources:
    engine: object
    runtime: object
    games: OwnedGames
    history: PredictionHistoryService
    predictor: WebPredictionService
    visitors: VisitorSessions
    contacts: ContactRoster


def create_app(settings: Settings | None = None):
    config=settings or Settings()
    @asynccontextmanager
    async def lifespan(app):
        if app.state.initializing or app.state.resources is not None:
            raise RuntimeError('Application lifespan is already active')
        app.state.initializing=True
        engine=None;games=None
        try:
            engine=db.create_db_engine(config);db.check_schema(engine)
            runtime=load_runtime_model(config)
            legacy=GameSessionService(max_active_sessions=config.max_active_games,session_ttl_seconds=float('inf'))
            games=OwnedGames(legacy,config.max_active_games,config.game_ttl_seconds)
            history=PredictionHistoryService(engine)
            app.state.resources=Resources(engine,runtime,games,history,WebPredictionService(games,runtime,history),
                                          VisitorSessions(config),ContactRoster.from_path(config.contact_members_path))
            yield
        finally:
            try:
                if games is not None:games.shutdown(timeout=config.database_timeout_seconds+5)
            finally:
                if engine is not None:engine.dispose()
                app.state.resources=None;app.state.initializing=False

    app=FastAPI(title='Mahjong Strategy AI',version='3.0',lifespan=lifespan,docs_url=None,redoc_url=None,
                description='One human vs three existing bots; real v3 discard suggestions and owned PostgreSQL history. Single worker.')
    app.state.resources=None;app.state.initializing=False;app.state.settings=config
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=config.allowed_hosts)
    app.add_middleware(BoundedBodyMiddleware,maximum_bytes=config.max_body_bytes)
    app.include_router(router)
    app.include_router(pages_router)
    app.mount('/static',StaticFiles(directory=ROOT/'app/static'),name='static')

    @app.get('/docs',include_in_schema=False)
    def swagger_docs():return documentation_response(app.openapi_url,'swagger')

    @app.get('/redoc',include_in_schema=False)
    def redoc_docs():return documentation_response(app.openapi_url,'redoc')

    @app.exception_handler(WebError)
    async def web_error(request: Request,error):
        return JSONResponse({'detail':{'code':error.code,'message':error.message}},status_code=error.status_code)

    mapping={GameNotFoundError:(404,'not_found','Unknown or expired game'),
             GameAlreadyFinishedError:(409,'game_finished','The round is already finished'),
             InvalidTurnStateError:(409,'turn_conflict','The turn is stale or not a human discard decision'),
             IllegalActionError:(400,'illegal_action','Choose a currently legal action'),
             SessionCapacityExceededError:(429,'capacity_reached','All game slots are occupied'),
             ServiceShuttingDownError:(503,'shutting_down','The game service is shutting down'),
             InvalidPredictionStateError:(503,'prediction_unavailable','The encoded prediction state is incompatible'),
             PredictionUnavailableError:(409,'prediction_unavailable','No legal discard prediction is available'),
             PredictionInvariantError:(503,'prediction_invariant','The prediction failed state or legality checks'),
             HistoryUnavailable:(503,'history_unavailable','Prediction history is unavailable; retry the same request'),
             db.DatabaseUnavailable:(503,'database_unavailable','PostgreSQL or required schema is unavailable')}
    async def domain_error(request: Request,error):
        status,code,message=mapping[type(error)]
        return JSONResponse({'detail':{'code':code,'message':message}},status_code=status)
    for error_type in mapping:app.add_exception_handler(error_type,domain_error)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request,error):
        fields=[{'loc':list(e['loc']),'type':e['type']} for e in error.errors()]
        return JSONResponse({'detail':{'code':'validation_error','message':'Request validation failed','fields':fields}},status_code=422)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request,error):
        return JSONResponse({'detail':{'code':'http_error','message':'The requested operation is unavailable'}},status_code=error.status_code)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request,error):
        return JSONResponse({'detail':{'code':'internal_error','message':'An unexpected error occurred'}},status_code=500)
    return app
