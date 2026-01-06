import json
import math
import base64
import os
from pathlib import Path
from PIL import Image


def convert_manga_translator_folder_to_anylabel(input_folder, output_folder=None, text_mode='both'):
    """
    批量将 manga-translator-ui 的 JSON 标注文件夹转换为 X-AnyLabeling 的 .json 标注文件。
    
    Args:
        input_folder: manga-translator JSON 文件夹路径
        output_folder: 输出文件夹路径（可选，默认输出到输入文件夹）
        text_mode: 文本导入模式
            - 'source': 仅导入原文 (text 字段)
            - 'target': 仅导入译文 (translation 字段)
            - 'both': 导入原文/译文 (默认)
    
    Returns:
        (成功数, 失败数, 输出文件列表)
    """
    input_path = Path(input_folder)
    output_path = Path(output_folder) if output_folder else input_path
    
    if not input_path.exists():
        print(f"错误：输入文件夹不存在 '{input_folder}'")
        return 0, 0, []
    
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 查找所有 *_translations.json 文件
    json_files = list(input_path.glob('*_translations.json'))
    if not json_files:
        # 也尝试查找普通 json 文件
        json_files = list(input_path.glob('*.json'))
    
    if not json_files:
        print(f"未找到任何 JSON 文件")
        return 0, 0, []
    
    print(f"找到 {len(json_files)} 个 JSON 文件")
    
    success_count = 0
    fail_count = 0
    output_files = []
    
    for json_file in json_files:
        try:
            result = convert_manga_translator_to_anylabel(
                str(json_file), 
                output_folder=str(output_path),
                text_mode=text_mode
            )
            if result:
                success_count += 1
                output_files.extend(result)
            else:
                fail_count += 1
        except Exception as e:
            print(f"  [错误] 处理 {json_file.name} 失败: {e}")
            fail_count += 1
    
    return success_count, fail_count, output_files


