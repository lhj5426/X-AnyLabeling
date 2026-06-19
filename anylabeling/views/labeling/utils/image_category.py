import json
import os
import re
import shutil

from PyQt5 import QtGui, QtWidgets


IMAGE_CATEGORY_FIELD = "image_category"
UNCATEGORIZED_FOLDER = "未分类"


def digit_to_category(labeling_widget, digit):
    if labeling_widget is None:
        return None
    shortcuts = getattr(labeling_widget, "drawing_digit_shortcuts", {}) or {}
    data = shortcuts.get(digit, shortcuts.get(str(digit), None))
    if not isinstance(data, dict):
        return None
    label = data.get("label", "")
    label = label.strip() if isinstance(label, str) else ""
    return label or None


def read_image_category(image_path):
    json_path = os.path.splitext(image_path)[0] + ".json"
    if not os.path.exists(json_path):
        return ""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return ""
    value = data.get(IMAGE_CATEGORY_FIELD, "")
    return value.strip() if isinstance(value, str) else ""


def _image_size(path):
    reader = QtGui.QImageReader(path)
    size = reader.size()
    if size.isValid():
        return size.width(), size.height()
    return 0, 0


def set_image_category(image_path, category):
    json_path = os.path.splitext(image_path)[0] + ".json"
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return False
    else:
        width, height = _image_size(image_path)
        data = {
            "version": "3.2.2",
            "flags": {},
            "shapes": [],
            "imagePath": os.path.basename(image_path),
            "imageData": None,
            "imageHeight": height,
            "imageWidth": width,
            "description": "",
            "manually_edited": False,
        }

    data[IMAGE_CATEGORY_FIELD] = category or ""
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        return False
    return True


def category_badge_text(image_path):
    category = read_image_category(image_path)
    return category if category else ""


def apply_digit_category(labeling_widget, image_path, digit):
    category = digit_to_category(labeling_widget, digit)
    if not category or not image_path:
        return False, ""

    current_category = read_image_category(image_path)
    new_category = "" if current_category == category else category
    if not set_image_category(image_path, new_category):
        return False, ""
    return True, new_category


def safe_folder_name(name):
    value = name.strip() if isinstance(name, str) else ""
    if not value:
        value = UNCATEGORIZED_FOLDER
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = value.rstrip(" .")
    return value or UNCATEGORIZED_FOLDER


def unique_destination_path(folder, filename):
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(folder, filename)
    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(folder, f"{base}_{counter}{ext}")
        counter += 1
    return candidate


def export_images_by_category(parent, image_list, output_dir):
    copied = 0
    failed = 0
    category_counts = {}
    for image_path in image_list:
        category = read_image_category(image_path) or UNCATEGORIZED_FOLDER
        folder_name = safe_folder_name(category)
        category_dir = os.path.join(output_dir, folder_name)
        os.makedirs(category_dir, exist_ok=True)
        dst = unique_destination_path(category_dir, os.path.basename(image_path))
        try:
            shutil.copy2(image_path, dst)
            copied += 1
            category_counts[folder_name] = category_counts.get(folder_name, 0) + 1
        except Exception:
            failed += 1
    return copied, failed, category_counts


def show_category_popup(parent, image_path, category):
    return


def category_badge_colors(labeling_widget, category):
    fallback_bg = QtGui.QColor(40, 30, 10, 220)
    fallback_fg = QtGui.QColor(255, 226, 126)
    if not labeling_widget or not category:
        return fallback_bg, fallback_fg

    try:
        rgb = labeling_widget._get_rgb_by_label(category)
    except Exception:
        rgb = None
    if not rgb or len(rgb) < 3:
        return fallback_bg, fallback_fg

    bg = QtGui.QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]), 230)
    luminance = 0.299 * int(rgb[0]) + 0.587 * int(rgb[1]) + 0.114 * int(rgb[2])
    fg = QtGui.QColor(0, 0, 0) if luminance > 150 else QtGui.QColor(255, 255, 255)
    return bg, fg
