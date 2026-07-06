import asyncio
import hashlib


class KeyedLock:
    """Fixed-size pool of locks striped by key hash, so unrelated keys don't
    serialize through one global lock, while memory stays bounded regardless
    of how many distinct keys are seen over the process lifetime."""

    def __init__(self, stripes: int = 64):
        self._locks = [asyncio.Lock() for _ in range(stripes)]

    def get(self, key) -> asyncio.Lock:
        index = int(hashlib.md5(str(key).encode()).hexdigest(), 16) % len(self._locks)
        return self._locks[index]
