import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

STATS_FILE = Path(__file__).resolve().parent.parent / "stats.json"

_total_bytes = 0


def _load():
    global _total_bytes
    try:
        data = json.loads(STATS_FILE.read_text())
        _total_bytes = int(data.get("total_bytes", 0))
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        _total_bytes = 0


def save():
    try:
        STATS_FILE.write_text(json.dumps({"total_bytes": _total_bytes}))
    except OSError:
        logger.exception("failed to persist traffic stats")


def add_bytes(n: int) -> None:
    global _total_bytes
    _total_bytes += n


def get_total_bytes() -> int:
    return _total_bytes


_load()
