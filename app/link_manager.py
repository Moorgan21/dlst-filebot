import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import List, Optional

from pyrogram.errors import FloodWait

from .config import BASE_URL, LINK_TTL_SECONDS, MAX_ACTIVE_LINKS
from .redis_client import client as redis_client
from .security import generate_token

logger = logging.getLogger(__name__)

_DRAIN_INTERVAL_SECONDS = 5
_NOTIFY_MAX_ATTEMPTS = 3
_NOTIFY_MAX_WAIT_SECONDS = 300

_ACTIVE_SET_KEY = "filebot:active_tokens"
_QUEUE_KEY = "filebot:queue"
_QUEUED_USERS_KEY = "filebot:queued_users"

# چک ظرفیت (MAX_ACTIVE_LINKS) و رزرو توکن باید یک عملیات اتمیک باشه؛ چون حالا
# ممکنه چند سرور جدا (چند پروسه/چند ماشین) هم‌زمان try_acquire رو صدا بزنن،
# یه asyncio.Lock تک‌پروسه‌ای دیگه کافی نیست و این چک باید خودِ Redis انجامش بده
_TRY_ACQUIRE_SCRIPT = """
local count = redis.call('SCARD', KEYS[1])
if count >= tonumber(ARGV[1]) then
    return 0
end
redis.call('SET', KEYS[2], ARGV[3], 'EX', ARGV[4])
redis.call('SADD', KEYS[1], ARGV[2])
return 1
"""


def _link_key(token: str) -> str:
    return f"filebot:link:{token}"


@dataclass
class ActiveLink:
    token: str
    owner_id: int
    chat_id: int
    message_id: int
    file_name: str
    file_size: int
    expires_at: float


@dataclass
class QueueItem:
    user_id: int
    notify_chat_id: int
    link_chat_id: int
    link_message_id: int
    file_name: str
    file_size: int


class LinkManager:
    def __init__(self):
        self._try_acquire_script = redis_client.register_script(_TRY_ACQUIRE_SCRIPT)

    async def _purge_expired(self) -> None:
        tokens = await redis_client.smembers(_ACTIVE_SET_KEY)
        if not tokens:
            return
        pipe = redis_client.pipeline()
        for token in tokens:
            pipe.exists(_link_key(token))
        exists_flags = await pipe.execute()
        stale = [token for token, exists in zip(tokens, exists_flags) if not exists]
        if stale:
            await redis_client.srem(_ACTIVE_SET_KEY, *stale)

    async def is_queued(self, user_id: int) -> bool:
        return bool(await redis_client.sismember(_QUEUED_USERS_KEY, user_id))

    async def try_acquire(
        self, owner_id: int, chat_id: int, message_id: int, file_name: str, file_size: int
    ) -> Optional[str]:
        await self._purge_expired()

        token = generate_token(chat_id, message_id)
        data = {
            "owner_id": owner_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "file_name": file_name,
            "file_size": file_size,
        }
        acquired = await self._try_acquire_script(
            keys=[_ACTIVE_SET_KEY, _link_key(token)],
            args=[MAX_ACTIVE_LINKS, token, json.dumps(data), LINK_TTL_SECONDS],
        )
        return token if acquired else None

    async def is_active(self, chat_id: int, message_id: int, token: str) -> bool:
        raw = await redis_client.get(_link_key(token))
        if not raw:
            return False
        data = json.loads(raw)
        return data["chat_id"] == chat_id and data["message_id"] == message_id

    async def active_count(self) -> int:
        await self._purge_expired()
        return await redis_client.scard(_ACTIVE_SET_KEY)

    async def list_active_for_user(self, owner_id: int) -> List[ActiveLink]:
        await self._purge_expired()
        tokens = await redis_client.smembers(_ACTIVE_SET_KEY)

        results = []
        now = time.time()
        for token in tokens:
            raw = await redis_client.get(_link_key(token))
            if not raw:
                continue
            data = json.loads(raw)
            if data["owner_id"] != owner_id:
                continue
            ttl = await redis_client.ttl(_link_key(token))
            results.append(ActiveLink(
                token=token,
                owner_id=data["owner_id"],
                chat_id=data["chat_id"],
                message_id=data["message_id"],
                file_name=data["file_name"],
                file_size=data["file_size"],
                expires_at=now + max(ttl, 0),
            ))
        return results

    async def try_enqueue(self, item: QueueItem) -> bool:
        # SADD خودش اتمیکه و برمی‌گردونه که آیا این کاربر تازه اضافه شده یا از قبل
        # عضو بوده؛ یعنی حتی اگه دو تا درخواست هم‌زمان از یه کاربر به اینجا برسن
        # (چون بین چک is_queued و اینجا چند تا await فاصله افتاده)، فقط یکیشون
        # می‌تونه واقعاً صف بشه و اون یکی دیگه False می‌گیره
        added = await redis_client.sadd(_QUEUED_USERS_KEY, item.user_id)
        if not added:
            return False
        await redis_client.rpush(_QUEUE_KEY, json.dumps(asdict(item)))
        return True

    async def run_drain_loop(self, bot) -> None:
        while True:
            await asyncio.sleep(_DRAIN_INTERVAL_SECONDS)
            try:
                await self._purge_expired()

                while True:
                    raw = await redis_client.lindex(_QUEUE_KEY, 0)
                    if raw is None:
                        break
                    item = QueueItem(**json.loads(raw))

                    token = await self.try_acquire(
                        item.user_id, item.link_chat_id, item.link_message_id, item.file_name, item.file_size
                    )
                    if token is None:
                        break

                    await redis_client.lpop(_QUEUE_KEY)
                    await redis_client.srem(_QUEUED_USERS_KEY, item.user_id)

                    link = f"{BASE_URL}/dl/{item.link_chat_id}/{item.link_message_id}?t={token}"
                    text = (
                        "✅ نوبتت شد! لینک مستقیم فایلت آماده‌ست:\n\n"
                        f"📄 نام: {item.file_name}\n"
                        f"📦 حجم: {item.file_size / (1024 * 1024):.2f} MB\n\n"
                        f"🔗 {link}\n\n"
                        f"⏱ این لینک تا {LINK_TTL_SECONDS // 60} دقیقه دیگه معتبره."
                    )
                    # fire-and-forget: یه FloodWait طولانی نباید تخلیهٔ بقیهٔ صف رو معطل کنه
                    asyncio.ensure_future(_notify_with_retry(bot, item.notify_chat_id, text))
            except Exception:
                # یه خطای گذرا (مثلاً قطعی لحظه‌ای Redis) نباید کل حلقهٔ تخلیهٔ صف
                # رو برای همیشه بکشه؛ لاگ کن و توی سیکل بعدی دوباره امتحان کن
                logger.exception("run_drain_loop iteration failed, will retry next cycle")


async def _notify_with_retry(bot, chat_id: int, text: str) -> None:
    for attempt in range(_NOTIFY_MAX_ATTEMPTS):
        try:
            await bot.send_message(chat_id, text, disable_web_page_preview=True)
            return
        except FloodWait as e:
            wait = min(e.value, _NOTIFY_MAX_WAIT_SECONDS)
            logger.warning("FloodWait %ss while notifying chat_id=%s (attempt %d)", wait, chat_id, attempt + 1)
            await asyncio.sleep(wait)
        except Exception:
            logger.exception("failed to notify queued user chat_id=%s", chat_id)
            return
    logger.error("giving up notifying chat_id=%s after %d attempts", chat_id, _NOTIFY_MAX_ATTEMPTS)


link_manager = LinkManager()
