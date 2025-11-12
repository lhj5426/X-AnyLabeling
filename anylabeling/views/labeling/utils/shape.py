import json
import math
import uuid

import numpy as np
import PIL.Image
import PIL.ImageDraw

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QProgressDialog

from anylabeling.views.labeling.logger import logger
from anylabeling.views.labeling.utils.opencv import get_bounding_boxes
from anylabeling.views.labeling.widgets import Popup
from anylabeling.views.labeling.widgets.label_selection_dialog import LabelSelectionDialog
from anylabeling.views.labeling.utils.qt import new_icon_path
from anylabeling.views.labeling.utils.style import *
from anylabeling.services.auto_labeling.utils import calculate_rotation_theta


def shape_conversion(self, mode):
    label_file_list = self.get_label_file_list()
    if len(label_file_list) == 0:
        return

    # 收集所有相关的标签
    all_labels = set()
    for label_file in label_file_list:
        try:
            with open(label_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict) or "shapes" not in data:
                continue

            for shape in data["shapes"]:
                if not isinstance(shape, dict):
                    continue

                shape_type = shape.get("shape_type")
                label = shape.get("label")

                # 根据转换模式收集相关标签
                if mode == "hbb_to_obb" and shape_type == "rectangle":
                    if label:
                        all_labels.add(label)
                elif mode == "obb_to_hbb" and shape_type == "rotation":
                    if label:
                        all_labels.add(label)
                elif mode == "polygon_to_hbb" and shape_type == "polygon":
                    if label:
                        all_labels.add(label)
                elif mode == "polygon_to_obb" and shape_type == "polygon":
                    if label:
                        all_labels.add(label)
        except Exception as e:
            logger.warning(f"Error reading {label_file}: {e}")
            continue

    # 如果没有找到可转换的标签，提示用户
    if not all_labels:
        QtWidgets.QMessageBox.information(
            self,
            self.tr("提示"),
            self.tr("没有找到可以转换的标签。")
        )
        return

    # 弹出标签选择对话框
    mode_titles = {
        "hbb_to_obb": "选择要转换为旋转框的标签",
        "obb_to_hbb": "选择要转换为水平框的标签",
        "polygon_to_hbb": "选择要转换为水平框的标签",
        "polygon_to_obb": "选择要转换为旋转框的标签",
    }

    dialog = LabelSelectionDialog(
        sorted(list(all_labels)),
        mode_title=mode_titles.get(mode, "选择要转换的标签"),
        parent=self
    )

    if dialog.exec_() != QtWidgets.QDialog.Accepted:
        return

    selected_labels = dialog.get_selected_labels()

    # 如果用户没有选择任何标签，直接返回
    if not selected_labels:
        QtWidgets.QMessageBox.information(
            self,
            self.tr("提示"),
            self.tr("未选择任何标签，操作已取消。")
        )
        return

    # 转换为集合以便快速查找
    selected_labels_set = set(selected_labels)

    response = QtWidgets.QMessageBox()
    response.setIcon(QtWidgets.QMessageBox.Warning)
    response.setWindowTitle("警告")
    response.setText("当前标注将会被改变")
    response.setInformativeText(
        f"您确定要转换选中的 {len(selected_labels)} 个标签吗？"
    )
    response.setStandardButtons(
        QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Ok
    )
    response.button(QtWidgets.QMessageBox.Ok).setText('确定')
    response.button(QtWidgets.QMessageBox.Cancel).setText('取消')
    response.setStyleSheet(get_msg_box_style())

    if response.exec_() != QtWidgets.QMessageBox.Ok:
        return

    progress_dialog = QProgressDialog(
        self.tr("Converting..."), self.tr("Cancel"), 0, 0, self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("Progress"))
    progress_dialog.setMinimumWidth(400)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setStyleSheet(get_progress_dialog_style())
    progress_dialog.show()

    try:
        for i, label_file in enumerate(label_file_list):
            with open(label_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                logger.warning(
                    f"Data in {label_file} is not a dictionary, skipping."
                )
                continue

            if "shapes" not in data:
                logger.warning(f"'shapes' key not found in {label_file}, skipping.")
                continue

            for j in range(len(data["shapes"])):
                shape = data["shapes"][j]
                if not isinstance(shape, dict):
                    logger.warning(
                        f"Shape at index {j} in {label_file} is not a dictionary, skipping."
                    )
                    continue

                shape_type = shape.get("shape_type")
                shape_label = shape.get("label")

                # 只转换选中的标签
                if shape_label not in selected_labels_set:
                    continue

                if mode == "hbb_to_obb" and shape_type == "rectangle":
                    shape["shape_type"] = "rotation"
                    shape["direction"] = 0

                elif mode == "obb_to_hbb" and shape_type == "rotation":
                    if "direction" in shape:
                        del shape["direction"]
                    shape["shape_type"] = "rectangle"
                    points = np.array(shape.get("points", []))
                    if len(points) != 4:
                        continue
                    xmin = int(np.min(points[:, 0]))
                    ymin = int(np.min(points[:, 1]))
                    xmax = int(np.max(points[:, 0]))
                    ymax = int(np.max(points[:, 1]))
                    shape["points"] = [
                        [xmin, ymin],
                        [xmax, ymin],
                        [xmax, ymax],
                        [xmin, ymax],
                    ]

                elif mode == "polygon_to_hbb" and shape_type == "polygon":
                    shape["shape_type"] = "rectangle"
                    points = np.array(shape.get("points", []))
                    if len(points) < 3:
                        continue
                    xmin = int(np.min(points[:, 0]))
                    ymin = int(np.min(points[:, 1]))
                    xmax = int(np.max(points[:, 0]))
                    ymax = int(np.max(points[:, 1]))
                    shape["points"] = [
                        [xmin, ymin],
                        [xmax, ymin],
                        [xmax, ymax],
                        [xmin, ymax],
                    ]

                elif mode == "polygon_to_obb" and shape_type == "polygon":
                    points = np.array(shape.get("points", []))
                    contours = points.reshape((-1, 1, 2)).astype(np.float32)
                    _, rotation_box = get_bounding_boxes(contours)
                    shape["shape_type"] = "rotation"
                    shape["points"] = rotation_box.tolist()
                    shape["direction"] = calculate_rotation_theta(
                        rotation_box
                    )

            with open(label_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            progress_dialog.setValue(i)
            if progress_dialog.wasCanceled():
                break

        progress_dialog.close()
        popup = Popup(
            "转换成功！",
            self,
            msec=1000,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self, popup_height=65, position="center")

        self.load_file(self.filename)

    except Exception as e:
        logger.error(f"Error occurred while converting shapes: {e}")
        popup = Popup(
            self.tr("Error occurred while converting shapes!"),
            self,
            msec=1000,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")


def polygons_to_mask(img_shape, polygons, shape_type=None):
    logger.warning(
        "The 'polygons_to_mask' function is deprecated, "
        "use 'shape_to_mask' instead."
    )
    return shape_to_mask(img_shape, points=polygons, shape_type=shape_type)


def shape_to_mask(
    img_shape, points, shape_type=None, line_width=10, point_size=5
):
    mask = np.zeros(img_shape[:2], dtype=np.uint8)
    mask = PIL.Image.fromarray(mask)
    draw = PIL.ImageDraw.Draw(mask)
    xy = [tuple(point) for point in points]
    if shape_type == "circle":
        assert len(xy) == 2, "Shape of shape_type=circle must have 2 points"
        (cx, cy), (px, py) = xy
        d = math.sqrt((cx - px) ** 2 + (cy - py) ** 2)
        draw.ellipse([cx - d, cy - d, cx + d, cy + d], outline=1, fill=1)
    elif shape_type == "rectangle":
        assert len(xy) == 2, "Shape of shape_type=rectangle must have 2 points"
        draw.rectangle(xy, outline=1, fill=1)
    elif shape_type == "rotation":
        assert len(xy) == 4, "Shape of shape_type=rotation must have 4 points"
        draw.polygon(xy=xy, outline=1, fill=1)
    elif shape_type == "line":
        assert len(xy) == 2, "Shape of shape_type=line must have 2 points"
        draw.line(xy=xy, fill=1, width=line_width)
    elif shape_type == "linestrip":
        draw.line(xy=xy, fill=1, width=line_width)
    elif shape_type == "point":
        assert len(xy) == 1, "Shape of shape_type=point must have 1 points"
        cx, cy = xy[0]
        r = point_size
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=1, fill=1)
    else:
        assert len(xy) > 2, "Polygon must have points more than 2"
        draw.polygon(xy=xy, outline=1, fill=1)
    mask = np.array(mask, dtype=bool)
    return mask


def shapes_to_label(img_shape, shapes, label_name_to_value):
    cls = np.zeros(img_shape[:2], dtype=np.int32)
    ins = np.zeros_like(cls)
    instances = []
    for shape in shapes:
        points = shape["points"]
        label = shape["label"]
        group_id = shape.get("group_id")
        if group_id is None:
            group_id = uuid.uuid1()
        shape_type = shape.get("shape_type", None)

        cls_name = label
        instance = (cls_name, group_id)

        if instance not in instances:
            instances.append(instance)
        ins_id = instances.index(instance) + 1
        cls_id = label_name_to_value[cls_name]

        mask = shape_to_mask(img_shape[:2], points, shape_type)
        cls[mask] = cls_id
        ins[mask] = ins_id

    return cls, ins


def masks_to_bboxes(masks):
    if masks.ndim != 3:
        raise ValueError(f"masks.ndim must be 3, but it is {masks.ndim}")
    if masks.dtype != bool:
        raise ValueError(
            f"masks.dtype must be bool type, but it is {masks.dtype}"
        )
    bboxes = []
    for mask in masks:
        where = np.argwhere(mask)
        (y1, x1), (y2, x2) = where.min(0), where.max(0) + 1
        bboxes.append((y1, x1, y2, x2))
    bboxes = np.asarray(bboxes, dtype=np.float32)
    return bboxes


def rectangle_from_diagonal(diagonal_vertices):
    """
    Generate rectangle vertices from diagonal vertices.

    Parameters:
    - diagonal_vertices (list of lists):
        List containing two points representing the diagonal vertices.

    Returns:
    - list of lists:
        List containing four points representing the rectangle's four corners.
        [tl -> tr -> br -> bl]
    """
    x1, y1 = diagonal_vertices[0]
    x2, y2 = diagonal_vertices[1]

    # Creating the four-point representation
    rectangle_vertices = [
        [x1, y1],  # Top-left
        [x2, y1],  # Top-right
        [x2, y2],  # Bottom-right
        [x1, y2],  # Bottom-left
    ]

    return rectangle_vertices
