"""Utilities for sorting labelme-style JSON files inside AnyLabeling."""

import json
import math
import os
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple


SORTABLE_SHAPE_TYPES = {"rectangle", "rotation"}


def is_sortable_shape(shape: dict) -> bool:
    """Return whether a shape participates in label sorting."""
    return shape.get("shape_type") in SORTABLE_SHAPE_TYPES


@dataclass
class LineGuide:
    """Represents a user-defined ordering guide line."""

    # Normalised coordinates relative to image width/height (0.0-1.0)
    start: Tuple[float, float]
    end: Tuple[float, float]
    rect: Tuple[float, float, float, float]  # x, y, width, height (normalised)
    order: Optional[int] = None
    # Normalized freehand path used by path reorder.
    path: List[Tuple[float, float]] = field(default_factory=list)


@dataclass
class SortOptions:
    """Configuration for sorting label entries in a JSON annotation file."""

    exception_label: Optional[str] = None
    prioritize_exception_label: bool = True  # True -> excluded labels stay ahead of others
    spatial_mode: str = "REV_X"
    line_guides: List[LineGuide] = field(default_factory=list)
    exclude_labels: List[str] = field(default_factory=list)
    priority_labels: List[str] = field(default_factory=list)
    horizontal_scan_distance: float = 12.0
    vertical_scan_distance: float = 12.0

    def normalized_exclude_labels(self) -> List[str]:
        labels: List[str] = []
        if self.exception_label:
            labels.append(self.exception_label)
        labels.extend(self.exclude_labels)
        normalized: List[str] = []
        for label in labels:
            if not label:
                continue
            clean = label.strip()
            if not clean:
                continue
            if clean not in normalized:
                normalized.append(clean)
        return normalized


@dataclass
class SortOutcome:
    file_path: str
    success: bool
    changed: bool
    message: str


SPATIAL_MODE_DESCRIPTIONS = {
    "LEFT_TO_RIGHT": "Sort horizontally from left to right",
    "RIGHT_TO_LEFT": "Sort horizontally from right to left",
    "X_THEN_Y": "Sort by X ascending, then Y ascending",
    "Y_THEN_X": "Sort by Y ascending, then X ascending",
    "LINE_GUIDES": "Follow custom line guides",
}


def available_spatial_modes() -> List[str]:
    return list(SPATIAL_MODE_DESCRIPTIONS.keys())


def _get_top_left(points: Sequence[Sequence[float]]) -> Tuple[float, float]:
    if not points:
        return 0.0, 0.0
    try:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
    except (TypeError, IndexError):
        return 0.0, 0.0
    return min(xs), min(ys)


def _get_center(points: Sequence[Sequence[float]]) -> Tuple[float, float]:
    if not points:
        return 0.0, 0.0
    try:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
    except (TypeError, IndexError):
        return 0.0, 0.0
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _spatial_key(mode: str, x_min: float, y_min: float) -> Tuple[float, float]:
    """
    计算空间排序键值
    注意：这里实现的是日漫阅读习惯的排序
    """
    normalized = (mode or "NONE").upper()

    # 暂时保持原有简单逻辑，后面会用新的日漫排序算法替换
    if normalized == "X_THEN_Y":
        return x_min, y_min
    if normalized == "Y_THEN_X":
        return y_min, x_min
    if normalized == "X":
        return x_min, 0.0
    if normalized == "Y":
        return y_min, 0.0
    if normalized == "NONE":
        return 0.0, 0.0
    if normalized == "LINE_GUIDES":
        return 0.0, 0.0
    raise ValueError(f"Unsupported spatial sort mode: {mode}")


def _shape_sort_entry(shape: dict, index: int) -> dict:
    points = shape.get("points") or []
    if not points:
        return {
            "shape": shape, "index": index, "left": 0.0, "right": 0.0,
            "top": 0.0, "bottom": 0.0, "cx": 0.0, "cy": 0.0,
            "width": 1.0, "height": 1.0,
        }
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    left, right = min(xs), max(xs)
    top, bottom = min(ys), max(ys)
    return {
        "shape": shape,
        "index": index,
        "left": left,
        "right": right,
        "top": top,
        "bottom": bottom,
        "cx": (left + right) / 2.0,
        "cy": (top + bottom) / 2.0,
        "width": max(right - left, 1.0),
        "height": max(bottom - top, 1.0),
    }


