
import os
import json
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QRadioButton,
    QLineEdit,
    QTextEdit,
    QLabel,
    QGroupBox,
)
from PyQt5.QtCore import Qt


class DualColorToolDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("双色标签工具")
        self.setMinimumSize(500, 400)
        # 设置窗口标志：移除帮助按钮,添加最小化按钮
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint
        )

        # Layout
        main_layout = QVBoxLayout(self)
        self.setLayout(main_layout)

        # Directory Selection
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel("目标文件夹:")
        self.dir_edit = QLineEdit()
        self.browse_button = QPushButton("浏览...")
        self.browse_button.clicked.connect(self.browse_directory)
        dir_layout.addWidget(self.dir_label)
        dir_layout.addWidget(self.dir_edit)
        dir_layout.addWidget(self.browse_button)
        main_layout.addLayout(dir_layout)

        # Mode Selection
        mode_groupbox = QGroupBox("操作模式")
        mode_layout = QVBoxLayout()
        self.convert_radio = QRadioButton("转换为双色标签")
        self.revert_radio = QRadioButton("还原为单色标签")
        self.convert_radio.setChecked(True)
        mode_layout.addWidget(self.convert_radio)
        mode_layout.addWidget(self.revert_radio)
        mode_groupbox.setLayout(mode_layout)
        main_layout.addWidget(mode_groupbox)

        # Target Labels
        labels_layout = QHBoxLayout()
        self.labels_label = QLabel("目标标签 (用逗号分隔):")
        self.labels_edit = QLineEdit("qipao,balloon,changfangtiao")
        labels_layout.addWidget(self.labels_label)
        labels_layout.addWidget(self.labels_edit)
        main_layout.addLayout(labels_layout)

        # Run Button
        self.run_button = QPushButton("开始处理")
        self.run_button.clicked.connect(self.run_processing)
        main_layout.addWidget(self.run_button)

        # Log View
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        main_layout.addWidget(self.log_view)

    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if directory:
            self.dir_edit.setText(directory)

    def log(self, message):
        self.log_view.append(message)
        self.log_view.repaint()

    def run_processing(self):
        directory = self.dir_edit.text()
        if not os.path.isdir(directory):
            self.log("错误: 请选择一个有效的文件夹。 সন")
            return

        target_labels_str = self.labels_edit.text()
        if not target_labels_str:
            self.log("错误: 请输入目标标签。 সন")
            return
        target_labels = {label.strip() for label in target_labels_str.split(",")}

        self.log("开始处理...")
        if self.convert_radio.isChecked():
            self.process_files(directory, target_labels, "convert")
        else:
            self.process_files(directory, target_labels, "revert")
        self.log("处理完成。")

    def process_files(self, directory, target_labels, mode):
        for filename in os.listdir(directory):
            if filename.endswith(".json"):
                json_path = os.path.join(directory, filename)
                if mode == "convert":
                    self.process_convert(json_path, target_labels)
                else:
                    self.process_revert(json_path, target_labels)

    def process_convert(self, json_path, target_labels):
        self.log(f"--- 正在处理文件: {os.path.basename(json_path)} ---")
        counters = {label: 0 for label in target_labels}
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.log(f"错误：无法读取或解析JSON文件 {json_path}。原因: {e}")
            return

        if 'shapes' not in data or not isinstance(data['shapes'], list):
            self.log(f"警告：在 {json_path} 中未找到 'shapes' 列表，跳过此文件。 সন")
            return

        for shape in data['shapes']:
            label = shape.get('label')
            if label in target_labels:
                counters[label] += 1
                if counters[label] % 2 == 0:
                    new_label = f"{label}2"
                    shape['label'] = new_label
                    self.log(f"  已将第 {counters[label]} 个 '{label}' 修改为 '{new_label}'")

        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.log(f"--- 文件 {os.path.basename(json_path)} 处理完成并已保存。 ---
")
        except Exception as e:
            self.log(f"错误：无法写入文件 {json_path}。原因: {e}")

    def process_revert(self, json_path, target_labels):
        self.log(f"--- 正在还原文件: {os.path.basename(json_path)} ---")
        labels_to_revert = {f"{label}2": label for label in target_labels}
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.log(f"错误：无法读取或解析JSON文件 {json_path}。原因: {e}")
            return

        if 'shapes' not in data or not isinstance(data['shapes'], list):
            self.log(f"警告：在 {json_path} 中未找到 'shapes' 列表，跳过此文件。 সন")
            return

        for shape in data['shapes']:
            label = shape.get('label')
            if label in labels_to_revert:
                original_label = labels_to_revert[label]
                shape['label'] = original_label
                self.log(f"  已将 '{label}' 还原为 '{original_label}'")

        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.log(f"--- 文件 {os.path.basename(json_path)} 还原完成并已保存。 ---
")
        except Exception as e:
            self.log(f"错误：无法写入文件 {json_path}。原因: {e}")
