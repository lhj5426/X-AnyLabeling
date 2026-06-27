"""文字掩膜生成 — 完全照搬 content.py 的 detect_content_mask_in_bbox 逻辑"""
import cv2
import numpy as np
from . import _cv2_compat as imk


def generate_text_mask(
    crop: np.ndarray,
    *,
    dilate_kernel_size: int = 0,
    dilate_iterations: int = 0,
    close_kernel_size: int = 3,
) -> np.ndarray:
    """
    完全移植 comic-translate-main/modules/detection/utils/content.py
    中的 detect_content_mask_in_bbox:

    1. 灰度化
    2. cv2 Otsu 阈值 (替代 mahotas)
    3. 黑/白双向连通组件 → connectedComponentsWithStats
    4. 过滤: min_area=10, margin=1, 排除 >50% 面积组件
    5. 形态学闭运算 (3x3) + 膨胀 (默认不膨胀, 参数由调用方传入)

    Args:
        crop: 输入的RGB图像裁剪区域
        dilate_kernel_size: 膨胀核大小（像素），0 表示不膨胀
        dilate_iterations: 膨胀迭代次数，0 表示不膨胀
        close_kernel_size: 闭运算核大小，默认3
    """
    if crop is None or crop.size == 0:
        return np.zeros((0, 0), dtype=np.uint8)

    h, w = crop.shape[:2]
    gray = imk.to_gray(crop)
    if gray.dtype != np.uint8:
        gray = gray.astype(np.uint8)

    # Otsu 阈值 — 用 cv2 替代 mahotas
    threshold, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 黑底白字 / 白底黑字 双向检测（照搬原版逻辑）
    binary_black_text = (gray < threshold).astype(np.uint8)
    binary_white_text = (gray > threshold).astype(np.uint8)
    if not np.any(binary_black_text):
        binary_black_text = (gray == gray.min()).astype(np.uint8)
    if not np.any(binary_white_text):
        binary_white_text = (gray == gray.max()).astype(np.uint8)

    mask_black = _mask_from_component_stats(binary_black_text)
    mask_white = _mask_from_component_stats(binary_white_text)

    mask = np.where((mask_black > 0) | (mask_white > 0), 255, 0).astype(np.uint8)

    if not np.any(mask):
        return mask

    # 闭运算
    close_kernel = imk.get_structuring_element(imk.MORPH_RECT, (close_kernel_size, close_kernel_size))
    mask = imk.morphology_ex(mask, imk.MORPH_CLOSE, close_kernel)

    # 膨胀（由调用方控制参数）
    if dilate_kernel_size > 0 and dilate_iterations > 0:
        dil_kernel = np.ones((dilate_kernel_size, dilate_kernel_size), np.uint8)
        mask = imk.dilate(mask, dil_kernel, iterations=dilate_iterations)

    return mask


def _mask_from_component_stats(
    binary: np.ndarray,
    *,
    min_area: int = 10,
    margin: int = 1,
    small_component_min_area: int = 4,
    small_component_max_span: int = 6,
) -> np.ndarray:
    """照搬 content.py 的 _mask_from_component_stats（向量化版本，含标点小组件保留逻辑）"""
    h, w = binary.shape[:2]
    num_labels, labels, stats, _ = imk.connected_components_with_stats(binary, connectivity=8)
    if num_labels <= 1:
        return np.zeros((h, w), dtype=np.uint8)

    # 去掉背景（index 0）
    stats_no_bg = stats[1:]
    if stats_no_bg.shape[0] == 0:
        return np.zeros((h, w), dtype=np.uint8)

    x1 = stats_no_bg[:, imk.CC_STAT_LEFT]
    y1 = stats_no_bg[:, imk.CC_STAT_TOP]
    cw = stats_no_bg[:, imk.CC_STAT_WIDTH]
    ch = stats_no_bg[:, imk.CC_STAT_HEIGHT]
    area = stats_no_bg[:, imk.CC_STAT_AREA]

    # 条件1：面积 > min_area（正常字符）
    area_mask = area > min_area
    # 条件2：标点/小符号组件保留（即使面积很小）
    small_component_mask = (
        (area >= small_component_min_area)
        & (cw <= small_component_max_span)
        & (ch <= small_component_max_span)
    )
    # 条件3：不贴边（贴边的通常是气泡框/分镜框，不是文字）
    border_mask = (
        (x1 >= margin)
        & (y1 >= margin)
        & ((x1 + cw) <= w - margin)
        & ((y1 + ch) <= h - margin)
    )
    keep = (area_mask | small_component_mask) & border_mask

    # 过滤过大的组件（彩色旁白盒的整片背景填充）
    if h * w > 150:
        max_area = int(0.50 * h * w)
        keep = keep & (area < max_area)

    if not np.any(keep):
        return np.zeros((h, w), dtype=np.uint8)

    # +1 因为 keep 对应 stats_no_bg（已去掉背景 index 0）
    keep_labels = np.flatnonzero(keep) + 1
    return np.where(np.isin(labels, keep_labels), 255, 0).astype(np.uint8)


