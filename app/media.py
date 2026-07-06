import mimetypes

from pyrogram.types import Message, Photo, Sticker, VideoNote, Voice

MEDIA_ATTRS = ("document", "video", "audio", "voice", "video_note", "animation", "photo", "sticker")

DEFAULT_MIME = "application/octet-stream"


def get_media(message: Message):
    for attr in MEDIA_ATTRS:
        media = getattr(message, attr, None)
        if media:
            return media
    return None


def resolve_file_name_and_mime(media):
    file_name = getattr(media, "file_name", None)
    mime_type = getattr(media, "mime_type", None)

    if isinstance(media, Photo):
        return file_name or "photo.jpg", "image/jpeg"

    if isinstance(media, Voice):
        return file_name or "voice.ogg", mime_type or "audio/ogg"

    if isinstance(media, VideoNote):
        return file_name or "video_note.mp4", mime_type or "video/mp4"

    if isinstance(media, Sticker):
        if media.is_video:
            return file_name or "sticker.webm", mime_type or "video/webm"
        if media.is_animated:
            return file_name or "sticker.tgs", mime_type or "application/x-tgsticker"
        return file_name or "sticker.webp", mime_type or "image/webp"

    # document / video / audio / animation
    if not file_name and mime_type:
        guessed_ext = mimetypes.guess_extension(mime_type)
        file_name = f"file{guessed_ext}" if guessed_ext else None

    file_name = file_name or "file"
    mime_type = mime_type or mimetypes.guess_type(file_name)[0] or DEFAULT_MIME
    return file_name, mime_type
