from __future__ import annotations

import struct
import zlib


def _chunk(kind: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def synthetic_damage_image() -> bytes:
    """Build a deterministic raster illustration with a visible door scrape."""
    width, height = 512, 320
    rows = bytearray()

    for y in range(height):
        rows.append(0)
        for x in range(width):
            if 35 <= x <= 476 and 38 <= y <= 278:
                shade = max(0, min(24, (y - 38) // 10))
                color = (176 - shade, 190 - shade, 199 - shade)
            else:
                color = (224, 231, 234)

            if 35 <= x <= 476 and (y == 37 or y == 279 or x in (34, 477)):
                color = (70, 82, 88)
            if 246 <= x <= 250 and 48 <= y <= 275:
                color = (108, 121, 128)
            if 336 <= x <= 395 and 78 <= y <= 91:
                color = (64, 77, 83) if y in (78, 91) or x in (336, 395) else (112, 126, 133)

            # Two contrasting, irregular marks make the synthetic scrape visible.
            scrape_y = 164 + (x - 200) * 0.23
            if 198 <= x <= 316 and abs(y - scrape_y) <= 2:
                color = (64, 55, 51)
            elif 205 <= x <= 309 and abs(y - (scrape_y - 4)) <= 1:
                color = (235, 236, 230)
            elif 224 <= x <= 282 and abs(y - (scrape_y + 5)) <= 1:
                color = (122, 99, 87)

            rows.extend(color)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(
        b"IDAT", zlib.compress(bytes(rows), level=9)
    ) + _chunk(b"IEND", b"")
