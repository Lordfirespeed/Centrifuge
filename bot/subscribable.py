from typing import Callable, Awaitable, Any
import asyncio


class SubscribableEvent:

    __slots__ = (
        "_subscribers"
    )

    def __init__(self):
        self._subscribers = set()

    def subscribe(self, subscriber: Callable[..., Awaitable]):
        self._subscribers.add(subscriber)

    def unsubscribe(self, subscriber: Callable[..., Awaitable]):
        self._subscribers.remove(subscriber)

    async def fire(self, *args, **kwargs):
        for subscriber in self._subscribers:
            await subscriber(*args, **kwargs)
