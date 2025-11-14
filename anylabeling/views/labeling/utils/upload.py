import json
import jsonlines
import os
import os.path as osp
from anylabeling.services.importers import convert_itp_to_anylabel
import time
import yaml

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QProgressDialog,
)

from anylabeling.views.labeling.label_converter import LabelConverter
from anylabeling.views.labeling.logger import logger
from anylabeling.views.labeling.widgets import Popup
from anylabeling.views.labeling.utils.qt import new_icon_path
from anylabeling.views.labeling.utils.style import *
from anylabeling.views.labeling.utils.export import _check_filename_exist


class UploadPPOCRThread(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, converter, input_file, output_path, image_path, mode):
        super().__init__()
        self.converter = converter
        self.input_file = input_file
        self.output_path = output_path
        self.image_path = image_path
        self.mode = mode

    def run(self):
        try:
            time.sleep(1)

            self.converter.ppocr_to_custom(
                input_file=self.input_file,
                output_path=self.output_path,
                image_path=self.image_path,
                mode=self.mode,
            )

            self.finished.emit(True, "")

        except Exception as e:
            self.finished.emit(False, str(e))


class UploadOdvgThread(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, converter, input_file, output_path):
        super().__init__()
        self.converter = converter
        self.input_file = input_file
        self.output_path = output_path

    def run(self):
        try:
            time.sleep(1)

            self.converter.odvg_to_custom(
                input_file=self.input_file,
                output_path=self.output_path,
            )

            self.finished.emit(True, "")

        except Exception as e:
            self.finished.emit(False, str(e))


class UploadMotThread(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, converter, gt_file, output_path, image_path):
        super().__init__()
        self.converter = converter
        self.gt_file = gt_file
        self.output_path = output_path
        self.image_path = image_path

    def run(self):
        try:
            time.sleep(1)

            self.converter.mot_to_custom(
                input_file=self.gt_file,
                output_path=self.output_path,
                image_path=self.image_path,
            )

            self.finished.emit(True, "")

        except Exception as e:
            self.finished.emit(False, str(e))


class UploadCocoThread(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, converter, input_file, output_dir_path, mode):
        super().__init__()
        self.converter = converter
        self.input_file = input_file
        self.output_dir_path = output_dir_path
        self.mode = mode

    def run(self):
        try:
            time.sleep(1)

            self.converter.coco_to_custom(
                input_file=self.input_file,
                output_dir_path=self.output_dir_path,
                mode=self.mode,
            )

            self.finished.emit(True, "")

        except Exception as e:
            self.finished.emit(False, str(e))


class UploadBallonTranslatorThread(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, input_file):
        super().__init__()
        self.input_file = input_file

    def run(self):
        try:
            from .converter_scripts import convert_ballons_to_anylabel
            time.sleep(1)
            convert_ballons_to_anylabel(self.input_file)
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


