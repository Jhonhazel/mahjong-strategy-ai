"""Signed anonymous ownership, CSRF and a bounded request-body boundary."""
from dataclasses import dataclass, field
import hmac
import hashlib
import re
import secrets

from itsdangerous import BadData, URLSafeTimedSerializer
from starlette.responses import JSONResponse

from app.web.errors import WebError

COOKIE_NAME = 'mahjong_visitor'
TOKEN_PATTERN = re.compile(r'^[A-Za-z0-9_-]{43}$')


@dataclass(frozen=True)
class Visitor:
    owner_key: str = field(repr=False)
    csrf_token: str = field(repr=False)
    cookie_value: str = field(repr=False)


class VisitorSessions:
    def __init__(self, settings):
        self.settings = settings
        self.secret = settings.session_secret.get_secret_value()
        self.serializer = URLSafeTimedSerializer(self.secret, salt='mahjong-visitor-v1',signer_kwargs={'digest_method':hashlib.sha256})

    def _visitor(self, payload, cookie):
        if not isinstance(payload,dict) or set(payload) != {'visitor','csrf'}:
            raise ValueError('Invalid signed session payload')
        if any(not isinstance(value,str) or not TOKEN_PATTERN.fullmatch(value) for value in payload.values()):
            raise ValueError('Invalid signed session token')
        owner = hmac.digest(self.secret.encode(), ('owner:'+payload['visitor']).encode(), 'sha256').hex()
        return Visitor(owner, payload['csrf'], cookie)

    def create(self):
        payload = {'visitor':secrets.token_urlsafe(32),'csrf':secrets.token_urlsafe(32)}
        return self._visitor(payload,self.serializer.dumps(payload))

    def load(self, cookie):
        try:
            if not isinstance(cookie,str) or not cookie or len(cookie)>1024:
                raise ValueError('Missing session')
            payload = self.serializer.loads(cookie,max_age=self.settings.session_ttl_seconds)
            return self._visitor(payload,cookie)
        except (BadData,ValueError,TypeError):
            raise WebError(401,'session_required','Start or renew your browser session before this operation') from None

    def check_csrf(self, visitor, provided_token, origin=None, expected_origin=None):
        if (not isinstance(provided_token,str) or not TOKEN_PATTERN.fullmatch(provided_token)
                or not secrets.compare_digest(provided_token,visitor.csrf_token)
                or (origin is not None and origin!=expected_origin)):
            raise WebError(403,'csrf_rejected','The request requires the current session CSRF token and same origin')

    def set_cookie(self, response, visitor):
        response.set_cookie(COOKIE_NAME,visitor.cookie_value,max_age=self.settings.session_ttl_seconds,
                            httponly=True,secure=self.settings.cookie_secure,samesite='lax',path='/')


class BoundedBodyMiddleware:
    def __init__(self, app, maximum_bytes=16384):
        self.app, self.maximum_bytes = app, maximum_bytes

    async def __call__(self, scope, receive, send):
        if scope['type']!='http':
            return await self.app(scope,receive,send)
        async def private_send(message):
            if message['type']=='http.response.start':
                response_headers=[*message.get('headers',[]),(b'cache-control',b'no-store'),
                                  (b'x-content-type-options',b'nosniff')]
                if not any(name.lower()==b'content-security-policy' for name,value in response_headers):
                    response_headers.append((b'content-security-policy',b"default-src 'self'; script-src 'self'; style-src 'self'; base-uri 'self'; frame-ancestors 'none'"))
                message['headers']=response_headers
            await send(message)
        headers = dict(scope.get('headers',[]))
        try:
            length = int(headers.get(b'content-length',b'0'))
            if length<0:raise ValueError
        except ValueError:
            return await JSONResponse({'detail':{'code':'invalid_body','message':'Invalid content length'}},status_code=400)(scope,receive,private_send)
        body = bytearray()
        if length>self.maximum_bytes:
            return await self._too_large(scope,receive,private_send)
        while True:
            message = await receive()
            if message['type']=='http.disconnect':return
            chunk = message.get('body',b'')
            if len(body)+len(chunk)>self.maximum_bytes:
                return await self._too_large(scope,receive,private_send)
            body.extend(chunk)
            if not message.get('more_body',False):break
        delivered = False
        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered=True
                return {'type':'http.request','body':bytes(body),'more_body':False}
            return await receive()
        await self.app(scope,bounded_receive,private_send)

    async def _too_large(self, scope, receive, send):
        response = JSONResponse({'detail':{'code':'payload_too_large','message':'Request body exceeds the allowed limit'}},
                                status_code=413,headers={'Connection':'close'})
        await response(scope,receive,send)
