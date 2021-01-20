from asyncio import Queue
from dataclasses import dataclass
from typing import Generic, List, TypeVar

T = TypeVar("T")


class Predicator(Generic[T]):
    """Predicator"""

    def __call__(self, message: T) -> bool:
        """Return True if the message is predicated"""
        ...


@dataclass(frozen=True)
class Route(Generic[T]):
    """Route which combine predicator and predicated messages"""

    messages: Queue[T]
    predicator: Predicator[T]


class Router(Generic[T]):
    """Router distribute messages to registered routes by predicators"""

    routes: List[Route[T]]

    def __init__(self) -> None:
        self.routes = []

    def distribute(self, message: T) -> bool:
        """Distribute message to routes"""
        for route in self.routes:
            if route.predicator(message):
                route.messages.put_nowait(message)
                return True
        return False
