"""
Filter Classes Dialog
用于在界面上配置要过滤的类别标签
"""

import os
import yaml
from PyQt5 import QtWidgets, QtCore


def _normalize_classes(classes):
    if isinstance(classes, dict):
        return list(classes.values())
    return classes or []


class FilterClassesDialog(QtWidgets.QDialog):
    """对话框用于选择要过滤的类别"""

    def __init__(self, all_classes, current_filter_classes=None,
                 extra_labels_from_yaml=None, on_yaml_import=None, on_apply=None,
                 info_text=None, parent=None):
        """
        初始化过滤类别对话框

        Args:
            all_classes: 所有可用的类别列表
            current_filter_classes: 当前已过滤的类别列表
            extra_labels_from_yaml: 从YAML导入的额外标签列表
            on_yaml_import: 导入YAML标签时的回调函数
            on_apply: 点击应用时的回调函数
            info_text: 自定义说明文字
            parent: 父窗口
        """
        super(FilterClassesDialog, self).__init__(parent)
        self.all_classes = all_classes or []
        self.current_filter_classes = current_filter_classes or []
        self.extra_labels_from_yaml = extra_labels_from_yaml or []
        self.on_yaml_import = on_yaml_import
        self.on_apply = on_apply
        self.info_text = info_text

        # 设置为非模态窗口
        self.setWindowModality(QtCore.Qt.NonModal)

        self.init_ui()

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle(self.tr("标签过滤设置"))
        self.setMinimumWidth(350)
        self.setMinimumHeight(400)
        self.resize(350, 400)  # 设置初始大小

        # 主布局
        main_layout = QtWidgets.QVBoxLayout()

        # 说明文字
        default_info = self.tr(
            "勾选要执行 OCR 的标签：\n"
            "未勾选的标签将被跳过，不会进行 OCR 识别"
        )
        info_label = QtWidgets.QLabel(self.info_text or default_info)
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background-color: #f0f0f0; border-radius: 5px;")
        main_layout.addWidget(info_label)

        # 按钮行：全选/取消全选/从YAML导入
        button_layout = QtWidgets.QHBoxLayout()
        select_all_btn = QtWidgets.QPushButton(self.tr("全选"))
        deselect_all_btn = QtWidgets.QPushButton(self.tr("取消全选"))
        import_yaml_btn = QtWidgets.QPushButton(self.tr("从YAML导入"))
        select_all_btn.clicked.connect(self.select_all)
        deselect_all_btn.clicked.connect(self.deselect_all)
        import_yaml_btn.clicked.connect(self.import_from_yaml)
        import_yaml_btn.setToolTip(self.tr("从YAML配置文件导入标签（临时添加到当前列表）"))
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(deselect_all_btn)
        button_layout.addWidget(import_yaml_btn)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        # 创建滚动区域用于显示复选框
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        # 设置白色背景
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: white;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
            }
        """)

        # 复选框容器
        checkbox_widget = QtWidgets.QWidget()
        checkbox_widget.setStyleSheet("background-color: white;")  # 设置白色背景
        self.checkbox_layout = QtWidgets.QVBoxLayout()
        self.checkbox_layout.setContentsMargins(10, 10, 10, 10)  # 添加内边距
        self.checkbox_layout.setSpacing(5)  # 设置复选框之间的间距
        checkbox_widget.setLayout(self.checkbox_layout)

        # 创建复选框字典
        self.checkboxes = {}
        for class_name in self.all_classes:
            checkbox = QtWidgets.QCheckBox(class_name)
            # 如果当前过滤列表为空，默认全选；否则根据列表勾选
            if not self.current_filter_classes:
                checkbox.setChecked(True)
            else:
                checkbox.setChecked(class_name in self.current_filter_classes)
            self.checkboxes[class_name] = checkbox
            self.checkbox_layout.addWidget(checkbox)

        # 添加弹性空间
        self.checkbox_layout.addStretch()

        scroll_area.setWidget(checkbox_widget)
        main_layout.addWidget(scroll_area)

        # 底部按钮：应用和关闭
        button_box = QtWidgets.QDialogButtonBox()

        apply_button = button_box.addButton(self.tr("应用"), QtWidgets.QDialogButtonBox.ApplyRole)
        close_button = button_box.addButton(self.tr("关闭"), QtWidgets.QDialogButtonBox.RejectRole)

        apply_button.clicked.connect(self.apply_filter)
        close_button.clicked.connect(self.close)

        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def select_all(self):
        """全选所有复选框"""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(True)

    def deselect_all(self):
        """取消选择所有复选框"""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(False)

    def import_from_yaml(self):
        """从YAML文件导入标签"""
        # 打开文件选择对话框
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.tr("选择YAML配置文件"),
            "",
            self.tr("YAML文件 (*.yaml *.yml)")
        )

        if not file_path:
            return

        try:
            # 读取YAML文件
            with open(file_path, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)

            # 获取classes字段
            yaml_classes = _normalize_classes(yaml_config.get("classes", []))

            if not yaml_classes:
                QtWidgets.QMessageBox.warning(
                    self,
                    self.tr("警告"),
                    self.tr("该YAML文件中没有找到 'classes' 字段或为空！")
                )
                return

            # 统计添加的新标签
            new_labels = []
            for class_name in yaml_classes:
                if class_name not in self.checkboxes:
                    # 创建新的复选框
                    checkbox = QtWidgets.QCheckBox(class_name)
                    checkbox.setChecked(True)  # 默认勾选新导入的标签
                    self.checkboxes[class_name] = checkbox
                    # 插入到布局中（在弹性空间之前）
                    index = self.checkbox_layout.count() - 1  # 最后一个是Stretch
                    self.checkbox_layout.insertWidget(index, checkbox)
                    new_labels.append(class_name)

            # 如果有新标签且提供了回调函数，调用回调保存到持久化存储
            if new_labels and self.on_yaml_import:
                self.on_yaml_import(new_labels)

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                self.tr("错误"),
                self.tr(f"读取YAML文件失败：\n{str(e)}")
            )

    def apply_filter(self):
        """应用过滤设置"""
        if self.on_apply:
            selected_classes = self.get_selected_classes()
            self.on_apply(selected_classes)

    def get_selected_classes(self):
        """
        获取已选择的类别列表

        Returns:
            list: 已勾选的类别名称列表
        """
        selected = []
        for class_name, checkbox in self.checkboxes.items():
            if checkbox.isChecked():
                selected.append(class_name)
        return selected
