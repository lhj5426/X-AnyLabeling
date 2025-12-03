"""放大镜设置对话框"""

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt


class MagnifierSettingsDialog(QtWidgets.QDialog):
    """放大镜设置对话框"""
    
    def __init__(self, parent=None, canvas=None, config=None):
        super().__init__(parent)
        self.canvas = canvas
        self.config = config or {}
        self.setWindowTitle("放大镜设置")
        self.setMinimumWidth(400)
        self.setup_ui()
        self.load_settings()
        
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # 窗口大小设置
        size_group = QtWidgets.QGroupBox("窗口大小")
        size_layout = QtWidgets.QGridLayout(size_group)
        
        size_layout.addWidget(QtWidgets.QLabel("宽度:"), 0, 0)
        self.width_spin = QtWidgets.QSpinBox()
        self.width_spin.setRange(100, 1500)
        self.width_spin.setSingleStep(50)
        self.width_spin.setSuffix(" px")
        size_layout.addWidget(self.width_spin, 0, 1)
        
        size_layout.addWidget(QtWidgets.QLabel("高度:"), 0, 2)
        self.height_spin = QtWidgets.QSpinBox()
        self.height_spin.setRange(100, 1500)
        self.height_spin.setSingleStep(50)
        self.height_spin.setSuffix(" px")
        size_layout.addWidget(self.height_spin, 0, 3)
        
        # 快捷预设按钮
        preset_layout = QtWidgets.QHBoxLayout()
        preset_layout.addWidget(QtWidgets.QLabel("预设:"))
        
        btn_300 = QtWidgets.QPushButton("300x300")
        btn_300.clicked.connect(lambda: self.set_size_preset(300, 300))
        preset_layout.addWidget(btn_300)
        
        btn_500 = QtWidgets.QPushButton("500x500")
        btn_500.clicked.connect(lambda: self.set_size_preset(500, 500))
        preset_layout.addWidget(btn_500)
        
        btn_800 = QtWidgets.QPushButton("800x800")
        btn_800.clicked.connect(lambda: self.set_size_preset(800, 800))
        preset_layout.addWidget(btn_800)
        
        preset_layout.addStretch()
        size_layout.addLayout(preset_layout, 1, 0, 1, 4)
        
        layout.addWidget(size_group)
        
        # 缩放比例设置
        zoom_group = QtWidgets.QGroupBox("缩放比例")
        zoom_layout = QtWidgets.QGridLayout(zoom_group)
        
        zoom_layout.addWidget(QtWidgets.QLabel("默认倍率:"), 0, 0)
        self.zoom_spin = QtWidgets.QDoubleSpinBox()
        self.zoom_spin.setRange(1.0, 10.0)
        self.zoom_spin.setSingleStep(0.5)
        self.zoom_spin.setDecimals(1)
        self.zoom_spin.setSuffix(" x")
        zoom_layout.addWidget(self.zoom_spin, 0, 1)
        
        # 原图百分比模式（可输入任意百分比）
        zoom_layout.addWidget(QtWidgets.QLabel("原图百分比:"), 1, 0)
        self.percent_spin = QtWidgets.QSpinBox()
        self.percent_spin.setRange(0, 500)  # 0表示禁用，使用倍率；其他值表示原图的百分比
        self.percent_spin.setSingleStep(10)
        self.percent_spin.setSuffix(" %")
        self.percent_spin.setSpecialValueText("禁用")  # 0时显示"禁用"
        self.percent_spin.setToolTip("设置放大镜显示原图的百分比（0=禁用，使用上面的倍率；100=原图1:1像素）")
        zoom_layout.addWidget(self.percent_spin, 1, 1)
        
        layout.addWidget(zoom_group)
        
        # 十字线设置
        crosshair_group = QtWidgets.QGroupBox("十字线")
        crosshair_layout = QtWidgets.QGridLayout(crosshair_group)
        
        self.crosshair_check = QtWidgets.QCheckBox("显示十字线")
        crosshair_layout.addWidget(self.crosshair_check, 0, 0, 1, 2)
        
        crosshair_layout.addWidget(QtWidgets.QLabel("颜色:"), 1, 0)
        self.crosshair_color_btn = QtWidgets.QPushButton()
        self.crosshair_color_btn.setFixedSize(80, 25)
        self.crosshair_color_btn.clicked.connect(self.choose_crosshair_color)
        crosshair_layout.addWidget(self.crosshair_color_btn, 1, 1)
        
        crosshair_layout.addWidget(QtWidgets.QLabel("宽度:"), 2, 0)
        self.crosshair_width_spin = QtWidgets.QSpinBox()
        self.crosshair_width_spin.setRange(1, 5)
        self.crosshair_width_spin.setSuffix(" px")
        crosshair_layout.addWidget(self.crosshair_width_spin, 2, 1)
        
        layout.addWidget(crosshair_group)
        
        # 边框设置
        border_group = QtWidgets.QGroupBox("边框")
        border_layout = QtWidgets.QGridLayout(border_group)
        
        border_layout.addWidget(QtWidgets.QLabel("颜色:"), 0, 0)
        self.border_color_btn = QtWidgets.QPushButton()
        self.border_color_btn.setFixedSize(80, 25)
        self.border_color_btn.clicked.connect(self.choose_border_color)
        border_layout.addWidget(self.border_color_btn, 0, 1)
        
        border_layout.addWidget(QtWidgets.QLabel("宽度:"), 1, 0)
        self.border_width_spin = QtWidgets.QSpinBox()
        self.border_width_spin.setRange(0, 10)
        self.border_width_spin.setSuffix(" px")
        border_layout.addWidget(self.border_width_spin, 1, 1)
        
        layout.addWidget(border_group)
        
        # 按钮
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        ok_btn = QtWidgets.QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        
        cancel_btn = QtWidgets.QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def set_size_preset(self, width, height):
        """设置预设尺寸"""
        self.width_spin.setValue(width)
        self.height_spin.setValue(height)
        
    def load_settings(self):
        """从config加载当前设置"""
        # 窗口大小
        self.width_spin.setValue(self.config.get('magnifier_width', 500))
        self.height_spin.setValue(self.config.get('magnifier_height', 500))
        
        # 缩放
        self.zoom_spin.setValue(self.config.get('magnifier_zoom', 1.0))
        # 原图百分比：0=禁用，100=原图100%
        self.percent_spin.setValue(self.config.get('magnifier_percent', 0))
        
        # 十字线
        self.crosshair_check.setChecked(self.config.get('magnifier_show_crosshair', True))
        self.crosshair_color = self.config.get('magnifier_crosshair_color', [255, 0, 0])
        self.update_color_button(self.crosshair_color_btn, self.crosshair_color)
        self.crosshair_width_spin.setValue(self.config.get('magnifier_crosshair_width', 1))
        
        # 边框
        self.border_color = self.config.get('magnifier_border_color', [128, 128, 128])
        self.update_color_button(self.border_color_btn, self.border_color)
        self.border_width_spin.setValue(self.config.get('magnifier_border_width', 2))
        
    def update_color_button(self, btn, color):
        """更新颜色按钮的背景色"""
        if isinstance(color, list):
            btn.setStyleSheet(f"background-color: rgb({color[0]},{color[1]},{color[2]});")
        elif isinstance(color, QtGui.QColor):
            btn.setStyleSheet(f"background-color: {color.name()};")
        
    def choose_crosshair_color(self):
        """选择十字线颜色"""
        initial = QtGui.QColor(*self.crosshair_color) if isinstance(self.crosshair_color, list) else self.crosshair_color
        color = QtWidgets.QColorDialog.getColor(initial, self, "选择十字线颜色")
        if color.isValid():
            self.crosshair_color = [color.red(), color.green(), color.blue()]
            self.update_color_button(self.crosshair_color_btn, color)
            
    def choose_border_color(self):
        """选择边框颜色"""
        initial = QtGui.QColor(*self.border_color) if isinstance(self.border_color, list) else self.border_color
        color = QtWidgets.QColorDialog.getColor(initial, self, "选择边框颜色")
        if color.isValid():
            self.border_color = [color.red(), color.green(), color.blue()]
            self.update_color_button(self.border_color_btn, color)
    
    def get_settings(self):
        """获取当前设置"""
        return {
            'magnifier_width': self.width_spin.value(),
            'magnifier_height': self.height_spin.value(),
            'magnifier_zoom': self.zoom_spin.value(),
            'magnifier_percent': self.percent_spin.value(),  # 0=禁用，其他值=原图百分比
            'magnifier_show_crosshair': self.crosshair_check.isChecked(),
            'magnifier_crosshair_color': self.crosshair_color,
            'magnifier_crosshair_width': self.crosshair_width_spin.value(),
            'magnifier_border_color': self.border_color,
            'magnifier_border_width': self.border_width_spin.value(),
        }
