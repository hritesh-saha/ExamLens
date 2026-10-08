"""Detect the lecture board as one quadrilateral in a photo.

The board is the large four-sided outline inside the photo. The photo's own
border is never accepted as the board.
"""

import cv2
import numpy as np

from app.vision.warp import order_points

# A real board fills a meaningful part of the photo, but not the whole frame.
_MIN_AREA_RATIO = 0.12
_MAX_AREA_RATIO = 0.92
# Corners this close to every image edge are the picture border, not a board.
_BORDER_TOLERANCE_RATIO = 0.02
# approxPolyDP tightness: fraction of the contour perimeter.
_APPROX_EPSILON_RATIO = 0.02


def detect_board_quadrilateral(image: np.ndarray) -> np.ndarray | None:
    """Return four board corners, or None when no reliable board is found.

    The returned array has shape (4, 2) and is ordered top-left, top-right,
    bottom-right, bottom-left. Coordinates are pixels on ``image``.
    This function does not read or write files. A missing board is not an error.
    """
    gray = _to_grayscale(image)
    if gray is None:
        return None

    height, width = gray.shape[:2]
    # Blur removes speckle so Canny follows the board edge instead of noise.
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    # Close small gaps so the four sides become one contour.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(width * height)
    best_points: np.ndarray | None = None
    best_area = 0.0

    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < _MIN_AREA_RATIO * image_area or area > _MAX_AREA_RATIO * image_area:
            continue
        perimeter = cv2.arcLength(contour, True)
        # Reduce the contour to a polygon. A board should simplify to 4 corners.
        approx = cv2.approxPolyDP(contour, _APPROX_EPSILON_RATIO * perimeter, True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        points = approx.reshape(4, 2).astype(np.float32)
        if _is_image_border(points, width, height):
            continue
        if not _has_reasonable_geometry(points):
            continue
        if area > best_area:
            best_area = area
            best_points = points

    if best_points is None:
        return None
    return order_points(best_points)


def _to_grayscale(image: np.ndarray) -> np.ndarray | None:
    """Return a grayscale view, or None when the array is not a usable image."""
    if image is None or not isinstance(image, np.ndarray) or image.size == 0:
        return None
    if image.ndim == 2:
        return image
    if image.ndim == 3 and image.shape[2] == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return None


def _is_image_border(points: np.ndarray, width: int, height: int) -> bool:
    """True when the quad is essentially the outer edge of the photo."""
    tolerance_x = max(3.0, width * _BORDER_TOLERANCE_RATIO)
    tolerance_y = max(3.0, height * _BORDER_TOLERANCE_RATIO)
    min_x = float(points[:, 0].min())
    min_y = float(points[:, 1].min())
    max_x = float(points[:, 0].max())
    max_y = float(points[:, 1].max())
    return (
        min_x <= tolerance_x
        and min_y <= tolerance_y
        and max_x >= width - 1 - tolerance_x
        and max_y >= height - 1 - tolerance_y
    )


def _has_reasonable_geometry(points: np.ndarray) -> bool:
    """Reject tiny, extremely thin, or collapsed quadrilaterals."""
    ordered = order_points(points)
    top_left, top_right, bottom_right, bottom_left = ordered
    width = max(
        float(np.linalg.norm(top_right - top_left)),
        float(np.linalg.norm(bottom_right - bottom_left)),
    )
    height = max(
        float(np.linalg.norm(bottom_left - top_left)),
        float(np.linalg.norm(bottom_right - top_right)),
    )
    if width < 30 or height < 30:
        return False
    ratio = width / height
    if ratio < 0.2 or ratio > 5.0:
        return False
    area = float(cv2.contourArea(ordered))
    # A usable board still covers a good share of its own bounding rectangle.
    return area >= 0.35 * width * height
