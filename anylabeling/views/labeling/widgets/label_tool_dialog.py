import os
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QFileDialog, QTextEdit,
    QLabel, QLineEdit, QRadioButton, QGroupBox, QHBoxLayout
)
from PyQt5.QtCore import QThread, pyqtSignal

class Worker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, folder_path, labels, mode):
        super().__init__()
        self.folder_path = folder_path
        self.labels = [label.strip() for label in labels.split(',') if label.strip()]
        self.mode = mode

    def run(self):
        if not self.labels:
            self.log_signal.emit("错误：请输入至少一个标签。")
            self.finished_signal.emit()
            return

        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}
        found_files = False
        for filename in os.listdir(self.folder_path):
            base_name, extension = os.path.splitext(filename)
            if extension.lower() in image_extensions:
                json_filename = base_name + '.json'
                json_path = os.path.join(self.folder_path, json_filename)
                if os.path.exists(json_path):
                    found_files = True
                    self.process_file(json_path)
        
        if not found_files:
            self.log_signal.emit("未在所选目录中找到任何匹配的图片和JSON文件对。")
        
        self.finished_signal.emit()

    def process_file(self, json_path):
        self.log_signal.emit(f"--- 正在处理文件: {os.path.basename(json_path)} ---")
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.log_signal.emit(f"错误：无法读取或解析JSON文件 {json_path}。原因: {e}")
            return

        if 'shapes' not in data or not isinstance(data['shapes'], list):
            self.log_signal.emit(f"警告：在 {json_path} 中未找到 'shapes' 列表，跳过此文件。")
            return

        if self.mode == 'to_bicolor':
            self.to_bicolor(data)
        elif self.mode == 'to_monocolor':
            self.to_monocolor(data)

        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.log_signal.emit(f"--- 文件 {os.path.basename(json_path)} 处理完成并已保存。 ---\n")
        except Exception as e:
            self.log_signal.emit(f"错误：无法写入文件 {json_path}。原因: {e}")

    def to_bicolor(self, data):
        counters = {label: 0 for label in self.labels}
        for shape in data['shapes']:
            label = shape.get('label')
            if label in self.labels:
                counters[label] += 1
                if counters[label] % 2 == 0:
                    new_label = f"{label}2"
                    shape['label'] = new_label
                    self.log_signal.emit(f"  已将第 {counters[label]} 个 '{label}' 修改为 '{new_label}'")

    def to_monocolor(self, data):
        labels_to_revert = {f"{label}2": label for label in self.labels}
        for shape in data['shapes']:
            label = shape.get('label')
            if label in labels_to_revert:
                original_label = labels_to_revert[label]
                shape['label'] = original_label
                self.log_signal.emit(f"  已将 '{label}' 还原为 '{original_label}'")

class LabelToolDialog(QDialog):
    def __init__(self, folder_path, parent=None):
        super().__init__(parent)
        self.folder_path = folder_path
        self.setWindowTitle("双色标签工具")
        self.setMinimumSize(500, 400)
        self.layout = QVBoxLayout(self)

        # Label input
        self.labels_label = QLabel(f"处理目录: {self.folder_path}\n\n要处理的标签 (用逗号分隔):")
        self.labels_edit = QLineEdit("qipao,balloon,changfangtiao")
        self.layout.addWidget(self.labels_label)
        self.layout.addWidget(self.labels_edit)

        # Mode selection
        self.mode_group = QGroupBox("模式")
        self.to_bicolor_radio = QRadioButton("转换为双色标签")
        self.to_monocolor_radio = QRadioButton("还原为单色标签")
        self.to_bicolor_radio.setChecked(True)
        mode_layout = QVBoxLayout()
        mode_layout.addWidget(self.to_bicolor_radio)
        mode_layout.addWidget(self.to_monocolor_radio)
        self.mode_group.setLayout(mode_layout)
        self.layout.addWidget(self.mode_group)

        # Action button
        self.run_button = QPushButton("开始处理")
        self.run_button.clicked.connect(self.run_processing)
        self.layout.addWidget(self.run_button)

        # Log display
        self.log_label = QLabel("日志:")
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.layout.addWidget(self.log_label)
        self.layout.addWidget(self.log_output)

    def run_processing(self):
        labels = self.labels_edit.text()
        mode = 'to_bicolor' if self.to_bicolor_radio.isChecked() else 'to_monocolor'
        
        self.run_button.setEnabled(False)
        self.log_output.clear()
        
        self.worker = Worker(self.folder_path, labels, mode)
        self.worker.log_signal.connect(self.log_output.append)
        self.worker.finished_signal.connect(lambda: self.run_button.setEnabled(True))
        self.worker.start()
