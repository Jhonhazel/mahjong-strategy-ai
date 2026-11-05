import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Header, Query, Request, Response
from starlette.responses import JSONResponse

from app.db import check_schema, DatabaseUnavailable
from app.web.errors import WebError
from app.web.schemas import ActionRequest, GameCreate, GameViewOut, TurnRequest, SavedPredictionOut, HistoryPageOut, HistoryDetailOut
from app.web.security import COOKIE_NAME, Visitor
from app.web.views import safe_player_view, history_summary, history_detail, saved_prediction

router = APIRouter(responses={401:{'description':'Missing or expired browser session'},403:{'description':'CSRF/origin rejected'},
                            404:{'description':'Unknown, expired or inaccessible resource'},409:{'description':'Stale turn or incompatible game phase'},
                            422:{'description':'Invalid request'},503:{'description':'Required model/history dependency unavailable'}})


def resources(request: Request):
    value = request.app.state.resources
    if value is None:raise WebError(503,'not_ready','Application resources are unavailable')
    return value


def current_visitor(request: Request,visitor_cookie: Annotated[str | None,Cookie(
        alias=COOKIE_NAME,description='Signed HttpOnly context issued by GET /api/session or a page; required for owned resources')]=None):
    # Page handlers also call this boundary directly, without FastAPI injection.
    return resources(request).visitors.load(visitor_cookie if visitor_cookie is not None else request.cookies.get(COOKIE_NAME))


def mutation_visitor(request: Request, visitor: Annotated[Visitor,Depends(current_visitor)],
                     csrf_token: Annotated[str | None,Header(alias='X-CSRF-Token',
                         description='Required for mutations: copy csrf_token from GET /api/session; keep its browser cookie')]=None):
    resources(request).visitors.check_csrf(visitor,csrf_token,request.headers.get('origin'),
                                          f'{request.url.scheme}://{request.headers.get("host","")}')
    return visitor


@router.get('/health/live',tags=['health'])
def live():return {'status':'alive'}


@router.get('/health/ready',tags=['health'])
def ready(request: Request):
    try:
        check_schema(resources(request).engine)
        return {'status':'ready','model':'ready','database':'ready'}
    except DatabaseUnavailable:
        return JSONResponse({'detail':{'code':'not_ready','message':'PostgreSQL or required schema is unavailable'}},status_code=503)


@router.get('/api/session',tags=['session'])
def session_context(request: Request, response: Response):
    origin=request.headers.get('origin');expected=f'{request.url.scheme}://{request.headers.get("host","")}'
    if request.headers.get('sec-fetch-site')=='cross-site' or (origin is not None and origin!=expected):
        raise WebError(403,'origin_rejected','Initialize a session from this website')
    sessions=resources(request).visitors
    try:visitor=sessions.load(request.cookies.get(COOKIE_NAME))
    except WebError:
        visitor=sessions.create();sessions.set_cookie(response,visitor)
    return {'csrf_token':visitor.csrf_token,'expires_in':sessions.settings.session_ttl_seconds}


@router.post('/api/games',response_model=GameViewOut,status_code=201,tags=['games'],responses={429:{'description':'Game capacity reached'}})
def create_game(payload: GameCreate,request: Request,visitor: Annotated[Visitor,Depends(mutation_visitor)]):
    return safe_player_view(resources(request).games.create(visitor.owner_key,**payload.model_dump()))


@router.get('/api/games/{game_id}',response_model=GameViewOut,tags=['games'])
def get_game(game_id: uuid.UUID,request: Request,visitor: Annotated[Visitor,Depends(current_visitor)]):
    return safe_player_view(resources(request).games.view(visitor.owner_key,game_id))


@router.post('/api/games/{game_id}/actions',response_model=GameViewOut,tags=['games'],responses={400:{'description':'Action is illegal'}})
def submit_action(game_id: uuid.UUID,payload: ActionRequest,request: Request,visitor: Annotated[Visitor,Depends(mutation_visitor)]):
    return safe_player_view(resources(request).games.action(visitor.owner_key,game_id,payload.action_id,payload.expected_turn_number))


@router.post('/api/games/{game_id}/predict',response_model=SavedPredictionOut,status_code=201,tags=['predictions'],responses={200:{'description':'Existing prediction reused'}})
def predict(game_id: uuid.UUID,payload: TurnRequest,request: Request,response: Response,visitor: Annotated[Visitor,Depends(mutation_visitor)]):
    record,reused=resources(request).predictor.predict(visitor.owner_key,game_id,payload.expected_turn_number)
    response.status_code=200 if reused else 201
    return saved_prediction(record,reused)


@router.get('/api/predictions',response_model=HistoryPageOut,tags=['history'])
def list_predictions(request: Request,visitor: Annotated[Visitor,Depends(current_visitor)],
                     limit: int=Query(20,ge=1,le=100),offset: int=Query(0,ge=0,le=100000)):
    records,total=resources(request).history.list(visitor.owner_key,limit,offset)
    return HistoryPageOut(items=[history_summary(r) for r in records],total=total,limit=limit,offset=offset)


@router.get('/api/predictions/{prediction_id}',response_model=HistoryDetailOut,tags=['history'])
def get_prediction(prediction_id: uuid.UUID,request: Request,visitor: Annotated[Visitor,Depends(current_visitor)]):
    record=resources(request).history.get(visitor.owner_key,prediction_id)
    if record is None:raise WebError(404,'not_found','Prediction not found')
    return history_detail(record)


@router.delete('/api/predictions/{prediction_id}',status_code=204,tags=['history'])
def delete_prediction(prediction_id: uuid.UUID,request: Request,visitor: Annotated[Visitor,Depends(mutation_visitor)]):
    if not resources(request).history.delete(visitor.owner_key,prediction_id):
        raise WebError(404,'not_found','Prediction not found')
    return Response(status_code=204)
