import asyncio
from dataclasses import replace
import secrets

import pytest
from pydantic import ValidationError
from starlette.responses import JSONResponse

from app.domain.exceptions import GameNotFoundError, SessionCapacityExceededError
from app.domain.models import RoundResult
from app.services.game_service import GameSessionService
from tests.test_phase3_bootstrap import settings


def test_signed_visitor_identity_csrf_and_forgery_protection(monkeypatch):
    from app.web.security import VisitorSessions
    from app.web.errors import WebError
    sessions=VisitorSessions(settings());visitor=sessions.create()
    assert sessions.load(visitor.cookie_value).owner_key==visitor.owner_key
    assert set(sessions.serializer.loads(visitor.cookie_value))=={'visitor','csrf'}
    assert visitor.cookie_value not in repr(visitor) and visitor.csrf_token not in repr(visitor)
    for cookie in (None,'forged',visitor.cookie_value+'x'):
        with pytest.raises(WebError) as error:sessions.load(cookie)
        assert error.value.status_code==401
    sessions.check_csrf(visitor,visitor.csrf_token,'http://testserver','http://testserver')
    for token,origin in ((None,None),('wrong',None),(visitor.csrf_token,'https://other.invalid')):
        with pytest.raises(WebError) as error:sessions.check_csrf(visitor,token,origin,'http://testserver')
        assert error.value.status_code==403


def test_expired_signed_visitor_cannot_mutate(monkeypatch):
    from itsdangerous.timed import TimestampSigner
    from app.web.security import VisitorSessions
    from app.web.errors import WebError
    sessions=VisitorSessions(settings().model_copy(update={'session_ttl_seconds':1}))
    original=TimestampSigner.get_timestamp
    with monkeypatch.context() as patch:
        patch.setattr(TimestampSigner,'get_timestamp',lambda self:original(self)-100)
        cookie=sessions.create().cookie_value
    with pytest.raises(WebError) as error:sessions.load(cookie)
    assert error.value.status_code==401


@pytest.mark.parametrize('content_length',[True,False])
def test_body_limit_rejects_declared_and_chunked_oversize_without_route(content_length):
    from app.web.security import BoundedBodyMiddleware
    called=[];messages=[]
    async def endpoint(scope,receive,send):
        called.append(True);await JSONResponse({'ok':True})(scope,receive,send)
    events=[{'type':'http.request','body':b'x'*700,'more_body':True},
            {'type':'http.request','body':b'x'*700,'more_body':False}]
    async def receive():return events.pop(0)
    async def send(message):messages.append(message)
    scope={'type':'http','method':'POST','path':'/api/games','headers':[(b'content-length',b'1400')] if content_length else []}
    asyncio.run(BoundedBodyMiddleware(endpoint,maximum_bytes=1024)(scope,receive,send))
    assert not called and messages[0]['status']==413


def test_owned_games_reject_other_owner_capacity_and_idle_expiry():
    from app.web.games import OwnedGames
    clock=[0.];legacy=GameSessionService(max_active_sessions=1,session_ttl_seconds=float('inf'))
    games=OwnedGames(legacy,max_active_games=1,ttl_seconds=10,clock=lambda:clock[0])
    owner=secrets.token_hex(32)
    try:
        view=games.create(owner,seed=42,human_seat=0)
        with pytest.raises(GameNotFoundError):games.view('other-owner',view.game_id)
        with pytest.raises(SessionCapacityExceededError):games.create(owner,seed=43)
        clock[0]=11
        with pytest.raises(GameNotFoundError):games.view(owner,view.game_id)
        assert legacy.active_session_count()==0
    finally:games.shutdown()


def test_game_lease_prevents_idle_eviction_during_prediction_and_other_game_creation():
    from app.web.games import OwnedGames
    clock=[0.];legacy=GameSessionService(max_active_sessions=2,session_ttl_seconds=float('inf'))
    games=OwnedGames(legacy,max_active_games=2,ttl_seconds=10,clock=lambda:clock[0]);owner=secrets.token_hex(32)
    try:
        view=games.create(owner,seed=42,human_seat=0)
        with games.owned(owner,view.game_id):
            clock[0]=100
            other=games.create(owner,seed=43,human_seat=0)
            assert legacy.get_player_view(view.game_id)==view
        assert games.view(owner,view.game_id)==view and other.game_id!=view.game_id
    finally:games.shutdown()


