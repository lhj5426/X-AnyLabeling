from PyQt5 import QtWidgets, QtCore, QtGui


class SafetyBorderSettingsDialog(QtWidgets.QDialog):
    def __init__(
        self, 
        label_name="",
        color_highlight="#FF0000", 
        opacity_highlight=255, 
        color_normal="#FF0000", 
        opacity_normal=128, 
        width=2.0, 
        parent=None
    ):
        super().__init__(parent)

        self._color_highlight = color_highlight
        self._opacity_highlight = opacity_highlight
        self._color_normal = color_normal
        self._opacity_normal = opacity_normal
        self._width = width

        title = f"安全边界设置 - {label_name}" if label_name else "安全边界设置"
        self.setWindowTitle(title)
        self.setModal(False)  # 非阻塞式窗口
        self.setMinimumWidth(400)
        self.setWindowFlags(
            QtCore.Qt.Window | QtCore.Qt.WindowMinimizeButtonHint | QtCore.Qt.WindowCloseButtonHint
        )

        # Create layout
        layout = QtWidgets.QVBoxLayout()

        # ===== 高亮时安全边界颜色 =====
        color_h_group = QtWidgets.QGroupBox("高亮时安全边界颜色")
        color_h_layout = QtWidgets.QHBoxLayout()
        
        self.color_h_block = QtWidgets.QLabel()
        self.color_h_block.setFixedSize(60, 30)
        self.color_h_block.setStyleSheet(f"background-color: {self._color_highlight}; border: 1px solid black;")
        
        self.color_h_button = QtWidgets.QPushButton("选择颜色")
        self.color_h_button.clicked.connect(lambda: self.choose_color('highlight'))
        
        color_h_layout.addWidget(self.color_h_block)
        color_h_layout.addWidget(self.color_h_button)
        color_h_layout.addStretch()
        color_h_group.setLayout(color_h_layout)

        # ===== 高亮时透明度 =====
        opacity_h_group = QtWidgets.QGroupBox("高亮时透明度")
        opacity_h_layout = QtWidgets.QHBoxLayout()
        
        opacity_h_label = QtWidgets.QLabel("透明度:")
        self.opacity_h_spinbox = QtWidgets.QSpinBox()
        self.opacity_h_spinbox.setMinimum(0)
        self.opacity_h_spinbox.setMaximum(255)
        self.opacity_h_spinbox.setValue(self._opacity_highlight)
        self.opacity_h_spinbox.setSuffix(" (0-255)")
        
        opacity_h_layout.addWidget(opacity_h_label)
        opacity_h_layout.addWidget(self.opacity_h_spinbox)
        opacity_h_layout.addStretch()
        opacity_h_group.setLayout(opacity_h_layout)

        # ===== 非高亮时安全边界颜色 =====
        color_n_group = QtWidgets.QGroupBox("非高亮时安全边界颜色")
        color_n_layout = QtWidgets.QHBoxLayout()
        
        self.color_n_block = QtWidgets.QLabel()
        self.color_n_block.setFixedSize(60, 30)
        self.color_n_block.setStyleSheet(f"background-color: {self._color_normal}; border: 1px solid black;")
        
        self.color_n_button = QtWidgets.QPushButton("选择颜色")
        self.color_n_button.clicked.connect(lambda: self.choose_color('normal'))
        
        color_n_layout.addWidget(self.color_n_block)
        color_n_layout.addWidget(self.color_n_button)
        color_n_layout.addStretch()
        color_n_group.setLayout(color_n_layout)

        # ===== 非高亮时透明度 =====
        opacity_n_group = QtWidgets.QGroupBox("非高亮时透明度")
        opacity_n_layout = QtWidgets.QHBoxLayout()
        
        opacity_n_label = QtWidgets.QLabel("透明度:")
        self.opacity_n_spinbox = QtWidgets.QSpinBox()
        self.opacity_n_spinbox.setMinimum(0)
        self.opacity_n_spinbox.setMaximum(255)
        self.opacity_n_spinbox.setValue(self._opacity_normal)
        self.opacity_n_spinbox.setSuffix(" (0-255)")
        
        opacity_n_layout.addWidget(opacity_n_label)
        opacity_n_layout.addWidget(self.opacity_n_spinbox)
        opacity_n_layout.addStretch()
        opacity_n_group.setLayout(opacity_n_layout)

        # ===== 线条粗细 =====
        width_group = QtWidgets.QGroupBox("线条粗细")
        width_layout = QtWidgets.QHBoxLayout()
        
        width_label = QtWidgets.QLabel("粗细:")
        self.width_spinbox = QtWidgets.QSpinBox()
        self.width_spinbox.setMinimum(1)
        self.width_spinbox.setMaximum(100)
        self.width_spinbox.setValue(int(self._width))
        self.width_spinbox.setSuffix(" px")
        
        width_layout.addWidget(width_label)
        width_layout.addWidget(self.width_spinbox)
        width_layout.addStretch()
        width_group.setLayout(width_layout)

        # Button layout
        button_layout = QtWidgets.QHBoxLayout()

        self.reset_button = QtWidgets.QPushButton("重置为默认")
        self.reset_button.clicked.connect(self.reset_settings)

        ok_button = QtWidgets.QPushButton("确定")
        ok_button.clicked.connect(self.accept)

        cancel_button = QtWidgets.QPushButton("取消")
        cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)

        # Add all layouts to the main layout
        layout.addWidget(color_h_group)
        layout.addWidget(opacity_h_group)
        layout.addWidget(color_n_group)
        layout.addWidget(opacity_n_group)
        layout.addWidget(width_group)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def choose_color(self, target):
        """打开颜色选择对话框"""
        if target == 'highlight':
            current_color = QtGui.QColor(self._color_highlight)
            color = QtWidgets.QColorDialog.getColor(current_color, self, "选择颜色")
            if color.isValid():
                self._color_highlight = color.name()
                self.color_h_block.setStyleSheet(f"background-color: {color.name()}; border: 1px solid black;")
        elif target == 'normal':
            current_color = QtGui.QColor(self._color_normal)
            color = QtWidgets.QColorDialog.getColor(current_color, self, "选择颜色")
            if color.isValid():
                self._color_normal = color.name()
                self.color_n_block.setStyleSheet(f"background-color: {color.name()}; border: 1px solid black;")

    def reset_settings(self):
        """重置为默认值"""
        self._color_highlight = "#FF0000"
        self._color_normal = "#FF0000"
        
        self.color_h_block.setStyleSheet(f"background-color: #FF0000; border: 1px solid black;")
        self.color_n_block.setStyleSheet(f"background-color: #FF0000; border: 1px solid black;")
        
        self.width_spinbox.setValue(2)
        self.opacity_h_spinbox.setValue(255)
        self.opacity_n_spinbox.setValue(128)

    def get_settings(self):
        """获取当前设置"""
        return {
            "color_highlight": self._color_highlight,
            "color_normal": self._color_normal,
            "opacity_highlight": self.opacity_h_spinbox.value(),
            "opacity_normal": self.opacity_n_spinbox.value(),
            "width": self.width_spinbox.value(),
        }
