"""Perspective correction for a detected lecture board.

This module only warps an image. It does not read files or talk to the API.
"""

import cv2
import numpy as np


def order_points(points: np.ndarray) -> np.ndarray:
    """Return four corners as top-left, top-right, bottom-right, bottom-left.

    The top-left point has the smallest x + y. The bottom-right point has the
    largest x + y. Of the remaining points, the top-right has the smallest
    y - x and the bottom-left has the largest y - x.
    """
    pts = np.asarray(points, dtype=np.float32).reshape(4, 2)
    ordered = np.zeros((4, 2), dtype=np.float32)
    sums = pts.sum(axis=1)
    # np.diff on [x, y] is y - x.
    diffs = np.diff(pts, axis=1).reshape(4)
    ordered[0] = pts[np.argmin(sums)]
    ordered[2] = pts[np.argmax(sums)]
    ordered[1] = pts[np.argmin(diffs)]
    ordered[3] = pts[np.argmax(diffs)]
    return ordered


def perspective_warp(
    image: np.ndarray,
    corners: np.ndarray,
    max_width: int | None = None,
    max_height: int | None = None,
) -> np.ndarray:
    """Warp the region inside ``corners`` to a top-down BGR image.

    Output width and height come from the quadrilateral's edge lengths, so a
    wide board stays wide. ``max_width`` and ``max_height`` only shrink that
    result and keep the same aspect ratio.
    """
    if image is None or not isinstance(image, np.ndarray) or image.size == 0:
        raise ValueError("image must be a non-empty array")
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("image must be a BGR image")
    if max_width is not None and max_width < 1:
        raise ValueError("max_width must be positive")
    if max_height is not None and max_height < 1:
        raise ValueError("max_height must be positive")

    ordered = order_points(_validate_corners(corners))
    width, height = _output_size(ordered, max_width, max_height)

    destination = np.array(
        [
            [0, 0],
            [width - 1, 0],
            [width - 1, height - 1],
            [0, height - 1],
        ],
        dtype=np.float32,
    )
    # Map the photographed board onto an upright rectangle.
    transform = cv2.getPerspectiveTransform(ordered, destination)
    return cv2.warpPerspective(image, transform, (width, height))


def _validate_corners(corners: np.ndarray) -> np.ndarray:
    """Require four finite points that enclose a real area."""
    if corners is None:
        raise ValueError("corners are required")
    pts = np.asarray(corners, dtype=np.float32)
    if pts.size != 8:
        raise ValueError("expected exactly 4 corner points")
    pts = pts.reshape(4, 2)
    if not np.isfinite(pts).all():
        raise ValueError("corners must be finite numbers")
    # A line or a repeated point has no area and would make the homography fail.
    if cv2.contourArea(pts) < 1.0:
        raise ValueError("corners do not form a quadrilateral with positive area")
    return pts


def _output_size(
    ordered: np.ndarray,
    max_width: int | None,
    max_height: int | None,
) -> tuple[int, int]:
    """Width and height, in pixels, of the upright board."""
    top_left, top_right, bottom_right, bottom_left = ordered
    width = max(
        np.linalg.norm(top_right - top_left),
        np.linalg.norm(bottom_right - bottom_left),
    )
    height = max(
        np.linalg.norm(bottom_left - top_left),
        np.linalg.norm(bottom_right - top_right),
    )
    width = max(int(round(float(width))), 1)
    height = max(int(round(float(height))), 1)

    if max_width is not None and width > max_width:
        scale = max_width / width
        width = max_width
        height = max(int(round(height * scale)), 1)
    if max_height is not None and height > max_height:
        scale = max_height / height
        height = max_height
        width = max(int(round(width * scale)), 1)
    return width, height
