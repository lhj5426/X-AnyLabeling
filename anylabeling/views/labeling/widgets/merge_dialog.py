from PyQt5 import QtWidgets, QtCore

class MergeDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("区域合并工具设置")
        self.setMinimumWidth(500)

        self.layout = QtWidgets.QVBoxLayout(self)

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

        self.merge_mode = QtWidgets.QComboBox()
        for text, data in self.merge_mode_map.items():
            self.merge_mode.addItem(text, userData=data)
        main_layout.addRow("合并模式:", self.merge_mode)

        # 添加文字阅读方向设置
        self.reading_direction = QtWidgets.QComboBox()
        self.reading_direction.addItem("从左到右 (LTR)", userData="LTR")
        self.reading_direction.addItem("从右到左 (RTL) - 日文漫画", userData="RTL")
        self.reading_direction.setCurrentIndex(1)  # 默认选择日文漫画模式
        main_layout.addRow("文字阅读方向:", self.reading_direction)

        self.layout.addWidget(main_group)

        # --- Labeling Rules --- #
        label_group = QtWidgets.QGroupBox("标签合并规则")
        label_layout = QtWidgets.QFormLayout(label_group)

        self.label_merge_strategy = QtWidgets.QComboBox()
        for text, data in self.label_strategy_map.items():
            self.label_merge_strategy.addItem(text, userData=data)
        label_layout.addRow("标签合并策略:", self.label_merge_strategy)

        self.exclude_labels = QtWidgets.QLineEdit()
        self.exclude_labels.setPlaceholderText("例如: label1,label2")
        label_layout.addRow("排除合并的标签 (黑名单):", self.exclude_labels)
        
        self.require_same_label = QtWidgets.QCheckBox("要求标签完全相同才合并")
        label_layout.addRow(self.require_same_label)

        self.use_specific_groups = QtWidgets.QCheckBox("仅在特定标签组内合并")
        self.specific_groups_edit = QtWidgets.QPlainTextEdit()
        self.specific_groups_edit.setPlaceholderText("每行一个分组, 组内标签用逗号分隔\n例如:\nballoon,balloon2\nqipao,qipao2")
        self.specific_groups_edit.setEnabled(False)
        self.use_specific_groups.toggled.connect(self.specific_groups_edit.setEnabled)
        self.use_specific_groups.toggled.connect(lambda checked: self.require_same_label.setDisabled(checked))

        label_layout.addRow(self.use_specific_groups)
        label_layout.addRow(self.specific_groups_edit)

        self.layout.addWidget(label_group)

        # --- Geometric Rules --- #
        geo_tabs = QtWidgets.QTabWidget()
        
        # Vertical Tab
        vertical_widget = QtWidgets.QWidget()
        vertical_layout = QtWidgets.QFormLayout(vertical_widget)
        self.max_vertical_gap = QtWidgets.QSpinBox()
        self.max_vertical_gap.setRange(0, 1000)
        self.max_vertical_gap.setValue(3)
        self.min_width_overlap_ratio = QtWidgets.QSpinBox()
        self.min_width_overlap_ratio.setRange(0, 100)
        self.min_width_overlap_ratio.setValue(95)
        self.min_width_overlap_ratio.setSuffix(" %")
        vertical_layout.addRow("最大垂直间隙 (像素):", self.max_vertical_gap)
        vertical_layout.addRow("最小水平重叠比例:", self.min_width_overlap_ratio)
        geo_tabs.addTab(vertical_widget, "垂直合并参数")

        # Horizontal Tab
        horizontal_widget = QtWidgets.QWidget()
        horizontal_layout = QtWidgets.QFormLayout(horizontal_widget)
        self.max_horizontal_gap = QtWidgets.QSpinBox()
        self.max_horizontal_gap.setRange(0, 1000)
        self.max_horizontal_gap.setValue(10)
        self.min_height_overlap_ratio = QtWidgets.QSpinBox()
        self.min_height_overlap_ratio.setRange(0, 100)
        self.min_height_overlap_ratio.setValue(10)
        self.min_height_overlap_ratio.setSuffix(" %")
        horizontal_layout.addRow("最大水平间隙 (像素):", self.max_horizontal_gap)
        horizontal_layout.addRow("最小垂直重叠比例:", self.min_height_overlap_ratio)
        geo_tabs.addTab(horizontal_widget, "水平合并参数")

        self.layout.addWidget(geo_tabs)

        # --- Advanced Options --- #
        advanced_group = QtWidgets.QGroupBox("高级选项")
        advanced_layout = QtWidgets.QVBoxLayout(advanced_group)
        self.allow_negative_gap = QtWidgets.QCheckBox("允许负间隙 (即允许框本身有重叠)")
        self.allow_negative_gap.setChecked(True)
        advanced_layout.addWidget(self.allow_negative_gap)

        self.layout.addWidget(advanced_group)

        # --- Buttons --- #
        self.button_box = QtWidgets.QDialogButtonBox()
        self.run_current_button = self.button_box.addButton("对当前文件运行", QtWidgets.QDialogButtonBox.ActionRole)
        self.run_all_button = self.button_box.addButton("对所有文件运行", QtWidgets.QDialogButtonBox.ActionRole)
        self.button_box.addButton(QtWidgets.QDialogButtonBox.Cancel)

        self.button_box.rejected.connect(self.reject)

        self.layout.addWidget(self.button_box)

    def get_config(self):
        config = {}
        config["MERGE_MODE"] = self.merge_mode.currentData()
        config["READING_DIRECTION"] = self.reading_direction.currentData()

        excluded = self.exclude_labels.text().strip()
        config["LABELS_TO_EXCLUDE_FROM_MERGE"] = set(l.strip() for l in excluded.split(",") if l.strip())

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

        return config
