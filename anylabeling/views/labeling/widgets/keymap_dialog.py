from PyQt5 import QtWidgets, QtCore, QtGui
import math
from anylabeling.config import save_config

class KeymapDialog(QtWidgets.QDialog):
    config_saved = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None, config=None, shortcut_key=None):
        super().__init__(parent)
        self.parent = parent
        self._config = config if config is not None else {}

        self.setWindowTitle(self.tr("旋转标签快捷键管理器"))
        # Set window flags to remove the question mark and add a minimize button
        self.setWindowFlags(
            self.windowFlags()
            & ~QtCore.Qt.WindowContextHelpButtonHint
            | QtCore.Qt.WindowMinimizeButtonHint
        )
        # self.setModal(True) # Removed
        self.setMinimumWidth(500)

        self.direction_actions = {
            self.tr("默认 (移动)"): "default",
            self.tr("向左大幅旋转 (Z)"): "rotate_large_left",
            self.tr("向右大幅旋转 (V)"): "rotate_large_right",
            self.tr("向左小幅旋转 (X)"): "rotate_small_left",
            self.tr("向右小幅旋转 (C)"): "rotate_small_right",
        }
        self.zxcv_actions = {
            self.tr("默认 (旋转)"): "default",
            self.tr("向上移动 (Up)"): "move_up",
            self.tr("向下移动 (Down)"): "move_down",
            self.tr("向左移动 (Left)"): "move_left",
            self.tr("向右移动 (Right)"): "move_right",
        }
        self.key_display_names = {
            "Up": self.tr("上方向键"),
            "Down": self.tr("下方向键"),
            "Left": self.tr("左方向键"),
            "Right": self.tr("右方向键"),
            "Z": self.tr("键盘区Z"),
            "X": self.tr("键盘区X"),
            "C": self.tr("键盘区C"),
            "V": self.tr("键盘区V"),
        }
        self.keys = {
            "direction": ["Up", "Down", "Left", "Right"],
            "zxcv": ["Z", "X", "C", "V"],
        }

        self.combos = {"direction": {}, "zxcv": {}}
        self.line_edits = {}

        layout = QtWidgets.QVBoxLayout()

        # Direction keys group
        direction_group = QtWidgets.QGroupBox(self.tr("方向键设置"))
        direction_layout = QtWidgets.QVBoxLayout()

        self.direction_enable_checkbox = QtWidgets.QCheckBox(self.tr("启用方向键自定义"))
        self.direction_enable_checkbox.setChecked(True)
        direction_layout.addWidget(self.direction_enable_checkbox)
        self.direction_enable_checkbox.toggled.connect(self._toggle_direction_keys_enabled)

        direction_labels_label = QtWidgets.QLabel(self.tr("适用标签 (逗号隔开):"))
        direction_layout.addWidget(direction_labels_label)
        self.line_edits["direction"] = QtWidgets.QLineEdit()
        direction_layout.addWidget(self.line_edits["direction"])

        direction_keys_layout = QtWidgets.QGridLayout()
        for i, key in enumerate(self.keys["direction"]):
            label = QtWidgets.QLabel(f"{self.key_display_names[key]}: ")
            combo = QtWidgets.QComboBox()
            for name in self.direction_actions.keys():
                combo.addItem(name)
            direction_keys_layout.addWidget(label, 0, i)
            direction_keys_layout.addWidget(combo, 1, i)
            self.combos["direction"][key] = combo
        direction_layout.addLayout(direction_keys_layout)
        direction_group.setLayout(direction_layout)

        # ZXCV keys group
        zxcv_group = QtWidgets.QGroupBox(self.tr("ZXCV键设置"))
        zxcv_layout = QtWidgets.QVBoxLayout()

        self.zxcv_enable_checkbox = QtWidgets.QCheckBox(self.tr("启用ZXCV键自定义"))
        self.zxcv_enable_checkbox.setChecked(True)
        zxcv_layout.addWidget(self.zxcv_enable_checkbox)
        self.zxcv_enable_checkbox.toggled.connect(self._toggle_zxcv_keys_enabled)

        zxcv_labels_label = QtWidgets.QLabel(self.tr("适用标签 (逗号隔开):"))
        zxcv_layout.addWidget(zxcv_labels_label)
        self.line_edits["zxcv"] = QtWidgets.QLineEdit()
        zxcv_layout.addWidget(self.line_edits["zxcv"])

        zxcv_keys_layout = QtWidgets.QGridLayout()
        for i, key in enumerate(self.keys["zxcv"]):
            label = QtWidgets.QLabel(f"{self.key_display_names[key]}: ")
            combo = QtWidgets.QComboBox()
            for name in self.zxcv_actions.keys():
                combo.addItem(name)
            zxcv_keys_layout.addWidget(label, 0, i)
            zxcv_keys_layout.addWidget(combo, 1, i)
            self.combos["zxcv"][key] = combo
        zxcv_layout.addLayout(zxcv_keys_layout)
        zxcv_group.setLayout(zxcv_layout)

        # Speed Adjustment group
        speed_group = QtWidgets.QGroupBox(self.tr("速度调整设置"))
        speed_layout = QtWidgets.QGridLayout()

        # Labels for speed settings
        move_speed_label = QtWidgets.QLabel(self.tr("移动速度"))
        large_rotation_label = QtWidgets.QLabel(self.tr("角度快调:"))
        small_rotation_label = QtWidgets.QLabel(self.tr("角度微调:"))

        speed_layout.addWidget(move_speed_label, 0, 0, QtCore.Qt.AlignCenter)
        speed_layout.addWidget(large_rotation_label, 0, 1, QtCore.Qt.AlignCenter)
        speed_layout.addWidget(small_rotation_label, 0, 2, QtCore.Qt.AlignCenter)

        self.move_speed_spinbox = QtWidgets.QDoubleSpinBox()
        self.move_speed_spinbox.setRange(0.01, 10.0)
        self.move_speed_spinbox.setSingleStep(0.1)
        self.move_speed_spinbox.setDecimals(2)
        self.move_speed_spinbox.setFixedWidth(60) # Adjust size
        self.move_speed_spinbox.valueChanged.connect(self._update_speed_settings)

        self.large_rotation_spinbox = QtWidgets.QDoubleSpinBox()
        self.large_rotation_spinbox.setRange(0.0, 360.0)
        self.large_rotation_spinbox.setSingleStep(0.1)
        self.large_rotation_spinbox.setDecimals(2)
        self.large_rotation_spinbox.setFixedWidth(60) # Adjust size
        self.large_rotation_spinbox.valueChanged.connect(self._update_speed_settings)

        self.small_rotation_spinbox = QtWidgets.QDoubleSpinBox()
        self.small_rotation_spinbox.setRange(0.0, 360.0)
        self.small_rotation_spinbox.setSingleStep(0.1)
        self.small_rotation_spinbox.setDecimals(2)
        self.small_rotation_spinbox.setFixedWidth(60) # Adjust size
        self.small_rotation_spinbox.valueChanged.connect(self._update_speed_settings)

        speed_layout.addWidget(self.move_speed_spinbox, 1, 0, QtCore.Qt.AlignCenter)
        speed_layout.addWidget(self.large_rotation_spinbox, 1, 1, QtCore.Qt.AlignCenter)
        speed_layout.addWidget(self.small_rotation_spinbox, 1, 2, QtCore.Qt.AlignCenter)

        speed_group.setLayout(speed_layout)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        save_button = QtWidgets.QPushButton(self.tr("保存配置"))
        save_button.clicked.connect(self._save_config_only)
        close_button = QtWidgets.QPushButton(self.tr("关闭"))
        close_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(close_button)

        layout.addWidget(direction_group)
        layout.addWidget(zxcv_group)
        layout.addWidget(speed_group)
        layout.addLayout(button_layout)

        self.setLayout(layout)
        self.load_config()

        # Add shortcut for closing/toggling the dialog
        if shortcut_key:
            self.toggle_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(shortcut_key), self)
            self.toggle_shortcut.activated.connect(self.accept) # Connect to accept, so it acts like a close button
            self.toggle_shortcut.setContext(QtCore.Qt.WindowShortcut) # Active when this window or its children have focus

    def _update_speed_settings(self):
        speed_settings = {
            "move_speed": self.move_speed_spinbox.value(),
            "large_rotation_increment": math.radians(self.large_rotation_spinbox.value()),
            "small_rotation_increment": math.radians(self.small_rotation_spinbox.value()),
        }
        self._config["speed_settings"] = speed_settings

        # Update keymap config with enabled/disabled states
        keymap_config = self._config.get("keymap", {})
        keymap_config["direction_enabled"] = self.direction_enable_checkbox.isChecked()
        keymap_config["zxcv_enabled"] = self.zxcv_enable_checkbox.isChecked()
        self._config["keymap"] = keymap_config

        self.config_saved.emit(self._config["keymap"])

    def _save_config_only(self):
        keymap_config = self.get_config()
        self._config["keymap"] = keymap_config
        save_config(self._config)
        self.config_saved.emit(self._config["keymap"])

    def load_config(self):
        keymap_config = self._config.get("keymap", {})

        # Load checkbox states
        self.direction_enable_checkbox.setChecked(keymap_config.get("direction_enabled", True))
        self.zxcv_enable_checkbox.setChecked(keymap_config.get("zxcv_enabled", True))

        # Set default labels if not present in config
        default_direction_labels = "shuqing, hengxie"
        default_zxcv_labels = "balloon, qipao, changfangtiao, other"

        for group, keys in self.keys.items():
            group_config = keymap_config.get(group, {})

            if group == "direction":
                labels = ",".join(group_config.get("labels", [])) or default_direction_labels
            else: # zxcv
                labels = ",".join(group_config.get("labels", [])) or default_zxcv_labels

            self.line_edits[group].setText(labels)
            actions = self.direction_actions if group == "direction" else self.zxcv_actions
            for key in keys:
                action = group_config.get("actions", {}).get(key.lower(), "default")
                for name, action_id in actions.items():
                    if action_id == action:
                        self.combos[group][key].setCurrentText(name)
                        break

        # Apply initial enabled/disabled state
        self._toggle_direction_keys_enabled(self.direction_enable_checkbox.isChecked())
        self._toggle_zxcv_keys_enabled(self.zxcv_enable_checkbox.isChecked())

        # Load speed settings
        speed_settings = self._config.get("speed_settings", {})
        self.move_speed_spinbox.setValue(speed_settings.get("move_speed", 0.5))
        self.large_rotation_spinbox.setValue(math.degrees(speed_settings.get("large_rotation_increment", 0.0087)))
        self.small_rotation_spinbox.setValue(math.degrees(speed_settings.get("small_rotation_increment", 0.001745)))

    def get_config(self):
        keymap_config = {"direction": {"labels": [], "actions": {}}, "zxcv": {"labels": [], "actions": {}}}
        for group, line_edit in self.line_edits.items():
            labels = [label.strip() for label in line_edit.text().split(",") if label.strip()]
            keymap_config[group]["labels"] = labels
            actions = self.direction_actions if group == "direction" else self.zxcv_actions
            for key, combo in self.combos[group].items():
                action_name = combo.currentText()
                keymap_config[group]["actions"][key.lower()] = actions[action_name]

        keymap_config["direction_enabled"] = self.direction_enable_checkbox.isChecked()
        keymap_config["zxcv_enabled"] = self.zxcv_enable_checkbox.isChecked()

        # Save speed settings
        keymap_config["speed_settings"] = {
            "move_speed": self.move_speed_spinbox.value(),
            "large_rotation_increment": math.radians(self.large_rotation_spinbox.value()),
            "small_rotation_increment": math.radians(self.small_rotation_spinbox.value()),
        }
        return keymap_config

    def _toggle_direction_keys_enabled(self, enabled):
        self.line_edits["direction"].setEnabled(enabled)
        for combo in self.combos["direction"].values():
            combo.setEnabled(enabled)

    def _toggle_zxcv_keys_enabled(self, enabled):
        self.line_edits["zxcv"].setEnabled(enabled)
        for combo in self.combos["zxcv"].values():
            combo.setEnabled(enabled)
