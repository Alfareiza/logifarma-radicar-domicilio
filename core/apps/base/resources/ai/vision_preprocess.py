"""Resize / normalize raster images before sending to Claude vision endpoints."""

from __future__ import annotations

import io
import logging

from PIL import Image, ImageOps

log = logging.getLogger(__name__)

# Anthropic rejects images whose width or height exceeds this (vision API).
_ANTHROPIC_MAX_IMAGE_EDGE_PX = 8000


def _normalize_image_media_type(mt: str) -> str:
    """
    Map MIME types from Drive or headers to types accepted by Claude image blocks.

    Unknown or unsupported types fall back to ``image/jpeg``.
    """
    allowed = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
    media = (mt or '').split(';')[0].strip().lower()
    if media == 'image/jpg':
        media = 'image/jpeg'
    if media in allowed:
        return media
    return 'image/jpeg'


def prepare_image_bytes_for_anthropic_vision(
    image_bytes: bytes, media_type: str
) -> tuple[bytes, str]:
    """
    Ensure image respects Anthropic's max edge length (currently 8000 px).

    If Pillow cannot decode, returns the original payload.
    """
    mt_out = _normalize_image_media_type(media_type)
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img.load()
            img = ImageOps.exif_transpose(img)
            w, h = img.size
            longest = max(w, h)
            if longest <= _ANTHROPIC_MAX_IMAGE_EDGE_PX:
                return image_bytes, mt_out

            scale = _ANTHROPIC_MAX_IMAGE_EDGE_PX / float(longest)
            new_w = max(1, int(round(w * scale)))
            new_h = max(1, int(round(h * scale)))
            resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            if resized.mode in ('RGBA', 'LA'):
                rgb = Image.new('RGB', resized.size, (255, 255, 255))
                rgb.paste(resized, mask=resized.split()[-1])
                resized = rgb
            elif resized.mode == 'P' and 'transparency' in resized.info:
                rgba = resized.convert('RGBA')
                rgb = Image.new('RGB', rgba.size, (255, 255, 255))
                rgb.paste(rgba, mask=rgba.split()[-1])
                resized = rgb
            elif resized.mode != 'RGB':
                resized = resized.convert('RGB')

            buf = io.BytesIO()
            resized.save(buf, format='JPEG', quality=92, optimize=True)
            out = buf.getvalue()
            log.info(
                'Downscaled OCR image before API: %sx%s → %sx%s JPEG',
                w,
                h,
                new_w,
                new_h,
            )
            return out, 'image/jpeg'

    except Exception:
        log.exception('Could not preprocess image bytes; sending original.')
        return image_bytes, mt_out
