import json
import math
from pathlib import Path
from PIL import Image

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
