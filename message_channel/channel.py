import asyncio
from asyncio import Event, Queue, Task
from contextlib import suppress
from typing import Any, Awaitable, Callable, Generic, Optional, TypeVar

from .router import Predicator, Route, Router

T = TypeVar("T")

Reader = Callable[[], Awaitable[T]]


class _ClosedError(Exception):
    pass


class Channel(Generic[T]):
    """Channel distribute messages into sub-channels and itself"""

    _router: Router[T]
    _messages: Queue[T]
    _consumer: Optional[Task[None]]

    def __init__(self, reader: Reader[T]) -> None:
        self._reader = reader
        self._closed = Event()
        self._router = Router()
        self._messages = Queue()
        self._consumer = None

    async def __aenter__(self) -> "Channel[T]":
        self.open()
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        await self.close()

    def open(self) -> None:
        """Open the channel"""
        if self._consumer:
            raise AttributeError("channel is already opened")
        self._consumer = asyncio.create_task(self._start_consumer())

    async def _waiter(self) -> None:
        await self._closed.wait()
        raise _ClosedError()

    async def _start_consumer(self) -> None:
        waiter = self._waiter
        reader = self._reader
        router = self._router
        messages = self._messages

        with suppress(_ClosedError):
            while True:
                m = await _race(reader(), waiter())
                if router.distribute(m):
                    continue
                # The message is not distributed so put in this channel
                messages.put_nowait(m)

    async def recv(self) -> T:
        """Receive a message which is not distributed to subchannels"""
        if self._consumer is None:
            raise AttributeError("channel is not opened")
        return await self._messages.get()

    async def close(self) -> None:
        """Close the channel"""
        if self._consumer is None:
            raise AttributeError("channel is not opened")
        self._closed.set()
        await self._consumer
        self._consumer = None

    def split(self, predicator: Predicator[T]) -> "Subchannel[T]":
        """Split the channel by the predicator and return subchannel"""
        if self._router is None:
            raise AttributeError("channel is not opened")

        return Subchannel(self, predicator)


class Subchannel(Channel[T]):
    _route: Route[T]
    _parent: Channel[T]

    def __init__(self, parent: Channel[T], predicator: Predicator[T]) -> None:
        self._route = Route(messages=Queue(), predicator=predicator)
        self._parent = parent
        super().__init__(self._route.messages.get)

    def open(self) -> None:
        super().open()
        self._parent._router.routes.append(self._route)

    async def close(self) -> None:
        self._parent._router.routes.remove(self._route)
        await super().close()


async def _race(*fs: Awaitable[Any]) -> Any:
    return await next(iter(asyncio.as_completed(fs)))
