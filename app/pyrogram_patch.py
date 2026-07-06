import pyrogram.utils

# Pyrogram 2.0.106 hardcodes the pre-2024 channel-ID range. Telegram has since
# widened the ID space, so channels/supergroups created more recently get IDs
# below this library's MIN_CHANNEL_ID and get rejected as "Peer id invalid"
# even though they're valid. Widen the bound to match Telegram's current range.
pyrogram.utils.MIN_CHANNEL_ID = -1997852516352
