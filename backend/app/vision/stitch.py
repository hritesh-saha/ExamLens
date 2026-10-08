"""Conservative feature-based stitching of overlapping lecture-board photos.

Pages are joined only when ORB matches plus a RANSAC homography show a real
shared board region. Uncertain pairs stay separate. No OCR is used.
"""

from pathlib import Path

import cv2
import numpy as np

from app.vision.models import CleanedPage

_MIN_KEYPOINTS = 20
_MIN_GOOD_MATCHES = 20
_MIN_INLIERS = 12
_MIN_INLIER_RATIO = 0.30
_RATIO_TEST = 0.70
_RANSAC_REPROJ = 5.0
_MAX_ROTATION_DEG = 25.0
_MIN_SCALE = 0.70
_MAX_SCALE = 1.40
_MAX_PERSPECTIVE = 0.0015
_MIN_OVERLAP = 0.15
_MAX_OVERLAP = 0.80
_MAX_CANVAS_SIDE = 4000
_MAX_CANVAS_SCALE = 3.0


def stitch_pages(pages: list[CleanedPage]) -> list[CleanedPage]:
    """Sequentially stitch overlapping pages that share a document_id.

    Empty input stays empty. A single page is returned unchanged. A failed
    pair never drops a page or deletes a file.
    """
    if not pages:
        return []
    if len(pages) == 1:
        return list(pages)

    result: list[CleanedPage] = []
    for page in pages:
        if not result:
            result.append(page)
            continue
        previous = result[-1]
        if previous.document_id != page.document_id:
            result.append(page)
            continue
        stitched = _try_stitch(previous, page)
        if stitched is None:
            result.append(page)
        else:
            result[-1] = stitched
    return result


def _try_stitch(first: CleanedPage, second: CleanedPage) -> CleanedPage | None:
    """Return a new CleanedPage if the pair overlaps geometrically, else None."""
    try:
        image_a = cv2.imread(first.image_path, cv2.IMREAD_COLOR)
        image_b = cv2.imread(second.image_path, cv2.IMREAD_COLOR)
        if image_a is None or image_b is None:
            return None
        if image_a.size == 0 or image_b.size == 0:
            return None

        homography, inliers = _estimate_homography(image_a, image_b)
        if homography is None:
            return None
        if not _transform_is_plausible(homography, image_a.shape, image_b.shape):
            return None

        panorama = _blend_panorama(image_a, image_b, homography)
        if panorama is None:
            return None

        sources = _merge_source_numbers(first.source_page_numbers, second.source_page_numbers)
        output_path = _stitched_output_path(first, sources)
        if output_path.resolve() in {
            Path(first.image_path).resolve(),
            Path(second.image_path).resolve(),
        }:
            return None
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(output_path), panorama):
            return None

        return CleanedPage(
            document_id=first.document_id,
            page_number=first.page_number,
            source_page_numbers=sources,
            doc_type="lecture_board",
            image_path=str(output_path),
            embedded_text=first.embedded_text,
            timestamp=first.timestamp,
            regions=[],
        )
    except Exception:
        return None


