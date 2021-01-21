import asyncio

import pytest

from message_channel.channel import Channel
from message_channel import exceptions


@pytest.fixture
async def queue() -> asyncio.Queue[str]:
    return asyncio.Queue()


@pytest.fixture
async def channel(queue) -> Channel[str]:
    async with Channel(queue.get) as channel:
        yield channel


@pytest.mark.asyncio
async def test_channel_behavior(queue, channel) -> None:
    queue.put_nowait("hello")
    queue.put_nowait("world")
    queue.put_nowait("hello")
    queue.put_nowait("world")
    queue.put_nowait("hello")
    queue.put_nowait("world")
    assert (await channel.recv()) == "hello"
    assert (await channel.recv()) == "world"
    assert (await channel.recv()) == "hello"
    assert (await channel.recv()) == "world"
    assert (await channel.recv()) == "hello"
    assert (await channel.recv()) == "world"

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(channel.recv(), timeout=0.1)

    async with channel.split(lambda m: m == "hello") as sub:
        queue.put_nowait("hello")
        queue.put_nowait("world")
        queue.put_nowait("hello")
        queue.put_nowait("world")
        queue.put_nowait("hello")
        queue.put_nowait("world")

        assert (await sub.recv()) == "hello"
        assert (await sub.recv()) == "hello"
        assert (await sub.recv()) == "hello"
        assert (await channel.recv()) == "world"
        assert (await channel.recv()) == "world"
        assert (await channel.recv()) == "world"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sub.recv(), timeout=0.1)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(channel.recv(), timeout=0.1)

    queue.put_nowait("hello")
    queue.put_nowait("world")
    queue.put_nowait("hello")
    queue.put_nowait("world")
    queue.put_nowait("hello")
    queue.put_nowait("world")
    assert (await channel.recv()) == "hello"
    assert (await channel.recv()) == "world"
    assert (await channel.recv()) == "hello"
    assert (await channel.recv()) == "world"
    assert (await channel.recv()) == "hello"
    assert (await channel.recv()) == "world"

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(channel.recv(), timeout=0.1)

    sub = channel.split(lambda m: m == "hello")
    queue.put_nowait("hello")
    queue.put_nowait("world")
    queue.put_nowait("hello")
    queue.put_nowait("world")
    queue.put_nowait("hello")
    queue.put_nowait("world")

    with pytest.raises(exceptions.ChannelClosedError):
        await asyncio.wait_for(sub.recv(), timeout=0.1)
    assert (await channel.recv()) == "hello"
    assert (await channel.recv()) == "world"
    assert (await channel.recv()) == "hello"
    assert (await channel.recv()) == "world"
    assert (await channel.recv()) == "hello"
    assert (await channel.recv()) == "world"

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(channel.recv(), timeout=0.1)

    sub.open()
    queue.put_nowait("hello")
    queue.put_nowait("world")
    queue.put_nowait("hello")
    queue.put_nowait("world")
    queue.put_nowait("hello")
    queue.put_nowait("world")

    assert (await sub.recv()) == "hello"
    assert (await sub.recv()) == "hello"
    assert (await sub.recv()) == "hello"
    assert (await channel.recv()) == "world"
    assert (await channel.recv()) == "world"
    assert (await channel.recv()) == "world"

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(sub.recv(), timeout=0.1)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(channel.recv(), timeout=0.1)
    sub.close()
