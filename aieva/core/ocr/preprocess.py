"""Image pre-processing for the OCR pipeline.

Only Pillow and NumPy are used - no OpenCV - so the same code runs on a weak
Android board (see ADR-003 and the Phase 11 notes).

The steps are the classic ones:

1. grayscale + autocontrast
2. deskew (the dominant ink angle is estimated and the image is rotated)
3. denoise (a 3x3 median filter)
4. adaptive threshold (local mean based)
5. auto crop (the ink bounding box)
6. upscale (small crops are enlarged so the OCR sees more pixels)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image, ImageOps

#: Below this width an image is considered "too small" for a good OCR.
MIN_WIDTH = 320


@dataclass
class PreprocessOptions:
    """Which steps of the pipeline are applied."""

    grayscale: bool = True
    autocontrast: bool = True
    deskew: bool = True
    denoise: bool = True
    threshold: bool = True
    autocrop: bool = True
    upscale: bool = True
    #: The window of the adaptive threshold in pixels.
    threshold_window: int = 25
    #: The threshold offset of the adaptive threshold.
    threshold_offset: int = 8
    #: The target width after the upscale.
    target_width: int = MIN_WIDTH
    #: Keep the colours (the LLM reads a colour image better than a binary one).
    keep_color: bool = True


def to_grayscale(image: Image.Image) -> Image.Image:
    """A grayscale copy of the image."""
    return image.convert("L")


def apply_autocontrast(image: Image.Image) -> Image.Image:
    """Stretch the contrast so faint ink becomes visible."""
    return ImageOps.autocontrast(image, cutoff=1)


def _ink_mask(gray: np.ndarray) -> np.ndarray:
    """The pixels that carry ink (dark on light)."""
    threshold = float(np.mean(gray))
    if threshold < 128:
        return gray > (255 - threshold)
    return gray < threshold


def estimate_skew(gray: np.ndarray, limit: float = 12.0) -> float:
    """Estimate the rotation of the text in degrees.

    The angle with the strongest horizontal projection profile wins - that is
    the direction in which the text rows line up.
    """
    mask = _ink_mask(gray)
    if not mask.any():
        return 0.0
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    if rows.size < 4 or cols.size < 4:
        return 0.0
    crop = mask[rows[0] : rows[-1] + 1, cols[0] : cols[-1] + 1]
    if crop.shape[0] < 4 or crop.shape[1] < 4:
        return 0.0
    best_angle = 0.0
    best_score = -1.0
    for angle in np.arange(-limit, limit + 0.1, 0.5):
        rotated = Image.fromarray((crop * 255).astype(np.uint8)).rotate(
            float(angle), resample=Image.BILINEAR, fillcolor=0
        )
        profile = np.asarray(rotated, dtype=np.float64).sum(axis=1)
        score = float(np.var(np.diff(profile)))
        if score > best_score:
            best_score = score
            best_angle = float(angle)
    return best_angle


def deskew(image: Image.Image, angle: float | None = None) -> Image.Image:
    """Rotate the image so the text is horizontal."""
    gray = np.asarray(image.convert("L"))
    if angle is None:
        angle = estimate_skew(gray)
    if abs(angle) < 0.2:
        return image
    fill = 255 if image.mode in ("L", "1") else (255, 255, 255)
    return image.rotate(angle, resample=Image.BICUBIC, fillcolor=fill)


def denoise(image: Image.Image) -> Image.Image:
    """A 3x3 median filter that removes salt and pepper noise."""
    array = np.asarray(image.convert("L"), dtype=np.int16)
    padded = np.pad(array, 1, mode="edge")
    windows = np.lib.stride_tricks.sliding_window_view(padded, (3, 3))
    median = np.median(windows.reshape(windows.shape[0], windows.shape[1], -1), axis=-1)
    return Image.fromarray(median.astype(np.uint8))


def adaptive_threshold(image: Image.Image, window: int = 25, offset: int = 8) -> Image.Image:
    """A local mean threshold - better than a global one for uneven light."""
    gray = np.asarray(image.convert("L"), dtype=np.float64)
    height, width = gray.shape
    window = max(3, int(window) | 1)
    pad = window // 2
    padded = np.pad(gray, pad, mode="edge")
    cumulative = np.cumsum(np.cumsum(padded, axis=0), axis=1)
    cumulative = np.pad(cumulative, ((1, 0), (1, 0)), mode="constant")

    def box_sum(row: int, column: int) -> np.ndarray:
        return (
            cumulative[row + window, column + window]
            - cumulative[row, column + window]
            - cumulative[row + window, column]
            + cumulative[row, column]
        )

    rows = np.arange(height)
    columns = np.arange(width)
    row_index = rows[:, None]
    column_index = columns[None, :]
    local_mean = box_sum(row_index, column_index) / float(window * window)
    binary = (gray < local_mean - offset) * 255
    return Image.fromarray(binary.astype(np.uint8))


def autocrop(image: Image.Image, margin: int = 8) -> Image.Image:
    """Cut the image down to the ink."""
    gray = np.asarray(image.convert("L"))
    mask = _ink_mask(gray)
    if not mask.any():
        return image
    rows = np.where(mask.any(axis=1))[0]
    columns = np.where(mask.any(axis=0))[0]
    top = max(int(rows[0]) - margin, 0)
    bottom = min(int(rows[-1]) + margin + 1, gray.shape[0])
    left = max(int(columns[0]) - margin, 0)
    right = min(int(columns[-1]) + margin + 1, gray.shape[1])
    if bottom - top < 4 or right - left < 4:
        return image
    return image.crop((left, top, right, bottom))


def upscale(image: Image.Image, target_width: int = MIN_WIDTH) -> Image.Image:
    """Enlarge a small image so the OCR has more pixels to work with."""
    width, height = image.size
    if width >= target_width or width == 0:
        return image
    factor = target_width / float(width)
    new_size = (target_width, max(1, int(height * factor)))
    return image.resize(new_size, Image.LANCZOS)


def preprocess(image: Image.Image, options: PreprocessOptions | None = None) -> Image.Image:
    """Run the whole pre-processing chain."""
    options = options or PreprocessOptions()
    result = image.convert("RGB")
    if options.grayscale:
        result = to_grayscale(result)
    if options.autocontrast:
        result = apply_autocontrast(result)
    if options.deskew:
        result = deskew(result)
    if options.denoise:
        result = denoise(result)
    if options.threshold:
        binary = adaptive_threshold(result, options.threshold_window, options.threshold_offset)
        if options.keep_color:
            # keep the original colours, but use the binary mask for the ink
            ink = np.asarray(binary) < 128
            coloured = np.asarray(image.convert("RGB")).copy()
            coloured[ink] = (0, 0, 0)
            result = Image.fromarray(coloured)
        else:
            result = binary
    if options.autocrop:
        result = autocrop(result)
    if options.upscale:
        result = upscale(result, options.target_width)
    return result


def image_hash(image: Image.Image) -> str:
    """A stable hash of the image content (used for the OCR cache)."""
    import hashlib

    grayscale = image.convert("L").resize((64, 64))
    return hashlib.sha256(grayscale.tobytes()).hexdigest()


def describe(image: Image.Image) -> dict[str, Any]:
    """A short description of an image (used in the logs and in the UI)."""
    return {
        "size": list(image.size),
        "mode": image.mode,
        "hash": image_hash(image),
    }


__all__ = [
    "MIN_WIDTH",
    "PreprocessOptions",
    "adaptive_threshold",
    "autocrop",
    "apply_autocontrast",
    "denoise",
    "describe",
    "deskew",
    "estimate_skew",
    "image_hash",
    "preprocess",
    "to_grayscale",
    "upscale",
]
