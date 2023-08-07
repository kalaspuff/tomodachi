from typing import List, Optional, Tuple, Union


def add_exception_cause(
    exc: BaseException, ignored_modules: Optional[Union[List[str], Tuple[str, ...]]] = None
) -> None:
    if not exc or not isinstance(exc, BaseException):
        return

    if not ignored_modules:
        return

    if getattr(exc, "__cause__", None):
        return

    frames = []
    tb_back = None
    tb = exc.__traceback__
    while tb:
        module_name = tb.tb_frame.f_globals.get("__name__", "")
        frames.append((tb, module_name))
        if module_name not in ignored_modules:
            tb_back = tb
        tb = tb.tb_next

    if not tb_back:
        return

    for tb, module_name in reversed(frames):
        if tb_back:
            if tb is not tb_back:
                continue
            tb_back = None

        if not tb.tb_next:
            continue

        if module_name in ignored_modules:
            exc.__cause__ = exc.with_traceback(tb.tb_next)
            break
