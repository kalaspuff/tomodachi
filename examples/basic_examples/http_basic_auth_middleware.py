import base64
import logging
from typing import Awaitable, Callable

from aiohttp import web

import tomodachi
from tomodachi import Options, http


class BasicAuthMiddleware:
    def __init__(self, username: str, password: str) -> None:
        self.valid_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

    async def __call__(self, func: Callable[..., Awaitable[web.Response]], *, request: web.Request) -> web.Response:
        try:
            auth = request.headers.get("Authorization", "")
            encoded_credentials = auth.split()[-1] if auth.startswith("Basic ") else ""

            if encoded_credentials == self.valid_credentials:
                username = base64.b64decode(encoded_credentials).decode().split(":")[0]
                return await func(username=username)
            elif auth:
                return web.json_response({"status": "auth required", "error": "bad credentials"}, status=401)

            return web.json_response({"status": "auth required"}, status=401)
        except BaseException as exc:
            try:
                logging.getLogger("exception").exception(exc)
                raise exc
            finally:
                return web.json_response({"status": "internal server error"}, status=500)


class ExampleHttpBasicAuthService(tomodachi.Service):
    name = "example-http-auth-service"
    http_middleware = [BasicAuthMiddleware(username="example", password="example")]
    options = Options(
        http=Options.HTTP(
            port=4711,
            content_type="text/plain; charset=utf-8",
        ),
    )

    @http("GET", r"/")
    async def index(self, *, username: str) -> web.Response:
        return web.json_response({"status": "authenticated", "username": username}, status=200)