def convert_manga_translator_to_anylabel(mt_json_path, output_folder=None, text_mode='both'):
    """
    将 manga-translator-ui 的 JSON 标注文件转换为 X-AnyLabeling 的 .json 标注文件。
    
    Args:
        mt_json_path: manga-translator JSON 文件路径
        output_folder: 输出文件夹路径（可选，默认输出到输入文件所在目录）
        text_mode: 文本导入模式
            - 'source': 仅导入原文 (text 字段)
            - 'target': 仅导入译文 (translation 字段)
            - 'both': 导入原文/译文 (默认)
    
    Returns:
        转换后的文件路径列表
    """
    try:
        with open(mt_json_path, 'r', encoding='utf-8') as f:
            mt_data = json.load(f)
    except FileNotFoundError:
        print(f"错误：找不到文件 '{mt_json_path}'")
        return []
    except json.JSONDecodeError:
        print(f"错误：文件 '{mt_json_path}' 不是有效的JSON格式。")
        return []

    base_dir = Path(mt_json_path).parent
    out_dir = Path(output_folder) if output_folder else base_dir
    output_files = []
    
    # manga-translator JSON 格式: {image_path: {regions: [...], original_width, original_height, ...}}
    for image_key, data in mt_data.items():
        # 获取图片文件名
        image_path = Path(image_key)
        img_name = image_path.name
        
        # 获取图片尺寸
        width = data.get('original_width', 0)
        height = data.get('original_height', 0)
        
        if width == 0 or height == 0:
            # 尝试从图片文件读取尺寸
            possible_image_path = base_dir / img_name
            if possible_image_path.exists():
                try:
                    with Image.open(possible_image_path) as img:
                        width, height = img.size
                except Exception:
                    pass
        
        regions = data.get('regions', [])
        if not regions:
            print(f"  [跳过] 没有区域数据：{img_name}")
            continue
        
        shapes = []
        group_id_counter = 1
        
        for region in regions:
            # 获取方向作为标签
            direction = region.get('direction', 'h')
            label = f"text_{direction}"  # text_v 或 text_h
            
            # 获取完整文本
            full_source = region.get('text', '')
            full_target = region.get('translation', '')
            texts = region.get('texts', [])
            
            # 从 lines 构建边界框
            lines = region.get('lines', [])
            if not lines:
                continue
            
            current_group_id = group_id_counter
            group_id_counter += 1
            
            # 为每个 line 创建一个小框
            for i, line in enumerate(lines):
                if len(line) < 4:
                    continue
                
                # 获取这一行的原文
                source_text = texts[i] if i < len(texts) else ''
                
                # 根据 text_mode 构建 description
                if text_mode == 'source':
                    description = source_text
                elif text_mode == 'target':
                    description = full_target if i == 0 else ''
                else:  # text_mode == 'both'
                    if i == 0 and full_source and full_target:
                        description = f"{full_source}/{full_target}"
                    elif i == 0 and full_target:
                        description = f"{source_text}/{full_target}"
                    else:
                        description = source_text
                
                # line 是四个角点，直接使用原始坐标
                points = [[p[0], p[1]] for p in line]
                
                shape = {
                    "label": label,
                    "score": region.get('prob', None),
                    "points": points,
                    "group_id": current_group_id,  # 同一 region 的框用相同 group_id
                    "description": description,
                    "difficult": False,
                    "shape_type": "rectangle",
                    "flags": {},
                    "attributes": {
                        "source_lang": region.get('source_lang', ''),
                        "target_lang": region.get('target_lang', ''),
                        "font_size": region.get('font_size', 0),
                        "alignment": region.get('alignment', ''),
                        "fg_colors": region.get('fg_colors', [0, 0, 0]),
                        "bg_colors": region.get('bg_colors', [255, 255, 255]),
                        "line_spacing": region.get('line_spacing', 1.0),
                        "stroke_width": region.get('stroke_width', 0.07),
                        "stroke_color_type": region.get('stroke_color_type', 'white'),
                        "adjust_bg_color": region.get('adjust_bg_color', True),
                    },
                    "kie_linking": [],
                    "is_edited": False
                }
                shapes.append(shape)
        
        if not shapes:
            print(f"  [跳过] 没有有效的形状：{img_name}")
            continue
        
        anylabel_data = {
            "version": "3.2.2",
            "flags": {},
            "shapes": shapes,
            "imagePath": img_name,
            "imageData": None,
            "imageHeight": height,
            "imageWidth": width,
            "manually_edited": False,
            "description": ""
        }
        
        output_file = out_dir / f"{Path(img_name).stem}.json"
        with open(output_file, 'w', encoding='utf-8') as out_f:
            json.dump(anylabel_data, out_f, ensure_ascii=False, indent=2)
        print(f"  [完成] 生成标注：{output_file.name}")
        output_files.append(str(output_file))
    
    return output_files


def convert_anylabel_folder_to_manga_translator(input_folder, output_folder=None, text_mode='both', excluded_labels=None):
    """
    批量将 X-AnyLabeling 的 .json 标注文件夹转换为 manga-translator-ui 的 JSON 格式。
    只处理有对应图片的 JSON 文件。
    
    Args:
        input_folder: X-AnyLabeling JSON 文件夹路径
        output_folder: 输出文件夹路径（可选，默认输出到输入文件夹）
        text_mode: 文本导出模式
            - 'source': description 作为原文
            - 'target': description 作为译文
            - 'both': 尝试解析 "原文/译文" 格式
        excluded_labels: 要排除的标签列表
    
    Returns:
        (成功数, 失败数, 输出文件列表)
    """
    input_path = Path(input_folder)
    output_path = Path(output_folder) if output_folder else input_path
    
    if excluded_labels is None:
        excluded_labels = []
    
    if not input_path.exists():
        print(f"错误：输入文件夹不存在 '{input_folder}'")
        return 0, 0, []
    
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 常见图片扩展名
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff', '.tif'}
    
    # 查找所有 json 文件（排除 *_translations.json），且必须有对应图片
    json_files = []
    for f in input_path.glob('*.json'):
        if f.name.endswith('_translations.json'):
            continue
        # 检查是否有对应的图片文件
        stem = f.stem
        has_image = any((input_path / f"{stem}{ext}").exists() for ext in image_extensions)
        if has_image:
            json_files.append(f)
    
    if not json_files:
        print(f"未找到任何有对应图片的 JSON 文件")
        return 0, 0, []
    
    print(f"找到 {len(json_files)} 个有对应图片的 JSON 文件")
    
    success_count = 0
    fail_count = 0
    output_files = []
    
    for json_file in json_files:
        try:
            result = convert_anylabel_to_manga_translator(
                str(json_file),
                output_folder=str(output_path),
                text_mode=text_mode,
                excluded_labels=excluded_labels
            )
            if result:
                success_count += 1
                output_files.append(result)
            else:
                fail_count += 1
        except Exception as e:
            print(f"  [错误] 处理 {json_file.name} 失败: {e}")
            fail_count += 1
    
    return success_count, fail_count, output_files


