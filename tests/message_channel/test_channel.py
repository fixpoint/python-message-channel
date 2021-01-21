import asyncio

import pytest

from message_channel import exceptions
from message_channel.channel import Channel


@pytest.fixture
async def queue() -> asyncio.Queue[str]:
    return asyncio.Queue()


@pytest.fixture
async def channel(queue) -> Channel[str]:
    async with Channel(queue.get, queue.put) as channel:
        yield channel


@pytest.mark.asyncio
async def test_channel_recv_raise_exception_on_closed_channel(queue) -> None:
    channel = Channel(queue.get)

    with pytest.raises(exceptions.ChannelClosedError):
        await channel.recv()


@pytest.mark.asyncio
async def test_channel_recv_does_not_raise_exception_on_closed_channel_with_residual_messages(
    queue,
) -> None:
    channel = Channel(queue.get)
    channel.open()
    queue.put_nowait("hello")
    queue.put_nowait("world")
    queue.put_nowait("hello")
    queue.put_nowait("world")
    queue.put_nowait("hello")
    queue.put_nowait("world")
    await asyncio.sleep(1)
    await channel.close()

    # channel.recv() receives residual messages
    assert (await channel.recv()) == "hello"
    assert (await channel.recv()) == "world"
    assert (await channel.recv()) == "hello"
    assert (await channel.recv()) == "world"
    assert (await channel.recv()) == "hello"
    assert (await channel.recv()) == "world"

    # channel.recv() raise exception while there is no residual message
    with pytest.raises(exceptions.ChannelClosedError):
        await channel.recv()


@pytest.mark.asyncio
async def test_channel_receive_messages_from_reader_and_wait(queue, channel) -> None:
    queue.put_nowait("hello")
    queue.put_nowait("world")
    queue.put_nowait("hello")
    queue.put_nowait("world")
    queue.put_nowait("hello")
    queue.put_nowait("world")
    # channel.recv() receives messages
    assert (await channel.recv()) == "hello"
    assert (await channel.recv()) == "world"
    assert (await channel.recv()) == "hello"
    assert (await channel.recv()) == "world"
    assert (await channel.recv()) == "hello"
    assert (await channel.recv()) == "world"
    # recv() waits next message
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(channel.recv(), timeout=0.1)

    queue.put_nowait("hello")
    queue.put_nowait("world")
    assert (await channel.recv()) == "hello"
    assert (await channel.recv()) == "world"


@pytest.mark.asyncio
async def test_channel_split_create_a_subchannel(queue, channel) -> None:
    sub = channel.split(lambda m: m == "hello")
    queue.put_nowait("hello")
    queue.put_nowait("world")
    # Open subchannel
    sub.open()
    queue.put_nowait("hello")
    queue.put_nowait("world")
    queue.put_nowait("hello")
    queue.put_nowait("world")
    # sub.recv() receives predicted messages
    assert (await sub.recv()) == "hello"
    assert (await sub.recv()) == "hello"
    assert (await sub.recv()) == "hello"
    # channel.recv() receives residual messages
    assert (await channel.recv()) == "world"
    assert (await channel.recv()) == "world"
    assert (await channel.recv()) == "world"
    # sub.recv() waits next message
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(sub.recv(), timeout=0.1)
    # channel.recv() waits next message
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(channel.recv(), timeout=0.1)
    queue.put_nowait("hello")
    queue.put_nowait("world")
    assert (await sub.recv()) == "hello"
    assert (await channel.recv()) == "world"

    # Close subchannel
    await sub.close()
    queue.put_nowait("hello")
    queue.put_nowait("world")
    with pytest.raises(exceptions.ChannelClosedError):
        await sub.recv()
    assert (await channel.recv()) == "hello"
    assert (await channel.recv()) == "world"


@pytest.mark.asyncio
async def test_channel_split_create_a_subchannel_context(queue, channel) -> None:
    queue.put_nowait("hello")
    queue.put_nowait("world")
    async with channel.split(lambda m: m == "hello") as sub:
        queue.put_nowait("hello")
        queue.put_nowait("world")
        queue.put_nowait("hello")
        queue.put_nowait("world")
        # sub.recv() receives predicted messages
        assert (await sub.recv()) == "hello"
        assert (await sub.recv()) == "hello"
        assert (await sub.recv()) == "hello"
        # channel.recv() receives residual messages
        assert (await channel.recv()) == "world"
        assert (await channel.recv()) == "world"
        assert (await channel.recv()) == "world"
        # sub.recv() waits next message
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sub.recv(), timeout=0.1)
        # channel.recv() waits next message
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(channel.recv(), timeout=0.1)

        queue.put_nowait("hello")
        queue.put_nowait("world")
        assert (await sub.recv()) == "hello"
        assert (await channel.recv()) == "world"

    queue.put_nowait("hello")
    queue.put_nowait("world")
    assert (await channel.recv()) == "hello"
    assert (await channel.recv()) == "world"


@pytest.mark.asyncio
async def test_channel_send(queue, channel) -> None:
    await channel.send("hello")
    await channel.send("world")
    assert (await channel.recv()) == "hello"
    assert (await channel.recv()) == "world"


@pytest.mark.asyncio
async def test_channel_send_from_subchannel(queue, channel) -> None:
    async with channel.split(lambda m: m == "hello") as sub:
        await sub.send("hello")
        await sub.send("world")
        assert (await sub.recv()) == "hello"
        assert (await channel.recv()) == "world"
