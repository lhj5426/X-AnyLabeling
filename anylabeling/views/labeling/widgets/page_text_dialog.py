# -*- encoding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt


class PageTextDialog(QtWidgets.QDialog):
    """页文本工具窗口 - 显示和编辑当前页面所有标签的 description"""
    
    # 信号：description 改变时发出 (shape_index, new_description)
    description_changed = QtCore.pyqtSignal(int, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.shapes = []  # 当前页面的所有形状

        self.setWindowTitle(self.tr("页文本工具"))
        # 设置窗口标志：非阻塞，可最小化
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint
        )
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        self.init_ui()

        # 连接标签顺序改变信号，实现自动刷新
        if parent and hasattr(parent, 'unique_label_list'):
            parent.unique_label_list.labels_ordered.connect(self.on_labels_ordered)
        else:
            # Optional: Log a warning if the connection fails, but don't print to console
            pass
    
    def init_ui(self):
        """初始化UI"""
        layout = QtWidgets.QVBoxLayout(self)
        
        # 标题标签
        title_label = QtWidgets.QLabel(self.tr("当前页面标签文本内容"))
        title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(title_label)
        
        # 创建表格
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels([
            self.tr("标签"),
            self.tr("文本内容")
        ])
        
        # 隐藏垂直行号表头
        self.table.verticalHeader().setVisible(False)
        
        # 设置列宽
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        
        # 设置行高
        self.table.verticalHeader().setDefaultSectionSize(30)
        
        # 启用编辑
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.DoubleClicked |
                                   QtWidgets.QAbstractItemView.EditKeyPressed)
        
        # 连接单元格改变信号
        self.table.cellChanged.connect(self.on_cell_changed)
        # 连接行选择信号
        self.table.itemSelectionChanged.connect(self.on_row_selected)

        layout.addWidget(self.table)
    
    def update_shapes(self, shapes):
        """更新显示的形状列表"""
        self.shapes = shapes
        self.refresh_table()

    def on_labels_ordered(self, labels):
        """标签顺序改变时自动刷新"""
        self.refresh_data()

    def refresh_data(self):
        """从父窗口刷新数据"""
        if self.parent and hasattr(self.parent, 'canvas'):
            self.shapes = self.parent.canvas.shapes
            self.refresh_table()
    
    def refresh_table(self):
        """刷新表格显示"""
        # 断开信号，避免触发 cellChanged
        self.table.cellChanged.disconnect(self.on_cell_changed)

        # 清空表格
        self.table.setRowCount(0)

        # 填充数据 - 只显示可见的形状
        visible_shapes = [s for s in self.shapes if s.visible]
        self.table.setRowCount(len(visible_shapes))

        # 计算每个标签的总数
        label_total_counters = {}
        for shape in visible_shapes:
            label = shape.label
            label_total_counters[label] = label_total_counters.get(label, 0) + 1

        # 用于显示当前标签是第几个
        display_counters = {}

        for row, shape in enumerate(visible_shapes):
            # 标签 - 显示格式：序号 标签名(当前计数)
            label = shape.label or ""
            display_counters[label] = display_counters.get(label, 0) + 1
            # total_count = label_total_counters.get(label, 0) # This line is no longer needed for display
            
            label_text = f"{row + 1} {label}({display_counters[label]})"

            label_item = QtWidgets.QTableWidgetItem(label_text)
            label_item.setFlags(label_item.flags() & ~Qt.ItemIsEditable)  # 不可编辑

            # 设置标签颜色
            if hasattr(shape, 'line_color') and shape.line_color:
                color = shape.line_color
                label_item.setBackground(color)
                # 根据背景色亮度设置文字颜色
                brightness = (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
                if brightness < 128:
                    label_item.setForeground(QtGui.QColor(255, 255, 255))
                else:
                    label_item.setForeground(QtGui.QColor(0, 0, 0))

            self.table.setItem(row, 0, label_item)

            # 文本内容（可编辑）
            description = shape.description or ""
            desc_item = QtWidgets.QTableWidgetItem(description)
            self.table.setItem(row, 1, desc_item)

            # 存储 shape 的索引到 item 的 UserRole
            label_item.setData(Qt.UserRole, self.shapes.index(shape))

        # 重新连接信号
        self.table.cellChanged.connect(self.on_cell_changed)
    
    def on_row_selected(self):
        """表格行被选中时，高亮画布上对应的图形"""
        selected_items = self.table.selectedItems()
        if not selected_items:
            return

        row = selected_items[0].row()
        # The item in the first column holds the shape index
        item = self.table.item(row, 0) 
        if not item:
            return

        shape_index = item.data(Qt.UserRole)
        if shape_index is None or shape_index >= len(self.shapes):
            return

        shape_to_select = self.shapes[shape_index]

        # Select the shape on the canvas
        if self.parent and hasattr(self.parent, 'canvas'):
            self.parent.canvas.select_shapes([shape_to_select])

    def on_cell_changed(self, row, column):
        """单元格内容改变时的处理"""
        if column != 1:  # 只处理文本内容列
            return

        # 获取 shape 索引
        index_item = self.table.item(row, 0)
        if not index_item:
            return

        shape_index = index_item.data(Qt.UserRole)
        if shape_index is None or shape_index >= len(self.shapes):
            return

        # 获取新的 description
        desc_item = self.table.item(row, 1)
        new_description = desc_item.text() if desc_item else ""

        # 更新 shape 的 description
        shape = self.shapes[shape_index]
        if shape.description != new_description:
            shape.description = new_description

            # 发出信号通知父窗口
            self.description_changed.emit(shape_index, new_description)

            # 如果父窗口有 set_dirty 方法，调用它
            if self.parent and hasattr(self.parent, 'set_dirty'):
                self.parent.set_dirty()
    
    def showEvent(self, event):
        """窗口显示时刷新数据"""
        super().showEvent(event)
        self.refresh_data()
    
    def tr(self, text):
        """翻译函数"""
        return QtWidgets.QApplication.translate("PageTextDialog", text)