def test_safe_serializer_excludes_referee_and_opponent_revealed_hands():
    from app.web.views import safe_player_view
    games=GameSessionService()
    try:
        view=games.create_game(seed=42,human_seat=0)
        result=RoundResult('draw',None,None,False,None,0,(),(0,0,0,0),(('W1',),)*4)
        data=safe_player_view(replace(view,status='FINISHED',round_result=result)).model_dump(mode='json')
        assert set(data)=={'game_id','status','human_seat','prevalent_wind','active_seat','turn_number',
                          'wall_tiles_remaining','own_hand','own_flowers','seat_public_states','legal_actions',
                          'can_request_ai_prediction','round_result'}
        assert 'revealed_hands' not in data['round_result'] and data['round_result']['ending']=='draw'
        assert all(set(seat)=={'seat','concealed_count','melds','flowers','discards','wall_remaining'} for seat in data['seat_public_states'])
    finally:games.shutdown()


def test_http_input_schemas_reject_client_tensors_boolean_tokens_and_invalid_ids():
    from app.web.schemas import ActionRequest,GameCreate,TurnRequest
    for cls,payload in [(ActionRequest,{'action_id':235,'expected_turn_number':0}),
                        (ActionRequest,{'action_id':True,'expected_turn_number':0}),
                        (TurnRequest,{'expected_turn_number':True}),
                        (TurnRequest,{'expected_turn_number':0,'obs':[]}),
                        (GameCreate,{'human_seat':4}),(GameCreate,{'wall':[]})]:
        with pytest.raises(ValidationError):cls.model_validate(payload)


def test_post_meld_annotation_follows_real_accepted_human_claim():
    import random
    from app.services.bot_service import ShantenHeuristicBot
    from app.web.games import OwnedGames
    legacy=GameSessionService(session_ttl_seconds=float('inf'));games=OwnedGames(legacy)
    owner=secrets.token_hex(32);helper=ShantenHeuristicBot();rng=random.Random(42)
    try:
        view=games.create(owner,seed=42,human_seat=1)
        for _ in range(200):
            if view.status=='FINISHED':break
            if view.status=='WAITING_HUMAN_DISCARD':
                state=legacy.get_human_encoded_turn(view.game_id)
                chosen_id=helper.select_action(state,view.own_hand,view.seat_public_states[1].melds,rng)
                chosen=next(a for a in view.legal_actions if a.action_id==chosen_id)
            else:
                choices=[a for a in view.legal_actions if a.action_type=='Hu'] or [a for a in view.legal_actions if a.action_type in ('Chi','Peng')] or list(view.legal_actions)
                chosen=choices[0]
            view=games.action(owner,view.game_id,chosen.action_id,view.turn_number)
            if chosen.action_type in ('Chi','Peng'):
                with games.owned(owner,view.game_id) as entry:assert entry.turn_phase=='POST_MELD_DISCARD'
                return
        pytest.fail('Known deterministic full-round policy did not reach a post-meld discard')
    finally:games.shutdown()


def test_competing_chi_does_not_label_the_next_draw_as_post_meld():
    from app.web.games import OwnedGames
    legacy=GameSessionService(session_ttl_seconds=float('inf'));games=OwnedGames(legacy);owner=secrets.token_hex(32)
    try:
        view=games.create(owner,seed=44,human_seat=1)
        for _ in range(10):
            choices=[a for a in view.legal_actions if a.action_type=='Hu'] or [a for a in view.legal_actions if a.action_type in ('Chi','Peng')] or list(view.legal_actions)
            chosen=choices[0];before=view
            view=games.action(owner,view.game_id,chosen.action_id,view.turn_number)
            if before.turn_number==33:
                assert chosen.action_id==73 and chosen.action_type=='Chi'
                assert view.turn_number==48 and len(view.seat_public_states[1].melds)==0
                assert legacy._sessions[view.game_id].engine.phase=='SELF_TURN'
                with games.owned(owner,view.game_id) as entry:assert entry.turn_phase=='SELF_TURN'
                return
        pytest.fail('Deterministic competitive Chi fixture was not reached')
    finally:games.shutdown()


def _body_boundary_exchange(headers,events,response=None):
    from app.web.security import BoundedBodyMiddleware
    messages=[];received=[];downstream=[];pending=list(events)
    async def endpoint(scope,receive,send):
        downstream.append(await receive())
        result=response if response is not None else JSONResponse({'ok':True},headers={'X-Route':'preserved'})
        await result(scope,receive,send)
    async def receive():
        assert pending, 'Middleware read past the supplied bounded request'
        event=pending.pop(0);received.append(event);return event
    async def send(message):messages.append(message)
    scope={'type':'http','method':'POST','path':'/api/games','headers':headers}
    asyncio.run(BoundedBodyMiddleware(endpoint,maximum_bytes=1024)(scope,receive,send))
    return messages,received,downstream,pending


