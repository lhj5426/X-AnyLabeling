from PyQt5 import QtWidgets, QtCore
from anylabeling.config import get_config, save_config
import os
import yaml


class MergeDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.setWindowTitle("区域合并工具设置")
        self.setMinimumWidth(650)  # 缩小宽度
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)
        self.adjustSize()
        # 设置窗口标志：移除帮助按钮,添加最小化按钮
        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.WindowMinimizeButtonHint |
            QtCore.Qt.WindowMaximizeButtonHint |
            QtCore.Qt.WindowCloseButtonHint
        )
        
        # 运行期间临时保存的窗口位置（不写入配置文件）
        self.saved_geometry = None

        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setSpacing(6)
        self.layout.setContentsMargins(8, 8, 8, 8)
        
        # 创建左右两栏布局
        main_content_layout = QtWidgets.QHBoxLayout()
        
        # 左侧栏
        left_column = QtWidgets.QVBoxLayout()
        
        # 右侧栏
        right_column = QtWidgets.QVBoxLayout()

        # --- Mappings for translation ---
        self.merge_mode_map = {
            self.tr("垂直合并"): "VERTICAL",
            self.tr("水平合并"): "HORIZONTAL",
            self.tr("先垂直后水平"): "VERTICAL_THEN_HORIZONTAL",
            self.tr("先水平后垂直"): "HORIZONTAL_THEN_VERTICAL",
            self.tr("无"): "NONE",
        }
        self.label_strategy_map = {
            self.tr("优先使用较短的标签"): "PREFER_SHORTER",
            self.tr("使用第一个框的标签"): "FIRST",
            self.tr("组合标签 (label1+label2)"): "COMBINE",
            self.tr("优先使用非默认标签"): "PREFER_NON_DEFAULT",
        }

        # --- Main Settings --- #
        main_group = QtWidgets.QGroupBox("主要设置")
        main_layout = QtWidgets.QFormLayout(main_group)
        main_layout.setSpacing(4)
        main_layout.setContentsMargins(8, 6, 8, 6)

        self.merge_mode = QtWidgets.QComboBox()
        for text, data in self.merge_mode_map.items():
            self.merge_mode.addItem(text, userData=data)
        main_layout.addRow("合并模式:", self.merge_mode)
        left_column.addWidget(main_group)

        # --- Text Reading Order Settings ---
        reading_order_group = QtWidgets.QGroupBox("文本合并顺序")
        reading_order_layout = QtWidgets.QFormLayout(reading_order_group)
        reading_order_layout.setSpacing(4)
        reading_order_layout.setContentsMargins(8, 6, 8, 6)
        
        self.ltr_labels_edit = QtWidgets.QLineEdit()
        self.ltr_labels_edit.setPlaceholderText("标签1,标签2,...")
        self.rtl_labels_edit = QtWidgets.QLineEdit()
        self.rtl_labels_edit.setText("balloon,qipao,shuqing")
        self.ttb_labels_edit = QtWidgets.QLineEdit()
        self.ttb_labels_edit.setText("changfangtiao,hengxie")

        reading_order_layout.addRow("从左到右 (LTR) 标签:", self.ltr_labels_edit)
        reading_order_layout.addRow("从右到左 (RTL) 标签:", self.rtl_labels_edit)
        reading_order_layout.addRow("从上到下 (TTB) 标签:", self.ttb_labels_edit)
        
        left_column.addWidget(reading_order_group)

        # --- Labeling Rules --- #
        label_group = QtWidgets.QGroupBox("标签合并规则")
        label_layout = QtWidgets.QFormLayout(label_group)
        label_layout.setSpacing(4)
        label_layout.setContentsMargins(8, 6, 8, 6)

        self.label_merge_strategy = QtWidgets.QComboBox()
        for text, data in self.label_strategy_map.items():
            self.label_merge_strategy.addItem(text, userData=data)
        label_layout.addRow("标签合并策略:", self.label_merge_strategy)

        # 黑名单启用复选框
        self.enable_exclude_labels = QtWidgets.QCheckBox("启用排除合并的标签")
        self.enable_exclude_labels.setChecked(True)  # 默认启用
        label_layout.addRow(self.enable_exclude_labels)
        
        self.exclude_labels = QtWidgets.QLineEdit()
        self.exclude_labels.setText("other")  # 默认填入other
        self.exclude_labels.setPlaceholderText("例如: label1,label2")
        label_layout.addRow("黑名单标签:", self.exclude_labels)
        
        # 连接复选框信号，控制输入框的启用状态
        self.enable_exclude_labels.toggled.connect(self.exclude_labels.setEnabled)
        
        self.require_same_label = QtWidgets.QCheckBox("要求标签完全相同才合并")
        label_layout.addRow(self.require_same_label)

        # 创建"仅在特定标签组内合并"复选框和按钮的水平布局
        specific_groups_row_layout = QtWidgets.QHBoxLayout()
        specific_groups_row_layout.setSpacing(8)
        
        self.use_specific_groups = QtWidgets.QCheckBox("仅在特定标签组内合并")
        specific_groups_row_layout.addWidget(self.use_specific_groups)
        
        # 添加全选/全不选按钮
        self.select_all_button = QtWidgets.QPushButton("全选")
        self.select_all_button.setEnabled(False)
        self.select_all_button.setFixedWidth(60)
        self.select_all_button.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:pressed {
                background-color: #2868a8;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.select_all_button.clicked.connect(self.select_all_groups)
        
        self.deselect_all_button = QtWidgets.QPushButton("全不选")
        self.deselect_all_button.setEnabled(False)
        self.deselect_all_button.setFixedWidth(60)
        self.deselect_all_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.deselect_all_button.clicked.connect(self.deselect_all_groups)
        
        self.invert_selection_button = QtWidgets.QPushButton("反选")
        self.invert_selection_button.setEnabled(False)
        self.invert_selection_button.setFixedWidth(60)
        self.invert_selection_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.invert_selection_button.clicked.connect(self.invert_selection_groups)
        
        specific_groups_row_layout.addWidget(self.select_all_button)
        specific_groups_row_layout.addWidget(self.deselect_all_button)
        specific_groups_row_layout.addWidget(self.invert_selection_button)
        specific_groups_row_layout.addStretch()
        
        # 使用原版的文本框，但改成带复选框的行编辑器
        self.specific_groups_widget = QtWidgets.QWidget()
        self.specific_groups_widget_layout = QtWidgets.QVBoxLayout(self.specific_groups_widget)
        self.specific_groups_widget_layout.setContentsMargins(0, 0, 0, 0)
        self.specific_groups_widget_layout.setSpacing(4)
        
        # 滚动区域
        self.specific_groups_scroll = QtWidgets.QScrollArea()
        self.specific_groups_scroll.setWidget(self.specific_groups_widget)
        self.specific_groups_scroll.setWidgetResizable(True)
        self.specific_groups_scroll.setMinimumHeight(150)
        self.specific_groups_scroll.setMaximumHeight(250)
        self.specific_groups_scroll.setEnabled(False)
        self.specific_groups_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                background-color: white;
            }
        """)
        
        # 初始化组行列表
        self.group_rows = []
        default_groups = [
            "balloon",
            "qipao",
            "shuqing",
            "changfangtiao",
            "hengxie",
            "other"
        ]
        for group_text in default_groups:
            self.add_group_row(group_text, checked=True)
        
        # 添加新组的输入框
        add_group_layout = QtWidgets.QHBoxLayout()
        self.new_group_input = QtWidgets.QLineEdit()
        self.new_group_input.setPlaceholderText("输入新组标签...")
        self.new_group_input.setEnabled(False)
        self.new_group_input.setStyleSheet("""
            QLineEdit {
                padding: 4px 8px;
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border: 1px solid #4a90e2;
            }
        """)
        self.new_group_input.returnPressed.connect(self.add_new_group)
        
        self.add_group_button = QtWidgets.QPushButton("添加组")
        self.add_group_button.setEnabled(False)
        self.add_group_button.setFixedWidth(70)
        self.add_group_button.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px 10px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:pressed {
                background-color: #2868a8;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.add_group_button.clicked.connect(self.add_new_group)
        add_group_layout.addWidget(self.new_group_input)
        add_group_layout.addWidget(self.add_group_button)
        
        self.use_specific_groups.toggled.connect(self.specific_groups_scroll.setEnabled)
        self.use_specific_groups.toggled.connect(self.new_group_input.setEnabled)
        self.use_specific_groups.toggled.connect(self.add_group_button.setEnabled)
        self.use_specific_groups.toggled.connect(self.select_all_button.setEnabled)
        self.use_specific_groups.toggled.connect(self.deselect_all_button.setEnabled)
        self.use_specific_groups.toggled.connect(self.invert_selection_button.setEnabled)
        self.use_specific_groups.toggled.connect(lambda checked: self.require_same_label.setDisabled(checked))

        label_layout.addRow(specific_groups_row_layout)
        label_layout.addRow(self.specific_groups_scroll)
        label_layout.addRow(add_group_layout)

        left_column.addWidget(label_group)

        # --- Geometric Rules --- 移到右侧栏
        geo_group = QtWidgets.QGroupBox("几何合并参数")
        geo_layout = QtWidgets.QFormLayout(geo_group)
        geo_layout.setSpacing(4)
        geo_layout.setContentsMargins(8, 6, 8, 6)

        # Vertical merge parameters
        self.max_vertical_gap = QtWidgets.QSpinBox()
        self.max_vertical_gap.setRange(0, 1000)
        self.max_vertical_gap.setValue(10)
        self.min_width_overlap_ratio = QtWidgets.QSpinBox()
        self.min_width_overlap_ratio.setRange(0, 100)
        self.min_width_overlap_ratio.setValue(90)
        self.min_width_overlap_ratio.setSuffix(" %")
        
        # Horizontal merge parameters
        self.max_horizontal_gap = QtWidgets.QSpinBox()
        self.max_horizontal_gap.setRange(0, 1000)
        self.max_horizontal_gap.setValue(10)
        self.min_height_overlap_ratio = QtWidgets.QSpinBox()
        self.min_height_overlap_ratio.setRange(0, 100)
        self.min_height_overlap_ratio.setValue(90)
        self.min_height_overlap_ratio.setSuffix(" %")

        # Add separator and widgets to layout
        geo_layout.addRow(QtWidgets.QLabel("<b>垂直合并 (上下)</b>"))
        geo_layout.addRow("最大垂直间隙 (像素):", self.max_vertical_gap)
        geo_layout.addRow("最小水平重叠比例:", self.min_width_overlap_ratio)
        geo_layout.addRow(QtWidgets.QLabel("<b>水平合并 (左右)</b>"))
        geo_layout.addRow("最大水平间隙 (像素):", self.max_horizontal_gap)
        geo_layout.addRow("最小垂直重叠比例:", self.min_height_overlap_ratio)

        right_column.addWidget(geo_group)

        # --- Advanced Options --- 移到右侧栏
        advanced_group = QtWidgets.QGroupBox("高级选项")
        advanced_layout = QtWidgets.QVBoxLayout(advanced_group)
        advanced_layout.setSpacing(4)
        advanced_layout.setContentsMargins(8, 6, 8, 6)
        self.allow_negative_gap = QtWidgets.QCheckBox("允许负间隙")
        self.allow_negative_gap.setChecked(True)
        advanced_layout.addWidget(self.allow_negative_gap)

        right_column.addWidget(advanced_group)

        # --- Merge Result Type --- 移到右侧栏
        result_type_group = QtWidgets.QGroupBox("合并结果类型")
        result_type_layout = QtWidgets.QVBoxLayout(result_type_group)
        result_type_layout.setSpacing(4)
        result_type_layout.setContentsMargins(8, 6, 8, 6)
        
        self.output_type_group = QtWidgets.QButtonGroup(self)
        self.radio_output_rectangle = QtWidgets.QRadioButton("合并水平矩形")
        self.radio_output_rotation = QtWidgets.QRadioButton("合并旋转矩形")
        
        self.radio_output_rectangle.setChecked(True) # Default to rectangle
        
        self.output_type_group.addButton(self.radio_output_rectangle, 1)
        self.output_type_group.addButton(self.radio_output_rotation, 2)
        
        result_type_layout.addWidget(self.radio_output_rectangle)
        result_type_layout.addWidget(self.radio_output_rotation)
        
        right_column.addWidget(result_type_group)
        
        # --- 日志显示区域 ---
        log_group = QtWidgets.QGroupBox("日志")
        log_layout = QtWidgets.QVBoxLayout(log_group)
        log_layout.setSpacing(4)
        log_layout.setContentsMargins(8, 6, 8, 6)
        
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(320)
        self.log_text.setPlaceholderText("执行日志将显示在这里...")
        log_layout.addWidget(self.log_text)
        
        right_column.addWidget(log_group)
        # 移除右侧栏底部留白，让日志窗口自然扩展
        # right_column.addStretch()  # 右侧栏底部留白
        
        # 组合左右两栏
        main_content_layout.addLayout(left_column, 3)  # 左侧占3份
        main_content_layout.addLayout(right_column, 2)  # 右侧占2份，更窄
        
        self.layout.addLayout(main_content_layout)

        # --- 范围选择 ---
        range_group = QtWidgets.QGroupBox("范围选择")
        range_layout = QtWidgets.QHBoxLayout(range_group)
        
        self.range_from = QtWidgets.QSpinBox()
        self.range_from.setMinimum(1)
        self.range_from.setValue(1)
        self.range_from.setPrefix("从: ")
        
        self.range_to = QtWidgets.QSpinBox()
        self.range_to.setMinimum(1)
        self.range_to.setValue(1)
        self.range_to.setPrefix("到: ")
        
        range_layout.addWidget(self.range_from)
        range_layout.addWidget(self.range_to)
        range_layout.addStretch()
        
        self.layout.addWidget(range_group)
        
        # 连接翻页信号
        if hasattr(self.parent_widget, 'file_list_widget'):
            self.parent_widget.file_list_widget.currentRowChanged.connect(self.on_page_changed)
        
        # 初始化范围（不设置当前页，等showEvent时再设置）
        if hasattr(self.parent_widget, 'image_list') and self.parent_widget.image_list:
            total = len(self.parent_widget.image_list)
            self.range_from.setMaximum(total)
            self.range_to.setMaximum(total)
            self.range_to.setValue(total)
        else:
            self.range_from.setMaximum(1)
            self.range_to.setMaximum(1)

        # --- Buttons --- 按钮放在底部横跨整个宽度
        button_layout = QtWidgets.QHBoxLayout()
        self.run_current_button = QtWidgets.QPushButton("对当前文件运行")
        self.run_all_button = QtWidgets.QPushButton("对所有文件运行")
        self.run_range_button = QtWidgets.QPushButton("对范围文件运行")
        self.cancel_button = QtWidgets.QPushButton("关闭")
        
        button_layout.addWidget(self.run_current_button)
        button_layout.addWidget(self.run_range_button)
        button_layout.addWidget(self.run_all_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()
        
        self.cancel_button.clicked.connect(self._on_close)
        
        # 🎯 运行按钮点击时也保存设置
        self.run_current_button.clicked.connect(self.save_settings_to_config)
        self.run_range_button.clicked.connect(self.save_settings_to_config)
        self.run_all_button.clicked.connect(self.save_settings_to_config)
        
        self.layout.addLayout(button_layout)
        
        # 🎯 在构造函数末尾加载配置
        self.load_settings_from_config()

    def add_group_row(self, group_text, checked=True):
        """添加一个可勾选的组行"""
        row_widget = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row_widget)
        row_layout.setContentsMargins(4, 2, 4, 2)
        row_layout.setSpacing(8)
        
        # 复选框
        checkbox = QtWidgets.QCheckBox()
        checkbox.setChecked(checked)
        checkbox.setFixedWidth(20)
        
        # 文本输入框（可编辑）
        line_edit = QtWidgets.QLineEdit(group_text)
        line_edit.setStyleSheet("""
            QLineEdit {
                padding: 4px 8px;
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                font-size: 10pt;
                font-family: Consolas, monospace;
            }
            QLineEdit:focus {
                border: 1px solid #4a90e2;
            }
        """)
        
        # 删除按钮
        delete_btn = QtWidgets.QPushButton("✕")
        delete_btn.setFixedSize(20, 20)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
                border-radius: 10px;
                color: #666;
                font-size: 12pt;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #ff4444;
                color: white;
                border: 1px solid #ff4444;
            }
            QPushButton:pressed {
                background-color: #cc0000;
            }
        """)
        delete_btn.clicked.connect(lambda: self.remove_group_row(row_widget))
        
        row_layout.addWidget(checkbox)
        row_layout.addWidget(line_edit)
        row_layout.addWidget(delete_btn)
        
        self.specific_groups_widget_layout.addWidget(row_widget)
        self.group_rows.append((checkbox, line_edit, row_widget))
    
    def add_new_group(self):
        """添加新组"""
        group_text = self.new_group_input.text().strip()
        if group_text:
            self.add_group_row(group_text, checked=True)
            self.new_group_input.clear()
    
    def select_all_groups(self):
        """全选所有组"""
        for checkbox, line_edit, _ in self.group_rows:
            checkbox.setChecked(True)
    
    def deselect_all_groups(self):
        """全不选所有组"""
        for checkbox, line_edit, _ in self.group_rows:
            checkbox.setChecked(False)
    
    def invert_selection_groups(self):
        """反选所有组"""
        for checkbox, line_edit, _ in self.group_rows:
            checkbox.setChecked(not checkbox.isChecked())
    
    def remove_group_row(self, row_widget):
        """删除组行"""
        self.group_rows = [(cb, le, widget) for cb, le, widget in self.group_rows if widget != row_widget]
        self.specific_groups_widget_layout.removeWidget(row_widget)
        row_widget.deleteLater()
    
    def get_checked_groups(self):
        """获取所有勾选的组"""
        groups = []
        for checkbox, line_edit, _ in self.group_rows:
            if checkbox.isChecked():
                group_text = line_edit.text().strip()
                if group_text:
                    # 分割逗号分隔的标签
                    labels = [l.strip() for l in group_text.split(',') if l.strip()]
                    if labels:
                        groups.append(labels)
        return groups

    def get_config(self):
        config = {}
        config["MERGE_MODE"] = self.merge_mode.currentData()
        # Set a default reading direction, as the UI for a global default has been removed.
        # The logic in merger.py uses this as a fallback.
        config["READING_DIRECTION"] = "LTR"

        # Parse per-label directions from the new QLineEdits
        per_label_directions = {}
        for label in [l.strip() for l in self.ltr_labels_edit.text().split(',') if l.strip()]:
            per_label_directions[label] = 'LTR'
        for label in [l.strip() for l in self.rtl_labels_edit.text().split(',') if l.strip()]:
            per_label_directions[label] = 'RTL'
        for label in [l.strip() for l in self.ttb_labels_edit.text().split(',') if l.strip()]:
            per_label_directions[label] = 'TTB'
        config["PER_LABEL_DIRECTIONS"] = per_label_directions

        # 只有当黑名单启用时才使用排除标签
        if self.enable_exclude_labels.isChecked():
            excluded = self.exclude_labels.text().strip()
            config["LABELS_TO_EXCLUDE_FROM_MERGE"] = set(l.strip() for l in excluded.split(",") if l.strip())
        else:
            config["LABELS_TO_EXCLUDE_FROM_MERGE"] = set()

        config["USE_SPECIFIC_MERGE_GROUPS"] = self.use_specific_groups.isChecked()
        if config["USE_SPECIFIC_MERGE_GROUPS"]:
            # 使用勾选的组
            groups = self.get_checked_groups()
            config["SPECIFIC_MERGE_GROUPS"] = groups
            config["REQUIRE_SAME_LABEL"] = False
        else:
            config["SPECIFIC_MERGE_GROUPS"] = []
            config["REQUIRE_SAME_LABEL"] = self.require_same_label.isChecked()

        config["LABEL_MERGE_STRATEGY"] = self.label_merge_strategy.currentData()

        config["VERTICAL_MERGE_PARAMS"] = {
            "max_vertical_gap": self.max_vertical_gap.value(),
            "min_width_overlap_ratio": self.min_width_overlap_ratio.value(),
            "overlap_epsilon": 1e-6
        }

        config["HORIZONTAL_MERGE_PARAMS"] = {
            "max_horizontal_gap": self.max_horizontal_gap.value(),
            "min_height_overlap_ratio": self.min_height_overlap_ratio.value(),
            "overlap_epsilon": 1e-6
        }

        config["ADVANCED_MERGE_OPTIONS"] = {
            "allow_negative_gap": self.allow_negative_gap.isChecked(),
            "debug_mode": False # Not exposed in UI
        }

        config["OUTPUT_SHAPE_TYPE"] = "rectangle" if self.output_type_group.checkedId() == 1 else "rotation"

        return config

    def save_settings_to_config(self):
        """保存当前设置到配置文件"""
        # 保存组行的状态
        group_states = []
        for checkbox, line_edit, _ in self.group_rows:
            group_states.append({
                "text": line_edit.text(),
                "checked": checkbox.isChecked()
            })
        
        merge_settings = {
            "merge_mode": self.merge_mode.currentData(),
            "ltr_labels": self.ltr_labels_edit.text(),
            "rtl_labels": self.rtl_labels_edit.text(),
            "ttb_labels": self.ttb_labels_edit.text(),
            "label_merge_strategy": self.label_merge_strategy.currentData(),
            "enable_exclude_labels": self.enable_exclude_labels.isChecked(),
            "exclude_labels": self.exclude_labels.text(),
            "require_same_label": self.require_same_label.isChecked(),
            "use_specific_groups": self.use_specific_groups.isChecked(),
            "group_states": group_states,  # 保存组状态
            "max_vertical_gap": self.max_vertical_gap.value(),
            "min_width_overlap_ratio": self.min_width_overlap_ratio.value(),
            "max_horizontal_gap": self.max_horizontal_gap.value(),
            "min_height_overlap_ratio": self.min_height_overlap_ratio.value(),
            "allow_negative_gap": self.allow_negative_gap.isChecked(),
            "output_shape_type": "rectangle" if self.output_type_group.checkedId() == 1 else "rotation",
        }
        
        # 直接读写配置文件，避免get_config的副作用
        from ....config import USER_CONFIG_FILE
        user_config_file = USER_CONFIG_FILE
        try:
            existing = {}
            if os.path.exists(user_config_file):
                with open(user_config_file, "r", encoding="utf-8") as f:
                    existing = yaml.safe_load(f) or {}
            
            existing["merge_tool_settings"] = merge_settings
            
            with open(user_config_file, "w", encoding="utf-8") as f:
                yaml.safe_dump(existing, f, allow_unicode=True)
        except Exception as e:
            print(f"[ERROR] Failed to save config: {e}")

    def load_settings_from_config(self):
        """从配置文件加载设置"""
        # 直接读取配置文件，避免get_config的副作用
        from ....config import USER_CONFIG_FILE
        user_config_file = USER_CONFIG_FILE
        try:
            if not os.path.exists(user_config_file):
                return
            with open(user_config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            return
        
        settings = config.get("merge_tool_settings", {})
        
        if not settings:
            return
        
        # 加载合并模式
        merge_mode = settings.get("merge_mode", "VERTICAL")
        for i in range(self.merge_mode.count()):
            if self.merge_mode.itemData(i) == merge_mode:
                self.merge_mode.setCurrentIndex(i)
                break
        
        # 加载标签方向设置
        self.ltr_labels_edit.setText(settings.get("ltr_labels", ""))
        self.rtl_labels_edit.setText(settings.get("rtl_labels", "balloon,qipao,shuqing"))
        self.ttb_labels_edit.setText(settings.get("ttb_labels", "changfangtiao,hengxie"))
        
        # 加载标签合并策略
        strategy = settings.get("label_merge_strategy", "PREFER_SHORTER")
        for i in range(self.label_merge_strategy.count()):
            if self.label_merge_strategy.itemData(i) == strategy:
                self.label_merge_strategy.setCurrentIndex(i)
                break
        
        # 加载黑名单设置
        self.enable_exclude_labels.setChecked(settings.get("enable_exclude_labels", True))
        self.exclude_labels.setText(settings.get("exclude_labels", "other"))
        
        # 加载其他复选框
        self.require_same_label.setChecked(settings.get("require_same_label", False))
        self.use_specific_groups.setChecked(settings.get("use_specific_groups", False))
        
        # 加载组状态
        group_states = settings.get("group_states", [])
        if group_states:
            # 清空现有组
            for cb, le, widget in list(self.group_rows):
                self.remove_group_row(widget)
            # 重新添加组
            for state in group_states:
                self.add_group_row(state["text"], state["checked"])
        else:
            # 如果没有保存的配置，确保有默认的other
            has_other = any(le.text().strip() == "other" for _, le, _ in self.group_rows)
            if not has_other:
                self.add_group_row("other", checked=True)
        
        # 加载几何参数
        self.max_vertical_gap.setValue(settings.get("max_vertical_gap", 10))
        self.min_width_overlap_ratio.setValue(settings.get("min_width_overlap_ratio", 90))
        self.max_horizontal_gap.setValue(settings.get("max_horizontal_gap", 10))
        self.min_height_overlap_ratio.setValue(settings.get("min_height_overlap_ratio", 90))
        
        # 加载高级选项
        self.allow_negative_gap.setChecked(settings.get("allow_negative_gap", True))
        
        # 加载输出类型
        output_type = settings.get("output_shape_type", "rectangle")
        if output_type == "rectangle":
            self.radio_output_rectangle.setChecked(True)
        else:
            self.radio_output_rotation.setChecked(True)

    def showEvent(self, event):
        """窗口显示时恢复上次位置并更新范围（仅运行期间有效）"""
        super().showEvent(event)
        # 如果有保存的位置，恢复它
        if self.saved_geometry is not None:
            self.restoreGeometry(self.saved_geometry)
        # 更新范围限制和当前页
        self.update_range_limits()

    def _on_close(self):
        """关闭按钮点击时保存配置并关闭"""
        self.save_settings_to_config()
        self.hide()

    def closeEvent(self, event):
        """窗口关闭时保存配置并断开信号"""
        self.save_settings_to_config()
        self.save_window_position()
        # 断开翻页信号
        if hasattr(self.parent_widget, 'file_list_widget'):
            try:
                self.parent_widget.file_list_widget.currentRowChanged.disconnect(self.on_page_changed)
            except:
                pass
        super().closeEvent(event)
    
    def hideEvent(self, event):
        """窗口隐藏时保存位置（仅运行期间有效）"""
        self.save_window_position()
        super().hideEvent(event)
    
    def save_window_position(self):
        """保存窗口位置到内存（不写入配置文件）"""
        self.saved_geometry = self.saveGeometry()
    
    def update_range_limits(self):
        """更新范围限制"""
        if hasattr(self.parent_widget, 'image_list') and self.parent_widget.image_list:
            total = len(self.parent_widget.image_list)
            self.range_from.setMaximum(total)
            self.range_to.setMaximum(total)
            self.range_to.setValue(total)
            
            # 设置"从"为当前页（优先使用file_list_widget的currentRow）
            current_page = 1
            if hasattr(self.parent_widget, 'file_list_widget'):
                current_row = self.parent_widget.file_list_widget.currentRow()
                if current_row >= 0:
                    current_page = current_row + 1
            elif hasattr(self.parent_widget, 'cur_img_idx'):
                current_page = self.parent_widget.cur_img_idx + 1
            
            self.range_from.setValue(current_page)
        else:
            self.range_from.setMaximum(1)
            self.range_to.setMaximum(1)
    
    def on_page_changed(self, current_row):
        """翻页时更新范围的"从"值"""
        if current_row >= 0:
            current_page = current_row + 1
            self.range_from.setValue(current_page)
    
    def log(self, message):
        """添加日志消息"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
    
    def clear_log(self):
        """清空日志"""
        self.log_text.clear()