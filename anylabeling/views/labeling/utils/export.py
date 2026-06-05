import json
import os
import os.path as osp
import pathlib
import shutil
import time
import math

from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QProgressDialog,
    QDialog,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
    QLabel,
)

from anylabeling.views.labeling.label_converter import LabelConverter
from anylabeling.views.labeling.logger import logger
from anylabeling.views.labeling.widgets import Popup
from anylabeling.views.labeling.utils.qt import new_icon_path
from anylabeling.views.labeling.utils.style import *


class ExportThread(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(
        self,
        converter,
        image_list,
        label_dir_path,
        save_path,
        mode,
        prefix=None,
        excluded_labels=None,
    ):
        super().__init__()
        self.converter = converter
        self.image_list = image_list
        self.label_dir_path = label_dir_path
        self.save_path = save_path
        self.mode = mode
        self.prefix = prefix
        self.excluded_labels = excluded_labels

    def run(self):
        try:
            time.sleep(1)

            if self.mode == "vlm_r1_ovd":
                self.converter.custom_to_vlm_r1_ovd(
                    self.image_list,
                    self.label_dir_path,
                    self.save_path,
                    self.prefix,
                )
            elif self.mode == "mot":
                self.converter.custom_to_mot(
                    self.label_dir_path, self.save_path
                )
            elif self.mode == "mots":
                self.converter.custom_to_mots(
                    self.label_dir_path, self.save_path
                )
            elif self.mode == "odvg":
                self.converter.custom_to_odvg(
                    self.image_list, self.label_dir_path, self.save_path
                )
            else:
                self.converter.custom_to_coco(
                    self.image_list,
                    self.label_dir_path,
                    self.save_path,
                    self.mode,
                    excluded_labels=self.excluded_labels,
                )
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


class ExportImageTransThread(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(
        self,
        converter,
        image_list,
        label_dir_path,
        template_path,
        save_path,
        excluded_labels,
    ):
        super().__init__()
        self.converter = converter
        self.image_list = image_list
        self.label_dir_path = label_dir_path
        self.template_path = template_path
        self.save_path = save_path
        self.excluded_labels = excluded_labels

    def run(self):
        try:
            logger.info("ExportImageTransThread.run started")
            time.sleep(1) # Keep this for better user experience with progress dialog

            self.converter.custom_to_imagetrans(
                self.image_list,
                self.label_dir_path,
                self.template_path,
                self.save_path,
                self.excluded_labels,
            )
            logger.info("ExportImageTransThread.run finished successfully")
            self.finished.emit(True, "")
        except Exception as e:
            logger.error(f"ExportImageTransThread.run error: {e}")
            self.finished.emit(False, str(e))


class ExportBallonTranslatorThread(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(
        self,
        converter,
        image_list,
        label_dir_path,
        save_path,
        excluded_labels,
    ):
        super().__init__()
        self.converter = converter
        self.image_list = image_list
        self.label_dir_path = label_dir_path
        self.save_path = save_path
        self.excluded_labels = excluded_labels

    def run(self):
        try:
            time.sleep(1)
            self.converter.custom_to_ballontranslator(
                self.image_list,
                self.label_dir_path,
                self.save_path,
                self.excluded_labels,
            )
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


class ExportMTUJsonThread(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(
        self,
        image_list,
        save_root_path,
        excluded_labels=None,
        output_dir=None,
        last_open_dir=None,
    ):
        super().__init__()
        self.image_list = image_list or []
        self.save_root_path = save_root_path
        self.excluded_labels = set(str(x) for x in (excluded_labels or []))
        self.output_dir = output_dir
        self.last_open_dir = last_open_dir
        self.stats = {
            "total_images": 0,
            "generated_json": 0,
            "failed": 0,
            "filtered_textlines": 0,
            "total_textlines": 0,
            "error_samples": [],
        }
        self.output_json_dir = osp.join(
            self.save_root_path, "manga_translator_work", "json"
        )

    def _resolve_label_path(self, image_path: str) -> str:
        image_name = osp.basename(image_path)
        label_file_name = osp.splitext(image_name)[0] + ".json"
        image_dir = osp.dirname(image_path)

        if self.output_dir:
            if self.last_open_dir:
                try:
                    rel_path = osp.relpath(image_dir, self.last_open_dir)
                    candidate = osp.join(
                        self.output_dir, rel_path, label_file_name
                    )
                    if osp.exists(candidate):
                        return candidate
                except Exception:
                    pass
            candidate = osp.join(self.output_dir, label_file_name)
            if osp.exists(candidate):
                return candidate

        return osp.join(image_dir, label_file_name)

    @staticmethod
    def _extract_xy(point):
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            return float(point[0]), float(point[1])
        if isinstance(point, dict):
            if "x" in point and "y" in point:
                return float(point["x"]), float(point["y"])
            if 0 in point and 1 in point:
                return float(point[0]), float(point[1])
        return None

    @classmethod
    def _shape_to_textline(cls, shape: dict) -> dict:
        points = shape.get("points", []) or []
        pts = []
        for p in points:
            xy = cls._extract_xy(p)
            if xy is None:
                continue
            pts.append([float(xy[0]), float(xy[1])])

        # XA rectangle may be saved as two diagonal points in some datasets.
        shape_type = str(shape.get("shape_type", "") or "").lower()
        if shape_type == "rectangle" and len(pts) == 2:
            x1, y1 = pts[0]
            x2, y2 = pts[1]
            xmin, xmax = sorted([x1, x2])
            ymin, ymax = sorted([y1, y2])
            pts = [
                [xmin, ymin],
                [xmax, ymin],
                [xmax, ymax],
                [xmin, ymax],
            ]

        # Keep MTU textline polygon stable as 4-point box when possible.
        if len(pts) > 4:
            pts = pts[:4]
        label = str(shape.get("label", "") or "")
        text = str(shape.get("description", "") or "")
        xa_direction = shape.get("direction", None)
        try:
            xa_direction = (
                float(xa_direction) if xa_direction is not None else None
            )
        except Exception:
            xa_direction = None
        return {
            "pts": pts,
            "text": text,
            "prob": 1.0,
            "fg_colors": [0, 0, 0],
            "bg_colors": [255, 255, 255],
            "direction": "v",
            "assigned_direction": None,
            "is_yolo_box": False,
            "imported_yolo_box": False,
            "det_label": None,
            "yolo_label": None,
            "_xa_label": label,
            "_xa_direction": xa_direction,
        }

    @staticmethod
    def _textline_to_region(textline: dict) -> dict:
        pts = textline.get("pts", []) or []
        if pts:
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
        else:
            cx = cy = 0.0
        angle = 0.0
        if len(pts) >= 2:
            # Use the longest edge and convert to MTU-like vertical slant angle.
            best_dx, best_dy, best_len = 0.0, 0.0, -1.0
            for i in range(len(pts)):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % len(pts)]
                dx = float(x2) - float(x1)
                dy = float(y2) - float(y1)
                l2 = dx * dx + dy * dy
                if l2 > best_len:
                    best_len = l2
                    best_dx, best_dy = dx, dy
            edge_angle = float(math.degrees(math.atan2(best_dy, best_dx)))
            angle = edge_angle + 90.0
            while angle > 180.0:
                angle -= 360.0
            while angle <= -180.0:
                angle += 360.0
            while angle > 90.0:
                angle -= 180.0
            while angle <= -90.0:
                angle += 180.0
        single_text = str(textline.get("text", "") or "")
        return {
            "lines": [pts],
            "center": [float(cx), float(cy)],
            "texts": [single_text],
            "text": single_text,
            "translation": "",
            "font_size": 20,
            "angle": angle,
            "fg_colors": textline.get("fg_colors", [0, 0, 0]),
            "bg_colors": textline.get("bg_colors", [255, 255, 255]),
            "direction": "v",
            "alignment": "center",
            "target_lang": "",
            "source_lang": "",
            "prob": float(textline.get("prob", 1.0) or 1.0),
            "line_spacing": 1.0,
            "letter_spacing": 1.0,
            "stroke_width": 0.07,
            "font_path": "",
            "white_frame_rect_local": [0.0, 0.0, 0.0, 0.0],
            "has_custom_white_frame": False,
        }

    def run(self):
        try:
            os.makedirs(self.output_json_dir, exist_ok=True)
            self.stats["total_images"] = len(self.image_list)

            for image_path in self.image_list:
                try:
                    label_path = self._resolve_label_path(image_path)
                    w = 0
                    h = 0
                    if osp.exists(label_path):
                        with open(label_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        shapes = data.get("shapes", []) or []
                        w = int(data.get("imageWidth") or 0)
                        h = int(data.get("imageHeight") or 0)
                    else:
                        data = {}
                        shapes = []

                    # Fallback: read dimensions from image only when JSON has no size.
                    if w <= 0 or h <= 0:
                        image = QtGui.QImage(image_path)
                        if not image.isNull():
                            w = int(image.width())
                            h = int(image.height())

                    textlines_data = []
                    for shape in shapes:
                        try:
                            label = str(shape.get("label", "") or "")
                            if (
                                self.excluded_labels
                                and label in self.excluded_labels
                            ):
                                self.stats["filtered_textlines"] += 1
                                continue
                            tl = self._shape_to_textline(shape)
                            if tl["pts"]:
                                textlines_data.append(tl)
                        except Exception:
                            # Skip malformed shapes but keep exporting this image.
                            continue

                    self.stats["total_textlines"] += len(shapes)
                    regions_data = [
                        self._textline_to_region(tl) for tl in textlines_data
                    ]

                    payload = {
                        os.path.abspath(image_path): {
                            "regions": regions_data,
                            "textlines": textlines_data,
                            "original_width": w,
                            "original_height": h,
                            "skip_font_scaling": False,
                        }
                    }

                    out_json = osp.join(
                        self.output_json_dir,
                        f"{osp.splitext(osp.basename(image_path))[0]}_translations.json",
                    )
                    with open(out_json, "w", encoding="utf-8") as f:
                        json.dump(payload, f, ensure_ascii=False, indent=4)
                    self.stats["generated_json"] += 1
                except Exception as e:
                    self.stats["failed"] += 1
                    if len(self.stats["error_samples"]) < 5:
                        self.stats["error_samples"].append(
                            f"{osp.basename(image_path)}: {e}"
                        )

            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


def _check_filename_exist(self):
    if not self.may_continue():
        return False

    if not self.filename:
        popup = Popup(
            self.tr("Please load an image folder before proceeding!"),
            self,
            icon=new_icon_path("warning", "svg"),
        )
        popup.show_popup(self, position="center")
        return False

    return True


def _filter_images_by_labels(image_list, label_dir_path, filter_config, parent_widget=None):
    """
    根据标签筛选配置过滤图片列表

    Args:
        image_list: 图片文件路径列表
        label_dir_path: 标签文件目录（可能不使用，改为从图片路径推导）
        filter_config: 筛选配置字典，包含 enabled, mode, match_condition, labels
        parent_widget: 父窗口对象，用于获取output_dir和last_open_dir

    Returns:
        过滤后的图片列表
    """
    if not filter_config['enabled'] or not filter_config['labels']:
        return image_list

    filtered_list = []
    mode = filter_config['mode']
    match_condition = filter_config['match_condition']
    target_labels = set(filter_config['labels'])

    for image_file in image_list:
        image_file_name = osp.basename(image_file)
        label_file_name = osp.splitext(image_file_name)[0] + ".json"
        
        # 修复：根据图片的实际路径找对应的JSON文件
        image_dir = osp.dirname(image_file)
        if parent_widget and hasattr(parent_widget, 'output_dir') and parent_widget.output_dir:
            if hasattr(parent_widget, 'last_open_dir') and parent_widget.last_open_dir:
                rel_path = osp.relpath(image_dir, parent_widget.last_open_dir)
                label_file = osp.join(parent_widget.output_dir, rel_path, label_file_name)
            else:
                label_file = osp.join(parent_widget.output_dir, label_file_name)
        else:
            label_file = osp.join(image_dir, label_file_name)

        if not osp.exists(label_file):
            # 如果标签文件不存在，根据模式决定是否包含
            # 排除模式：没有标签就导出
            # 包含模式：没有标签就不导出
            if mode == 'exclude':
                filtered_list.append(image_file)
            continue

        try:
            with open(label_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 获取该图片中所有的标签
                image_labels = set()
                for shape in data.get('shapes', []):
                    label = shape.get('label', '')
                    if label:
                        image_labels.add(label)

                # 根据筛选配置决定是否包含该图片
                if mode == 'include':
                    # 包含模式：图片标签必须满足条件
                    if match_condition == 'any':
                        # 包含任意一个目标标签
                        if image_labels & target_labels:
                            filtered_list.append(image_file)
                    else:  # match_condition == 'all'
                        # 包含所有目标标签
                        if target_labels.issubset(image_labels):
                            filtered_list.append(image_file)
                else:  # mode == 'exclude'
                    # 排除模式：图片标签不能包含任何目标标签
                    if not (image_labels & target_labels):
                        filtered_list.append(image_file)
        except Exception as e:
            logger.warning(f"Failed to read label file {label_file}: {e}")
            # 读取失败时，排除模式包含该图片，包含模式排除该图片
            if mode == 'exclude':
                filtered_list.append(image_file)

    return filtered_list


class LabelExclusionDialog(QDialog):
    def __init__(self, labels, parent=None):
        super().__init__(parent)
        self.setWindowTitle("排除标签")
        self.setMinimumWidth(300)
        layout = QVBoxLayout(self)

        description = QLabel("勾选要从导出中排除的标签：")
        layout.addWidget(description)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        for label in labels:
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.list_widget.addItem(item)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_excluded_labels(self):
        excluded = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                excluded.append(item.text())
        return excluded


class LabelFilterDialog(QDialog):
    """对话框用于筛选包含或排除特定标签的文件"""
    def __init__(self, labels, parent=None):
        super().__init__(parent)
        self.setWindowTitle("高级标签筛选")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)

        # 启用筛选的复选框
        self.enable_filter_checkbox = QtWidgets.QCheckBox("启用标签筛选")
        self.enable_filter_checkbox.setChecked(False)
        layout.addWidget(self.enable_filter_checkbox)

        # 筛选模式选择
        mode_layout = QHBoxLayout()
        mode_label = QLabel("筛选模式：")
        mode_layout.addWidget(mode_label)

        self.mode_group = QtWidgets.QButtonGroup(self)
        self.include_radio = QtWidgets.QRadioButton("包含模式（导出包含以下标签的图片）")
        self.exclude_radio = QtWidgets.QRadioButton("排除模式（不导出包含以下标签的图片）")
        self.exclude_labels_only_radio = QtWidgets.QRadioButton("只排除标签（导出图片但不导出特定标签）")
        self.include_radio.setChecked(True)

        self.mode_group.addButton(self.include_radio)
        self.mode_group.addButton(self.exclude_radio)
        self.mode_group.addButton(self.exclude_labels_only_radio)

        layout.addWidget(self.include_radio)
        layout.addWidget(self.exclude_radio)
        layout.addWidget(self.exclude_labels_only_radio)

        # 匹配条件选择（仅在包含模式下可用）
        self.match_layout = QHBoxLayout()
        self.match_label = QLabel("匹配条件：")
        self.match_layout.addWidget(self.match_label)

        self.match_group = QtWidgets.QButtonGroup(self)
        self.match_any_radio = QtWidgets.QRadioButton("包含任意一个标签")
        self.match_all_radio = QtWidgets.QRadioButton("包含所有标签")
        self.match_any_radio.setChecked(True)

        self.match_group.addButton(self.match_any_radio)
        self.match_group.addButton(self.match_all_radio)

        layout.addWidget(self.match_any_radio)
        layout.addWidget(self.match_all_radio)

        # 标签列表
        description = QLabel("勾选要筛选的标签：")
        layout.addWidget(description)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        for label in labels:
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.list_widget.addItem(item)

        # 连接信号，控制匹配条件的可用性
        self.include_radio.toggled.connect(self._update_match_condition_state)
        self.enable_filter_checkbox.toggled.connect(self._update_all_controls_state)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # 初始化状态
        self._update_all_controls_state()

    def _update_match_condition_state(self):
        """更新匹配条件的启用状态"""
        is_include_mode = self.include_radio.isChecked()
        is_enabled = self.enable_filter_checkbox.isChecked()
        self.match_any_radio.setEnabled(is_include_mode and is_enabled)
        self.match_all_radio.setEnabled(is_include_mode and is_enabled)
        self.match_label.setEnabled(is_include_mode and is_enabled)

    def _update_all_controls_state(self):
        """更新所有控件的启用状态"""
        is_enabled = self.enable_filter_checkbox.isChecked()
        self.include_radio.setEnabled(is_enabled)
        self.exclude_radio.setEnabled(is_enabled)
        self.exclude_labels_only_radio.setEnabled(is_enabled)
        self.list_widget.setEnabled(is_enabled)
        self._update_match_condition_state()

    def is_filter_enabled(self):
        """返回是否启用了筛选"""
        return self.enable_filter_checkbox.isChecked()

    def get_filter_config(self):
        """
        返回筛选配置
        返回格式: {
            'enabled': bool,
            'mode': 'include' or 'exclude',
            'match_condition': 'any' or 'all',  # 仅在 include 模式下有意义
            'labels': [label1, label2, ...]
        }
        """
        selected_labels = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected_labels.append(item.text())

        mode = 'include'
        if self.exclude_radio.isChecked():
            mode = 'exclude'
        elif self.exclude_labels_only_radio.isChecked():
            mode = 'exclude_labels'

        return {
            'enabled': self.enable_filter_checkbox.isChecked(),
            'mode': mode,
            'match_condition': 'any' if self.match_any_radio.isChecked() else 'all',
            'labels': selected_labels
        }


def export_yolo_annotation(self, mode):
    if not _check_filename_exist(self):
        return

    # Handle config/classes file selection based on mode
    if mode == "pose":
        filter = "Classes Files (*.yaml);;All Files (*)"
        self.yaml_file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.tr("Select a specific yolo-pose config file"),
            "",
            filter,
        )
        if not self.yaml_file:
            return
        converter = LabelConverter(pose_cfg_file=self.yaml_file)

    elif mode in ["hbb", "obb", "seg"]:
        filter = "Classes Files (*.txt);;All Files (*)"
        self.classes_file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.tr("Select a specific classes file"),
            "",
            filter,
        )
        if not self.classes_file:
            return
        converter = LabelConverter(classes_file=self.classes_file)

    dialog = QtWidgets.QDialog(self)
    dialog.setWindowTitle(self.tr("导出选项"))
    dialog.setMinimumWidth(500)
    dialog.setStyleSheet(get_export_option_style())

    layout = QVBoxLayout()
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)

    path_layout = QVBoxLayout()
    path_label = QtWidgets.QLabel(self.tr("导出路径"))
    path_layout.addWidget(path_label)

    path_input_layout = QHBoxLayout()
    path_input_layout.setSpacing(8)

    # Set default folder name based on mode
    folder_names = {
        "hbb": "labels",
        "obb": "OBB_labels",
        "seg": "SEG_labels",
        "pose": "POSE_labels"
    }
    default_folder = folder_names.get(mode, "labels")

    path_edit = QtWidgets.QLineEdit()
    path_edit.setText(
        osp.realpath(osp.join(osp.dirname(self.filename), "..", default_folder))
    )
    path_edit.setPlaceholderText(self.tr("Select Export Directory"))

    def browse_export_path():
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.tr("Select Export Directory"),
            path_edit.text(),
            QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if path:
            path_edit.setText(path)

    path_button = QtWidgets.QPushButton(self.tr("Browse"))
    path_button.clicked.connect(browse_export_path)
    path_button.setStyleSheet(get_cancel_btn_style())

    path_input_layout.addWidget(path_edit)
    path_input_layout.addWidget(path_button)
    path_layout.addLayout(path_input_layout)
    layout.addLayout(path_layout)

    options_label = QtWidgets.QLabel(self.tr("导出选项"))
    layout.addWidget(options_label)

    save_images_checkbox = QtWidgets.QCheckBox(self.tr("同时保存图片？"))
    save_images_checkbox.setChecked(False)
    layout.addWidget(save_images_checkbox)

    skip_empty_files_checkbox = QtWidgets.QCheckBox(
        self.tr("跳过没有标签的空文件？")
    )
    skip_empty_files_checkbox.setChecked(False)
    layout.addWidget(skip_empty_files_checkbox)

    only_manually_edited_checkbox = QtWidgets.QCheckBox(
        self.tr("仅导出手动调整的文件？")
    )
    only_manually_edited_checkbox.setChecked(False)
    layout.addWidget(only_manually_edited_checkbox)

    # 高级标签筛选按钮
    advanced_filter_layout = QHBoxLayout()
    advanced_filter_button = QtWidgets.QPushButton(self.tr("筛选标签"))
    advanced_filter_button.setMinimumWidth(120)
    advanced_filter_button.setStyleSheet(get_cancel_btn_style())

    # 存储筛选配置
    filter_config = {
        'enabled': False,
        'mode': 'include',
        'match_condition': 'any',
        'labels': []
    }

    def open_label_filter_dialog():
        # 获取所有唯一标签
        unique_labels = []
        if hasattr(self, 'unique_label_list'):
            for i in range(self.unique_label_list.count()):
                item = self.unique_label_list.item(i)
                label_text = item.data(Qt.UserRole)
                if label_text:
                    unique_labels.append(label_text)

        if not unique_labels:
            popup = Popup(
                self.tr("没有找到标签，请先标注图片"),
                self,
                icon=new_icon_path("warning", "svg"),
            )
            popup.show_popup(self, position="center")
            return

        filter_dialog = LabelFilterDialog(unique_labels, self)
        if filter_dialog.exec_() == QtWidgets.QDialog.Accepted:
            nonlocal filter_config
            filter_config = filter_dialog.get_filter_config()

    advanced_filter_button.clicked.connect(open_label_filter_dialog)
    advanced_filter_layout.addWidget(advanced_filter_button)
    advanced_filter_layout.addStretch()
    layout.addLayout(advanced_filter_layout)

    button_layout = QHBoxLayout()
    button_layout.setContentsMargins(0, 16, 0, 0)
    button_layout.setSpacing(8)

    cancel_button = QtWidgets.QPushButton(self.tr("Cancel"))
    cancel_button.clicked.connect(dialog.reject)
    cancel_button.setStyleSheet(get_cancel_btn_style())

    ok_button = QtWidgets.QPushButton(self.tr("OK"))
    ok_button.clicked.connect(dialog.accept)
    ok_button.setStyleSheet(get_ok_btn_style())

    button_layout.addStretch()
    button_layout.addWidget(cancel_button)
    button_layout.addWidget(ok_button)
    layout.addLayout(button_layout)

    dialog.setLayout(layout)
    result = dialog.exec_()

    if not result:
        return

    save_images = save_images_checkbox.isChecked()
    skip_empty_files = skip_empty_files_checkbox.isChecked()
    only_manually_edited = only_manually_edited_checkbox.isChecked()
    save_path = path_edit.text()

    if osp.exists(save_path):
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setIcon(QtWidgets.QMessageBox.Warning)
        msg_box.setWindowTitle(self.tr("输出目录已存在！"))
        msg_box.setText(self.tr("目录已存在，请选择一个操作："))
        msg_box.setInformativeText(
            self.tr(
                "• 是 (Yes) - 合并到现有文件\n"
                "• 否 (No) - 删除现有目录\n"
                "• 取消 (Cancel) - 中止导出"
            )
        )

        msg_box.addButton(self.tr("是"), QtWidgets.QMessageBox.YesRole)
        no_button = msg_box.addButton(
            self.tr("否"), QtWidgets.QMessageBox.NoRole
        )
        cancel_button = msg_box.addButton(
            self.tr("取消"), QtWidgets.QMessageBox.RejectRole
        )
        msg_box.setStyleSheet(get_msg_box_style())
        msg_box.exec_()

        clicked_button = msg_box.clickedButton()
        if clicked_button == no_button:
            shutil.rmtree(save_path)
            os.makedirs(save_path)
        elif clicked_button == cancel_button:
            return
    else:
        os.makedirs(save_path)

    image_list = self.image_list if self.image_list else [self.filename]
    label_dir_path = osp.dirname(self.filename)
    if self.output_dir:
        label_dir_path = self.output_dir

    # Filter for manually edited files if option is checked
    if only_manually_edited:
        filtered_image_list = []
        for image_file in image_list:
            image_file_name = osp.basename(image_file)
            label_file_name = osp.splitext(image_file_name)[0] + ".json"
            
            # 修复：根据图片的实际路径找对应的JSON文件
            image_dir = osp.dirname(image_file)
            if self.output_dir:
                if hasattr(self, 'last_open_dir') and self.last_open_dir:
                    rel_path = osp.relpath(image_dir, self.last_open_dir)
                    src_file = osp.join(self.output_dir, rel_path, label_file_name)
                else:
                    src_file = osp.join(self.output_dir, label_file_name)
            else:
                src_file = osp.join(image_dir, label_file_name)

            if osp.exists(src_file):
                try:
                    with open(src_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if data.get("manually_edited", False):
                            filtered_image_list.append(image_file)
                except:
                    pass
        image_list = filtered_image_list

    # Filter by labels if advanced filter is enabled
    if filter_config['enabled']:
        if filter_config['mode'] != 'exclude_labels':
            image_list = _filter_images_by_labels(image_list, label_dir_path, filter_config, self)
            if not image_list:
                popup = Popup(
                    self.tr("没有图片符合筛选条件！"),
                    self,
                    icon=new_icon_path("warning", "svg"),
                )
                popup.show_popup(self, position="center")
                return

    progress_dialog = QProgressDialog(
        self.tr("Exporting..."), self.tr("Cancel"), 0, len(image_list), self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("Progress"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setStyleSheet(
        get_progress_dialog_style(color="#1d1d1f", height=20)
    )

    try:
        for i, image_file in enumerate(image_list):
            image_file_name = osp.basename(image_file)
            label_file_name = osp.splitext(image_file_name)[0] + ".json"
            dst_file_name = osp.splitext(image_file_name)[0] + ".txt"

            # 修复：根据图片的实际路径找对应的JSON文件
            # 如果图片在子文件夹中，JSON文件也应该在同一个子文件夹中
            image_dir = osp.dirname(image_file)
            if self.output_dir:
                # 如果设置了output_dir，JSON文件在output_dir的对应子目录中
                # 计算图片相对于根目录的路径
                if hasattr(self, 'last_open_dir') and self.last_open_dir:
                    rel_path = osp.relpath(image_dir, self.last_open_dir)
                    src_file = osp.join(self.output_dir, rel_path, label_file_name)
                else:
                    src_file = osp.join(self.output_dir, label_file_name)
            else:
                # 没有output_dir，JSON文件就在图片同目录
                src_file = osp.join(image_dir, label_file_name)
            
            dst_file = osp.join(save_path, dst_file_name)

            excluded_labels = filter_config['labels'] if filter_config['enabled'] and filter_config['mode'] == 'exclude_labels' else None
            is_empty_file = converter.custom_to_yolo(
                src_file, dst_file, mode, skip_empty_files, excluded_labels=excluded_labels
            )

            if save_images and not (skip_empty_files and is_empty_file):
                image_dst = osp.join(save_path, image_file_name)
                shutil.copy(image_file, image_dst)

            if skip_empty_files and is_empty_file and osp.exists(dst_file):
                os.remove(dst_file)

            progress_dialog.setValue(i)
            if progress_dialog.wasCanceled():
                break

        progress_dialog.close()
        template = self.tr(
            "导出标注成功！\n"
            "结果已保存到：\n"
            "%s"
        )
        message_text = template % save_path
        skipped_text = ""
        if hasattr(converter, "yolo_skipped_unknown_labels_text"):
            skipped_text = converter.yolo_skipped_unknown_labels_text()

        if skipped_text:
            message_box = QtWidgets.QMessageBox(self)
            message_box.setIcon(QtWidgets.QMessageBox.Warning)
            message_box.setWindowTitle(self.tr("YOLO导出完成"))
            message_box.setText(
                message_text
                + "\n\n部分标签不在类别文件中，已跳过未导出。"
                + skipped_text
            )
            if hasattr(converter, "yolo_skipped_unknown_labels_details"):
                skipped_details = converter.yolo_skipped_unknown_labels_details()
                if skipped_details:
                    message_box.setDetailedText(skipped_details)
            message_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
            ok_button = message_box.button(QtWidgets.QMessageBox.Ok)
            if ok_button is not None:
                ok_button.setText(self.tr("确定"))
            def relabel_details_button():
                for button in message_box.findChildren(QtWidgets.QPushButton):
                    if button.text() in ("Show Details...", "Show Details"):
                        button.setText(self.tr("详细信息"))
                        button.clicked.connect(
                            lambda: QTimer.singleShot(
                                0, relabel_details_button
                            )
                        )
                    elif button.text() in ("Hide Details...", "Hide Details"):
                        button.setText(self.tr("隐藏详情"))
                        button.clicked.connect(
                            lambda: QTimer.singleShot(
                                0, relabel_details_button
                            )
                        )

            relabel_details_button()
            message_box.exec_()
            return

        popup = Popup(
            message_text,
            self,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self, popup_height=65, position="center")

    except Exception as e:
        message = f"Error occurred while exporting annotations: {str(e)}"
        progress_dialog.close()
        logger.error(message)
        popup = Popup(
            message,
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")


def export_voc_annotation(self, mode):
    if not _check_filename_exist(self):
        return

    dialog = QtWidgets.QDialog(self)
    dialog.setWindowTitle(self.tr("导出选项"))
    dialog.setMinimumWidth(500)
    dialog.setStyleSheet(get_export_option_style())

    layout = QVBoxLayout()
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)

    path_layout = QVBoxLayout()
    path_label = QtWidgets.QLabel(self.tr("导出路径"))
    path_layout.addWidget(path_label)

    path_input_layout = QHBoxLayout()
    path_input_layout.setSpacing(8)

    path_edit = QtWidgets.QLineEdit()
    path_edit.setText(
        osp.realpath(osp.join(osp.dirname(self.filename), "..", "Annotations"))
    )
    path_edit.setPlaceholderText(self.tr("Select Export Directory"))

    def browse_export_path():
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.tr("Select Export Directory"),
            path_edit.text(),
            QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if path:
            path_edit.setText(path)

    path_button = QtWidgets.QPushButton(self.tr("Browse"))
    path_button.clicked.connect(browse_export_path)
    path_button.setStyleSheet(get_cancel_btn_style())

    path_input_layout.addWidget(path_edit)
    path_input_layout.addWidget(path_button)
    path_layout.addLayout(path_input_layout)
    layout.addLayout(path_layout)

    options_label = QtWidgets.QLabel(self.tr("导出选项"))
    layout.addWidget(options_label)

    save_images_checkbox = QtWidgets.QCheckBox(self.tr("同时保存图片？"))
    save_images_checkbox.setChecked(False)
    layout.addWidget(save_images_checkbox)

    skip_empty_files_checkbox = QtWidgets.QCheckBox(
        self.tr("跳过没有标签的空文件？")
    )
    skip_empty_files_checkbox.setChecked(False)
    layout.addWidget(skip_empty_files_checkbox)

    # 高级标签筛选按钮
    advanced_filter_layout = QHBoxLayout()
    advanced_filter_button = QtWidgets.QPushButton(self.tr("筛选标签"))
    advanced_filter_button.setMinimumWidth(120)
    advanced_filter_button.setStyleSheet(get_cancel_btn_style())

    # 存储筛选配置
    filter_config = {
        'enabled': False,
        'mode': 'include',
        'match_condition': 'any',
        'labels': []
    }

    def open_label_filter_dialog():
        # 获取所有唯一标签
        unique_labels = []
        if hasattr(self, 'unique_label_list'):
            for i in range(self.unique_label_list.count()):
                item = self.unique_label_list.item(i)
                label_text = item.data(Qt.UserRole)
                if label_text:
                    unique_labels.append(label_text)

        if not unique_labels:
            popup = Popup(
                self.tr("没有找到标签，请先标注图片"),
                self,
                icon=new_icon_path("warning", "svg"),
            )
            popup.show_popup(self, position="center")
            return

        filter_dialog = LabelFilterDialog(unique_labels, self)
        if filter_dialog.exec_() == QtWidgets.QDialog.Accepted:
            nonlocal filter_config
            filter_config = filter_dialog.get_filter_config()

    advanced_filter_button.clicked.connect(open_label_filter_dialog)
    advanced_filter_layout.addWidget(advanced_filter_button)
    advanced_filter_layout.addStretch()
    layout.addLayout(advanced_filter_layout)

    button_layout = QHBoxLayout()
    button_layout.setContentsMargins(0, 16, 0, 0)
    button_layout.setSpacing(8)

    cancel_button = QtWidgets.QPushButton(self.tr("Cancel"))
    cancel_button.clicked.connect(dialog.reject)
    cancel_button.setStyleSheet(get_cancel_btn_style())

    ok_button = QtWidgets.QPushButton(self.tr("OK"))
    ok_button.clicked.connect(dialog.accept)
    ok_button.setStyleSheet(get_ok_btn_style())

    button_layout.addStretch()
    button_layout.addWidget(cancel_button)
    button_layout.addWidget(ok_button)
    layout.addLayout(button_layout)

    dialog.setLayout(layout)
    result = dialog.exec_()

    if not result:
        return

    save_images = save_images_checkbox.isChecked()
    skip_empty_files = skip_empty_files_checkbox.isChecked()
    save_path = path_edit.text()

    if osp.exists(save_path):
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setIcon(QtWidgets.QMessageBox.Warning)
        msg_box.setWindowTitle(self.tr("输出目录已存在！"))
        msg_box.setText(self.tr("目录已存在，请选择一个操作："))
        msg_box.setInformativeText(
            self.tr(
                "• 是 (Yes) - 合并到现有文件\n"
                "• 否 (No) - 删除现有目录\n"
                "• 取消 (Cancel) - 中止导出"
            )
        )

        msg_box.addButton(self.tr("是"), QtWidgets.QMessageBox.YesRole)
        no_button = msg_box.addButton(
            self.tr("否"), QtWidgets.QMessageBox.NoRole
        )
        cancel_button = msg_box.addButton(
            self.tr("取消"), QtWidgets.QMessageBox.RejectRole
        )
        msg_box.setStyleSheet(get_msg_box_style())
        msg_box.exec_()

        clicked_button = msg_box.clickedButton()
        if clicked_button == no_button:
            shutil.rmtree(save_path)
            os.makedirs(save_path)
        elif clicked_button == cancel_button:
            return
    else:
        os.makedirs(save_path)

    converter = LabelConverter()

    image_list = self.image_list if self.image_list else [self.filename]
    label_dir_path = osp.dirname(self.filename)
    if self.output_dir:
        label_dir_path = self.output_dir

    # Filter by labels if advanced filter is enabled
    if filter_config['enabled']:
        if filter_config['mode'] != 'exclude_labels':
            image_list = _filter_images_by_labels(image_list, label_dir_path, filter_config, self)
            if not image_list:
                popup = Popup(
                    self.tr("没有图片符合筛选条件！"),
                    self,
                    icon=new_icon_path("warning", "svg"),
                )
                popup.show_popup(self, position="center")
                return

    progress_dialog = QProgressDialog(
        self.tr("Exporting..."), self.tr("Cancel"), 0, len(image_list), self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("Progress"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setStyleSheet(
        get_progress_dialog_style(color="#1d1d1f", height=20)
    )

    try:
        for i, image_file in enumerate(image_list):
            image_file_name = osp.basename(image_file)
            label_file_name = osp.splitext(image_file_name)[0] + ".json"
            dst_file_name = osp.splitext(image_file_name)[0] + ".xml"

            # 修复：根据图片的实际路径找对应的JSON文件
            image_dir = osp.dirname(image_file)
            if self.output_dir:
                if hasattr(self, 'last_open_dir') and self.last_open_dir:
                    rel_path = osp.relpath(image_dir, self.last_open_dir)
                    src_file = osp.join(self.output_dir, rel_path, label_file_name)
                else:
                    src_file = osp.join(self.output_dir, label_file_name)
            else:
                src_file = osp.join(image_dir, label_file_name)
            
            dst_file = osp.join(save_path, dst_file_name)

            excluded_labels = filter_config['labels'] if filter_config['enabled'] and filter_config['mode'] == 'exclude_labels' else None
            is_empty_file = converter.custom_to_voc(
                image_file, src_file, dst_file, mode, skip_empty_files, excluded_labels=excluded_labels
            )

            if save_images and not (skip_empty_files and is_empty_file):
                image_dst = osp.join(save_path, image_file_name)
                shutil.copy(image_file, image_dst)

            if skip_empty_files and is_empty_file and osp.exists(dst_file):
                os.remove(dst_file)

            progress_dialog.setValue(i)
            if progress_dialog.wasCanceled():
                break

        progress_dialog.close()
        template = self.tr(
            "导出标注成功！\n"
            "结果已保存到：\n"
            "%s"
        )
        message_text = template % save_path
        popup = Popup(
            message_text,
            self,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self, popup_height=65, position="center")

    except Exception as e:
        message = f"Error occurred while exporting annotations: {str(e)}"
        progress_dialog.close()
        logger.error(message)
        popup = Popup(
            message,
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")


def export_coco_annotation(self, mode):
    if not _check_filename_exist(self):
        return

    if mode == "pose":
        filter = "Classes Files (*.yaml);;All Files (*)"
        self.yaml_file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.tr("Select a specific coco-pose config file"),
            "",
            filter,
        )
        if not self.yaml_file:
            return
        converter = LabelConverter(pose_cfg_file=self.yaml_file)
    elif mode in ["rectangle", "polygon"]:
        filter = "Classes Files (*.txt);;All Files (*)"
        self.classes_file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.tr("Select a specific classes file"),
            "",
            filter,
        )
        if not self.classes_file:
            return
        converter = LabelConverter(classes_file=self.classes_file)

    dialog = QtWidgets.QDialog(self)
    dialog.setWindowTitle(self.tr("导出选项"))
    dialog.setMinimumWidth(500)
    dialog.setStyleSheet(get_export_option_style())

    layout = QVBoxLayout()
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)

    path_layout = QVBoxLayout()
    path_label = QtWidgets.QLabel(self.tr("导出路径"))
    path_layout.addWidget(path_label)

    path_input_layout = QHBoxLayout()
    path_input_layout.setSpacing(8)

    label_dir_path = osp.dirname(self.filename)
    if self.output_dir:
        label_dir_path = self.output_dir

    path_edit = QtWidgets.QLineEdit()
    path_edit.setText(
        osp.realpath(osp.join(label_dir_path, "..", "annotations"))
    )
    path_edit.setPlaceholderText(self.tr("Select Export Directory"))

    def browse_export_path():
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.tr("Select Export Directory"),
            path_edit.text(),
            QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if path:
            path_edit.setText(path)

    path_button = QtWidgets.QPushButton(self.tr("Browse"))
    path_button.clicked.connect(browse_export_path)
    path_button.setStyleSheet(get_cancel_btn_style())

    path_input_layout.addWidget(path_edit)
    path_input_layout.addWidget(path_button)
    path_layout.addLayout(path_input_layout)
    layout.addLayout(path_layout)

    # 高级标签筛选按钮
    advanced_filter_layout = QHBoxLayout()
    advanced_filter_button = QtWidgets.QPushButton(self.tr("筛选标签"))
    advanced_filter_button.setMinimumWidth(120)
    advanced_filter_button.setStyleSheet(get_cancel_btn_style())

    # 存储筛选配置
    filter_config = {
        'enabled': False,
        'mode': 'include',
        'match_condition': 'any',
        'labels': []
    }

    def open_label_filter_dialog():
        # 获取所有唯一标签
        unique_labels = []
        if hasattr(self, 'unique_label_list'):
            for i in range(self.unique_label_list.count()):
                item = self.unique_label_list.item(i)
                label_text = item.data(Qt.UserRole)
                if label_text:
                    unique_labels.append(label_text)

        if not unique_labels:
            popup = Popup(
                self.tr("没有找到标签，请先标注图片"),
                self,
                icon=new_icon_path("warning", "svg"),
            )
            popup.show_popup(self, position="center")
            return

        filter_dialog = LabelFilterDialog(unique_labels, self)
        if filter_dialog.exec_() == QtWidgets.QDialog.Accepted:
            nonlocal filter_config
            filter_config = filter_dialog.get_filter_config()

    advanced_filter_button.clicked.connect(open_label_filter_dialog)
    advanced_filter_layout.addWidget(advanced_filter_button)
    advanced_filter_layout.addStretch()
    layout.addLayout(advanced_filter_layout)

    button_layout = QHBoxLayout()
    button_layout.setContentsMargins(0, 16, 0, 0)
    button_layout.setSpacing(8)

    cancel_button = QtWidgets.QPushButton(self.tr("Cancel"))
    cancel_button.clicked.connect(dialog.reject)
    cancel_button.setStyleSheet(get_cancel_btn_style())

    ok_button = QtWidgets.QPushButton(self.tr("OK"))
    ok_button.clicked.connect(dialog.accept)
    ok_button.setStyleSheet(get_ok_btn_style())

    button_layout.addStretch()
    button_layout.addWidget(cancel_button)
    button_layout.addWidget(ok_button)
    layout.addLayout(button_layout)

    dialog.setLayout(layout)
    result = dialog.exec_()

    if not result:
        return

    save_path = path_edit.text()
    if osp.exists(save_path):
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setIcon(QtWidgets.QMessageBox.Warning)
        msg_box.setWindowTitle(self.tr("输出目录已存在！"))
        msg_box.setText(self.tr("目录已存在，请选择一个操作："))
        msg_box.setInformativeText(
            self.tr(
                "• 覆盖 - 覆盖现有目录\n"
                "• 取消 - 中止导出"
            )
        )

        msg_box.addButton(self.tr("覆盖"), QtWidgets.QMessageBox.YesRole)
        cancel_button = msg_box.addButton(
            self.tr("取消"), QtWidgets.QMessageBox.RejectRole
        )
        msg_box.setStyleSheet(get_msg_box_style())
        msg_box.exec_()

        clicked_button = msg_box.clickedButton()
        if clicked_button == cancel_button:
            return
        else:
            shutil.rmtree(save_path)
            os.makedirs(save_path)
    else:
        os.makedirs(save_path)

    image_list = self.image_list if self.image_list else [self.filename]
    progress_dialog = QProgressDialog(
        self.tr("Exporting..."), self.tr("Cancel"), 0, 0, self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("Progress"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setRange(0, 0)
    progress_dialog.setStyleSheet(get_progress_dialog_style())

    self.export_thread = ExportThread(
        converter, image_list, label_dir_path, save_path, mode
    )

    def on_export_finished(success, error_msg):
        progress_dialog.close()
        if success:
            template = self.tr(
                "导出标注成功！\n"
                "结果已保存到：\n"
                "%s"
            )
            message_text = template % save_path
            popup = Popup(
                message_text,
                self,
                icon=new_icon_path("copy-green", "svg"),
            )
            popup.show_popup(self, popup_height=65, position="center")
        else:
            message = (
                f"Error occurred while exporting annotations: {str(error_msg)}"
            )
            logger.error(message)
            popup = Popup(
                message,
                self,
                icon=new_icon_path("error", "svg"),
            )
            popup.show_popup(self, position="center")

    self.export_thread.finished.connect(on_export_finished)

    progress_dialog.show()
    self.export_thread.start()

    progress_dialog.canceled.connect(self.export_thread.terminate)


def export_dota_annotation(self):
    if not _check_filename_exist(self):
        return

    filter = "Classes Files (*.txt);;All Files (*)"
    self.classes_file, _ = QtWidgets.QFileDialog.getOpenFileName(
        self,
        self.tr("Select a specific classes file"),
        "",
        filter,
    )
    if not self.classes_file:
        return

    dialog = QtWidgets.QDialog(self)
    dialog.setWindowTitle(self.tr("导出选项"))
    dialog.setMinimumWidth(500)
    dialog.setStyleSheet(get_export_option_style())

    layout = QVBoxLayout()
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)

    path_layout = QVBoxLayout()
    path_label = QtWidgets.QLabel(self.tr("导出路径"))
    path_layout.addWidget(path_label)

    path_input_layout = QHBoxLayout()
    path_input_layout.setSpacing(8)

    path_edit = QtWidgets.QLineEdit()
    path_edit.setText(
        osp.realpath(osp.join(osp.dirname(self.filename), "..", "labelTxt"))
    )
    path_edit.setPlaceholderText(self.tr("Select Export Directory"))

    def browse_export_path():
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.tr("Select Export Directory"),
            path_edit.text(),
            QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if path:
            path_edit.setText(path)

    path_button = QtWidgets.QPushButton(self.tr("Browse"))
    path_button.clicked.connect(browse_export_path)
    path_button.setStyleSheet(get_cancel_btn_style())

    path_input_layout.addWidget(path_edit)
    path_input_layout.addWidget(path_button)
    path_layout.addLayout(path_input_layout)
    layout.addLayout(path_layout)

    button_layout = QHBoxLayout()
    button_layout.setContentsMargins(0, 16, 0, 0)
    button_layout.setSpacing(8)

    cancel_button = QtWidgets.QPushButton(self.tr("Cancel"))
    cancel_button.clicked.connect(dialog.reject)
    cancel_button.setStyleSheet(get_cancel_btn_style())

    ok_button = QtWidgets.QPushButton(self.tr("OK"))
    ok_button.clicked.connect(dialog.accept)
    ok_button.setStyleSheet(get_ok_btn_style())

    button_layout.addStretch()
    button_layout.addWidget(cancel_button)
    button_layout.addWidget(ok_button)
    layout.addLayout(button_layout)

    dialog.setLayout(layout)
    result = dialog.exec_()

    if not result:
        return

    save_path = path_edit.text()

    if osp.exists(save_path):
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setIcon(QtWidgets.QMessageBox.Warning)
        msg_box.setWindowTitle(self.tr("输出目录已存在！"))
        msg_box.setText(self.tr("目录已存在，请选择一个操作："))
        msg_box.setInformativeText(
            self.tr(
                "• 是 (Yes) - 合并到现有文件\n"
                "• 否 (No) - 删除现有目录\n"
                "• 取消 (Cancel) - 中止导出"
            )
        )

        msg_box.addButton(self.tr("是"), QtWidgets.QMessageBox.YesRole)
        no_button = msg_box.addButton(
            self.tr("否"), QtWidgets.QMessageBox.NoRole
        )
        cancel_button = msg_box.addButton(
            self.tr("取消"), QtWidgets.QMessageBox.RejectRole
        )
        msg_box.setStyleSheet(get_msg_box_style())
        msg_box.exec_()

        clicked_button = msg_box.clickedButton()
        if clicked_button == no_button:
            shutil.rmtree(save_path)
            os.makedirs(save_path)
        elif clicked_button == cancel_button:
            return
    else:
        os.makedirs(save_path)

    converter = LabelConverter(classes_file=self.classes_file)

    image_list = self.image_list if self.image_list else [self.filename]
    label_dir_path = osp.dirname(self.filename)
    if self.output_dir:
        label_dir_path = self.output_dir

    progress_dialog = QProgressDialog(
        self.tr("Exporting..."), self.tr("Cancel"), 0, len(image_list), self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("Progress"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setStyleSheet(
        get_progress_dialog_style(color="#1d1d1f", height=20)
    )

    try:
        for i, image_file in enumerate(image_list):
            image_file_name = osp.basename(image_file)
            label_file_name = osp.splitext(image_file_name)[0] + ".json"
            dst_file_name = osp.splitext(image_file_name)[0] + ".txt"

            # 修复：根据图片的实际路径找对应的JSON文件
            image_dir = osp.dirname(image_file)
            if self.output_dir:
                if hasattr(self, 'last_open_dir') and self.last_open_dir:
                    rel_path = osp.relpath(image_dir, self.last_open_dir)
                    src_file = osp.join(self.output_dir, rel_path, label_file_name)
                else:
                    src_file = osp.join(self.output_dir, label_file_name)
            else:
                src_file = osp.join(image_dir, label_file_name)
            
            dst_file = osp.join(save_path, dst_file_name)

            if not osp.exists(src_file):
                pathlib.Path(dst_file).touch()
            else:
                converter.custom_to_dota(src_file, dst_file)

            progress_dialog.setValue(i)
            if progress_dialog.wasCanceled():
                break

        progress_dialog.close()
        template = self.tr(
            "导出标注成功！\n"
            "结果已保存到：\n"
            "%s"
        )
        message_text = template % save_path
        popup = Popup(
            message_text,
            self,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self, popup_height=65, position="center")

    except Exception as e:
        message = f"Error occurred while exporting annotations: {str(e)}"
        progress_dialog.close()
        logger.error(message)
        popup = Popup(
            message,
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")


def export_mask_annotation(self):
    if not _check_filename_exist(self):
        return

    filter = "JSON Files (*.json);;All Files (*)"
    color_map_file, _ = QtWidgets.QFileDialog.getOpenFileName(
        self,
        self.tr("Select a specific color_map file"),
        "",
        filter,
    )
    if not color_map_file:
        return

    with open(color_map_file, "r", encoding="utf-8") as f:
        mapping_table = json.load(f)

    dialog = QtWidgets.QDialog(self)
    dialog.setWindowTitle(self.tr("导出选项"))
    dialog.setMinimumWidth(500)
    dialog.setStyleSheet(get_export_option_style())

    layout = QVBoxLayout()
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)

    path_layout = QVBoxLayout()
    path_label = QtWidgets.QLabel(self.tr("导出路径"))
    path_layout.addWidget(path_label)

    path_input_layout = QHBoxLayout()
    path_input_layout.setSpacing(8)

    label_dir_path = osp.dirname(self.filename)
    if self.output_dir:
        label_dir_path = self.output_dir

    path_edit = QtWidgets.QLineEdit()
    path_edit.setText(osp.realpath(osp.join(label_dir_path, "..", "masks")))
    path_edit.setPlaceholderText(self.tr("Select Export Directory"))

    def browse_export_path():
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.tr("Select Export Directory"),
            path_edit.text(),
            QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if path:
            path_edit.setText(path)

    path_button = QtWidgets.QPushButton(self.tr("Browse"))
    path_button.clicked.connect(browse_export_path)
    path_button.setStyleSheet(get_cancel_btn_style())

    path_input_layout.addWidget(path_edit)
    path_input_layout.addWidget(path_button)
    path_layout.addLayout(path_input_layout)
    layout.addLayout(path_layout)

    button_layout = QHBoxLayout()
    button_layout.setContentsMargins(0, 16, 0, 0)
    button_layout.setSpacing(8)

    cancel_button = QtWidgets.QPushButton(self.tr("Cancel"))
    cancel_button.clicked.connect(dialog.reject)
    cancel_button.setStyleSheet(get_cancel_btn_style())

    ok_button = QtWidgets.QPushButton(self.tr("OK"))
    ok_button.clicked.connect(dialog.accept)
    ok_button.setStyleSheet(get_ok_btn_style())

    button_layout.addStretch()
    button_layout.addWidget(cancel_button)
    button_layout.addWidget(ok_button)
    layout.addLayout(button_layout)

    dialog.setLayout(layout)
    result = dialog.exec_()

    if not result:
        return

    save_path = path_edit.text()
    if osp.exists(save_path):
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setIcon(QtWidgets.QMessageBox.Warning)
        msg_box.setWindowTitle(self.tr("输出目录已存在！"))
        msg_box.setText(self.tr("目录已存在，请选择一个操作："))
        msg_box.setInformativeText(
            self.tr(
                "• 覆盖 - 覆盖现有目录\n"
                "• 取消 - 中止导出"
            )
        )

        msg_box.addButton(self.tr("覆盖"), QtWidgets.QMessageBox.YesRole)
        cancel_button = msg_box.addButton(
            self.tr("取消"), QtWidgets.QMessageBox.RejectRole
        )
        msg_box.setStyleSheet(get_msg_box_style())
        msg_box.exec_()

        clicked_button = msg_box.clickedButton()
        if clicked_button == cancel_button:
            return
        else:
            shutil.rmtree(save_path)
            os.makedirs(save_path)
    else:
        os.makedirs(save_path)

    converter = LabelConverter()
    image_list = self.image_list if self.image_list else [self.filename]

    progress_dialog = QProgressDialog(
        self.tr("Exporting..."), self.tr("Cancel"), 0, len(image_list), self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("Progress"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setRange(0, 0)
    progress_dialog.setStyleSheet(
        get_progress_dialog_style(color="#1d1d1f", height=20)
    )

    try:
        for i, image_file in enumerate(image_list):
            image_file_name = osp.basename(image_file)
            label_file_name = osp.splitext(image_file_name)[0] + ".json"
            dst_file_name = osp.splitext(image_file_name)[0] + ".png"

            # 修复：根据图片的实际路径找对应的JSON文件
            image_dir = osp.dirname(image_file)
            if self.output_dir:
                if hasattr(self, 'last_open_dir') and self.last_open_dir:
                    rel_path = osp.relpath(image_dir, self.last_open_dir)
                    src_file = osp.join(self.output_dir, rel_path, label_file_name)
                else:
                    src_file = osp.join(self.output_dir, label_file_name)
            else:
                src_file = osp.join(image_dir, label_file_name)
            
            dst_file = osp.join(save_path, dst_file_name)

            if not osp.exists(src_file):
                continue

            converter.custom_to_mask(src_file, dst_file, mapping_table)

            progress_dialog.setValue(i)
            if progress_dialog.wasCanceled():
                break

        progress_dialog.close()
        template = self.tr(
            "导出标注成功！\n"
            "结果已保存到：\n"
            "%s"
        )
        message_text = template % save_path
        popup = Popup(
            message_text,
            self,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self, popup_height=65, position="center")

    except Exception as e:
        message = f"Error occurred while exporting annotations: {str(e)}"
        progress_dialog.close()
        logger.error(message)
        popup = Popup(
            message,
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")


def export_mot_annotation(self, mode):
    if not _check_filename_exist(self):
        return

    filter = "Classes Files (*.txt);;All Files (*)"
    self.classes_file, _ = QtWidgets.QFileDialog.getOpenFileName(
        self,
        self.tr("Select a specific classes file"),
        "",
        filter,
    )
    if not self.classes_file:
        return
    converter = LabelConverter(classes_file=self.classes_file)

    dialog = QtWidgets.QDialog(self)
    dialog.setWindowTitle(self.tr("导出选项"))
    dialog.setMinimumWidth(500)
    dialog.setStyleSheet(get_export_option_style())

    layout = QVBoxLayout()
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)

    path_layout = QVBoxLayout()
    path_label = QtWidgets.QLabel(self.tr("导出路径"))
    path_layout.addWidget(path_label)

    path_input_layout = QHBoxLayout()
    path_input_layout.setSpacing(8)

    label_dir_path = osp.dirname(self.filename)
    if self.output_dir:
        label_dir_path = self.output_dir

    path_edit = QtWidgets.QLineEdit()
    path_edit.setText(osp.realpath(osp.join(label_dir_path, "..", mode)))
    path_edit.setPlaceholderText(self.tr("Select Export Directory"))

    def browse_export_path():
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.tr("Select Export Directory"),
            path_edit.text(),
            QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if path:
            path_edit.setText(path)

    path_button = QtWidgets.QPushButton(self.tr("Browse"))
    path_button.clicked.connect(browse_export_path)
    path_button.setStyleSheet(get_cancel_btn_style())

    path_input_layout.addWidget(path_edit)
    path_input_layout.addWidget(path_button)
    path_layout.addLayout(path_input_layout)
    layout.addLayout(path_layout)

    button_layout = QHBoxLayout()
    button_layout.setContentsMargins(0, 16, 0, 0)
    button_layout.setSpacing(8)

    cancel_button = QtWidgets.QPushButton(self.tr("Cancel"))
    cancel_button.clicked.connect(dialog.reject)
    cancel_button.setStyleSheet(get_cancel_btn_style())

    ok_button = QtWidgets.QPushButton(self.tr("OK"))
    ok_button.clicked.connect(dialog.accept)
    ok_button.setStyleSheet(get_ok_btn_style())

    button_layout.addStretch()
    button_layout.addWidget(cancel_button)
    button_layout.addWidget(ok_button)
    layout.addLayout(button_layout)

    dialog.setLayout(layout)
    result = dialog.exec_()

    if not result:
        return

    save_path = path_edit.text()
    if osp.exists(save_path):
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setIcon(QtWidgets.QMessageBox.Warning)
        msg_box.setWindowTitle(self.tr("输出目录已存在！"))
        msg_box.setText(self.tr("目录已存在，请选择一个操作："))
        msg_box.setInformativeText(
            self.tr(
                "• 覆盖 - 覆盖现有目录\n"
                "• 取消 - 中止导出"
            )
        )

        msg_box.addButton(self.tr("覆盖"), QtWidgets.QMessageBox.YesRole)
        cancel_button = msg_box.addButton(
            self.tr("取消"), QtWidgets.QMessageBox.RejectRole
        )
        msg_box.setStyleSheet(get_msg_box_style())
        msg_box.exec_()

        clicked_button = msg_box.clickedButton()
        if clicked_button == cancel_button:
            return
        else:
            shutil.rmtree(save_path)
            os.makedirs(save_path)
    else:
        os.makedirs(save_path)

    image_list = self.image_list if self.image_list else [self.filename]
    progress_dialog = QProgressDialog(
        self.tr("Exporting..."), self.tr("Cancel"), 0, 0, self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("Progress"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setRange(0, 0)
    progress_dialog.setStyleSheet(get_progress_dialog_style())

    self.export_thread = ExportThread(
        converter, image_list, label_dir_path, save_path, mode
    )

    def on_export_finished(success, error_msg):
        progress_dialog.close()
        if success:
            template = self.tr(
                "导出标注成功！\n"
                "结果已保存到：\n"
                "%s"
            )
            message_text = template % save_path
            popup = Popup(
                message_text,
                self,
                icon=new_icon_path("copy-green", "svg"),
            )
            popup.show_popup(self, popup_height=65, position="center")
        else:
            message = (
                f"Error occurred while exporting annotations: {str(error_msg)}"
            )
            logger.error(message)
            popup = Popup(
                message,
                self,
                icon=new_icon_path("error", "svg"),
            )
            popup.show_popup(self, position="center")

    self.export_thread.finished.connect(on_export_finished)

    progress_dialog.show()
    self.export_thread.start()

    progress_dialog.canceled.connect(self.export_thread.terminate)


def export_odvg_annotation(self):
    export_mot_annotation(self, "odvg")


def export_pporc_annotation(self, mode):
    if not _check_filename_exist(self):
        return

    dialog = QtWidgets.QDialog(self)
    dialog.setWindowTitle(self.tr("导出选项"))
    dialog.setMinimumWidth(500)
    dialog.setStyleSheet(get_export_option_style())

    layout = QVBoxLayout()
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)

    path_layout = QVBoxLayout()
    path_label = QtWidgets.QLabel(self.tr("导出路径"))
    path_layout.addWidget(path_label)

    path_input_layout = QHBoxLayout()
    path_input_layout.setSpacing(8)

    label_dir_path = osp.dirname(self.filename)
    if self.output_dir:
        label_dir_path = self.output_dir

    path_edit = QtWidgets.QLineEdit()
    path_edit.setText(
        osp.realpath(osp.join(label_dir_path, "..", f"ppocr_{mode}"))
    )
    path_edit.setPlaceholderText(self.tr("Select Export Directory"))

    def browse_export_path():
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.tr("Select Export Directory"),
            path_edit.text(),
            QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if path:
            path_edit.setText(path)

    path_button = QtWidgets.QPushButton(self.tr("Browse"))
    path_button.clicked.connect(browse_export_path)
    path_button.setStyleSheet(get_cancel_btn_style())

    path_input_layout.addWidget(path_edit)
    path_input_layout.addWidget(path_button)
    path_layout.addLayout(path_input_layout)
    layout.addLayout(path_layout)

    button_layout = QHBoxLayout()
    button_layout.setContentsMargins(0, 16, 0, 0)
    button_layout.setSpacing(8)

    cancel_button = QtWidgets.QPushButton(self.tr("Cancel"))
    cancel_button.clicked.connect(dialog.reject)
    cancel_button.setStyleSheet(get_cancel_btn_style())

    ok_button = QtWidgets.QPushButton(self.tr("OK"))
    ok_button.clicked.connect(dialog.accept)
    ok_button.setStyleSheet(get_ok_btn_style())

    button_layout.addStretch()
    button_layout.addWidget(cancel_button)
    button_layout.addWidget(ok_button)
    layout.addLayout(button_layout)

    dialog.setLayout(layout)
    result = dialog.exec_()

    if not result:
        return

    save_path = path_edit.text()
    if osp.exists(save_path):
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setIcon(QtWidgets.QMessageBox.Warning)
        msg_box.setWindowTitle(self.tr("输出目录已存在！"))
        msg_box.setText(self.tr("目录已存在，请选择一个操作："))
        msg_box.setInformativeText(
            self.tr(
                "• 覆盖 - 覆盖现有目录\n"
                "• 取消 - 中止导出"
            )
        )

        msg_box.addButton(self.tr("覆盖"), QtWidgets.QMessageBox.YesRole)
        cancel_button = msg_box.addButton(
            self.tr("取消"), QtWidgets.QMessageBox.RejectRole
        )
        msg_box.setStyleSheet(get_msg_box_style())
        msg_box.exec_()

        clicked_button = msg_box.clickedButton()
        if clicked_button == cancel_button:
            return
        else:
            shutil.rmtree(save_path)
            os.makedirs(save_path)
    else:
        os.makedirs(save_path)

    if mode == "rec":
        save_crop_img_path = osp.join(save_path, "crop_img")
        if osp.exists(save_crop_img_path):
            shutil.rmtree(save_crop_img_path)
        os.makedirs(save_crop_img_path, exist_ok=True)
    elif mode == "kie":
        total_class_set = set()
        class_list_file = osp.join(save_path, "class_list.txt")

    converter = LabelConverter()

    image_list = self.image_list if self.image_list else [self.filename]
    progress_dialog = QProgressDialog(
        self.tr("Exporting..."), self.tr("Cancel"), 0, len(image_list), self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("Progress"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setStyleSheet(
        get_progress_dialog_style(color="#1d1d1f", height=20)
    )

    try:
        for i, image_file in enumerate(image_list):
            image_file_name = osp.basename(image_file)
            label_file_name = osp.splitext(image_file_name)[0] + ".json"
            label_file = osp.join(osp.dirname(image_file), label_file_name)
            if mode == "rec":
                converter.custom_to_ppocr(
                    image_file, label_file, save_path, mode
                )
            elif mode == "kie":
                class_set = converter.custom_to_ppocr(
                    image_file, label_file, save_path, mode
                )
                total_class_set = total_class_set.union(class_set)

            progress_dialog.setValue(i)
            if progress_dialog.wasCanceled():
                break

        if mode == "kie":
            with open(class_list_file, "w") as f:
                for c in total_class_set:
                    f.writelines(f"{c.upper()}\n")

        progress_dialog.close()

        template = self.tr(
            "导出标注成功！\n"
            "结果已保存到：\n"
            "%s"
        )
        message_text = template % save_path
        popup = Popup(
            message_text,
            self,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self, popup_height=65, position="center")

    except Exception as e:
        message = f"Error occurred while exporting annotations: {str(e)}"
        progress_dialog.close()
        logger.error(message)
        popup = Popup(
            message,
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")


def export_vlm_r1_ovd_annotation(self):
    if not _check_filename_exist(self):
        return

    dialog = QtWidgets.QDialog(self)
    dialog.setWindowTitle(self.tr("Export VLM-R1 OVD Annotation"))
    dialog.setMinimumWidth(500)
    dialog.setStyleSheet(get_export_option_style())

    main_layout = QVBoxLayout()
    main_layout.setContentsMargins(24, 24, 24, 24)
    main_layout.setSpacing(16)

    # --- File path selection ---
    path_layout = QVBoxLayout()
    path_label = QtWidgets.QLabel(self.tr("Export to"))
    path_layout.addWidget(path_label)

    path_input_layout = QHBoxLayout()
    path_input_layout.setSpacing(8)

    # Default export path and filename
    label_dir_path = osp.dirname(self.filename)
    if self.output_dir:
        label_dir_path = self.output_dir
    default_export_path = osp.realpath(
        osp.join(label_dir_path, "..", "vlm_r1_ovd.jsonl")
    )

    path_edit = QtWidgets.QLineEdit()
    path_edit.setText(default_export_path)
    path_edit.setPlaceholderText(self.tr("Select Export File"))

    def browse_export_file():
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            dialog,
            self.tr("Select Export File"),
            path_edit.text(),
            "JSONL Files (*.jsonl)",
            options=QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if path:
            if not path.endswith(".jsonl"):
                path += ".jsonl"
            path_edit.setText(path)

    path_button = QtWidgets.QPushButton(self.tr("Browse"))
    path_button.clicked.connect(browse_export_file)
    path_button.setStyleSheet(get_cancel_btn_style())

    path_input_layout.addWidget(path_edit)
    path_input_layout.addWidget(path_button)
    path_layout.addLayout(path_input_layout)
    main_layout.addLayout(path_layout)

    # --- Prefix input ---
    prefix_layout = QVBoxLayout()
    prefix_layout.setSpacing(8)

    prefix_label = QHBoxLayout()
    prefix_label.setSpacing(2)

    prefix_title_label = QtWidgets.QLabel(self.tr("Prefix:"))
    prefix_preview_label = QtWidgets.QLabel("")
    prefix_preview_label.setStyleSheet(
        "color: gray; font-style: italic; padding-left: 5px;"
    )

    prefix_label.addWidget(prefix_title_label)
    prefix_label.addWidget(prefix_preview_label)
    prefix_label.addStretch()

    prefix_edit = QtWidgets.QLineEdit()
    prefix_edit_placeholder = self.tr(
        "Optional prefix for image filenames (e.g., 'path/to/images/')"
    )
    prefix_edit.setPlaceholderText(prefix_edit_placeholder)

    prefix_layout.addLayout(prefix_label)
    prefix_layout.addWidget(prefix_edit)
    main_layout.addLayout(prefix_layout)

    def _update_preview():
        prefix = prefix_edit.text()
        if not prefix:
            prefix = "demo.jpg"
        else:
            prefix += "demo.jpg"
        preview_text = self.tr("{}").format(prefix)
        prefix_preview_label.setText(preview_text)

    prefix_edit.textChanged.connect(_update_preview)
    _update_preview()

    # --- Class Filtering ---
    self.classes_file = None

    # --- Class Label ---
    class_label = QtWidgets.QLabel(self.tr("Use specific classes? (Optional)"))
    main_layout.addWidget(class_label)

    # --- Class Path Layout ---
    class_path_layout = QHBoxLayout()
    class_path_layout.setSpacing(8)

    class_path_edit = QtWidgets.QLineEdit()
    class_path_edit.setPlaceholderText(
        self.tr("Select a specific classes file")
    )

    def _handle_class_file_upload():
        filter = "Classes Files (*.txt);;All Files (*)"
        classes_file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.tr("Select a specific classes file"),
            "",
            filter,
        )
        class_path_edit.setText(classes_file)

    class_path_button = QtWidgets.QPushButton(self.tr("Upload"))
    class_path_edit.textChanged.connect(
        lambda text: setattr(self, "classes_file", text)
    )
    class_path_button.clicked.connect(_handle_class_file_upload)
    class_path_button.setStyleSheet(get_cancel_btn_style())

    class_path_layout.addWidget(class_path_edit)
    class_path_layout.addWidget(class_path_button)
    main_layout.addLayout(class_path_layout)

    # --- Hint Label ---
    class_hint_label = QtWidgets.QLabel(
        self.tr(
            "Hint: If you don't upload a specific classes file, all unique labels found in one of the annotations will be used for the export."
        )
    )
    class_hint_label.setStyleSheet(
        "color: gray; font-style: italic; padding-left: 5px;"
    )
    class_hint_label.setWordWrap(True)
    main_layout.addWidget(class_hint_label)

    # --- Buttons layout ---
    button_layout = QHBoxLayout()
    button_layout.setContentsMargins(0, 16, 0, 0)
    button_layout.setSpacing(8)

    cancel_button = QtWidgets.QPushButton(self.tr("Cancel"))
    cancel_button.clicked.connect(dialog.reject)
    cancel_button.setStyleSheet(get_cancel_btn_style())

    ok_button = QtWidgets.QPushButton(self.tr("OK"))
    ok_button.clicked.connect(dialog.accept)
    ok_button.setStyleSheet(get_ok_btn_style())

    button_layout.addWidget(cancel_button)
    button_layout.addWidget(ok_button)
    main_layout.addLayout(button_layout)

    dialog.setLayout(main_layout)
    result = dialog.exec_()

    if not result:
        return

    save_path = path_edit.text()
    prefix = prefix_edit.text().strip()

    # --- File Exists Check ---
    if osp.exists(save_path):
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setIcon(QtWidgets.QMessageBox.Warning)
        msg_box.setWindowTitle(self.tr("文件已存在！"))
        msg_box.setText(self.tr("文件已存在，请选择一个操作："))
        msg_box.setInformativeText(
            self.tr(
                "• 覆盖 - 替换现有文件\n"
                "• 取消 - 中止导出"
            )
        )
        _ = msg_box.addButton(
            self.tr("覆盖"), QtWidgets.QMessageBox.YesRole
        )
        cancel_msg_button = msg_box.addButton(
            self.tr("取消"), QtWidgets.QMessageBox.RejectRole
        )
        msg_box.setDefaultButton(cancel_msg_button)

        msg_box.setStyleSheet(get_msg_box_style())
        msg_box.exec_()

        clicked_button = msg_box.clickedButton()
        if clicked_button == cancel_msg_button:
            return

    image_list = self.image_list if self.image_list else [self.filename]
    label_dir_path = osp.dirname(self.filename)
    if self.output_dir:
        label_dir_path = self.output_dir

    # --- Attempt to create LabelConverter first ---
    try:
        converter = LabelConverter(classes_file=self.classes_file)
    except Exception as e:
        logger.error(f"Failed to initialize LabelConverter: {e}")
        template = self.tr("Error initializing export: %s")
        popup = Popup(
            template % e,
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")
        return

    # --- Progress Dialog ---
    progress_dialog = QProgressDialog(
        self.tr("Exporting..."), self.tr("Cancel"), 0, 0, self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("Progress"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setRange(0, 0)
    progress_dialog.setStyleSheet(get_progress_dialog_style())

    try:
        self.export_thread = ExportThread(
            converter,
            image_list,
            label_dir_path,
            save_path,
            "vlm_r1_ovd",
            prefix=prefix,
        )

        def on_export_finished(success, error_msg):
            progress_dialog.close()
            if success:
                template = self.tr(
                    "导出标注成功！\n"
                    "结果已保存到：\n"
                    "%s"
                )
                message_text = template % save_path
                popup = Popup(
                    message_text,
                    self,
                    icon=new_icon_path("copy-green", "svg"),
                )
                popup.show_popup(self, popup_height=65, position="center")
            else:
                message = f"Error occurred while exporting annotations: {str(error_msg)}"
                logger.error(message)
                popup = Popup(
                    message,
                    self,
                    icon=new_icon_path("error", "svg"),
                )
                popup.show_popup(self, position="center")

        self.export_thread.finished.connect(on_export_finished)

        progress_dialog.show()
        self.export_thread.start()

        progress_dialog.canceled.connect(self.export_thread.terminate)

    except Exception as e:
        message = f"Error occurred while exporting annotations: {str(e)}"
        progress_dialog.close()
        logger.error(message)
        popup = Popup(
            message,
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")

def export_imagetrans_annotation(self):
    logger.info("Starting export_imagetrans_annotation")
    if not _check_filename_exist(self):
        return

    # 1. Ask user for the template .itp file
    template_path, _ = QtWidgets.QFileDialog.getOpenFileName(
        self,
        "选择 ImageTrans 模板文件 (.itp)",
        self.current_path(),
        "ImageTrans Project (*.itp);;All Files (*)",
    )
    if not template_path:
        return

    # 2. Get unique labels and show exclusion dialog
    unique_labels = []
    for i in range(self.unique_label_list.count()):
        item = self.unique_label_list.item(i)
        label_text = item.data(Qt.UserRole)
        unique_labels.append(label_text)

    if not unique_labels:
        excluded_labels = []
    else:
        exclusion_dialog = LabelExclusionDialog(unique_labels, self)
        if exclusion_dialog.exec_() == QtWidgets.QDialog.Accepted:
            excluded_labels = exclusion_dialog.get_excluded_labels()
        else:
            return  # User cancelled

    # 3. Ask for save path
    default_path = osp.join(
        osp.dirname(self.filename), "project_converted.itp"
    )
    save_path, _ = QtWidgets.QFileDialog.getSaveFileName(
        self,
        "导出 ImageTrans ipt",
        default_path,
        "ImageTrans Project (*.itp)",
    )

    if not save_path:
        return

    # 4. Proceed with export
    image_list = self.image_list if self.image_list else [self.filename]
    label_dir_path = osp.dirname(self.filename)
    if self.output_dir:
        label_dir_path = self.output_dir

    converter = LabelConverter()

    progress_dialog = QProgressDialog(
        self.tr("正在导出为 ImageTrans 项目..."), self.tr("取消"), 0, 0, self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("导出进度"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setRange(0, 0) # Indeterminate
    progress_dialog.setStyleSheet(
        get_progress_dialog_style(color="#1d1d1f", height=20)
    )

    self.export_thread = ExportImageTransThread(
        converter,
        image_list,
        label_dir_path,
        template_path,
        save_path,
        excluded_labels,
    )

    def on_export_finished(success, error_msg):
        logger.info(f"on_export_finished called with success={success}")
        progress_dialog.close()
        if success:
            QtWidgets.QApplication.beep()
            template = self.tr(
                "ImageTrans 项目导出成功！\n"
                "文件已保存到：\n"
                "%s"
            )
            message_text = template % save_path
            popup = Popup(
                message_text,
                self,
                icon=new_icon_path("copy-green", "svg"),
            )
            popup.show_popup(self, popup_height=65, position="center")
        else:
            message = f"导出时发生错误: {str(error_msg)}"
            logger.error(message)
            popup = Popup(
                message,
                self,
                icon=new_icon_path("error", "svg"),
            )
            popup.show_popup(self, position="center")

    self.export_thread.finished.connect(on_export_finished)

    logger.info("Starting ExportImageTransThread")
    progress_dialog.show()
    self.export_thread.start()

    progress_dialog.canceled.connect(self.export_thread.terminate)


def export_mtu_json_annotation(self):
    if not _check_filename_exist(self):
        return

    unique_labels = []
    seen = set()
    if hasattr(self, "unique_label_list"):
        for i in range(self.unique_label_list.count()):
            item = self.unique_label_list.item(i)
            label_text = item.data(Qt.UserRole)
            if not label_text:
                label_text = item.text()
            if label_text and label_text not in seen:
                seen.add(label_text)
                unique_labels.append(label_text)

    excluded_labels = []
    if unique_labels:
        exclusion_dialog = LabelExclusionDialog(unique_labels, self)
        if exclusion_dialog.exec_() == QtWidgets.QDialog.Accepted:
            excluded_labels = exclusion_dialog.get_excluded_labels()
        else:
            return

    save_path = QtWidgets.QFileDialog.getExistingDirectory(
        self,
        self.tr("选择 MTU JSON 导出目录"),
        osp.dirname(self.filename),
    )
    if not save_path:
        return

    target_json_dir = osp.join(save_path, "manga_translator_work", "json")
    if osp.exists(target_json_dir) and os.listdir(target_json_dir):
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setIcon(QtWidgets.QMessageBox.Warning)
        msg_box.setWindowTitle(self.tr("已存在MTUJSON目录"))
        msg_box.setText(self.tr("是否覆盖"))
        msg_box.setInformativeText(
            self.tr(
                "是 - 覆盖\n"
                "否 - 清空并导入\n"
                "取消 - 停止导入"
            )
        )
        msg_box.addButton(self.tr("是"), QtWidgets.QMessageBox.YesRole)
        no_button = msg_box.addButton(
            self.tr("否"), QtWidgets.QMessageBox.NoRole
        )
        cancel_button = msg_box.addButton(
            self.tr("取消"), QtWidgets.QMessageBox.RejectRole
        )
        msg_box.setStyleSheet(get_msg_box_style())
        msg_box.exec_()

        clicked_button = msg_box.clickedButton()
        if clicked_button == no_button:
            shutil.rmtree(target_json_dir)
            os.makedirs(target_json_dir, exist_ok=True)
        elif clicked_button == cancel_button:
            return
    else:
        os.makedirs(target_json_dir, exist_ok=True)

    image_list = self.image_list if self.image_list else [self.filename]

    progress_dialog = QProgressDialog(
        self.tr("正在导出 MTU JSON..."), self.tr("取消"), 0, 0, self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("导出进度"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setRange(0, 0)
    progress_dialog.setStyleSheet(
        get_progress_dialog_style(color="#1d1d1f", height=20)
    )

    self.export_thread = ExportMTUJsonThread(
        image_list=image_list,
        save_root_path=save_path,
        excluded_labels=excluded_labels,
        output_dir=self.output_dir,
        last_open_dir=getattr(self, "last_open_dir", None),
    )

    def on_export_finished(success, error_msg):
        progress_dialog.close()
        if success:
            stats = getattr(self.export_thread, "stats", {})
            out_dir = getattr(self.export_thread, "output_json_dir", save_path)
            template = (
                "MTU JSON 导出完成。\n"
                "输出目录：\n%s\n\n"
                "总图片: %d  生成JSON: %d  失败: %d  过滤标签框: %d"
            )
            message_text = template % (
                out_dir,
                int(stats.get("total_images", 0)),
                int(stats.get("generated_json", 0)),
                int(stats.get("failed", 0)),
                int(stats.get("filtered_textlines", 0)),
            )
            error_samples = stats.get("error_samples", []) or []
            if error_samples:
                message_text += "\n\n失败示例：\n- " + "\n- ".join(error_samples)
            popup = Popup(
                message_text,
                self,
                icon=new_icon_path("copy-green", "svg"),
            )
            popup.show_popup(self, popup_height=120, position="center")
        else:
            message = f"Error occurred while exporting MTU JSON: {str(error_msg)}"
            logger.error(message)
            popup = Popup(
                message,
                self,
                icon=new_icon_path("error", "svg"),
            )
            popup.show_popup(self, position="center")

    self.export_thread.finished.connect(on_export_finished)
    progress_dialog.show()
    self.export_thread.start()
    progress_dialog.canceled.connect(self.export_thread.terminate)


def export_ballontranslator_annotation(self):
    if not _check_filename_exist(self):
        return

    # 1. Ask user for a classes file
    filter = "Label Files (*.txt);;All Files (*)"
    classes_file, _ = QtWidgets.QFileDialog.getOpenFileName(
        self,
        "选择标签文件",
        "",
        filter,
    )
    if not classes_file:
        return

    # 2. Read labels from the file
    with open(classes_file, 'r', encoding='utf-8') as f:
        unique_labels = [line.strip() for line in f.readlines() if line.strip()]

    # 3. Show exclusion dialog
    if not unique_labels:
        excluded_labels = []
    else:
        exclusion_dialog = LabelExclusionDialog(unique_labels, self)
        if exclusion_dialog.exec_() == QtWidgets.QDialog.Accepted:
            excluded_labels = exclusion_dialog.get_excluded_labels()
        else:
            return # User cancelled

    # 4. Ask for save path
    default_path = osp.join(
        osp.dirname(self.filename), "output_ballons.json"
    )
    save_path, _ = QtWidgets.QFileDialog.getSaveFileName(
        self,
        "导出 Ballontranslator JSON",
        default_path,
        "JSON Files (*.json)",
    )

    if not save_path:
        return

    # 5. Proceed with export
    image_list = self.image_list if self.image_list else [self.filename]
    label_dir_path = osp.dirname(self.filename)
    if self.output_dir:
        label_dir_path = self.output_dir

    converter = LabelConverter()

    progress_dialog = QProgressDialog(
        self.tr("正在导出为 Ballontranslator 项目..."), self.tr("取消"), 0, 0, self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("导出进度"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setRange(0, 0)  # Indeterminate
    progress_dialog.setStyleSheet(
        get_progress_dialog_style(color="#1d1d1f", height=20)
    )

    self.export_thread = ExportBallonTranslatorThread(
        converter,
        image_list,
        label_dir_path,
        save_path,
        excluded_labels,
    )

    def on_export_finished(success, error_msg):
        progress_dialog.close()
        if success:
            template = self.tr(
                "导出标注成功！\n"
                "结果已保存到：\n"
                "%s"
            )
            message_text = template % save_path
            popup = Popup(
                message_text,
                self,
                icon=new_icon_path("copy-green", "svg"),
            )
            popup.show_popup(self, popup_height=65, position="center")
        else:
            message = f"Error occurred while exporting annotations: {str(error_msg)}"
            logger.error(message)
            popup = Popup(
                message,
                self,
                icon=new_icon_path("error", "svg"),
            )
            popup.show_popup(self, position="center")

    self.export_thread.finished.connect(on_export_finished)

    progress_dialog.show()
    self.export_thread.start()

    progress_dialog.canceled.connect(self.export_thread.terminate)

class ExportRotatedJsonThread(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(
        self,
        converter,
        image_list,
        label_dir_path,
        save_path,
        excluded_labels,
    ):
        super().__init__()
        self.converter = converter
        self.image_list = image_list
        self.label_dir_path = label_dir_path
        self.save_path = save_path
        self.excluded_labels = excluded_labels

    def run(self):
        try:
            time.sleep(1)
            self.converter.custom_to_rotated_json(
                self.image_list,
                self.label_dir_path,
                self.save_path,
                self.excluded_labels,
            )
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))

def export_rotated_json_annotation(self):
    if not _check_filename_exist(self):
        return

    # 1. Ask user for a classes file
    filter = "Label Files (*.txt);;All Files (*)"
    classes_file, _ = QtWidgets.QFileDialog.getOpenFileName(
        self,
        "选择标签文件",
        "",
        filter,
    )
    if not classes_file:
        return

    # 2. Read labels from the file
    with open(classes_file, 'r', encoding='utf-8') as f:
        unique_labels = [line.strip() for line in f.readlines() if line.strip()]

    # 3. Show exclusion dialog
    if not unique_labels:
        excluded_labels = []
    else:
        exclusion_dialog = LabelExclusionDialog(unique_labels, self)
        if exclusion_dialog.exec_() == QtWidgets.QDialog.Accepted:
            excluded_labels = exclusion_dialog.get_excluded_labels()
        else:
            return # User cancelled

    # 4. Ask for save path
    default_path = osp.join(
        osp.dirname(self.filename), "output_rotated.json"
    )
    save_path, _ = QtWidgets.QFileDialog.getSaveFileName(
        self,
        "导出BallonsTranslator JSON 旋转框",
        default_path,
        "JSON Files (*.json)",
    )

    if not save_path:
        return

    # 5. Proceed with export
    image_list = self.image_list if self.image_list else [self.filename]
    label_dir_path = osp.dirname(self.filename)
    if self.output_dir:
        label_dir_path = self.output_dir

    converter = LabelConverter()

    progress_dialog = QProgressDialog(
        self.tr("正在导出为旋转框JSON..."), self.tr("取消"), 0, 0, self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("导出进度"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setRange(0, 0)  # Indeterminate
    progress_dialog.setStyleSheet(
        get_progress_dialog_style(color="#1d1d1f", height=20)
    )

    self.export_thread = ExportRotatedJsonThread(
        converter,
        image_list,
        label_dir_path,
        save_path,
        excluded_labels,
    )

    def on_export_finished(success, error_msg):
        progress_dialog.close()
        if success:
            template = self.tr(
                "导出标注成功！\n"
                "结果已保存到：\n"
                "%s"
            )
            message_text = template % save_path
            popup = Popup(
                message_text,
                self,
                icon=new_icon_path("copy-green", "svg"),
            )
            popup.show_popup(self, popup_height=65, position="center")
        else:
            message = f"Error occurred while exporting annotations: {str(error_msg)}"
            logger.error(message)
            popup = Popup(
                message,
                self,
                icon=new_icon_path("error", "svg"),
            )
            popup.show_popup(self, position="center")

    self.export_thread.finished.connect(on_export_finished)

    progress_dialog.show()
    self.export_thread.start()

    progress_dialog.canceled.connect(self.export_thread.terminate)


class ExportLabelPlusThread(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(
        self,
        converter,
        image_list,
        label_dir_path,
        save_path,
    ):
        super().__init__()
        self.converter = converter
        self.image_list = image_list
        self.label_dir_path = label_dir_path
        self.save_path = save_path

    def run(self):
        try:
            time.sleep(1)
            self.converter.custom_to_labelplus(
                self.image_list,
                self.label_dir_path,
                self.save_path,
            )
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


def export_labelplus_annotation(self):
    """
    Export annotations to LabelPlus format.

    LabelPlus format uses:
    - Rectangle mode: top-right corner of the rectangle
    - Point mode: point position

    Coordinates are normalized to [0, 1] range.
    """
    if not _check_filename_exist(self):
        return

    # Get image list
    image_list = self.image_list if self.image_list else [self.filename]
    label_dir_path = osp.dirname(self.filename)
    if self.output_dir:
        label_dir_path = self.output_dir

    # Ask for save path
    default_filename = "labelplus_export.txt"
    if self.filename:
        default_filename = osp.splitext(osp.basename(self.filename))[0] + "_labelplus.txt"

    default_path = osp.join(osp.dirname(self.filename), default_filename)

    save_path, _ = QtWidgets.QFileDialog.getSaveFileName(
        self,
        self.tr("导出 LabelPlus 格式"),
        default_path,
        "Text Files (*.txt);;All Files (*)",
    )

    if not save_path:
        return

    converter = LabelConverter()

    progress_dialog = QProgressDialog(
        self.tr("正在导出为 LabelPlus 格式..."), self.tr("取消"), 0, 0, self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("导出进度"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setRange(0, 0)  # Indeterminate
    progress_dialog.setStyleSheet(
        get_progress_dialog_style(color="#1d1d1f", height=20)
    )

    self.export_thread = ExportLabelPlusThread(
        converter,
        image_list,
        label_dir_path,
        save_path,
    )

    def on_export_finished(success, error_msg):
        progress_dialog.close()
        if success:
            template = self.tr(
                "导出标注成功！\n"
                "结果已保存到：\n"
                "%s"
            )
            message_text = template % save_path
            popup = Popup(
                message_text,
                self,
                icon=new_icon_path("copy-green", "svg"),
            )
            popup.show_popup(self, popup_height=65, position="center")
        else:
            message = self.tr("导出标注时发生错误: %s") % str(error_msg)
            logger.error(message)
            popup = Popup(
                message,
                self,
                icon=new_icon_path("error", "svg"),
            )
            popup.show_popup(self, position="center")

    self.export_thread.finished.connect(on_export_finished)

    progress_dialog.show()
    self.export_thread.start()

    progress_dialog.canceled.connect(self.export_thread.terminate)


def export_description_txt(self):
    """
    导出所有标注的 description 字段到 TXT 文件
    支持每个图片一个 TXT 文件，或合并到单个 TXT 文件
    """
    if not _check_filename_exist(self):
        return

    # 创建导出选项对话框
    dialog = QtWidgets.QDialog(self)
    dialog.setWindowTitle(self.tr("导出文本到TXT"))
    dialog.setMinimumWidth(500)
    dialog.setStyleSheet(get_export_option_style())

    layout = QVBoxLayout()
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)

    # 导出模式选择（独立文件 vs 单个文件）
    export_mode_label = QtWidgets.QLabel(self.tr("导出模式"))
    layout.addWidget(export_mode_label)

    export_mode_group = QtWidgets.QButtonGroup(dialog)
    
    separate_files_radio = QtWidgets.QRadioButton(
        self.tr("每个图片一个TXT文件")
    )
    separate_files_radio.setChecked(True)
    
    single_file_radio = QtWidgets.QRadioButton(
        self.tr("合并到单个TXT文件")
    )
    
    export_mode_group.addButton(separate_files_radio, 0)
    export_mode_group.addButton(single_file_radio, 1)
    
    layout.addWidget(separate_files_radio)
    layout.addWidget(single_file_radio)

    # 导出路径选择
    path_layout = QVBoxLayout()
    path_label = QtWidgets.QLabel(self.tr("导出路径"))
    path_layout.addWidget(path_label)

    path_input_layout = QHBoxLayout()
    path_input_layout.setSpacing(8)

    path_edit = QtWidgets.QLineEdit()
    default_dir = osp.realpath(osp.join(osp.dirname(self.filename), "..", "descriptions"))
    path_edit.setText(default_dir)
    path_edit.setPlaceholderText(self.tr("选择导出目录"))

    def browse_export_path():
        if single_file_radio.isChecked():
            # 单个文件模式：选择保存文件
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                self.tr("选择导出文件"),
                path_edit.text(),
                self.tr("文本文件 (*.txt);;所有文件 (*)"),
            )
        else:
            # 独立文件模式：选择目录
            path = QtWidgets.QFileDialog.getExistingDirectory(
                self,
                self.tr("选择导出目录"),
                path_edit.text(),
                QtWidgets.QFileDialog.DontUseNativeDialog,
            )
        if path:
            path_edit.setText(path)

    def get_filename_by_text_mode():
        """根据文本模式获取默认文件名"""
        if all_radio.isChecked():
            return "全部文本.txt"
        elif source_only_radio.isChecked():
            return "原文文本.txt"
        elif target_only_radio.isChecked():
            return "译文文本.txt"
        return "全部文本.txt"

    def on_export_mode_changed():
        if single_file_radio.isChecked():
            # 切换到单个文件模式
            filename = get_filename_by_text_mode()
            default_file = osp.realpath(osp.join(osp.dirname(self.filename), "..", filename))
            path_edit.setText(default_file)
            path_edit.setPlaceholderText(self.tr("选择导出文件"))
            path_label.setText(self.tr("导出文件"))
        else:
            # 切换到独立文件模式
            default_dir = osp.realpath(osp.join(osp.dirname(self.filename), "..", "descriptions"))
            path_edit.setText(default_dir)
            path_edit.setPlaceholderText(self.tr("选择导出目录"))
            path_label.setText(self.tr("导出路径"))

    def on_text_mode_changed():
        """文本选项变化时更新文件名（仅在单文件模式下）"""
        if single_file_radio.isChecked():
            # 获取当前路径的目录部分
            current_path = path_edit.text()
            parent_dir = osp.dirname(current_path)
            # 使用新的文件名
            filename = get_filename_by_text_mode()
            new_path = osp.join(parent_dir, filename)
            path_edit.setText(new_path)

    separate_files_radio.toggled.connect(on_export_mode_changed)

    path_button = QtWidgets.QPushButton(self.tr("浏览"))
    path_button.clicked.connect(browse_export_path)
    path_button.setStyleSheet(get_cancel_btn_style())

    path_input_layout.addWidget(path_edit)
    path_input_layout.addWidget(path_button)
    path_layout.addLayout(path_input_layout)
    layout.addLayout(path_layout)

    # 导出选项
    options_label = QtWidgets.QLabel(self.tr("文本选项"))
    layout.addWidget(options_label)

    # 文本模式选择
    text_mode_group = QtWidgets.QButtonGroup(dialog)
    
    all_radio = QtWidgets.QRadioButton(
        self.tr("导出全部文本（原文/译文）")
    )
    all_radio.setToolTip(self.tr("格式：原文[TAB]译文"))
    all_radio.setChecked(True)
    
    source_only_radio = QtWidgets.QRadioButton(
        self.tr("仅导出原文（/ 前面的部分）")
    )
    source_only_radio.setToolTip(self.tr("如果文本包含 /，只导出前半部分"))
    
    target_only_radio = QtWidgets.QRadioButton(
        self.tr("仅导出译文（/ 后面的部分）")
    )
    target_only_radio.setToolTip(self.tr("如果文本包含 /，只导出后半部分"))
    
    text_mode_group.addButton(all_radio, 0)
    text_mode_group.addButton(source_only_radio, 1)
    text_mode_group.addButton(target_only_radio, 2)
    
    layout.addWidget(all_radio)
    layout.addWidget(source_only_radio)
    layout.addWidget(target_only_radio)

    # 连接文本选项信号
    all_radio.toggled.connect(on_text_mode_changed)
    source_only_radio.toggled.connect(on_text_mode_changed)
    target_only_radio.toggled.connect(on_text_mode_changed)

    # 其他选项
    skip_empty_checkbox = QtWidgets.QCheckBox(
        self.tr("跳过空文本")
    )
    skip_empty_checkbox.setChecked(True)
    layout.addWidget(skip_empty_checkbox)

    # 按钮
    button_layout = QHBoxLayout()
    button_layout.setContentsMargins(0, 16, 0, 0)
    button_layout.setSpacing(8)

    cancel_button = QtWidgets.QPushButton(self.tr("取消"))
    cancel_button.clicked.connect(dialog.reject)
    cancel_button.setStyleSheet(get_cancel_btn_style())

    ok_button = QtWidgets.QPushButton(self.tr("确定"))
    ok_button.clicked.connect(dialog.accept)
    ok_button.setStyleSheet(get_ok_btn_style())

    button_layout.addStretch()
    button_layout.addWidget(cancel_button)
    button_layout.addWidget(ok_button)
    layout.addLayout(button_layout)

    dialog.setLayout(layout)
    
    # 显示对话框
    if dialog.exec_() != QtWidgets.QDialog.Accepted:
        return
    
    # 获取导出模式
    export_to_single_file = single_file_radio.isChecked()

    # 获取选项
    save_path = path_edit.text()
    skip_empty = skip_empty_checkbox.isChecked()
    
    selected_id = text_mode_group.checkedId()
    text_mode_map = {0: 'all', 1: 'source', 2: 'target'}
    text_mode = text_mode_map.get(selected_id, 'all')

    # 检查路径是否存在
    if export_to_single_file:
        # 单文件模式：检查文件是否存在
        if osp.exists(save_path):
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Warning)
            msg_box.setWindowTitle(self.tr("文件已存在！"))
            msg_box.setText(self.tr("文件已存在，是否覆盖？"))
            msg_box.addButton(self.tr("是"), QtWidgets.QMessageBox.YesRole)
            cancel_button = msg_box.addButton(
                self.tr("取消"), QtWidgets.QMessageBox.RejectRole
            )
            msg_box.setStyleSheet(get_msg_box_style())
            msg_box.exec_()
            if msg_box.clickedButton() == cancel_button:
                return
        # 确保父目录存在
        parent_dir = osp.dirname(save_path)
        if parent_dir and not osp.exists(parent_dir):
            os.makedirs(parent_dir)
    else:
        # 独立文件模式：检查目录是否存在
        if osp.exists(save_path):
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Warning)
            msg_box.setWindowTitle(self.tr("输出目录已存在！"))
            msg_box.setText(self.tr("目录已存在，请选择一个操作："))
            msg_box.setInformativeText(
                self.tr(
                    "• 是 (Yes) - 合并到现有文件\n"
                    "• 否 (No) - 删除现有目录\n"
                    "• 取消 (Cancel) - 中止导出"
                )
            )

            msg_box.addButton(self.tr("是"), QtWidgets.QMessageBox.YesRole)
            no_button = msg_box.addButton(
                self.tr("否"), QtWidgets.QMessageBox.NoRole
            )
            cancel_button = msg_box.addButton(
                self.tr("取消"), QtWidgets.QMessageBox.RejectRole
            )
            msg_box.setStyleSheet(get_msg_box_style())
            msg_box.exec_()

            clicked_button = msg_box.clickedButton()
            if clicked_button == no_button:
                shutil.rmtree(save_path)
                os.makedirs(save_path)
            elif clicked_button == cancel_button:
                return
        else:
            os.makedirs(save_path)

    # 获取图片列表
    image_list = self.image_list if self.image_list else [self.filename]
    label_dir_path = osp.dirname(self.filename)
    if self.output_dir:
        label_dir_path = self.output_dir

    # 进度对话框
    progress_dialog = QProgressDialog(
        self.tr("正在导出..."), self.tr("取消"), 0, len(image_list), self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("导出进度"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setStyleSheet(
        get_progress_dialog_style(color="#1d1d1f", height=20)
    )

    exported_count = 0
    skipped_count = 0
    all_descriptions = []  # 用于单文件模式

    def process_description(description, text_mode):
        """根据文本模式处理description"""
        if text_mode == 'source':
            # 只取 / 前的内容
            if '/' in description:
                return description.split('/', 1)[0].strip()
            return description
        elif text_mode == 'target':
            # 只取 / 后的内容
            if '/' in description:
                parts = description.split('/', 1)
                return parts[1].strip() if len(parts) > 1 else ''
            return ''
        # text_mode == 'all' 时，原文和译文用TAB分隔
        if '/' in description:
            parts = description.split('/', 1)
            source_text = parts[0].strip()
            target_text = parts[1].strip() if len(parts) > 1 else ''
            return f"{source_text}\t{target_text}"
        return description

    try:
        for i, image_file in enumerate(image_list):
            image_file_name = osp.basename(image_file)
            label_file_name = osp.splitext(image_file_name)[0] + ".json"
            label_file_path = osp.join(label_dir_path, label_file_name)

            # 读取标注文件
            if not osp.exists(label_file_path):
                skipped_count += 1
                progress_dialog.setValue(i + 1)
                if progress_dialog.wasCanceled():
                    break
                continue

            try:
                with open(label_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                logger.warning(f"无法读取标注文件 {label_file_path}: {e}")
                skipped_count += 1
                progress_dialog.setValue(i + 1)
                if progress_dialog.wasCanceled():
                    break
                continue

            # 提取 description
            descriptions = []
            for shape in data.get('shapes', []):
                description = shape.get('description', '')
                
                if skip_empty and not description.strip():
                    continue
                
                # 根据文本模式处理
                description = process_description(description, text_mode)
                
                if description or not skip_empty:
                    descriptions.append(description)

            if export_to_single_file:
                # 单文件模式：收集所有描述
                all_descriptions.extend(descriptions)
                if descriptions:
                    exported_count += 1
                else:
                    skipped_count += 1
            else:
                # 独立文件模式：每个图片一个TXT
                txt_file_name = osp.splitext(image_file_name)[0] + ".txt"
                txt_file_path = osp.join(save_path, txt_file_name)
                
                if descriptions or not skip_empty:
                    with open(txt_file_path, 'w', encoding='utf-8') as f:
                        for desc in descriptions:
                            f.write(f"{desc}\n")
                    exported_count += 1
                else:
                    skipped_count += 1

            progress_dialog.setValue(i + 1)
            if progress_dialog.wasCanceled():
                break

        # 单文件模式：写入合并的文件
        if export_to_single_file and all_descriptions:
            with open(save_path, 'w', encoding='utf-8') as f:
                for desc in all_descriptions:
                    f.write(f"{desc}\n")

        progress_dialog.close()
        
        # 显示成功消息
        mode_names = {
            'all': self.tr("全部文本（原文/译文）"),
            'source': self.tr("仅原文"),
            'target': self.tr("仅译文"),
            'source_target_tab': self.tr("原文+译文（TAB分隔）")
        }
        
        if export_to_single_file:
            template = self.tr(
                "导出文本成功！\n"
                "文本模式：%s\n"
                "处理图片：%d 个\n"
                "跳过图片：%d 个\n"
                "总行数：%d\n"
                "保存位置：\n%s"
            )
            message_text = template % (mode_names[text_mode], exported_count, skipped_count, len(all_descriptions), save_path)
        else:
            template = self.tr(
                "导出文本成功！\n"
                "文本模式：%s\n"
                "成功：%d 个文件\n"
                "跳过：%d 个文件\n"
                "保存位置：\n%s"
            )
            message_text = template % (mode_names[text_mode], exported_count, skipped_count, save_path)
        
        popup = Popup(
            message_text,
            self,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self, popup_height=100, position="center")

    except Exception as e:
        progress_dialog.close()
        message = f"导出时发生错误: {str(e)}"
        logger.error(message)
        popup = Popup(
            message,
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")
