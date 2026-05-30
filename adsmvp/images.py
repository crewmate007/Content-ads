"""Ad image generation.

`images.py` is the SINGLE image-backend boundary — swapping Imagen for another
provider touches only this file. With a Gemini key we call Imagen via
google-genai; without one (offline/stub) we write a deterministic solid-color
placeholder PNG using stdlib only (no Pillow dependency), so the whole pipeline
runs end-to-end with zero credentials.

Policy: prompts are editorial/illustrative. Never depict betting slips, money,
odds, or casino imagery (enforced in the prompt builder in creative.py).
"""
from __future__ import annotations

import hashlib
import struct
import sys
import zlib
from pathlib import Path
from typing import Optional


def _solid_png(path: Path, rgb=(20, 30, 48), width: int = 16, height: int = 16) -> None:
    """Write a minimal valid PNG of a solid color using only stdlib."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    raw = bytearray()
    row = bytes(rgb) * width
    for _ in range(height):
        raw.append(0)            # filter type 0 (none)
        raw.extend(row)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    path.write_bytes(png)


def _color_from_seed(seed: str) -> tuple:
    h = hashlib.sha256(seed.encode("utf-8")).digest()
    # Keep it dark/editorial: bias toward low-luminance brand-ish tones.
    return (30 + h[0] % 60, 30 + h[1] % 60, 50 + h[2] % 90)


def generate_image(prompt: str, out_path: Path, *, client=None, model: str = "",
                   seed: str = "") -> Optional[Path]:
    """Generate an image for `prompt` at `out_path`. Returns the path or None.

    Falls back to a deterministic placeholder PNG when no client/model is given
    or when the Imagen call fails — the pipeline must never break on imagery.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if client is not None and model:
        try:
            from google.genai import types as genai_types  # lazy
            resp = client.models.generate_images(
                model=model,
                prompt=prompt,
                config=genai_types.GenerateImagesConfig(
                    number_of_images=1, aspect_ratio="1:1"),
            )
            img = resp.generated_images[0].image
            data = getattr(img, "image_bytes", None)
            if data:
                out_path.write_bytes(data)
                return out_path
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] Imagen failed ({type(exc).__name__}: {exc}); "
                  "writing placeholder", file=sys.stderr)

    _solid_png(out_path, rgb=_color_from_seed(seed or prompt))
    return out_path