def _interval_overlap_ratio(a_low, a_high, b_low, b_high) -> float:
    overlap = min(a_high, b_high) - max(a_low, b_low)
    if overlap <= 0.0:
        return 0.0
    return overlap / max(min(a_high - a_low, b_high - b_low), 1.0)


def _cluster_entries(entries, axis: str, distance: Optional[float] = None):
    """Build stable visual rows or columns without joining distant objects."""
    if not entries:
        return []

    if axis == "row":
        low_key, high_key, center_key, size_key = "top", "bottom", "cy", "height"
        pending = sorted(entries, key=lambda e: (e["top"], e["cy"], e["left"], e["index"]))
    else:
        low_key, high_key, center_key, size_key = "left", "right", "cx", "width"
        pending = sorted(entries, key=lambda e: (-e["right"], -e["cx"], e["top"], e["index"]))

    groups = []
    for entry in pending:
        best_group = None
        best_score = float("-inf")
        for group in groups:
            overlap = _interval_overlap_ratio(
                entry[low_key], entry[high_key], group["low"], group["high"]
            )
            center_gap = abs(entry[center_key] - group["center"])
            scale = max(entry[size_key], group["average_size"], 1.0)

            # Require real interval overlap, or very close centers. This avoids
            # a tall object bridging several unrelated rows/columns.
            allowed_gap = max(scale * 0.45, float(distance or 0.0))
            if overlap < 0.25 and center_gap > allowed_gap:
                continue
            score = overlap * 2.0 - center_gap / scale
            if score > best_score:
                best_score = score
                best_group = group

        if best_group is None:
            groups.append({
                "items": [entry],
                "low": entry[low_key],
                "high": entry[high_key],
                "center": entry[center_key],
                "average_size": entry[size_key],
            })
            continue

        best_group["items"].append(entry)
        # Use median-like central values from member centers rather than the
        # union rectangle, so one tall/wide item cannot drag in distant items.
        centers = sorted(item[center_key] for item in best_group["items"])
        sizes = sorted(item[size_key] for item in best_group["items"])
        mid = len(centers) // 2
        best_group["center"] = centers[mid]
        best_group["average_size"] = sizes[mid]
        best_group["low"] = min(item[low_key] for item in best_group["items"])
        best_group["high"] = max(item[high_key] for item in best_group["items"])

    return groups


def _sort_by_rows(
    shapes: Sequence[dict], *, left_to_right: bool, vertical_distance: Optional[float] = None, horizontal_distance: Optional[float] = None
) -> List[dict]:
    entries = [_shape_sort_entry(shape, index) for index, shape in enumerate(shapes)]
    rows = _cluster_entries(entries, "row", vertical_distance)
    rows.sort(key=lambda group: (group["center"], group["low"]))
    result = []
    for row in rows:
        if left_to_right:
            row["items"].sort(key=lambda entry: (entry["cx"], entry["cy"], entry["index"]))
        else:
            row["items"].sort(key=lambda entry: (-entry["cx"], entry["cy"], entry["index"]))
        result.extend(entry["shape"] for entry in row["items"])
    return result


def _sort_by_columns(
    shapes: Sequence[dict], *, right_to_left: bool, horizontal_distance: Optional[float] = None, vertical_distance: Optional[float] = None
) -> List[dict]:
    entries = [_shape_sort_entry(shape, index) for index, shape in enumerate(shapes)]
    columns = _cluster_entries(entries, "column", horizontal_distance)
    if right_to_left:
        columns.sort(key=lambda group: (-group["center"], -group["high"]))
    else:
        columns.sort(key=lambda group: (group["center"], group["low"]))
    result = []
    for column in columns:
        column["items"].sort(key=lambda entry: (entry["cy"], -entry["cx"], entry["index"]))
        result.extend(entry["shape"] for entry in column["items"])
    return result


