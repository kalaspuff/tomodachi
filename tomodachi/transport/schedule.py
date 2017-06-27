import datetime
from typing import Any, Dict, List, Union, Optional, Callable, Awaitable
from tomodachi.invoker import Invoker


class Scheduler(Invoker):
    async def schedule_handler(cls: Any, obj: Any, context: Dict, func: Callable, interval: Optional[Union[str, int]]=None, timestamp: Optional[Union[str, List[Union[str, datetime.datetime]], datetime.datetime]]=None) -> Callable:
        async def schedule_loop() -> None:
            kwargs = {k: None for k in func.__code__.co_varnames[1:] if k != 'self'}  # type: Any

            routine = func(*(obj,), **kwargs)
            try:
                if isinstance(routine, Awaitable):
                    await routine
            except Exception as e:
                pass

        async def start_schedule_loop() -> None:
            if context.get('_schedule_loop_started'):
                return None
            context['_schedule_loop_started'] = True

        return start_schedule_loop

schedule = Scheduler.decorator(Scheduler.schedule_handler)
