import uuid
from typing import Any

from aiohttp import web

import tomodachi
from tomodachi import HttpResponse, Options, http


@tomodachi.decorator
async def require_auth_token(instance: Any, request: web.Request) -> Any:
    post_body = await request.read() if request.body_exists else None
    if not post_body or post_body.decode() != instance._allowed_token:
        return HttpResponse(body="Invalid token", status=403)


class ExampleHttpAuthService(tomodachi.Service):
    name = "example-http-service"

    # Some options can be specified to define credentials, used ports, hostnames, access log, etc.
    options = Options(
        http=Options.HTTP(
            port=4711,
            content_type="text/plain; charset=utf-8",
            access_log=True,
        ),
    )

    _allowed_token: str = str(uuid.uuid4())

    @http("GET", r"/get-token/?")
    async def get_token(self, request: web.Request) -> str:
        return self._allowed_token

    @http("POST", r"/validate/?")
    @require_auth_token
    async def validate(self, request: web.Request) -> str:
        return "Valid auth token!"
