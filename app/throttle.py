import asyncio
import logging
import time

from .config import TOTAL_SERVER_BYTES_PER_SECOND
from .link_manager import link_manager
from .redis_client import client as redis_client

logger = logging.getLogger(__name__)

_ACTIVE_COUNT_REFRESH_SECONDS = 2

# مدت زمانی که وضعیت pacing هر توکن روی ردیس زنده می‌مونه اگه استفاده نشه؛ چون
# خودِ EXPIRE پاک‌سازی خودکار انجام می‌ده، دیگه نیازی به یه حلقه‌ی cleanup جدا نیست
_STALE_AFTER_SECONDS = 3600

# منطق pacing (GCRA-ساده) روی خودِ Redis اجرا می‌شه، نه توی حافظه‌ی پروسه؛ چون
# با چند سرور استریم جدا (چند پروسه/چند ماشین)، اگه اتصالات یه توکن واحد بین
# چند سرور تقسیم بشه، هر سرور باید از همون بودجه‌ی مشترکِ آن توکن کم کنه، نه
# اینکه هرکدوم مستقل حساب کنن و اون لینک عملاً چند برابر سهمیه‌ش بگیره
_WAIT_FOR_SLOT_SCRIPT = """
local next_time = tonumber(redis.call('HGET', KEYS[1], 'next_time') or ARGV[1])
local start = math.max(next_time, tonumber(ARGV[1]))
local new_next = start + (tonumber(ARGV[3]) / tonumber(ARGV[2]))
redis.call('HSET', KEYS[1], 'next_time', new_next)
redis.call('EXPIRE', KEYS[1], ARGV[4])
return tostring(start - tonumber(ARGV[1]))
"""


def _throttle_key(token: str) -> str:
    return f"filebot:throttle:{token}"


class SharedTokenThrottle:
    """Caps aggregate throughput per token (not per connection), and the per-token
    share is recomputed continuously as TOTAL_SERVER_BYTES_PER_SECOND divided by
    however many links are currently active — fewer active links means each one
    gets more bandwidth, more active links means each one gets less, down to the
    floor of TOTAL/MAX_ACTIVE_LINKS once the link cap is full. Each link's share
    is fixed regardless of how many IPs (or how many separate stream servers)
    use it; pacing state lives in Redis so concurrent connections to the same
    token — even from different servers — contend for that one token's shared
    budget, never drawing from other links' shares."""

    def __init__(self, total_bytes_per_second: float):
        self._total_rate = total_bytes_per_second
        self._active_count = 1
        self._wait_for_slot_script = redis_client.register_script(_WAIT_FOR_SLOT_SCRIPT)

    def _current_rate_per_link(self) -> float:
        return self._total_rate / max(self._active_count, 1)

    async def wait_for_slot(self, token: str, num_bytes: int) -> None:
        now = time.time()
        rate = self._current_rate_per_link()
        wait = float(await self._wait_for_slot_script(
            keys=[_throttle_key(token)],
            args=[now, rate, num_bytes, _STALE_AFTER_SECONDS],
        ))
        if wait > 0:
            await asyncio.sleep(wait)

    async def run_active_count_refresh_loop(self) -> None:
        while True:
            try:
                self._active_count = max(await link_manager.active_count(), 1)
            except Exception:
                logger.exception("failed to refresh active link count for throttle")
            await asyncio.sleep(_ACTIVE_COUNT_REFRESH_SECONDS)


shared_throttle = SharedTokenThrottle(TOTAL_SERVER_BYTES_PER_SECOND)
