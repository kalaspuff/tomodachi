import datetime
import asyncio
import time
from typing import Any, Dict, List, Union, Optional, Callable, Awaitable  # noqa
from tomodachi.invoker import Invoker
from tomodachi.helpers.crontab import get_next_datetime


class Scheduler(Invoker):
    close_waiter = None

    async def schedule_handler(cls: Any, obj: Any, context: Dict, func: Any, interval: Optional[Union[str, int]]=None, timestamp: Optional[str]=None, timezone: Optional[str]=None) -> Any:
        async def handler() -> None:
            kwargs = {k: func.__defaults__[len(func.__defaults__) - len(func.__code__.co_varnames[1:]) + i] if func.__defaults__ and len(func.__defaults__) - len(func.__code__.co_varnames[1:]) + i >= 0 else None for i, k in enumerate(func.__code__.co_varnames[1:])}  # type: Dict
            routine = func(*(obj,), **kwargs)
            try:
                if isinstance(routine, Awaitable):
                    await routine
            except Exception as e:
                pass

        context['_schedule_scheduled_functions'] = context.get('_schedule_scheduled_functions', [])
        context['_schedule_scheduled_functions'].append((interval, timestamp, timezone, func, handler))

        start_func = cls.start_scheduler(cls, obj, context)
        return (await start_func) if start_func else None

    @classmethod
    def next_call_at(cls, current_time: float, interval: Optional[Union[str, int]]=None, timestamp: Optional[str]=None, timezone: Optional[str]=None) -> int:
        if interval is None and timestamp is not None:
            if isinstance(timestamp, str):
                try:
                    datetime_object = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                    interval = '{} {} {} {} * {}'.format(datetime_object.minute, datetime_object.hour, datetime_object.day, datetime_object.month, datetime_object.year)
                    second_modifier = 1
                    if datetime_object > datetime.datetime.fromtimestamp(current_time):
                        second_modifier = -60
                    next_at = get_next_datetime(interval, datetime.datetime.fromtimestamp(current_time + second_modifier))
                    if not next_at:
                        return int(current_time + 60 * 60 * 24 * 365 * 100)
                    return int(next_at.timestamp() + datetime_object.second)
                except ValueError:
                    pass

                try:
                    datetime_object = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M')
                    interval = '{} {} {} {} * {}'.format(datetime_object.minute, datetime_object.hour, datetime_object.day, datetime_object.month, datetime_object.year)
                    next_at = get_next_datetime(interval, datetime.datetime.fromtimestamp(current_time + 1))
                    if not next_at:
                        return int(current_time + 60 * 60 * 24 * 365 * 100)
                    return int(next_at.timestamp())
                except ValueError:
                    pass

                try:
                    datetime_object = datetime.datetime.strptime(timestamp, '%H:%M:%S')
                    datetime_object = datetime.datetime(datetime.datetime.fromtimestamp(current_time).year, datetime.datetime.fromtimestamp(current_time).month, datetime.datetime.fromtimestamp(current_time).day, datetime_object.hour, datetime_object.minute, datetime_object.second)
                    interval = '{} {} * * *'.format(datetime_object.minute, datetime_object.hour)
                    second_modifier = 1
                    if datetime_object > datetime.datetime.fromtimestamp(current_time):
                        second_modifier = -60
                    next_at = get_next_datetime(interval, datetime.datetime.fromtimestamp(current_time + second_modifier))
                    if not next_at:
                        return int(current_time + 60 * 60 * 24 * 365 * 100)
                    return int(next_at.timestamp() + datetime_object.second)
                except ValueError:
                    pass

                try:
                    datetime_object = datetime.datetime.strptime(timestamp, '%H:%M')
                    interval = '{} {} * * *'.format(datetime_object.minute, datetime_object.hour)
                    next_at = get_next_datetime(interval, datetime.datetime.fromtimestamp(current_time + 1))
                    if not next_at:
                        return int(current_time + 60 * 60 * 24 * 365 * 100)
                    return int(next_at.timestamp())
                except ValueError:
                    pass

                raise Exception('Invalid timestamp')

        if interval is not None:
            if isinstance(interval, int):
                return int(current_time + interval)
            interval = interval.lower()
            if interval in ('every second', '1s', '1 s', '1second', '1 second', 'second', 'secondly', 'once per second'):
                return int(current_time + 1)
            if interval in ('every minute', '1m', '1 m', '1minute', '1 minute', 'minute', 'minutely', 'once per minute'):
                interval = '@minutely'
            if interval in ('every hour', '1h', '1 h', '1hour', '1 hour', 'hour', 'hourly', 'once per hour'):
                interval = '@hourly'
            if interval in ('every day', '1d', '1 d', '1day', '1 day', 'day', 'daily', 'once per day', 'nightly'):
                interval = '@daily'
            if interval in ('every month', '1month', '1 month', 'month', 'monthly', 'once per month'):
                interval = '@monthly'
            if interval in ('every year', '1y', '1 y', '1year', '1 year', 'year', 'yearly', 'once per year', 'annually'):
                interval = '@yearly'
            if interval in ('monday', 'mondays', 'mon', 'every monday', 'once per monday', 'weekly', 'once per week', 'week', 'every week'):
                interval = '0 0 * * 1'
            if interval in ('tuesday', 'tuesdays', 'tue', 'every tuesday', 'once per tuesday'):
                interval = '0 0 * * 2'
            if interval in ('wednesday', 'wednesdays', 'wed', 'every wednesday', 'once per wednesday'):
                interval = '0 0 * * 3'
            if interval in ('thursday', 'thursdays', 'thu', 'every thursday', 'once per thursday'):
                interval = '0 0 * * 4'
            if interval in ('friday', 'fridays', 'fri', 'every friday', 'once per friday'):
                interval = '0 0 * * 5'
            if interval in ('saturday', 'saturdays', 'sat', 'every saturday', 'once per saturday'):
                interval = '0 0 * * 6'
            if interval in ('sunday', 'sundays', 'sun', 'every sunday', 'once per sunday'):
                interval = '0 0 * * 0'
            if interval in ('weekday', 'weekdays', 'every weekday'):
                interval = '0 0 * * 1-5'
            if interval in ('weekend', 'weekends', 'every weekend'):
                interval = '0 0 * * 0,6'

            try:
                next_at = get_next_datetime(interval, datetime.datetime.fromtimestamp(current_time + 1))
                if not next_at:
                    return int(current_time + 60 * 60 * 24 * 365 * 100)
                return int(next_at.timestamp())
            except:
                raise Exception('Invalid interval')

        return int(current_time + 60 * 60 * 24 * 365 * 100)

    async def start_schedule_loop(cls: Any, obj: Any, context: Dict, handler: Callable, interval: Optional[Union[str, int]]=None, timestamp: Optional[str]=None, timezone: Optional[str]=None) -> None:
        if timezone:
            raise Exception("Timezone support not yet implemented")

        if not cls.close_waiter:
            cls.close_waiter = asyncio.Future()
        stop_waiter = asyncio.Future()  # type: asyncio.Future
        start_waiter = asyncio.Future()  # type: asyncio.Future

        async def schedule_loop() -> None:
            await start_waiter
            next_call_at = None
            prev_call_at = None
            tasks = []  # type: List
            current_time = time.time()
            while not cls.close_waiter.done():
                last_time = current_time
                actual_time = time.time()
                current_time = last_time + 1 if int(last_time + 1) < int(actual_time) else actual_time
                if next_call_at is None:
                    next_call_at = cls.next_call_at(current_time, interval, timestamp, timezone)
                    if prev_call_at and prev_call_at == next_call_at:
                        next_call_at = None
                        continue
                sleep_diff = int(current_time + 1) - actual_time + 0.001
                if sleep_diff > 0:
                    await asyncio.sleep(sleep_diff)
                if next_call_at > time.time():
                    continue
                if cls.close_waiter.done():
                    continue
                prev_call_at = next_call_at
                next_call_at = None
                tasks = [task for task in tasks if not task.done()]
                tasks.append(asyncio.ensure_future(asyncio.shield(handler())))

            if tasks:
                await asyncio.wait(tasks)
            if not stop_waiter.done():
                stop_waiter.set_result(None)

        loop = asyncio.get_event_loop()  # type: Any

        stop_method = getattr(obj, '_stop_service', None)
        async def stop_service(*args: Any, **kwargs: Any) -> None:
            if not cls.close_waiter.done():
                cls.close_waiter.set_result(None)

                if not start_waiter.done():
                    start_waiter.set_result(None)
                await stop_waiter
                if stop_method:
                    await stop_method(*args, **kwargs)
            else:
                await stop_waiter
                if stop_method:
                    await stop_method(*args, **kwargs)

        setattr(obj, '_stop_service', stop_service)

        started_method = getattr(obj, '_started_service', None)
        async def started_service(*args: Any, **kwargs: Any) -> None:
            if started_method:
                await started_method(*args, **kwargs)
            if not start_waiter.done():
                start_waiter.set_result(None)

        setattr(obj, '_started_service', started_service)

        loop.create_task(schedule_loop())

    async def start_scheduler(cls: Any, obj: Any, context: Dict) -> Optional[Callable]:
        if context.get('_schedule_loop_started'):
            return None
        context['_schedule_loop_started'] = True

        async def _schedule() -> None:
            for interval, timestamp, timezone, func, handler in context.get('_schedule_scheduled_functions', []):
                await cls.start_schedule_loop(cls, obj, context, handler, interval, timestamp, timezone)

        return _schedule

schedule = Scheduler.decorator(Scheduler.schedule_handler)
