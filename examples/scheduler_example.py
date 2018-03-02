import logging
import os
import tomodachi
from tomodachi import schedule, minutely, hourly


@tomodachi.service
class SchedulerService(object):
    name = 'example_scheduler_service'
    log_level = 'DEBUG'
    logger = logging.getLogger('log.{}'.format(name))
    uuid = os.environ.get('SERVICE_UUID')

    @schedule(interval='every second')
    async def every_second(self) -> None:
        self.logger.info('Heartbeat')

    @minutely  # @schedule(interval='minutely')
    async def every_minute(self) -> None:
        self.logger.info('Heartbeat (every minute)')

    @hourly  # @schedule(interval='hourly')
    async def every_hour(self) -> None:
        self.logger.info('Heartbeat (every hour)')

    @schedule(interval='*/2 * * * *')  # cron notation
    async def every_second_minute(self) -> None:
        self.logger.info('Heartbeat (every 2nd minute)')

    @schedule(interval='1/2 8-18 * * mon-fri')  # advanced cron notation
    async def work_hours(self) -> None:
        self.logger.info('Heartbeat (every odd minute between 8-18 on weekdays)')

    @schedule(interval='30 5 * jan,mar Ltue')  # the last Tuesday of January and March at 05:30 AM
    async def advanced_cron_notation_scheduling(self) -> None:
        self.logger.info('Heartbeat (the last Tuesday of January and March at 05:30 AM)')

    @schedule(timestamp='22:15:30')  # as a date timestamp
    async def as_timestamp(self) -> None:
        self.logger.info('Heartbeat (22:15:30)')

    @schedule(timestamp='00:00:00', timezone='Europe/Stockholm')  # with timezone support
    async def midnight_in_sweden(self) -> None:
        self.logger.info('Heartbeat (midnight in Sweden)')
