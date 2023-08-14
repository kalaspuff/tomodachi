import base64
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
        except BaseException:
            try:
                tomodachi.get_logger("exception").exception()
                raise
            finally:
                return web.json_response({"status": "internal server error"}, status=500)


class ExampleHttpBasicAuthService(tomodachi.Service):
    name = "example-http-service"

    # Adds a middleware function that is run on every HTTP call. Several middlewares can be chained.
    http_middleware = [BasicAuthMiddleware(username="example", password="example")]

    # Some options can be specified to define credentials, used ports, hostnames, access log, etc.
    options = Options(
        http=Options.HTTP(
            port=4711,
            content_type="text/plain; charset=utf-8",
        ),
    )

    @http("GET", r"/")
    async def index(self, *, username: str) -> web.Response:
        return web.json_response({"status": "authenticated", "username": username}, status=200)
