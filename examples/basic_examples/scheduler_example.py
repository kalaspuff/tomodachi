import os

import tomodachi
from tomodachi import hourly, minutely, schedule


class SchedulerService(tomodachi.Service):
    name = "example-scheduler-service"
    log_level = "DEBUG"
    uuid = str(os.environ.get("SERVICE_UUID") or "")

    @schedule(interval="every second")
    async def every_second(self) -> None:
        self.log("Heartbeat")

    @minutely  # @schedule(interval='minutely')
    async def every_minute(self) -> None:
        self.log("Heartbeat (every minute)")

    @hourly  # @schedule(interval='hourly')
    async def every_hour(self) -> None:
        self.log("Heartbeat (every hour)")

    @schedule(interval="*/2 * * * *")  # cron notation
    async def every_second_minute(self) -> None:
        self.log("Heartbeat (every 2nd minute)")

    @schedule(interval="1/2 8-18 * * mon-fri")  # advanced cron notation
    async def work_hours(self) -> None:
        self.log("Heartbeat (every odd minute between 8-18 on weekdays)")

    @schedule(interval="30 5 * jan,mar Ltue")  # the last Tuesday of January and March at 05:30 AM
    async def advanced_cron_notation_scheduling(self) -> None:
        self.log("Heartbeat (the last Tuesday of January and March at 05:30 AM)")

    @schedule(timestamp="22:15:30")  # as a date timestamp
    async def as_timestamp(self) -> None:
        self.log("Heartbeat (22:15:30)")

    @schedule(timestamp="00:00:00", timezone="Europe/Stockholm")  # with timezone support
    async def midnight_in_sweden(self) -> None:
        self.log("Heartbeat (midnight in Sweden)")

    @schedule(interval=20)
    async def every_twenty_seconds(self) -> None:
        self.log("Every 20 seconds")

    @schedule(interval=20, immediately=True)
    async def every_twenty_seconds_and_immediately(self) -> None:
        self.log("Every 20 seconds and immediately")
