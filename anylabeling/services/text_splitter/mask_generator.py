"""文字掩膜生成 — 完全照搬 content.py 的 detect_content_mask_in_bbox 逻辑"""
import cv2
import numpy as np
from . import _cv2_compat as imk


def generate_text_mask(crop: np.ndarray) -> np.ndarray:
    """
    完全移植 comic-translate-main/modules/detection/utils/content.py
    中的 detect_content_mask_in_bbox:

    1. 灰度化
    2. cv2 Otsu 阈值 (替代 mahotas)
    3. 黑/白双向连通组件 → connectedComponentsWithStats
    4. 过滤: min_area=10, margin=1, 排除 >50% 面积组件
    5. 形态学闭运算 (3x3) + 膨胀 3 次 (5x5)
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

    # 闭运算 + 膨胀（照搬 detect_and_split.py）
    close_kernel = imk.get_structuring_element(imk.MORPH_RECT, (3, 3))
    mask = imk.morphology_ex(mask, imk.MORPH_CLOSE, close_kernel)
    dil_kernel = np.ones((5, 5), np.uint8)
    mask = imk.dilate(mask, dil_kernel, iterations=3)

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
