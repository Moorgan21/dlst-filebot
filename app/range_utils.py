import math
from typing import Optional, Tuple


def parse_range(range_header: Optional[str], file_size: int) -> Tuple[int, int]:
    if range_header:
        range_value = range_header.strip().replace("bytes=", "")
        from_str, _, until_str = range_value.partition("-")
        from_bytes = int(from_str) if from_str else 0
        until_bytes = int(until_str) if until_str else file_size - 1
    else:
        from_bytes = 0
        until_bytes = file_size - 1

    until_bytes = min(until_bytes, file_size - 1)
    return from_bytes, until_bytes


def compute_chunk_params(from_bytes: int, until_bytes: int, chunk_size: int):
    offset = from_bytes - (from_bytes % chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = (until_bytes % chunk_size) + 1
    part_count = math.ceil(until_bytes / chunk_size) - math.floor(offset / chunk_size)
    first_chunk_index = offset // chunk_size
    return first_chunk_index, first_part_cut, last_part_cut, part_count
