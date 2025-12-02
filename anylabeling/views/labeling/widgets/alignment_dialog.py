# -*- encoding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore, QtGui
from datetime import datetime


class AlignmentButton(QtWidgets.QPushButton):
    """Custom button that emits different signals for left and right click."""

    left_clicked = QtCore.pyqtSignal()  # Left click: execute and exit
    right_clicked = QtCore.pyqtSignal()  # Right click: execute only

    def __init__(self, text, parent=None):
        super(AlignmentButton, self).__init__(text, parent)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.left_clicked.emit()
        elif event.button() == QtCore.Qt.RightButton:
            self.right_clicked.emit()
        # Call parent to maintain button visual feedback
        super(AlignmentButton, self).mousePressEvent(event)


class AlignmentDialog(QtWidgets.QDialog):
    """A non-modal dialog for aligning shapes."""

    # Signals now carry a boolean: True = auto exit, False = stay in mode
    align_left = QtCore.pyqtSignal(bool)
    align_h_center = QtCore.pyqtSignal(bool)
    align_right = QtCore.pyqtSignal(bool)
    align_top = QtCore.pyqtSignal(bool)
    align_v_center = QtCore.pyqtSignal(bool)
    align_bottom = QtCore.pyqtSignal(bool)
    unify_height = QtCore.pyqtSignal(bool)
    unify_width = QtCore.pyqtSignal(bool)
    unify_angle = QtCore.pyqtSignal(bool)
    
    # 指定尺寸信号: (标签, 宽度, 高度, 范围) 范围: "current", "selected", "range", "all"
    apply_specified_size = QtCore.pyqtSignal(str, int, int, str)
    # 指定尺寸范围信号: (标签, 宽度, 高度, 起始索引, 结束索引)
    apply_specified_size_range = QtCore.pyqtSignal(str, int, int, int, int)

    select_reference = QtCore.pyqtSignal(bool)
    reset_mode = QtCore.pyqtSignal()
    select_all_same_label = QtCore.pyqtSignal()
    closing = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super(AlignmentDialog, self).__init__(parent)
        self.setWindowTitle(self.tr("矩形对齐工具"))
        # 设置窗口标志：保持最小化按钮
        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.WindowTitleHint |
            QtCore.Qt.WindowSystemMenuHint |
            QtCore.Qt.WindowMinimizeButtonHint |
            QtCore.Qt.WindowCloseButtonHint
        )
        self.resize(400, 450)
        
        self.init_ui()
        


    def init_ui(self):
        """Initialize the user interface."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # Label Filter
        filter_layout = QtWidgets.QHBoxLayout()
        filter_layout.addWidget(QtWidgets.QLabel(self.tr("指定标签 (逗号分隔):")))
        self.label_filter_input = QtWidgets.QLineEdit("balloon, qipao, changfangtiao, other")
        self.label_filter_input.setPlaceholderText(self.tr("留空则处理所有标签"))
        filter_layout.addWidget(self.label_filter_input)
        main_layout.addLayout(filter_layout)

        # --- Control Buttons ---
        control_layout = QtWidgets.QHBoxLayout()
        self.select_ref_button = QtWidgets.QPushButton(self.tr("选择/重选参照物"))
        self.select_ref_button.setCheckable(True)
        
        self.select_same_button = QtWidgets.QPushButton(self.tr("选中同类"))

        self.exit_button = QtWidgets.QPushButton(self.tr("退出对齐模式"))

        # --- Styles ---
        button_height = 36
        button_min_width = 120

        toggle_style = """
            QPushButton {
                background-color: #0071e3; /* Default Blue */
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 500;
                min-width: %dpx;
                height: %dpx;
            }
            QPushButton:hover {
                background-color: #0077ED;
            }
            QPushButton:checked {
                background-color: #5cb85c; /* Active Green */
                color: white;
                border: 1px solid #4cae4c;
            }
            QPushButton:checked:hover {
                background-color: #62c462;
            }
        """ % (button_min_width, button_height)

        select_same_style = """
            QPushButton {
                background-color: #5bc0de;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 500;
                min-width: %dpx;
                height: %dpx;
            }
            QPushButton:hover {
                background-color: #46b8da;
            }
        """ % (button_min_width, button_height)

        danger_style = """
            QPushButton {
                background-color: #d9534f;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 500;
                min-width: %dpx;
                height: %dpx;
            }
            QPushButton:hover {
                background-color: #c9302c;
            }
        """ % (button_min_width, button_height)

        # Save default style for later reset
        self.default_button_style = toggle_style

        self.target_selection_style = """
            QPushButton {
                background-color: #f0ad4e; /* Orange */
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 500;
                min-width: %dpx;
                height: %dpx;
            }
            QPushButton:hover {
                background-color: #ec971f;
            }
        """ % (button_min_width, button_height)

        self.select_ref_button.setStyleSheet(toggle_style)
        self.select_same_button.setStyleSheet(select_same_style)
        self.exit_button.setStyleSheet(danger_style)

        control_layout.addWidget(self.select_ref_button)
        control_layout.addWidget(self.select_same_button)
        control_layout.addWidget(self.exit_button)
        main_layout.addLayout(control_layout)
        
        # --- Alignment buttons ---
        alignment_group = QtWidgets.QGroupBox(self.tr("对齐"))
        alignment_layout = QtWidgets.QGridLayout(alignment_group)

        tooltip_text = self.tr("左键: 执行后自动退出模式\n右键: 执行后保持模式")

        self.btn_align_left = AlignmentButton(self.tr("左对齐"))
        self.btn_align_left.setToolTip(tooltip_text)

        self.btn_align_h_center = AlignmentButton(self.tr("水平居中"))
        self.btn_align_h_center.setToolTip(tooltip_text)

        self.btn_align_right = AlignmentButton(self.tr("右对齐"))
        self.btn_align_right.setToolTip(tooltip_text)

        self.btn_align_top = AlignmentButton(self.tr("上对齐"))
        self.btn_align_top.setToolTip(tooltip_text)

        self.btn_align_v_center = AlignmentButton(self.tr("垂直居中"))
        self.btn_align_v_center.setToolTip(tooltip_text)

        self.btn_align_bottom = AlignmentButton(self.tr("下对齐"))
        self.btn_align_bottom.setToolTip(tooltip_text)

        alignment_layout.addWidget(self.btn_align_left, 0, 0)
        alignment_layout.addWidget(self.btn_align_h_center, 0, 1)
        alignment_layout.addWidget(self.btn_align_right, 0, 2)
        alignment_layout.addWidget(self.btn_align_top, 1, 0)
        alignment_layout.addWidget(self.btn_align_v_center, 1, 1)
        alignment_layout.addWidget(self.btn_align_bottom, 1, 2)
        main_layout.addWidget(alignment_group)

        # --- Unify Size buttons ---
        unify_group = QtWidgets.QGroupBox(self.tr("统一尺寸"))
        unify_layout = QtWidgets.QVBoxLayout(unify_group)

        # 统一高度和宽度按钮
        unify_buttons_layout = QtWidgets.QHBoxLayout()
        self.btn_unify_height = AlignmentButton(self.tr("统一高度"))
        self.btn_unify_height.setToolTip(tooltip_text)

        self.btn_unify_width = AlignmentButton(self.tr("统一宽度"))
        self.btn_unify_width.setToolTip(tooltip_text)

        unify_buttons_layout.addWidget(self.btn_unify_height)
        unify_buttons_layout.addWidget(self.btn_unify_width)
        unify_layout.addLayout(unify_buttons_layout)

        # 统一角度专用区域
        angle_layout = QtWidgets.QHBoxLayout()
        angle_layout.addWidget(QtWidgets.QLabel(self.tr("旋转标签:")))
        self.angle_label_input = QtWidgets.QLineEdit("shuqing, hengxie")
        self.angle_label_input.setPlaceholderText(self.tr("统一角度时只处理这些标签"))
        self.angle_label_input.setToolTip(self.tr("统一角度时只处理这些标签的旋转矩形"))
        angle_layout.addWidget(self.angle_label_input)

        self.btn_unify_angle = AlignmentButton(self.tr("统一角度"))
        self.btn_unify_angle.setToolTip(tooltip_text)
        angle_layout.addWidget(self.btn_unify_angle)

        unify_layout.addLayout(angle_layout)
        
        # 分隔线
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        unify_layout.addWidget(separator)
        
        # 指定尺寸区域
        size_label_layout = QtWidgets.QHBoxLayout()
        size_label_layout.addWidget(QtWidgets.QLabel(self.tr("标签:")))
        self.size_label_input = QtWidgets.QLineEdit()
        self.size_label_input.setPlaceholderText(self.tr("输入要调整的标签名"))
        size_label_layout.addWidget(self.size_label_input)
        unify_layout.addLayout(size_label_layout)
        
        size_input_layout = QtWidgets.QHBoxLayout()
        size_input_layout.setSpacing(3)  # 减小间距
        width_label = QtWidgets.QLabel(self.tr("宽:"))
        width_label.setFixedWidth(22)
        size_input_layout.addWidget(width_label)
        self.size_width_input = QtWidgets.QSpinBox()
        self.size_width_input.setRange(0, 9999)
        self.size_width_input.setValue(0)
        self.size_width_input.setSpecialValueText(self.tr("不变"))
        self.size_width_input.setToolTip(self.tr("0表示不修改宽度"))
        size_input_layout.addWidget(self.size_width_input)
        
        size_input_layout.addSpacing(8)
        height_label = QtWidgets.QLabel(self.tr("高:"))
        height_label.setFixedWidth(22)
        size_input_layout.addWidget(height_label)
        self.size_height_input = QtWidgets.QSpinBox()
        self.size_height_input.setRange(0, 9999)
        self.size_height_input.setValue(0)
        self.size_height_input.setSpecialValueText(self.tr("不变"))
        self.size_height_input.setToolTip(self.tr("0表示不修改高度"))
        size_input_layout.addWidget(self.size_height_input)
        
        # 范围选择放在同一行
        size_input_layout.addSpacing(15)
        from_label = QtWidgets.QLabel(self.tr("从:"))
        from_label.setFixedWidth(22)
        size_input_layout.addWidget(from_label)
        self.size_start_spinbox = QtWidgets.QSpinBox()
        self.size_start_spinbox.setRange(1, 9999)
        self.size_start_spinbox.setValue(1)
        size_input_layout.addWidget(self.size_start_spinbox)
        
        size_input_layout.addSpacing(8)
        to_label = QtWidgets.QLabel(self.tr("到:"))
        to_label.setFixedWidth(22)
        size_input_layout.addWidget(to_label)
        self.size_end_spinbox = QtWidgets.QSpinBox()
        self.size_end_spinbox.setRange(1, 9999)
        self.size_end_spinbox.setValue(1)
        size_input_layout.addWidget(self.size_end_spinbox)
        size_input_layout.addStretch()
        unify_layout.addLayout(size_input_layout)
        
        # 应用按钮
        apply_size_layout = QtWidgets.QHBoxLayout()
        self.btn_apply_size_current = QtWidgets.QPushButton(self.tr("本页"))
        self.btn_apply_size_selected = QtWidgets.QPushButton(self.tr("选中"))
        self.btn_apply_size_range = QtWidgets.QPushButton(self.tr("范围"))
        self.btn_apply_size_all = QtWidgets.QPushButton(self.tr("全部"))
        
        apply_btn_style = """
            QPushButton {
                background-color: #5cb85c;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px 12px;
            }
            QPushButton:hover {
                background-color: #4cae4c;
            }
        """
        range_btn_style = apply_btn_style.replace("#5cb85c", "#5bc0de").replace("#4cae4c", "#46b8da")
        all_btn_style = apply_btn_style.replace("#5cb85c", "#f0ad4e").replace("#4cae4c", "#ec971f")
        
        self.btn_apply_size_current.setStyleSheet(apply_btn_style)
        self.btn_apply_size_selected.setStyleSheet(apply_btn_style)
        self.btn_apply_size_range.setStyleSheet(range_btn_style)
        self.btn_apply_size_all.setStyleSheet(all_btn_style)
        
        apply_size_layout.addWidget(self.btn_apply_size_current)
        apply_size_layout.addWidget(self.btn_apply_size_selected)
        apply_size_layout.addWidget(self.btn_apply_size_range)
        apply_size_layout.addWidget(self.btn_apply_size_all)
        unify_layout.addLayout(apply_size_layout)
        
        main_layout.addWidget(unify_group)

        # --- Log GroupBox ---
        log_group = QtWidgets.QGroupBox(self.tr("日志"))
        log_layout = QtWidgets.QVBoxLayout(log_group)
        self.log_widget = QtWidgets.QTextEdit()
        self.log_widget.setReadOnly(True)
        log_layout.addWidget(self.log_widget)
        main_layout.addWidget(log_group)
        
        # --- Connect signals ---
        self.select_ref_button.toggled.connect(self.set_reference_mode)
        self.exit_button.clicked.connect(self._on_exit_alignment_mode)
        self.select_same_button.clicked.connect(self.select_all_same_label.emit)

        # Connect alignment buttons: left click = auto exit, right click = stay
        self.btn_align_left.left_clicked.connect(lambda: self.align_left.emit(True))
        self.btn_align_left.right_clicked.connect(lambda: self.align_left.emit(False))

        self.btn_align_h_center.left_clicked.connect(lambda: self.align_h_center.emit(True))
        self.btn_align_h_center.right_clicked.connect(lambda: self.align_h_center.emit(False))

        self.btn_align_right.left_clicked.connect(lambda: self.align_right.emit(True))
        self.btn_align_right.right_clicked.connect(lambda: self.align_right.emit(False))

        self.btn_align_top.left_clicked.connect(lambda: self.align_top.emit(True))
        self.btn_align_top.right_clicked.connect(lambda: self.align_top.emit(False))

        self.btn_align_v_center.left_clicked.connect(lambda: self.align_v_center.emit(True))
        self.btn_align_v_center.right_clicked.connect(lambda: self.align_v_center.emit(False))

        self.btn_align_bottom.left_clicked.connect(lambda: self.align_bottom.emit(True))
        self.btn_align_bottom.right_clicked.connect(lambda: self.align_bottom.emit(False))

        # Connect unify buttons: left click = auto exit, right click = stay
        self.btn_unify_height.left_clicked.connect(lambda: self.unify_height.emit(True))
        self.btn_unify_height.right_clicked.connect(lambda: self.unify_height.emit(False))

        self.btn_unify_width.left_clicked.connect(lambda: self.unify_width.emit(True))
        self.btn_unify_width.right_clicked.connect(lambda: self.unify_width.emit(False))

        self.btn_unify_angle.left_clicked.connect(lambda: self.unify_angle.emit(True))
        self.btn_unify_angle.right_clicked.connect(lambda: self.unify_angle.emit(False))
        
        # Connect specified size buttons
        self.btn_apply_size_current.clicked.connect(lambda: self._emit_apply_size("current"))
        self.btn_apply_size_selected.clicked.connect(lambda: self._emit_apply_size("selected"))
        self.btn_apply_size_range.clicked.connect(self._emit_apply_size_range)
        self.btn_apply_size_all.clicked.connect(lambda: self._emit_apply_size("all"))

    def _emit_apply_size(self, scope):
        """发送指定尺寸信号"""
        label = self.size_label_input.text().strip()
        if not label:
            self.log(self.tr("请输入标签名"))
            return
        width = self.size_width_input.value()
        height = self.size_height_input.value()
        if width == 0 and height == 0:
            self.log(self.tr("宽度和高度不能都为0"))
            return
        self.apply_specified_size.emit(label, width, height, scope)

    def _emit_apply_size_range(self):
        """发送指定尺寸范围信号"""
        label = self.size_label_input.text().strip()
        if not label:
            self.log(self.tr("请输入标签名"))
            return
        width = self.size_width_input.value()
        height = self.size_height_input.value()
        if width == 0 and height == 0:
            self.log(self.tr("宽度和高度不能都为0"))
            return
        start = self.size_start_spinbox.value() - 1  # 转为0索引
        end = self.size_end_spinbox.value() - 1
        if start > end:
            self.log(self.tr("起始位置不能大于结束位置"))
            return
        self.apply_specified_size_range.emit(label, width, height, start, end)

    def _on_exit_alignment_mode(self):
        """Handle exit alignment mode button click."""
        self.log(self.tr("已退出对齐模式，所有状态已重置。鼠标可以移动矩形了"))
        self.reset_mode.emit()
        # Reset button to default style and text
        self.select_ref_button.setStyleSheet(self.default_button_style)
        self.select_ref_button.setText(self.tr("选择/重选参照物"))
        self.select_ref_button.setChecked(False)

    def set_button_to_target_selection_mode(self):
        """Set the reference selection button to indicate waiting for target selection."""
        self.select_ref_button.setStyleSheet(self.target_selection_style)
        self.select_ref_button.setText(self.tr("请选择要对齐的矩形"))
        self.select_ref_button.setChecked(False) # Ensure it's not in 'checked' green state

    def set_reference_mode(self, is_active):
        if is_active:
            self.select_ref_button.setText(self.tr("请选择参照"))
            self.log(self.tr("已进入参照物选择模式，已禁用鼠标移动矩形"))
        else:
            self.select_ref_button.setText(self.tr("选择/重选参照物"))
            self.select_ref_button.setChecked(False)
            # Back to default blue style when leaving selection mode
            self.select_ref_button.setStyleSheet(self.default_button_style)
        self.select_reference.emit(is_active)

    def log(self, message):
        """Append a message to the log widget with a timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_widget.append(f"[{timestamp}] {message}")

    def get_angle_target_labels(self):
        """获取统一角度专用的目标标签列表"""
        text = self.angle_label_input.text().strip()
        if not text:
            return set()
        return {label.strip() for label in text.split(',') if label.strip()}

    def update_page_range(self, current_page, total_pages):
        """更新范围选择的页码范围"""
        if total_pages > 0:
            self.size_start_spinbox.setRange(1, total_pages)
            self.size_end_spinbox.setRange(1, total_pages)
            self.size_start_spinbox.setValue(current_page)
            self.size_end_spinbox.setValue(total_pages)

    def closeEvent(self, event):
        """Emit a closing signal when the dialog is closed."""
        self.closing.emit()
        super(AlignmentDialog, self).closeEvent(event)
