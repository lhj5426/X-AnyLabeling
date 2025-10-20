import os
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QFileDialog, QTextEdit,
    QLabel, QLineEdit, QRadioButton, QGroupBox, QHBoxLayout, QSpinBox
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt

class Worker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, files_to_process, labels_a, labels_b, mode):
        super().__init__()
        self.files_to_process = files_to_process
        self.labels_a = labels_a
        self.labels_b = labels_b
        self.mode = mode

    def run(self):
        if not self.files_to_process:
            self.log_signal.emit("没有找到需要处理的文件。")
            self.finished_signal.emit()
            return

        for image_path in self.files_to_process:
            if self.isInterruptionRequested():
                self.log_signal.emit("操作被用户取消。")
                break
            
            json_filename = os.path.splitext(os.path.basename(image_path))[0] + '.json'
            # Assuming JSON files are in the same directory as images
            json_path = os.path.join(os.path.dirname(image_path), json_filename)
            
            if os.path.exists(json_path):
                self.process_file(json_path)
            else:
                self.log_signal.emit(f"警告：未找到对应的JSON文件，跳过 {os.path.basename(image_path)}")

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
        elif self.mode == 'bulk_edit':
            self.bulk_edit(data)
        elif self.mode == 'to_monocolor':
            self.to_monocolor(data)

        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.log_signal.emit(f"--- 文件 {os.path.basename(json_path)} 处理完成并已保存。 ---\n")
        except Exception as e:
            self.log_signal.emit(f"错误：无法写入文件 {json_path}。原因: {e}")

    def to_bicolor(self, data):
        label_map = dict(zip(self.labels_a, self.labels_b))
        counters = {label: 0 for label in self.labels_a}
        for shape in data['shapes']:
            label = shape.get('label')
            if label in counters:
                counters[label] += 1
                if counters[label] % 2 == 0:
                    new_label = label_map[label]
                    shape['label'] = new_label
                    self.log_signal.emit(f"  已将第 {counters[label]} 个 '{label}' 修改为 '{new_label}'")

    def bulk_edit(self, data):
        label_map = dict(zip(self.labels_a, self.labels_b))
        for shape in data['shapes']:
            label = shape.get('label')
            if label in label_map:
                original_label = label
                new_label = label_map[label]
                shape['label'] = new_label
                self.log_signal.emit(f"  已将 '{original_label}' 批量修改为 '{new_label}'")

    def to_monocolor(self, data):
        revert_map = dict(zip(self.labels_b, self.labels_a))
        for shape in data['shapes']:
            label = shape.get('label')
            if label in revert_map:
                original_label = revert_map[label]
                shape['label'] = original_label
                self.log_signal.emit(f"  已将 '{label}' 还原为 '{original_label}'")