def _scanline_horizontal_left_to_right(
    shapes: Sequence[dict], horizontal_distance: Optional[float] = None, vertical_distance: Optional[float] = None
) -> List[dict]:
    """Read rows top-to-bottom and each row left-to-right."""
    return _sort_by_rows(shapes, left_to_right=True, vertical_distance=vertical_distance, horizontal_distance=horizontal_distance)


def _scanline_horizontal_right_to_left(
    shapes: Sequence[dict], horizontal_distance: Optional[float] = None, vertical_distance: Optional[float] = None
) -> List[dict]:
    """Read rows top-to-bottom and each row right-to-left."""
    return _sort_by_rows(shapes, left_to_right=False, vertical_distance=vertical_distance, horizontal_distance=horizontal_distance)


def _manga_x_then_y_sort(
    shapes: Sequence[dict], image_width: float = 1000, image_height: float = 1000
) -> List[dict]:
    """Japanese horizontal priority: reading bands top-down, right-to-left."""
    return _sort_by_rows(shapes, left_to_right=False, vertical_distance=None, horizontal_distance=None)


def _manga_y_then_x_sort(
    shapes: Sequence[dict], image_width: float = 1000, image_height: float = 1000
) -> List[dict]:
    """Japanese vertical priority: columns right-to-left, each top-to-bottom."""
    return _sort_by_columns(shapes, right_to_left=True)


