# -*- encoding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore, QtGui
from datetime import datetime
import os.path as osp
import yaml


def _load_split_settings():
    """从用户配置文件加载分割工具设置"""
    from ....config import USER_CONFIG_FILE
    config_file = USER_CONFIG_FILE
    try:
        if osp.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
                return config.get("text_split_settings", {})
    except Exception:
        pass
    return {}


def _save_split_settings(settings):
    """保存分割工具设置到用户配置文件"""
    from ....config import USER_CONFIG_FILE
    config_file = USER_CONFIG_FILE
    try:
        existing = {}
        if osp.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
        existing["text_split_settings"] = settings
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(existing, f, allow_unicode=True)
    except Exception:
        pass


class SegmentationDialog(QtWidgets.QDialog):
    """A non-modal dialog for splitting rectangles."""

    # Signals for mode changes
    enter_vertical_cut_mode = QtCore.pyqtSignal()
    enter_horizontal_cut_mode = QtCore.pyqtSignal()
    exit_segmentation_mode = QtCore.pyqtSignal()

    # Signal when a split is completed
    split_completed = QtCore.pyqtSignal(str)  # Message to log

    # Signals for crosshair length changes
    horizontal_length_changed = QtCore.pyqtSignal(int)  # Horizontal line length
    vertical_length_changed = QtCore.pyqtSignal(int)  # Vertical line length

    closing = QtCore.pyqtSignal()

    # Auto-split signals
    auto_split_selected = QtCore.pyqtSignal(dict)
    auto_split_page = QtCore.pyqtSignal(dict)
    auto_split_range = QtCore.pyqtSignal(int, int, dict)

    def __init__(self, parent=None, shortcut_key=None):
        super(SegmentationDialog, self).__init__(parent)
        self.setWindowTitle(self.tr("矩形分割工具"))
        self.setWindowFlags(
            self.windowFlags()
            & ~QtCore.Qt.WindowContextHelpButtonHint
            | QtCore.Qt.WindowMinimizeButtonHint
        )
        # 设置为非模态窗口，这样主窗口可以接收快捷键
        self.setModal(False)
        self.resize(400, 500)

        self.current_mode = None  # 'vertical', 'horizontal', or None

        self.init_ui()
        self._load_split_settings()

        # 注意：不再在对话框内部创建快捷键，由主窗口的 ApplicationShortcut 统一处理
        # 这样无论焦点在哪里，快捷键都能正常触发 toggle 逻辑

        # Restore window position from last session
        self.restore_window_position()

    def init_ui(self):
        """Initialize the user interface."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # Instructions
        instructions = QtWidgets.QLabel(
            self.tr(
                "左键【单独分割】 右键【分割线内全部】\n"
                "中键【退出分割模式】\n"
                "分割模式下 按【大键盘区】数字键1和2可切换垂直/水平模式"
            )
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("padding: 10px; background-color: #f0f0f0; border-radius: 5px;")
        main_layout.addWidget(instructions)

        # Mode buttons
        mode_group = QtWidgets.QGroupBox(self.tr("分割模式"))
        mode_layout = QtWidgets.QVBoxLayout()

        # Button styles
        button_height = 40
        button_style = """
            QPushButton {
                background-color: #0071e3;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 500;
                font-size: 13px;
                height: %dpx;
            }
            QPushButton:hover {
                background-color: #0077ED;
            }
            QPushButton:checked {
                background-color: #5cb85c;
                color: white;
                border: 2px solid #4cae4c;
            }
            QPushButton:checked:hover {
                background-color: #62c462;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """ % button_height

        exit_button_style = """
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 500;
                font-size: 13px;
                height: %dpx;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """ % button_height

        # Vertical cut button
        self.vertical_button = QtWidgets.QPushButton(self.tr("1. 垂直分割模式"))
        self.vertical_button.setCheckable(True)
        self.vertical_button.setStyleSheet(button_style)
        self.vertical_button.clicked.connect(self.on_vertical_mode)
        mode_layout.addWidget(self.vertical_button)

        # Horizontal cut button
        self.horizontal_button = QtWidgets.QPushButton(self.tr("2. 水平分割模式"))
        self.horizontal_button.setCheckable(True)
        self.horizontal_button.setStyleSheet(button_style)
        self.horizontal_button.clicked.connect(self.on_horizontal_mode)
        mode_layout.addWidget(self.horizontal_button)

        # Exit button
        self.exit_button = QtWidgets.QPushButton(self.tr("3. 退出分割模式"))
        self.exit_button.setStyleSheet(exit_button_style)
        self.exit_button.clicked.connect(self._exit_button_clicked)
        mode_layout.addWidget(self.exit_button)

        mode_group.setLayout(mode_layout)
        main_layout.addWidget(mode_group)

        # Crosshair length adjustment
        length_group = QtWidgets.QGroupBox(self.tr("十字线长度调整"))
        length_layout = QtWidgets.QHBoxLayout()
        length_layout.setSpacing(15)

        # Horizontal line length
        h_layout = QtWidgets.QHBoxLayout()
        h_label = QtWidgets.QLabel(self.tr("横向长度:"))
        self.horizontal_length_spinbox = QtWidgets.QSpinBox()
        self.horizontal_length_spinbox.setRange(50, 5000)
        self.horizontal_length_spinbox.setValue(2000)
        self.horizontal_length_spinbox.setMaximumWidth(100)
        self.horizontal_length_spinbox.setToolTip(self.tr("调整横向十字线的长度，用于控制批量切割范围"))
        self.horizontal_length_spinbox.valueChanged.connect(self.on_horizontal_length_changed)
        h_layout.addWidget(h_label)
        h_layout.addWidget(self.horizontal_length_spinbox)
        length_layout.addLayout(h_layout)

        # Vertical line length
        v_layout = QtWidgets.QHBoxLayout()
        v_label = QtWidgets.QLabel(self.tr("纵向长度:"))
        self.vertical_length_spinbox = QtWidgets.QSpinBox()
        self.vertical_length_spinbox.setRange(50, 5000)
        self.vertical_length_spinbox.setValue(2000)
        self.vertical_length_spinbox.setMaximumWidth(100)
        self.vertical_length_spinbox.setToolTip(self.tr("调整纵向十字线的长度，用于控制批量切割范围"))
        self.vertical_length_spinbox.valueChanged.connect(self.on_vertical_length_changed)
        v_layout.addWidget(v_label)
        v_layout.addWidget(self.vertical_length_spinbox)
        length_layout.addLayout(v_layout)

        length_group.setLayout(length_layout)
        main_layout.addWidget(length_group)

        # Current mode display
        self.mode_label = QtWidgets.QLabel(self.tr("当前模式: 未激活"))
        self.mode_label.setAlignment(QtCore.Qt.AlignCenter)
        self.mode_label.setStyleSheet(
            "padding: 8px; background-color: #e9ecef; "
            "border-radius: 5px; font-weight: bold; font-size: 12px;"
        )
        main_layout.addWidget(self.mode_label)

        # Auto-split section
        auto_group = QtWidgets.QGroupBox(self.tr("智能行分割（无需手动划线）"))
        auto_layout = QtWidgets.QVBoxLayout()

        # Row 1: checkbox + range spinboxes
        row1 = QtWidgets.QHBoxLayout()
        self.cb_keep_original = QtWidgets.QCheckBox(self.tr("保留原始框"))
        self.cb_keep_original.setChecked(True)
        row1.addWidget(self.cb_keep_original)
        row1.addSpacing(10)
        row1.addWidget(QtWidgets.QLabel(self.tr("从")))
        self.spin_start = QtWidgets.QSpinBox()
        self.spin_start.setRange(1, 9999)
        self.spin_start.setValue(1)
        self.spin_start.setFixedWidth(55)
        row1.addWidget(self.spin_start)
        row1.addWidget(QtWidgets.QLabel(self.tr("到")))
        self.spin_end = QtWidgets.QSpinBox()
        self.spin_end.setRange(1, 9999)
        self.spin_end.setValue(1)
        self.spin_end.setFixedWidth(55)
        row1.addWidget(self.spin_end)
        row1.addStretch()
        auto_layout.addLayout(row1)

        # Label filter row (指定标签，仅对匹配标签的矩形做行分割)
        label_row = QtWidgets.QHBoxLayout()
        label_row.addWidget(QtWidgets.QLabel(self.tr("指定标签:")))
        self.split_label_filter = QtWidgets.QLineEdit()
        self.split_label_filter.setPlaceholderText(self.tr("逗号分隔, 留空=全部分割"))
        label_row.addWidget(self.split_label_filter)
        auto_layout.addLayout(label_row)

        # Row 2: action buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)

        btn_style_green = """
            QPushButton {
                background-color: #5cb85c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 0px;
            }
            QPushButton:hover {
                background-color: #4cae4c;
            }
        """
        btn_style_blue = """
            QPushButton {
                background-color: #5bc0de;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 0px;
            }
            QPushButton:hover {
                background-color: #46b8da;
            }
        """

        self.btn_auto_selected = QtWidgets.QPushButton(self.tr("分割选中"))
        self.btn_auto_selected.setStyleSheet(btn_style_green)
        self.btn_auto_selected.clicked.connect(self._on_auto_selected)
        btn_row.addWidget(self.btn_auto_selected, 1)

        self.btn_auto_page = QtWidgets.QPushButton(self.tr("分割本页"))
        self.btn_auto_page.setStyleSheet(btn_style_green)
        self.btn_auto_page.clicked.connect(self._on_auto_page)
        btn_row.addWidget(self.btn_auto_page, 1)

        self.btn_auto_range = QtWidgets.QPushButton(self.tr("分割范围"))
        self.btn_auto_range.setStyleSheet(btn_style_blue)
        self.btn_auto_range.clicked.connect(self._on_auto_range)
        btn_row.addWidget(self.btn_auto_range, 1)

        auto_layout.addLayout(btn_row)

        auto_group.setLayout(auto_layout)
        main_layout.addWidget(auto_group)

        # Log area
        log_group = QtWidgets.QGroupBox(self.tr("操作日志"))
        log_layout = QtWidgets.QVBoxLayout()
        
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        
        # Clear log button
        clear_log_btn = QtWidgets.QPushButton(self.tr("清空日志"))
        clear_log_btn.clicked.connect(self.log_text.clear)
        log_layout.addWidget(clear_log_btn)
        
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

        main_layout.addStretch()

        # Initial log message
        self.log_message(self.tr("矩形分割工具已打开，请选择分割模式。"))

    def on_vertical_mode(self):
        """Handle vertical cut mode activation."""
        if self.vertical_button.isChecked():
            self.horizontal_button.setChecked(False)
            self.current_mode = 'vertical'
            self.mode_label.setText(self.tr("当前模式: 垂直分割"))
            self.mode_label.setStyleSheet(
                "padding: 8px; background-color: #d4edda; "
                "border-radius: 5px; font-weight: bold; font-size: 12px; color: #155724;"
            )
            self.log_message(self.tr("垂直分割模式"))
            self.enter_vertical_cut_mode.emit()
        else:
            self.current_mode = None
            self.mode_label.setText(self.tr("当前模式: 未激活"))
            self.mode_label.setStyleSheet(
                "padding: 8px; background-color: #e9ecef; "
                "border-radius: 5px; font-weight: bold; font-size: 12px;"
            )
            self.log_message(self.tr("已退出垂直分割模式。"))
            self.exit_segmentation_mode.emit()

    def on_horizontal_mode(self):
        """Handle horizontal cut mode activation."""
        if self.horizontal_button.isChecked():
            self.vertical_button.setChecked(False)
            self.current_mode = 'horizontal'
            self.mode_label.setText(self.tr("当前模式: 水平分割"))
            self.mode_label.setStyleSheet(
                "padding: 8px; background-color: #d1ecf1; "
                "border-radius: 5px; font-weight: bold; font-size: 12px; color: #0c5460;"
            )
            self.log_message(self.tr("水平分割模式"))
            self.enter_horizontal_cut_mode.emit()
        else:
            self.current_mode = None
            self.mode_label.setText(self.tr("当前模式: 未激活"))
            self.mode_label.setStyleSheet(
                "padding: 8px; background-color: #e9ecef; "
                "border-radius: 5px; font-weight: bold; font-size: 12px;"
            )
            self.log_message(self.tr("已退出水平分割模式。"))
            self.exit_segmentation_mode.emit()

    def on_exit_mode(self):
        """Handle exit mode."""
        self.vertical_button.setChecked(False)
        self.horizontal_button.setChecked(False)
        self.current_mode = None
        self.mode_label.setText(self.tr("当前模式: 未激活"))
        self.mode_label.setStyleSheet(
            "padding: 8px; background-color: #e9ecef; "
            "border-radius: 5px; font-weight: bold; font-size: 12px;"
        )
        self.exit_segmentation_mode.emit()

    def _exit_button_clicked(self):
        """退出按钮：打日志后退出"""
        self.log_message(self.tr("已退出分割模式。"))
        self.on_exit_mode()

    def on_horizontal_length_changed(self, value):
        """Handle horizontal line length change."""
        self.horizontal_length_changed.emit(value)
        self.log_message(self.tr(f"横向十字线长度已调整为: {value} px"))

    def on_vertical_length_changed(self, value):
        """Handle vertical line length change."""
        self.vertical_length_changed.emit(value)
        self.log_message(self.tr(f"纵向十字线长度已调整为: {value} px"))

    def log_message(self, message):
        """Add a message to the log with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        # Auto scroll to bottom
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def update_shortcut(self, shortcut_key):
        """Update the close shortcut key.

        Args:
            shortcut_key: New shortcut key string (e.g., "Ctrl+Shift+X")
        
        注意：不再在对话框内部创建快捷键，由主窗口的 ApplicationShortcut 统一处理。
        这个方法保留是为了兼容性，但不再执行任何操作。
        """
        # 移除旧的内部快捷键（如果存在）
        if hasattr(self, 'close_shortcut'):
            self.close_shortcut.setKey(QtGui.QKeySequence())  # 清空快捷键
            self.close_shortcut.deleteLater()
            delattr(self, 'close_shortcut')

    def restore_window_position(self):
        """Restore window position and size from settings."""
        settings = QtCore.QSettings()
        geometry = settings.value("segmentation_dialog/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        else:
            # Default position if no settings are found (center of parent)
            if self.parent():
                parent_geometry = self.parent().geometry()
                x = parent_geometry.x() + (parent_geometry.width() - self.width()) // 2
                y = parent_geometry.y() + (parent_geometry.height() - self.height()) // 2
                self.move(x, y)

    def save_window_position(self):
        """Save current window position and size to settings."""
        settings = QtCore.QSettings()
        settings.setValue("segmentation_dialog/geometry", self.saveGeometry())

    def closeEvent(self, event):
        """Handle dialog close event."""
        # Save window position before closing
        self.save_window_position()
        self._save_split_settings()
        # Exit mode when closing
        if self.current_mode:
            self.on_exit_mode()
        self.closing.emit()
        event.accept()

    def hideEvent(self, event):
        """Handle the window hide event."""
        self.save_window_position()
        self._save_split_settings()
        super(SegmentationDialog, self).hideEvent(event)


    def keyPressEvent(self, event):
        """Handle key press events for mode switching."""
        key = event.key()
        # 数字键1切换到垂直分割模式
        if key == QtCore.Qt.Key_1:
            if self.current_mode != 'vertical':
                self.vertical_button.setChecked(True)
                self.horizontal_button.setChecked(False)
                self.on_vertical_mode()
            event.accept()
            return
        # 数字键2切换到水平分割模式
        elif key == QtCore.Qt.Key_2:
            if self.current_mode != 'horizontal':
                self.horizontal_button.setChecked(True)
                self.vertical_button.setChecked(False)
                self.on_horizontal_mode()
            event.accept()
            return
        super(SegmentationDialog, self).keyPressEvent(event)

    def _options(self):
        return {
            "keep_original": self.cb_keep_original.isChecked(),
            "target_labels": self.split_label_filter.text(),
        }

    def get_options(self):
        """公开方法：供外部自动调用时读取当前分割选项（target_labels 等）"""
        return self._options()

    def _on_auto_selected(self):
        self.auto_split_selected.emit(self._options())

    def _on_auto_page(self):
        self.auto_split_page.emit(self._options())

    def _on_auto_range(self):
        start = self.spin_start.value()
        end = self.spin_end.value()
        if start > end:
            start, end = end, start
        self.auto_split_range.emit(start, end, self._options())

    def update_page_range(self, current_page, total_pages):
        """更新范围选择的页码"""
        if total_pages > 0:
            self.spin_start.setRange(1, total_pages)
            self.spin_end.setRange(1, total_pages)
            self.spin_start.setValue(current_page)
            self.spin_end.setValue(total_pages)

    def log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {msg}")

    def _load_split_settings(self):
        """从配置文件加载分割工具设置"""
        settings = _load_split_settings()
        if settings:
            if "target_labels" in settings:
                self.split_label_filter.setText(settings["target_labels"])

    def _save_split_settings(self):
        """保存分割工具设置到配置文件"""
        settings = {
            "target_labels": self.split_label_filter.text(),
        }
        _save_split_settings(settings)
