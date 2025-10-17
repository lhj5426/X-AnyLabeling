import os
import json
import copy
import math

def cross_product(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

def convex_hull(points):
    """
    Computes the convex hull of a set of 2D points using the Monotone Chain algorithm.
    Points are expected as a list of [x, y] lists.
    """
    if len(points) <= 2:
        return points

    # Sort points lexicographically
    points.sort()

    # Build lower hull
    lower = []
    for p in points:
        while len(lower) >= 2 and cross_product(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    # Build upper hull
    upper = []
    for p in reversed(points):
        while len(upper) >= 2 and cross_product(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    # Concatenation of the lower and upper hulls
    # Last point of lower hull is the same as first point of upper hull
    # Last point of upper hull is the same as first point of lower hull
    return lower[:-1] + upper[:-1]

def dot_product(v1, v2):
    return v1[0] * v2[0] + v1[1] * v2[1]

def normalize_vector(v):
    length = math.sqrt(v[0]**2 + v[1]**2)
    if length == 0: return (0, 0)
    return (v[0] / length, v[1] / length)

def perpendicular_vector(v):
    return (-v[1], v[0])

def get_bounding_box(shape):
    """
    根据 shape['points'] 计算外接矩形 [x_min, y_min, x_max, y_max]。
    """
    points = shape['points']
    x_coords = [p[0] for p in points]
    y_coords = [p[1] for p in points]
    return [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]

def get_mabr_from_points(points):
    """
    Computes the Minimum Area Bounding Rectangle (MABR) for a set of 2D points.
    Returns: (center_x, center_y, width, height, angle_radians)
    """
    if len(points) <= 1:
        # Handle single point or empty list
        if not points: return 0, 0, 0, 0, 0
        p = points[0]
        return p[0], p[1], 0, 0, 0

    hull_points = convex_hull(points)
    if len(hull_points) <= 1:
        p = hull_points[0]
        return p[0], p[1], 0, 0, 0

    min_area = float('inf')
    mabr_params = None # (center_x, center_y, width, height, angle_radians)

    for i in range(len(hull_points)):
        p1 = hull_points[i]
        p2 = hull_points[(i + 1) % len(hull_points)]

        # Edge vector
        edge_vec = (p2[0] - p1[0], p2[1] - p1[1])
        edge_len = math.sqrt(edge_vec[0]**2 + edge_vec[1]**2)
        if edge_len == 0: continue

        # Normalized edge vector (axis of the potential MABR)
        axis = (edge_vec[0] / edge_len, edge_vec[1] / edge_len)
        # Perpendicular axis
        perp_axis = (-axis[1], axis[0])

        # Project all hull points onto both axes
        min_proj_axis = float('inf')
        max_proj_axis = float('-inf')
        min_proj_perp = float('inf')
        max_proj_perp = float('-inf')

        for p in hull_points:
            proj_axis = dot_product(p, axis)
            proj_perp = dot_product(p, perp_axis)

            min_proj_axis = min(min_proj_axis, proj_axis)
            max_proj_axis = max(max_proj_axis, proj_axis)
            min_proj_perp = min(min_proj_perp, proj_perp)
            max_proj_perp = max(max_proj_perp, proj_perp)

        width = max_proj_axis - min_proj_axis
        height = max_proj_perp - min_proj_perp
        area = width * height

        if area < min_area:
            min_area = area
            
            # Calculate angle of the MABR
            angle_radians = math.atan2(axis[1], axis[0])
            if angle_radians < 0: angle_radians += 2 * math.pi # Normalize to [0, 2*pi)

            # Calculate center of the MABR in the rotated coordinate system
            x_c_rot = min_proj_axis + width / 2
            y_c_rot = min_proj_perp + height / 2
            
            # Convert center back to original coordinate system (rotate by -angle_radians)
            center_orig_x = x_c_rot * math.cos(angle_radians) - y_c_rot * math.sin(angle_radians)
            center_orig_y = x_c_rot * math.sin(angle_radians) + y_c_rot * math.cos(angle_radians)

            mabr_params = (center_orig_x, center_orig_y, width, height, angle_radians)

    if mabr_params is None:
        # Fallback to AABB if MABR calculation fails (e.g., degenerate hull)
        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]
        x_min, y_min, x_max, y_max = min(x_coords), min(y_coords), max(x_coords), max(y_coords)
        center_x = (x_min + x_max) / 2.0
        center_y = (y_min + y_max) / 2.0
        width = x_max - x_min
        height = y_max - y_min
        angle_radians = 0.0
        return center_x, center_y, width, height, angle_radians

    return mabr_params

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

def create_shape_from_box(box, shape1, shape2, config, output_shape_type="rectangle"):
    # 检查输入参数是否为None
    if shape1 is None or shape2 is None:
        raise ValueError("shape1 and shape2 cannot be None")

    new_shape = copy.deepcopy(shape1)
    x_min, y_min, x_max, y_max = box

    if output_shape_type == "rotation":
        all_points = shape1['points'] + shape2['points']
        center_x, center_y, width, height, mab_angle_radians = get_mabr_from_points(all_points)

        # Determine final angle: preserve angle if all input shapes have the same angle, else use MABR angle
        final_angle = mab_angle_radians
        if shape1.get('direction') == shape2.get('direction'):
            final_angle = shape1.get('direction', 0)

        # Calculate the four corner points of the rotated rectangle
        cos_angle = math.cos(final_angle)
        sin_angle = math.sin(final_angle)
        half_w = width / 2
        half_h = height / 2

        corners = [
            [-half_w, -half_h],  # Top-left relative to center
            [half_w, -half_h],   # Top-right relative to center
            [half_w, half_h],    # Bottom-right relative to center
            [-half_w, half_h]    # Bottom-left relative to center
        ]

        rotated_points = []
        for dx, dy in corners:
            rotated_x = dx * cos_angle - dy * sin_angle + center_x
            rotated_y = dx * sin_angle + dy * cos_angle + center_y
            rotated_points.append([rotated_x, rotated_y])

        new_shape['points'] = rotated_points
        new_shape['shape_type'] = 'rotation'
        new_shape['direction'] = final_angle
    else: # output_shape_type == "rectangle"
        # 普通矩形保持轴对齐
        new_shape['points'] = [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]
        new_shape['shape_type'] = 'rectangle'

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

    output_shape_type = config.get("OUTPUT_SHAPE_TYPE", "rectangle")
    # Filter shapes based on the selected output type
    shapes = [s for s in shapes if s.get("shape_type") == output_shape_type]

    if not shapes:
        return [], 0

    # Use a Disjoint Set Union (DSU) data structure
    parent = list(range(len(shapes)))
    def find(i):
        if parent[i] == i:
            return i
        parent[i] = find(parent[i])
        return parent[i]

    def union(i, j):
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            parent[root_j] = root_i
            return True
        return False

    # Build the graph of mergeable shapes
    for i in range(len(shapes)):
        for j in range(i + 1, len(shapes)):
            if find(i) != find(j):
                if can_merge_shapes(shapes[i], shapes[j], mode, config):
                    union(i, j)

    # Group shapes by their root parent
    groups = {}
    for i in range(len(shapes)):
        root = find(i)
        if root not in groups:
            groups[root] = []
        groups[root].append(i)

    # Merge shapes in each group
    final_shapes = []
    total_merge_count = 0
    for root_index in groups:
        indices = groups[root_index]
        if len(indices) == 1:
            final_shapes.append(shapes[indices[0]])
        else:
            group_shapes = [shapes[i] for i in indices]
            
            # --- Start of new group merge logic ---

            # Determine the final label for the group first
            final_label = ''
            if group_shapes:
                # The sorting for label merging itself doesn't matter, so we can pre-calculate the final label
                temp_label = group_shapes[0].get('label', '')
                for i in range(1, len(group_shapes)):
                    temp_label = merge_labels(temp_label, group_shapes[i].get('label', ''), config.get("LABEL_MERGE_STRATEGY", "FIRST"))
                final_label = temp_label

            # Determine reading direction based on the final label
            per_label_directions = config.get("PER_LABEL_DIRECTIONS", {})
            default_direction = config.get("READING_DIRECTION", "LTR")
            reading_direction = per_label_directions.get(final_label, default_direction)

            # Sort shapes based on the determined reading direction to merge descriptions correctly
            if reading_direction == "RTL":  # Right-to-Left
                group_shapes.sort(key=lambda s: get_bounding_box(s)[0], reverse=True)
            elif reading_direction == "TTB":  # Top-to-Bottom
                group_shapes.sort(key=lambda s: get_bounding_box(s)[1])
            else:  # "LTR" (Left-to-Right)
                group_shapes.sort(key=lambda s: get_bounding_box(s)[0])

            # Merge descriptions and labels from the sorted group
            final_description = "".join(s.get('description', '').strip() for s in group_shapes if s.get('description'))
            
            # The final_label is already calculated

            # Collect all points from all shapes in the group
            all_points = [p for shape in group_shapes for p in shape['points']]
            if not all_points:
                continue

            # Create the new merged shape from scratch
            merged_shape = copy.deepcopy(group_shapes[0]) # Use first shape as a template for flags etc.
            merged_shape['label'] = final_label
            merged_shape['description'] = final_description

            if output_shape_type == "rotation":
                # Check if all shapes in the group have the same direction
                first_direction = group_shapes[0].get('direction')
                all_same_direction = all(s.get('direction') == first_direction for s in group_shapes)

                center_x, center_y, width, height, mab_angle_radians = get_mabr_from_points(all_points)
                
                final_angle = mab_angle_radians
                if all_same_direction:
                    final_angle = first_direction if first_direction is not None else 0

                # Calculate corners for the new rotated rectangle
                cos_angle = math.cos(final_angle)
                sin_angle = math.sin(final_angle)
                half_w = width / 2
                half_h = height / 2
                corners = [[-half_w, -half_h], [half_w, -half_h], [half_w, half_h], [-half_w, half_h]]
                rotated_points = []
                for dx, dy in corners:
                    rotated_x = dx * cos_angle - dy * sin_angle + center_x
                    rotated_y = dx * sin_angle + dy * cos_angle + center_y
                    rotated_points.append([rotated_x, rotated_y])

                merged_shape['points'] = rotated_points
                merged_shape['shape_type'] = 'rotation'
                merged_shape['direction'] = final_angle
            else:  # "rectangle"
                x_coords = [p[0] for p in all_points]
                y_coords = [p[1] for p in all_points]
                merged_box = [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]
                merged_shape['points'] = [[merged_box[0], merged_box[1]], [merged_box[2], merged_box[1]], [merged_box[2], merged_box[3]], [merged_box[0], merged_box[3]]]
                merged_shape['shape_type'] = 'rectangle'
                if 'direction' in merged_shape:
                    merged_shape.pop('direction', None)
            
            final_shapes.append(merged_shape)
            total_merge_count += len(group_shapes) - 1
            
            # --- End of new group merge logic ---

    return final_shapes, total_merge_count

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
