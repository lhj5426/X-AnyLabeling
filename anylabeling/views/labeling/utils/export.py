import json
import os
import os.path as osp
import pathlib
import shutil
import time

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QThread, pyqtSignal
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
    ):
        super().__init__()
        self.converter = converter
        self.image_list = image_list
        self.label_dir_path = label_dir_path
        self.save_path = save_path
        self.mode = mode
        self.prefix = prefix

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

    path_edit = QtWidgets.QLineEdit()
    path_edit.setText(
        osp.realpath(osp.join(osp.dirname(self.filename), "..", "labels"))
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
            src_file = osp.join(label_dir_path, label_file_name)

            if osp.exists(src_file):
                try:
                    with open(src_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if data.get("manually_edited", False):
                            filtered_image_list.append(image_file)
                except:
                    pass
        image_list = filtered_image_list

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

            src_file = osp.join(label_dir_path, label_file_name)
            dst_file = osp.join(save_path, dst_file_name)

            is_empty_file = converter.custom_to_yolo(
                src_file, dst_file, mode, skip_empty_files
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

            src_file = osp.join(label_dir_path, label_file_name)
            dst_file = osp.join(save_path, dst_file_name)

            is_empty_file = converter.custom_to_voc(
                image_file, src_file, dst_file, mode, skip_empty_files
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

            src_file = osp.join(label_dir_path, label_file_name)
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

            src_file = osp.join(label_dir_path, label_file_name)
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
