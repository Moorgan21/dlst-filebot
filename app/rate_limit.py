import time
import uuid

from .config import FILE_RATE_WINDOW_SECONDS, MAX_FILES_PER_WINDOW
from .keyed_lock import KeyedLock
from .redis_client import client as redis_client


class SlidingWindowRateLimiter:
    def __init__(self, key_prefix: str, limit: int, window_seconds: float):
        self._key_prefix = key_prefix
        self._limit = limit
        self._window = window_seconds
        self._locks = KeyedLock()

    def _key(self, user_id: int) -> str:
        return f"filebot:rate:{self._key_prefix}:{user_id}"

    async def allow(self, user_id: int) -> bool:
        key = self._key(user_id)
        async with self._locks.get(user_id):
            now = time.time()
            await redis_client.zremrangebyscore(key, 0, now - self._window)
            count = await redis_client.zcard(key)
            if count >= self._limit:
                return False

            # عضو باید یکتا باشه نه فقط امتیاز؛ استفاده از خودِ زمان به‌عنوان عضو
            # اگه دو تا hit دقیقاً روی یه timestamp بیفتن، یکی رو جای دیگری بازنویسی
            # می‌کنه و شمارش رو کم می‌کنه، پس یه شناسهٔ یکتا (uuid) به‌عنوان عضو
            # و خودِ زمان به‌عنوان امتیاز استفاده می‌شه
            pipe = redis_client.pipeline()
            pipe.zadd(key, {str(uuid.uuid4()): now})
            pipe.expire(key, int(self._window))
            await pipe.execute()
            return True


file_rate_limiter = SlidingWindowRateLimiter("file", MAX_FILES_PER_WINDOW, FILE_RATE_WINDOW_SECONDS)