def convert_anylabel_to_manga_translator(anylabel_json_path, output_folder=None, image_path=None, text_mode='both', excluded_labels=None):
    """
    将 X-AnyLabeling 的 .json 标注文件转换为 manga-translator-ui 的 JSON 格式。
    
    Args:
        anylabel_json_path: X-AnyLabeling JSON 文件路径
        output_folder: 输出文件夹路径（可选，默认输出到输入文件所在目录）
        image_path: 图片完整路径（可选，用于生成 manga-translator 格式的 key）
        text_mode: 文本导出模式
            - 'source': description 作为原文
            - 'target': description 作为译文
            - 'both': 尝试解析 "原文/译文" 格式
        excluded_labels: 要排除的标签列表
    
    Returns:
        转换后的文件路径
    """
    if excluded_labels is None:
        excluded_labels = []
        
    try:
        with open(anylabel_json_path, 'r', encoding='utf-8') as f:
            anylabel_data = json.load(f)
    except FileNotFoundError:
        print(f"错误：找不到文件 '{anylabel_json_path}'")
        return None
    except json.JSONDecodeError:
        print(f"错误：文件 '{anylabel_json_path}' 不是有效的JSON格式。")
        return None
    
    base_dir = Path(anylabel_json_path).parent
    out_dir = Path(output_folder) if output_folder else base_dir
    
    # 获取图片信息
    img_name = anylabel_data.get('imagePath', '')
    width = anylabel_data.get('imageWidth', 0)
    height = anylabel_data.get('imageHeight', 0)
    
    # 确定图片的完整路径作为 key
    if image_path:
        image_key = str(Path(image_path).resolve())
    else:
        image_key = str((base_dir / img_name).resolve())
    
    shapes = anylabel_data.get('shapes', [])
    
    # 按 group_id 分组
    grouped_shapes = {}
    ungrouped_shapes = []
    
    for shape in shapes:
        label = shape.get('label', '')
        if label in excluded_labels:
            continue
        points = shape.get('points', [])
        if len(points) < 4:
            continue
        
        group_id = shape.get('group_id')
        if group_id is not None:
            if group_id not in grouped_shapes:
                grouped_shapes[group_id] = []
            grouped_shapes[group_id].append(shape)
        else:
            ungrouped_shapes.append(shape)
    
    regions = []
    
    # 处理分组的 shapes - 合并成一个 region
    for group_id, group in grouped_shapes.items():
        if not group:
            continue
        
        # 收集所有 lines 和 texts
        lines = []
        texts = []
        full_source = ''
        full_target = ''
        first_shape = group[0]
        
        # 先从第一个框获取完整原文和译文
        first_desc = first_shape.get('description', '') or ''
        if text_mode == 'both' and '/' in first_desc:
            parts = first_desc.split('/', 1)
            full_source = parts[0]
            full_target = parts[1] if len(parts) > 1 else ''
        elif text_mode == 'source':
            full_source = first_desc
        elif text_mode == 'target':
            full_target = first_desc
        else:
            full_source = first_desc
        
        for i, shape in enumerate(group):
            points = shape.get('points', [])
            lines.append([[float(p[0]), float(p[1])] for p in points])
            
            description = shape.get('description', '') or ''
            
            # 每行的原文：如果有 / 就取前面部分，否则取整个
            if description:
                if '/' in description:
                    texts.append(description.split('/')[0])
                else:
                    texts.append(description)
            else:
                texts.append('')
        
        # 从标签推断方向
        label = first_shape.get('label', '')
        if 'text_v' in label.lower() or label.lower() == 'v':
            direction = 'v'
        elif 'text_h' in label.lower() or label.lower() == 'h':
            direction = 'h'
        else:
            direction = 'v'
        
        attributes = first_shape.get('attributes', {}) or {}
        
        region = {
            "lines": lines,
            "texts": texts,
            "text": full_source,
            "translation": full_target,
            "angle": 0,
            "font_size": attributes.get('font_size', 30) or 30,
            "fg_colors": attributes.get('fg_colors', [0, 0, 0]) or [0, 0, 0],
            "bg_colors": attributes.get('bg_colors', [255, 255, 255]) or [255, 255, 255],
            "direction": direction,
            "alignment": attributes.get('alignment', 'left') or 'left',
            "target_lang": attributes.get('target_lang', 'CHS') or 'CHS',
            "source_lang": attributes.get('source_lang', 'ja') or 'ja',
            "line_spacing": attributes.get('line_spacing', 1.0) or 1.0,
            "stroke_width": attributes.get('stroke_width', 0.07) or 0.07,
            "stroke_color_type": attributes.get('stroke_color_type', 'white') or 'white',
            "adjust_bg_color": attributes.get('adjust_bg_color', True),
            "prob": first_shape.get('score', 0.9) or 0.9
        }
        regions.append(region)
    
    # 处理未分组的 shapes - 每个单独一个 region
    for shape in ungrouped_shapes:
        points = shape.get('points', [])
        description = shape.get('description', '') or ''
        
        source_text = ''
        target_text = ''
        if text_mode == 'source':
            source_text = description
        elif text_mode == 'target':
            target_text = description
        else:
            if '/' in description:
                parts = description.split('/', 1)
                source_text = parts[0]
                target_text = parts[1] if len(parts) > 1 else ''
            else:
                source_text = description
        
        label = shape.get('label', '')
        if 'text_v' in label.lower():
            direction = 'v'
        elif 'text_h' in label.lower():
            direction = 'h'
        else:
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            direction = 'v' if h > w else 'h'
        
        attributes = shape.get('attributes', {}) or {}
        
        region = {
            "lines": [[[float(p[0]), float(p[1])] for p in points]],
            "texts": [source_text] if source_text else [],
            "text": source_text,
            "translation": target_text,
            "angle": 0,
            "font_size": attributes.get('font_size', 30) or 30,
            "fg_colors": attributes.get('fg_colors', [0, 0, 0]) or [0, 0, 0],
            "bg_colors": attributes.get('bg_colors', [255, 255, 255]) or [255, 255, 255],
            "direction": direction,
            "alignment": attributes.get('alignment', 'left') or 'left',
            "target_lang": attributes.get('target_lang', 'CHS') or 'CHS',
            "source_lang": attributes.get('source_lang', 'ja') or 'ja',
            "line_spacing": attributes.get('line_spacing', 1.0) or 1.0,
            "stroke_width": attributes.get('stroke_width', 0.07) or 0.07,
            "stroke_color_type": attributes.get('stroke_color_type', 'white') or 'white',
            "adjust_bg_color": attributes.get('adjust_bg_color', True),
            "prob": shape.get('score', 0.9) or 0.9
        }
        regions.append(region)
    
    if not regions:
        print(f"  [跳过] 没有有效的区域：{img_name}")
        return None
    
    mt_data = {
        image_key: {
            "regions": regions,
            "original_width": width,
            "original_height": height
        }
    }
    
    # 输出文件名
    output_file = out_dir / f"{Path(img_name).stem}_translations.json"
    with open(output_file, 'w', encoding='utf-8') as out_f:
        json.dump(mt_data, out_f, ensure_ascii=False, indent=4)
    print(f"  [完成] 生成 manga-translator 标注：{output_file.name}")
    
    return str(output_file)


