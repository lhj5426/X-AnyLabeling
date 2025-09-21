"""Utilities for sorting labelme-style JSON files inside AnyLabeling."""

import json
import math
import os
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple


@dataclass
class LineGuide:
    """Represents a user-defined ordering guide line."""

    # Normalised coordinates relative to image width/height (0.0-1.0)
    start: Tuple[float, float]
    end: Tuple[float, float]
    rect: Tuple[float, float, float, float]  # x, y, width, height (normalised)
    order: Optional[int] = None


@dataclass
class SortOptions:
    """Configuration for sorting label entries in a JSON annotation file."""

    exception_label: Optional[str] = None
    prioritize_exception_label: bool = True  # True -> excluded labels stay ahead of others
    spatial_mode: str = "REV_X"
    line_guides: List[LineGuide] = field(default_factory=list)
    exclude_labels: List[str] = field(default_factory=list)

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


def _scanline_horizontal_left_to_right(shapes: Sequence[dict]) -> List[dict]:
    """横向扫描：从左向右"""
    if not shapes:
        return list(shapes)

    shape_data = []
    for shape in shapes:
        center = _get_center(shape.get("points", []))
        shape_data.append({'shape': shape, 'center_x': center[0], 'center_y': center[1]})

    # 按X坐标排序（从左到右）
    shape_data.sort(key=lambda x: x['center_x'])
    return [data['shape'] for data in shape_data]


def _scanline_horizontal_right_to_left(shapes: Sequence[dict]) -> List[dict]:
    """横向扫描：从右向左"""
    if not shapes:
        return list(shapes)

    shape_data = []
    for shape in shapes:
        center = _get_center(shape.get("points", []))
        shape_data.append({'shape': shape, 'center_x': center[0], 'center_y': center[1]})

    # 按X坐标倒序排序（从右到左）
    shape_data.sort(key=lambda x: -x['center_x'])
    return [data['shape'] for data in shape_data]


def _manga_x_then_y_sort(shapes: Sequence[dict], image_width: float = 1000, image_height: float = 1000) -> List[dict]:
    """
    日漫横向优先排序：先从右到左，遇到换行时从上到下
    适合传统日漫的分栏阅读习惯
    """
    if not shapes:
        return list(shapes)

    shape_data = []
    for shape in shapes:
        center = _get_center(shape.get("points", []))
        shape_data.append({'shape': shape, 'center_x': center[0], 'center_y': center[1]})

    # 日漫排序：按Y坐标分组（从上到下），每组内按X坐标从右到左
    shape_data.sort(key=lambda x: (x['center_y'], -x['center_x']))
    return [data['shape'] for data in shape_data]


def _manga_y_then_x_sort(shapes: Sequence[dict], image_width: float = 1000, image_height: float = 1000) -> List[dict]:
    """
    日漫纵向优先排序：先从右到左分栏，每栏内从上到下
    这是最符合传统日漫阅读习惯的排序方式
    """
    if not shapes:
        return list(shapes)

    shape_data = []
    for shape in shapes:
        center = _get_center(shape.get("points", []))
        shape_data.append({'shape': shape, 'center_x': center[0], 'center_y': center[1]})

    # 日漫排序：按X坐标分组（从右到左），每组内按Y坐标从上到下
    shape_data.sort(key=lambda x: (-x['center_x'], x['center_y']))
    return [data['shape'] for data in shape_data]


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
    remaining = []
    for entry in candidate_entries:
        idx = entry["index"]
        if idx in assigned:
            continue
        x_order, y_order = entry["spatial_key"]
        remaining.append((x_order, y_order, idx))

    remaining.sort(key=lambda item: (item[0], item[1], item[2]))
    remaining_indices = [item[2] for item in remaining]

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


def sort_shapes(
    shapes: Sequence[dict],
    options: SortOptions,
    image_size: Optional[Tuple[float, float]] = None,
) -> List[dict]:
    mode = (options.spatial_mode or "").upper()

    # 使用新的扫描线排序算法
    if mode == "LEFT_TO_RIGHT":  # 横向（从左到右）
        all_shapes = _scanline_horizontal_left_to_right(shapes)
    elif mode == "RIGHT_TO_LEFT":  # 横向（从右到左）
        all_shapes = _scanline_horizontal_right_to_left(shapes)
    elif mode == "X_THEN_Y":  # 先横后纵
        all_shapes = _manga_x_then_y_sort(shapes, 1000, 1000)
    elif mode == "Y_THEN_X":  # 先纵后横
        all_shapes = _manga_y_then_x_sort(shapes, 1000, 1000)
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
        return all_shapes

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
        return excluded_shapes + included_shapes
    else:
        return included_shapes + excluded_shapes


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

    sorted_shapes = sort_shapes(shapes, opts, image_size=image_size)
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
