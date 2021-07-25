import os
import uuid as uuid_
from typing import Any

from aiohttp import web

import tomodachi
from tomodachi import HttpResponse, http


@tomodachi.decorator
async def require_auth_token(instance: Any, request: web.Request) -> Any:
    post_body = await request.read() if request.body_exists else None
    if not post_body or post_body.decode() != instance.allowed_token:
        return HttpResponse(body="Invalid token", status=403)


class ExampleHttpAuthService(tomodachi.Service):
    name = "example-http-auth-service"
    log_level = "DEBUG"
    uuid = str(os.environ.get("SERVICE_UUID") or "")

    allowed_token = str(uuid_.uuid4())

    options = {"http.port": 4711, "http.content_type": "text/plain; charset=utf-8", "http.access_log": True}

    @http("GET", r"/get-token/?")
    async def get_token(self, request: web.Request) -> str:
        return self.allowed_token

    @http("POST", r"/validate/?")
    @require_auth_token
    async def validate(self, request: web.Request) -> str:
        return "Valid auth token!"
