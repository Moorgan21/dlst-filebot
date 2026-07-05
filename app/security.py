import hashlib
import hmac

from .config import BOT_TOKEN

_TOKEN_LENGTH = 32


def generate_token(chat_id: int, message_id: int) -> str:
    payload = f"{chat_id}:{message_id}".encode()
    return hmac.new(BOT_TOKEN.encode(), payload, hashlib.sha256).hexdigest()[:_TOKEN_LENGTH]


def verify_token(chat_id: int, message_id: int, token: str) -> bool:
    expected = generate_token(chat_id, message_id)
    return hmac.compare_digest(expected, token or "")
