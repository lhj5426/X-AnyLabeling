"""
测试矩形间距线功能

测试内容：
1. 矩形类型判断
2. 间距检测算法
3. 间距线绘制
"""

import sys
import math
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import QPointF

# 添加项目路径
sys.path.insert(0, '.')

from views.labeling.shape import Shape
from views.labeling.widgets.rectangle_spacing_guide import RectangleSpacingGuide


def test_rectangle_type_detection():
    """测试矩形类型判断"""
    print("=" * 60)
    print("测试 1: 矩形类型判断")
    print("=" * 60)
    
    # 测试 1.1: 水平矩形
    print("\n1.1 水平矩形 (rectangle)")
    rect = Shape(shape_type="rectangle")
    rect.points = [QPointF(0, 0), QPointF(100, 0), QPointF(100, 100), QPointF(0, 100)]
    rect_type = RectangleSpacingGuide.get_rectangle_type(rect)
    print(f"   类型: {rect_type}")
    assert rect_type == 'horizontal', f"期望 'horizontal'，得到 '{rect_type}'"
    print("   ✓ 通过")
    
    # 测试 1.2: 水平旋转矩形 (0°)
    print("\n1.2 水平旋转矩形 (0°)")
    rot_h = Shape(shape_type="rotation")
    rot_h.points = [QPointF(0, 0), QPointF(100, 0), QPointF(100, 100), QPointF(0, 100)]
    rot_h.direction = 0  # 0 弧度
    rot_type = RectangleSpacingGuide.get_rectangle_type(rot_h)
    print(f"   类型: {rot_type}")
    assert rot_type == 'horizontal_rotation', f"期望 'horizontal_rotation'，得到 '{rot_type}'"
    print("   ✓ 通过")
    
    # 测试 1.3: 水平旋转矩形 (90°)
    print("\n1.3 水平旋转矩形 (90°)")
    rot_90 = Shape(shape_type="rotation")
    rot_90.points = [QPointF(0, 0), QPointF(0, 100), QPointF(100, 100), QPointF(100, 0)]
    rot_90.direction = math.pi / 2  # 90 度
    rot_type = RectangleSpacingGuide.get_rectangle_type(rot_90)
    print(f"   类型: {rot_type}")
    assert rot_type == 'horizontal_rotation', f"期望 'horizontal_rotation'，得到 '{rot_type}'"
    print("   ✓ 通过")
    
    # 测试 1.4: 有角度旋转矩形 (45°)
    print("\n1.4 有角度旋转矩形 (45°)")
    rot_45 = Shape(shape_type="rotation")
    rot_45.points = [QPointF(50, 0), QPointF(100, 50), QPointF(50, 100), QPointF(0, 50)]
    rot_45.direction = math.pi / 4  # 45 度
    rot_type = RectangleSpacingGuide.get_rectangle_type(rot_45)
    print(f"   类型: {rot_type}")
    assert rot_type == 'tilted_rotation', f"期望 'tilted_rotation'，得到 '{rot_type}'"
    print("   ✓ 通过")
    
    print("\n✓ 矩形类型判断测试全部通过！\n")


def test_point_to_line_distance():
    """测试点到直线的距离计算"""
    print("=" * 60)
    print("测试 2: 点到直线距离计算")
    print("=" * 60)
    
    # 测试 2.1: 点到水平线的距离
    print("\n2.1 点到水平线的距离")
    point = QPointF(50, 50)
    line_p1 = QPointF(0, 0)
    line_p2 = QPointF(100, 0)
    dist = RectangleSpacingGuide.point_to_line_distance(point, line_p1, line_p2)
    print(f"   距离: {dist:.2f}")
    assert abs(dist - 50) < 0.01, f"期望 50，得到 {dist}"
    print("   ✓ 通过")
    
    # 测试 2.2: 点到竖直线的距离
    print("\n2.2 点到竖直线的距离")
    point = QPointF(50, 50)
    line_p1 = QPointF(0, 0)
    line_p2 = QPointF(0, 100)
    dist = RectangleSpacingGuide.point_to_line_distance(point, line_p1, line_p2)
    print(f"   距离: {dist:.2f}")
    assert abs(dist - 50) < 0.01, f"期望 50，得到 {dist}"
    print("   ✓ 通过")
    
    # 测试 2.3: 点到斜线的距离
    print("\n2.3 点到斜线的距离 (45°)")
    point = QPointF(50, 50)
    line_p1 = QPointF(0, 0)
    line_p2 = QPointF(100, 100)
    dist = RectangleSpacingGuide.point_to_line_distance(point, line_p1, line_p2)
    print(f"   距离: {dist:.2f}")
    # 点 (50, 50) 在直线 y=x 上，距离应该是 0
    assert abs(dist) < 0.01, f"期望 0，得到 {dist}"
    print("   ✓ 通过")
    
    print("\n✓ 点到直线距离计算测试全部通过！\n")


