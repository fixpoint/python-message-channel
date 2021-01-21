import asyncio
from asyncio import Event, Queue, Task
from contextlib import suppress
from typing import Any, Awaitable, Callable, Generic, Optional, TypeVar

from . import exceptions
from .router import Predicator, Route, Router

T = TypeVar("T")

Reader = Callable[[], Awaitable[T]]
Writer = Callable[[T], Awaitable[None]]


class Channel(Generic[T]):
    """Channel distribute messages into sub-channels and itself"""

    _router: Router[T]
    _messages: Queue[T]
    _consumer: Optional[Task[None]]

    def __init__(self, reader: Reader[T], writer: Optional[Writer[T]] = None) -> None:
        self._reader = reader
        self._writer = writer
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
            raise exceptions.ChannelAlreadyOpenedError("the channel is already opened")
        self._consumer = asyncio.create_task(self._start_consumer())

    async def _waiter(self) -> None:
        await self._closed.wait()
        raise exceptions.ChannelClosedError()

    async def _start_consumer(self) -> None:
        waiter = self._waiter
        reader = self._reader
        router = self._router
        messages = self._messages

        with suppress(exceptions.ChannelClosedError):
            while True:
                m = await _race(reader(), waiter())
                if router.distribute(m):
                    continue
                # The message is not distributed so put in this channel
                messages.put_nowait(m)

    async def recv(self) -> T:
        """Receive a message which is not distributed to subchannels

        It raises ChannelClosedError when the channel is closed and no
        residual messages exist in the internal message queue.
        """
        if self._consumer is None and self._messages.empty():
            raise exceptions.ChannelClosedError(
                "the channel is closed and no residual message exist"
            )
        return await self._messages.get()

    async def send(self, message: T) -> None:
        """Send a message through the writer

        It raises ChannelNoWriterError when no writer had specified to
        the channel constructor.
        """
        if self._writer is None:
            raise exceptions.ChannelNoWriterError("the channel does not have writer")
        await self._writer(message)

    async def close(self) -> None:
        """Close the channel"""
        if self._consumer is None:
            raise exceptions.ChannelClosedError("the channel is already closed")
        self._closed.set()
        await self._consumer
        self._consumer = None

    def split(self, predicator: Predicator[T]) -> "Subchannel[T]":
        """Split the channel by the predicator and return subchannel"""
        if self._consumer is None:
            raise exceptions.ChannelClosedError("the channel is not opened yet")
        return Subchannel(self, predicator)


class Subchannel(Channel[T]):
    _route: Route[T]
    _parent: Channel[T]

    def __init__(self, parent: Channel[T], predicator: Predicator[T]) -> None:
        self._route = Route(messages=Queue(), predicator=predicator)
        self._parent = parent
        super().__init__(self._route.messages.get, self._parent._writer)

    def open(self) -> None:
        super().open()
        self._parent._router.routes.append(self._route)

    async def close(self) -> None:
        self._parent._router.routes.remove(self._route)
        await super().close()


async def _race(*fs: Awaitable[Any]) -> Any:
    return await next(iter(asyncio.as_completed(fs)))