def _scanline_plan(
    shapes: Sequence[dict],
    mode: str,
    image_size: Optional[Tuple[float, float]] = None,
    container_labels: Optional[Sequence[str]] = None,
    priority_labels: Optional[Sequence[str]] = None,
    horizontal_scan_distance: float = 12.0,
    vertical_scan_distance: float = 12.0,
):
    """Sort manga text with a two-dimensional page grid.

    The grid first detects broad horizontal reading bands from low-occupancy
    rows. Bands are read top-to-bottom; shapes inside a band are read
    right-to-left. Very tall shapes crossing a band separator are deferred so
    they cannot merge separate panels or steal the first position.
    """
    width, height = image_size or (1000.0, 1000.0)
    width = max(float(width or 1.0), 1.0)
    height = max(float(height or 1.0), 1.0)
    entries = [_shape_sort_entry(shape, index) for index, shape in enumerate(shapes)]
    excluded = {
        str(label).strip() for label in (container_labels or []) if str(label).strip()
    }
    candidates = [
        entry for entry in entries
        if entry["shape"].get("label") not in excluded
    ]

    if not candidates:
        return list(shapes), []

    widths = sorted(entry["width"] for entry in candidates if entry["width"] > 0)
    heights = sorted(entry["height"] for entry in candidates if entry["height"] > 0)
    median_width = widths[len(widths) // 2] if widths else 16.0
    median_height = heights[len(heights) // 2] if heights else 16.0
    auto_grid_step = max(
        4.0,
        min(20.0, min(median_width, median_height) * 0.35),
    )
    # Detection distance controls the actual scan sampling grid. Changing it
    # is expected to affect reading-band detection and therefore label order.
    x_step = max(1.0, float(horizontal_scan_distance or auto_grid_step))
    y_step = max(1.0, float(vertical_scan_distance or auto_grid_step))

    x_grid = [index * x_step for index in range(int(width / x_step) + 1)]
    y_grid = [index * y_step for index in range(int(height / y_step) + 1)]
    if not x_grid or x_grid[-1] < width:
        x_grid.append(width)
    if not y_grid or y_grid[-1] < height:
        y_grid.append(height)

    # A real # grid: every vertical and horizontal line spans the full page.
    segments = [((x, 0.0), (x, height)) for x in x_grid]
    segments.extend(((0.0, y), (width, y)) for y in y_grid)

    # Count how many text rectangles cross each horizontal grid row. Long
    # low-occupancy valleys are panel/read-band separators. One narrow bridge
    # is allowed, which handles marginal narration crossing a panel boundary.
    occupancy = []
    for y in y_grid:
        count = sum(1 for entry in candidates if entry["top"] <= y <= entry["bottom"])
        occupancy.append(count)
    bridge_limit = max(1, min(2, len(candidates) // 8))
    min_valley_height = max(y_step * 2.0, median_height * 0.45)
    separators = []
    run_start = None
    for index, count in enumerate(occupancy):
        y = y_grid[index]
        is_inner = y_step < y < height - y_step
        if is_inner and count <= bridge_limit:
            if run_start is None:
                run_start = index
        elif run_start is not None:
            run_end = index - 1
            if y_grid[run_end] - y_grid[run_start] >= min_valley_height:
                separators.append((y_grid[run_start] + y_grid[run_end]) / 2.0)
            run_start = None
    if run_start is not None:
        run_end = len(y_grid) - 1
        if y_grid[run_end] - y_grid[run_start] >= min_valley_height:
            separators.append((y_grid[run_start] + y_grid[run_end]) / 2.0)

    # Ignore separators too close together; keep the center of the strongest
    # whitespace area represented by the detected run.
    filtered_separators = []
    for separator in separators:
        if not filtered_separators or separator - filtered_separators[-1] >= median_height * 0.6:
            filtered_separators.append(separator)
    separators = filtered_separators

    boundaries = [0.0] + separators + [height]
    bands = [[] for _ in range(max(1, len(boundaries) - 1))]
    deferred = []
    tall_threshold = max(median_height * 1.8, height * 0.28)
    for entry in candidates:
        crossed = [cut for cut in separators if entry["top"] < cut < entry["bottom"]]
        if crossed and entry["height"] >= tall_threshold:
            deferred.append(entry)
            continue
        center_y = entry["cy"]
        band_index = len(bands) - 1
        for index in range(len(boundaries) - 1):
            if boundaries[index] <= center_y < boundaries[index + 1]:
                band_index = index
                break
        bands[band_index].append(entry)

    # Detection distances are direct hit-grouping thresholds, not animation
    # speed. Horizontal distance groups nearby right edges into one scan
    # column; vertical distance groups nearby tops into one scan row. Both
    # values therefore directly participate in the resulting label order.
    horizontal_distance = max(1.0, x_step)
    vertical_distance = max(1.0, y_step)

    def sort_band_right_to_left(items):
        if not items:
            return []
        right_edge = max(item["right"] for item in items)
        top_edge = min(item["top"] for item in items)
        return sorted(
            items,
            key=lambda item: (
                int((right_edge - item["right"]) // horizontal_distance),
                int((item["top"] - top_edge) // vertical_distance),
                item["top"],
                -item["right"],
                item["index"],
            ),
        )

    ordered_entries = []
    for band in bands:
        ordered_entries.extend(sort_band_right_to_left(band))

    # Enter the page from the upper-right corner: first identify the top
    # reading strip, then choose its rightmost text box. This prevents a lower
    # caption with a slightly farther-right edge from becoming item 1.
    all_orderable = ordered_entries + deferred
    if all_orderable:
        top_edge = min(entry["top"] for entry in all_orderable)
        top_window = max(vertical_distance, median_height * 0.45)
        top_frontier = [
            entry for entry in all_orderable
            if entry["top"] <= top_edge + top_window
        ]
        if top_frontier:
            first_entry = max(
                top_frontier,
                key=lambda entry: (entry["right"], -entry["top"], -entry["index"]),
            )
            all_orderable.remove(first_entry)
            ordered_entries = [first_entry] + all_orderable
        else:
            ordered_entries = all_orderable

    seen = {entry["index"] for entry in ordered_entries}
    for entry in entries:
        if entry["index"] not in seen:
            ordered_entries.append(entry)
            seen.add(entry["index"])
    ordered_shapes = [entry["shape"] for entry in ordered_entries]
    ordered_shapes = _apply_priority_labels(ordered_shapes, priority_labels)
    return ordered_shapes, segments

def build_scanline_plan(
    shapes: Sequence[dict],
    mode: str,
    image_size: Optional[Tuple[float, float]] = None,
    container_labels: Optional[Sequence[str]] = None,
    priority_labels: Optional[Sequence[str]] = None,
    horizontal_scan_distance: float = 12.0,
    vertical_scan_distance: float = 12.0,
):
    """Public preview helper returning ordered shapes and full scanline arrows."""
    return _scanline_plan(
        shapes, mode, image_size, container_labels, priority_labels,
        horizontal_scan_distance, vertical_scan_distance
    )

def _point_in_rect(point: Tuple[float, float], rect: Tuple[float, float, float, float]) -> bool:
    px, py = point
    rx, ry, rw, rh = rect
    return rx <= px <= rx + rw and ry <= py <= ry + rh


def _absolute_guide(
    guide: LineGuide, image_size: Tuple[float, float]
) -> Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float, float, float]]:
    width, height = image_size
    width = max(width or 1.0, 1.0)
    height = max(height or 1.0, 1.0)

    start = (guide.start[0] * width, guide.start[1] * height)
    end = (guide.end[0] * width, guide.end[1] * height)

    rect = (
        guide.rect[0] * width,
        guide.rect[1] * height,
        guide.rect[2] * width,
        guide.rect[3] * height,
    )
    return start, end, rect


def _segment_rect_hit_t(p1, p2, rect, padding=12.0):
    """Return the first normalized segment position touching a label box."""
    x1, y1, x2, y2 = rect
    left, right = min(x1, x2) - padding, max(x1, x2) + padding
    top, bottom = min(y1, y2) - padding, max(y1, y2) + padding
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]

    # Exact segment/rectangle clipping avoids missing narrow labels between
    # coarse samples of a long mouse segment.
    t_enter = 0.0
    t_exit = 1.0
    for p, q in (
        (-dx, p1[0] - left),
        (dx, right - p1[0]),
        (-dy, p1[1] - top),
        (dy, bottom - p1[1]),
    ):
        if abs(p) <= 1e-12:
            if q < 0:
                return None
            continue
        ratio = q / p
        if p < 0:
            if ratio > t_exit:
                return None
            t_enter = max(t_enter, ratio)
        else:
            if ratio < t_enter:
                return None
            t_exit = min(t_exit, ratio)
    return t_enter if t_enter <= t_exit else None


def _sort_by_line_guides(
    shapes: Sequence[dict],
    options: SortOptions,
    image_size: Optional[Tuple[float, float]] = None,
) -> List[dict]:
    if not options.line_guides:
        return list(shapes)

    if not image_size or image_size[0] is None or image_size[1] is None:
        # Without image size the guides cannot be converted. Fallback to original order.
        return list(shapes)

    width, height = image_size
    exclude_set = set(options.normalized_exclude_labels())

    entries = []
    for idx, shape in enumerate(shapes):
        points = shape.get("points") or []
        center = _get_center(points)
        x_min, y_min = _get_top_left(points)
        entries.append(
            {
                "index": idx,
                "shape": shape,
                "center": center,
                "label": shape.get("label"),
                "excluded": shape.get("label") in exclude_set,
                "spatial_key": _spatial_key(options.spatial_mode, x_min, y_min),
            }
        )

    excluded_indices = [entry["index"] for entry in entries if entry["excluded"]]
    candidate_entries = [entry for entry in entries if not entry["excluded"]]

    assigned: set[int] = set()
    ordered_indices: List[int] = []

    guides_with_index = list(enumerate(options.line_guides))

    def _guide_sort_key(item):
        idx, guide = item
        if getattr(guide, "order", None) is not None:
            return (0, guide.order, idx)
        rect = getattr(guide, "rect", None) or (0.0, 0.0, 0.0, 0.0)
        center_x = rect[0] + rect[2] / 2.0
        center_y = rect[1] + rect[3] / 2.0
        return (1, round(center_y, 6), round(center_x, 6), idx)

    sorted_guides = [guide for _, guide in sorted(guides_with_index, key=_guide_sort_key)]

    for guide in sorted_guides:
        path = getattr(guide, "path", None) or []
        if len(path) >= 2:
            abs_path = [(float(x) * width, float(y) * height) for x, y in path]
            hit_items = []
            for entry in candidate_entries:
                idx = entry["index"]
                if idx in assigned:
                    continue
                points = entry["shape"].get("points") or []
                if not points:
                    continue
                x1, y1 = _get_top_left(points)
                x2 = max((float(p[0]) for p in points), default=x1)
                y2 = max((float(p[1]) for p in points), default=y1)
                distance = 0.0
                hit_distance = None
                for p1, p2 in zip(abs_path, abs_path[1:]):
                    segment_length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                    hit_t = _segment_rect_hit_t(p1, p2, (x1, y1, x2, y2))
                    if hit_t is not None:
                        hit_distance = distance + segment_length * hit_t
                        break
                    distance += segment_length
                if hit_distance is not None:
                    hit_items.append((hit_distance, idx))
            hit_items.sort(key=lambda item: (item[0], item[1]))
            for _, idx in hit_items:
                assigned.add(idx)
                ordered_indices.append(idx)
            continue
        start, end, rect = _absolute_guide(guide, (width, height))
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 1e-8:
            continue
        ux, uy = dx / length, dy / length

        guide_items = []
        for entry in candidate_entries:
            idx = entry["index"]
            if idx in assigned:
                continue
            if not _point_in_rect(entry["center"], rect):
                continue
            rel_x = entry["center"][0] - start[0]
            rel_y = entry["center"][1] - start[1]
            projection = rel_x * ux + rel_y * uy
            guide_items.append((projection, entry["index"]))

        guide_items.sort(key=lambda item: (item[0], item[1]))
        for _, idx in guide_items:
            assigned.add(idx)
            ordered_indices.append(idx)
    # Match BallonsTranslator: untouched labels keep their original order.
    remaining_indices = []
    for entry in candidate_entries:
        idx = entry["index"]
        if idx not in assigned:
            remaining_indices.append(idx)

    final_indices: List[int] = []
    if options.prioritize_exception_label:
        final_indices.extend(excluded_indices)
        final_indices.extend(ordered_indices)
        final_indices.extend(remaining_indices)
    else:
        final_indices.extend(ordered_indices)
        final_indices.extend(remaining_indices)
        final_indices.extend(excluded_indices)

    # Safety: append any missing indices in original order
    seen = set(final_indices)
    for entry in entries:
        if entry["index"] not in seen:
            final_indices.append(entry["index"])
            seen.add(entry["index"])

    return [shapes[i] for i in final_indices]


def _apply_priority_labels(shapes: Sequence[dict], priority_labels: Sequence[str]) -> List[dict]:
    """Move configured labels to the front in the exact user-specified order."""
    priorities = []
    for label in priority_labels or []:
        clean = str(label).strip()
        if clean and clean not in priorities:
            priorities.append(clean)
    if not priorities:
        return list(shapes)

    buckets = {label: [] for label in priorities}
    remaining = []
    for shape in shapes:
        label = str(shape.get("label", "")).strip()
        if label in buckets:
            buckets[label].append(shape)
        else:
            remaining.append(shape)
    result = []
    for label in priorities:
        result.extend(buckets[label])
    result.extend(remaining)
    return result


def sort_shapes(
    shapes: Sequence[dict],
    options: SortOptions,
    image_size: Optional[Tuple[float, float]] = None,
) -> List[dict]:
    mode = (options.spatial_mode or "").upper()

    # Only RIGHT_TO_LEFT uses the new continuous grid scan for now.
    # The other three modes retain their own independent algorithms.
    if mode == "RIGHT_TO_LEFT":
        all_shapes, _ = _scanline_plan(
            shapes,
            mode,
            image_size,
            options.normalized_exclude_labels(),
            options.priority_labels,
            options.horizontal_scan_distance,
            options.vertical_scan_distance,
        )
    elif mode == "LEFT_TO_RIGHT":
        all_shapes = _scanline_horizontal_left_to_right(
            shapes, options.horizontal_scan_distance, options.vertical_scan_distance
        )
    elif mode == "X_THEN_Y":
        size = image_size or (1000.0, 1000.0)
        all_shapes = _scanline_horizontal_right_to_left(
            shapes, options.horizontal_scan_distance, options.vertical_scan_distance
        )
    elif mode == "Y_THEN_X":
        size = image_size or (1000.0, 1000.0)
        all_shapes = _sort_by_columns(
            shapes, right_to_left=True,
            horizontal_distance=options.horizontal_scan_distance,
            vertical_distance=options.vertical_scan_distance,
        )
    elif mode == "LINE_GUIDES":
        if options.line_guides:
            return _sort_by_line_guides(shapes, options, image_size)
        return list(shapes)
    else:
        # 默认使用从右到左排序（适合日漫）
        all_shapes = _scanline_horizontal_right_to_left(shapes)

    # 处理排除标签
    exclude_set = set(options.normalized_exclude_labels())
    if not exclude_set:
        return _apply_priority_labels(all_shapes, options.priority_labels)

    # 分离排除和非排除的shapes，保持排序后的顺序
    excluded_shapes = []
    included_shapes = []

    for shape in all_shapes:
        if shape.get("label") in exclude_set:
            excluded_shapes.append(shape)
        else:
            included_shapes.append(shape)

    # 根据prioritize_exception_label决定顺序
    if options.prioritize_exception_label:
        result = excluded_shapes + included_shapes
    else:
        result = included_shapes + excluded_shapes
    return _apply_priority_labels(result, options.priority_labels)


def sort_json_file(
    file_path: str,
    options: Optional[SortOptions] = None,
    *,
    write: bool = True,
) -> SortOutcome:
    opts = options or SortOptions()
    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:  # pragma: no cover - surface to UI
        return SortOutcome(file_path, False, False, f"Failed to read file: {exc}")

    shapes = data.get("shapes")
    if not isinstance(shapes, list):
        return SortOutcome(file_path, False, False, "Missing shapes array in JSON")

    image_width = data.get("imageWidth")
    image_height = data.get("imageHeight")
    image_size = (image_width, image_height)

    # Only horizontal and rotated rectangles are sortable. Keep polygons and
    # other annotation shapes in their original list positions.
    sortable_shapes = [shape for shape in shapes if is_sortable_shape(shape)]
    sorted_sortable_shapes = sort_shapes(sortable_shapes, opts, image_size=image_size)
    sorted_shapes = list(shapes)
    sortable_index = 0
    for index, shape in enumerate(shapes):
        if is_sortable_shape(shape):
            sorted_shapes[index] = sorted_sortable_shapes[sortable_index]
            sortable_index += 1
    changed = shapes != sorted_shapes
    if not changed:
        return SortOutcome(file_path, True, False, "Already sorted")

    if not write:
        return SortOutcome(file_path, True, True, "Changes pending (dry run)")

    data["shapes"] = sorted_shapes
    try:
        with open(file_path, "w", encoding="utf-8") as fh:
            json.dump(
                data,
                fh,
                indent=2,
                ensure_ascii=False,
            )
    except Exception as exc:  # pragma: no cover - surface to UI
        return SortOutcome(file_path, False, False, f"Failed to write file: {exc}")

    return SortOutcome(file_path, True, True, "Sorted successfully")


def sort_many_files(
    file_paths: Iterable[str],
    options: Optional[SortOptions] = None,
    *,
    write: bool = True,
) -> List[SortOutcome]:
    resolved_paths = [os.path.abspath(path) for path in file_paths]
    opts = options or SortOptions()
    results: List[SortOutcome] = []
    for path in resolved_paths:
        outcome = sort_json_file(path, opts, write=write)
        results.append(outcome)
    return results
