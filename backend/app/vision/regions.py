"""Visual region segmentation for a cleaned lecture-board image.

This stage does not read text, recognise equations, or run OCR. It groups
ink strokes into boxes and labels each box text, diagram, or equation using
shape and layout only. Ambiguous boxes are labelled text.
"""

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.vision.models import Region


def segment_regions(
    image: np.ndarray,
    page_id: str,
    output_dir: str | Path | None = None,
) -> list[Region]:
    """Return reading-order regions on a cleaned BGR page.

    Coordinates are pixels on ``image``, origin at the top-left. ``image`` is
    not modified. Diagram and equation crops are written under
    ``output_dir/crops/`` when ``output_dir`` is set.
    """
    bgr = _as_bgr(image)
    if bgr is None:
        return []

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    ink = _ink_mask(gray)
    if cv2.countNonZero(ink) == 0:
        return []

    raw_boxes = _component_boxes(ink, min_area=_min_stroke_area(gray))
    block_mask = _close_into_lines(ink, gray.shape)
    block_boxes = _component_boxes(block_mask, min_area=_min_block_area(gray))
    blocks = _merge_nearby(block_boxes, gray.shape)
    blocks = _drop_page_border_and_slivers(blocks, gray.shape, ink, raw_boxes)
    blocks.sort(key=lambda box: (box.y, box.x))

    regions: list[Region] = []
    for index, box in enumerate(blocks, start=1):
        region_id = f"r{index:03d}"
        strokes = [raw for raw in raw_boxes if _centroid_in(raw, box)]
        region_type = _classify(box, strokes, gray.shape, ink)
        crop_path = None
        if output_dir is not None and region_type in {"diagram", "equation"}:
            crop_path = _write_crop(bgr, box, page_id, region_id, output_dir)
        regions.append(
            Region(
                region_id=region_id,
                region_type=region_type,
                x=box.x,
                y=box.y,
                width=box.w,
                height=box.h,
                crop_path=crop_path,
            )
        )
    return regions


@dataclass
class _Box:
    x: int
    y: int
    w: int
    h: int

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2.0

    @property
    def cy(self) -> float:
        return self.y + self.h / 2.0

    @property
    def area(self) -> int:
        return self.w * self.h


def _as_bgr(image: np.ndarray) -> np.ndarray | None:
    if image is None or not isinstance(image, np.ndarray) or image.size == 0:
        return None
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.ndim == 3 and image.shape[2] == 3:
        return image
    return None


def _odd(value: int) -> int:
    value = max(3, value)
    return value if value % 2 == 1 else value + 1


def _ink_mask(gray: np.ndarray) -> np.ndarray:
    """Foreground strokes without a fixed brightness cutoff."""
    block = _odd(max(15, min(gray.shape[:2]) // 25))
    dark_on_light = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, block, 8
    )
    light_on_dark = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, 8
    )
    _otsu_thresh, otsu = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    chosen = _pick_mask([dark_on_light, light_on_dark, otsu])
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    return cv2.morphologyEx(chosen, cv2.MORPH_OPEN, kernel)


def _pick_mask(candidates: list[np.ndarray]) -> np.ndarray:
    """Prefer a mask whose ink coverage looks like writing, not noise or fill."""
    scored: list[tuple[float, np.ndarray]] = []
    for mask in candidates:
        ratio = cv2.countNonZero(mask) / mask.size
        if 0.002 <= ratio <= 0.40:
            scored.append((abs(ratio - 0.07), mask))
    if not scored:
        return np.zeros_like(candidates[0])
    return min(scored, key=lambda item: item[0])[1]