def upload_vlm_r1_ovd_annotation(self):
    if not _check_filename_exist(self):
        return

    filter = "Attribute Files (*.jsonl);;All Files (*)"
    input_file, _ = QtWidgets.QFileDialog.getOpenFileName(
        self,
        self.tr("Select a custom vlm_r1_ovd annotation file"),
        "",
        filter,
    )

    if not input_file:
        return

    output_dir_path = osp.dirname(self.filename)
    if self.output_dir:
        output_dir_path = self.output_dir

    response = QtWidgets.QMessageBox()
    response.setIcon(QtWidgets.QMessageBox.Warning)
    response.setWindowTitle(self.tr("Warning"))
    response.setText(self.tr("Current annotation will be lost"))
    response.setInformativeText(
        self.tr(
            "You are going to upload new annotations to this task. Continue?"
        )
    )
    response.setStandardButtons(
        QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Ok
    )
    response.setStyleSheet(get_msg_box_style())

    if response.exec_() != QtWidgets.QMessageBox.Ok:
        return

    image_list = self.image_list if self.image_list else [self.filename]
    progress_dialog = QProgressDialog(
        self.tr("Uploading..."), self.tr("Cancel"), 0, len(image_list), self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("Progress"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setStyleSheet(
        get_progress_dialog_style(color="#1d1d1f", height=20)
    )

    converter = LabelConverter()

    try:
        # parse input_data
        input_data = {}
        with jsonlines.open(input_file, "r") as reader:
            for data in list(reader):
                image_path = osp.basename(data["image"])
                input_data[image_path] = data["conversations"][1]["value"]

        for i, image_file in enumerate(image_list):
            image_filename = osp.basename(image_file)
            label_filename = osp.splitext(image_filename)[0] + ".json"
            output_file = osp.join(output_dir_path, label_filename)

            converter.vlm_r1_ovd_to_custom(
                input_data=input_data[image_filename],
                output_file=output_file,
                image_file=image_file,
            )

            progress_dialog.setValue(i)
            if progress_dialog.wasCanceled():
                break

        progress_dialog.close()
        template = (
            "上传标注成功！\n"
            "结果已保存到：\n"
            "%s"
        )
        message_text = template % output_dir_path
        popup = Popup(
            message_text,
            self,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self, popup_height=65, position="center")

        # update and refresh the current canvas
        self.load_file(self.filename)

    except Exception as e:
        progress_dialog.close()
        message = f"Error occurred while uploading annotations: {str(e)}"
        logger.error(message)

        popup = Popup(
            message,
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")


def upload_ppocr_annotation(self, mode):
    if not _check_filename_exist(self):
        return

    if mode == "rec":
        filter = "Attribute Files (*.txt);;All Files (*)"
        input_file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.tr("Select a custom annotation file (Label.txt)"),
            "",
            filter,
        )

        if not input_file:
            return

    elif mode == "kie":
        filter = "Attribute Files (*.json);;All Files (*)"
        input_file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.tr("Select a custom annotation file (ppocr_kie.json)"),
            "",
            filter,
        )

        if not input_file:
            return

    response = QtWidgets.QMessageBox()
    response.setIcon(QtWidgets.QMessageBox.Warning)
    response.setWindowTitle(self.tr("Warning"))
    response.setText(self.tr("Current annotation will be lost"))
    response.setInformativeText(
        self.tr(
            "You are going to upload new annotations to this task. Continue?"
        )
    )
    response.setStandardButtons(
        QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Ok
    )
    response.setStyleSheet(get_msg_box_style())

    if response.exec_() != QtWidgets.QMessageBox.Ok:
        return

    progress_dialog = QProgressDialog(
        self.tr("Uploading..."), self.tr("Cancel"), 0, 0, self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("Progress"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setRange(0, 0)
    progress_dialog.setStyleSheet(get_progress_dialog_style())

    converter = LabelConverter()
    image_path = osp.dirname(self.filename)
    output_path = osp.dirname(self.filename)
    if self.output_dir:
        output_path = self.output_dir
    self.upload_thread = UploadPPOCRThread(
        converter, input_file, output_path, image_path, mode
    )

    def on_upload_finished(success, error_msg):
        progress_dialog.close()
        if success:
            # update and refresh the current canvas
            self.load_file(self.filename)

            popup = Popup(
                "上传标注成功！",
                self,
                icon=new_icon_path("copy-green", "svg"),
            )
            popup.show_popup(self, popup_height=65, position="center")
        else:
            message = (
                f"Error occurred while uploading annotations: {str(error_msg)}"
            )
            logger.error(message)
            popup = Popup(
                message,
                self,
                icon=new_icon_path("error", "svg"),
            )
            popup.show_popup(self, position="center")

    self.upload_thread.finished.connect(on_upload_finished)

    progress_dialog.show()
    self.upload_thread.start()

    progress_dialog.canceled.connect(self.upload_thread.terminate)


def upload_odvg_annotation(self):
    if not _check_filename_exist(self):
        return

    filter = "OD Files (*.json *.jsonl);;All Files (*)"
    input_file, _ = QtWidgets.QFileDialog.getOpenFileName(
        self,
        self.tr("Select a specific OD file"),
        "",
        filter,
    )

    if not input_file:
        return

    response = QtWidgets.QMessageBox()
    response.setIcon(QtWidgets.QMessageBox.Warning)
    response.setWindowTitle(self.tr("Warning"))
    response.setText(self.tr("Current annotation will be lost"))
    response.setInformativeText(
        self.tr(
            "You are going to upload new annotations to this task. Continue?"
        )
    )
    response.setStandardButtons(
        QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Ok
    )
    response.setStyleSheet(get_msg_box_style())

    if response.exec_() != QtWidgets.QMessageBox.Ok:
        return

    progress_dialog = QProgressDialog(
        self.tr("Uploading..."), self.tr("Cancel"), 0, 0, self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("Progress"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setRange(0, 0)
    progress_dialog.setStyleSheet(get_progress_dialog_style())

    converter = LabelConverter()
    output_path = osp.dirname(self.filename)
    if self.output_dir:
        output_path = self.output_dir
    self.upload_thread = UploadOdvgThread(converter, input_file, output_path)

    def on_upload_finished(success, error_msg):
        progress_dialog.close()
        if success:
            # update and refresh the current canvas
            self.load_file(self.filename)

            popup = Popup(
                "上传标注成功！",
                self,
                icon=new_icon_path("copy-green", "svg"),
            )
            popup.show_popup(self, popup_height=65, position="center")
        else:
            message = (
                f"Error occurred while uploading annotations: {str(error_msg)}"
            )
            logger.error(message)
            popup = Popup(
                message,
                self,
                icon=new_icon_path("error", "svg"),
            )
            popup.show_popup(self, position="center")

    self.upload_thread.finished.connect(on_upload_finished)

    progress_dialog.show()
    self.upload_thread.start()

    progress_dialog.canceled.connect(self.upload_thread.terminate)


def upload_mmgd_annotation(self, LABEL_OPACITY):
    if not _check_filename_exist(self):
        return

    filter = "Classes Files (*.txt);;All Files (*)"
    classes_file, _ = QtWidgets.QFileDialog.getOpenFileName(
        self,
        self.tr("Select a specific classes file"),
        "",
        filter,
    )
    if not classes_file:
        return

    try:
        with open(classes_file, "r", encoding="utf-8") as f:
            classes = f.read().splitlines()
    except Exception as e:
        popup = Popup(
            self.tr(f"Error reading classes file: {str(e)}"),
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")
        return

    dialog = QtWidgets.QDialog(self)
    dialog.setWindowTitle(self.tr("Upload Options"))
    dialog.setMinimumWidth(500)
    dialog.setStyleSheet(get_export_option_style())

    layout = QVBoxLayout()
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)

    folder_layout = QVBoxLayout()
    folder_label = QtWidgets.QLabel(self.tr("Select Upload Folder"))
    folder_layout.addWidget(folder_label)

    folder_input_layout = QHBoxLayout()
    folder_input_layout.setSpacing(8)

    path_edit = QtWidgets.QLineEdit()
    path_edit.setPlaceholderText(
        self.tr("Please select a folder containing annotation files")
    )

    def browse_json_folder():
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.tr("Select Upload Folder"),
            None,
            QtWidgets.QFileDialog.ShowDirsOnly
            | QtWidgets.QFileDialog.DontResolveSymlinks
            | QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if path:
            path_edit.setText(path)

    folder_button = QtWidgets.QPushButton(self.tr("Browse"))
    folder_button.clicked.connect(browse_json_folder)
    folder_button.setStyleSheet(get_cancel_btn_style())

    folder_input_layout.addWidget(path_edit)
    folder_input_layout.addWidget(folder_button)
    folder_layout.addLayout(folder_input_layout)
    layout.addLayout(folder_layout)

    category_layout = QVBoxLayout()
    category_label = QtWidgets.QLabel(self.tr("Category Settings"))
    category_layout.addWidget(category_label)

    scroll_area = QtWidgets.QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_area.setMaximumHeight(200)
    scroll_widget = QtWidgets.QWidget()
    scroll_layout = QVBoxLayout(scroll_widget)

    category_widgets = {}
    for i, class_name in enumerate(classes):
        row_layout = QHBoxLayout()

        checkbox = QtWidgets.QCheckBox(class_name)
        checkbox.setChecked(True)

        threshold_label = QtWidgets.QLabel(self.tr("Threshold:"))
        threshold_input = QtWidgets.QDoubleSpinBox()
        threshold_input.setRange(0.0, 1.0)
        threshold_input.setSingleStep(0.01)
        threshold_input.setValue(0.20)
        threshold_input.setDecimals(2)

        row_layout.addWidget(checkbox)
        row_layout.addStretch()
        row_layout.addWidget(threshold_label)
        row_layout.addWidget(threshold_input)

        scroll_layout.addLayout(row_layout)
        category_widgets[class_name] = (checkbox, threshold_input)

    scroll_area.setWidget(scroll_widget)
    category_layout.addWidget(scroll_area)
    layout.addLayout(category_layout)

    button_layout = QHBoxLayout()
    button_layout.setContentsMargins(0, 16, 0, 0)
    button_layout.setSpacing(8)

    cancel_button = QtWidgets.QPushButton(self.tr("Cancel"))
    cancel_button.clicked.connect(dialog.reject)
    cancel_button.setStyleSheet(get_cancel_btn_style())

    ok_button = QtWidgets.QPushButton(self.tr("OK"))

    def on_ok_clicked():
        if not path_edit.text().strip():
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("Warning"),
                self.tr("Upload folder path cannot be empty!"),
            )
            return

        dialog.accept()

    ok_button.clicked.connect(on_ok_clicked)
    ok_button.setStyleSheet(get_ok_btn_style())

    button_layout.addStretch()
    button_layout.addWidget(cancel_button)
    button_layout.addWidget(ok_button)
    layout.addLayout(button_layout)

    dialog.setLayout(layout)
    result = dialog.exec_()

    if not result:
        return

    labels = []
    thresholds = {}
    for class_name, (checkbox, threshold_input) in category_widgets.items():
        if checkbox.isChecked():
            labels.append(class_name)
            thresholds[class_name] = threshold_input.value()

    if not labels:
        popup = Popup(
            self.tr("Please select at least one category!"),
            self,
            icon=new_icon_path("warning", "svg"),
        )
        popup.show_popup(self, position="center")
        return

    label_dir_path = path_edit.text()
    image_dir_path = osp.dirname(self.filename)
    image_file_list = os.listdir(image_dir_path)
    label_file_list = os.listdir(label_dir_path)
    output_dir_path = self.output_dir if self.output_dir else image_dir_path
    converter = LabelConverter(classes_file=classes_file)

    response = QtWidgets.QMessageBox()
    response.setIcon(QtWidgets.QMessageBox.Warning)
    response.setWindowTitle(self.tr("Warning"))
    response.setText(self.tr("Current annotation will be lost"))
    response.setInformativeText(
        self.tr(
            "You are going to upload new annotations to this task. Continue?"
        )
    )
    response.setStandardButtons(
        QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Ok
    )
    response.setStyleSheet(get_msg_box_style())

    if response.exec_() != QtWidgets.QMessageBox.Ok:
        return

    progress_dialog = QProgressDialog(
        self.tr("Uploading..."),
        self.tr("Cancel"),
        0,
        len(image_file_list),
        self,
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("Progress"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setStyleSheet(
        get_progress_dialog_style(color="#1d1d1f", height=20)
    )

    try:
        for i, image_filename in enumerate(image_file_list):
            label_filename = osp.splitext(image_filename)[0] + ".json"
            if (
                image_filename.endswith(".json")
                or label_filename not in label_file_list
            ):
                continue

            if progress_dialog.wasCanceled():
                break

        progress_dialog.close()
        template = (
            "上传标注成功！\n"
            "结果已保存到：\n"
            "%s"
        )
        message_text = template % output_dir_path
        popup = Popup(
            message_text,
            self,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self, popup_height=65, position="center")

        for label in labels:
            if not self.unique_label_list.find_items_by_label(label):
                item = self.unique_label_list.create_item_from_label(label)
                self.unique_label_list.addItem(item)
                rgb = self._get_rgb_by_label(label)
                self.unique_label_list.set_item_label(
                    item, label, rgb, LABEL_OPACITY
                )

        self.load_file(self.filename)

    except Exception as e:
        progress_dialog.close()
        message = f"Error occurred while uploading annotations: {str(e)}"
        logger.error(message)

        popup = Popup(
            message,
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")


def upload_mot_annotation(self, LABEL_OPACITY):
    if not _check_filename_exist(self):
        return

    filter = "Classes Files (*.txt);;All Files (*)"
    classes_file, _ = QtWidgets.QFileDialog.getOpenFileName(
        self,
        self.tr("Select a specific classes file"),
        "",
        filter,
    )

    if not classes_file:
        return

    filter = "Gt Files (*.txt);;All Files (*)"
    gt_file, _ = QtWidgets.QFileDialog.getOpenFileName(
        self,
        self.tr("Select a specific gt file"),
        "",
        filter,
    )

    if not gt_file:
        popup = Popup(
            self.tr("Please select a specific gt file!"),
            self,
            icon=new_icon_path("warning", "svg"),
        )
        popup.show_popup(self, position="center")
        return

    response = QtWidgets.QMessageBox()
    response.setIcon(QtWidgets.QMessageBox.Warning)
    response.setWindowTitle(self.tr("Warning"))
    response.setText(self.tr("Current annotation will be lost"))
    response.setInformativeText(
        self.tr(
            "You are going to upload new annotations to this task. Continue?"
        )
    )
    response.setStandardButtons(
        QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Ok
    )
    response.setStyleSheet(get_msg_box_style())

    if response.exec_() != QtWidgets.QMessageBox.Ok:
        return

    # Initialize unique labels
    with open(classes_file, "r", encoding="utf-8") as f:
        labels = f.read().splitlines()
        for label in labels:
            if not self.unique_label_list.find_items_by_label(label):
                item = self.unique_label_list.create_item_from_label(label)
                self.unique_label_list.addItem(item)
                rgb = self._get_rgb_by_label(label)
                self.unique_label_list.set_item_label(
                    item, label, rgb, LABEL_OPACITY
                )

    progress_dialog = QProgressDialog(
        self.tr("Uploading..."), self.tr("Cancel"), 0, 0, self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("Progress"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setRange(0, 0)
    progress_dialog.setStyleSheet(get_progress_dialog_style())

    converter = LabelConverter(classes_file=classes_file)
    image_path = osp.dirname(self.filename)
    output_path = image_path
    if self.output_dir:
        output_path = self.output_dir
    self.upload_thread = UploadMotThread(
        converter, gt_file, output_path, image_path
    )

    def on_upload_finished(success, error_msg):
        progress_dialog.close()
        if success:
            # update and refresh the current canvas
            self.load_file(self.filename)

            popup = Popup(
                "上传标注成功！",
                self,
                icon=new_icon_path("copy-green", "svg"),
            )
            popup.show_popup(self, popup_height=65, position="center")
        else:
            message = (
                f"Error occurred while uploading annotations: {str(error_msg)}"
            )
            logger.error(message)
            popup = Popup(
                message,
                self,
                icon=new_icon_path("error", "svg"),
            )
            popup.show_popup(self, position="center")

    self.upload_thread.finished.connect(on_upload_finished)

    progress_dialog.show()
    self.upload_thread.start()

    progress_dialog.canceled.connect(self.upload_thread.terminate)


def upload_mask_annotation(self, LABEL_OPACITY):
    if not _check_filename_exist(self):
        return

    filter = "Attribute Files (*.json);;All Files (*)"
    color_map_file, _ = QtWidgets.QFileDialog.getOpenFileName(
        self,
        self.tr("Select a specific color_map file"),
        "",
        filter,
    )

    if not color_map_file:
        return

    dialog = QtWidgets.QDialog(self)
    dialog.setWindowTitle(self.tr("Upload Options"))
    dialog.setMinimumWidth(500)
    dialog.setStyleSheet(get_export_option_style())

    layout = QVBoxLayout()
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)

    path_layout = QVBoxLayout()
    path_label = QtWidgets.QLabel(self.tr("Select Upload Folder"))
    path_layout.addWidget(path_label)

    path_input_layout = QHBoxLayout()
    path_input_layout.setSpacing(8)

    path_edit = QtWidgets.QLineEdit()
    path_edit.setText(osp.dirname(osp.dirname(self.filename)))

    def browse_upload_folder():
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.tr("Select Upload Folder"),
            path_edit.text(),
            QtWidgets.QFileDialog.ShowDirsOnly
            | QtWidgets.QFileDialog.DontResolveSymlinks
            | QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if path:
            path_edit.setText(path)

    path_button = QtWidgets.QPushButton(self.tr("Browse"))
    path_button.clicked.connect(browse_upload_folder)
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

    response = QtWidgets.QMessageBox()
    response.setIcon(QtWidgets.QMessageBox.Warning)
    response.setWindowTitle(self.tr("Warning"))
    response.setText(self.tr("Current annotation will be lost"))
    response.setInformativeText(
        self.tr(
            "You are going to upload new annotations to this task. Continue?"
        )
    )
    response.setStandardButtons(
        QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Ok
    )
    response.setStyleSheet(get_msg_box_style())

    if response.exec_() != QtWidgets.QMessageBox.Ok:
        return

    # Initialize unique labels
    with open(color_map_file, "r", encoding="utf-8") as f:
        mapping_table = json.load(f)
        classes = list(mapping_table["colors"].keys())
        for label in classes:
            if not self.unique_label_list.find_items_by_label(label):
                item = self.unique_label_list.create_item_from_label(label)
                self.unique_label_list.addItem(item)
                rgb = self._get_rgb_by_label(label)
                self.unique_label_list.set_item_label(
                    item, label, rgb, LABEL_OPACITY
                )

    label_dir_path = path_edit.text()
    image_dir_path = osp.dirname(self.filename)
    image_file_list = os.listdir(image_dir_path)
    label_file_list = os.listdir(label_dir_path)
    output_dir_path = self.output_dir if self.output_dir else image_dir_path
    converter = LabelConverter()

    image_list = self.image_list if self.image_list else [self.filename]
    progress_dialog = QProgressDialog(
        self.tr("Uploading..."), self.tr("Cancel"), 0, len(image_list), self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("Progress"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setStyleSheet(
        get_progress_dialog_style(color="#1d1d1f", height=20)
    )

    try:
        for i, image_filename in enumerate(image_file_list):
            if image_filename.endswith(".json"):
                continue
            data_filename = osp.splitext(image_filename)[0] + ".json"
            if osp.splitext(image_filename)[0] + ".png" in label_file_list:
                label_filename = osp.splitext(image_filename)[0] + ".png"
            elif osp.splitext(image_filename)[0] + ".jpg" in label_file_list:
                label_filename = osp.splitext(image_filename)[0] + ".jpg"
            else:
                continue
            input_file = osp.join(label_dir_path, label_filename)
            output_file = osp.join(output_dir_path, data_filename)
            image_file = osp.join(image_dir_path, image_filename)
            converter.mask_to_custom(
                input_file=input_file,
                output_file=output_file,
                image_file=image_file,
                mapping_table=mapping_table,
            )

            progress_dialog.setValue(i)
            if progress_dialog.wasCanceled():
                break

        progress_dialog.close()
        template = (
            "上传标注成功！\n"
            "结果已保存到：\n"
            "%s"
        )
        message_text = template % output_dir_path
        popup = Popup(
            message_text,
            self,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self, popup_height=65, position="center")

        # update and refresh the current canvas
        self.load_file(self.filename)

    except Exception as e:
        progress_dialog.close()
        message = f"Error occurred while uploading annotations: {str(e)}"
        logger.error(message)

        popup = Popup(
            message,
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")


def upload_dota_annotation(self):
    if not _check_filename_exist(self):
        return

    dialog = QtWidgets.QDialog(self)
    dialog.setWindowTitle(self.tr("Upload Options"))
    dialog.setMinimumWidth(500)
    dialog.setStyleSheet(get_export_option_style())

    layout = QVBoxLayout()
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)

    path_layout = QVBoxLayout()
    path_label = QtWidgets.QLabel(self.tr("Select Upload Folder"))
    path_layout.addWidget(path_label)

    path_input_layout = QHBoxLayout()
    path_input_layout.setSpacing(8)

    path_edit = QtWidgets.QLineEdit()
    path_edit.setText(osp.dirname(osp.dirname(self.filename)))

    def browse_upload_folder():
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.tr("Select Upload Folder"),
            path_edit.text(),
            QtWidgets.QFileDialog.ShowDirsOnly
            | QtWidgets.QFileDialog.DontResolveSymlinks
            | QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if path:
            path_edit.setText(path)

    path_button = QtWidgets.QPushButton(self.tr("Browse"))
    path_button.clicked.connect(browse_upload_folder)
    path_button.setStyleSheet(get_cancel_btn_style())

    path_input_layout.addWidget(path_edit)
    path_input_layout.addWidget(path_button)
    path_layout.addLayout(path_input_layout)
    layout.addLayout(path_layout)

    # Button section
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

    label_dir_path = path_edit.text()
    image_dir_path = osp.dirname(self.filename)
    label_file_list = os.listdir(label_dir_path)
    output_dir_path = self.output_dir if self.output_dir else image_dir_path
    converter = LabelConverter()

    response = QtWidgets.QMessageBox()
    response.setIcon(QtWidgets.QMessageBox.Warning)
    response.setWindowTitle(self.tr("Warning"))
    response.setText(self.tr("Current annotation will be lost"))
    response.setInformativeText(
        self.tr(
            "You are going to upload new annotations to this task. Continue?"
        )
    )
    response.setStandardButtons(
        QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Ok
    )
    response.setStyleSheet(get_msg_box_style())

    if response.exec_() != QtWidgets.QMessageBox.Ok:
        return

    image_list = self.image_list if self.image_list else [self.filename]
    progress_dialog = QProgressDialog(
        self.tr("Uploading..."), self.tr("Cancel"), 0, len(image_list), self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("Progress"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setStyleSheet(
        get_progress_dialog_style(color="#1d1d1f", height=20)
    )

    try:
        for i, image_path in enumerate(image_list):
            image_filename = osp.basename(image_path)
            label_filename = osp.splitext(image_filename)[0] + ".txt"
            if label_filename not in label_file_list:
                continue

            input_file = osp.join(label_dir_path, label_filename)
            output_file = osp.join(
                output_dir_path, osp.splitext(image_filename)[0] + ".json"
            )
            image_file = osp.join(image_dir_path, image_filename)

            converter.dota_to_custom(
                input_file=input_file,
                output_file=output_file,
                image_file=image_file,
            )

            progress_dialog.setValue(i)
            if progress_dialog.wasCanceled():
                break

        progress_dialog.close()
        template = (
            "上传标注成功！\n"
            "结果已保存到：\n"
            "%s"
        )
        message_text = template % output_dir_path
        popup = Popup(
            message_text,
            self,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self, popup_height=65, position="center")

        # update and refresh the current canvas
        self.load_file(self.filename)

    except Exception as e:
        progress_dialog.close()
        message = f"Error occurred while uploading annotations: {str(e)}"
        logger.error(message)

        popup = Popup(
            message,
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")


def upload_coco_annotation(self, mode):
    if not _check_filename_exist(self):
        return

    filter = "Attribute Files (*.json);;All Files (*)"
    input_file, _ = QtWidgets.QFileDialog.getOpenFileName(
        self,
        self.tr("Select a custom coco annotation file"),
        "",
        filter,
    )

    if not input_file:
        return

    output_dir_path = osp.dirname(self.filename)
    if self.output_dir:
        output_dir_path = self.output_dir

    response = QtWidgets.QMessageBox()
    response.setIcon(QtWidgets.QMessageBox.Warning)
    response.setWindowTitle(self.tr("Warning"))
    response.setText(self.tr("Current annotation will be lost"))
    response.setInformativeText(
        self.tr(
            "You are going to upload new annotations to this task. Continue?"
        )
    )
    response.setStandardButtons(
        QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Ok
    )
    response.setStyleSheet(get_msg_box_style())

    if response.exec_() != QtWidgets.QMessageBox.Ok:
        return

    progress_dialog = QProgressDialog(
        self.tr("Uploading..."), self.tr("Cancel"), 0, 0, self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("Progress"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setRange(0, 0)
    progress_dialog.setStyleSheet(get_progress_dialog_style())

    self.upload_thread = UploadCocoThread(
        LabelConverter(), input_file, output_dir_path, mode
    )

    def on_upload_finished(success, error_msg):
        progress_dialog.close()
        if success:
            # update and refresh the current canvas
            self.load_file(self.filename)

            popup = Popup(
                "上传标注成功！",
                self,
                icon=new_icon_path("copy-green", "svg"),
            )
            popup.show_popup(self, popup_height=65, position="center")
        else:
            message = (
                f"Error occurred while uploading annotations: {str(error_msg)}"
            )
            logger.error(message)
            popup = Popup(
                message,
                self,
                icon=new_icon_path("error", "svg"),
            )
            popup.show_popup(self, position="center")

    self.upload_thread.finished.connect(on_upload_finished)

    progress_dialog.show()
    self.upload_thread.start()

    progress_dialog.canceled.connect(self.upload_thread.terminate)


def upload_voc_annotation(self, mode):
    if not _check_filename_exist(self):
        return

    dialog = QtWidgets.QDialog(self)
    dialog.setWindowTitle(self.tr("Upload Options"))
    dialog.setMinimumWidth(500)
    dialog.setStyleSheet(get_export_option_style())

    layout = QVBoxLayout()
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)

    path_layout = QVBoxLayout()
    path_label = QtWidgets.QLabel(self.tr("Select Upload Folder"))
    path_layout.addWidget(path_label)

    path_input_layout = QHBoxLayout()
    path_input_layout.setSpacing(8)

    path_edit = QtWidgets.QLineEdit()
    path_edit.setText(osp.dirname(osp.dirname(self.filename)))

    def browse_upload_folder():
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.tr("Select Upload Folder"),
            path_edit.text(),
            QtWidgets.QFileDialog.ShowDirsOnly
            | QtWidgets.QFileDialog.DontResolveSymlinks
            | QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if path:
            path_edit.setText(path)

    path_button = QtWidgets.QPushButton(self.tr("Browse"))
    path_button.clicked.connect(browse_upload_folder)
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

    label_dir_path = path_edit.text()
    image_dir_path = osp.dirname(self.filename)
    label_file_list = os.listdir(label_dir_path)
    output_dir_path = self.output_dir if self.output_dir else image_dir_path
    converter = LabelConverter()

    response = QtWidgets.QMessageBox()
    response.setIcon(QtWidgets.QMessageBox.Warning)
    response.setWindowTitle(self.tr("Warning"))
    response.setText(self.tr("Current annotation will be lost"))
    response.setInformativeText(
        self.tr(
            "You are going to upload new annotations to this task. Continue?"
        )
    )
    response.setStandardButtons(
        QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Ok
    )
    response.setStyleSheet(get_msg_box_style())

    if response.exec_() != QtWidgets.QMessageBox.Ok:
        return

    image_list = self.image_list if self.image_list else [self.filename]
    progress_dialog = QProgressDialog(
        self.tr("Uploading..."), self.tr("Cancel"), 0, len(image_list), self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("Progress"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setStyleSheet(
        get_progress_dialog_style(color="#1d1d1f", height=20)
    )

    try:
        for i, image_path in enumerate(image_list):
            image_filename = osp.basename(image_path)
            label_filename = osp.splitext(image_filename)[0] + ".xml"
            if label_filename not in label_file_list:
                continue

            input_file = osp.join(label_dir_path, label_filename)
            output_file = osp.join(
                output_dir_path, osp.splitext(image_filename)[0] + ".json"
            )
            converter.voc_to_custom(
                input_file=input_file,
                output_file=output_file,
                image_filename=image_filename,
                mode=mode,
            )

            progress_dialog.setValue(i)
            if progress_dialog.wasCanceled():
                break

        progress_dialog.close()
        template = (
            "上传标注成功！\n"
            "结果已保存到：\n"
            "%s"
        )
        message_text = template % output_dir_path
        popup = Popup(
            message_text,
            self,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self, popup_height=65, position="center")

        # update and refresh the current canvas
        self.load_file(self.filename)

    except Exception as e:
        progress_dialog.close()
        message = f"Error occurred while uploading annotations: {str(e)}"
        logger.error(message)

        popup = Popup(
            message,
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")


def upload_yolo_annotation(self, mode, LABEL_OPACITY):
    if not _check_filename_exist(self):
        return

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

        labels = []
        with open(self.yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            for class_name, keypoint_name in data["classes"].items():
                labels.append(class_name)
                labels.extend(keypoint_name)
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

        with open(self.classes_file, "r", encoding="utf-8") as f:
            labels = f.read().splitlines()
        converter = LabelConverter(classes_file=self.classes_file)

    dialog = QtWidgets.QDialog(self)
    dialog.setWindowTitle(self.tr("Upload Options"))
    dialog.setMinimumWidth(500)
    dialog.setStyleSheet(get_export_option_style())

    layout = QVBoxLayout()
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)

    path_layout = QVBoxLayout()
    path_label = QtWidgets.QLabel(self.tr("Select Upload Folder"))
    path_layout.addWidget(path_label)

    path_input_layout = QHBoxLayout()
    path_input_layout.setSpacing(8)

    path_edit = QtWidgets.QLineEdit()
    path_edit.setText(osp.dirname(osp.dirname(self.filename)))

    def browse_upload_folder():
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.tr("Select Upload Folder"),
            path_edit.text(),
            QtWidgets.QFileDialog.ShowDirsOnly
            | QtWidgets.QFileDialog.DontResolveSymlinks
            | QtWidgets.QFileDialog.DontUseNativeDialog,
        )
        if path:
            path_edit.setText(path)

    path_button = QtWidgets.QPushButton(self.tr("Browse"))
    path_button.clicked.connect(browse_upload_folder)
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

    label_dir_path = path_edit.text()
    image_dir_path = osp.dirname(self.filename)
    image_file_list = os.listdir(image_dir_path)
    label_file_list = os.listdir(label_dir_path)
    output_dir_path = self.output_dir if self.output_dir else image_dir_path

    # Create a custom message box
    msg_box = QtWidgets.QMessageBox(self)
    msg_box.setWindowTitle(self.tr("导入选项"))
    msg_box.setText(self.tr("部分图片可能已存在标签。"))
    msg_box.setInformativeText(self.tr("您希望合并现有标签还是覆盖它们？"))
    msg_box.setIcon(QtWidgets.QMessageBox.Question)

    # Add custom buttons
    merge_button = msg_box.addButton(self.tr("合并"), QtWidgets.QMessageBox.AcceptRole)
    overwrite_button = msg_box.addButton(self.tr("覆盖"), QtWidgets.QMessageBox.DestructiveRole)
    cancel_button = msg_box.addButton(self.tr("取消"), QtWidgets.QMessageBox.RejectRole)
    
    msg_box.setDefaultButton(merge_button)
    
    reply = msg_box.exec_()

    merge = False
    if msg_box.clickedButton() == merge_button:
        merge = True
    elif msg_box.clickedButton() == overwrite_button:
        merge = False
    else: # cancel_button
        return

    progress_dialog = QProgressDialog(
        self.tr("Uploading..."),
        self.tr("Cancel"),
        0,
        len(image_file_list),
        self,
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("Progress"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setStyleSheet(
        get_progress_dialog_style(color="#1d1d1f", height=20)
    )

    try:
        for i, image_filename in enumerate(image_file_list):
            if image_filename.endswith(".json"):
                continue
            label_filename = osp.splitext(image_filename)[0] + ".txt"
            data_filename = osp.splitext(image_filename)[0] + ".json"
            if label_filename not in label_file_list:
                continue
            input_file = osp.join(label_dir_path, label_filename)
            output_file = osp.join(output_dir_path, data_filename)
            image_file = osp.join(image_dir_path, image_filename)

            if mode in ["hbb", "seg"]:
                converter.yolo_to_custom(
                    input_file=input_file,
                    output_file=output_file,
                    image_file=image_file,
                    mode=mode,
                    merge=merge,
                )
            elif mode == "obb":
                converter.yolo_obb_to_custom(
                    input_file=input_file,
                    output_file=output_file,
                    image_file=image_file,
                    merge=merge,
                )
            elif mode == "pose":
                converter.yolo_pose_to_custom(
                    input_file=input_file,
                    output_file=output_file,
                    image_file=image_file,
                    merge=merge,
                )

            progress_dialog.setValue(i)
            if progress_dialog.wasCanceled():
                break

        progress_dialog.close()
        self.load_file(self.filename)
        popup = Popup(
            "上传完成！",
            self,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self, position="center")

        # Initialize unique labels
        for label in labels:
            if not self.unique_label_list.find_items_by_label(label):
                item = self.unique_label_list.create_item_from_label(label)
                self.unique_label_list.addItem(item)
                rgb = self._get_rgb_by_label(label)
                self.unique_label_list.set_item_label(
                    item, label, rgb, LABEL_OPACITY
                )

    except Exception as e:
        progress_dialog.close()
        message = f"Error occurred while uploading annotations: {str(e)}"
        logger.error(message)

        popup = Popup(
            message,
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")


def upload_label_classes_file(self):
    filter = "Label Files (*.txt);;All Files (*)"
    file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
        self,
        self.tr("Select a specific label classes file"),
        "",
        filter,
    )
    if not file_path:
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            labels = [line.strip() for line in f.readlines()]

        if not labels:
            popup = Popup(
                self.tr("No labels found in the file!"),
                self,
                icon=new_icon_path("error", "svg"),
            )
            popup.show_popup(self, position="center")
            return

        response = QtWidgets.QMessageBox()
        response.setIcon(QtWidgets.QMessageBox.Warning)
        response.setWindowTitle(self.tr("Warning"))
        response.setText(self.tr("Current labels will be lost"))
        response.setInformativeText(
            self.tr(
                "You are going to upload new labels to this task. Continue?"
            )
        )
        response.setStandardButtons(
            QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Ok
        )
        response.setStyleSheet(get_msg_box_style())

        if response.exec_() != QtWidgets.QMessageBox.Ok:
            return

        # Update unique_label_list
        self.unique_label_list.clear()
        self.load_labels(labels)

        # Update label_dialog.label_list
        self.label_dialog.label_list.clear()
        self.label_dialog.label_list.addItems(labels)
        if self.label_dialog._sort_labels:
            self.label_dialog.sort_labels()

        popup = Popup(
            self.tr(f"Successfully loaded {len(set(labels))} labels!"),
            self,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self, position="center")

    except Exception as e:
        message = (
            f"Error occurred while uploading label classes file: {str(e)}"
        )
        logger.error(message)

        popup = Popup(
            message,
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")


def upload_shape_attrs_file(self, LABEL_OPACITY):
    filter = "Shape Attributes Files (*.json);;All Files (*)"
    file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
        self,
        self.tr("Select a specific shape attributes file"),
        "",
        filter,
    )
    if not file_path:
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            self.attributes = json.load(f)
            for label in list(self.attributes.keys()):
                if not self.unique_label_list.find_items_by_label(label):
                    item = self.unique_label_list.create_item_from_label(label)
                    self.unique_label_list.addItem(item)
                    rgb = self._get_rgb_by_label(label)
                    self.unique_label_list.set_item_label(
                        item, label, rgb, LABEL_OPACITY
                    )

        # update the shape attributes dialog
        self.shape_attributes.show()
        self.scroll_area.show()
        self.canvas.h_shape_is_hovered = False
        self.canvas.mode_changed.disconnect(self.set_edit_mode)

        popup = Popup(
            "上传形状属性文件成功！",
            self,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self, popup_height=65, position="center")

    except Exception as e:
        message = (
            f"Error occurred while uploading shape attributes file: {str(e)}"
        )
        logger.error(message)

        popup = Popup(
            message,
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")


def upload_label_flags_file(self, LABEL_OPACITY):
    filter = "Label Flags Files (*.yaml);;All Files (*)"
    file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
        self,
        self.tr("Select a specific flags file"),
        "",
        filter,
    )
    if not file_path:
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            # Each line in the file is an flag-level flag
            self.label_flags = yaml.safe_load(f)
            for label in list(self.label_flags.keys()):
                if not self.unique_label_list.find_items_by_label(label):
                    item = self.unique_label_list.create_item_from_label(label)
                    self.unique_label_list.addItem(item)
                    rgb = self._get_rgb_by_label(label)
                    self.unique_label_list.set_item_label(
                        item, label, rgb, LABEL_OPACITY
                    )

        # update the label dialog
        self.label_dialog.upload_flags(self.label_flags)

        popup = Popup(
            "上传标志文件成功！",
            self,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self, popup_height=65, position="center")

    except Exception as e:
        message = f"Error occurred while uploading flags file: {str(e)}"
        logger.error(message)

        popup = Popup(
            message,
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")


def upload_image_flags_file(self):
    filter = "Image Flags Files (*.txt);;All Files (*)"
    file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
        self,
        self.tr("Select a specific flags file"),
        "",
        filter,
    )
    if not file_path:
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            # Each line in the file is an image-level flag
            self.image_flags = f.read().splitlines()
            self.load_flags({k: False for k in self.image_flags})
        self.flag_dock.show()

        # update and refresh the current canvas
        self.load_file(self.filename)

        popup = Popup(
            "上传标志文件成功！",
            self,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self, popup_height=65, position="center")

    except Exception as e:
        message = f"Error occurred while uploading flags file: {str(e)}"
        logger.error(message)
        popup = Popup(
            message,
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")


def upload_ballontranslator_annotation(self):
    if not _check_filename_exist(self):
        return

    filter = "BallonsTranslator JSON (*.json);;All Files (*)"
    input_file, _ = QtWidgets.QFileDialog.getOpenFileName(
        self,
        self.tr("选择一个 BallonsTranslator 项目文件"),
        "",
        filter,
    )

    if not input_file:
        return

    progress_dialog = QProgressDialog(
        self.tr("正在导入 BallonsTranslator 项目..."), self.tr("取消"), 0, 0, self
    )
    progress_dialog.setWindowModality(Qt.WindowModal)
    progress_dialog.setWindowTitle(self.tr("导入进度"))
    progress_dialog.setMinimumWidth(500)
    progress_dialog.setMinimumHeight(150)
    progress_dialog.setRange(0, 0)  # Indeterminate
    progress_dialog.setStyleSheet(
        get_progress_dialog_style(color="#1d1d1f", height=20)
    )

    self.upload_thread = UploadBallonTranslatorThread(input_file)

    def on_upload_finished(success, error_msg):
        progress_dialog.close()
        if success:
            # 刷新文件列表和UI
            current_dir = osp.dirname(self.filename)
            self.import_image_folder(current_dir, load=True)

            popup = Popup(
                self.tr("成功导入 BallonsTranslator 标注！\n文件已保存至原始图片目录。"),
                self,
                icon=new_icon_path("copy-green", "svg"),
            )
            popup.show_popup(self, popup_height=65, position="center")
        else:
            message = f"导入标注时发生错误: {str(error_msg)}"
            logger.error(message)
            popup = Popup(
                message,
                self,
                icon=new_icon_path("error", "svg"),
            )
            popup.show_popup(self, position="center")

    self.upload_thread.finished.connect(on_upload_finished)

    progress_dialog.show()
    self.upload_thread.start()

    progress_dialog.canceled.connect(self.upload_thread.terminate)

def upload_imagetrans_annotation(self):
    if not _check_filename_exist(self):
        return

    filter = "ImageTrans Project (*.itp *.json);;All Files (*)"
    input_file, _ = QtWidgets.QFileDialog.getOpenFileName(
        self,
        self.tr("选择一个 ImageTrans 项目文件"),
        "",
        filter,
    )

    if not input_file:
        return

    try:
        convert_itp_to_anylabel(input_file)
        
        # 刷新文件列表和UI
        current_dir = osp.dirname(self.filename)
        self.import_image_folder(current_dir, load=True)

        popup = Popup(
            self.tr("成功导入 ImageTrans 标注！\n文件已保存至原始图片目录。"),
            self,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self, popup_height=65, position="center")

    except Exception as e:
        message = f"导入标注时发生错误: {str(e)}"
        logger.error(message)
        popup = Popup(
            message,
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")

def upload_labelplus_annotation(self):
    if not _check_filename_exist(self):
        return

    filter = "LabelPlus Files (*.txt);;All Files (*)"
    input_file, _ = QtWidgets.QFileDialog.getOpenFileName(
        self,
        self.tr("选择 LabelPlus 格式文件"),
        "",
        filter,
    )

    if not input_file:
        return

    output_dir_path = osp.dirname(self.filename)
    if self.output_dir:
        output_dir_path = self.output_dir

    # Get image directory
    image_dir_path = osp.dirname(self.filename)

    response = QtWidgets.QMessageBox()
    response.setIcon(QtWidgets.QMessageBox.Warning)
    response.setWindowTitle(self.tr("警告"))
    response.setText(self.tr("当前标注将会丢失"))
    response.setInformativeText(
        self.tr(
            "您将要为此任务上传新的标注。是否继续？"
        )
    )
    response.setStandardButtons(
        QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Ok
    )
    response.setStyleSheet(get_msg_box_style())

    if response.exec_() != QtWidgets.QMessageBox.Ok:
        return

    try:
        converter = LabelConverter()
        converter.labelplus_to_custom(
            input_file=input_file,
            output_dir_path=output_dir_path,
            image_dir_path=image_dir_path,
        )

        # Refresh file list and UI
        current_dir = osp.dirname(self.filename)
        self.import_image_folder(current_dir, load=True)

        popup = Popup(
            self.tr("成功导入 LabelPlus 标注！\n标注已保存为点模式。"),
            self,
            icon=new_icon_path("copy-green", "svg"),
        )
        popup.show_popup(self, popup_height=65, position="center")

    except Exception as e:
        message = self.tr("导入 LabelPlus 标注时发生错误: %s") % str(e)
        logger.error(message)
        popup = Popup(
            message,
            self,
            icon=new_icon_path("error", "svg"),
        )
        popup.show_popup(self, position="center")

