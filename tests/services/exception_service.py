class ExceptionService(object):
    name = 'exception'
    log_level = 'DEBUG'

    async def _start_service(self):
        raise Exception("fail in _start_service()")
