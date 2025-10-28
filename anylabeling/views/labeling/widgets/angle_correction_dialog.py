# -*- encoding: utf-8 -*- 

import json
import math
import os
from datetime import datetime

from PyQt5 import QtCore, QtGui, QtWidgets


from anylabeling.views.labeling.logger import logger
from anylabeling.views.labeling.widgets.popup import Popup
from anylabeling.views.labeling.utils.qt import new_icon_path
from anylabeling.views.labeling.utils.style import get_ok_btn_style

def angular_distance(angle1, angle2):
    """Calculates the shortest distance between two angles."""
    d = abs(angle1 - angle2) % 360
    return min(d, 360 - d)

def rotate_point(p, center, theta):
    """Helper function to rotate a point around a center."""
    order = p - center
    cosTheta = math.cos(theta)
    sinTheta = math.sin(theta)
    pResx = cosTheta * order.x() + sinTheta * order.y()
    pResy = -sinTheta * order.x() + cosTheta * order.y()
    pRes = QtCore.QPointF(center.x() + pResx, center.y() + pResy)
    return pRes


class AngleCorrectionDialog(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(AngleCorrectionDialog, self).__init__(parent)
        self.parent = parent
        self.image_file_list = self.get_image_file_list()
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle(self.tr("旋转框角度批量修正工具"))
        self.setWindowFlags(
            self.windowFlags()
            | QtCore.Qt.WindowMinimizeButtonHint
            | QtCore.Qt.WindowMaximizeButtonHint
        )
        self.resize(500, 450)
        self.move_to_center()

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # --- Top GroupBox for settings ---
        settings_group = QtWidgets.QGroupBox()
        settings_layout = QtWidgets.QFormLayout(settings_group)
        settings_layout.setSpacing(10)
        settings_layout.setLabelAlignment(QtCore.Qt.AlignRight)

        # 1. Specify Labels
        self.labels_input = QtWidgets.QLineEdit("balloon, qipao, changfangtiao, other")
        self.labels_input.setPlaceholderText(self.tr("留空则处理所有标签"))
        settings_layout.addRow(self.tr("指定标签 (逗号分隔):"), self.labels_input)

        # 2. Scope
        # 2. Scope
        self.scope_group = QtWidgets.QButtonGroup(self)
        self.radio_current = QtWidgets.QRadioButton(self.tr("仅当前页"))
        self.radio_all = QtWidgets.QRadioButton(self.tr("所有打开的页面"))
        self.radio_range = QtWidgets.QRadioButton(self.tr("指定范围"))
        self.radio_current.setChecked(True)

        self.scope_group.addButton(self.radio_current, 1)
        self.scope_group.addButton(self.radio_all, 2)
        self.scope_group.addButton(self.radio_range, 3)

        scope_layout = QtWidgets.QHBoxLayout()
        scope_layout.addWidget(self.radio_current)
        scope_layout.addWidget(self.radio_all)
        scope_layout.addWidget(self.radio_range)
        scope_layout.addStretch()
        settings_layout.addRow(self.tr("应用范围:"), scope_layout)

        # Range selection
        self.range_group = QtWidgets.QGroupBox()
        self.range_group.setEnabled(False) # Initially disabled
        range_layout = QtWidgets.QHBoxLayout(self.range_group)
        range_layout.setContentsMargins(10, 5, 10, 5)

        self.start_spinbox = QtWidgets.QSpinBox()
        self.start_spinbox.setPrefix(self.tr("从: "))
        self.end_spinbox = QtWidgets.QSpinBox()
        self.end_spinbox.setPrefix(self.tr("到: "))

        total_files = len(self.image_file_list)
        if total_files > 0:
            self.start_spinbox.setRange(1, total_files)
            self.end_spinbox.setRange(1, total_files)
            self.start_spinbox.setValue(1)
            self.end_spinbox.setValue(total_files)

        range_layout.addWidget(self.start_spinbox)
        range_layout.addWidget(self.end_spinbox)
        range_layout.addStretch()

        self.radio_range.toggled.connect(self.range_group.setEnabled)
        settings_layout.addRow(self.range_group)

        # 3. Target Angles
        self.target_angles_input = QtWidgets.QLineEdit("0, 90, 180, 270")
        settings_layout.addRow(self.tr("目标角度 (逗号分隔):"), self.target_angles_input)

        # 4. Tolerance
        self.pos_tolerance_input = QtWidgets.QDoubleSpinBox()
        self.pos_tolerance_input.setRange(0, 360)
        self.pos_tolerance_input.setWrapping(True)
        self.pos_tolerance_input.setValue(5.0)
        self.pos_tolerance_input.setDecimals(1)
        
        self.neg_tolerance_input = QtWidgets.QDoubleSpinBox()
        self.neg_tolerance_input.setRange(0, 360)
        self.neg_tolerance_input.setWrapping(True)
        self.neg_tolerance_input.setValue(5.0)
        self.neg_tolerance_input.setDecimals(1)
        
        tolerance_layout = QtWidgets.QHBoxLayout()
        tolerance_layout.addWidget(QtWidgets.QLabel(self.tr("正容差:")))
        tolerance_layout.addWidget(self.pos_tolerance_input)
        tolerance_layout.addSpacing(20)
        tolerance_layout.addWidget(QtWidgets.QLabel(self.tr("负容差:")))
        tolerance_layout.addWidget(self.neg_tolerance_input)
        tolerance_layout.addStretch()
        settings_layout.addRow(self.tr("容差设置:"), tolerance_layout)

        main_layout.addWidget(settings_group)

        # --- Deletion GroupBox for settings ---
        deletion_settings_group = QtWidgets.QGroupBox(self.tr("按角度批量删除旋转框"))
        deletion_settings_layout = QtWidgets.QFormLayout(deletion_settings_group)
        deletion_settings_layout.setSpacing(10)
        deletion_settings_layout.setLabelAlignment(QtCore.Qt.AlignRight)

        # 1. Specify Labels for deletion
        self.deletion_labels_input = QtWidgets.QLineEdit("balloon, qipao, changfangtiao, other")
        self.deletion_labels_input.setPlaceholderText(self.tr("留空则处理所有标签"))
        deletion_settings_layout.addRow(self.tr("指定标签 (逗号分隔):"), self.deletion_labels_input)

        # 2. Scope for deletion
        self.deletion_scope_group = QtWidgets.QButtonGroup(self)
        self.deletion_radio_current = QtWidgets.QRadioButton(self.tr("仅当前页"))
        self.deletion_radio_all = QtWidgets.QRadioButton(self.tr("所有打开的页面"))
        self.deletion_radio_range = QtWidgets.QRadioButton(self.tr("指定范围"))
        self.deletion_radio_current.setChecked(True)

        self.deletion_scope_group.addButton(self.deletion_radio_current, 1)
        self.deletion_scope_group.addButton(self.deletion_radio_all, 2)
        self.deletion_scope_group.addButton(self.deletion_radio_range, 3)

        deletion_scope_layout = QtWidgets.QHBoxLayout()
        deletion_scope_layout.addWidget(self.deletion_radio_current)
        deletion_scope_layout.addWidget(self.deletion_radio_all)
        deletion_scope_layout.addWidget(self.deletion_radio_range)
        deletion_scope_layout.addStretch()
        deletion_settings_layout.addRow(self.tr("应用范围:"), deletion_scope_layout)

        # Range selection for deletion
        self.deletion_range_group = QtWidgets.QGroupBox()
        self.deletion_range_group.setEnabled(False)
        deletion_range_layout = QtWidgets.QHBoxLayout(self.deletion_range_group)
        deletion_range_layout.setContentsMargins(10, 5, 10, 5)

        self.deletion_start_spinbox = QtWidgets.QSpinBox()
        self.deletion_start_spinbox.setPrefix(self.tr("从: "))
        self.deletion_end_spinbox = QtWidgets.QSpinBox()
        self.deletion_end_spinbox.setPrefix(self.tr("到: "))

        total_files = len(self.image_file_list)
        if total_files > 0:
            self.deletion_start_spinbox.setRange(1, total_files)
            self.deletion_end_spinbox.setRange(1, total_files)
            self.deletion_start_spinbox.setValue(1)
            self.deletion_end_spinbox.setValue(total_files)

        deletion_range_layout.addWidget(self.deletion_start_spinbox)
        deletion_range_layout.addWidget(self.deletion_end_spinbox)
        deletion_range_layout.addStretch()
        deletion_settings_layout.addRow(self.deletion_range_group)

        self.deletion_radio_range.toggled.connect(self.deletion_range_group.setEnabled)

        # Deletion Mode
        self.deletion_mode_group = QtWidgets.QButtonGroup(self)
        self.radio_delete_outside = QtWidgets.QRadioButton(self.tr("删除范围外 (默认)"))
        self.radio_delete_inside = QtWidgets.QRadioButton(self.tr("删除范围内"))
        self.radio_delete_outside.setChecked(True)

        self.deletion_mode_group.addButton(self.radio_delete_outside, 1)
        self.deletion_mode_group.addButton(self.radio_delete_inside, 2)

        deletion_mode_layout = QtWidgets.QHBoxLayout()
        deletion_mode_layout.addWidget(self.radio_delete_outside)
        deletion_mode_layout.addWidget(self.radio_delete_inside)
        deletion_mode_layout.addStretch()
        deletion_settings_layout.addRow(self.tr("删除模式:"), deletion_mode_layout)

        # 3. Target Angles for deletion
        self.deletion_target_angles_input = QtWidgets.QLineEdit("0, 90, 180, 270")
        deletion_settings_layout.addRow(self.tr("目标角度 (逗号分隔):"), self.deletion_target_angles_input)

        # 3. Tolerance for deletion
        self.deletion_pos_tolerance_input = QtWidgets.QDoubleSpinBox()
        self.deletion_pos_tolerance_input.setRange(0, 360)
        self.deletion_pos_tolerance_input.setWrapping(True)
        self.deletion_pos_tolerance_input.setValue(5.0)
        self.deletion_pos_tolerance_input.setDecimals(1)
        
        self.deletion_neg_tolerance_input = QtWidgets.QDoubleSpinBox()
        self.deletion_neg_tolerance_input.setRange(0, 360)
        self.deletion_neg_tolerance_input.setWrapping(True)
        self.deletion_neg_tolerance_input.setValue(5.0)
        self.deletion_neg_tolerance_input.setDecimals(1)
        
        deletion_tolerance_layout = QtWidgets.QHBoxLayout()
        deletion_tolerance_layout.addWidget(QtWidgets.QLabel(self.tr("正容差:")))
        deletion_tolerance_layout.addWidget(self.deletion_pos_tolerance_input)
        deletion_tolerance_layout.addSpacing(20)
        deletion_tolerance_layout.addWidget(QtWidgets.QLabel(self.tr("负容差:")))
        deletion_tolerance_layout.addWidget(self.deletion_neg_tolerance_input)
        deletion_tolerance_layout.addStretch()
        deletion_settings_layout.addRow(self.tr("容差设置:"), deletion_tolerance_layout)

        main_layout.addWidget(deletion_settings_group)

        # --- Action Buttons ---
        buttons_layout = QtWidgets.QHBoxLayout()
        self.run_button = QtWidgets.QPushButton(self.tr("开始角度扶正"))
        self.run_button.setStyleSheet(get_ok_btn_style())
        self.run_button.clicked.connect(self.run_correction)
        
        self.run_deletion_button = QtWidgets.QPushButton(self.tr("开始删除"))
        deletion_button_style = """
            QPushButton {
                background-color: #d9534f;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 500;
                min-width: 100px;
                height: 36px;
            }
            QPushButton:hover {
                background-color: #c9302c;
            }
            QPushButton:pressed {
                background-color: #ac2925;
            }
        """
        self.run_deletion_button.setStyleSheet(deletion_button_style)
        self.run_deletion_button.clicked.connect(self.run_deletion)

        buttons_layout.addWidget(self.run_button)
        buttons_layout.addWidget(self.run_deletion_button)
        main_layout.addLayout(buttons_layout)

        # --- Log GroupBox ---
        log_group = QtWidgets.QGroupBox(self.tr("日志"))
        log_layout = QtWidgets.QVBoxLayout(log_group)
        self.log_widget = QtWidgets.QTextEdit()
        self.log_widget.setReadOnly(True)
        log_layout.addWidget(self.log_widget)
        main_layout.addWidget(log_group)

    def log(self, message):
        """Append a message to the log widget with a timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_widget.append(f"[{timestamp}] {message}")

    def get_image_file_list(self):
        """Get the list of image files from the parent widget."""
        image_file_list = []
        if hasattr(self.parent, 'file_list_widget'):
            count = self.parent.file_list_widget.count()
            for c in range(count):
                image_file = self.parent.file_list_widget.item(c).text()
                image_file_list.append(image_file)
        return image_file_list

    def move_to_center(self):
        """Move the dialog to the center of the screen."""
        qr = self.frameGeometry()
        cp = QtWidgets.QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def run_correction(self):
        """Parse inputs and execute the angle correction process."""
        self.log_widget.clear()
        
        # 1. Parse labels
        labels_to_process = {label.strip() for label in self.labels_input.text().split(',') if label.strip()}
        
        # 2. Parse target angles
        try:
            target_angles = [float(angle.strip()) for angle in self.target_angles_input.text().split(',') if angle.strip()]
            if not target_angles:
                self.log(self.tr("错误: 目标角度不能为空。"))
                return
        except ValueError:
            self.log(self.tr("错误: 目标角度包含无效数字。"))
            return

        # 3. Parse tolerances
        pos_tol = self.pos_tolerance_input.value()
        neg_tol = self.neg_tolerance_input.value()

        # 4. Determine scope
        scope_id = self.scope_group.checkedId()
        files_to_process = []
        if scope_id == 1: # Current page
            current_file = self.parent.filename
            if current_file:
                files_to_process.append(current_file)
            self.log(self.tr("范围: 仅当前页"))
        elif scope_id == 2: # All pages
            files_to_process = self.image_file_list
            self.log(self.tr("范围: 所有打开的页面"))
        else: # Specified range
            start_index = self.start_spinbox.value() - 1
            end_index = self.end_spinbox.value()
            if start_index >= end_index:
                self.log(self.tr("错误: 起始位置必须小于结束位置。"))
                return
            files_to_process = self.image_file_list[start_index:end_index]
            self.log(self.tr("范围: 从 {start} 到 {end}").format(start=start_index + 1, end=end_index))

        if not files_to_process:
            self.log(self.tr("错误: 没有找到要处理的文件。"))
            return

        self.log(self.tr("开始角度扶正..."))
        self.process_files(files_to_process, labels_to_process, target_angles, pos_tol, neg_tol, action='correct')

    def run_deletion(self):
        """Parse inputs and execute the angle deletion process."""
        self.log_widget.clear()
        
        # 1. Parse labels
        labels_to_process = {label.strip() for label in self.deletion_labels_input.text().split(',') if label.strip()}
        
        # 2. Parse target angles
        try:
            target_angles = [float(angle.strip()) for angle in self.deletion_target_angles_input.text().split(',') if angle.strip()]
            if not target_angles:
                self.log(self.tr("错误: 目标角度不能为空。"))
                return
        except ValueError:
            self.log(self.tr("错误: 目标角度包含无效数字。"))
            return

        # 3. Parse tolerances
        pos_tol = self.deletion_pos_tolerance_input.value()
        neg_tol = self.deletion_neg_tolerance_input.value()

        # 4. Determine scope
        scope_id = self.deletion_scope_group.checkedId()
        files_to_process = []
        if scope_id == 1: # Current page
            current_file = self.parent.filename
            if current_file:
                files_to_process.append(current_file)
            self.log(self.tr("范围: 仅当前页"))
        elif scope_id == 2: # All pages
            files_to_process = self.image_file_list
            self.log(self.tr("范围: 所有打开的页面"))
        else: # Specified range
            start_index = self.deletion_start_spinbox.value() - 1
            end_index = self.deletion_end_spinbox.value()
            if start_index >= end_index:
                self.log(self.tr("错误: 起始位置必须小于结束位置。"))
                return
            files_to_process = self.image_file_list[start_index:end_index]
            self.log(self.tr("范围: 从 {start} 到 {end}").format(start=start_index + 1, end=end_index))

        if not files_to_process:
            self.log(self.tr("错误: 没有找到要处理的文件。"))
            return

        self.log(self.tr("开始按角度删除..."))
        deletion_mode = self.deletion_mode_group.checkedId()
        self.process_files(files_to_process, labels_to_process, target_angles, pos_tol, neg_tol, action='delete', deletion_mode=deletion_mode)

    def process_files(self, files, labels_to_process, target_angles, pos_tol, neg_tol, action='correct', deletion_mode=1):
        """Process the files to correct angles or delete shapes."""
        total_processed = 0
        
        for image_file in files:
            label_dir, filename = os.path.split(image_file)
            if self.parent and self.parent.output_dir:
                label_dir = self.parent.output_dir
            
            label_file = os.path.join(label_dir, os.path.splitext(filename)[0] + ".json")

            if not os.path.exists(label_file):
                continue

            try:
                with open(label_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                original_shapes = data.get("shapes", [])
                shapes_to_keep = []
                made_change = False
                file_processed_count = 0

                for shape in original_shapes:
                    if shape.get("shape_type") != "rotation":
                        shapes_to_keep.append(shape)
                        continue
                    
                    if labels_to_process and shape.get("label") not in labels_to_process:
                        shapes_to_keep.append(shape)
                        continue

                    direction_rad = shape.get("direction", 0)
                    direction_deg = math.degrees(direction_rad) % 360

                    closest_target = min(target_angles, key=lambda x: angular_distance(direction_deg, x))

                    should_process = False
                    # Normalize the difference to be between -180 and 180
                    diff = direction_deg - closest_target
                    if diff > 180:
                        diff -= 360
                    if diff < -180:
                        diff += 360

                    # Check if the normalized difference falls within the tolerance
                    if diff >= 0 and diff <= pos_tol:
                        should_process = True
                    elif diff < 0 and abs(diff) <= neg_tol:
                        should_process = True

                    # Invert logic for deletion mode 1 (Delete Outside)
                    if action == 'delete' and deletion_mode == 1:
                        should_process = not should_process

                    if should_process:
                        made_change = True
                        file_processed_count += 1
                        if action == 'correct':
                            self.log(self.tr("标签 '{label}' 的形状角度从 {angle:.2f}° 扶正到 {target}° 。").format(
                                label=shape.get("label"), angle=direction_deg, target=closest_target
                            ))
                            
                            points = [QtCore.QPointF(p[0], p[1]) for p in shape["points"]]
                            if len(points) != 4: 
                                shapes_to_keep.append(shape)
                                continue
                            
                            from anylabeling.views.labeling import utils
                            center = (points[0] + points[2]) / 2.0
                            width = utils.distance(points[0] - points[1])
                            height = utils.distance(points[1] - points[2])

                            half_w, half_h = width / 2.0, height / 2.0
                            canonical_points = [
                                center + QtCore.QPointF(-half_w, -half_h),
                                center + QtCore.QPointF(half_w, -half_h),
                                center + QtCore.QPointF(half_w, half_h),
                                center + QtCore.QPointF(-half_w, half_h),
                            ]
                            
                            target_rad = math.radians(closest_target)
                            rotation_to_apply = -target_rad
                            new_points = []
                            for p in canonical_points:
                                rotated = rotate_point(p, center, rotation_to_apply)
                                new_points.append((rotated.x(), rotated.y()))

                            shape["points"] = new_points
                            shape["direction"] = target_rad
                            shapes_to_keep.append(shape)
                        
                        elif action == 'delete':
                            self.log(self.tr("标签 '{label}' 的形状 (角度: {angle:.2f}°) 已删除。").format(
                                label=shape.get("label"), angle=direction_deg
                            ))
                            # Do not append the shape to shapes_to_keep, effectively deleting it
                            pass

                    else:
                        shapes_to_keep.append(shape)

                if made_change:
                    data["shapes"] = shapes_to_keep
                    with open(label_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    
                    log_message = ""
                    if action == 'correct':
                        log_message = self.tr("文件 {file} 共扶正 {count} 个形状。")
                    elif action == 'delete':
                        log_message = self.tr("文件 {file} 共删除 {count} 个形状。")

                    self.log(log_message.format(
                        file=os.path.basename(image_file), count=file_processed_count
                    ))
                    total_processed += file_processed_count

            except Exception as e:
                self.log(f"处理文件 {label_file} 时出错: {e}")
                logger.error(f"处理文件 {label_file} 时出错: {e}")
                continue
        
        final_log_message = ""
        if action == 'correct':
            final_log_message = self.tr("角度扶正完成。共修正 {count} 个形状。")
        elif action == 'delete':
            final_log_message = self.tr("删除操作完成。共删除 {count} 个形状。")

        self.log(final_log_message.format(count=total_processed))
        
        # Reload current file if it was processed
        if self.parent.filename in files:
            self.parent.load_file(self.parent.filename)


        