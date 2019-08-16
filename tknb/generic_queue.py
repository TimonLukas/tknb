from queue import Queue
from typing import Generic, TypeVar

T = TypeVar("T")


class GenericQueue(Queue, Generic[T]):
    def put(self, item: T, *args, **kwargs) -> None:
        super().put(item, *args, **kwargs)

    def get(self, *args, **kwargs) -> T:
        return super().get(*args, **kwargs)
