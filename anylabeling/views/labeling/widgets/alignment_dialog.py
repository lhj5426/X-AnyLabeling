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

    select_reference = QtCore.pyqtSignal(bool)
    reset_mode = QtCore.pyqtSignal()
    select_all_same_label = QtCore.pyqtSignal()
    closing = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super(AlignmentDialog, self).__init__(parent)
        self.setWindowTitle(self.tr("矩形对齐工具"))
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint | QtCore.Qt.WindowMinimizeButtonHint)
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

    def closeEvent(self, event):
        """Emit a closing signal when the dialog is closed."""
        self.closing.emit()
        super(AlignmentDialog, self).closeEvent(event)
