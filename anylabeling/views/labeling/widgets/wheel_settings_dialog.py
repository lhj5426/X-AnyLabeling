# -*- encoding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore, QtGui


class WheelSettingsDialog(QtWidgets.QDialog):
    """Dialog for configuring mouse wheel rectangle editing settings."""

    def __init__(self, parent=None, config=None):
        super(WheelSettingsDialog, self).__init__(parent)
        self.parent = parent
        self._config = config if config is not None else {}
        # Read from canvas.wheel_rectangle_editing, not root level
        self.wheel_settings = self._config.get("canvas", {}).get("wheel_rectangle_editing", {})

        self.setWindowTitle(self.tr("鼠标滚轮设置"))
        self.setWindowFlags(
            self.windowFlags()
            & ~QtCore.Qt.WindowContextHelpButtonHint
            | QtCore.Qt.WindowMinimizeButtonHint
        )
        # 紧凑的窗口大小
        self.setMinimumWidth(180)
        self.setMaximumWidth(200)

        self.init_ui()
        self.load_settings()
        self.restore_window_position()

    def init_ui(self):
        """Initialize the user interface."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Instructions
        instructions = QtWidgets.QLabel(self.tr("调整实时生效"))
        instructions.setStyleSheet("padding: 4px; background-color: #e8f4f8; border-radius: 3px; font-size: 9pt;")
        main_layout.addWidget(instructions)

        # Settings layout (no scroll area needed)
        settings_layout = QtWidgets.QVBoxLayout()
        settings_layout.setSpacing(5)

        # === 边界调整设置 ===
        edge_group = QtWidgets.QGroupBox(self.tr("边界调整（鼠标在矩形外部）"))
        edge_layout = QtWidgets.QVBoxLayout()
        edge_layout.setSpacing(3)
        edge_layout.setContentsMargins(6, 6, 6, 6)

        # Normal adjustment
        normal_label = QtWidgets.QLabel(self.tr("普通滚轮（微调）"))
        normal_label.setStyleSheet("font-weight: bold; color: #0071e3; font-size: 9pt;")
        edge_layout.addWidget(normal_label)
        
        normal_h_layout = QtWidgets.QHBoxLayout()
        normal_h_layout.addWidget(QtWidgets.QLabel(self.tr("水平边界调整：")))
        self.adjust_step_h_spinbox = QtWidgets.QDoubleSpinBox()
        self.adjust_step_h_spinbox.setRange(0.1, 100.0)
        self.adjust_step_h_spinbox.setSingleStep(0.5)
        self.adjust_step_h_spinbox.setValue(1.0)
        self.adjust_step_h_spinbox.setMaximumWidth(70)
        self.adjust_step_h_spinbox.valueChanged.connect(self.on_value_changed)
        normal_h_layout.addWidget(self.adjust_step_h_spinbox)
        normal_h_layout.addWidget(QtWidgets.QLabel(self.tr("像素")))
        normal_h_layout.addSpacing(5)
        normal_h_layout.addStretch()
        edge_layout.addLayout(normal_h_layout)

        normal_v_layout = QtWidgets.QHBoxLayout()
        normal_v_layout.addWidget(QtWidgets.QLabel(self.tr("垂直边界调整：")))
        self.adjust_step_v_spinbox = QtWidgets.QDoubleSpinBox()
        self.adjust_step_v_spinbox.setRange(0.1, 100.0)
        self.adjust_step_v_spinbox.setSingleStep(0.5)
        self.adjust_step_v_spinbox.setValue(1.0)
        self.adjust_step_v_spinbox.setMaximumWidth(70)
        self.adjust_step_v_spinbox.valueChanged.connect(self.on_value_changed)
        normal_v_layout.addWidget(self.adjust_step_v_spinbox)
        normal_v_layout.addWidget(QtWidgets.QLabel(self.tr("像素")))
        normal_v_layout.addSpacing(5)
        normal_v_layout.addStretch()
        edge_layout.addLayout(normal_v_layout)

        edge_layout.addSpacing(4)

        # Shift adjustment
        shift_label = QtWidgets.QLabel(self.tr("Shift+滚轮（大幅微调）"))
        shift_label.setStyleSheet("font-weight: bold; color: #5cb85c; font-size: 9pt;")
        edge_layout.addWidget(shift_label)

        shift_h_layout = QtWidgets.QHBoxLayout()
        shift_h_layout.addWidget(QtWidgets.QLabel(self.tr("水平边界调整：")))
        self.shift_adjust_step_h_spinbox = QtWidgets.QDoubleSpinBox()
        self.shift_adjust_step_h_spinbox.setRange(0.1, 100.0)
        self.shift_adjust_step_h_spinbox.setSingleStep(0.5)
        self.shift_adjust_step_h_spinbox.setValue(5.0)
        self.shift_adjust_step_h_spinbox.setMaximumWidth(70)
        self.shift_adjust_step_h_spinbox.valueChanged.connect(self.on_value_changed)
        shift_h_layout.addWidget(self.shift_adjust_step_h_spinbox)
        shift_h_layout.addWidget(QtWidgets.QLabel(self.tr("像素")))
        shift_h_layout.addSpacing(5)
        shift_h_layout.addStretch()
        edge_layout.addLayout(shift_h_layout)

        shift_v_layout = QtWidgets.QHBoxLayout()
        shift_v_layout.addWidget(QtWidgets.QLabel(self.tr("垂直边界调整：")))
        self.shift_adjust_step_v_spinbox = QtWidgets.QDoubleSpinBox()
        self.shift_adjust_step_v_spinbox.setRange(0.1, 100.0)
        self.shift_adjust_step_v_spinbox.setSingleStep(0.5)
        self.shift_adjust_step_v_spinbox.setValue(5.0)
        self.shift_adjust_step_v_spinbox.setMaximumWidth(70)
        self.shift_adjust_step_v_spinbox.valueChanged.connect(self.on_value_changed)
        shift_v_layout.addWidget(self.shift_adjust_step_v_spinbox)
        shift_v_layout.addWidget(QtWidgets.QLabel(self.tr("像素")))
        shift_v_layout.addSpacing(5)
        shift_v_layout.addStretch()
        edge_layout.addLayout(shift_v_layout)

        edge_layout.addSpacing(4)

        # Fast adjustment
        fast_label = QtWidgets.QLabel(self.tr("Ctrl+滚轮（快速调整）"))
        fast_label.setStyleSheet("font-weight: bold; color: #d9534f; font-size: 9pt;")
        edge_layout.addWidget(fast_label)

        fast_h_layout = QtWidgets.QHBoxLayout()
        fast_h_layout.addWidget(QtWidgets.QLabel(self.tr("水平边界调整：")))
        self.fast_adjust_step_h_spinbox = QtWidgets.QDoubleSpinBox()
        self.fast_adjust_step_h_spinbox.setRange(0.1, 100.0)
        self.fast_adjust_step_h_spinbox.setSingleStep(0.5)
        self.fast_adjust_step_h_spinbox.setValue(10.0)
        self.fast_adjust_step_h_spinbox.setMaximumWidth(70)
        self.fast_adjust_step_h_spinbox.valueChanged.connect(self.on_value_changed)
        fast_h_layout.addWidget(self.fast_adjust_step_h_spinbox)
        fast_h_layout.addWidget(QtWidgets.QLabel(self.tr("像素")))
        fast_h_layout.addSpacing(5)
        fast_h_layout.addStretch()
        edge_layout.addLayout(fast_h_layout)

        fast_v_layout = QtWidgets.QHBoxLayout()
        fast_v_layout.addWidget(QtWidgets.QLabel(self.tr("垂直边界调整：")))
        self.fast_adjust_step_v_spinbox = QtWidgets.QDoubleSpinBox()
        self.fast_adjust_step_v_spinbox.setRange(0.1, 100.0)
        self.fast_adjust_step_v_spinbox.setSingleStep(0.5)
        self.fast_adjust_step_v_spinbox.setValue(10.0)
        self.fast_adjust_step_v_spinbox.setMaximumWidth(70)
        self.fast_adjust_step_v_spinbox.valueChanged.connect(self.on_value_changed)
        fast_v_layout.addWidget(self.fast_adjust_step_v_spinbox)
        fast_v_layout.addWidget(QtWidgets.QLabel(self.tr("像素")))
        fast_v_layout.addSpacing(5)
        fast_v_layout.addStretch()
        edge_layout.addLayout(fast_v_layout)

        edge_group.setLayout(edge_layout)
        settings_layout.addWidget(edge_group)

        settings_layout.addSpacing(5)

        # === 矩形内扩展设置 ===
        inner_group = QtWidgets.QGroupBox(self.tr("矩形内扩展（鼠标在矩形内部）"))
        inner_layout = QtWidgets.QVBoxLayout()
        inner_layout.setSpacing(3)
        inner_layout.setContentsMargins(6, 6, 6, 6)

        # Normal scale
        inner_normal_label = QtWidgets.QLabel(self.tr("普通滚轮（扩展宽度）"))
        inner_normal_label.setStyleSheet("font-weight: bold; color: #0071e3; font-size: 9pt;")
        inner_layout.addWidget(inner_normal_label)

        scale_h_layout = QtWidgets.QHBoxLayout()
        scale_h_layout.addWidget(QtWidgets.QLabel(self.tr("宽度扩展步长：")))
        self.scale_step_h_spinbox = QtWidgets.QDoubleSpinBox()
        self.scale_step_h_spinbox.setRange(0.1, 100.0)
        self.scale_step_h_spinbox.setSingleStep(0.5)
        self.scale_step_h_spinbox.setValue(3.0)
        self.scale_step_h_spinbox.setMaximumWidth(70)
        self.scale_step_h_spinbox.valueChanged.connect(self.on_value_changed)
        scale_h_layout.addWidget(self.scale_step_h_spinbox)
        scale_h_layout.addWidget(QtWidgets.QLabel(self.tr("像素")))
        scale_h_layout.addSpacing(5)
        scale_h_layout.addStretch()
        inner_layout.addLayout(scale_h_layout)

        inner_layout.addSpacing(4)

        # Ctrl scale
        inner_ctrl_label = QtWidgets.QLabel(self.tr("Ctrl+滚轮（扩展高度）"))
        inner_ctrl_label.setStyleSheet("font-weight: bold; color: #d9534f; font-size: 9pt;")
        inner_layout.addWidget(inner_ctrl_label)

        scale_v_layout = QtWidgets.QHBoxLayout()
        scale_v_layout.addWidget(QtWidgets.QLabel(self.tr("高度扩展步长：")))
        self.scale_step_v_spinbox = QtWidgets.QDoubleSpinBox()
        self.scale_step_v_spinbox.setRange(0.1, 100.0)
        self.scale_step_v_spinbox.setSingleStep(0.5)
        self.scale_step_v_spinbox.setValue(3.0)
        self.scale_step_v_spinbox.setMaximumWidth(70)
        self.scale_step_v_spinbox.valueChanged.connect(self.on_value_changed)
        scale_v_layout.addWidget(self.scale_step_v_spinbox)
        scale_v_layout.addWidget(QtWidgets.QLabel(self.tr("像素")))
        scale_v_layout.addSpacing(5)
        scale_v_layout.addStretch()
        inner_layout.addLayout(scale_v_layout)

        inner_group.setLayout(inner_layout)
        settings_layout.addWidget(inner_group)

        main_layout.addLayout(settings_layout)

    def load_settings(self):
        """Load settings from config into UI."""
        # Block signals during loading to prevent multiple on_value_changed calls
        self.adjust_step_h_spinbox.blockSignals(True)
        self.adjust_step_v_spinbox.blockSignals(True)
        self.shift_adjust_step_h_spinbox.blockSignals(True)
        self.shift_adjust_step_v_spinbox.blockSignals(True)
        self.fast_adjust_step_h_spinbox.blockSignals(True)
        self.fast_adjust_step_v_spinbox.blockSignals(True)
        self.scale_step_h_spinbox.blockSignals(True)
        self.scale_step_v_spinbox.blockSignals(True)

        # Edge adjustment - normal
        self.adjust_step_h_spinbox.setValue(self.wheel_settings.get("adjust_step_h", 1.0))
        self.adjust_step_v_spinbox.setValue(self.wheel_settings.get("adjust_step_v", 1.0))

        # Edge adjustment - shift
        self.shift_adjust_step_h_spinbox.setValue(self.wheel_settings.get("shift_adjust_step_h", 5.0))
        self.shift_adjust_step_v_spinbox.setValue(self.wheel_settings.get("shift_adjust_step_v", 5.0))

        # Edge adjustment - fast (ctrl)
        self.fast_adjust_step_h_spinbox.setValue(self.wheel_settings.get("fast_adjust_step_h", 10.0))
        self.fast_adjust_step_v_spinbox.setValue(self.wheel_settings.get("fast_adjust_step_v", 10.0))

        # Inner scale
        self.scale_step_h_spinbox.setValue(self.wheel_settings.get("scale_step_h", 3.0))
        self.scale_step_v_spinbox.setValue(self.wheel_settings.get("scale_step_v", 3.0))

        # Unblock signals
        self.adjust_step_h_spinbox.blockSignals(False)
        self.adjust_step_v_spinbox.blockSignals(False)
        self.shift_adjust_step_h_spinbox.blockSignals(False)
        self.shift_adjust_step_v_spinbox.blockSignals(False)
        self.fast_adjust_step_h_spinbox.blockSignals(False)
        self.fast_adjust_step_v_spinbox.blockSignals(False)
        self.scale_step_h_spinbox.blockSignals(False)
        self.scale_step_v_spinbox.blockSignals(False)

        # Manually trigger on_value_changed once to update canvas
        self.on_value_changed()

    def get_settings(self):
        """Get current settings from UI."""
        return {
            "adjust_step_h": self.adjust_step_h_spinbox.value(),
            "adjust_step_v": self.adjust_step_v_spinbox.value(),
            "shift_adjust_step_h": self.shift_adjust_step_h_spinbox.value(),
            "shift_adjust_step_v": self.shift_adjust_step_v_spinbox.value(),
            "fast_adjust_step_h": self.fast_adjust_step_h_spinbox.value(),
            "fast_adjust_step_v": self.fast_adjust_step_v_spinbox.value(),
            "scale_step_h": self.scale_step_h_spinbox.value(),
            "scale_step_v": self.scale_step_v_spinbox.value(),
        }

    def on_value_changed(self):
        """Called when any spinbox value changes - update canvas immediately and save to config."""
        if self.parent and hasattr(self.parent, 'canvas'):
            settings = self.get_settings()
            # Update canvas settings immediately
            self.parent.canvas.rect_adjust_step_h = settings["adjust_step_h"]
            self.parent.canvas.rect_adjust_step_v = settings["adjust_step_v"]
            self.parent.canvas.rect_shift_adjust_step_h = settings["shift_adjust_step_h"]
            self.parent.canvas.rect_shift_adjust_step_v = settings["shift_adjust_step_v"]
            self.parent.canvas.rect_fast_adjust_step_h = settings["fast_adjust_step_h"]
            self.parent.canvas.rect_fast_adjust_step_v = settings["fast_adjust_step_v"]
            self.parent.canvas.rect_scale_step_h = settings["scale_step_h"]
            self.parent.canvas.rect_scale_step_v = settings["scale_step_v"]

            # Save to config file at the correct location (canvas.wheel_rectangle_editing)
            if hasattr(self.parent, '_config'):
                if "canvas" not in self.parent._config:
                    self.parent._config["canvas"] = {}
                self.parent._config["canvas"]["wheel_rectangle_editing"] = settings
                # Import and use the save_config function
                from anylabeling.config import save_config
                save_config(self.parent._config)

    def reset_to_defaults(self):
        """Reset all settings to default values."""
        self.adjust_step_h_spinbox.setValue(1.0)
        self.adjust_step_v_spinbox.setValue(1.0)
        self.shift_adjust_step_h_spinbox.setValue(5.0)
        self.shift_adjust_step_v_spinbox.setValue(5.0)
        self.fast_adjust_step_h_spinbox.setValue(10.0)
        self.fast_adjust_step_v_spinbox.setValue(10.0)
        self.scale_step_h_spinbox.setValue(3.0)
        self.scale_step_v_spinbox.setValue(3.0)

    def restore_window_position(self):
        """Restore window position and size from settings."""
        settings = QtCore.QSettings()
        geometry = settings.value("wheel_settings_dialog/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        else:
            # Default position if no settings are found (center of parent)
            if self.parent:
                parent_geometry = self.parent.geometry()
                x = parent_geometry.x() + (parent_geometry.width() - self.width()) // 2
                y = parent_geometry.y() + (parent_geometry.height() - self.height()) // 2
                self.move(x, y)

    def save_window_position(self):
        """Save current window position and size to settings."""
        settings = QtCore.QSettings()
        settings.setValue("wheel_settings_dialog/geometry", self.saveGeometry())

    def closeEvent(self, event):
        """Handle dialog close event."""
        self.save_window_position()
        event.accept()

    def hideEvent(self, event):
        """Handle the window hide event."""
        self.save_window_position()
        super(WheelSettingsDialog, self).hideEvent(event)

