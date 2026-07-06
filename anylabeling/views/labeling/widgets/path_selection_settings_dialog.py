# -*- encoding: utf-8 -*-
"""路径线 / 矩形框多选设置对话框（非阻塞模式）"""

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt

from anylabeling.config import save_config, get_config


class PathSelectionSettingsDialog(QtWidgets.QWidget):
    """路径线 / 矩形框多选的模式设置：
        - 默认多选模式：原有行为，只选中图形
        - 标签模式：多选完成后自动将所有选中图形改为指定标签

    注意：该窗口为非阻塞（modeless），带最小化按钮，可常驻在桌面上。
          所有设置即时保存，无需"确定"按钮。
    """

    def __init__(self, parent=None):
        super(PathSelectionSettingsDialog, self).__init__(parent)
        self.setWindowTitle("路径线/框选设置")
        self.setFixedWidth(200)
        self._parent = parent
        self._config = get_config()

        # 非阻塞窗口，带最小化 / 关闭按钮
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowTitleHint
            | Qt.WindowCloseButtonHint
            | Qt.WindowMinimizeButtonHint
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # ========== 1. 模式选择 ==========
        mode_group = QtWidgets.QGroupBox("选择模式")
        mode_layout = QtWidgets.QVBoxLayout()
        mode_layout.setSpacing(6)
        mode_group.setLayout(mode_layout)

        self.rb_default = QtWidgets.QRadioButton("默认多选模式")
        self.rb_label = QtWidgets.QRadioButton("标签模式")

        mode_layout.addWidget(self.rb_default)
        mode_layout.addWidget(self.rb_label)

        layout.addWidget(mode_group)

        # ========== 2. 标签列表 ==========
        label_group = QtWidgets.QGroupBox("目标标签")
        label_layout = QtWidgets.QVBoxLayout()
        label_layout.setSpacing(6)
        label_group.setLayout(label_layout)

        self.label_list = QtWidgets.QListWidget()
        self.label_list.setSelectionMode(QtWidgets.QListWidget.NoSelection)
        self.label_list.itemChanged.connect(self._on_item_changed)
        label_layout.addWidget(self.label_list)

        layout.addWidget(label_group)

        # ========== 信号 ==========
        self.rb_label.toggled.connect(self._on_mode_toggled)
        self.rb_default.toggled.connect(self._on_mode_toggled)

        # ========== 初始化 ==========
        self._populate_labels()
        self._load_settings()

    def _get_label_color(self, label):
        """使用与主界面完全一致的标签颜色"""
        if self._parent is not None and hasattr(self._parent, "_get_rgb_by_label"):
            try:
                # 先找已有的 unique_label_list 项，避免 _get_rgb_by_label 新建项
                items = self._parent.unique_label_list.find_items_by_label(label)
                if items:
                    return self._parent._get_rgb_by_label(
                        label, unique_item=items[0]
                    )
                return self._parent._get_rgb_by_label(label)
            except Exception:
                pass
        return (128, 128, 128)

    def _populate_labels(self):
        """从配置中读取标签列表并填充带颜色背景的项"""
        self.label_list.clear()
        labels = self._config.get("labels", [])
        if not labels:
            item = QtWidgets.QListWidgetItem("（无可用标签）")
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.label_list.addItem(item)
            return

        for label in labels:
            item = QtWidgets.QListWidgetItem(label)
            item.setData(Qt.UserRole, label)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)

            color = self._get_label_color(label)
            background_color = QtGui.QColor(*color, 128)
            item.setBackground(background_color)
            self.label_list.addItem(item)

    def _load_settings(self):
        """从配置中加载当前设置"""
        ps_config = self._config.get("path_selection_settings", {})
        is_label_mode = ps_config.get("label_mode", False)
        selected_label = ps_config.get("target_label", "")

        if is_label_mode:
            self.rb_label.setChecked(True)
        else:
            self.rb_default.setChecked(True)

        # 勾选目标标签
        for row in range(self.label_list.count()):
            item = self.label_list.item(row)
            label = item.data(Qt.UserRole)
            if label and label == selected_label:
                item.setCheckState(Qt.Checked)
                break

        self._on_mode_toggled(is_label_mode)

    def _on_mode_toggled(self, checked):
        """标签模式切换时启用/禁用标签列表并即时保存"""
        label_mode = self.rb_label.isChecked()
        self.label_list.setEnabled(label_mode)
        self._save_settings()

    def _on_item_changed(self, item):
        """勾选变化时保证单选并即时保存"""
        if not self.rb_label.isChecked():
            return
        if item.checkState() == Qt.Checked:
            # 取消其他项的勾选
            for row in range(self.label_list.count()):
                other = self.label_list.item(row)
                if other is not item:
                    other.setCheckState(Qt.Unchecked)
            self._save_settings()
        elif self._get_current_checked_label() is None:
            # 不允许全部取消：至少保留一个勾选
            item.setCheckState(Qt.Checked)

    def _get_current_checked_label(self):
        """获取当前勾选的标签"""
        for row in range(self.label_list.count()):
            item = self.label_list.item(row)
            if item.checkState() == Qt.Checked:
                return item.data(Qt.UserRole)
        return None

    def _save_settings(self):
        """保存当前设置到配置并同步到 canvas"""
        is_label_mode = self.rb_label.isChecked()
        target_label = self._get_current_checked_label() if is_label_mode else ""

        self._config["path_selection_settings"] = {
            "label_mode": is_label_mode,
            "target_label": target_label or "",
        }
        save_config(self._config)

        # 同步到 canvas 内存配置，避免选中时读取文件
        if self._parent and hasattr(self._parent, "canvas"):
            self._parent.canvas._config["path_selection_settings"] = {
                "label_mode": is_label_mode,
                "target_label": target_label or "",
            }

    def closeEvent(self, event):
        """关闭时保存设置"""
        self._save_settings()
        event.accept()

    @staticmethod
    def is_label_mode():
        """静态方法：当前是否为标签模式"""
        cfg = get_config()
        return cfg.get("path_selection_settings", {}).get("label_mode", False)

    @staticmethod
    def get_target_label():
        """静态方法：获取当前目标标签"""
        cfg = get_config()
        return cfg.get("path_selection_settings", {}).get("target_label", "")
