"""
Text region extraction utilities.
Ported from manga-translator's Quadrilateral class (sort_pnts + get_transformed_region).
"""

from typing import Tuple, List
import numpy as np
import cv2


def sort_quadrilateral_points(pts: np.ndarray) -> Tuple[np.ndarray, bool]:
    """
    Sort 4 unordered quadrilateral points into [top-left, top-right, bottom-right, bottom-left]
    order and determine if the text is vertical or horizontal.

    Args:
        pts: Array of shape (4, 2) with 4 unordered points.

    Returns:
        Tuple of (sorted_pts, is_vertical).
        sorted_pts: Array of shape (4, 2) in [tl, tr, br, bl] order.
        is_vertical: True if the text direction is vertical.
    """
    if isinstance(pts, list):
        pts = np.array(pts)
    assert isinstance(pts, np.ndarray) and pts.shape == (4, 2)

    pairwise_vec = (pts[:, None] - pts[None]).reshape((16, -1))
    pairwise_vec_norm = np.linalg.norm(pairwise_vec, axis=1)
    long_side_ids = np.argsort(pairwise_vec_norm)[[8, 10]]
    long_side_vecs = pairwise_vec[long_side_ids]
    inner_prod = (long_side_vecs[0] * long_side_vecs[1]).sum()
    if inner_prod < 0:
        long_side_vecs[0] = -long_side_vecs[0]
    struc_vec = np.abs(long_side_vecs.mean(axis=0))
    is_vertical = struc_vec[0] <= struc_vec[1]

    if is_vertical:
        pts = pts[np.argsort(pts[:, 1])]
        pts = pts[[*np.argsort(pts[:2, 0]), *np.argsort(pts[2:, 0])[::-1] + 2]]
        return pts, is_vertical
    else:
        pts = pts[np.argsort(pts[:, 0])]
        pts_sorted = np.zeros_like(pts)
        pts_sorted[[0, 3]] = sorted(pts[[0, 1]], key=lambda x: x[1])
        pts_sorted[[1, 2]] = sorted(pts[[2, 3]], key=lambda x: x[1])
        return pts_sorted, is_vertical


def extract_text_region(
    image: np.ndarray,
    pts: np.ndarray,
    text_height: int = 48
) -> Tuple[np.ndarray, str]:
    """
    Extract a perspective-corrected text region from the image.
    The region is resized to a fixed height. Vertical text is rotated 90 degrees
    counterclockwise so it reads left-to-right.

    Args:
        image: Source image (BGR or RGB, numpy array).
        pts: 4 points of the quadrilateral (will be sorted internally).
        text_height: Fixed height of the output region (default 48 for the OCR model).

    Returns:
        Tuple of (region_image, direction).
        region_image: Extracted and deskewed text region of shape (text_height, W, 3).
        direction: 'h' for horizontal, 'v' for vertical.
    """
    sorted_pts, is_vertical = sort_quadrilateral_points(pts)
    direction = 'v' if is_vertical else 'h'

    # Compute structure vectors (midpoints of edges)
    p1 = ((sorted_pts[0] + sorted_pts[1]) / 2).astype(np.float32)  # top edge midpoint
    p2 = ((sorted_pts[2] + sorted_pts[3]) / 2).astype(np.float32)  # bottom edge midpoint
    p3 = ((sorted_pts[1] + sorted_pts[2]) / 2).astype(np.float32)  # right edge midpoint
    p4 = ((sorted_pts[3] + sorted_pts[0]) / 2).astype(np.float32)  # left edge midpoint

    v_vec = p2 - p1  # vertical vector
    h_vec = p3 - p4  # horizontal vector

    v_len = np.linalg.norm(v_vec)
    h_len = np.linalg.norm(h_vec)
    if h_len < 1e-6:
        ratio = 1.0
    else:
        ratio = v_len / h_len

    src_pts = sorted_pts.astype(np.int64).copy()
    im_h, im_w = image.shape[:2]

    # Bounding box clipped to image dimensions
    x1 = int(np.clip(src_pts[:, 0].min(), 0, im_w))
    y1 = int(np.clip(src_pts[:, 1].min(), 0, im_h))
    x2 = int(np.clip(src_pts[:, 0].max(), 0, im_w))
    y2 = int(np.clip(src_pts[:, 1].max(), 0, im_h))

    # Handle degenerate regions
    if x1 >= x2 or y1 >= y2:
        if direction == 'h':
            h = max(int(text_height), 2)
            w = max(int(text_height / 8), 2)
            return np.ones((h, w, 3), dtype=np.uint8) * 255, direction
        else:
            w = max(int(text_height), 2)
            h = max(int(text_height * 8), 2)
            region = np.ones((h, w, 3), dtype=np.uint8) * 255
            region = cv2.rotate(region, cv2.ROTATE_90_COUNTERCLOCKWISE)
            return region, direction

    # Crop to bounding box to avoid warpPerspective overflow on large images
    img_cropped = image[y1:y2, x1:x2]
    src_pts[:, 0] -= x1
    src_pts[:, 1] -= y1

    if direction == 'h':
        h = max(int(text_height), 2)
        w = max(int(round(text_height / ratio)) if ratio > 0 else 2, 2)
        dst_pts = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32)
        M, _ = cv2.findHomography(src_pts.astype(np.float32), dst_pts, cv2.RANSAC, 5.0)
        if M is None:
            M = cv2.getPerspectiveTransform(src_pts.astype(np.float32), dst_pts)
        region = cv2.warpPerspective(img_cropped, M, (w, h))
        return region, direction
    else:
        w = max(int(text_height), 2)
        h = max(int(round(text_height * ratio)) if ratio > 0 else 2, 2)
        dst_pts = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32)
        M, _ = cv2.findHomography(src_pts.astype(np.float32), dst_pts, cv2.RANSAC, 5.0)
        if M is None:
            M = cv2.getPerspectiveTransform(src_pts.astype(np.float32), dst_pts)
        region = cv2.warpPerspective(img_cropped, M, (w, h))
        region = cv2.rotate(region, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return region, direction
