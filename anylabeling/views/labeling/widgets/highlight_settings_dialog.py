from PyQt5 import QtWidgets, QtCore
from anylabeling.config import save_config

class HighlightSettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, config=None):
        super(HighlightSettingsDialog, self).__init__(parent)
        self.setWindowTitle("高亮与锁定设置")
        self.setMinimumWidth(300)

        self._config = config

        self.layout = QtWidgets.QVBoxLayout(self)

        # Positive Highlight
        self.positive_group = QtWidgets.QGroupBox("正向高亮")
        self.positive_layout = QtWidgets.QVBoxLayout()
        self.positive_label = QtWidgets.QLabel("需要高亮的标签 (英文逗号分隔):")
        self.positive_input = QtWidgets.QLineEdit()
        self.positive_layout.addWidget(self.positive_label)
        self.positive_layout.addWidget(self.positive_input)
        self.positive_group.setLayout(self.positive_layout)

        # Negative Highlight
        self.negative_group = QtWidgets.QGroupBox("反向高亮")
        self.negative_layout = QtWidgets.QVBoxLayout()
        self.negative_label = QtWidgets.QLabel("需要取消高亮的标签 (英文逗号分隔):")
        self.negative_input = QtWidgets.QLineEdit()
        self.negative_layout.addWidget(self.negative_label)
        self.negative_layout.addWidget(self.negative_input)
        self.negative_group.setLayout(self.negative_layout)

        # Label Lock
        self.lock_group = QtWidgets.QGroupBox("标签锁定")
        self.lock_layout = QtWidgets.QVBoxLayout()
        self.lock_label = QtWidgets.QLabel("需要锁定的标签 (英文逗号分隔):")
        self.lock_input = QtWidgets.QLineEdit()
        self.lock_highlight_checkbox = QtWidgets.QCheckBox("锁定后仍可高亮")
        self.lock_highlight_checkbox.setToolTip("启用后，锁定的标签也能参与高亮/反向高亮功能")
        self.lock_hide_info_checkbox = QtWidgets.QCheckBox("锁定后不显示宽高和角度")
        self.lock_hide_info_checkbox.setToolTip("启用后，锁定的标签不显示宽高和旋转角度信息")
        self.lock_layout.addWidget(self.lock_label)
        self.lock_layout.addWidget(self.lock_input)
        self.lock_layout.addWidget(self.lock_highlight_checkbox)
        self.lock_layout.addWidget(self.lock_hide_info_checkbox)
        self.lock_group.setLayout(self.lock_layout)

        # Label Pin to Top
        self.pin_group = QtWidgets.QGroupBox("创建后置顶")
        self.pin_layout = QtWidgets.QVBoxLayout()
        self.pin_label = QtWidgets.QLabel("创建后置顶的标签 (英文逗号分隔):")
        self.pin_input = QtWidgets.QLineEdit()
        self.pin_layout.addWidget(self.pin_label)
        self.pin_layout.addWidget(self.pin_input)
        self.pin_group.setLayout(self.pin_layout)

        # No Highlight After Creation
        self.no_highlight_group = QtWidgets.QGroupBox("创建后不高亮")
        self.no_highlight_layout = QtWidgets.QVBoxLayout()
        self.no_highlight_label = QtWidgets.QLabel("创建后不高亮的标签 (英文逗号分隔):")
        self.no_highlight_input = QtWidgets.QLineEdit()
        self.no_highlight_layout.addWidget(self.no_highlight_label)
        self.no_highlight_layout.addWidget(self.no_highlight_input)
        self.no_highlight_group.setLayout(self.no_highlight_layout)

        # Mixed Mode Detection
        self.mixed_mode_group = QtWidgets.QGroupBox("混合模式检测")
        self.mixed_mode_layout = QtWidgets.QVBoxLayout()
        self.mixed_mode_checkbox = QtWidgets.QCheckBox("启用混合模式检测")
        self.mixed_mode_layout.addWidget(self.mixed_mode_checkbox)
        self.mixed_mode_group.setLayout(self.mixed_mode_layout)

        # Default Highlight Enabled
        self.default_highlight_group = QtWidgets.QGroupBox("高亮常驻设置")
        self.default_highlight_layout = QtWidgets.QVBoxLayout()
        self.default_highlight_checkbox = QtWidgets.QCheckBox("启用常驻高亮")
        self.default_highlight_layout.addWidget(self.default_highlight_checkbox)
        self.default_highlight_group.setLayout(self.default_highlight_layout)

        self.layout.addWidget(self.positive_group)
        self.layout.addWidget(self.negative_group)
        self.layout.addWidget(self.lock_group)
        self.layout.addWidget(self.pin_group)
        self.layout.addWidget(self.no_highlight_group)
        self.layout.addWidget(self.mixed_mode_group)
        self.layout.addWidget(self.default_highlight_group)

        # 添加最小化按钮，移除帮助按钮
        self.setWindowFlags(
            self.windowFlags() 
            | QtCore.Qt.WindowMinimizeButtonHint 
            | QtCore.Qt.WindowMaximizeButtonHint 
            & ~QtCore.Qt.WindowContextHelpButtonHint
        )

        # Connect signals for real-time saving
        self.positive_input.textChanged.connect(self._realtime_save_settings)
        self.negative_input.textChanged.connect(self._realtime_save_settings)
        self.lock_input.textChanged.connect(self._realtime_save_settings)
        self.lock_highlight_checkbox.stateChanged.connect(self._realtime_save_settings)
        self.lock_hide_info_checkbox.stateChanged.connect(self._realtime_save_settings)
        self.pin_input.textChanged.connect(self._realtime_save_settings)
        self.no_highlight_input.textChanged.connect(self._realtime_save_settings)
        self.mixed_mode_checkbox.stateChanged.connect(self._realtime_save_settings)
        self.default_highlight_checkbox.stateChanged.connect(self._on_default_highlight_changed)

        self.load_settings()

    def load_settings(self):
        """Loads settings from the config object into the line edits."""
        if self._config:
            # Temporarily disconnect signals to prevent saving during loading
            self.positive_input.textChanged.disconnect(self._realtime_save_settings)
            self.negative_input.textChanged.disconnect(self._realtime_save_settings)
            self.lock_input.textChanged.disconnect(self._realtime_save_settings)
            self.lock_highlight_checkbox.stateChanged.disconnect(self._realtime_save_settings)
            self.lock_hide_info_checkbox.stateChanged.disconnect(self._realtime_save_settings)
            self.pin_input.textChanged.disconnect(self._realtime_save_settings)
            self.no_highlight_input.textChanged.disconnect(self._realtime_save_settings)
            self.mixed_mode_checkbox.stateChanged.disconnect(self._realtime_save_settings)
            self.default_highlight_checkbox.stateChanged.disconnect(self._on_default_highlight_changed)

            positive_labels = self._config.get("highlight_positive", "")
            negative_labels = self._config.get("highlight_negative", "")
            locked_labels = self._config.get("locked_labels", "")
            lock_can_highlight = self._config.get("locked_can_highlight", False)
            lock_hide_info = self._config.get("locked_hide_info", False)
            pin_labels = self._config.get("pin_labels", "")
            no_highlight_labels = self._config.get("no_highlight_labels", "")
            mixed_mode_enabled = self._config.get("highlight_mixed_mode", False)
            default_highlight_enabled = self._config.get("highlight_enabled_by_default", True)
            self.positive_input.setText(positive_labels)
            self.negative_input.setText(negative_labels)
            self.lock_input.setText(locked_labels)
            self.lock_highlight_checkbox.setChecked(lock_can_highlight)
            self.lock_hide_info_checkbox.setChecked(lock_hide_info)
            self.pin_input.setText(pin_labels)
            self.no_highlight_input.setText(no_highlight_labels)
            self.mixed_mode_checkbox.setChecked(mixed_mode_enabled)
            self.default_highlight_checkbox.setChecked(default_highlight_enabled)

            # Reconnect signals
            self.positive_input.textChanged.connect(self._realtime_save_settings)
            self.negative_input.textChanged.connect(self._realtime_save_settings)
            self.lock_input.textChanged.connect(self._realtime_save_settings)
            self.lock_highlight_checkbox.stateChanged.connect(self._realtime_save_settings)
            self.lock_hide_info_checkbox.stateChanged.connect(self._realtime_save_settings)
            self.pin_input.textChanged.connect(self._realtime_save_settings)
            self.no_highlight_input.textChanged.connect(self._realtime_save_settings)
            self.mixed_mode_checkbox.stateChanged.connect(self._realtime_save_settings)
            self.default_highlight_checkbox.stateChanged.connect(self._on_default_highlight_changed)

    def _realtime_save_settings(self):
        """Saves the current settings from the line edits to the config file in real-time."""
        if self._config:
            self._config["highlight_positive"] = self.positive_input.text()
            self._config["highlight_negative"] = self.negative_input.text()
            self._config["locked_labels"] = self.lock_input.text()
            self._config["locked_can_highlight"] = self.lock_highlight_checkbox.isChecked()
            self._config["locked_hide_info"] = self.lock_hide_info_checkbox.isChecked()
            self._config["pin_labels"] = self.pin_input.text()
            self._config["no_highlight_labels"] = self.no_highlight_input.text()
            self._config["highlight_mixed_mode"] = self.mixed_mode_checkbox.isChecked()
            save_config(self._config)

    def _on_default_highlight_changed(self, state):
        """Handle default highlight checkbox state change with real-time effect."""
        if self._config:
            is_enabled = self.default_highlight_checkbox.isChecked()
            self._config["highlight_enabled_by_default"] = is_enabled
            save_config(self._config)
            
            # Apply the change immediately to all shapes in the parent (label_widget)
            if self.parent() and hasattr(self.parent(), 'apply_default_highlight_setting'):
                self.parent().apply_default_highlight_setting(is_enabled)

    def showEvent(self, event):
        """Override showEvent to reload settings every time the dialog is shown."""
        super().showEvent(event)
        self.load_settings()