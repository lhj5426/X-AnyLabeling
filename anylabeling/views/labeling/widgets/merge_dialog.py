from PyQt5 import QtWidgets, QtCore
from anylabeling.config import get_config, save_config
import os
import yaml


class MergeDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("区域合并工具设置")
        self.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self.adjustSize()
        # 设置窗口标志：移除帮助按钮,添加最小化按钮
        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.WindowMinimizeButtonHint |
            QtCore.Qt.WindowMaximizeButtonHint |
            QtCore.Qt.WindowCloseButtonHint
        )

        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setSpacing(6)
        self.layout.setContentsMargins(8, 8, 8, 8)

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
        self.layout.addWidget(main_group)

        # --- Text Reading Order Settings ---
        reading_order_group = QtWidgets.QGroupBox("文本合并顺序 (按标签)")
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
        
        self.layout.addWidget(reading_order_group)

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
        self.enable_exclude_labels = QtWidgets.QCheckBox("启用排除合并的标签 (黑名单)")
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

        self.use_specific_groups = QtWidgets.QCheckBox("仅在特定标签组内合并")
        self.specific_groups_edit = QtWidgets.QPlainTextEdit()
        self.specific_groups_edit.setPlaceholderText("每行一个分组, 组内标签用逗号分隔\n例如:\nballoon,balloon2\nqipao,qipao2")
        self.specific_groups_edit.setPlainText("balloon\nqipao\nshuqing\nchangfangtiao\nhengxie")
        self.specific_groups_edit.setMaximumHeight(80)
        self.specific_groups_edit.setEnabled(False)
        self.use_specific_groups.toggled.connect(self.specific_groups_edit.setEnabled)
        self.use_specific_groups.toggled.connect(lambda checked: self.require_same_label.setDisabled(checked))

        label_layout.addRow(self.use_specific_groups)
        label_layout.addRow(self.specific_groups_edit)

        self.layout.addWidget(label_group)

        # --- Geometric Rules ---
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

        self.layout.addWidget(geo_group)

        # --- Advanced Options --- #
        advanced_group = QtWidgets.QGroupBox("高级选项")
        advanced_layout = QtWidgets.QVBoxLayout(advanced_group)
        advanced_layout.setSpacing(4)
        advanced_layout.setContentsMargins(8, 6, 8, 6)
        self.allow_negative_gap = QtWidgets.QCheckBox("允许负间隙 (即允许框本身有重叠)")
        self.allow_negative_gap.setChecked(True)
        advanced_layout.addWidget(self.allow_negative_gap)

        self.layout.addWidget(advanced_group)

        # --- Merge Result Type --- #
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
        
        self.layout.addWidget(result_type_group)

        # --- Buttons --- #
        button_layout = QtWidgets.QHBoxLayout()
        self.run_current_button = QtWidgets.QPushButton("对当前文件运行")
        self.run_all_button = QtWidgets.QPushButton("对所有文件运行")
        self.cancel_button = QtWidgets.QPushButton("关闭")
        
        button_layout.addWidget(self.run_current_button)
        button_layout.addWidget(self.run_all_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()
        
        self.cancel_button.clicked.connect(self._on_close)
        
        # 🎯 运行按钮点击时也保存设置
        self.run_current_button.clicked.connect(self.save_settings_to_config)
        self.run_all_button.clicked.connect(self.save_settings_to_config)
        
        self.layout.addLayout(button_layout)
        
        # 🎯 在构造函数末尾加载配置
        self.load_settings_from_config()

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
            groups_text = self.specific_groups_edit.toPlainText().strip()
            groups = []
            for line in groups_text.split('\n'):
                if line.strip():
                    groups.append([l.strip() for l in line.split(',')])
            config["SPECIFIC_MERGE_GROUPS"] = groups
            config["REQUIRE_SAME_LABEL"] = False # This is disabled in UI
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
            "specific_groups": self.specific_groups_edit.toPlainText(),
            "max_vertical_gap": self.max_vertical_gap.value(),
            "min_width_overlap_ratio": self.min_width_overlap_ratio.value(),
            "max_horizontal_gap": self.max_horizontal_gap.value(),
            "min_height_overlap_ratio": self.min_height_overlap_ratio.value(),
            "allow_negative_gap": self.allow_negative_gap.isChecked(),
            "output_shape_type": "rectangle" if self.output_type_group.checkedId() == 1 else "rotation",
        }
        
        # 直接读写配置文件，避免get_config的副作用
        user_config_file = os.path.join(os.path.expanduser("~"), ".YSGxanylabelingrc")
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
        user_config_file = os.path.join(os.path.expanduser("~"), ".YSGxanylabelingrc")
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
        self.specific_groups_edit.setPlainText(settings.get("specific_groups", "balloon\nqipao\nshuqing\nchangfangtiao\nhengxie"))
        
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
        """窗口显示时不再重新加载配置，避免覆盖用户修改"""
        super().showEvent(event)
        # 注意：不再在这里加载配置，因为对话框是单例模式
        # 配置只在构造函数中加载一次

    def _on_close(self):
        """关闭按钮点击时保存配置并关闭"""
        self.save_settings_to_config()
        self.hide()

    def closeEvent(self, event):
        """窗口关闭时保存配置"""
        self.save_settings_to_config()
        super().closeEvent(event)