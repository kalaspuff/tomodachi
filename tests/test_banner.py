import asyncio
from typing import Any

import pytest

from tomodachi.helpers.banner import render_banner

try:
    import uvloop  # noqa  # isort:skip

    uvloop_installed = True
except Exception:  # pragma: no cover
    uvloop_installed = False


def test_banner_output(capsys: Any) -> None:
    render_banner(service_files=[], use_execution_context=False)

    out, err = capsys.readouterr()
    assert "event loop             ⇢ asyncio" in out


@pytest.mark.skipif(
    not uvloop_installed,
    reason="uvloop is not installed",
)
def test_banner_output_uvloop(capsys: Any) -> None:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

    render_banner(service_files=[], loop=loop, use_execution_context=False)

    out, err = capsys.readouterr()
    assert f"event loop             ⇢ uvloop (version: {str(uvloop.__version__)}" in out
