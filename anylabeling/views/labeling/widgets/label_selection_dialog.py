"""
Label Selection Dialog
用于在标签转换时选择要转换的标签
"""

from PyQt5 import QtWidgets, QtCore


class LabelSelectionDialog(QtWidgets.QDialog):
    """对话框用于选择要转换的标签"""

    def __init__(self, labels, mode_title="选择要转换的标签", parent=None):
        """
        初始化标签选择对话框

        Args:
            labels: 所有可用的标签列表
            mode_title: 对话框标题
            parent: 父窗口
        """
        super(LabelSelectionDialog, self).__init__(parent)
        self.labels = labels or []
        self.mode_title = mode_title
        
        self.init_ui()

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle(self.mode_title)
        self.setMinimumWidth(400)
        self.setMinimumHeight(450)
        self.resize(400, 450)

        # 主布局
        main_layout = QtWidgets.QVBoxLayout()

        # 说明文字
        info_label = QtWidgets.QLabel(
            self.tr("请选择要转换的标签：\n"
                   "勾选的标签将被转换，未勾选的标签保持不变")
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background-color: #f0f0f0; border-radius: 5px;")
        main_layout.addWidget(info_label)

        # 按钮行：全选/取消全选
        button_layout = QtWidgets.QHBoxLayout()
        select_all_btn = QtWidgets.QPushButton(self.tr("全选"))
        deselect_all_btn = QtWidgets.QPushButton(self.tr("取消全选"))
        select_all_btn.clicked.connect(self.select_all)
        deselect_all_btn.clicked.connect(self.deselect_all)
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(deselect_all_btn)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        # 创建滚动区域用于显示复选框
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: white;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
            }
        """)

        # 复选框容器
        checkbox_widget = QtWidgets.QWidget()
        checkbox_widget.setStyleSheet("background-color: white;")
        self.checkbox_layout = QtWidgets.QVBoxLayout()
        self.checkbox_layout.setContentsMargins(10, 10, 10, 10)
        self.checkbox_layout.setSpacing(5)
        checkbox_widget.setLayout(self.checkbox_layout)

        # 创建复选框字典
        self.checkboxes = {}
        for label in self.labels:
            checkbox = QtWidgets.QCheckBox(label)
            checkbox.setChecked(True)  # 默认全选
            self.checkboxes[label] = checkbox
            self.checkbox_layout.addWidget(checkbox)

        # 添加弹性空间
        self.checkbox_layout.addStretch()

        scroll_area.setWidget(checkbox_widget)
        main_layout.addWidget(scroll_area)

        # 底部按钮：确定和取消
        button_box = QtWidgets.QDialogButtonBox()
        ok_button = button_box.addButton(self.tr("确定"), QtWidgets.QDialogButtonBox.AcceptRole)
        cancel_button = button_box.addButton(self.tr("取消"), QtWidgets.QDialogButtonBox.RejectRole)

        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

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

    def get_selected_labels(self):
        """
        获取已选择的标签列表

        Returns:
            list: 已勾选的标签名称列表
        """
        selected = []
        for label, checkbox in self.checkboxes.items():
            if checkbox.isChecked():
                selected.append(label)
        return selected

