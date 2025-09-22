import os
import json
import copy
import math

def get_bounding_box(shape):
    """
    根据 shape['points'] 计算外接矩形 [x_min, y_min, x_max, y_max]。
    """
    points = shape['points']
    x_coords = [p[0] for p in points]
    y_coords = [p[1] for p in points]
    return [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]

def get_merge_group_for_label(label, config):
    if not config.get("USE_SPECIFIC_MERGE_GROUPS", False):
        return -1
    for idx, group in enumerate(config.get("SPECIFIC_MERGE_GROUPS", [])):
        if label in group:
            return idx
    return -1

def can_labels_merge(label1, label2, config):
    if label1 in config.get("LABELS_TO_EXCLUDE_FROM_MERGE", set()) or label2 in config.get("LABELS_TO_EXCLUDE_FROM_MERGE", set()):
        return False

    if config.get("USE_SPECIFIC_MERGE_GROUPS", False):
        g1 = get_merge_group_for_label(label1, config)
        g2 = get_merge_group_for_label(label2, config)
        return g1 != -1 and g1 == g2

    if config.get("REQUIRE_SAME_LABEL", False):
        return label1 == label2
    return True


def merge_labels(label1, label2, strategy):
    if strategy == "FIRST":
        return label1
    elif strategy == "COMBINE":
        return label1 if label1 == label2 else f"{label1}+{label2}"
    elif strategy == "PREFER_NON_DEFAULT":
        default_labels = {"label", ""}
        if label1 in default_labels and label2 not in default_labels:
            return label2
        if label2 in default_labels and label1 not in default_labels:
            return label1
        return label1
    elif strategy == "PREFER_SHORTER":
        if label1 == label2:
            return label1
        return label1 if len(label1) <= len(label2) else label2
    else:
        return label1

def create_shape_from_box(box, shape1, shape2, config):
    # 检查输入参数是否为None
    if shape1 is None or shape2 is None:
        raise ValueError("shape1 and shape2 cannot be None")

    new_shape = copy.deepcopy(shape1)
    x_min, y_min, x_max, y_max = box

    # 检查是否为旋转矩形，如果是则保持旋转状态
    if shape1.get('shape_type') == 'rotation':
        # 保持旋转矩形的角度和类型
        original_angle = shape1.get('direction', 0)
        center_x = (x_min + x_max) / 2
        center_y = (y_min + y_max) / 2
        width = x_max - x_min
        height = y_max - y_min

        # 根据原始角度计算旋转矩形的四个角点
        cos_angle = math.cos(original_angle)
        sin_angle = math.sin(original_angle)
        half_w = width / 2
        half_h = height / 2

        # 计算旋转后的四个角点
        corners = [
            [-half_w, -half_h],  # 左上
            [half_w, -half_h],   # 右上
            [half_w, half_h],    # 右下
            [-half_w, half_h]    # 左下
        ]

        rotated_points = []
        for dx, dy in corners:
            rotated_x = dx * cos_angle - dy * sin_angle + center_x
            rotated_y = dx * sin_angle + dy * cos_angle + center_y
            rotated_points.append([rotated_x, rotated_y])

        new_shape['points'] = rotated_points
        new_shape['shape_type'] = 'rotation'
        new_shape['direction'] = original_angle
    else:
        # 普通矩形保持轴对齐
        new_shape['points'] = [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]

    new_shape['label'] = merge_labels(shape1.get('label', ''), shape2.get('label', ''), config.get("LABEL_MERGE_STRATEGY", "FIRST"))

    # 合并文本内容 - 根据阅读方向决定合并顺序
    desc1 = shape1.get('description', '') or ''
    desc2 = shape2.get('description', '') or ''
    desc1 = desc1.strip() if desc1 else ''
    desc2 = desc2.strip() if desc2 else ''
    if desc1 and desc2:
        # 根据阅读方向合并文本
        reading_direction = config.get("READING_DIRECTION", "LTR")
        if reading_direction == "RTL":  # 从右到左（日文）
            # 比较x坐标，右边的文本在前
            box1 = get_bounding_box(shape1)
            box2 = get_bounding_box(shape2)
            if box1[0] > box2[0]:  # shape1在右边
                new_shape['description'] = desc1 + desc2
            else:  # shape2在右边
                new_shape['description'] = desc2 + desc1
        else:  # 从左到右（默认）
            # 比较x坐标，左边的文本在前
            box1 = get_bounding_box(shape1)
            box2 = get_bounding_box(shape2)
            if box1[0] < box2[0]:  # shape1在左边
                new_shape['description'] = desc1 + desc2
            else:  # shape2在左边
                new_shape['description'] = desc2 + desc1
    elif desc1:
        new_shape['description'] = desc1
    elif desc2:
        new_shape['description'] = desc2
    else:
        new_shape['description'] = ''

    return new_shape

def vertical_can_merge(box1, box2, params, advanced_options):
    eps = params.get("overlap_epsilon", 0.0)
    overlap_x = max(0.0, min(box1[2], box2[2]) - max(box1[0], box2[0]))
    overlap_x_adj = max(0.0, overlap_x + eps)
    width1 = max(0.0, box1[2] - box1[0])
    width2 = max(0.0, box2[2] - box2[0])
    min_width = max(1e-6, min(width1, width2))
    overlap_ratio_w = (overlap_x_adj / min_width) * 100.0
    vertical_gap = max(box1[1], box2[1]) - min(box1[3], box2[3])

    if advanced_options.get("debug_mode", False):
        print(f"      垂直判定: overlap_w={overlap_ratio_w:.2f}%, gap={vertical_gap:.3f}")

    if overlap_ratio_w < params["min_width_overlap_ratio"]:
        return False

    if advanced_options.get("allow_negative_gap", True):
        return vertical_gap <= params["max_vertical_gap"]
    else:
        return 0 <= vertical_gap <= params["max_vertical_gap"]

