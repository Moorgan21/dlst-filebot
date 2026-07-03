import os

from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

PORT = int(os.environ.get("PORT", 8080))
BIND_ADDRESS = os.environ.get("BIND_ADDRESS", "0.0.0.0")
BASE_URL = os.environ.get("BASE_URL", f"http://127.0.0.1:{PORT}").rstrip("/")

_log_channel = os.environ.get("LOG_CHANNEL", "").strip()
LOG_CHANNEL = int(_log_channel) if _log_channel else None

_admin_id = os.environ.get("ADMIN_ID", "").strip()
ADMIN_ID = int(_admin_id) if _admin_id else None

# اندازه هر بخش (chunk) که تلگرام برای دانلود فایل استفاده می‌کند
CHUNK_SIZE = 1024 * 1024
