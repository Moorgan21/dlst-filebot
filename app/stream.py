import logging
import mimetypes
import urllib.parse

from aiohttp import web
from pyrogram.errors import RPCError

from . import stats
from .config import CHUNK_SIZE
from .range_utils import parse_range, compute_chunk_params

logger = logging.getLogger(__name__)
routes = web.RouteTableDef()


def _get_media(message):
    for attr in ("document", "video", "audio", "voice", "video_note", "animation", "photo"):
        media = getattr(message, attr, None)
        if media:
            return media
    return None


async def _resolve(request: web.Request):
    client = request.app["bot"]
    try:
        chat_id = int(request.match_info["chat_id"])
        message_id = int(request.match_info["message_id"])
    except ValueError:
        raise web.HTTPBadRequest(text="لینک نامعتبر است")

    try:
        message = await client.get_messages(chat_id, message_id)
    except RPCError:
        raise web.HTTPNotFound(text="فایل پیدا نشد")

    if message is None or message.empty:
        raise web.HTTPNotFound(text="فایل پیدا نشد")

    media = _get_media(message)
    if not media:
        raise web.HTTPNotFound(text="پیام موردنظر فایلی ندارد")

    return client, message, media


def _headers_for(media, from_bytes, until_bytes, file_size, is_range):
    file_name = getattr(media, "file_name", None) or "file"
    mime_type = getattr(media, "mime_type", None) or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    quoted_name = urllib.parse.quote(file_name)

    headers = {
        "Content-Type": mime_type,
        "Content-Length": str(until_bytes - from_bytes + 1),
        "Accept-Ranges": "bytes",
        "Content-Disposition": f"inline; filename*=UTF-8''{quoted_name}",
    }
    if is_range:
        headers["Content-Range"] = f"bytes {from_bytes}-{until_bytes}/{file_size}"
    return headers


@routes.head("/dl/{chat_id}/{message_id}")
async def stream_head(request: web.Request):
    _, _, media = await _resolve(request)
    file_size = media.file_size
    from_bytes, until_bytes = parse_range(request.headers.get("Range"), file_size)
    headers = _headers_for(media, from_bytes, until_bytes, file_size, bool(request.headers.get("Range")))
    status = 206 if request.headers.get("Range") else 200
    return web.Response(status=status, headers=headers)


@routes.get("/dl/{chat_id}/{message_id}", allow_head=False)
async def stream_get(request: web.Request):
    client, message, media = await _resolve(request)
    file_size = media.file_size

    range_header = request.headers.get("Range")
    from_bytes, until_bytes = parse_range(range_header, file_size)

    if from_bytes < 0 or until_bytes >= file_size or from_bytes > until_bytes:
        raise web.HTTPRequestRangeNotSatisfiable()

    first_chunk_index, first_cut, last_cut, part_count = compute_chunk_params(
        from_bytes, until_bytes, CHUNK_SIZE
    )

    headers = _headers_for(media, from_bytes, until_bytes, file_size, bool(range_header))
    status = 206 if range_header else 200

    response = web.StreamResponse(status=status, headers=headers)
    await response.prepare(request)

    current_part = 0
    async for chunk in client.stream_media(message, offset=first_chunk_index, limit=part_count):
        current_part += 1
        if part_count == 1:
            chunk = chunk[first_cut:last_cut]
        elif current_part == 1:
            chunk = chunk[first_cut:]
        elif current_part == part_count:
            chunk = chunk[:last_cut]

        try:
            await response.write(chunk)
        except (ConnectionResetError, BrokenPipeError):
            break
        else:
            stats.add_bytes(len(chunk))

    await response.write_eof()
    return response
