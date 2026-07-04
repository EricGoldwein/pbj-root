"""Small bounded in-memory caches (LRU by insertion order)."""

from __future__ import annotations

from collections import OrderedDict
from threading import Lock
from typing import Generic, TypeVar

K = TypeVar('K')
V = TypeVar('V')


class BoundedDictCache(Generic[K, V]):
    """Thread-safe dict cache with max entry count; evicts oldest on overflow."""

    __slots__ = ('_max', '_data', '_lock')

    def __init__(self, maxsize: int) -> None:
        self._max = max(1, int(maxsize))
        self._data: OrderedDict[K, V] = OrderedDict()
        self._lock = Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def get(self, key: K, default: V | None = None) -> V | None:
        with self._lock:
            if key not in self._data:
                return default
            self._data.move_to_end(key)
            return self._data[key]

    def __contains__(self, key: object) -> bool:
        with self._lock:
            return key in self._data

    def set(self, key: K, value: V) -> None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = value
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def items_snapshot(self) -> list[tuple[K, V]]:
        with self._lock:
            return list(self._data.items())
