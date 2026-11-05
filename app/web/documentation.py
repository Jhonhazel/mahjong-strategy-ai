"""Generated API documentation with a policy scoped to its known assets."""
import base64
import hashlib
import re

from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html


def documentation_response(openapi_url,kind):
    if kind=='swagger':
        response=get_swagger_ui_html(openapi_url=openapi_url,title='Mahjong Strategy AI · API')
    else:
        response=get_redoc_html(openapi_url=openapi_url,title='Mahjong Strategy AI · ReDoc',with_google_fonts=False)
    inline_scripts=re.findall(r'<script\b[^>]*>(.*?)</script>',response.body.decode(),re.S)
    hashes=["'sha256-"+base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()+"'"
            for script in inline_scripts if script.strip()]
    # Only these two documentation responses permit the generated CDN resources
    # and ReDoc's injected styles. Application pages retain the self-only policy.
    response.headers['Content-Security-Policy']=(
        "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net "+' '.join(hashes)+
        "; style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
        "img-src 'self' data: https://fastapi.tiangolo.com; "
        "worker-src 'self' blob:; base-uri 'self'; frame-ancestors 'none'"
    )
    return response