def _estimate_homography(
    image_a: np.ndarray, image_b: np.ndarray
) -> tuple[np.ndarray | None, int]:
    """Homography mapping image_b into image_a coordinates."""
    gray_a = cv2.cvtColor(image_a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(image_b, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(nfeatures=2000)
    keypoints_a, descriptors_a = orb.detectAndCompute(gray_a, None)
    keypoints_b, descriptors_b = orb.detectAndCompute(gray_b, None)
    if (
        descriptors_a is None
        or descriptors_b is None
        or len(keypoints_a) < _MIN_KEYPOINTS
        or len(keypoints_b) < _MIN_KEYPOINTS
    ):
        return None, 0

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    raw_matches = matcher.knnMatch(descriptors_b, descriptors_a, k=2)
    good: list[cv2.DMatch] = []
    for pair in raw_matches:
        if len(pair) < 2:
            continue
        best, second = pair
        if best.distance < _RATIO_TEST * second.distance:
            good.append(best)
    if len(good) < _MIN_GOOD_MATCHES:
        return None, 0

    source = np.float32([keypoints_b[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    destination = np.float32([keypoints_a[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    method = getattr(cv2, "USAC_MAGSAC", cv2.RANSAC)
    homography, mask = cv2.findHomography(source, destination, method, _RANSAC_REPROJ)
    if homography is None or mask is None:
        return None, 0
    inliers = int(mask.ravel().sum())
    if inliers < _MIN_INLIERS:
        return None, 0
    if inliers / len(good) < _MIN_INLIER_RATIO:
        return None, 0
    return homography, inliers


def _transform_is_plausible(
    homography: np.ndarray,
    shape_a: tuple[int, ...],
    shape_b: tuple[int, ...],
) -> bool:
    """Reject extreme scale, rotation, perspective, or tiny/huge overlap."""
    if not np.isfinite(homography).all():
        return False
    linear = homography[:2, :2]
    scale_x = float(np.hypot(linear[0, 0], linear[1, 0]))
    scale_y = float(np.hypot(linear[0, 1], linear[1, 1]))
    if scale_x < _MIN_SCALE or scale_x > _MAX_SCALE:
        return False
    if scale_y < _MIN_SCALE or scale_y > _MAX_SCALE:
        return False
    rotation = abs(np.degrees(np.arctan2(linear[1, 0], linear[0, 0])))
    if rotation > _MAX_ROTATION_DEG:
        return False
    if abs(float(homography[2, 0])) > _MAX_PERSPECTIVE:
        return False
    if abs(float(homography[2, 1])) > _MAX_PERSPECTIVE:
        return False

    height_a, width_a = shape_a[:2]
    height_b, width_b = shape_b[:2]
    overlap = _overlap_ratio(homography, width_a, height_a, width_b, height_b)
    if overlap is None or overlap < _MIN_OVERLAP or overlap > _MAX_OVERLAP:
        return False

    xmin, ymin, xmax, ymax = _canvas_bounds(homography, width_a, height_a, width_b, height_b)
    canvas_w = xmax - xmin
    canvas_h = ymax - ymin
    if canvas_w < 1 or canvas_h < 1:
        return False
    if canvas_w > _MAX_CANVAS_SIDE or canvas_h > _MAX_CANVAS_SIDE:
        return False
    if canvas_w > _MAX_CANVAS_SCALE * max(width_a, width_b):
        return False
    if canvas_h > _MAX_CANVAS_SCALE * max(height_a, height_b):
        return False
    return True


def _overlap_ratio(
    homography: np.ndarray,
    width_a: int,
    height_a: int,
    width_b: int,
    height_b: int,
) -> float | None:
    corners_b = np.float32(
        [[0, 0], [width_b, 0], [width_b, height_b], [0, height_b]]
    ).reshape(-1, 1, 2)
    warped = cv2.perspectiveTransform(corners_b, homography).reshape(-1, 2)
    x1 = max(0.0, float(warped[:, 0].min()))
    y1 = max(0.0, float(warped[:, 1].min()))
    x2 = min(float(width_a), float(warped[:, 0].max()))
    y2 = min(float(height_a), float(warped[:, 1].max()))
    if x2 <= x1 or y2 <= y1:
        return 0.0
    intersection = (x2 - x1) * (y2 - y1)
    area_a = float(width_a * height_a)
    area_b = float(width_b * height_b)
    return intersection / min(area_a, area_b)


def _canvas_bounds(
    homography: np.ndarray,
    width_a: int,
    height_a: int,
    width_b: int,
    height_b: int,
) -> tuple[int, int, int, int]:
    corners_a = np.float32(
        [[0, 0], [width_a, 0], [width_a, height_a], [0, height_a]]
    ).reshape(-1, 1, 2)
    corners_b = np.float32(
        [[0, 0], [width_b, 0], [width_b, height_b], [0, height_b]]
    ).reshape(-1, 1, 2)
    warped_b = cv2.perspectiveTransform(corners_b, homography)
    all_corners = np.concatenate([corners_a, warped_b], axis=0).reshape(-1, 2)
    xmin = int(np.floor(all_corners[:, 0].min()))
    ymin = int(np.floor(all_corners[:, 1].min()))
    xmax = int(np.ceil(all_corners[:, 0].max()))
    ymax = int(np.ceil(all_corners[:, 1].max()))
    return xmin, ymin, xmax, ymax


def _blend_panorama(
    image_a: np.ndarray, image_b: np.ndarray, homography: np.ndarray
) -> np.ndarray | None:
    height_a, width_a = image_a.shape[:2]
    height_b, width_b = image_b.shape[:2]
    xmin, ymin, xmax, ymax = _canvas_bounds(homography, width_a, height_a, width_b, height_b)
    offset_x = -xmin if xmin < 0 else 0
    offset_y = -ymin if ymin < 0 else 0
    canvas_w = xmax + offset_x
    canvas_h = ymax + offset_y
    if canvas_w < 2 or canvas_h < 2:
        return None
    if canvas_w > _MAX_CANVAS_SIDE or canvas_h > _MAX_CANVAS_SIDE:
        return None

    translate = np.array(
        [[1.0, 0.0, float(offset_x)], [0.0, 1.0, float(offset_y)], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    warp_a = translate
    warp_b = translate @ homography
    warped_a = cv2.warpPerspective(image_a, warp_a, (canvas_w, canvas_h))
    warped_b = cv2.warpPerspective(image_b, warp_b, (canvas_w, canvas_h))
    mask_a = cv2.warpPerspective(
        np.full((height_a, width_a), 255, dtype=np.uint8), warp_a, (canvas_w, canvas_h)
    )
    mask_b = cv2.warpPerspective(
        np.full((height_b, width_b), 255, dtype=np.uint8), warp_b, (canvas_w, canvas_h)
    )
    present_a = mask_a > 0
    present_b = mask_b > 0
    dist_a = cv2.distanceTransform(present_a.astype(np.uint8), cv2.DIST_L2, 3)
    dist_b = cv2.distanceTransform(present_b.astype(np.uint8), cv2.DIST_L2, 3)
    weight_a = np.zeros((canvas_h, canvas_w), dtype=np.float32)
    weight_a[present_a] = 1.0
    overlap = present_a & present_b
    weight_a[overlap] = dist_a[overlap] / (dist_a[overlap] + dist_b[overlap] + 1e-6)
    weight_a[~present_a & present_b] = 0.0
    alpha = weight_a[..., None]
    blended = warped_a.astype(np.float32) * alpha + warped_b.astype(np.float32) * (1.0 - alpha)
    return np.clip(blended, 0, 255).astype(np.uint8)


def _merge_source_numbers(first: list[int], second: list[int]) -> list[int]:
    merged: list[int] = []
    seen: set[int] = set()
    for number in [*first, *second]:
        if number not in seen:
            seen.add(number)
            merged.append(number)
    return merged


def _stitched_output_path(first: CleanedPage, sources: list[int]) -> Path:
    image_path = Path(first.image_path)
    cleaned_dir = image_path.parent
    if cleaned_dir.name == "stitched":
        stitched_dir = cleaned_dir
    else:
        stitched_dir = cleaned_dir / "stitched"
    name = "page_" + "_".join(str(number) for number in sources) + ".png"
    return stitched_dir / name
