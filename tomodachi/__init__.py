from typing import Any
from tomodachi.__version__ import __version__  # noqa

CLASS_ATTRIBUTE = 'TOMODACHI_SERVICE_CLASS'


def service(cls: Any) -> Any:
    setattr(cls, CLASS_ATTRIBUTE, True)
    return cls
