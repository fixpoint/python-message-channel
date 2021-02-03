import asyncio
from asyncio import Event, Future, Queue, Task
from functools import partial
from logging import getLogger
from typing import Any, Awaitable, Callable, Generic, Optional, TypeVar, Union

from . import exceptions
from .router import Predicator, Route, Router

T = TypeVar("T")

Reader = Callable[[], Awaitable[T]]
Writer = Callable[[T], Awaitable[None]]

logger = getLogger(__name__)


class Channel(Generic[T]):
    """Channel distribute messages into sub-channels and itself"""

    _router: Router[T]
    _messages: Queue[T]
    _listener: Optional[Task[None]]

    def __init__(self, reader: Reader[T], writer: Optional[Writer[T]] = None) -> None:
        self._reader = reader
        self._writer = writer
        self._closed = Event()
        self._router = Router()
        self._messages = Queue()
        self._listener = None

    async def __aenter__(self) -> "Channel[T]":
        self.open()
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        await self.close()

    def open(self) -> None:
        """Open the channel"""
        if self._listener:
            raise exceptions.ChannelAlreadyOpenedError("the channel is already opened")
        self._listener = asyncio.create_task(self._start_listener())

    async def _start_listener(self) -> None:
        async def waiter_handler() -> None:
            await self._closed.wait()

        async def consumer_handler() -> None:
            router = self._router
            messages = self._messages

            while True:
                logger.debug(f"Receive message [pre ] ({id(self)})")
                m = await self._reader()
                logger.debug(f"Receive message [post] ({id(self)}): {str(m)}")
                if router.distribute(m):
                    logger.debug(f"The message is distributed ({id(self)})")
                    continue
                logger.debug(f"The message is queued ({id(self)})")
                # The message is not distributed so put in this channel
                messages.put_nowait(m)

        logger.debug(f"Open listener ({id(self)})")
        waiter = asyncio.create_task(waiter_handler())
        consumer = asyncio.create_task(consumer_handler())
        done, pending = await asyncio.wait(
            [waiter, consumer],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        for task in done:
            task.result()
        logger.debug(f"Close listener ({id(self)})")

    async def recv(self) -> T:
        """Receive a message which is not distributed to subchannels

        It raises ChannelClosedError when the channel is closed and no
        residual messages exist in the internal message queue.
        """
        if self._listener is None and self._messages.empty():
            raise exceptions.ChannelClosedError(
                "the channel is closed and no residual message exist"
            )

        loop = asyncio.get_event_loop()
        waiter: Future[T] = loop.create_future()

        def _release_waiter(f: Union[Future[T], Future[None]]) -> None:
            if waiter.done():
                return
            elif (exc := f.exception()) :
                waiter.set_exception(exc)
            elif (res := f.result()) :
                waiter.set_result(res)
            else:
                waiter.set_exception(
                    exceptions.ChannelClosedError("the channel is closed")
                )

        if self._listener:
            self._listener.add_done_callback(_release_waiter)
            waiter.add_done_callback(
                partial(self._listener.remove_done_callback, _release_waiter)
            )

        getter = asyncio.create_task(self._messages.get())
        getter.add_done_callback(_release_waiter)
        try:
            return await waiter
        finally:
            getter.cancel()

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
        if self._listener is None:
            raise exceptions.ChannelClosedError("the channel is already closed")
        self._closed.set()
        await self._listener
        self._listener = None

    def split(self, predicator: Predicator[T]) -> "Subchannel[T]":
        """Split the channel by the predicator and return subchannel"""
        if self._listener is None:
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