def horizontal_can_merge(box1, box2, params, advanced_options):
    eps = params.get("overlap_epsilon", 0.0)
    overlap_y = max(0.0, min(box1[3], box2[3]) - max(box1[1], box2[1]))
    overlap_y_adj = max(0.0, overlap_y + eps)
    height1 = max(0.0, box1[3] - box1[1])
    height2 = max(0.0, box2[3] - box2[1])
    min_height = max(1e-6, min(height1, height2))
    overlap_ratio_h = (overlap_y_adj / min_height) * 100.0
    horizontal_gap = max(box1[0], box2[0]) - min(box1[2], box2[2])

    if advanced_options.get("debug_mode", False):
        print(f"      水平判定: overlap_h={overlap_ratio_h:.2f}%, gap={horizontal_gap:.3f}")

    if overlap_ratio_h < params["min_height_overlap_ratio"]:
        return False

    if advanced_options.get("allow_negative_gap", True):
        return horizontal_gap <= params["max_horizontal_gap"]
    else:
        return 0 <= horizontal_gap <= params["max_horizontal_gap"]

def can_merge_shapes(shape1, shape2, mode, config):
    if not can_labels_merge(shape1.get('label', ''), shape2.get('label', ''), config):
        if config.get("ADVANCED_MERGE_OPTIONS", {}).get("debug_mode", False):
            print(f"    跳过: 标签规则不允许 -> {shape1.get('label','')} vs {shape2.get('label','')}")
        return False

    box1, box2 = get_bounding_box(shape1), get_bounding_box(shape2)

    if mode == "VERTICAL":
        return vertical_can_merge(box1, box2, config.get("VERTICAL_MERGE_PARAMS", {}), config.get("ADVANCED_MERGE_OPTIONS", {}))
    elif mode == "HORIZONTAL":
        return horizontal_can_merge(box1, box2, config.get("HORIZONTAL_MERGE_PARAMS", {}), config.get("ADVANCED_MERGE_OPTIONS", {}))
    return False

def perform_merge(shapes, mode, config):
    # 过滤掉None值
    shapes = [shape for shape in shapes if shape is not None]

    params = config.get("VERTICAL_MERGE_PARAMS", {}) if mode == "VERTICAL" else config.get("HORIZONTAL_MERGE_PARAMS", {})
    merge_count = 0
    while True:
        merged_in_pass = False
        i = 0
        while i < len(shapes):
            j = i + 1
            while j < len(shapes):
                shape1, shape2 = shapes[i], shapes[j]
                if can_merge_shapes(shape1, shape2, mode, config):
                    b1, b2 = get_bounding_box(shape1), get_bounding_box(shape2)
                    merged_box = [min(b1[0], b2[0]), min(b1[1], b2[1]), max(b1[2], b2[2]), max(b1[3], b2[3])]
                    new_shape = create_shape_from_box(merged_box, shape1, shape2, config)
                    shapes.pop(j)
                    shapes.pop(i)
                    shapes.insert(i, new_shape)
                    merge_count += 1
                    merged_in_pass = True
                    if config.get("ADVANCED_MERGE_OPTIONS", {}).get("debug_mode", False):
                        print(f"    合并: '{shape1.get('label','')}' + '{shape2.get('label','')}' -> '{new_shape.get('label','')}'")
                    break
                else:
                    j += 1
            if merged_in_pass:
                break
            else:
                i += 1
        if not merged_in_pass:
            break
    return shapes, merge_count

def process_file(file_path, config):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return False, f"读取文件失败: {e}"

    if 'shapes' not in data or not data['shapes']:
        return False, "文件中无标注框"

    initial_shapes = copy.deepcopy(data['shapes'])
    initial_count = len(initial_shapes)
    
    mode = config.get("MERGE_MODE", "NONE")
    if mode == "NONE":
        return False, "合并模式为NONE"

    total_merged = 0
    if mode == "VERTICAL":
        final_shapes, count = perform_merge(initial_shapes, "VERTICAL", config)
        total_merged += count
    elif mode == "HORIZONTAL":
        final_shapes, count = perform_merge(initial_shapes, "HORIZONTAL", config)
        total_merged += count
    elif mode == "VERTICAL_THEN_HORIZONTAL":
        temp, count1 = perform_merge(initial_shapes, "VERTICAL", config)
        final_shapes, count2 = perform_merge(temp, "HORIZONTAL", config)
        total_merged += (count1 + count2)
    elif mode == "HORIZONTAL_THEN_VERTICAL":
        temp, count1 = perform_merge(initial_shapes, "HORIZONTAL", config)
        final_shapes, count2 = perform_merge(temp, "VERTICAL", config)
        total_merged += (count1 + count2)
    else:
        final_shapes = initial_shapes

    if total_merged == 0:
        return False, "未发生任何合并"

    data['shapes'] = final_shapes
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        final_count = len(final_shapes)
        return True, f"处理完成: 框数 {initial_count} -> {final_count} (减少了 {initial_count - final_count} 个)"
    except Exception as e:
        return False, f"写入文件失败: {e}"
