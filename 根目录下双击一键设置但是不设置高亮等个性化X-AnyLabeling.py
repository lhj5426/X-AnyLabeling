import os

# === 公共路径 ===
root = os.path.dirname(os.path.abspath(__file__))

shape_path = os.path.join(root, "anylabeling", "views", "labeling", "shape.py")
canvas_path = os.path.join(root, "anylabeling", "views", "labeling", "widgets", "canvas.py")

print(f"跳过 shape.py 修改，保留原文件：{shape_path}")
print(f"开始处理 canvas.py 路径：{canvas_path}")

# === 修改 canvas.py ===
with open(canvas_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
i = 0

modified_move_speed = False
modified_large_rotation = False
modified_small_rotation = False
commented_tooltip_if_block = False
cleared_image_tooltip = 0
commented_multiline_tooltip_blocks = 0

while i < len(lines):
    line = lines[i]
    stripped = line.strip()

    # 替换常量值
    if stripped.startswith("MOVE_SPEED") and not modified_move_speed:
        new_lines.append("MOVE_SPEED = 0.5\n")
        modified_move_speed = True
        print("✔ 修改 MOVE_SPEED = 0.5")
        i += 1
        continue
    elif stripped.startswith("LARGE_ROTATION_INCREMENT") and not modified_large_rotation:
        new_lines.append("LARGE_ROTATION_INCREMENT = 0.0087\n")
        modified_large_rotation = True
        print("✔ 修改 LARGE_ROTATION_INCREMENT = 0.0087")
        i += 1
        continue
    elif stripped.startswith("SMALL_ROTATION_INCREMENT") and not modified_small_rotation:
        new_lines.append("SMALL_ROTATION_INCREMENT = 0.001745\n")
        modified_small_rotation = True
        print("✔ 修改 SMALL_ROTATION_INCREMENT = 0.001745")
        i += 1
        continue

    # 注释掉 tooltip if 块（多行）
    if stripped.startswith('if shape.group_id and shape.shape_type == "rectangle":') and not commented_tooltip_if_block:
        print("✔ 注释 tooltip if 块（最多10行）")
        commented_tooltip_if_block = True
        for _ in range(10):  # 最多注释10行
            if i >= len(lines):
                break
            current_line = lines[i]
            if current_line.strip():
                new_lines.append("# " + current_line)
            else:
                new_lines.append(current_line)
            i += 1
        continue

    # 清空 Image ToolTip
    if 'self.setToolTip(self.tr("Image"))' in stripped:
        cleared_image_tooltip += 1
        print(f"✔ 清空 Image ToolTip（第{cleared_image_tooltip}处）")
        new_lines.append(line.replace('"Image"', '""'))
        i += 1
        continue

    # 注释 tooltip 的多行结构（点形状提示）4行块
    if "self.setToolTip(" in stripped and i + 3 < len(lines):
        next1 = lines[i + 1].strip()
        next2 = lines[i + 2].strip()
        next3 = lines[i + 3].strip()

        if (
            "Click & drag to move point" in next1
            or "Click to create point" in next1
        ):
            commented_multiline_tooltip_blocks += 1
            print(f"✔ 注释多行 ToolTip 4行块（第{commented_multiline_tooltip_blocks}处）")
            new_lines.append("# " + line)
            new_lines.append("# " + lines[i + 1])
            new_lines.append("# " + lines[i + 2])
            new_lines.append("# " + lines[i + 3])
            i += 4
            continue

    # 正常行
    new_lines.append(line)
    i += 1

with open(canvas_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print(f"\ncanvas.py 修改完成：")
print(f"  - MOVE_SPEED 修改: {'是' if modified_move_speed else '否'}")
print(f"  - LARGE_ROTATION_INCREMENT 修改: {'是' if modified_large_rotation else '否'}")
print(f"  - SMALL_ROTATION_INCREMENT 修改: {'是' if modified_small_rotation else '否'}")
print(f"  - tooltip if 块注释: {'是' if commented_tooltip_if_block else '否'}")
print(f"  - Image ToolTip 清空次数: {cleared_image_tooltip}")
print(f"  - 多行 ToolTip 块注释次数: {commented_multiline_tooltip_blocks}\n")

print("🎉 所有个性化修改完成（已跳过 shape.py），祝你使用愉快！")
input("按回车键退出...")
