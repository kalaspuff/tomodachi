import datetime
import asyncio
import time
from typing import Any, Dict, List, Union, Optional, Callable, Awaitable
from tomodachi.invoker import Invoker


class Scheduler(Invoker):
    close_waiter = None

    async def schedule_handler(cls: Any, obj: Any, context: Dict, func: Callable, interval: Optional[Union[str, int]]=None, timestamp: Optional[Union[str, List[Union[str, datetime.datetime]], datetime.datetime]]=None, timezone: Optional[str]=None) -> Callable:
        async def handler() -> None:
            kwargs = {k: None for k in func.__code__.co_varnames[1:] if k != 'self'}  # type: Any

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
    def next_call_at(cls, current_time: float, interval: Optional[Union[str, int]]=None, timestamp: Optional[Union[str, List[Union[str, datetime.datetime]], datetime.datetime]]=None, timezone: Optional[str]=None) -> int:
        if interval is not None:
            if isinstance(interval, int):
                return int(current_time + interval)
            if interval in ('every second', '1s', '1 s', '1second', '1 second', 'second', 'secondly', 'once per second'):
                return int(current_time + 1)
            if interval in ('every minute', '1m', '1 m', '1minute', '1 minute', 'minute', 'minutely', 'once per minute'):
                return int(current_time + 60 - (int(current_time + 60) % 60))
            if interval in ('every hour', '1h', '1 h', '1hour', '1 hour', 'hour', 'hourly', 'once per hour'):
                return int(current_time + 3600 - (int(current_time + 3600) % 3600))
        return int(current_time + 3600)

    async def start_schedule_loop(cls: Any, obj: Any, context: Dict, handler: Callable, interval: Optional[Union[str, int]]=None, timestamp: Optional[Union[str, List[Union[str, datetime.datetime]], datetime.datetime]]=None, timezone: Optional[str]=None) -> None:
        if not cls.close_waiter:
            cls.close_waiter = asyncio.Future()
        stop_waiter = asyncio.Future()  # type: asyncio.Future
        start_waiter = asyncio.Future()  # type: asyncio.Future

        async def schedule_loop() -> None:
            await start_waiter
            next_call_at = None
            tasks = []  # type: List
            current_time = time.time()
            while not cls.close_waiter.done():
                last_time = current_time
                actual_time = time.time()
                current_time = last_time + 1 if int(last_time + 1) < int(actual_time) else actual_time
                if next_call_at is None:
                    next_call_at = cls.next_call_at(current_time, interval, timestamp, timezone)
                sleep_diff = int(current_time + 1) - actual_time + 0.001
                if sleep_diff > 0:
                    await asyncio.sleep(sleep_diff)
                if next_call_at > time.time():
                    continue
                if cls.close_waiter.done():
                    continue
                next_call_at = None
                tasks = [task for task in tasks if not task.done()]
                tasks.append(asyncio.ensure_future(asyncio.shield(handler())))

            if tasks:
                await asyncio.wait(tasks)
            if not stop_waiter.done():
                stop_waiter.set_result(None)

        loop = asyncio.get_event_loop()  # type: Any

        try:
            stop_method = getattr(obj, '_stop_service')
        except AttributeError as e:
            stop_method = None
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

        try:
            started_method = getattr(obj, '_started_service')
        except AttributeError as e:
            started_method = None
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
