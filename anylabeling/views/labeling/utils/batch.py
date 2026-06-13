import base64
import json
import os.path as osp
from PIL import Image

from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QVBoxLayout,
    QProgressDialog,
    QDialog,
    QLabel,
    QLineEdit,
    QDialogButtonBox,
)

from anylabeling.app_info import __version__
from anylabeling.views.labeling.logger import logger
from anylabeling.views.labeling.utils._io import io_open
from anylabeling.views.labeling.utils.qt import new_icon_path
from anylabeling.views.labeling.utils.style import get_msg_box_style
from anylabeling.views.labeling.widgets.popup import Popup


__all__ = ["run_all_images"]


INVALID_MODEL_LIST = [
    "segment_anything",
    "segment_anything_2",
    "sam_med2d",
    "sam_hq",
    "efficientvit_sam",
    "edge_sam",
    "open_vision",
    "geco",
]

TEXT_PROMPT_MODELS = [
    "grounding_dino",
    "grounding_sam",
    "grounding_sam2",
    "yoloe",
]

VIDEO_MODELS = [
    "segment_anything_2_video",
]


class TextInputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(self.tr("Enter Text Prompt"))
        self.setFixedSize(400, 180)
        self.setWindowFlags(Qt.Dialog | Qt.MSWindowsFixedSizeDialogHint)

        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        prompt_label = QLabel(self.tr("Please enter your text prompt:"))
        prompt_label.setStyleSheet(
            "font-size: 13px; color: #1d1d1f; font-weight: 500;"
        )
        layout.addWidget(prompt_label)

        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText(self.tr("Enter prompt here..."))
        layout.addWidget(self.text_input)

        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #ffffff;
                border-radius: 10px;
            }
            
            QLineEdit {
                border: 1px solid #E5E5E5;
                border-radius: 8px;
                background-color: #F9F9F9;
                font-size: 13px;
                height: 36px;
                padding: 0 12px;
            }
            
            QLineEdit:hover {
                background-color: #DBDBDB;
            }
            
            QLineEdit:focus {
                border: 2px solid #0066FF;
                background-color: #F9F9F9;
            }
            
            QPushButton {
                min-width: 100px;
                height: 36px;
                border-radius: 8px;
                font-weight: 500;
                font-size: 13px;
            }
            
            QPushButton[text="OK"] {
                background-color: #0066FF;
                color: white;
                border: none;
            }
            
            QPushButton[text="OK"]:hover {
                background-color: #0077ED;
            }
            
            QPushButton[text="OK"]:pressed {
                background-color: #0068D0;
            }
            
            QPushButton[text="Cancel"] {
                background-color: #f5f5f7;
                color: #1d1d1f;
                border: 1px solid #d2d2d7;
            }
            
            QPushButton[text="Cancel"]:hover {
                background-color: #e5e5e5;
            }
            
            QPushButton[text="Cancel"]:pressed {
                background-color: #d5d5d5;
            }
        """
        )

    def get_input_text(self):
        if self.exec_() == QDialog.Accepted:
            return self.text_input.text().strip()
        return ""


def get_image_size(image_path):
    try:
        with Image.open(image_path) as img:
            return img.size
    except Exception:
        # Fallback to Qt
        qimg = QtGui.QImage(image_path)
        if not qimg.isNull():
            return qimg.width(), qimg.height()
        raise


def finish_processing(self, progress_dialog):
    current_filename = self.image_list[self.current_index]
    self.filename = current_filename
    
    # 重新导入文件夹，这会重新加载文件列表和当前文件
    # 从而正确更新manually_edited状态和颜色
    # 使用last_open_dir(根文件夹)而不是dirname(filename)(子文件夹)
    # 并保持recursive设置以加载所有子文件夹
    recursive = self._config.get("load_subfolders", False)
    self.import_image_folder(self.last_open_dir, load=True, recursive=recursive)

    del self.text_prompt
    del self.run_tracker
    del self.image_index
    del self.current_index

    progress_dialog.close()

    popup = Popup(
        "处理成功！",
        self,
        icon=new_icon_path("copy-green", "svg"),
    )
    popup.show_popup(self, position="center")


def cancel_operation(self):
    self.cancel_processing = True


def _predict_with_existing_boxes(self, image_file):
    """使用已有检测框进行 OCR（不运行检测器），直接修改 JSON 文件，不改框只加文字"""
    import json, os, cv2, numpy as np

    label_file = os.path.splitext(image_file)[0] + ".json"
    if not os.path.exists(label_file):
        return False

    try:
        with open(label_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return False

    shapes = data.get("shapes", [])
    if not shapes:
        return False

    # 读取过滤标签
    filter_classes = self.auto_labeling_widget.model_manager.loaded_model_config.get(
        "filter_classes", None
    )

    # 提取框坐标（过滤器标签）
    boxes = []
    box_indices = []  # 记录 shapes 中哪些下标被送 OCR
    for i, s in enumerate(shapes):
        if filter_classes is not None and s.get("label") not in filter_classes:
            continue
        pts = s.get("points", [])
        if len(pts) == 4:
            boxes.append([[int(p[0]), int(p[1])] for p in pts])
            box_indices.append(i)

    if not boxes:
        return False

    img = cv2.imdecode(np.fromfile(image_file, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return False

    model = self.auto_labeling_widget.model_manager.loaded_model_config.get("model")
    if not model or not hasattr(model, "predict_shapes_from_boxes"):
        return False

    result, timing = model.predict_shapes_from_boxes(img, boxes, image_file)
    if result is None or not result.shapes:
        return False

    # 直接把 OCR 文字写回对应原框
    for j, idx in enumerate(box_indices):
        if j < len(result.shapes):
            shapes[idx]["description"] = result.shapes[j].description or ""
            shapes[idx]["score"] = float(result.shapes[j].score)

    # 打印日志（按标签分组，带序号和耗时）
    import time, sys
    from collections import defaultdict
    t_total = time.time()
    timing_str = f"[框识别耗时] 读图={timing.get('读图',0):.3f}s  裁剪+识别={timing.get('裁剪+识别',0):.3f}s  总={timing.get('总',0):.3f}s" if timing else ""
    grouped = defaultdict(list)
    for j, idx in enumerate(box_indices):
        if j < len(result.shapes):
            text = result.shapes[j].description or ""
            score = float(result.shapes[j].score)
            grouped[shapes[idx].get("label", "")].append((boxes[j], text, score))
    fname = os.path.basename(image_file)
    print(f"\n[批量已有框OCR] {fname}  共{len(box_indices)}个框 → {timing_str}")
    for label, items in sorted(grouped.items()):
        print(f"标签:{label}  ({len(items)}个)")
        for idx, item in enumerate(items, 1):
            coord, text, score = item
            print(f"标签:{label}({idx})")
            print(f"[{coord}, ('{text}', {score:.4f})]")
    sys.stdout.flush()

    data["shapes"] = shapes
    data["manually_edited"] = False

    # 处理 output_dir
    if self.output_dir:
        output_label_file = osp.join(self.output_dir, osp.basename(label_file))
    else:
        output_label_file = label_file

    with open(output_label_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return True


def save_auto_labeling_result(self, image_file, auto_labeling_result):
    try:
        label_file = osp.splitext(image_file)[0] + ".json"
        if self.output_dir:
            label_file = osp.join(self.output_dir, osp.basename(label_file))

        if auto_labeling_result is None:
            new_shapes = []
            new_description = ""
            replace = True
        else:
            new_shapes = [
                shape.to_dict() for shape in auto_labeling_result.shapes
            ]
            new_description = auto_labeling_result.description
            replace = auto_labeling_result.replace

        if osp.exists(label_file):
            with io_open(label_file, "r") as f:
                data = json.load(f)

            if replace:
                data["shapes"] = new_shapes
                data["description"] = new_description
                # Clear manually_edited flag when AI batch inference (use root level format for compatibility)
                data["manually_edited"] = False
            else:
                data["shapes"].extend(new_shapes)
                if "description" in data:
                    data["description"] += new_description
                else:
                    data["description"] = new_description
                # Clear manually_edited flag when AI batch inference (use root level format for compatibility)
                data["manually_edited"] = False
        else:
            if self._config["store_data"]:
                with open(image_file, "rb") as f:
                    image_data = f.read()
                image_data = base64.b64encode(image_data).decode("utf-8")
            else:
                image_data = None

            image_path = osp.basename(image_file)
            image_width, image_height = get_image_size(image_file)

            data = {
                "version": __version__,
                "flags": {},
                "shapes": new_shapes,
                "imagePath": image_path,
                "imageData": image_data,
                "imageHeight": image_height,
                "imageWidth": image_width,
                "description": new_description,
                "manually_edited": False,
            }

        with io_open(label_file, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(
            f"Failed to save auto labeling result for image file '{image_file}': {str(e)}"
        )


def process_next_image(self, progress_dialog):
    try:
        batch = True
        total_images = len(self.image_list)

        while (self.image_index < total_images) and (
            not self.cancel_processing
        ):
            image_file = self.image_list[self.image_index]

            if (
                self.auto_labeling_widget.model_manager.loaded_model_config[
                    "type"
                ]
                in VIDEO_MODELS
            ):
                self.filename = image_file
                self.load_file(self.filename)
                batch = False

            if self.text_prompt:
                auto_labeling_result = (
                    self.auto_labeling_widget.model_manager.predict_shapes(
                        self.image,
                        image_file,
                        text_prompt=self.text_prompt,
                        batch=batch,
                    )
                )
            elif self.run_tracker:
                auto_labeling_result = (
                    self.auto_labeling_widget.model_manager.predict_shapes(
                        self.image,
                        image_file,
                        run_tracker=self.run_tracker,
                        batch=batch,
                    )
                )
            else:
                # 检查是否启用"使用已有框"模式
                use_existing = (
                    hasattr(self.auto_labeling_widget, 'toggle_use_existing_boxes')
                    and self.auto_labeling_widget.toggle_use_existing_boxes.isChecked()
                )
                if use_existing:
                    _predict_with_existing_boxes(
                        self, image_file
                    )
                    auto_labeling_result = None  # 跳过 save_auto_labeling_result
                else:
                    auto_labeling_result = (
                        self.auto_labeling_widget.model_manager.predict_shapes(
                            self.image, image_file, batch=batch
                        )
                    )

            if batch and auto_labeling_result is not None:
                save_auto_labeling_result(
                    self, image_file, auto_labeling_result
                )

            progress_dialog.setValue(self.image_index)
            self.image_index += 1

        finish_processing(self, progress_dialog)

    except Exception as e:
        progress_dialog.close()

        logger.error(f"Error occurred while processing images: {e}")
        popup = Popup(
            self.tr("Error occurred while processing images!"),
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")


def show_progress_dialog_and_process(self):
    self.cancel_processing = False
    
    # 记录起始位置,用于显示
    start_index = self.image_index
    start_num = start_index + 1  # 显示用的起始页码
    end_num = len(self.image_list)
    total_to_process = end_num - start_index  # 总共要处理的数量

    progress_dialog = QProgressDialog(
        f"处理范围: 第 {start_num}-{end_num} 张 (共 {total_to_process} 张)\n进度: 1/{total_to_process}",
        "取消",
        start_index,  # 最小值是起始索引
        len(self.image_list),  # 最大值是总数
        self,
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle("批量处理中")
    progress_dialog.setMinimumWidth(400)
    progress_dialog.setMinimumHeight(150)

    progress_bar = progress_dialog.findChild(QtWidgets.QProgressBar)

    if progress_bar:

        def update_progress(value):
            # value是实际的image_index
            processed = value - start_index + 1  # 已处理的数量(从1开始)
            current_num = value + 1  # 当前图片编号
            progress_dialog.setLabelText(
                f"处理范围: 第 {start_num}-{end_num} 张 (共 {total_to_process} 张)\n"
                f"当前: 第 {current_num} 张\n"
                f"进度: {processed}/{total_to_process}"
            )

        progress_bar.valueChanged.connect(update_progress)

    progress_dialog.setStyleSheet(
        """
        QProgressDialog {
            background-color: rgba(255, 255, 255, 0.95);
            border-radius: 12px;
            min-width: 280px;
            min-height: 120px;
            padding: 20px;
            backdrop-filter: blur(20px);
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.08),
                        0 2px 6px rgba(0, 0, 0, 0.04);
        }
        QProgressBar {
            border: none;
            border-radius: 4px;
            background-color: rgba(0, 0, 0, 0.05);
            text-align: center;
            color: #1d1d1f;
            font-size: 13px;
            min-height: 20px;
            max-height: 20px;
            margin: 16px 0;
        }
        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #0066FF,
                stop:0.5 #00A6FF,
                stop:1 #0066FF);
            border-radius: 3px;
        }
        QLabel {
            color: #1d1d1f;
            font-size: 13px;
            font-weight: 500;
            margin-bottom: 8px;
        }
        QPushButton {
            background-color: rgba(255, 255, 255, 0.8);
            border: 0.5px solid rgba(0, 0, 0, 0.1);
            border-radius: 6px;
            font-weight: 500;
            font-size: 13px;
            color: #0066FF;
            min-width: 82px;
            height: 36px;
            padding: 0 16px;
            margin-top: 16px;
        }
        QPushButton:hover {
            background-color: rgba(0, 0, 0, 0.05);
        }
        QPushButton:pressed {
            background-color: rgba(0, 0, 0, 0.08);
        }
    """
    )
    progress_dialog.canceled.connect(lambda: cancel_operation(self))
    progress_dialog.show()

    QTimer.singleShot(200, lambda: process_next_image(self, progress_dialog))


def run_all_images(self):
    if len(self.image_list) < 1:
        return

    if self.auto_labeling_widget.model_manager.loaded_model_config is None:
        self.auto_labeling_widget.model_manager.new_model_status.emit(
            self.tr("Model is not loaded. Choose a mode to continue.")
        )
        return

    if (
        self.auto_labeling_widget.model_manager.loaded_model_config["type"]
        in INVALID_MODEL_LIST
    ):
        logger.warning(
            f"The model `{self.auto_labeling_widget.model_manager.loaded_model_config['type']}`"
            f" is not supported for this action."
            f" Please choose a valid model to execute."
        )
        self.auto_labeling_widget.model_manager.new_model_status.emit(
            self.tr(
                "Invalid model type, please choose a valid model_type to run."
            )
        )
        return

    # 计算要处理的图片范围
    current_index = self.fn_to_index[str(self.filename)]
    start_num = current_index + 1  # 显示用的起始页码(从1开始)
    end_num = len(self.image_list)  # 显示用的结束页码
    total_to_process = end_num - current_index  # 要处理的图片数量
    
    response = QtWidgets.QMessageBox()
    response.setIcon(QtWidgets.QMessageBox.Warning)
    response.setWindowTitle("确认")
    response.setText(f"是否要处理第 {start_num}-{end_num} 张图片?\n(共 {total_to_process} 张)")
    ok_button = response.addButton("确定", QtWidgets.QMessageBox.AcceptRole)
    response.addButton("取消", QtWidgets.QMessageBox.RejectRole)
    response.setStyleSheet(get_msg_box_style())

    response.exec_()
    if response.clickedButton() != ok_button:
        return

    logger.info("Start running all images...")

    self.current_index = self.fn_to_index[str(self.filename)]
    self.image_index = self.current_index
    self.text_prompt = ""
    self.run_tracker = False

    if (
        self.auto_labeling_widget.model_manager.loaded_model_config["type"]
        in TEXT_PROMPT_MODELS
    ):
        text_input_dialog = TextInputDialog(parent=self)
        self.text_prompt = text_input_dialog.get_input_text()
        if (
            self.text_prompt
            or self.auto_labeling_widget.model_manager.loaded_model_config[
                "type"
            ]
            == "yoloe"
        ):
            show_progress_dialog_and_process(self)

    elif (
        self.auto_labeling_widget.model_manager.loaded_model_config["type"]
        in VIDEO_MODELS
    ):
        self.run_tracker = True
        show_progress_dialog_and_process(self)

    else:
        show_progress_dialog_and_process(self)
