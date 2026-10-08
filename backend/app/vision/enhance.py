"""Illumination normalization for a perspective-corrected lecture board.

CLAHE, background division, and adaptive thresholding are used as helpers.
The returned image stays grayscale-valued BGR so OCR and region detection
can still see writing and diagrams. It is never a binary black-and-white page.
"""

import cv2
import numpy as np


def remove_glare_and_shadows(image: np.ndarray) -> np.ndarray:
    """Even out board lighting while keeping writing and diagrams.

    Works on luminance only, then writes the result back as BGR with the
    original colour channels. Output size matches the input.
    """
    bgr = _validate_bgr(image)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    luminance = lab[:, :, 0]

    luminance = _reduce_local_glare(luminance)
    background = _estimate_illumination(luminance)
    luminance = _divide_by_background(luminance, background)
    luminance = _apply_clahe(luminance)
    luminance = _reinforce_writing(luminance)

    lab[:, :, 0] = luminance
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def _validate_bgr(image: np.ndarray) -> np.ndarray:
    """Require a non-empty 3-channel BGR image."""
    if image is None:
        raise ValueError("image must be a non-empty BGR array")
    if not isinstance(image, np.ndarray):
        raise ValueError("image must be a numpy array")
    if image.size == 0 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("image must be a non-empty BGR array with 3 channels")
    if image.shape[0] < 1 or image.shape[1] < 1:
        raise ValueError("image must be a non-empty BGR array")
    return image


def _odd_kernel(image: np.ndarray, fraction: float, minimum: int) -> int:
    """Odd window size from the shorter image side, with a safe floor."""
    shorter = min(image.shape[:2])
    size = max(int(round(shorter * fraction)), minimum)
    if size % 2 == 0:
        size += 1
    upper = shorter - 1 if shorter % 2 == 0 else shorter
    if upper < 3:
        return 3
    if upper % 2 == 0:
        upper -= 1
    return min(size, upper)


def _reduce_local_glare(luminance: np.ndarray) -> np.ndarray:
    """Soften small saturated hotspots, not the whole bright whiteboard.

    A pixel is treated as glare only when it is near saturation *and* much
    brighter than a large neighbourhood. If that mask covers too much of the
    board, it is ignored so ordinary white surface is left alone.
    Text under fully clipped glare cannot be recovered.
    """
    kernel = _odd_kernel(luminance, fraction=0.08, minimum=31)
    local = cv2.GaussianBlur(luminance, (kernel, kernel), 0)
    saturated = luminance >= 250
    much_brighter = luminance.astype(np.int16) - local.astype(np.int16) > 35
    glare = saturated & much_brighter
    if not np.any(glare) or float(glare.mean()) > 0.08:
        return luminance

    mask = glare.astype(np.uint8) * 255
    return cv2.inpaint(luminance, mask, 3, cv2.INPAINT_TELEA)


def _estimate_illumination(luminance: np.ndarray) -> np.ndarray:
    """Large-scale brightness map. Letters are too small to survive this kernel."""
    kernel_size = _odd_kernel(luminance, fraction=0.12, minimum=31)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    # Opening removes thin dark strokes, leaving the board's lighting.
    opened = cv2.morphologyEx(luminance, cv2.MORPH_OPEN, kernel)
    return cv2.GaussianBlur(opened, (kernel_size, kernel_size), 0)


def _divide_by_background(luminance: np.ndarray, background: np.ndarray) -> np.ndarray:
    """Flatten shadows and gradients by dividing out the estimated lighting."""
    bg = np.maximum(background.astype(np.float32), 1.0)
    scale = float(np.median(bg))
    normalized = luminance.astype(np.float32) / bg * scale
    return np.clip(normalized, 0, 255).astype(np.uint8)


def _apply_clahe(luminance: np.ndarray) -> np.ndarray:
    """Raise local contrast without clipping writing into solid black."""
    height, width = luminance.shape[:2]
    tile = min(8, max(2, height // 8), max(2, width // 8))
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(tile, tile))
    return clahe.apply(luminance)


def _reinforce_writing(luminance: np.ndarray) -> np.ndarray:
    """Use adaptive threshold only as a soft mask, not as the final image.

    Darker-than-neighbourhood pixels (strokes) are darkened slightly. The
    board itself stays a continuous gray so diagrams keep their shading.
    """
    block = _odd_kernel(luminance, fraction=0.05, minimum=15)
    if block < 3:
        return luminance
    writing = cv2.adaptiveThreshold(
        luminance,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        block,
        8,
    )
    weight = writing.astype(np.float32) / 255.0
    mixed = luminance.astype(np.float32) * (1.0 - 0.12 * weight)
    return np.clip(mixed, 0, 255).astype(np.uint8)
