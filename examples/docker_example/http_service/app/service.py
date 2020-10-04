import json

import tomodachi


class Service(tomodachi.Service):
    name = "example"
    options = {"http": {"port": 80, "content_type": "application/json; charset=utf-8"}}

    _healthy = True

    @tomodachi.http("GET", r"/")
    async def index_endpoint(self, request):
        return json.dumps(
            {
                "data": "hello world!",
                "execution_context": tomodachi.get_execution_context(),
            }
        )

    @tomodachi.http("GET", r"/health/?", ignore_logging=True)
    async def health_check(self, request):
        if self._healthy:
            return 200, json.dumps({"status": "healthy"})
        else:
            return 503, json.dumps({"status": "not healthy"})

    @tomodachi.http_error(status_code=400)
    async def error_400(self, request):
        return json.dumps({"error": "bad-request"})

    @tomodachi.http_error(status_code=404)
    async def error_404(self, request):
        return json.dumps({"error": "not-found"})

    @tomodachi.http_error(status_code=405)
    async def error_405(self, request):
        return json.dumps({"error": "method-not-allowed"})
