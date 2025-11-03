"""
矩形间距线检测模块

用于检测矩形之间的间距，并生成间距线和吸附偏移量。
支持：
1. 水平矩形 ↔ 水平旋转矩形（0°/90°/180°/270°）：水平/垂直间距线
2. 倾斜旋转矩形 ↔ 倾斜旋转矩形：倾斜间距线
"""

import math
import logging
from typing import List, Tuple, Optional, Dict
from PyQt5 import QtCore

logger = logging.getLogger(__name__)


class RectangleSpacingGuide:
    """矩形间距线检测和吸附功能"""

    @staticmethod
    def get_rectangle_type(shape) -> str:
        """
        判断矩形类型

        Returns:
            'horizontal': 水平矩形（shape_type='rectangle'）
            'horizontal_rotation': 水平旋转矩形（0°/90°/180°/270°）
            'tilted_rotation': 倾斜旋转矩形（其他角度）
            'other': 其他类型
        """
        if not hasattr(shape, 'shape_type'):
            return 'other'

        if shape.shape_type == 'rectangle':
            return 'horizontal'

        if shape.shape_type in ['rotation', 'rotation3']:
            # 检查旋转角度
            if not hasattr(shape, 'direction') or shape.direction is None:
                return 'horizontal_rotation'

            # 获取旋转角度（弧度转度数）
            angle_rad = shape.direction
            angle_deg = math.degrees(angle_rad)
            # 归一化到 [0, 360)
            angle_deg = angle_deg % 360

            # 检查是否接近 0°/90°/180°/270°
            angle_threshold = 5.0
            is_axis_aligned = (
                abs(angle_deg) < angle_threshold or
                abs(angle_deg - 90) < angle_threshold or
                abs(angle_deg - 180) < angle_threshold or
                abs(angle_deg - 270) < angle_threshold or
                abs(angle_deg - 360) < angle_threshold
            )

            if is_axis_aligned:
                return 'horizontal_rotation'
            else:
                return 'tilted_rotation'

        return 'other'

    @staticmethod
    def get_rect_bounds(shape) -> Optional[QtCore.QRectF]:
        """
        获取矩形的轴对齐边界框（AABB）
        """
        if not hasattr(shape, 'points') or len(shape.points) < 2:
            return None

        xs = [p.x() for p in shape.points]
        ys = [p.y() for p in shape.points]

        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)

        return QtCore.QRectF(x_min, y_min, x_max - x_min, y_max - y_min)

    @staticmethod
    def get_shape_edges(shape) -> List[Tuple]:
        """
        获取形状的四条边

        Returns:
            list: [(p1, p2), ...] 每条边的两个端点
        """
        if not hasattr(shape, 'points') or len(shape.points) < 4:
            return []

        edges = []
        points = shape.points[:4]

        for i in range(4):
            p1 = points[i]
            p2 = points[(i + 1) % 4]
            edges.append((p1, p2))

        return edges

    @staticmethod
    def point_to_line_distance(point: QtCore.QPointF, line_p1: QtCore.QPointF,
                               line_p2: QtCore.QPointF) -> float:
        """
        计算点到直线的距离
        """
        x0, y0 = point.x(), point.y()
        x1, y1 = line_p1.x(), line_p1.y()
        x2, y2 = line_p2.x(), line_p2.y()

        # 直线方程: (y2-y1)*x - (x2-x1)*y + (x2-x1)*y1 - (y2-y1)*x1 = 0
        numerator = abs((y2 - y1) * x0 - (x2 - x1) * y0 + (x2 - x1) * y1 - (y2 - y1) * x1)
        denominator = math.sqrt((y2 - y1) ** 2 + (x2 - x1) ** 2)

        if denominator < 1e-6:
            return math.sqrt((x0 - x1) ** 2 + (y0 - y1) ** 2)

        return numerator / denominator

    @staticmethod
    def detect_spacing_lines(moving_shapes: List, all_shapes: List,
                            display_distance: float = 500,
                            snap_distance: float = 10,
                            max_shapes: int = 0,
                            selected_only: bool = False) -> Tuple[Optional[QtCore.QPointF], List]:
        """
        检测矩形之间的间距线

        规则：
        1. 水平矩形 ↔ 水平旋转矩形：检测，显示水平/垂直线
        2. 倾斜旋转矩形 ↔ 倾斜旋转矩形：检测，显示倾斜线
        3. 其他组合：不检测

        Args:
            moving_shapes: 正在移动的形状列表
            all_shapes: 所有形状列表
            display_distance: 显示间距线的最大距离（像素）
            snap_distance: 吸附距离（像素）
            max_shapes: 最多检测的矩形数量（0表示检测所有）
            selected_only: 是否仅对选中的矩形测距（True时只检测moving_shapes与其他矩形的距离）

        Returns:
            (snap_offset, spacing_lines)
        """
        if not moving_shapes or not all_shapes:
            return None, []

        spacing_lines = []
        snap_offset = None

        for moving_shape in moving_shapes:
            moving_type = RectangleSpacingGuide.get_rectangle_type(moving_shape)
            moving_rect = RectangleSpacingGuide.get_rect_bounds(moving_shape)
            if not moving_rect:
                continue

            # 为当前moving_shape收集所有间距线
            shape_spacing_lines = []

            for target_shape in all_shapes:
                # 跳过自己
                if target_shape is moving_shape:
                    continue

                target_type = RectangleSpacingGuide.get_rectangle_type(target_shape)
                target_rect = RectangleSpacingGuide.get_rect_bounds(target_shape)
                if not target_rect:
                    continue

                # 检查是否应该检测间距
                # 规则1: 水平矩形 ↔ 水平旋转矩形
                if (moving_type in ['horizontal', 'horizontal_rotation'] and
                    target_type in ['horizontal', 'horizontal_rotation']):
                    RectangleSpacingGuide._detect_axis_aligned_spacing(
                        moving_shape, moving_rect, target_shape, target_rect,
                        shape_spacing_lines, display_distance, snap_distance
                    )



            # 如果设置了max_shapes限制，按四个方向分别限制
            if max_shapes > 0:
                # 按方向分组
                direction_groups = {
                    'left': [],
                    'right': [],
                    'top': [],
                    'bottom': [],
                    'tilted': []
                }

                for line_data in shape_spacing_lines:
                    line_type = line_data.get('type', 'horizontal')

                    if line_type == 'tilted':
                        direction_groups['tilted'].append(line_data)
                    else:
                        # 对于轴对齐的间距线，根据坐标判断方向
                        x1, y1 = line_data.get('x1', 0), line_data.get('y1', 0)
                        x2, y2 = line_data.get('x2', 0), line_data.get('y2', 0)

                        # 判断是水平线还是竖直线
                        if abs(y1 - y2) < 1e-6:  # 水平线
                            # 判断是左还是右
                            if x1 < moving_rect.left():
                                direction_groups['left'].append(line_data)
                            else:
                                direction_groups['right'].append(line_data)
                        else:  # 竖直线
                            # 判断是上还是下
                            if y1 < moving_rect.top():
                                direction_groups['top'].append(line_data)
                            else:
                                direction_groups['bottom'].append(line_data)

                # 每个方向按距离排序，只保留最近的max_shapes条
                filtered_lines = []
                for direction in ['left', 'right', 'top', 'bottom', 'tilted']:
                    group = direction_groups[direction]
                    if group:
                        group.sort(key=lambda x: x.get('distance', float('inf')))
                        filtered_lines.extend(group[:max_shapes])

                shape_spacing_lines = filtered_lines

            spacing_lines.extend(shape_spacing_lines)

        return snap_offset, spacing_lines

    @staticmethod
    def _detect_axis_aligned_spacing(moving_shape, moving_rect, target_shape, target_rect,
                                     spacing_lines, display_distance, snap_distance):
        """
        检测轴对齐矩形（水平/水平旋转）之间的间距
        """
        # 左侧间距
        if target_rect.right() < moving_rect.left():
            if not (target_rect.bottom() < moving_rect.top() or target_rect.top() > moving_rect.bottom()):
                dist = moving_rect.left() - target_rect.right()
                if dist < display_distance:
                    overlap_top = max(moving_rect.top(), target_rect.top())
                    overlap_bottom = min(moving_rect.bottom(), target_rect.bottom())
                    overlap_mid_y = (overlap_top + overlap_bottom) / 2

                    spacing_lines.append({
                        'x1': target_rect.right(),
                        'y1': overlap_mid_y,
                        'x2': moving_rect.left(),
                        'y2': overlap_mid_y,
                        'distance': dist,
                        'type': 'vertical'
                    })

        # 右侧间距
        if target_rect.left() > moving_rect.right():
            if not (target_rect.bottom() < moving_rect.top() or target_rect.top() > moving_rect.bottom()):
                dist = target_rect.left() - moving_rect.right()
                if dist < display_distance:
                    overlap_top = max(moving_rect.top(), target_rect.top())
                    overlap_bottom = min(moving_rect.bottom(), target_rect.bottom())
                    overlap_mid_y = (overlap_top + overlap_bottom) / 2

                    spacing_lines.append({
                        'x1': moving_rect.right(),
                        'y1': overlap_mid_y,
                        'x2': target_rect.left(),
                        'y2': overlap_mid_y,
                        'distance': dist,
                        'type': 'vertical'
                    })

        # 上侧间距
        if target_rect.bottom() < moving_rect.top():
            if not (target_rect.right() < moving_rect.left() or target_rect.left() > moving_rect.right()):
                dist = moving_rect.top() - target_rect.bottom()
                if dist < display_distance:
                    overlap_left = max(moving_rect.left(), target_rect.left())
                    overlap_right = min(moving_rect.right(), target_rect.right())
                    overlap_mid_x = (overlap_left + overlap_right) / 2

                    spacing_lines.append({
                        'x1': overlap_mid_x,
                        'y1': target_rect.bottom(),
                        'x2': overlap_mid_x,
                        'y2': moving_rect.top(),
                        'distance': dist,
                        'type': 'horizontal'
                    })

        # 下侧间距
        if target_rect.top() > moving_rect.bottom():
            if not (target_rect.right() < moving_rect.left() or target_rect.left() > moving_rect.right()):
                dist = target_rect.top() - moving_rect.bottom()
                if dist < display_distance:
                    overlap_left = max(moving_rect.left(), target_rect.left())
                    overlap_right = min(moving_rect.right(), target_rect.right())
                    overlap_mid_x = (overlap_left + overlap_right) / 2

                    spacing_lines.append({
                        'x1': overlap_mid_x,
                        'y1': moving_rect.bottom(),
                        'x2': overlap_mid_x,
                        'y2': target_rect.top(),
                        'distance': dist,
                        'type': 'horizontal'
                    })

    @staticmethod
    def _closest_points_on_segments(p1, p2, p3, p4):
        """
        计算两条线段之间最近的两个点，沿着垂直于两条边的方向
        返回 (distance, point_on_seg1, point_on_seg2)
        """
        x1, y1 = p1.x(), p1.y()
        x2, y2 = p2.x(), p2.y()
        x3, y3 = p3.x(), p3.y()
        x4, y4 = p4.x(), p4.y()

        # 线段1的方向向量
        dx1 = x2 - x1
        dy1 = y2 - y1
        len1_sq = dx1 * dx1 + dy1 * dy1

        # 线段2的方向向量
        dx2 = x4 - x3
        dy2 = y4 - y3
        len2_sq = dx2 * dx2 + dy2 * dy2

        if len1_sq < 1e-6 or len2_sq < 1e-6:
            return float('inf'), None, None

        # 计算垂直于两条边的方向（平均垂直方向）
        # 线段1的垂直方向
        perp1_x = -dy1
        perp1_y = dx1
        # 线段2的垂直方向
        perp2_x = -dy2
        perp2_y = dx2

        # 平均垂直方向
        avg_perp_x = perp1_x + perp2_x
        avg_perp_y = perp1_y + perp2_y
        avg_perp_len = math.sqrt(avg_perp_x * avg_perp_x + avg_perp_y * avg_perp_y)

        if avg_perp_len < 1e-6:
            # 两条边平行，使用其中一条的垂直方向
            avg_perp_x = perp1_x
            avg_perp_y = perp1_y
            avg_perp_len = math.sqrt(avg_perp_x * avg_perp_x + avg_perp_y * avg_perp_y)

        if avg_perp_len > 1e-6:
            avg_perp_x /= avg_perp_len
            avg_perp_y /= avg_perp_len

        min_dist = float('inf')
        best_pt1 = None
        best_pt2 = None

        # 采样线段1上的多个点
        for i in range(11):
            t1 = i / 10.0
            pt1_x = x1 + t1 * dx1
            pt1_y = y1 + t1 * dy1

            # 沿着垂直方向找到线段2上最近的点
            # 计算pt1到线段2的投影
            t2 = ((pt1_x - x3) * dx2 + (pt1_y - y3) * dy2) / len2_sq
            t2 = max(0, min(1, t2))

            pt2_x = x3 + t2 * dx2
            pt2_y = y3 + t2 * dy2

            dist = math.sqrt((pt1_x - pt2_x) ** 2 + (pt1_y - pt2_y) ** 2)
            if dist < min_dist:
                min_dist = dist
                best_pt1 = QtCore.QPointF(pt1_x, pt1_y)
                best_pt2 = QtCore.QPointF(pt2_x, pt2_y)

        # 采样线段2上的多个点
        for i in range(11):
            t2 = i / 10.0
            pt2_x = x3 + t2 * dx2
            pt2_y = y3 + t2 * dy2

            # 计算pt2到线段1的最近点
            t1 = ((pt2_x - x1) * dx1 + (pt2_y - y1) * dy1) / len1_sq
            t1 = max(0, min(1, t1))

            pt1_x = x1 + t1 * dx1
            pt1_y = y1 + t1 * dy1

            dist = math.sqrt((pt1_x - pt2_x) ** 2 + (pt1_y - pt2_y) ** 2)
            if dist < min_dist:
                min_dist = dist
                best_pt1 = QtCore.QPointF(pt1_x, pt1_y)
                best_pt2 = QtCore.QPointF(pt2_x, pt2_y)

        return min_dist, best_pt1, best_pt2

    @staticmethod
    def _closest_point_on_segment(point, seg_p1, seg_p2):
        """
        计算点到线段上最近的点
        返回 (closest_point, distance)
        """
        px, py = point.x(), point.y()
        x1, y1 = seg_p1.x(), seg_p1.y()
        x2, y2 = seg_p2.x(), seg_p2.y()

        dx = x2 - x1
        dy = y2 - y1
        len_sq = dx * dx + dy * dy

        if len_sq < 1e-6:
            dist = math.sqrt((px - x1) ** 2 + (py - y1) ** 2)
            return QtCore.QPointF(x1, y1), dist

        # 计算投影参数
        t = ((px - x1) * dx + (py - y1) * dy) / len_sq
        t = max(0, min(1, t))

        closest_x = x1 + t * dx
        closest_y = y1 + t * dy

        dist = math.sqrt((px - closest_x) ** 2 + (py - closest_y) ** 2)
        return QtCore.QPointF(closest_x, closest_y), dist



