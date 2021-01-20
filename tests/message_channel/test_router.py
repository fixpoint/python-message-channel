import asyncio

import pytest

from message_channel.router import Route, Router


@pytest.mark.asyncio
async def test_router_behavior() -> None:
    router: Router[str] = Router()

    assert len(router.routes) == 0
    assert router.distribute("hello") is False
    assert router.distribute("world") is False

    route = Route(
        messages=asyncio.Queue(),
        predicator=lambda m: m == "hello",
    )
    router.routes.append(route)
    assert router.distribute("hello") is True
    assert router.distribute("world") is False

    assert (await route.messages.get()) == "hello"
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(route.messages.get(), timeout=0.1)
    assert router.distribute("hello") is True
    assert router.distribute("hello") is True
    assert (await route.messages.get()) == "hello"
    assert (await route.messages.get()) == "hello"
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(route.messages.get(), timeout=0.1)

    router.routes.remove(route)
    assert router.distribute("hello") is False
    assert router.distribute("world") is False
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(route.messages.get(), timeout=0.1)
