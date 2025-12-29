from PyQt5 import QtWidgets, QtCore
from anylabeling.config import save_config

class HighlightSettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, config=None):
        super(HighlightSettingsDialog, self).__init__(parent)
        self.setWindowTitle("高亮与锁定设置")

        self._config = config

        # 主布局使用水平布局，分为左右两列
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 左列容器
        self.left_widget = QtWidgets.QWidget()
        self.left_column = QtWidgets.QVBoxLayout(self.left_widget)
        self.left_column.setContentsMargins(0, 0, 0, 0)
        self.left_column.setSpacing(5)
        
        # 右列容器
        self.right_widget = QtWidgets.QWidget()
        self.right_column = QtWidgets.QVBoxLayout(self.right_widget)
        self.right_column.setContentsMargins(0, 0, 0, 0)
        self.right_column.setSpacing(5)

        # ========== 左列内容 ==========
        
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
        self.lock_hide_order_checkbox = QtWidgets.QCheckBox("锁定后不显示序号")
        self.lock_hide_order_checkbox.setToolTip("启用后，锁定的标签不参与序号排序和显示")
        self.lock_hide_order_checkbox.setChecked(True)
        self.lock_show_point_checkbox = QtWidgets.QCheckBox("锁定后显示点 (圆形)")
        self.lock_show_point_checkbox.setToolTip("启用后，锁定的标签显示顶点圆形控制柄")
        self.lock_show_square_checkbox = QtWidgets.QCheckBox("锁定后显示块 (方形)")
        self.lock_show_square_checkbox.setToolTip("启用后，锁定的标签显示方形控制柄")
        self.lock_layout.addWidget(self.lock_label)
        self.lock_layout.addWidget(self.lock_input)
        self.lock_layout.addWidget(self.lock_highlight_checkbox)
        self.lock_layout.addWidget(self.lock_hide_info_checkbox)
        self.lock_layout.addWidget(self.lock_hide_order_checkbox)
        self.lock_layout.addWidget(self.lock_show_point_checkbox)
        self.lock_layout.addWidget(self.lock_show_square_checkbox)
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

        # 画布内信息显示设置（移到左列）
        self.canvas_overlay_group = QtWidgets.QGroupBox("画布内信息显示")
        self.canvas_overlay_layout = QtWidgets.QVBoxLayout()
        self.canvas_overlay_enabled_checkbox = QtWidgets.QCheckBox("启用画布内坐标显示")
        self.canvas_overlay_enabled_checkbox.setToolTip("启用后，在画布角落显示鼠标坐标和选中矩形信息")
        
        # 位置选择
        self.canvas_overlay_position_layout = QtWidgets.QHBoxLayout()
        self.canvas_overlay_position_label = QtWidgets.QLabel("显示位置:")
        self.canvas_overlay_position_combo = QtWidgets.QComboBox()
        self.canvas_overlay_position_combo.addItem("左下角", "bottom_left")
        self.canvas_overlay_position_combo.addItem("左上角", "top_left")
        self.canvas_overlay_position_layout.addWidget(self.canvas_overlay_position_label)
        self.canvas_overlay_position_layout.addWidget(self.canvas_overlay_position_combo)
        self.canvas_overlay_position_layout.addStretch()
        
        self.canvas_overlay_layout.addWidget(self.canvas_overlay_enabled_checkbox)
        self.canvas_overlay_layout.addLayout(self.canvas_overlay_position_layout)
        self.canvas_overlay_group.setLayout(self.canvas_overlay_layout)

        # 画布平移设置
        self.canvas_pan_group = QtWidgets.QGroupBox("画布平移")
        self.canvas_pan_layout = QtWidgets.QVBoxLayout()
        self.canvas_pan_enabled_checkbox = QtWidgets.QCheckBox("启用PS风格画布平移")
        self.canvas_pan_enabled_checkbox.setToolTip("启用后，图片的任意角落都可以拖到视口中央（类似Photoshop）\n禁用后，恢复原来的平移限制")
        self.canvas_pan_layout.addWidget(self.canvas_pan_enabled_checkbox)
        self.canvas_pan_group.setLayout(self.canvas_pan_layout)

        # 添加到左列
        self.left_column.addWidget(self.positive_group)
        self.left_column.addWidget(self.negative_group)
        self.left_column.addWidget(self.lock_group)
        self.left_column.addWidget(self.pin_group)
        self.left_column.addWidget(self.no_highlight_group)
        self.left_column.addWidget(self.canvas_overlay_group)
        self.left_column.addWidget(self.canvas_pan_group)
        self.left_column.addStretch()

        # ========== 右列内容 ==========

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
        self.highlight_use_border_color_checkbox = QtWidgets.QCheckBox("高亮时直接进入状态5")
        self.highlight_use_border_color_checkbox.setToolTip(
            "勾选后，高亮时直接进入状态5：\n"
            "- 填充色消失\n"
            "- 保留独立边框颜色和宽度\n"
            "（无需先点击矩形再移开鼠标）"
        )
        self.default_highlight_layout.addWidget(self.default_highlight_checkbox)
        self.default_highlight_layout.addWidget(self.highlight_use_border_color_checkbox)
        self.default_highlight_group.setLayout(self.default_highlight_layout)

        # Control Handle Display Settings
        self.handle_group = QtWidgets.QGroupBox("控制柄显示设置")
        self.handle_layout = QtWidgets.QVBoxLayout()
        
        self.handle_highlight_label = QtWidgets.QLabel("高亮时:")
        self.handle_highlight_point_checkbox = QtWidgets.QCheckBox("显示点 (圆形)")
        self.handle_highlight_square_checkbox = QtWidgets.QCheckBox("显示块 (方形)")
        self.handle_highlight_point_checkbox.setChecked(True)
        self.handle_highlight_square_checkbox.setChecked(True)
        
        self.handle_normal_label = QtWidgets.QLabel("非高亮时:")
        self.handle_normal_point_checkbox = QtWidgets.QCheckBox("显示点 (圆形)")
        self.handle_normal_square_checkbox = QtWidgets.QCheckBox("显示块 (方形)")
        self.handle_normal_point_checkbox.setChecked(False)
        self.handle_normal_square_checkbox.setChecked(False)
        
        self.handle_detect_chaotic_checkbox = QtWidgets.QCheckBox("检测点击高亮后的非高亮状态")
        self.handle_detect_chaotic_checkbox.setToolTip("勾选后，高亮状态下被点击过的图形会使用非高亮时的设置")
        self.handle_detect_chaotic_checkbox.setChecked(True)
        
        self.handle_layout.addWidget(self.handle_highlight_label)
        self.handle_layout.addWidget(self.handle_highlight_point_checkbox)
        self.handle_layout.addWidget(self.handle_highlight_square_checkbox)
        self.handle_layout.addWidget(self.handle_normal_label)
        self.handle_layout.addWidget(self.handle_normal_point_checkbox)
        self.handle_layout.addWidget(self.handle_normal_square_checkbox)
        self.handle_layout.addWidget(self.handle_detect_chaotic_checkbox)
        self.handle_group.setLayout(self.handle_layout)

        # 取消功能增强设置
        self.deselect_group = QtWidgets.QGroupBox("取消功能增强")
        self.deselect_layout = QtWidgets.QVBoxLayout()
        self.deselect_exclude_locked_checkbox = QtWidgets.QCheckBox("排除锁定的标签")
        self.deselect_exclude_locked_checkbox.setToolTip("勾选后，点击取消按钮时不会取消锁定标签的勾选")
        self.deselect_exclude_locked_checkbox.setChecked(True)
        self.deselect_even_checkbox = QtWidgets.QCheckBox("按偶数取消")
        self.deselect_even_checkbox.setToolTip("勾选后，只取消偶数位置的项目（2, 4, 6...）")
        self.deselect_odd_checkbox = QtWidgets.QCheckBox("按奇数取消")
        self.deselect_odd_checkbox.setToolTip("勾选后，只取消奇数位置的项目（1, 3, 5...）")
        self.deselect_layout.addWidget(self.deselect_exclude_locked_checkbox)
        self.deselect_layout.addWidget(self.deselect_even_checkbox)
        self.deselect_layout.addWidget(self.deselect_odd_checkbox)
        self.deselect_group.setLayout(self.deselect_layout)

        # 反选功能增强设置
        self.invert_group = QtWidgets.QGroupBox("反选功能增强")
        self.invert_layout = QtWidgets.QVBoxLayout()
        self.invert_exclude_locked_checkbox = QtWidgets.QCheckBox("排除锁定的标签")
        self.invert_exclude_locked_checkbox.setToolTip("勾选后，点击反选按钮时锁定的标签不参与反选")
        self.invert_exclude_locked_checkbox.setChecked(True)
        self.invert_layout.addWidget(self.invert_exclude_locked_checkbox)
        self.invert_group.setLayout(self.invert_layout)

        # 重叠检测设置
        self.overlap_group = QtWidgets.QGroupBox("重叠检测")
        self.overlap_layout = QtWidgets.QVBoxLayout()
        self.overlap_enabled_checkbox = QtWidgets.QCheckBox("启用重叠检测")
        self.overlap_enabled_checkbox.setToolTip("启用后，当矩形重叠率达到阈值时，在矩形内部上方显示重叠数量")
        self.overlap_exclude_locked_checkbox = QtWidgets.QCheckBox("排除锁定的标签")
        self.overlap_exclude_locked_checkbox.setToolTip("勾选后，锁定的标签不参与重叠检测")
        self.overlap_exclude_locked_checkbox.setChecked(True)
        
        # 排除标签输入框
        self.overlap_exclude_labels_label = QtWidgets.QLabel("排除的标签 (英文逗号分隔):")
        self.overlap_exclude_labels_input = QtWidgets.QLineEdit()
        self.overlap_exclude_labels_input.setToolTip("输入要排除的标签名称，多个标签用英文逗号分隔")
        
        # 重叠率阈值设置
        self.overlap_threshold_layout = QtWidgets.QHBoxLayout()
        self.overlap_threshold_label = QtWidgets.QLabel("重叠率阈值:")
        self.overlap_threshold_spin = QtWidgets.QSpinBox()
        self.overlap_threshold_spin.setRange(1, 100)
        self.overlap_threshold_spin.setValue(50)
        self.overlap_threshold_spin.setSuffix("%")
        self.overlap_threshold_spin.setToolTip("两个矩形的交集面积占较小矩形面积的百分比达到此值时，视为重叠")
        self.overlap_threshold_layout.addWidget(self.overlap_threshold_label)
        self.overlap_threshold_layout.addWidget(self.overlap_threshold_spin)
        self.overlap_threshold_layout.addStretch()
        
        self.overlap_layout.addWidget(self.overlap_enabled_checkbox)
        self.overlap_layout.addWidget(self.overlap_exclude_locked_checkbox)
        self.overlap_layout.addWidget(self.overlap_exclude_labels_label)
        self.overlap_layout.addWidget(self.overlap_exclude_labels_input)
        self.overlap_layout.addLayout(self.overlap_threshold_layout)
        self.overlap_group.setLayout(self.overlap_layout)

        # 添加到右列
        self.right_column.addWidget(self.mixed_mode_group)
        self.right_column.addWidget(self.default_highlight_group)
        self.right_column.addWidget(self.handle_group)
        self.right_column.addWidget(self.deselect_group)
        self.right_column.addWidget(self.invert_group)
        self.right_column.addWidget(self.overlap_group)

        # 右列底部添加弹簧
        self.right_column.addStretch()

        # 将左右列添加到主布局
        self.main_layout.addWidget(self.left_widget)
        self.main_layout.addWidget(self.right_widget)

        # 设置窗口大小策略，让窗口自动适应内容
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.adjustSize()

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
        self.lock_hide_order_checkbox.stateChanged.connect(self._realtime_save_settings)
        self.lock_show_point_checkbox.stateChanged.connect(self._on_lock_handle_setting_changed)
        self.lock_show_square_checkbox.stateChanged.connect(self._on_lock_handle_setting_changed)
        self.pin_input.textChanged.connect(self._realtime_save_settings)
        self.no_highlight_input.textChanged.connect(self._realtime_save_settings)
        self.mixed_mode_checkbox.stateChanged.connect(self._realtime_save_settings)
        self.default_highlight_checkbox.stateChanged.connect(self._on_default_highlight_changed)
        self.highlight_use_border_color_checkbox.stateChanged.connect(self._on_highlight_border_setting_changed)
        
        self.handle_highlight_point_checkbox.stateChanged.connect(self._on_handle_setting_changed)
        self.handle_highlight_square_checkbox.stateChanged.connect(self._on_handle_setting_changed)
        self.handle_normal_point_checkbox.stateChanged.connect(self._on_handle_setting_changed)
        self.handle_normal_square_checkbox.stateChanged.connect(self._on_handle_setting_changed)
        self.handle_detect_chaotic_checkbox.stateChanged.connect(self._on_handle_setting_changed)
        
        self.deselect_exclude_locked_checkbox.stateChanged.connect(self._on_deselect_setting_changed)
        self.deselect_even_checkbox.stateChanged.connect(self._on_deselect_setting_changed)
        self.deselect_odd_checkbox.stateChanged.connect(self._on_deselect_setting_changed)
        self.deselect_even_checkbox.stateChanged.connect(self._on_even_odd_exclusive)
        self.deselect_odd_checkbox.stateChanged.connect(self._on_even_odd_exclusive)
        
        self.invert_exclude_locked_checkbox.stateChanged.connect(self._on_invert_setting_changed)
        
        # 重叠检测设置信号连接
        self.overlap_enabled_checkbox.stateChanged.connect(self._on_overlap_setting_changed)
        self.overlap_exclude_locked_checkbox.stateChanged.connect(self._on_overlap_setting_changed)
        self.overlap_exclude_labels_input.textChanged.connect(self._on_overlap_setting_changed)
        self.overlap_threshold_spin.valueChanged.connect(self._on_overlap_setting_changed)

        # 画布内信息显示设置信号连接
        self.canvas_overlay_enabled_checkbox.stateChanged.connect(self._on_canvas_overlay_setting_changed)
        self.canvas_overlay_position_combo.currentIndexChanged.connect(self._on_canvas_overlay_setting_changed)

        # 画布平移设置信号连接
        self.canvas_pan_enabled_checkbox.stateChanged.connect(self._on_canvas_pan_setting_changed)

        self.load_settings()

    def load_settings(self):
        if self._config:
            self.positive_input.textChanged.disconnect(self._realtime_save_settings)
            self.negative_input.textChanged.disconnect(self._realtime_save_settings)
            self.lock_input.textChanged.disconnect(self._realtime_save_settings)
            self.lock_highlight_checkbox.stateChanged.disconnect(self._realtime_save_settings)
            self.lock_hide_info_checkbox.stateChanged.disconnect(self._realtime_save_settings)
            self.lock_hide_order_checkbox.stateChanged.disconnect(self._realtime_save_settings)
            self.lock_show_point_checkbox.stateChanged.disconnect(self._on_lock_handle_setting_changed)
            self.lock_show_square_checkbox.stateChanged.disconnect(self._on_lock_handle_setting_changed)
            self.pin_input.textChanged.disconnect(self._realtime_save_settings)
            self.no_highlight_input.textChanged.disconnect(self._realtime_save_settings)
            self.mixed_mode_checkbox.stateChanged.disconnect(self._realtime_save_settings)
            self.default_highlight_checkbox.stateChanged.disconnect(self._on_default_highlight_changed)
            self.highlight_use_border_color_checkbox.stateChanged.disconnect(self._on_highlight_border_setting_changed)
            self.handle_highlight_point_checkbox.stateChanged.disconnect(self._on_handle_setting_changed)
            self.handle_highlight_square_checkbox.stateChanged.disconnect(self._on_handle_setting_changed)
            self.handle_normal_point_checkbox.stateChanged.disconnect(self._on_handle_setting_changed)
            self.handle_normal_square_checkbox.stateChanged.disconnect(self._on_handle_setting_changed)
            self.handle_detect_chaotic_checkbox.stateChanged.disconnect(self._on_handle_setting_changed)
            self.deselect_exclude_locked_checkbox.stateChanged.disconnect(self._on_deselect_setting_changed)
            self.deselect_even_checkbox.stateChanged.disconnect(self._on_deselect_setting_changed)
            self.deselect_odd_checkbox.stateChanged.disconnect(self._on_deselect_setting_changed)
            self.deselect_even_checkbox.stateChanged.disconnect(self._on_even_odd_exclusive)
            self.deselect_odd_checkbox.stateChanged.disconnect(self._on_even_odd_exclusive)
            self.invert_exclude_locked_checkbox.stateChanged.disconnect(self._on_invert_setting_changed)
            self.overlap_enabled_checkbox.stateChanged.disconnect(self._on_overlap_setting_changed)
            self.overlap_exclude_locked_checkbox.stateChanged.disconnect(self._on_overlap_setting_changed)
            self.overlap_exclude_labels_input.textChanged.disconnect(self._on_overlap_setting_changed)
            self.overlap_threshold_spin.valueChanged.disconnect(self._on_overlap_setting_changed)
            self.canvas_overlay_enabled_checkbox.stateChanged.disconnect(self._on_canvas_overlay_setting_changed)
            self.canvas_overlay_position_combo.currentIndexChanged.disconnect(self._on_canvas_overlay_setting_changed)
            self.canvas_pan_enabled_checkbox.stateChanged.disconnect(self._on_canvas_pan_setting_changed)

            self.positive_input.setText(self._config.get("highlight_positive", ""))
            self.negative_input.setText(self._config.get("highlight_negative", ""))
            self.lock_input.setText(self._config.get("locked_labels", ""))
            self.lock_highlight_checkbox.setChecked(self._config.get("locked_can_highlight", False))
            self.lock_hide_info_checkbox.setChecked(self._config.get("locked_hide_info", False))
            self.lock_hide_order_checkbox.setChecked(self._config.get("locked_hide_order", True))
            self.lock_show_point_checkbox.setChecked(self._config.get("locked_show_point", False))
            self.lock_show_square_checkbox.setChecked(self._config.get("locked_show_square", False))
            self.pin_input.setText(self._config.get("pin_labels", ""))
            self.no_highlight_input.setText(self._config.get("no_highlight_labels", ""))
            self.mixed_mode_checkbox.setChecked(self._config.get("highlight_mixed_mode", False))
            self.default_highlight_checkbox.setChecked(self._config.get("highlight_enabled_by_default", True))
            self.highlight_use_border_color_checkbox.setChecked(self._config.get("highlight_use_border_color", False))
            
            self.handle_highlight_point_checkbox.setChecked(self._config.get("handle_highlight_point", True))
            self.handle_highlight_square_checkbox.setChecked(self._config.get("handle_highlight_square", True))
            self.handle_normal_point_checkbox.setChecked(self._config.get("handle_normal_point", False))
            self.handle_normal_square_checkbox.setChecked(self._config.get("handle_normal_square", False))
            self.handle_detect_chaotic_checkbox.setChecked(self._config.get("handle_detect_chaotic", True))
            
            self.deselect_exclude_locked_checkbox.setChecked(self._config.get("deselect_exclude_locked", True))
            deselect_even = self._config.get("deselect_even", False)
            deselect_odd = self._config.get("deselect_odd", False)
            if deselect_even and deselect_odd:
                deselect_even = False
                deselect_odd = False
                self._config["deselect_even"] = False
                self._config["deselect_odd"] = False
            self.deselect_even_checkbox.setChecked(deselect_even)
            self.deselect_odd_checkbox.setChecked(deselect_odd)
            
            self.invert_exclude_locked_checkbox.setChecked(self._config.get("invert_exclude_locked", True))
            
            # 重叠检测设置
            self.overlap_enabled_checkbox.setChecked(self._config.get("overlap_detect_enabled", False))
            self.overlap_exclude_locked_checkbox.setChecked(self._config.get("overlap_exclude_locked", True))
            self.overlap_exclude_labels_input.setText(self._config.get("overlap_exclude_labels", ""))
            self.overlap_threshold_spin.setValue(self._config.get("overlap_detect_threshold", 50))

            # 画布内信息显示设置
            self.canvas_overlay_enabled_checkbox.setChecked(self._config.get("canvas_overlay_info_enabled", False))
            # 设置位置下拉框
            position = self._config.get("canvas_overlay_position", "bottom_left")
            index = self.canvas_overlay_position_combo.findData(position)
            if index >= 0:
                self.canvas_overlay_position_combo.setCurrentIndex(index)

            # 画布平移设置
            self.canvas_pan_enabled_checkbox.setChecked(self._config.get("canvas_pan_ps_style", True))

            self.positive_input.textChanged.connect(self._realtime_save_settings)
            self.negative_input.textChanged.connect(self._realtime_save_settings)
            self.lock_input.textChanged.connect(self._realtime_save_settings)
            self.lock_highlight_checkbox.stateChanged.connect(self._realtime_save_settings)
            self.lock_hide_info_checkbox.stateChanged.connect(self._realtime_save_settings)
            self.lock_hide_order_checkbox.stateChanged.connect(self._realtime_save_settings)
            self.lock_show_point_checkbox.stateChanged.connect(self._on_lock_handle_setting_changed)
            self.lock_show_square_checkbox.stateChanged.connect(self._on_lock_handle_setting_changed)
            self.pin_input.textChanged.connect(self._realtime_save_settings)
            self.no_highlight_input.textChanged.connect(self._realtime_save_settings)
            self.mixed_mode_checkbox.stateChanged.connect(self._realtime_save_settings)
            self.default_highlight_checkbox.stateChanged.connect(self._on_default_highlight_changed)
            self.highlight_use_border_color_checkbox.stateChanged.connect(self._on_highlight_border_setting_changed)
            self.handle_highlight_point_checkbox.stateChanged.connect(self._on_handle_setting_changed)
            self.handle_highlight_square_checkbox.stateChanged.connect(self._on_handle_setting_changed)
            self.handle_normal_point_checkbox.stateChanged.connect(self._on_handle_setting_changed)
            self.handle_normal_square_checkbox.stateChanged.connect(self._on_handle_setting_changed)
            self.handle_detect_chaotic_checkbox.stateChanged.connect(self._on_handle_setting_changed)
            self.deselect_exclude_locked_checkbox.stateChanged.connect(self._on_deselect_setting_changed)
            self.deselect_even_checkbox.stateChanged.connect(self._on_deselect_setting_changed)
            self.deselect_odd_checkbox.stateChanged.connect(self._on_deselect_setting_changed)
            self.deselect_even_checkbox.stateChanged.connect(self._on_even_odd_exclusive)
            self.deselect_odd_checkbox.stateChanged.connect(self._on_even_odd_exclusive)
            self.invert_exclude_locked_checkbox.stateChanged.connect(self._on_invert_setting_changed)
            self.overlap_enabled_checkbox.stateChanged.connect(self._on_overlap_setting_changed)
            self.overlap_exclude_locked_checkbox.stateChanged.connect(self._on_overlap_setting_changed)
            self.overlap_exclude_labels_input.textChanged.connect(self._on_overlap_setting_changed)
            self.overlap_threshold_spin.valueChanged.connect(self._on_overlap_setting_changed)
            self.canvas_overlay_enabled_checkbox.stateChanged.connect(self._on_canvas_overlay_setting_changed)
            self.canvas_overlay_position_combo.currentIndexChanged.connect(self._on_canvas_overlay_setting_changed)
            self.canvas_pan_enabled_checkbox.stateChanged.connect(self._on_canvas_pan_setting_changed)

    def _realtime_save_settings(self):
        if self._config:
            self._config["highlight_positive"] = self.positive_input.text()
            self._config["highlight_negative"] = self.negative_input.text()
            self._config["locked_labels"] = self.lock_input.text()
            self._config["locked_can_highlight"] = self.lock_highlight_checkbox.isChecked()
            self._config["locked_hide_info"] = self.lock_hide_info_checkbox.isChecked()
            self._config["locked_hide_order"] = self.lock_hide_order_checkbox.isChecked()
            self._config["pin_labels"] = self.pin_input.text()
            self._config["no_highlight_labels"] = self.no_highlight_input.text()
            self._config["highlight_mixed_mode"] = self.mixed_mode_checkbox.isChecked()
            save_config(self._config)
            if self.parent() and hasattr(self.parent(), 'apply_handle_display_settings'):
                self.parent().apply_handle_display_settings()

    def _on_default_highlight_changed(self, state):
        if self._config:
            is_enabled = self.default_highlight_checkbox.isChecked()
            self._config["highlight_enabled_by_default"] = is_enabled
            save_config(self._config)
            if self.parent() and hasattr(self.parent(), 'apply_default_highlight_setting'):
                self.parent().apply_default_highlight_setting(is_enabled)

    def _on_highlight_border_setting_changed(self, state):
        if self._config:
            is_enabled = self.highlight_use_border_color_checkbox.isChecked()
            self._config["highlight_use_border_color"] = is_enabled
            save_config(self._config)
            if self.parent() and hasattr(self.parent(), 'apply_highlight_border_setting'):
                self.parent().apply_highlight_border_setting(is_enabled)

    def _on_handle_setting_changed(self, state):
        if self._config:
            self._config["handle_highlight_point"] = self.handle_highlight_point_checkbox.isChecked()
            self._config["handle_highlight_square"] = self.handle_highlight_square_checkbox.isChecked()
            self._config["handle_normal_point"] = self.handle_normal_point_checkbox.isChecked()
            self._config["handle_normal_square"] = self.handle_normal_square_checkbox.isChecked()
            self._config["handle_detect_chaotic"] = self.handle_detect_chaotic_checkbox.isChecked()
            save_config(self._config)
            if self.parent() and hasattr(self.parent(), 'apply_handle_display_settings'):
                self.parent().apply_handle_display_settings()

    def _on_lock_handle_setting_changed(self, state):
        if self._config:
            self._config["locked_show_point"] = self.lock_show_point_checkbox.isChecked()
            self._config["locked_show_square"] = self.lock_show_square_checkbox.isChecked()
            save_config(self._config)
            if self.parent() and hasattr(self.parent(), 'apply_handle_display_settings'):
                self.parent().apply_handle_display_settings()

    def _on_deselect_setting_changed(self, state):
        if self._config:
            self._config["deselect_exclude_locked"] = self.deselect_exclude_locked_checkbox.isChecked()
            self._config["deselect_even"] = self.deselect_even_checkbox.isChecked()
            self._config["deselect_odd"] = self.deselect_odd_checkbox.isChecked()
            save_config(self._config)

    def _on_invert_setting_changed(self, state):
        if self._config:
            self._config["invert_exclude_locked"] = self.invert_exclude_locked_checkbox.isChecked()
            save_config(self._config)

    def _on_even_odd_exclusive(self, state):
        sender = self.sender()
        if state == QtCore.Qt.Checked:
            if sender == self.deselect_even_checkbox:
                self.deselect_odd_checkbox.blockSignals(True)
                self.deselect_odd_checkbox.setChecked(False)
                self.deselect_odd_checkbox.blockSignals(False)
            elif sender == self.deselect_odd_checkbox:
                self.deselect_even_checkbox.blockSignals(True)
                self.deselect_even_checkbox.setChecked(False)
                self.deselect_even_checkbox.blockSignals(False)

    def _on_overlap_setting_changed(self, state=None):
        if self._config:
            self._config["overlap_detect_enabled"] = self.overlap_enabled_checkbox.isChecked()
            self._config["overlap_exclude_locked"] = self.overlap_exclude_locked_checkbox.isChecked()
            self._config["overlap_exclude_labels"] = self.overlap_exclude_labels_input.text()
            self._config["overlap_detect_threshold"] = self.overlap_threshold_spin.value()
            save_config(self._config)
            if self.parent() and hasattr(self.parent(), 'canvas'):
                self.parent().canvas.update()

    def _on_canvas_overlay_setting_changed(self, state=None):
        if self._config:
            self._config["canvas_overlay_info_enabled"] = self.canvas_overlay_enabled_checkbox.isChecked()
            self._config["canvas_overlay_position"] = self.canvas_overlay_position_combo.currentData()
            save_config(self._config)
            # Update overlay position
            if self.parent() and hasattr(self.parent(), '_update_canvas_overlay_on_shape_change'):
                self.parent()._update_canvas_overlay_on_shape_change()

    def _on_canvas_pan_setting_changed(self, state=None):
        if self._config:
            is_enabled = self.canvas_pan_enabled_checkbox.isChecked()
            self._config["canvas_pan_ps_style"] = is_enabled
            save_config(self._config)
            # Update canvas pan mode
            if self.parent() and hasattr(self.parent(), 'canvas'):
                self.parent().canvas.set_pan_ps_style(is_enabled)

    def showEvent(self, event):
        super().showEvent(event)
        self.load_settings()
