# -*- encoding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt


class MultiLineDelegate(QtWidgets.QStyledItemDelegate):
    """自定义委托，非编辑和编辑状态都支持多行显示全部文本"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._click_pos = None
        self._editing_row = None
        self._original_height = None
    
    def paint(self, painter, option, index):
        """绘制单元格 - 支持多行文本换行显示"""
        # 第一列（标签列）使用默认绘制
        if index.column() == 0:
            super().paint(painter, option, index)
            return
        
        # 绘制背景
        if option.state & QtWidgets.QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        
        # 绘制文本（支持换行）
        text = index.data() or ""
        if text:
            painter.save()
            if option.state & QtWidgets.QStyle.State_Selected:
                painter.setPen(option.palette.highlightedText().color())
            else:
                painter.setPen(option.palette.text().color())
            
            # 文本区域留一点边距
            text_rect = option.rect.adjusted(4, 2, -4, -2)
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, text)
            painter.restore()
    
    def sizeHint(self, option, index):
        """计算单元格大小 - 根据文本内容自动计算高度"""
        if index.column() == 0:
            return super().sizeHint(option, index)
        
        text = index.data() or ""
        if not text:
            return super().sizeHint(option, index)
        
        # 获取列宽
        table = self.parent()
        col_width = table.columnWidth(index.column()) if table else 200
        
        # 计算文本需要的高度
        fm = option.fontMetrics
        text_rect = fm.boundingRect(0, 0, col_width - 8, 10000, 
                                     Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, text)
        
        # 返回计算的高度，加上边距
        return QtCore.QSize(col_width, max(30, text_rect.height() + 8))
    
    def editorEvent(self, event, model, option, index):
        """捕获双击事件的位置"""
        if event.type() == QtCore.QEvent.MouseButtonDblClick:
            self._click_pos = event.pos() - option.rect.topLeft()
        return super().editorEvent(event, model, option, index)
    
    def createEditor(self, parent, option, index):
        """创建多行文本编辑器"""
        # 只对可编辑列使用多行编辑器
        if index.column() == 0:
            return super().createEditor(parent, option, index)
        
        editor = QtWidgets.QTextEdit(parent)
        editor.setAcceptRichText(False)
        editor.setLineWrapMode(QtWidgets.QTextEdit.WidgetWidth)
        # 去掉边框，融入表格
        editor.setFrameShape(QtWidgets.QFrame.NoFrame)
        editor.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        table = self.parent()
        row = index.row()
        
        # 保存原始行高
        self._editing_row = row
        self._original_height = table.rowHeight(row)
        
        # 计算需要的行高
        text = index.data() or ""
        fm = editor.fontMetrics()
        col_width = table.columnWidth(index.column())
        text_width = fm.horizontalAdvance(text)
        
        if text_width > col_width and col_width > 0:
            lines_needed = (text_width // col_width) + 1
            line_height = fm.height() + 4
            new_height = max(self._original_height, int(line_height * lines_needed + 10))
            # 限制最大高度
            new_height = min(new_height, 200)
            table.setRowHeight(row, new_height)
        
        return editor
    
    def setEditorData(self, editor, index):
        """设置编辑器数据"""
        if isinstance(editor, QtWidgets.QTextEdit):
            text = index.data() or ""
            editor.setPlainText(text)
            # 光标定位到点击位置
            if self._click_pos is not None:
                cursor = editor.cursorForPosition(self._click_pos)
                editor.setTextCursor(cursor)
                self._click_pos = None
            else:
                # 默认光标到开头
                cursor = editor.textCursor()
                cursor.movePosition(QtGui.QTextCursor.Start)
                editor.setTextCursor(cursor)
        else:
            super().setEditorData(editor, index)
    
    def setModelData(self, editor, model, index):
        """从编辑器获取数据"""
        if isinstance(editor, QtWidgets.QTextEdit):
            # 获取纯文本，保留换行符
            text = editor.toPlainText()
            model.setData(index, text, Qt.EditRole)
        else:
            super().setModelData(editor, model, index)
    
    def destroyEditor(self, editor, index):
        """编辑结束时恢复原始行高"""
        if self._editing_row is not None and self._original_height is not None:
            table = self.parent()
            if table:
                table.setRowHeight(self._editing_row, self._original_height)
        self._editing_row = None
        self._original_height = None
        super().destroyEditor(editor, index)
    
    def updateEditorGeometry(self, editor, option, index):
        """设置编辑器几何位置"""
        editor.setGeometry(option.rect)


class PageTextDialog(QtWidgets.QDialog):
    """页文本工具窗口 - 显示和编辑当前页面所有标签的 description（双语模式）"""
    
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
        self.setMinimumWidth(800)
        self.setMinimumHeight(400)

        self.init_ui()

        # 连接标签顺序改变信号，实现自动刷新
        if parent and hasattr(parent, 'unique_label_list'):
            parent.unique_label_list.labels_ordered.connect(self.on_labels_ordered)
    
    def init_ui(self):
        """初始化UI"""
        layout = QtWidgets.QVBoxLayout(self)
        
        # 标题标签
        title_label = QtWidgets.QLabel(self.tr("当前页面标签文本内容"))
        title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(title_label)
        
        # 创建表格 - 3列：标签、原文、译文
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels([
            self.tr("标签"),
            self.tr("原文"),
            self.tr("译文")
        ])
        
        # 显示垂直表头，用于拖拽调整行高
        self.table.verticalHeader().setVisible(True)
        self.table.verticalHeader().setDefaultSectionSize(30)
        # 允许拖拽调整行高
        self.table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        
        # 设置列宽 - 允许拖拽调整
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Interactive)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Interactive)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Interactive)
        # 设置默认列宽
        header.setDefaultSectionSize(150)
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(1, 300)
        self.table.setColumnWidth(2, 300)
        # 最后一列拉伸填充剩余空间
        header.setStretchLastSection(True)
        
        self.table.setWordWrap(True)
        
        # 启用编辑
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.DoubleClicked |
                                   QtWidgets.QAbstractItemView.EditKeyPressed)
        
        # 连接单元格改变信号
        self.table.cellChanged.connect(self.on_cell_changed)
        # 连接行选择信号
        self.table.itemSelectionChanged.connect(self.on_row_selected)
        
        # 设置自定义委托，双击编辑时使用多行文本框显示全部文本
        self.table.setItemDelegate(MultiLineDelegate(self.table))

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
    
    def _parse_description(self, description):
        """解析 description，分离原文和译文"""
        if not description:
            return "", ""
        if '/' in description:
            parts = description.split('/', 1)
            return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""
        return description, ""
    
    def _combine_description(self, source, target):
        """合并原文和译文为 description"""
        source = source.strip()
        target = target.strip()
        if target:
            return f"{source}/{target}"
        return source
    
    def refresh_table(self):
        """刷新表格显示 - 双语模式，左右两列"""
        # 断开信号，避免触发 cellChanged
        self.table.cellChanged.disconnect(self.on_cell_changed)

        # 清空表格
        self.table.setRowCount(0)

        # 填充数据 - 只显示可见的形状
        visible_shapes = [s for s in self.shapes if s.visible]
        self.table.setRowCount(len(visible_shapes))

        # 用于显示当前标签是第几个
        display_counters = {}

        for row, shape in enumerate(visible_shapes):
            # 标签列
            label = shape.label or ""
            display_counters[label] = display_counters.get(label, 0) + 1
            
            label_text = f"{row + 1} {label}({display_counters[label]})"
            label_item = QtWidgets.QTableWidgetItem(label_text)
            label_item.setFlags(label_item.flags() & ~Qt.ItemIsEditable)

            # 设置标签颜色
            if hasattr(shape, 'line_color') and shape.line_color:
                color = shape.line_color
                label_item.setBackground(color)
                brightness = (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
                if brightness < 128:
                    label_item.setForeground(QtGui.QColor(255, 255, 255))
                else:
                    label_item.setForeground(QtGui.QColor(0, 0, 0))

            self.table.setItem(row, 0, label_item)

            # 解析原文和译文
            description = shape.description or ""
            source_text, target_text = self._parse_description(description)

            # 原文列（可编辑）
            source_item = QtWidgets.QTableWidgetItem(source_text)
            self.table.setItem(row, 1, source_item)

            # 译文列（可编辑）
            target_item = QtWidgets.QTableWidgetItem(target_text)
            self.table.setItem(row, 2, target_item)

            # 存储 shape 索引
            label_item.setData(Qt.UserRole, self.shapes.index(shape))

        # 重新连接信号
        self.table.cellChanged.connect(self.on_cell_changed)
        
        # 自动调整行高以显示全部文本
        self.table.resizeRowsToContents()
    
    def on_row_selected(self):
        """表格行被选中时，高亮画布上对应的图形"""
        selected_items = self.table.selectedItems()
        if not selected_items:
            return

        row = selected_items[0].row()
        item = self.table.item(row, 0) 
        if not item:
            return

        shape_index = item.data(Qt.UserRole)
        if shape_index is None or shape_index >= len(self.shapes):
            return

        shape_to_select = self.shapes[shape_index]

        if self.parent and hasattr(self.parent, 'canvas'):
            self.parent.canvas.select_shapes([shape_to_select])

    def on_cell_changed(self, row, column):
        """单元格内容改变时的处理"""
        if column == 0:  # 标签列不处理
            return

        # 获取 shape 索引
        index_item = self.table.item(row, 0)
        if not index_item:
            return

        shape_index = index_item.data(Qt.UserRole)
        if shape_index is None or shape_index >= len(self.shapes):
            return

        shape = self.shapes[shape_index]
        
        # 获取原文和译文
        source_item = self.table.item(row, 1)
        target_item = self.table.item(row, 2)
        source_text = source_item.text() if source_item else ""
        target_text = target_item.text() if target_item else ""
        
        # 组合新的 description
        new_description = self._combine_description(source_text, target_text)

        # 更新 shape 的 description
        if shape.description != new_description:
            shape.description = new_description
            self.description_changed.emit(shape_index, new_description)

            if self.parent and hasattr(self.parent, 'set_dirty'):
                self.parent.set_dirty()
    
    def showEvent(self, event):
        """窗口显示时刷新数据"""
        super().showEvent(event)
        self.refresh_data()
    
    def tr(self, text):
        """翻译函数"""
        return QtWidgets.QApplication.translate("PageTextDialog", text)