def test_parallel_lines():
    """测试平行线检测"""
    print("=" * 60)
    print("测试 3: 平行线检测")
    print("=" * 60)
    
    # 测试 3.1: 平行的水平线
    print("\n3.1 平行的水平线")
    p1 = QPointF(0, 0)
    p2 = QPointF(100, 0)
    p3 = QPointF(0, 50)
    p4 = QPointF(100, 50)
    is_parallel = RectangleSpacingGuide.are_lines_parallel(p1, p2, p3, p4)
    print(f"   平行: {is_parallel}")
    assert is_parallel, "期望平行"
    print("   ✓ 通过")
    
    # 测试 3.2: 平行的竖直线
    print("\n3.2 平行的竖直线")
    p1 = QPointF(0, 0)
    p2 = QPointF(0, 100)
    p3 = QPointF(50, 0)
    p4 = QPointF(50, 100)
    is_parallel = RectangleSpacingGuide.are_lines_parallel(p1, p2, p3, p4)
    print(f"   平行: {is_parallel}")
    assert is_parallel, "期望平行"
    print("   ✓ 通过")
    
    # 测试 3.3: 不平行的线
    print("\n3.3 不平行的线")
    p1 = QPointF(0, 0)
    p2 = QPointF(100, 0)
    p3 = QPointF(0, 0)
    p4 = QPointF(0, 100)
    is_parallel = RectangleSpacingGuide.are_lines_parallel(p1, p2, p3, p4)
    print(f"   平行: {is_parallel}")
    assert not is_parallel, "期望不平行"
    print("   ✓ 通过")
    
    print("\n✓ 平行线检测测试全部通过！\n")


def test_shape_edges():
    """测试获取形状的边"""
    print("=" * 60)
    print("测试 4: 获取形状的边")
    print("=" * 60)
    
    # 测试 4.1: 矩形的边
    print("\n4.1 矩形的边")
    rect = Shape(shape_type="rectangle")
    rect.points = [QPointF(0, 0), QPointF(100, 0), QPointF(100, 100), QPointF(0, 100)]
    edges = RectangleSpacingGuide.get_shape_edges(rect)
    print(f"   边数: {len(edges)}")
    assert len(edges) == 4, f"期望 4 条边，得到 {len(edges)}"
    print("   ✓ 通过")
    
    # 测试 4.2: 旋转矩形的边
    print("\n4.2 旋转矩形的边")
    rot = Shape(shape_type="rotation")
    rot.points = [QPointF(0, 0), QPointF(100, 0), QPointF(100, 100), QPointF(0, 100)]
    rot.direction = math.pi / 4
    edges = RectangleSpacingGuide.get_shape_edges(rot)
    print(f"   边数: {len(edges)}")
    assert len(edges) == 4, f"期望 4 条边，得到 {len(edges)}"
    print("   ✓ 通过")
    
    print("\n✓ 获取形状的边测试全部通过！\n")


if __name__ == '__main__':
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "  矩形间距线功能测试".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    try:
        test_rectangle_type_detection()
        test_point_to_line_distance()
        test_parallel_lines()
        test_shape_edges()
        
        print("=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
        print()
        
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