def convert_itp_to_anylabel(itp_json_path, text_mode='both'):
    """
    将 ImageTrans 的 .itp 项目文件转换为多个 X-AnyLabeling 的 .json 标注文件。
    *** 新版本: 支持对带有 "degree" 字段的 box 进行旋转变换，生成精确的旋转框。***
    
    Args:
        itp_json_path: ImageTrans 项目文件路径
        text_mode: 文本导入模式
            - 'source': 仅导入原文 (text 字段)
            - 'target': 仅导入译文 (target 字段)
            - 'both': 导入原文/译文 (默认)
    """
    try:
        base_dir = Path(itp_json_path).parent
        with open(itp_json_path, 'r', encoding='utf-8') as f:
            itp_data = json.load(f)
    except FileNotFoundError:
        print(f"错误：找不到文件 '{itp_json_path}'")
        return
    except json.JSONDecodeError:
        print(f"错误：文件 '{itp_json_path}' 不是有效的JSON格式。")
        return

    images = itp_data.get("images", {})
    if not images:
        print("未在 .itp 文件中找到任何 'images' 数据。")
        return

    print(f"开始转换 {len(images)} 张图片的标注...")
    
    for img_name, data in images.items():
        image_path = base_dir / img_name
        if not image_path.exists():
            print(f"  [跳过] 图片不存在：{img_name}")
            continue

        try:
            with Image.open(image_path) as img:
                width, height = img.size
        except Exception as e:
            print(f"  [跳过] 无法打开图片 {img_name}: {e}")
            continue

        shapes = []
        for box in data.get("boxes", []):
            geo = box.get("geometry", {})
            x, y = geo.get("X", 0), geo.get("Y", 0)
            w, h = geo.get("width", 0), geo.get("height", 0)
            
            # 根据 text_mode 处理文本内容
            source_text = box.get("text", "")
            target_text = box.get("target", "")
            
            if text_mode == 'source':
                description = source_text
            elif text_mode == 'target':
                description = target_text
            else:  # text_mode == 'both'
                if source_text and target_text:
                    description = f"{source_text}/{target_text}"
                elif source_text:
                    description = source_text
                elif target_text:
                    description = target_text
                else:
                    description = ""
            
            label = box.get("fontstyle", "unknown")
            degree = box.get("degree", 0)

            shape_type = "rectangle"
            points = []
            direction = 0.0

            if degree != 0:
                shape_type = "rotation"
                angle_rad = math.radians(degree)
                direction = angle_rad

                center_x = x + w / 2
                center_y = y + h / 2

                unrotated_points = [
                    (-w / 2, -h / 2),
                    (w / 2, -h / 2),
                    (w / 2, h / 2),
                    (-w / 2, h / 2)
                ]

                cos_a = math.cos(angle_rad)
                sin_a = math.sin(angle_rad)
                
                for px, py in unrotated_points:
                    rotated_x = px * cos_a - py * sin_a
                    rotated_y = px * sin_a + py * cos_a
                    
                    final_x = center_x + rotated_x
                    final_y = center_y + rotated_y
                    points.append([final_x, final_y])
            else:
                shape_type = "rectangle"
                points = [
                    [x, y],
                    [x + w, y],
                    [x + w, y + h],
                    [x, y + h]
                ]

            shape = {
                "label": label,
                "score": None,
                "points": points,
                "group_id": None,
                "description": description,
                "difficult": False,
                "shape_type": shape_type,
                "flags": {},
                "attributes": {},
                "kie_linking": []
            }
            if shape_type == "rotation":
                shape["direction"] = direction

            shapes.append(shape)

        anylabel_data = {
            "version": "3.2.2",
            "flags": {},
            "shapes": shapes,
            "imagePath": img_name,
            "imageData": None,
            "imageHeight": height,
            "imageWidth": width,
            "description": ""
        }

        output_path = base_dir / f"{Path(img_name).stem}.json"
        with open(output_path, 'w', encoding='utf-8') as out_f:
            json.dump(anylabel_data, out_f, ensure_ascii=False, indent=2)
        print(f"  [完成] 生成标注：{output_path.name}")
