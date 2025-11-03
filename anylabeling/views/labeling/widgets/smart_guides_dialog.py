# -*- encoding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt


class SmartGuidesDialog(QtWidgets.QDialog):
    """辅助线工具窗口"""
    
    # 信号：设置改变时发出
    setting_changed = QtCore.pyqtSignal(str, object)
    
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.parent = parent
        self._config = config if config is not None else {}
        
        self.setWindowTitle(self.tr("辅助线工具"))
        # 设置窗口标志：非阻塞，可最小化
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint
        )
        self.setMinimumWidth(320)
        self.setMaximumWidth(400)
        
        self.init_ui()
        self.load_settings()
    
    def init_ui(self):
        """初始化UI"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 1. 开启/关闭辅助线显示
        self.enable_checkbox = QtWidgets.QCheckBox(self.tr("开启辅助线显示"))
        self.enable_checkbox.setChecked(True)
        self.enable_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('smart_guides_enabled', state == Qt.Checked)
        )
        layout.addWidget(self.enable_checkbox)

        # 分隔线
        layout.addWidget(self._create_separator())

        # 2. 吸附距离（磁铁效果）
        snap_distance_layout = QtWidgets.QHBoxLayout()
        snap_distance_label = QtWidgets.QLabel(self.tr("吸附距离:"))
        snap_distance_label.setMinimumWidth(100)
        self.snap_distance_spinbox = QtWidgets.QSpinBox()
        self.snap_distance_spinbox.setRange(1, 50)
        self.snap_distance_spinbox.setSingleStep(1)
        self.snap_distance_spinbox.setValue(10)
        self.snap_distance_spinbox.valueChanged.connect(
            lambda value: self._on_setting_changed('smart_guides_snap_distance', value)
        )
        snap_distance_layout.addWidget(snap_distance_label)
        snap_distance_layout.addWidget(self.snap_distance_spinbox)
        layout.addLayout(snap_distance_layout)

        # 3. 辅助线显示距离
        display_distance_layout = QtWidgets.QHBoxLayout()
        display_distance_label = QtWidgets.QLabel(self.tr("辅助线显示距离:"))
        display_distance_label.setMinimumWidth(100)
        self.display_distance_spinbox = QtWidgets.QSpinBox()
        self.display_distance_spinbox.setRange(1, 500)
        self.display_distance_spinbox.setSingleStep(1)
        self.display_distance_spinbox.setValue(100)
        self.display_distance_spinbox.valueChanged.connect(
            lambda value: self._on_setting_changed('smart_guides_display_distance', value)
        )
        display_distance_layout.addWidget(display_distance_label)
        display_distance_layout.addWidget(self.display_distance_spinbox)
        layout.addLayout(display_distance_layout)

        # 4. 最大辅助线条数
        max_lines_layout = QtWidgets.QHBoxLayout()
        max_lines_label = QtWidgets.QLabel(self.tr("最大辅助线条数:"))
        max_lines_label.setMinimumWidth(100)
        self.max_lines_spinbox = QtWidgets.QSpinBox()
        self.max_lines_spinbox.setRange(1, 50)
        self.max_lines_spinbox.setSingleStep(1)
        self.max_lines_spinbox.setValue(10)
        self.max_lines_spinbox.valueChanged.connect(
            lambda value: self._on_setting_changed('smart_guides_max_lines', value)
        )
        max_lines_layout.addWidget(max_lines_label)
        max_lines_layout.addWidget(self.max_lines_spinbox)
        layout.addLayout(max_lines_layout)

        # 分隔线
        layout.addWidget(self._create_separator())

        # === 粘贴模式设置 ===
        paste_mode_title = QtWidgets.QLabel(self.tr("<b>粘贴模式设置</b>"))
        layout.addWidget(paste_mode_title)

        # 7. 启用虚影粘贴模式
        self.paste_preview_checkbox = QtWidgets.QCheckBox(self.tr("启用虚影粘贴模式"))
        self.paste_preview_checkbox.setChecked(self._config.get('smart_guides_paste_preview_enabled', True))
        self.paste_preview_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('smart_guides_paste_preview_enabled', state == Qt.Checked)
        )
        layout.addWidget(self.paste_preview_checkbox)

        # 说明文本
        help_text = QtWidgets.QLabel(
            self.tr("• <b>启用</b>：复制后显示虚影跟随鼠标，粘贴到鼠标位置\n"
                   "  （适合在同一图片内复制标注）\n"
                   "• <b>禁用</b>：传统模式，粘贴到原始坐标位置\n"
                   "  （适合跨图片复制标注到相同位置）")
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: gray; font-size: 9pt; margin-left: 20px;")
        layout.addWidget(help_text)

        # 添加分隔线
        layout.addWidget(self._create_separator())

        # 矩形间距线设置
        spacing_guide_title = QtWidgets.QLabel(self.tr("<b>矩形间距线</b>"))
        layout.addWidget(spacing_guide_title)

        # 开启/关闭间距线显示
        self.spacing_guide_checkbox = QtWidgets.QCheckBox(self.tr("开启间距线显示"))
        self.spacing_guide_checkbox.setChecked(True)
        self.spacing_guide_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('spacing_guide_enabled', state == Qt.Checked)
        )
        layout.addWidget(self.spacing_guide_checkbox)

        # 仅对选中矩形测距
        self.spacing_guide_selected_only_checkbox = QtWidgets.QCheckBox(
            self.tr("仅对选中矩形测距")
        )
        self.spacing_guide_selected_only_checkbox.setChecked(False)
        self.spacing_guide_selected_only_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('spacing_guide_selected_only', state == Qt.Checked)
        )
        layout.addWidget(self.spacing_guide_selected_only_checkbox)

        # 间距线显示距离
        spacing_display_distance_layout = QtWidgets.QHBoxLayout()
        spacing_display_distance_label = QtWidgets.QLabel(self.tr("显示距离:"))
        spacing_display_distance_label.setMinimumWidth(100)
        self.spacing_display_distance_spinbox = QtWidgets.QSpinBox()
        self.spacing_display_distance_spinbox.setRange(1, 999999)  # 移除限制，允许任意输入
        self.spacing_display_distance_spinbox.setSingleStep(10)
        self.spacing_display_distance_spinbox.setValue(200)
        self.spacing_display_distance_spinbox.setSuffix(self.tr(" px"))
        self.spacing_display_distance_spinbox.valueChanged.connect(
            lambda value: self._on_setting_changed('spacing_guide_display_distance', value)
        )
        spacing_display_distance_layout.addWidget(spacing_display_distance_label)
        spacing_display_distance_layout.addWidget(self.spacing_display_distance_spinbox)
        layout.addLayout(spacing_display_distance_layout)

        # 最多检测的矩形数量
        spacing_max_shapes_layout = QtWidgets.QHBoxLayout()
        spacing_max_shapes_label = QtWidgets.QLabel(self.tr("最多检测矩形数:"))
        spacing_max_shapes_label.setMinimumWidth(100)
        self.spacing_max_shapes_spinbox = QtWidgets.QSpinBox()
        self.spacing_max_shapes_spinbox.setRange(0, 50)
        self.spacing_max_shapes_spinbox.setSingleStep(1)
        self.spacing_max_shapes_spinbox.setValue(0)
        self.spacing_max_shapes_spinbox.setSuffix(self.tr(" (0=全部)"))
        self.spacing_max_shapes_spinbox.valueChanged.connect(
            lambda value: self._on_setting_changed('spacing_guide_max_shapes', value)
        )
        spacing_max_shapes_layout.addWidget(spacing_max_shapes_label)
        spacing_max_shapes_layout.addWidget(self.spacing_max_shapes_spinbox)
        layout.addLayout(spacing_max_shapes_layout)

        # 添加弹性空间
        layout.addStretch()
    
    def _create_separator(self):
        """创建分隔线"""
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        return line
    
    def _on_setting_changed(self, key, value):
        """设置改变时的回调"""
        # 更新配置
        if self._config is not None:
            self._config[key] = value

        # 发出信号
        self.setting_changed.emit(key, value)

        # 如果父窗口有 canvas，直接更新
        if self.parent and hasattr(self.parent, 'canvas'):
            if key == 'smart_guides_enabled':
                self.parent.canvas.smart_guides_enabled = value
            elif key == 'smart_guides_snap_distance':
                self.parent.canvas.smart_guides_snap_distance = value
            elif key == 'smart_guides_display_distance':
                self.parent.canvas.smart_guides_display_distance = value
            elif key == 'smart_guides_max_lines':
                self.parent.canvas.smart_guides_max_lines = value
            elif key == 'smart_guides_paste_preview_enabled':
                self.parent.canvas.smart_guides_paste_preview_enabled = value
            elif key == 'spacing_guide_enabled':
                self.parent.canvas.spacing_guide_enabled = value
            elif key == 'spacing_guide_selected_only':
                self.parent.canvas.spacing_guide_selected_only = value
            elif key == 'spacing_guide_display_distance':
                self.parent.canvas.spacing_guide_display_distance = value
            elif key == 'spacing_guide_max_shapes':
                self.parent.canvas.spacing_guide_max_shapes = value

            # 刷新画布
            self.parent.canvas.update()


    def load_settings(self):
        """从配置加载设置"""
        if self._config is None:
            return

        # 加载辅助线设置到控件
        self.enable_checkbox.setChecked(
            self._config.get('smart_guides_enabled', True)
        )
        self.snap_distance_spinbox.setValue(
            self._config.get('smart_guides_snap_distance', 10)
        )
        self.display_distance_spinbox.setValue(
            self._config.get('smart_guides_display_distance', 100)
        )
        self.max_lines_spinbox.setValue(
            self._config.get('smart_guides_max_lines', 10)
        )
        self.paste_preview_checkbox.setChecked(
            self._config.get('smart_guides_paste_preview_enabled', True)
        )

        # 加载间距线设置到控件
        self.spacing_guide_checkbox.setChecked(
            self._config.get('spacing_guide_enabled', True)
        )
        self.spacing_guide_selected_only_checkbox.setChecked(
            self._config.get('spacing_guide_selected_only', False)
        )
        self.spacing_display_distance_spinbox.setValue(
            self._config.get('spacing_guide_display_distance', 200)
        )
        self.spacing_max_shapes_spinbox.setValue(
            self._config.get('spacing_guide_max_shapes', 0)
        )

        # 手动同步到 canvas（因为 setChecked/setValue 不会触发信号）
        if self.parent and hasattr(self.parent, 'canvas'):
            self.parent.canvas.smart_guides_enabled = self._config.get('smart_guides_enabled', True)
            self.parent.canvas.smart_guides_snap_distance = self._config.get('smart_guides_snap_distance', 10)
            self.parent.canvas.smart_guides_display_distance = self._config.get('smart_guides_display_distance', 100)
            self.parent.canvas.smart_guides_max_lines = self._config.get('smart_guides_max_lines', 10)
            self.parent.canvas.smart_guides_paste_preview_enabled = self._config.get('smart_guides_paste_preview_enabled', True)

            # 同步间距线设置
            self.parent.canvas.spacing_guide_enabled = self._config.get('spacing_guide_enabled', True)
            self.parent.canvas.spacing_guide_selected_only = self._config.get('spacing_guide_selected_only', False)
            self.parent.canvas.spacing_guide_display_distance = self._config.get('spacing_guide_display_distance', 200)
            self.parent.canvas.spacing_guide_max_shapes = self._config.get('spacing_guide_max_shapes', 0)
            # 注意：spacing_guide_line_color 和 spacing_guide_opacity 现在由颜色管理器处理

            self.parent.canvas.update()

