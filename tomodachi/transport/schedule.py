import datetime
import asyncio
import time
import pytz
import tzlocal
import traceback
import inspect
import logging
from typing import Any, Dict, List, Union, Optional, Callable, Tuple, Awaitable  # noqa
from tomodachi.invoker import Invoker
from tomodachi.helpers.crontab import get_next_datetime


class Scheduler(Invoker):
    close_waiter = None

    async def schedule_handler(cls: Any, obj: Any, context: Dict, func: Any, interval: Optional[Union[str, int]]=None, timestamp: Optional[str]=None, timezone: Optional[str]=None) -> Any:
        async def handler() -> None:
            values = inspect.getfullargspec(func)
            kwargs = {k: values.defaults[i] for i, k in enumerate(values.args[len(values.args) - len(values.defaults):])} if values.defaults else {}
            try:
                routine = func(*(obj,), **kwargs)
                if isinstance(routine, Awaitable):
                    await routine
            except Exception as e:
                if not context.get('log_level') or context.get('log_level') in ['DEBUG']:
                    traceback.print_exception(e.__class__, e, e.__traceback__)

        context['_schedule_scheduled_functions'] = context.get('_schedule_scheduled_functions', [])
        context['_schedule_scheduled_functions'].append((interval, timestamp, timezone, func, handler))

        start_func = cls.start_scheduler(cls, obj, context)
        return (await start_func) if start_func else None

    @classmethod
    def schedule_handler_with_interval(cls, interval: Union[str, int]) -> Callable:
        def _func(cls: Any, obj: Any, context: Dict, func: Any) -> Any:
            return cls.schedule_handler(cls, obj, context, func, interval=interval)

        return _func

    @classmethod
    def next_call_at(cls, current_time: float, interval: Optional[Union[str, int]]=None, timestamp: Optional[str]=None, timezone: Optional[str]=None) -> int:
        if not timezone:
            tz = tzlocal.get_localzone()
        else:
            try:
                tz = pytz.timezone(timezone or '')
            except Exception as e:
                raise Exception('Unknown timezone: {}'.format(timezone)) from e
        local_tz = tzlocal.get_localzone()

        if interval is None and timestamp is not None:
            if isinstance(timestamp, str):
                try:
                    datetime_object = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                    interval = '{} {} {} {} * {}'.format(datetime_object.minute, datetime_object.hour, datetime_object.day, datetime_object.month, datetime_object.year)
                    second_modifier = 1
                    if tz.localize(datetime_object) > local_tz.localize(datetime.datetime.fromtimestamp(current_time)):
                        second_modifier = -60
                    next_at = get_next_datetime(interval, local_tz.localize(datetime.datetime.fromtimestamp(current_time + second_modifier)).astimezone(tz))
                    if not next_at:
                        return int(current_time + 60 * 60 * 24 * 365 * 100)
                    return int(next_at.timestamp() + datetime_object.second)
                except ValueError:
                    pass

                try:
                    datetime_object = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M')
                    interval = '{} {} {} {} * {}'.format(datetime_object.minute, datetime_object.hour, datetime_object.day, datetime_object.month, datetime_object.year)
                    next_at = get_next_datetime(interval, local_tz.localize(datetime.datetime.fromtimestamp(current_time + 1)).astimezone(tz))
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
                    if tz.localize(datetime_object) > local_tz.localize(datetime.datetime.fromtimestamp(current_time)):
                        second_modifier = -60
                    next_at = get_next_datetime(interval, local_tz.localize(datetime.datetime.fromtimestamp(current_time + second_modifier)).astimezone(tz))
                    if not next_at:
                        return int(current_time + 60 * 60 * 24 * 365 * 100)
                    return int(next_at.timestamp() + datetime_object.second)
                except ValueError:
                    pass

                try:
                    datetime_object = datetime.datetime.strptime(timestamp, '%H:%M')
                    interval = '{} {} * * *'.format(datetime_object.minute, datetime_object.hour)
                    next_at = get_next_datetime(interval, local_tz.localize(datetime.datetime.fromtimestamp(current_time + 1)).astimezone(tz))
                    if not next_at:
                        return int(current_time + 60 * 60 * 24 * 365 * 100)
                    return int(next_at.timestamp())
                except ValueError:
                    pass

                raise Exception('Invalid timestamp')

        if interval is not None:
            if isinstance(interval, int):
                return int(current_time + interval)

            interval_aliases = {
                ('every second', '1s', '1 s', '1second', '1 second', 'second', 'secondly', 'once per second'): 1,
                ('every minute', '1m', '1 m', '1minute', '1 minute', 'minute', 'minutely', 'once per minute'): '@minutely',
                ('every hour', '1h', '1 h', '1hour', '1 hour', 'hour', 'hourly', 'once per hour'): '@hourly',
                ('every day', '1d', '1 d', '1day', '1 day', 'day', 'daily', 'once per day', 'nightly'): '@daily',
                ('every month', '1month', '1 month', 'month', 'monthly', 'once per month'): '@monthly',
                ('every year', '1y', '1 y', '1year', '1 year', 'year', 'yearly', 'once per year', 'annually'): '@yearly',
                ('monday', 'mondays', 'mon', 'every monday', 'once per monday', 'weekly', 'once per week', 'week', 'every week'): '0 0 * * 1',
                ('tuesday', 'tuesdays', 'tue', 'every tuesday', 'once per tuesday'): '0 0 * * 2',
                ('wednesday', 'wednesdays', 'wed', 'every wednesday', 'once per wednesday'): '0 0 * * 3',
                ('thursday', 'thursdays', 'thu', 'every thursday', 'once per thursday'): '0 0 * * 4',
                ('friday', 'fridays', 'fri', 'every friday', 'once per friday'): '0 0 * * 5',
                ('saturday', 'saturdays', 'sat', 'every saturday', 'once per saturday'): '0 0 * * 6',
                ('sunday', 'sundays', 'sun', 'every sunday', 'once per sunday'): '0 0 * * 0',
                ('weekday', 'weekdays', 'every weekday'): '0 0 * * 1-5',
                ('weekend', 'weekends', 'every weekend'): '0 0 * * 0,6'
            }  # type: Dict[Tuple[str, ...], Union[str, int]]
            interval = interval.lower()

            if interval.endswith('s') or interval.endswith('seconds'):
                try:
                    interval = int(interval.replace('seconds', '').replace('s', '').replace(' ', ''))
                except ValueError:
                    pass

            try:
                interval_value = [v for k, v in interval_aliases.items() if interval in k][0]  # type: Union[str, int]
            except IndexError:
                interval_value = interval
            if isinstance(interval_value, int):
                return int(current_time + interval_value)

            try:
                next_at = get_next_datetime(interval_value, local_tz.localize(datetime.datetime.fromtimestamp(current_time + 1)).astimezone(tz))
                if not next_at:
                    return int(current_time + 60 * 60 * 24 * 365 * 100)
                return int(next_at.timestamp())
            except Exception:
                raise Exception('Invalid interval')

        return int(current_time + 60 * 60 * 24 * 365 * 100)

    def get_timezone(cls: Any, timezone: Optional[str]=None) -> Optional[str]:
        if timezone:
            tz_aliases = {
                ('+00:00', '-00:00', '00:00', '0000', 'GMT +0000', 'GMT +00:00', 'GMT -00', 'GMT +00', 'GMT -0', 'GMT +0'): 'GMT0',
                ('+01:00', '+0100', 'GMT +0100', 'GMT +01:00', 'GMT +01', 'GMT +1'): 'Etc/GMT-1',
                ('+02:00', '+0200', 'GMT +0200', 'GMT +02:00', 'GMT +02', 'GMT +2'): 'Etc/GMT-2',
                ('+03:00', '+0300', 'GMT +0300', 'GMT +03:00', 'GMT +03', 'GMT +3'): 'Etc/GMT-3',
                ('+04:00', '+0400', 'GMT +0400', 'GMT +04:00', 'GMT +04', 'GMT +4'): 'Etc/GMT-4',
                ('+05:00', '+0500', 'GMT +0500', 'GMT +05:00', 'GMT +05', 'GMT +5'): 'Etc/GMT-5',
                ('+06:00', '+0600', 'GMT +0600', 'GMT +06:00', 'GMT +06', 'GMT +6'): 'Etc/GMT-6',
                ('+07:00', '+0700', 'GMT +0700', 'GMT +07:00', 'GMT +07', 'GMT +7'): 'Etc/GMT-7',
                ('+08:00', '+0800', 'GMT +0800', 'GMT +08:00', 'GMT +08', 'GMT +8'): 'Etc/GMT-8',
                ('+09:00', '+0900', 'GMT +0900', 'GMT +09:00', 'GMT +09', 'GMT +9'): 'Etc/GMT-9',
                ('+10:00', '+1000', 'GMT +1000', 'GMT +10:00', 'GMT +10'): 'Etc/GMT-10',
                ('+11:00', '+1100', 'GMT +1100', 'GMT +11:00', 'GMT +11'): 'Etc/GMT-11',
                ('+12:00', '+1200', 'GMT +1200', 'GMT +12:00', 'GMT +12'): 'Etc/GMT-12',
                ('-01:00', '-0100', 'GMT -0100', 'GMT -01:00', 'GMT -01', 'GMT -1'): 'Etc/GMT+1',
                ('-02:00', '-0200', 'GMT -0200', 'GMT -02:00', 'GMT -02', 'GMT -2'): 'Etc/GMT+2',
                ('-03:00', '-0300', 'GMT -0300', 'GMT -03:00', 'GMT -03', 'GMT -3'): 'Etc/GMT+3',
                ('-04:00', '-0400', 'GMT -0400', 'GMT -04:00', 'GMT -04', 'GMT -4'): 'Etc/GMT+4',
                ('-05:00', '-0500', 'GMT -0500', 'GMT -05:00', 'GMT -05', 'GMT -5'): 'Etc/GMT+5',
                ('-06:00', '-0600', 'GMT -0600', 'GMT -06:00', 'GMT -06', 'GMT -6'): 'Etc/GMT+6',
                ('-07:00', '-0700', 'GMT -0700', 'GMT -07:00', 'GMT -07', 'GMT -7'): 'Etc/GMT+7',
                ('-08:00', '-0800', 'GMT -0800', 'GMT -08:00', 'GMT -08', 'GMT -8'): 'Etc/GMT+8',
                ('-09:00', '-0900', 'GMT -0900', 'GMT -09:00', 'GMT -09', 'GMT -9'): 'Etc/GMT+9',
                ('-10:00', '-1000', 'GMT -1000', 'GMT -10:00', 'GMT -10'): 'Etc/GMT+10',
                ('-11:00', '-1100', 'GMT -1100', 'GMT -11:00', 'GMT -11'): 'Etc/GMT+11',
                ('-12:00', '-1200', 'GMT -1200', 'GMT -12:00', 'GMT -12'): 'Etc/GMT+12'
            }  # type: Dict[Tuple[str, ...], str]
            try:
                try:
                    timezone = [v for k, v in tz_aliases.items() if timezone in k or timezone.replace(' ', '') in [x.replace(' ', '') for x in k]][0]
                except IndexError:
                    pass
                pytz.timezone(timezone or '')
            except Exception as e:
                raise Exception('Unknown timezone: {}'.format(timezone)) from e

        return timezone

    async def start_schedule_loop(cls: Any, obj: Any, context: Dict, handler: Callable, func: Callable, interval: Optional[Union[str, int]]=None, timestamp: Optional[str]=None, timezone: Optional[str]=None) -> None:
        timezone = cls.get_timezone(timezone)

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
            too_many_tasks = False
            while not cls.close_waiter.done():
                try:
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
                    if len(tasks) >= 20:
                        if not too_many_tasks:
                            too_many_tasks = True
                            logging.getLogger('transport.schedule').warning('Too many scheduled tasks (20) for function "{}"'.format(func.__name__))
                        await asyncio.sleep(1)
                        continue
                    too_many_tasks = False
                    tasks.append(asyncio.ensure_future(asyncio.shield(handler())))
                except Exception as e:
                    if not context.get('log_level') or context.get('log_level') in ['DEBUG']:
                        traceback.print_exception(e.__class__, e, e.__traceback__)
                    await asyncio.sleep(1)

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
            cls.close_waiter = asyncio.Future()

            for interval, timestamp, timezone, func, handler in context.get('_schedule_scheduled_functions', []):
                cls.next_call_at(time.time(), interval, timestamp, cls.get_timezone(timezone))  # test provided interval/timestamp on init

            for interval, timestamp, timezone, func, handler in context.get('_schedule_scheduled_functions', []):
                await cls.start_schedule_loop(cls, obj, context, handler, func, interval, timestamp, timezone)

        return _schedule


schedule = Scheduler.decorator(Scheduler.schedule_handler)

heartbeat = Scheduler.decorator(Scheduler.schedule_handler_with_interval(1))
every_second = Scheduler.decorator(Scheduler.schedule_handler_with_interval(1))

minutely = Scheduler.decorator(Scheduler.schedule_handler_with_interval('minutely'))
hourly = Scheduler.decorator(Scheduler.schedule_handler_with_interval('hourly'))
daily = Scheduler.decorator(Scheduler.schedule_handler_with_interval('daily'))
monthly = Scheduler.decorator(Scheduler.schedule_handler_with_interval('monthly'))