def _close_into_lines(ink: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Join neighbouring letters into lines, then nearby lines into a block."""
    height, width = shape[:2]
    kx = _odd(max(3, int(0.028 * width)))
    ky = _odd(max(3, int(0.010 * height)))
    closed = cv2.morphologyEx(
        ink, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (kx, ky))
    )
    # Tall enough to join a text line with the line below, not with a distant figure.
    ky2 = _odd(max(3, int(0.12 * height)))
    return cv2.morphologyEx(
        closed, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (3, ky2))
    )


def _min_stroke_area(gray: np.ndarray) -> int:
    # Keep tiny operators such as "=", "+", "-".
    return max(6, int(0.00002 * gray.size))


def _min_block_area(gray: np.ndarray) -> int:
    return max(18, int(0.00008 * gray.size))


def _component_boxes(mask: np.ndarray, min_area: int) -> list[_Box]:
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    boxes: list[_Box] = []
    for i in range(1, count):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area < min_area:
            continue
        boxes.append(
            _Box(
                x=int(stats[i, cv2.CC_STAT_LEFT]),
                y=int(stats[i, cv2.CC_STAT_TOP]),
                w=int(stats[i, cv2.CC_STAT_WIDTH]),
                h=int(stats[i, cv2.CC_STAT_HEIGHT]),
            )
        )
    return boxes


def _merge_nearby(boxes: list[_Box], shape: tuple[int, int]) -> list[_Box]:
    if not boxes:
        return []
    height, width = shape[:2]
    parent = list(range(len(boxes)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    for i, a in enumerate(boxes):
        for j, b in enumerate(boxes):
            if j <= i:
                continue
            if _should_merge(a, b, width, height):
                union(i, j)

    groups: dict[int, list[_Box]] = {}
    for i, box in enumerate(boxes):
        groups.setdefault(find(i), []).append(box)
    return [_union_boxes(group, width, height) for group in groups.values()]


def _should_merge(a: _Box, b: _Box, width: int, height: int) -> bool:
    if _iou(a, b) >= 0.35 or _contains(a, b) or _contains(b, a):
        return True
    gap_x = max(0, max(a.x, b.x) - min(a.x2, b.x2))
    gap_y = max(0, max(a.y, b.y) - min(a.y2, b.y2))
    x_overlap = min(a.x2, b.x2) - max(a.x, b.x)
    same_line = gap_y <= max(a.h, b.h) * 0.55
    close_x = gap_x <= max(0.045 * width, 0.9 * max(a.h, b.h))
    if same_line and close_x and (x_overlap > 0 or gap_x <= 0.045 * width):
        return True
    stacked = x_overlap > 0.25 * min(a.w, b.w)
    close_y = gap_y <= max(1.8 * max(a.h, b.h), 0.12 * height)
    return stacked and close_y


def _iou(a: _Box, b: _Box) -> float:
    x1 = max(a.x, b.x)
    y1 = max(a.y, b.y)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    union = a.area + b.area - inter
    return inter / union if union else 0.0


def _contains(outer: _Box, inner: _Box) -> bool:
    return (
        inner.x >= outer.x
        and inner.y >= outer.y
        and inner.x2 <= outer.x2
        and inner.y2 <= outer.y2
    )


def _union_boxes(boxes: list[_Box], width: int, height: int) -> _Box:
    x1 = max(0, min(box.x for box in boxes))
    y1 = max(0, min(box.y for box in boxes))
    x2 = min(width, max(box.x2 for box in boxes))
    y2 = min(height, max(box.y2 for box in boxes))
    return _Box(x=x1, y=y1, w=max(1, x2 - x1), h=max(1, y2 - y1))


def _drop_page_border_and_slivers(
    boxes: list[_Box],
    shape: tuple[int, int],
    ink: np.ndarray,
    raw_boxes: list[_Box],
) -> list[_Box]:
    height, width = shape[:2]
    kept: list[_Box] = []
    for box in boxes:
        if box.w < 3 or box.h < 3:
            continue
        if box.area > 0.92 * width * height:
            continue
        roi = ink[box.y:box.y2, box.x:box.x2]
        fill = cv2.countNonZero(roi) / max(roi.size, 1)
        touches_border = (
            box.x <= 2
            or box.y <= 2
            or box.x2 >= width - 2
            or box.y2 >= height - 2
        )
        # Warp leaves dark corners; those are not board content.
        if touches_border and fill > 0.35:
            continue
        strokes = [raw for raw in raw_boxes if _centroid_in(raw, box)]
        aspect = box.w / max(box.h, 1)
        # One isolated underline/stroke is not a useful text block.
        if len(strokes) <= 1 and aspect > 8 and box.h < 0.09 * height:
            continue
        kept.append(box)
    return kept


def _centroid_in(inner: _Box, outer: _Box) -> bool:
    return outer.x <= inner.cx <= outer.x2 and outer.y <= inner.cy <= outer.y2


def _classify(
    box: _Box,
    strokes: list[_Box],
    shape: tuple[int, int],
    ink: np.ndarray,
) -> str:
    """Visual labels only. Prefer text when diagram/equation evidence is weak."""
    roi = ink[box.y:box.y2, box.x:box.x2]
    if _looks_like_diagram(box, roi, shape):
        return "diagram"
    if _looks_like_equation(box, strokes, shape):
        return "equation"
    return "text"


def _looks_like_diagram(box: _Box, roi: np.ndarray, shape: tuple[int, int]) -> bool:
    height, width = shape[:2]
    if roi.size == 0:
        return False
    aspect = box.w / max(box.h, 1)
    fill = cv2.countNonZero(roi) / roi.size
    large_2d = box.w > 0.18 * width and box.h > 0.18 * height
    roughly_square = 0.35 <= aspect <= 2.6

    contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    closed_quads = 0
    for contour in contours:
        area = cv2.contourArea(contour)
        # Tiny boxes (letters, fraction terms) are not diagrams.
        if area < max(200, 0.12 * box.area):
            continue
        approx = cv2.approxPolyDP(contour, 0.04 * cv2.arcLength(contour, True), True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            closed_quads += 1

    if closed_quads >= 1 and box.w > 0.12 * width and box.h > 0.12 * height:
        return True
    if large_2d and roughly_square and fill < 0.28:
        return True
    return False


def _looks_like_equation(box: _Box, strokes: list[_Box], shape: tuple[int, int]) -> bool:
    height, width = shape[:2]
    if len(strokes) < 3:
        return False
    # Long, short bands are ordinary written lines, not formulas.
    if box.w > 0.65 * width and box.h < 0.10 * height:
        return False
    compact = box.w < 0.60 * width and box.h < 0.40 * height
    if not compact:
        return False

    heights = sorted(stroke.h for stroke in strokes)
    median_h = heights[len(heights) // 2]
    raised_small = 0
    for stroke in strokes:
        above = stroke.cy < box.y + 0.42 * box.h
        if stroke.h < 0.75 * median_h and above:
            raised_small += 1

    has_bar = False
    for stroke in strokes:
        if stroke.h == 0:
            continue
        aspect = stroke.w / stroke.h
        near_mid = abs(stroke.cy - (box.y + box.h / 2)) < 0.28 * box.h
        if aspect >= 5 and stroke.h < 0.30 * box.h and near_mid:
            has_bar = True
            break

    if has_bar and len(strokes) >= 3:
        return True
    if raised_small >= 2 and len(strokes) >= 4:
        return True
    if len(strokes) >= 6 and box.w / max(box.h, 1) < 5.5:
        return True
    return False


def _write_crop(
    image: np.ndarray,
    box: _Box,
    page_id: str,
    region_id: str,
    output_dir: str | Path,
) -> str | None:
    crops_dir = Path(output_dir) / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)
    path = crops_dir / f"{page_id}_{region_id}.png"
    crop = np.ascontiguousarray(image[box.y:box.y2, box.x:box.x2])
    if crop.size == 0:
        return None
    if not cv2.imwrite(str(path), crop):
        return None
    return str(path)
