import asyncio
from typing import Iterator

import pytest

pytest_plugins = ("asyncio",)


@pytest.fixture()
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.get_event_loop()
    yield loop
    for task in asyncio.all_tasks(loop=loop):
        task.cancel()
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.stop()
    loop.run_forever()