class LabelToolDialog(QDialog):
    def __init__(self, folder_path, parent=None):
        super().__init__(parent)
        self.folder_path = folder_path
        self.setWindowTitle("双色标签工具")
        self.setMinimumSize(500, 400)
        # 设置窗口标志：移除帮助按钮,添加最小化按钮
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint
        )
        self.layout = QVBoxLayout(self)

        # Folder path display
        self.folder_label = QLabel(f"处理目录: {self.folder_path}\n")
        self.layout.addWidget(self.folder_label)

        # Label input group
        labels_group = QGroupBox("标签设置")
        labels_layout = QVBoxLayout(labels_group)

        self.label_a_label = QLabel("单数标签 (Label A):")
        self.label_a_edit = QLineEdit("qipao,balloon,changfangtiao")
        labels_layout.addWidget(self.label_a_label)
        labels_layout.addWidget(self.label_a_edit)

        self.label_b_label = QLabel("双数标签 (Label B):")
        self.label_b_edit = QLineEdit("qipao2,balloon2,changfangtiao2")
        labels_layout.addWidget(self.label_b_label)
        labels_layout.addWidget(self.label_b_edit)

        self.layout.addWidget(labels_group)

        # Range selection group
        range_group = QGroupBox("范围选择")
        range_layout = QHBoxLayout(range_group)
        self.start_spinbox = QSpinBox()
        self.start_spinbox.setPrefix("从: ")
        self.end_spinbox = QSpinBox()
        self.end_spinbox.setPrefix("到: ")

        total_files = 0
        if self.parent() and hasattr(self.parent(), 'file_list_widget'):
            total_files = self.parent().file_list_widget.count()

        if total_files > 0:
            self.start_spinbox.setRange(1, total_files)
            self.end_spinbox.setRange(1, total_files)
            self.start_spinbox.setValue(1)
            self.end_spinbox.setValue(total_files)

        range_layout.addWidget(self.start_spinbox)
        range_layout.addWidget(self.end_spinbox)
        range_layout.addStretch()
        range_group.setLayout(range_layout)
        self.layout.addWidget(range_group)

        # Mode selection
        self.mode_group = QGroupBox("模式")
        self.bulk_edit_radio = QRadioButton("批量修改标签 (将所有A替换为B)")
        self.to_bicolor_radio = QRadioButton("间隔修改标签 (将偶数个A替换为B)")
        self.to_monocolor_radio = QRadioButton("还原为单色标签 (将B还原为A)")
        self.bulk_edit_radio.setChecked(True)
        mode_layout = QVBoxLayout()
        mode_layout.addWidget(self.bulk_edit_radio)
        mode_layout.addWidget(self.to_bicolor_radio)
        mode_layout.addWidget(self.to_monocolor_radio)
        self.mode_group.setLayout(mode_layout)
        self.layout.addWidget(self.mode_group)

        # Action buttons
        button_layout = QHBoxLayout()
        self.run_all_button = QPushButton("处理全部")
        self.run_all_button.clicked.connect(self.run_all_processing)
        self.run_range_button = QPushButton("处理指定范围")
        self.run_range_button.clicked.connect(self.run_range_processing)
        self.run_current_button = QPushButton("处理当前页")
        self.run_current_button.clicked.connect(self.run_current_page_processing)
        button_layout.addWidget(self.run_all_button)
        button_layout.addWidget(self.run_range_button)
        button_layout.addWidget(self.run_current_button)
        self.layout.addLayout(button_layout)

        # Log display
        self.log_label = QLabel("日志:")
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.layout.addWidget(self.log_label)
        self.layout.addWidget(self.log_output)

    def refresh_state(self, total_files: int, current_page: int, folder_path: str) -> None:
        """刷新对话框的状态，包括文件范围和文件夹路径。"""
        self.folder_path = folder_path
        self.folder_label.setText(f"处理目录: {self.folder_path}\n")

        if total_files > 0:
            self.start_spinbox.setRange(1, total_files)
            self.end_spinbox.setRange(1, total_files)
            self.start_spinbox.setValue(1)
            self.end_spinbox.setValue(total_files)


    def run_all_processing(self):
        if not self.parent() or not hasattr(self.parent(), 'image_list') or not self.parent().image_list:
            self.log_output.setText("错误：文件列表为空。")
            return
        self._run_processing_with_worker(self.parent().image_list)

    def run_range_processing(self):
        if not self.parent() or not hasattr(self.parent(), 'image_list') or not self.parent().image_list:
            self.log_output.setText("错误：文件列表为空。")
            return

        start_index = self.start_spinbox.value() - 1
        end_index = self.end_spinbox.value() - 1

        if start_index > end_index:
            self.log_output.setText("错误：起始位置不能大于结束位置。")
            return

        full_list = self.parent().image_list
        if not (0 <= start_index < len(full_list) and 0 <= end_index < len(full_list)):
            self.log_output.setText("错误：指定的范围超出了文件列表的有效索引。")
            return

        files_to_process = full_list[start_index : end_index + 1]
        self._run_processing_with_worker(files_to_process)

    def _run_processing_with_worker(self, files_to_process):
        labels_a_str = self.label_a_edit.text().strip()
        labels_b_str = self.label_b_edit.text().strip()
        
        if self.bulk_edit_radio.isChecked():
            mode = 'bulk_edit'
        elif self.to_bicolor_radio.isChecked():
            mode = 'to_bicolor'
        else:
            mode = 'to_monocolor'

        labels_a = [label.strip() for label in labels_a_str.split(',') if label.strip()]
        labels_b = [label.strip() for label in labels_b_str.split(',') if label.strip()]

        self.log_output.clear()
        if not labels_a or not labels_b:
            self.log_output.setText("错误：两个标签输入框都不能为空。")
            return
        if len(labels_a) != len(labels_b):
            self.log_output.setText("错误：两个输入框中的标签数量必须相同。")
            return

        self.run_all_button.setEnabled(False)
        self.run_range_button.setEnabled(False)
        self.run_current_button.setEnabled(False)
        
        self.worker = Worker(files_to_process, labels_a, labels_b, mode)
        self.worker.log_signal.connect(self.log_output.append)
        self.worker.finished_signal.connect(self._on_processing_finished)
        self.worker.start()

    def run_current_page_processing(self):
        labels_a_str = self.label_a_edit.text().strip()
        labels_b_str = self.label_b_edit.text().strip()

        if self.bulk_edit_radio.isChecked():
            mode = 'bulk_edit'
        elif self.to_bicolor_radio.isChecked():
            mode = 'to_bicolor'
        else:
            mode = 'to_monocolor'

        labels_a = [label.strip() for label in labels_a_str.split(',') if label.strip()]
        labels_b = [label.strip() for label in labels_b_str.split(',') if label.strip()]

        self.log_output.clear()
        if not labels_a or not labels_b:
            self.log_output.setText("错误：两个标签输入框都不能为空。")
            return
        if len(labels_a) != len(labels_b):
            self.log_output.setText("错误：两个输入框中的标签数量必须相同。")
            return

        if not self.parent() or not hasattr(self.parent(), 'filename') or not self.parent().filename:
            self.log_output.setText("错误：没有在主窗口中打开任何文件。")
            return

        self.run_all_button.setEnabled(False)
        self.run_range_button.setEnabled(False)
        self.run_current_button.setEnabled(False)

        current_image_file = self.parent().filename
        json_path = os.path.splitext(current_image_file)[0] + ".json"

        if not os.path.exists(json_path):
            self.log_output.setText(f"错误：未找到当前文件对应的JSON文件：\n{json_path}")
            self._on_processing_finished()
            return

        self.log_output.append(f"--- 正在处理当前文件: {os.path.basename(json_path)} ---")
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.log_output.append(f"错误：无法读取或解析JSON文件。原因: {e}")
            self._on_processing_finished()
            return

        if 'shapes' not in data or not isinstance(data['shapes'], list):
            self.log_output.append(f"警告：在文件中未找到 'shapes' 列表，已跳过。")
            self._on_processing_finished()
            return

        if mode == 'to_bicolor':
            self._to_bicolor(data, labels_a, labels_b)
        elif mode == 'bulk_edit':
            self._bulk_edit(data, labels_a, labels_b)
        elif mode == 'to_monocolor':
            self._to_monocolor(data, labels_a, labels_b)

        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.log_output.append(f"--- 文件处理完成并已保存。 ---\n")
            # Reload the file in the main window to show changes
            if self.parent() and hasattr(self.parent(), 'load_file'):
                self.parent().load_file(current_image_file)
                self.log_output.append("主窗口已刷新。")

        except Exception as e:
            self.log_output.append(f"错误：无法写入文件。原因: {e}")
        finally:
            self._on_processing_finished()

    def _on_processing_finished(self):
        self.run_all_button.setEnabled(True)
        self.run_range_button.setEnabled(True)
        self.run_current_button.setEnabled(True)

    def _to_bicolor(self, data, labels_a, labels_b):
        label_map = dict(zip(labels_a, labels_b))
        counters = {label: 0 for label in labels_a}
        for shape in data['shapes']:
            label = shape.get('label')
            if label in counters:
                counters[label] += 1
                if counters[label] % 2 == 0:
                    new_label = label_map[label]
                    shape['label'] = new_label
                    self.log_output.append(f"  已将第 {counters[label]} 个 '{label}' 修改为 '{new_label}'")

    def _bulk_edit(self, data, labels_a, labels_b):
        label_map = dict(zip(labels_a, labels_b))
        for shape in data['shapes']:
            label = shape.get('label')
            if label in label_map:
                original_label = label
                new_label = label_map[label]
                shape['label'] = new_label
                self.log_output.append(f"  已将 '{original_label}' 批量修改为 '{new_label}'")

    def _to_monocolor(self, data, labels_a, labels_b):
        revert_map = dict(zip(labels_b, labels_a))
        for shape in data['shapes']:
            label = shape.get('label')
            if label in revert_map:
                original_label = revert_map[label]
                shape['label'] = original_label
                self.log_output.append(f"  已将 '{label}' 还原为 '{original_label}'")
