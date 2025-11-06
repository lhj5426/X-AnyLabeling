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
        self.setMinimumWidth(640)  # 增加宽度以容纳左右分栏
        self.setMinimumHeight(500)
        
        self.init_ui()
        self.load_settings()
    
    def init_ui(self):
        """初始化UI"""
        # 主布局：水平分栏
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 左侧面板：辅助线设置
        left_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(left_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. 开启/关闭辅助线显示
        self.enable_checkbox = QtWidgets.QCheckBox(self.tr("开启辅助线显示"))
        self.enable_checkbox.setChecked(True)
        self.enable_checkbox.stateChanged.connect(self._on_enable_checkbox_changed)
        layout.addWidget(self.enable_checkbox)

        # 2. 启用辅助线吸附功能（依赖于辅助线显示）
        self.enable_snap_checkbox = QtWidgets.QCheckBox(self.tr("启用辅助线吸附功能"))
        self.enable_snap_checkbox.setChecked(True)
        self.enable_snap_checkbox.setToolTip(self.tr("关闭后只显示辅助线，不会自动吸附（配合矩形边缘吸附使用）"))
        self.enable_snap_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('smart_guides_enable_snap', state == Qt.Checked)
        )
        layout.addWidget(self.enable_snap_checkbox)

        # 🎯 辅助线方向显示开关（紧凑布局）
        show_direction_layout = QtWidgets.QHBoxLayout()
        show_direction_layout.setSpacing(10)
        show_direction_layout.setContentsMargins(20, 0, 0, 0)  # 左侧缩进

        self.show_horizontal_checkbox = QtWidgets.QCheckBox(self.tr("显示水平辅助线"))
        self.show_horizontal_checkbox.setChecked(True)
        self.show_horizontal_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('smart_guides_show_horizontal', state == Qt.Checked)
        )
        show_direction_layout.addWidget(self.show_horizontal_checkbox)

        self.show_vertical_checkbox = QtWidgets.QCheckBox(self.tr("显示垂直辅助线"))
        self.show_vertical_checkbox.setChecked(True)
        self.show_vertical_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('smart_guides_show_vertical', state == Qt.Checked)
        )
        show_direction_layout.addWidget(self.show_vertical_checkbox)

        show_direction_layout.addStretch()  # 右侧弹性空间
        layout.addLayout(show_direction_layout)

        # 🎯 方向吸附开关（紧凑布局，只显示4条边）
        direction_layout = QtWidgets.QHBoxLayout()
        direction_layout.setSpacing(10)
        direction_layout.setContentsMargins(20, 0, 0, 0)  # 左侧缩进

        self.snap_left_checkbox = QtWidgets.QCheckBox(self.tr("左边缘吸附"))
        self.snap_left_checkbox.setChecked(True)
        self.snap_left_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('smart_guides_snap_left', state == Qt.Checked)
        )
        direction_layout.addWidget(self.snap_left_checkbox)

        self.snap_right_checkbox = QtWidgets.QCheckBox(self.tr("右边缘吸附"))
        self.snap_right_checkbox.setChecked(True)
        self.snap_right_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('smart_guides_snap_right', state == Qt.Checked)
        )
        direction_layout.addWidget(self.snap_right_checkbox)

        self.snap_top_checkbox = QtWidgets.QCheckBox(self.tr("上边缘吸附"))
        self.snap_top_checkbox.setChecked(True)
        self.snap_top_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('smart_guides_snap_top', state == Qt.Checked)
        )
        direction_layout.addWidget(self.snap_top_checkbox)

        self.snap_bottom_checkbox = QtWidgets.QCheckBox(self.tr("下边缘吸附"))
        self.snap_bottom_checkbox.setChecked(True)
        self.snap_bottom_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('smart_guides_snap_bottom', state == Qt.Checked)
        )
        direction_layout.addWidget(self.snap_bottom_checkbox)

        direction_layout.addStretch()  # 右侧弹性空间
        layout.addLayout(direction_layout)

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

        # 8. 粘贴模式下显示辅助线
        self.paste_show_guides_checkbox = QtWidgets.QCheckBox(self.tr("粘贴模式显示辅助线"))
        self.paste_show_guides_checkbox.setChecked(self._config.get('smart_guides_paste_show_guides', True))
        self.paste_show_guides_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('smart_guides_paste_show_guides', state == Qt.Checked)
        )
        layout.addWidget(self.paste_show_guides_checkbox)

        # 9. 粘贴模式下启用吸附功能
        self.paste_enable_snap_checkbox = QtWidgets.QCheckBox(self.tr("粘贴模式启用吸附"))
        self.paste_enable_snap_checkbox.setChecked(self._config.get('smart_guides_paste_enable_snap', True))
        self.paste_enable_snap_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('smart_guides_paste_enable_snap', state == Qt.Checked)
        )
        layout.addWidget(self.paste_enable_snap_checkbox)

        # 10. 粘贴模式吸附距离
        paste_snap_distance_layout = QtWidgets.QHBoxLayout()
        paste_snap_distance_label = QtWidgets.QLabel(self.tr("粘贴模式吸附距离:"))
        paste_snap_distance_label.setMinimumWidth(100)
        self.paste_snap_distance_spinbox = QtWidgets.QSpinBox()
        self.paste_snap_distance_spinbox.setRange(1, 50)
        self.paste_snap_distance_spinbox.setSingleStep(1)
        self.paste_snap_distance_spinbox.setValue(10)
        self.paste_snap_distance_spinbox.valueChanged.connect(
            lambda value: self._on_setting_changed('smart_guides_paste_snap_distance', value)
        )
        paste_snap_distance_layout.addWidget(paste_snap_distance_label)
        paste_snap_distance_layout.addWidget(self.paste_snap_distance_spinbox)
        layout.addLayout(paste_snap_distance_layout)

        # 🎯 粘贴模式方向吸附开关（紧凑布局，只显示4条边）
        paste_direction_layout = QtWidgets.QHBoxLayout()
        paste_direction_layout.setSpacing(10)
        paste_direction_layout.setContentsMargins(20, 0, 0, 0)  # 左侧缩进

        self.paste_snap_left_checkbox = QtWidgets.QCheckBox(self.tr("左边缘吸附"))
        self.paste_snap_left_checkbox.setChecked(True)
        self.paste_snap_left_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('smart_guides_paste_snap_left', state == Qt.Checked)
        )
        paste_direction_layout.addWidget(self.paste_snap_left_checkbox)

        self.paste_snap_right_checkbox = QtWidgets.QCheckBox(self.tr("右边缘吸附"))
        self.paste_snap_right_checkbox.setChecked(True)
        self.paste_snap_right_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('smart_guides_paste_snap_right', state == Qt.Checked)
        )
        paste_direction_layout.addWidget(self.paste_snap_right_checkbox)

        self.paste_snap_top_checkbox = QtWidgets.QCheckBox(self.tr("上边缘吸附"))
        self.paste_snap_top_checkbox.setChecked(True)
        self.paste_snap_top_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('smart_guides_paste_snap_top', state == Qt.Checked)
        )
        paste_direction_layout.addWidget(self.paste_snap_top_checkbox)

        self.paste_snap_bottom_checkbox = QtWidgets.QCheckBox(self.tr("下边缘吸附"))
        self.paste_snap_bottom_checkbox.setChecked(True)
        self.paste_snap_bottom_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('smart_guides_paste_snap_bottom', state == Qt.Checked)
        )
        paste_direction_layout.addWidget(self.paste_snap_bottom_checkbox)

        paste_direction_layout.addStretch()  # 右侧弹性空间
        layout.addLayout(paste_direction_layout)

        # 添加分隔线
        # 添加弹性空间
        layout.addStretch()

        # 将左侧面板添加到主布局
        main_layout.addWidget(left_widget)

        # 添加垂直分隔线
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.VLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        main_layout.addWidget(separator)

        # 右侧面板：边缘吸附设置
        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setSpacing(15)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 边缘吸附标题
        edge_snap_title = QtWidgets.QLabel(self.tr("<b>边缘吸附</b>"))
        right_layout.addWidget(edge_snap_title)

        # 说明文字
        edge_snap_desc = QtWidgets.QLabel(
            self.tr("矩形边缘贴边吸附\n优先级：辅助线 > 边缘吸附")
        )
        edge_snap_desc.setWordWrap(True)
        edge_snap_desc.setStyleSheet("color: gray; font-size: 11px;")
        right_layout.addWidget(edge_snap_desc)

        # 开启/关闭边缘吸附
        self.edge_snap_checkbox = QtWidgets.QCheckBox(self.tr("开启边缘吸附"))
        self.edge_snap_checkbox.setChecked(False)
        self.edge_snap_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('edge_snap_enabled', state == Qt.Checked)
        )
        right_layout.addWidget(self.edge_snap_checkbox)

        # 分隔线
        right_layout.addWidget(self._create_separator())

        # 边缘吸附距离
        edge_snap_distance_layout = QtWidgets.QHBoxLayout()
        edge_snap_distance_label = QtWidgets.QLabel(self.tr("吸附距离:"))
        edge_snap_distance_label.setMinimumWidth(80)
        self.edge_snap_distance_spinbox = QtWidgets.QSpinBox()
        self.edge_snap_distance_spinbox.setRange(1, 200)
        self.edge_snap_distance_spinbox.setSingleStep(1)
        self.edge_snap_distance_spinbox.setValue(50)
        self.edge_snap_distance_spinbox.setToolTip(
            self.tr("在此距离内自动吸附到边缘")
        )
        self.edge_snap_distance_spinbox.valueChanged.connect(
            lambda value: self._on_setting_changed('edge_snap_distance', value)
        )
        edge_snap_distance_layout.addWidget(edge_snap_distance_label)
        edge_snap_distance_layout.addWidget(self.edge_snap_distance_spinbox)
        right_layout.addLayout(edge_snap_distance_layout)

        # 脱离吸附距离
        edge_snap_release_distance_layout = QtWidgets.QHBoxLayout()
        edge_snap_release_distance_label = QtWidgets.QLabel(self.tr("脱离吸附距离:"))
        self.edge_snap_release_distance_spinbox = QtWidgets.QSpinBox()
        self.edge_snap_release_distance_spinbox.setRange(1, 50)
        self.edge_snap_release_distance_spinbox.setSingleStep(1)
        self.edge_snap_release_distance_spinbox.setValue(3)
        self.edge_snap_release_distance_spinbox.setToolTip(
            self.tr("反方向移动超过此距离可解锁吸附（建议设置较小值，如 3-5 像素）")
        )
        self.edge_snap_release_distance_spinbox.valueChanged.connect(
            lambda value: self._on_setting_changed('edge_snap_release_distance', value)
        )
        edge_snap_release_distance_layout.addWidget(edge_snap_release_distance_label)
        edge_snap_release_distance_layout.addWidget(self.edge_snap_release_distance_spinbox)
        right_layout.addLayout(edge_snap_release_distance_layout)

        # 分隔线
        right_layout.addWidget(self._create_separator())

        # 方向控制标题
        direction_title = QtWidgets.QLabel(self.tr("<b>吸附方向</b>"))
        right_layout.addWidget(direction_title)

        # 上边缘吸附
        self.edge_snap_top_checkbox = QtWidgets.QCheckBox(self.tr("上边缘吸附"))
        self.edge_snap_top_checkbox.setChecked(True)
        self.edge_snap_top_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('edge_snap_top', state == Qt.Checked)
        )
        right_layout.addWidget(self.edge_snap_top_checkbox)

        # 下边缘吸附
        self.edge_snap_bottom_checkbox = QtWidgets.QCheckBox(self.tr("下边缘吸附"))
        self.edge_snap_bottom_checkbox.setChecked(True)
        self.edge_snap_bottom_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('edge_snap_bottom', state == Qt.Checked)
        )
        right_layout.addWidget(self.edge_snap_bottom_checkbox)

        # 左边缘吸附
        self.edge_snap_left_checkbox = QtWidgets.QCheckBox(self.tr("左边缘吸附"))
        self.edge_snap_left_checkbox.setChecked(True)
        self.edge_snap_left_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('edge_snap_left', state == Qt.Checked)
        )
        right_layout.addWidget(self.edge_snap_left_checkbox)

        # 右边缘吸附
        self.edge_snap_right_checkbox = QtWidgets.QCheckBox(self.tr("右边缘吸附"))
        self.edge_snap_right_checkbox.setChecked(True)
        self.edge_snap_right_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('edge_snap_right', state == Qt.Checked)
        )
        right_layout.addWidget(self.edge_snap_right_checkbox)

        # 分隔线
        right_layout.addWidget(self._create_separator())

        # 矩形间距线设置
        spacing_guide_title = QtWidgets.QLabel(self.tr("<b>矩形间距线</b>"))
        right_layout.addWidget(spacing_guide_title)

        # 开启/关闭间距线显示
        self.spacing_guide_checkbox = QtWidgets.QCheckBox(self.tr("开启间距线显示"))
        self.spacing_guide_checkbox.setChecked(True)
        self.spacing_guide_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('spacing_guide_enabled', state == Qt.Checked)
        )
        right_layout.addWidget(self.spacing_guide_checkbox)

        # 仅对选中矩形测距
        self.spacing_guide_selected_only_checkbox = QtWidgets.QCheckBox(
            self.tr("仅对选中矩形测距")
        )
        self.spacing_guide_selected_only_checkbox.setChecked(False)
        self.spacing_guide_selected_only_checkbox.stateChanged.connect(
            lambda state: self._on_setting_changed('spacing_guide_selected_only', state == Qt.Checked)
        )
        right_layout.addWidget(self.spacing_guide_selected_only_checkbox)

        # 间距线显示距离
        spacing_display_distance_layout = QtWidgets.QHBoxLayout()
        spacing_display_distance_label = QtWidgets.QLabel(self.tr("显示距离:"))
        spacing_display_distance_label.setMinimumWidth(80)
        self.spacing_display_distance_spinbox = QtWidgets.QSpinBox()
        self.spacing_display_distance_spinbox.setRange(1, 999999)
        self.spacing_display_distance_spinbox.setSingleStep(10)
        self.spacing_display_distance_spinbox.setValue(200)
        self.spacing_display_distance_spinbox.setSuffix(self.tr(" px"))
        self.spacing_display_distance_spinbox.valueChanged.connect(
            lambda value: self._on_setting_changed('spacing_guide_display_distance', value)
        )
        spacing_display_distance_layout.addWidget(spacing_display_distance_label)
        spacing_display_distance_layout.addWidget(self.spacing_display_distance_spinbox)
        right_layout.addLayout(spacing_display_distance_layout)

        # 最多检测的矩形数量
        spacing_max_shapes_layout = QtWidgets.QHBoxLayout()
        spacing_max_shapes_label = QtWidgets.QLabel(self.tr("最多检测矩形数:"))
        spacing_max_shapes_label.setMinimumWidth(80)
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
        right_layout.addLayout(spacing_max_shapes_layout)

        # 添加弹性空间
        right_layout.addStretch()

        # 将右侧面板添加到主布局
        main_layout.addWidget(right_widget)
    
    def _create_separator(self):
        """创建分隔线"""
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        return line

    def _on_enable_checkbox_changed(self, state):
        """辅助线显示开关改变时的回调"""
        enabled = state == Qt.Checked

        # 更新配置
        self._on_setting_changed('smart_guides_enabled', enabled)

        # 🎯 关键：当辅助线显示关闭时，禁用吸附开关
        self.enable_snap_checkbox.setEnabled(enabled)
        if not enabled:
            # 辅助线关闭时，强制关闭吸附
            self.enable_snap_checkbox.setChecked(False)

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
            elif key == 'smart_guides_enable_snap':
                self.parent.canvas.smart_guides_enable_snap = value
            elif key == 'smart_guides_show_horizontal':
                self.parent.canvas.smart_guides_show_horizontal = value
            elif key == 'smart_guides_show_vertical':
                self.parent.canvas.smart_guides_show_vertical = value
            elif key == 'smart_guides_snap_distance':
                self.parent.canvas.smart_guides_snap_distance = value
            elif key == 'smart_guides_display_distance':
                self.parent.canvas.smart_guides_display_distance = value
            elif key == 'smart_guides_max_lines':
                self.parent.canvas.smart_guides_max_lines = value
            elif key == 'smart_guides_paste_preview_enabled':
                self.parent.canvas.smart_guides_paste_preview_enabled = value
            elif key == 'smart_guides_paste_show_guides':
                self.parent.canvas.smart_guides_paste_show_guides = value
            elif key == 'smart_guides_paste_enable_snap':
                self.parent.canvas.smart_guides_paste_enable_snap = value
            elif key == 'smart_guides_paste_snap_distance':
                self.parent.canvas.smart_guides_paste_snap_distance = value
            # 🎯 辅助线方向开关（只有4条边）
            elif key == 'smart_guides_snap_left':
                self.parent.canvas.smart_guides_snap_left = value
            elif key == 'smart_guides_snap_right':
                self.parent.canvas.smart_guides_snap_right = value
            elif key == 'smart_guides_snap_top':
                self.parent.canvas.smart_guides_snap_top = value
            elif key == 'smart_guides_snap_bottom':
                self.parent.canvas.smart_guides_snap_bottom = value
            # 🎯 粘贴模式方向开关（只有4条边）
            elif key == 'smart_guides_paste_snap_left':
                self.parent.canvas.smart_guides_paste_snap_left = value
            elif key == 'smart_guides_paste_snap_right':
                self.parent.canvas.smart_guides_paste_snap_right = value
            elif key == 'smart_guides_paste_snap_top':
                self.parent.canvas.smart_guides_paste_snap_top = value
            elif key == 'smart_guides_paste_snap_bottom':
                self.parent.canvas.smart_guides_paste_snap_bottom = value
            elif key == 'edge_snap_enabled':
                self.parent.canvas.edge_snap_enabled = value
            elif key == 'edge_snap_distance':
                self.parent.canvas.edge_snap_distance = value
            elif key == 'edge_snap_release_distance':
                self.parent.canvas.edge_snap_release_distance = value
            elif key == 'edge_snap_left':
                self.parent.canvas.edge_snap_left = value
            elif key == 'edge_snap_right':
                self.parent.canvas.edge_snap_right = value
            elif key == 'edge_snap_top':
                self.parent.canvas.edge_snap_top = value
            elif key == 'edge_snap_bottom':
                self.parent.canvas.edge_snap_bottom = value
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
        guides_enabled = self._config.get('smart_guides_enabled', True)
        self.enable_checkbox.setChecked(guides_enabled)

        # 🎯 根据辅助线显示状态，设置吸附开关的启用状态
        self.enable_snap_checkbox.setEnabled(guides_enabled)
        self.enable_snap_checkbox.setChecked(
            self._config.get('smart_guides_enable_snap', True)
        )

        # 🎯 加载辅助线方向显示开关
        self.show_horizontal_checkbox.setChecked(
            self._config.get('smart_guides_show_horizontal', True)
        )
        self.show_vertical_checkbox.setChecked(
            self._config.get('smart_guides_show_vertical', True)
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
        self.paste_show_guides_checkbox.setChecked(
            self._config.get('smart_guides_paste_show_guides', True)
        )
        self.paste_enable_snap_checkbox.setChecked(
            self._config.get('smart_guides_paste_enable_snap', True)
        )
        self.paste_snap_distance_spinbox.setValue(
            self._config.get('smart_guides_paste_snap_distance', 10)
        )

        # 🎯 加载辅助线方向开关（只有4条边）
        self.snap_left_checkbox.setChecked(
            self._config.get('smart_guides_snap_left', True)
        )
        self.snap_right_checkbox.setChecked(
            self._config.get('smart_guides_snap_right', True)
        )
        self.snap_top_checkbox.setChecked(
            self._config.get('smart_guides_snap_top', True)
        )
        self.snap_bottom_checkbox.setChecked(
            self._config.get('smart_guides_snap_bottom', True)
        )

        # 🎯 加载粘贴模式方向开关（只有4条边）
        self.paste_snap_left_checkbox.setChecked(
            self._config.get('smart_guides_paste_snap_left', True)
        )
        self.paste_snap_right_checkbox.setChecked(
            self._config.get('smart_guides_paste_snap_right', True)
        )
        self.paste_snap_top_checkbox.setChecked(
            self._config.get('smart_guides_paste_snap_top', True)
        )
        self.paste_snap_bottom_checkbox.setChecked(
            self._config.get('smart_guides_paste_snap_bottom', True)
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

        # 加载边缘吸附设置到控件
        self.edge_snap_checkbox.setChecked(
            self._config.get('edge_snap_enabled', False)
        )
        self.edge_snap_distance_spinbox.setValue(
            self._config.get('edge_snap_distance', 50)
        )
        self.edge_snap_release_distance_spinbox.setValue(
            self._config.get('edge_snap_release_distance', 3)
        )
        self.edge_snap_left_checkbox.setChecked(
            self._config.get('edge_snap_left', True)
        )
        self.edge_snap_right_checkbox.setChecked(
            self._config.get('edge_snap_right', True)
        )
        self.edge_snap_top_checkbox.setChecked(
            self._config.get('edge_snap_top', True)
        )
        self.edge_snap_bottom_checkbox.setChecked(
            self._config.get('edge_snap_bottom', True)
        )

        # 手动同步到 canvas（因为 setChecked/setValue 不会触发信号）
        if self.parent and hasattr(self.parent, 'canvas'):
            self.parent.canvas.smart_guides_enabled = self._config.get('smart_guides_enabled', True)
            self.parent.canvas.smart_guides_show_horizontal = self._config.get('smart_guides_show_horizontal', True)
            self.parent.canvas.smart_guides_show_vertical = self._config.get('smart_guides_show_vertical', True)
            self.parent.canvas.smart_guides_snap_distance = self._config.get('smart_guides_snap_distance', 10)
            self.parent.canvas.smart_guides_display_distance = self._config.get('smart_guides_display_distance', 100)
            self.parent.canvas.smart_guides_max_lines = self._config.get('smart_guides_max_lines', 10)
            self.parent.canvas.smart_guides_paste_preview_enabled = self._config.get('smart_guides_paste_preview_enabled', True)
            self.parent.canvas.smart_guides_paste_show_guides = self._config.get('smart_guides_paste_show_guides', True)
            self.parent.canvas.smart_guides_paste_enable_snap = self._config.get('smart_guides_paste_enable_snap', True)
            self.parent.canvas.smart_guides_paste_snap_distance = self._config.get('smart_guides_paste_snap_distance', 10)

            # 🎯 同步辅助线方向开关（只有4条边）
            self.parent.canvas.smart_guides_snap_left = self._config.get('smart_guides_snap_left', True)
            self.parent.canvas.smart_guides_snap_right = self._config.get('smart_guides_snap_right', True)
            self.parent.canvas.smart_guides_snap_top = self._config.get('smart_guides_snap_top', True)
            self.parent.canvas.smart_guides_snap_bottom = self._config.get('smart_guides_snap_bottom', True)

            # 🎯 同步粘贴模式方向开关（只有4条边）
            self.parent.canvas.smart_guides_paste_snap_left = self._config.get('smart_guides_paste_snap_left', True)
            self.parent.canvas.smart_guides_paste_snap_right = self._config.get('smart_guides_paste_snap_right', True)
            self.parent.canvas.smart_guides_paste_snap_top = self._config.get('smart_guides_paste_snap_top', True)
            self.parent.canvas.smart_guides_paste_snap_bottom = self._config.get('smart_guides_paste_snap_bottom', True)

            # 同步间距线设置
            self.parent.canvas.spacing_guide_enabled = self._config.get('spacing_guide_enabled', True)
            self.parent.canvas.spacing_guide_selected_only = self._config.get('spacing_guide_selected_only', False)
            self.parent.canvas.spacing_guide_display_distance = self._config.get('spacing_guide_display_distance', 200)
            self.parent.canvas.spacing_guide_max_shapes = self._config.get('spacing_guide_max_shapes', 0)
            # 注意：spacing_guide_line_color 和 spacing_guide_opacity 现在由颜色管理器处理

            # 同步边缘吸附设置
            self.parent.canvas.edge_snap_enabled = self._config.get('edge_snap_enabled', False)
            self.parent.canvas.edge_snap_distance = self._config.get('edge_snap_distance', 50)
            self.parent.canvas.edge_snap_release_distance = self._config.get('edge_snap_release_distance', 3)
            self.parent.canvas.edge_snap_left = self._config.get('edge_snap_left', True)
            self.parent.canvas.edge_snap_right = self._config.get('edge_snap_right', True)
            self.parent.canvas.edge_snap_top = self._config.get('edge_snap_top', True)
            self.parent.canvas.edge_snap_bottom = self._config.get('edge_snap_bottom', True)

            self.parent.canvas.update()

