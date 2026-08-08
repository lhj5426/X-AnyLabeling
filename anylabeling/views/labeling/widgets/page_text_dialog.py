# -*- encoding: utf-8 -*-

import os
import os.path as osp

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

        # 反向同步：画布选中 -> 页文本工具对应行（在 __init__ 中连接，
        # 确保无论是首次打开还是复用旧实例都能订阅 selection_changed）
        if parent and hasattr(parent, 'canvas'):
            try:
                parent.canvas.selection_changed.disconnect(
                    self.on_canvas_selection_changed
                )
            except (TypeError, RuntimeError):
                pass
            parent.canvas.selection_changed.connect(
                self.on_canvas_selection_changed
            )
    
    def init_ui(self):
        """初始化UI"""
        layout = QtWidgets.QVBoxLayout(self)
        
        # 标题标签
        title_label = QtWidgets.QLabel(self.tr("当前页面标签文本内容"))
        title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(title_label)
        
        # 批量操作按钮
        button_layout = QtWidgets.QHBoxLayout()
        self.btn_clear_source = QtWidgets.QPushButton(self.tr("清空原文"))
        self.btn_copy_source_to_target = QtWidgets.QPushButton(self.tr("原文复制到译文"))
        self.btn_clear_target = QtWidgets.QPushButton(self.tr("清空译文"))
        self.btn_clear_source.clicked.connect(self.clear_all_source)
        self.btn_copy_source_to_target.clicked.connect(self.copy_source_to_target)
        self.btn_clear_target.clicked.connect(self.clear_all_target)
        button_layout.addWidget(self.btn_clear_source)
        button_layout.addWidget(self.btn_copy_source_to_target)
        button_layout.addWidget(self.btn_clear_target)
        button_layout.addStretch(1)
        layout.addLayout(button_layout)
        
        # 范围设置
        scope_widget = QtWidgets.QWidget()
        scope_layout = QtWidgets.QHBoxLayout(scope_widget)
        scope_layout.setContentsMargins(0, 4, 0, 4)
        scope_layout.addWidget(QtWidgets.QLabel(self.tr("应用范围:")))
        self.scope_group = QtWidgets.QButtonGroup(self)
        self.radio_current = QtWidgets.QRadioButton(self.tr("仅当前页"))
        self.radio_all = QtWidgets.QRadioButton(self.tr("所有页面"))
        self.radio_range = QtWidgets.QRadioButton(self.tr("指定范围"))
        self.radio_current.setChecked(True)
        self.scope_group.addButton(self.radio_current, 1)
        self.scope_group.addButton(self.radio_all, 2)
        self.scope_group.addButton(self.radio_range, 3)
        scope_layout.addWidget(self.radio_current)
        scope_layout.addWidget(self.radio_all)
        scope_layout.addWidget(self.radio_range)
        self.spin_start = QtWidgets.QSpinBox()
        self.spin_start.setPrefix(self.tr("从: "))
        self.spin_end = QtWidgets.QSpinBox()
        self.spin_end.setPrefix(self.tr("到: "))
        self.spin_start.setEnabled(False)
        self.spin_end.setEnabled(False)
        self.radio_range.toggled.connect(lambda checked: (
            self.spin_start.setEnabled(checked),
            self.spin_end.setEnabled(checked)
        ))
        scope_layout.addWidget(self.spin_start)
        scope_layout.addWidget(self.spin_end)
        scope_layout.addStretch()
        layout.addWidget(scope_widget)
        
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

            # 原文和译文：直接读 shape 字段
            source_text = shape.description or ""
            target_text = getattr(shape, "translation", "")

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

    def on_canvas_selection_changed(self, selected_shapes):
        """画布选中变化时，同步表格行选中（反向同步）

        阻断 table 信号以避免 select_shapes -> selection_changed 回环。
        """
        self.table.blockSignals(True)
        try:
            self.table.clearSelection()
            if not selected_shapes:
                return
            target = selected_shapes[0]
            if target not in self.shapes:
                return
            target_index = self.shapes.index(target)
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item and item.data(Qt.UserRole) == target_index:
                    self.table.selectRow(row)
                    self.table.scrollToItem(
                        item, QtWidgets.QAbstractItemView.PositionAtCenter
                    )
                    break
        finally:
            self.table.blockSignals(False)

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

        # 直接写入 shape 的 description 和 translation 字段
        changed = False
        if shape.description != source_text:
            shape.description = source_text
            changed = True
        if getattr(shape, "translation", "") != target_text:
            shape.translation = target_text
            changed = True

        if changed:
            # 兼容旧代码：通过 description 信号传递修改
            self.description_changed.emit(shape_index, source_text)

            if self.parent and hasattr(self.parent, 'set_dirty'):
                self.parent.set_dirty()
    
    def _apply_to_all_rows(self, apply_func):
        """对当前页所有可见 shape 应用操作，直接修改 shape 对象并刷新表格"""
        for row in range(self.table.rowCount()):
            index_item = self.table.item(row, 0)
            if not index_item:
                continue
            shape_index = index_item.data(Qt.UserRole)
            if shape_index is None or shape_index >= len(self.shapes):
                continue
            shape = self.shapes[shape_index]
            apply_func(shape)

        self.refresh_table()
        if self.parent and hasattr(self.parent, 'set_dirty'):
            self.parent.set_dirty()

    def _get_scope_files(self):
        """返回需要处理的图片文件列表"""
        scope = self.scope_group.checkedId()  # 1=当前页, 2=全部, 3=范围
        if scope == 1:
            # 仅当前页
            if self.parent and hasattr(self.parent, 'filename'):
                return [self.parent.filename]
            return []

        # 获取所有图片文件
        image_files = []
        if self.parent and hasattr(self.parent, 'image_list'):
            image_files = list(self.parent.image_list)
        elif self.parent and hasattr(self.parent, 'filename'):
            # 没有 image_list 但有当前图片，返回当前图片
            image_files = [self.parent.filename]

        if not image_files:
            return []

        if scope == 2:
            return image_files
        elif scope == 3:
            start = self.spin_start.value() - 1
            end = self.spin_end.value()
            return image_files[max(0, start):min(len(image_files), end)]
        return []

    def _get_label_path(self, img_path):
        """根据图片路径计算对应的 JSON 标注路径，考虑 output_dir"""
        json_path = osp.splitext(img_path)[0] + ".json"
        if self.parent and getattr(self.parent, 'output_dir', None):
            json_path = osp.join(self.parent.output_dir, osp.basename(json_path))
        return json_path

    def _apply_to_image(self, img_path, apply_func):
        """对单个图片的标注JSON应用操作并保存"""
        import json
        json_path = self._get_label_path(img_path)
        if not json_path or not os.path.exists(json_path):
            return
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return

        modified = False
        for shape in data.get('shapes', []):
            desc = shape.get('description', '') or ''
            trans = shape.get('translation', '') or ''
            old_desc, old_trans = desc, trans
            desc, trans = apply_func(desc, trans)
            if desc != old_desc or trans != old_trans:
                shape['description'] = desc
                shape['translation'] = trans
                modified = True

        if modified:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def clear_all_source(self):
        """清空所有原文"""
        self._apply_to_all_rows(lambda shape: setattr(shape, 'description', ''))
        scope = self.scope_group.checkedId()
        if scope != 1:
            for img_path in self._get_scope_files():
                self._apply_to_image(img_path, lambda d, t: ("", t))

    def copy_source_to_target(self):
        """原文复制到译文"""
        self._apply_to_all_rows(
            lambda shape: setattr(shape, 'translation', shape.description or '')
        )
        scope = self.scope_group.checkedId()
        if scope != 1:
            for img_path in self._get_scope_files():
                self._apply_to_image(img_path, lambda d, t: (d, d))

    def clear_all_target(self):
        """清空所有译文"""
        self._apply_to_all_rows(lambda shape: setattr(shape, 'translation', ''))
        scope = self.scope_group.checkedId()
        if scope != 1:
            for img_path in self._get_scope_files():
                self._apply_to_image(img_path, lambda d, t: (d, ""))

    def update_page_range(self, current_page, total_pages):
        total_pages = max(1, int(total_pages or 1))
        current_page = max(1, min(int(current_page or 1), total_pages))
        self.spin_start.setRange(1, total_pages)
        self.spin_end.setRange(1, total_pages)
        self.spin_start.setValue(current_page)
        self.spin_end.setValue(total_pages)
    
    def showEvent(self, event):
        """窗口显示时刷新数据"""
        super().showEvent(event)
        self.refresh_data()
        # 更新范围 spinbox
        if self.parent and hasattr(self.parent, '_current_file_list_page_state'):
            current_page, total_pages = self.parent._current_file_list_page_state()
            self.update_page_range(current_page, total_pages)
        elif self.parent and hasattr(self.parent, 'image_list'):
            n = len(self.parent.image_list)
            self.update_page_range(1, n)
    
    def tr(self, text):
        """翻译函数"""
        return QtWidgets.QApplication.translate("PageTextDialog", text)
