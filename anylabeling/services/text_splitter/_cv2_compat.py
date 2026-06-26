"""imkit → cv2 + numpy 兼容层"""
import cv2
import numpy as np

# ── 常量 ──
MORPH_RECT = cv2.MORPH_RECT
MORPH_ELLIPSE = cv2.MORPH_ELLIPSE
MORPH_CLOSE = cv2.MORPH_CLOSE
MORPH_DILATE = cv2.MORPH_DILATE
MORPH_ERODE = cv2.MORPH_ERODE
MORPH_OPEN = cv2.MORPH_OPEN

CC_STAT_LEFT = cv2.CC_STAT_LEFT
CC_STAT_TOP = cv2.CC_STAT_TOP
CC_STAT_WIDTH = cv2.CC_STAT_WIDTH
CC_STAT_HEIGHT = cv2.CC_STAT_HEIGHT
CC_STAT_AREA = cv2.CC_STAT_AREA


# ── 图像 I/O ──
def to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)


# ── 阈值 ──
def otsu_threshold(gray: np.ndarray) -> tuple[float, np.ndarray]:
    if gray.dtype != np.uint8:
        gray = gray.astype(np.uint8)
    threshold, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return float(threshold), (binary > 0)


# ── 形态学 ──
def get_structuring_element(shape, ksize):
    return cv2.getStructuringElement(shape, ksize)


def morphology_ex(src, op, kernel, iterations=1):
    return cv2.morphologyEx(src, op, kernel, iterations=iterations)


def dilate(src, kernel, iterations=1):
    return cv2.dilate(src, kernel, iterations=iterations)


def erode(src, kernel, iterations=1):
    return cv2.erode(src, kernel, iterations=iterations)


# ── 连通组件 ──
def connected_components_with_stats(binary, connectivity=8):
    if binary.dtype != np.uint8:
        binary = binary.astype(np.uint8)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        binary, connectivity=connectivity
    )
    return num_labels, labels, stats, centroids


# ── 积分图 ──
def integral_image(image):
    if image.dtype != np.float64:
        image = image.astype(np.float64)
    return cv2.integral(image)


# ── 高斯模糊 ──
def gaussian_blur(src, sigma):
    ksize = int(2 * np.ceil(3 * sigma) + 1)
    if ksize % 2 == 0:
        ksize += 1
    return cv2.GaussianBlur(src.astype(np.float32), (ksize, ksize), sigma)