def _assert_p3_01_headers(messages,expected_csp=None):
    expected_csp=expected_csp or "default-src 'self'; script-src 'self'; style-src 'self'; base-uri 'self'; frame-ancestors 'none'"
    headers=messages[0]['headers']
    for name,expected in ((b'cache-control',b'no-store'),(b'x-content-type-options',b'nosniff'),
                          (b'content-security-policy',expected_csp.encode())):
        values=[value for key,value in headers if key.lower()==name]
        assert values==[expected], (name,values)


@pytest.mark.parametrize('length',[b'-1',b'malformed'])
def test_p3_01_invalid_content_length_has_security_headers_without_route(length):
    import json
    messages,received,downstream,_=_body_boundary_exchange([(b'content-length',length)],[])
    assert messages[0]['status']==400 and not received and not downstream
    assert json.loads(messages[1]['body'])=={'detail':{'code':'invalid_body','message':'Invalid content length'}}
    assert b'connection' not in dict(messages[0]['headers'])
    _assert_p3_01_headers(messages)


def test_p3_01_declared_oversize_has_security_headers_and_connection_close():
    import json
    messages,received,downstream,_=_body_boundary_exchange([(b'content-length',b'1025')],[])
    assert messages[0]['status']==413 and not received and not downstream
    assert json.loads(messages[1]['body'])=={'detail':{'code':'payload_too_large','message':'Request body exceeds the allowed limit'}}
    assert dict(messages[0]['headers'])[b'connection']==b'close'
    _assert_p3_01_headers(messages)


@pytest.mark.parametrize('length',[None,b'1'])
def test_p3_01_streamed_oversize_has_security_headers_and_stops_reading(length):
    import json
    events=[{'type':'http.request','body':b'x'*700,'more_body':True},
            {'type':'http.request','body':b'y'*400,'more_body':True},
            {'type':'http.request','body':b'unread','more_body':False}]
    headers=[] if length is None else [(b'content-length',length)]
    messages,received,downstream,pending=_body_boundary_exchange(headers,events)
    assert messages[0]['status']==413 and not downstream
    assert len(received)==2 and pending==events[2:]
    assert json.loads(messages[1]['body'])=={'detail':{'code':'payload_too_large','message':'Request body exceeds the allowed limit'}}
    assert dict(messages[0]['headers'])[b'connection']==b'close'
    _assert_p3_01_headers(messages)


@pytest.mark.parametrize('kind',['normal','swagger','redoc'])
def test_p3_01_normal_and_documentation_responses_preserve_body_and_csp(kind):
    from app.web.documentation import documentation_response
    response=(JSONResponse({'ok':True},headers={'X-Route':'preserved'}) if kind=='normal'
              else documentation_response('/openapi.json',kind))
    original_csp=response.headers.get('content-security-policy')
    event={'type':'http.request','body':b'input','more_body':False}
    messages,received,downstream,pending=_body_boundary_exchange([], [event],response)
    assert messages[0]['status']==200 and messages[1]['body']==response.body
    assert received==[event] and downstream==[event] and not pending
    if kind=='normal':assert dict(messages[0]['headers'])[b'x-route']==b'preserved'
    else:assert original_csp and 'https://cdn.jsdelivr.net' in original_csp
    _assert_p3_01_headers(messages,original_csp)


def test_p3_01_exact_body_limit_preserves_the_full_request():
    event={'type':'http.request','body':b'x'*1024,'more_body':False}
    messages,received,downstream,pending=_body_boundary_exchange([(b'content-length',b'1024')],[event])
    assert messages[0]['status']==200 and downstream==[event] and received==[event] and not pending
    _assert_p3_01_headers(messages)


def test_p3_01_disconnect_does_not_execute_downstream_or_respond():
    events=[{'type':'http.request','body':b'partial','more_body':True},{'type':'http.disconnect'},
            {'type':'http.request','body':b'unread','more_body':False}]
    messages,received,downstream,pending=_body_boundary_exchange([],events)
    assert not messages and not downstream and received==events[:2] and pending==events[2:]


def test_p3_01_non_http_scope_keeps_original_callbacks():
    from app.web.security import BoundedBodyMiddleware
    scope={'type':'lifespan'};messages=[]
    async def receive():return {'type':'lifespan.startup'}
    async def send(message):messages.append(message)
    async def endpoint(actual_scope,actual_receive,actual_send):
        assert actual_scope is scope and actual_receive is receive and actual_send is send
        assert await actual_receive()=={'type':'lifespan.startup'}
        await actual_send({'type':'lifespan.startup.complete'})
    asyncio.run(BoundedBodyMiddleware(endpoint)(scope,receive,send))
    assert messages==[{'type':'lifespan.startup.complete'}]