def mask_to_polygons(mask: np.ndarray) -> list:
    """掩膜 → 多边形列表"""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    polygons = []
    for cnt in contours:
        if len(cnt) < 3:
            continue
        perimeter = cv2.arcLength(cnt, True)
        epsilon = 0.005 * perimeter
        approx = cv2.approxPolyDP(cnt, epsilon, True)
        pts = [[int(pt[0][0]), int(pt[0][1])] for pt in approx]
        if len(pts) >= 3:
            polygons.append(pts)
    return polygons


# ── 多边形过滤：删除不在矩形/旋转框内的 mask ──

def _point_in_polygon(point, polygon):
    """射线法：判断点是否在多边形内部（支持旋转矩形）

    Args:
        point: (x, y) 坐标
        polygon: [[x1,y1], [x2,y2], ...] 多边形顶点

    Returns:
        bool: 点在多边形内返回 True
    """
    x, y = float(point[0]), float(point[1])
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi = float(polygon[i][0])
        yi = float(polygon[i][1])
        xj = float(polygon[j][0])
        yj = float(polygon[j][1])
        # 检查射线是否穿过此边（ys 严格在 yi, yj 之间）
        if ((yi > y) != (yj > y)):
            dy = yj - yi
            if abs(dy) < 1e-10:
                j = i
                continue
            x_intersect = (xj - xi) * (y - yi) / dy + xi
            if x < x_intersect:
                inside = not inside
        j = i
    return inside


def filter_polygons_by_boxes(shapes, vertex_ratio: float = 0.5):
    """删除不在矩形/旋转框内的 mask 多边形

    判断逻辑：统计多边形有多少个顶点落在参考框内，
    超过 vertex_ratio（默认 50%）顶点在框内才保留。

    针对 "rotation" 类型矩形框使用精确的点-in-多边形判断，
    针对 "rectangle" 类型使用轴对齐包围盒判断。

    Args:
        shapes: X-AnyLabeling JSON 的 shapes 列表
        vertex_ratio: 顶点占比阈值（0~1），默认 0.5 即多数顶点在框内才保留

    Returns:
        (filtered_shapes, removed_count): 过滤后的 shapes 列表和删除数量
    """
    import numpy as np

    # 第一步：收集所有参考框
    ref_boxes = []  # [{'type': 'rotation'|'rect', 'polygon': arr|None, 'aabb': (x1,y1,x2,y2)}, ...]
    for s in shapes:
        shape_type = s.get('shape_type')
        if shape_type not in ('rectangle', 'rotation'):
            continue
        pts = s.get('points', [])
        if len(pts) < 4:
            continue

        arr = np.array(pts, dtype=np.float64)
        x1, y1 = arr[:, 0].min(), arr[:, 1].min()
        x2, y2 = arr[:, 0].max(), arr[:, 1].max()

        if shape_type == 'rotation':
            ref_boxes.append({
                'type': 'rotation',
                'polygon': arr,
                'aabb': (x1, y1, x2, y2),
            })
        else:
            ref_boxes.append({
                'type': 'rect',
                'polygon': None,
                'aabb': (x1, y1, x2, y2),
            })

    if not ref_boxes:
        return shapes, 0  # 无参考框，全部保留

    # 第二步：筛选 mask 多边形（顶点多数原则）
    kept = []
    removed = 0

    for s in shapes:
        if s.get('label') != 'mask' or s.get('shape_type') != 'polygon':
            kept.append(s)
            continue

        pts = s.get('points', [])
        if len(pts) < 3:
            removed += 1
            continue

        arr = np.array(pts, dtype=np.float64)

        # 统计每个顶点是否落在任意参考框内
        vertices_inside = 0
        for pt in arr:
            pt_inside = False
            for rb in ref_boxes:
                if rb['type'] == 'rotation':
                    if _point_in_polygon(pt, rb['polygon']):
                        pt_inside = True
                        break
                else:
                    rx1, ry1, rx2, ry2 = rb['aabb']
                    px, py = float(pt[0]), float(pt[1])
                    if rx1 <= px <= rx2 and ry1 <= py <= ry2:
                        pt_inside = True
                        break
            if pt_inside:
                vertices_inside += 1

        ratio = vertices_inside / max(len(arr), 1)
        if ratio >= vertex_ratio:
            kept.append(s)
        else:
            removed += 1

    return kept, removed
