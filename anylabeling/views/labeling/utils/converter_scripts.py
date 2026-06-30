import sys
import os
import json
import math
from pathlib import Path
from PIL import Image

def convert_ballons_to_anylabel(ballons_json_path, text_mode='both'):
    """
    将 BallonsTranslator 的项目文件转换为多个 X-AnyLabeling 的 .json 标注文件。
    
    导入内容：
      - description: 原文 (text 字段)
      - translation: 译文 (translation 字段)
      - attributes.fg: 文字颜色 (fontformat.frgb)
      - attributes.bg: 背景颜色 (fontformat.srgb)
      - label: 标签类型 (label 字段)
      - points: 坐标 (xyxy / _bounding_rect + angle)
    
    Args:
        ballons_json_path: BallonsTranslator 项目文件路径
        text_mode: 文本导入模式（保留向后兼容，已不再区分）
            - 'source': 仅原文作为 description
            - 'target': 仅译文作为 description
            - 'both': 原文→description, 译文→translation (默认)
    """
    try:
        base_dir = Path(ballons_json_path).parent
        with open(ballons_json_path, 'r', encoding='utf-8') as f:
            ballons_data = json.load(f)
    except FileNotFoundError:
        print(f"错误：找不到文件 '{ballons_json_path}'")
        return
    except json.JSONDecodeError:
        print(f"错误：文件 '{ballons_json_path}' 不是有效的JSON格式。")
        return

    pages = ballons_data.get('pages', {})
    if not pages:
        print("未在文件中找到任何 'pages' 数据。")
        return
    
    print(f"开始转换 {len(pages)} 张图片的标注...")

    for img_name, items in pages.items():
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
        for item in items:
            # 提取文本内容
            source_text = ''.join(item.get('text', []))
            target_text = item.get('translation', '')
            
            if text_mode == 'source':
                description = source_text
                translation = ""
            elif text_mode == 'target':
                description = target_text
                translation = ""
            else:  # text_mode == 'both'
                description = source_text
                translation = target_text

            # 提取颜色信息: fontformat.frgb→fg, fontformat.srgb→bg
            fontformat = item.get('fontformat', {})
            fg_color = fontformat.get('frgb', None)
            bg_color = fontformat.get('srgb', None)
            
            attrs = {}
            if fg_color and isinstance(fg_color, (list, tuple)) and len(fg_color) >= 3:
                attrs['fg'] = [int(c) for c in fg_color[:3]]
            if bg_color and isinstance(bg_color, (list, tuple)) and len(bg_color) >= 3:
                attrs['bg'] = [int(c) for c in bg_color[:3]]

            # --- 几何信息处理 ---
            # 优先使用 xyxy (原始外接矩形)，_bounding_rect 可能被 BT 重新计算过
            angle_deg = item.get('angle', 0)
            
            rect = item.get('xyxy')  # [x1, y1, x2, y2]
            if rect:
                rect = [rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1]]
            if not rect:
                rect = item.get('_bounding_rect')  # [x, y, w, h]

            if not rect:
                print(f"  [警告] 在 {img_name} 中找到无效的几何数据，已跳过。")
                continue

            x, y, w, h = rect
            
            shape_type = "rectangle"
            points = []
            direction = 0.0

            if angle_deg != 0:
                shape_type = "rotation"
                angle_rad = math.radians(angle_deg)
                direction = angle_rad

                center_x = x + w / 2
                center_y = y + h / 2

                unrotated_points = [
                    (-w / 2, -h / 2), (w / 2, -h / 2),
                    (w / 2, h / 2), (-w / 2, h / 2)
                ]

                cos_a = math.cos(angle_rad)
                sin_a = math.sin(angle_rad)
                
                for px, py in unrotated_points:
                    final_x = center_x + (px * cos_a - py * sin_a)
                    final_y = center_y + (px * sin_a + py * cos_a)
                    points.append([final_x, final_y])
            else:
                shape_type = "rectangle"
                points = [
                    [x, y], [x + w, y],
                    [x + w, y + h], [x, y + h]
                ]

            shape = {
                "label": item.get("label") or "text_region", 
                "score": None,
                "points": points,
                "group_id": None,
                "description": description,
                "translation": translation,
                "difficult": False,
                "shape_type": shape_type,
                "flags": {},
                "attributes": attrs,
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