import tomodachi


@tomodachi.service
class Service(tomodachi.Service):
    name = 'example'
    options = {
        'http': {
            'port': 8080
        }
    }

    @tomodachi.http('GET', r'/')
    async def index_endpoint(self, request):
        return 'friends forever!'

    @tomodachi.http('GET', r'/health')
    async def health_check(self, request):
        return 'healthy'