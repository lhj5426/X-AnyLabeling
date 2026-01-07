# -*- encoding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt

from .. import utils
from .label_category_widget import LabelCategoryWidget
from .object_list_widget import ObjectListWidget


class TrafficLightDelegate(QtWidgets.QStyledItemDelegate):
    """Delegate to draw traffic light indicators for object list items"""
    
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.config = config or {}
    
    def paint(self, painter, option, index):
        # Draw the default item
        super().paint(painter, option, index)
        
        dot_radius = 4
        dot_diameter = dot_radius * 2
        spacing = 2
        dot_y = option.rect.center().y()
        
        # Define fixed positions for each dot from right to left
        # Position 1 (Rightmost): Selected (红色)
        pos1_x = option.rect.right() - dot_radius - 5
        
        # Position 2: Locked/Unlocked (黄色/蓝色)
        pos2_x = pos1_x - (dot_diameter + spacing)
        
        # Position 3: Edited (绿色)
        pos3_x = pos2_x - (dot_diameter + spacing)
        
        # Position 4 (Leftmost): Difficult (紫色)
        pos4_x = pos3_x - (dot_diameter + spacing)
        
        shape = index.data(Qt.UserRole)
        
        # 1. Draw Selected dot (Position 1)
        if option.state & QtWidgets.QStyle.State_Selected:
            painter.save()
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            selected_color_rgb = self.config.get("traffic_light_colors", {}).get("selected", [255, 0, 0])
            painter.setBrush(QtGui.QBrush(QtGui.QColor(*selected_color_rgb)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QtCore.QPointF(pos1_x, dot_y), dot_radius, dot_radius)
            painter.restore()
        
        # 2. Draw Locked/Unlocked dot (Position 2)
        if shape and self.parent_widget:
            # 使用shape的is_label_locked()方法来判断是否锁定
            is_locked = shape.is_label_locked()
            
            # 只有被锁定过的标签才显示锁定状态灯
            if is_locked or (hasattr(shape, 'is_session_unlocked') and shape.is_session_unlocked):
                painter.save()
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                
                if is_locked:
                    # 当前锁定状态
                    if hasattr(shape, 'is_session_unlocked') and shape.is_session_unlocked:
                        # Session解锁：显示蓝色
                        color_rgb = self.config.get("traffic_light_colors", {}).get("unlocked", [0, 0, 255])
                    else:
                        # 完全锁定：显示黄色
                        color_rgb = self.config.get("traffic_light_colors", {}).get("locked", [255, 255, 0])
                else:
                    # 曾经锁定，现在解锁：显示蓝色
                    color_rgb = self.config.get("traffic_light_colors", {}).get("unlocked", [0, 0, 255])
                
                color = QtGui.QColor(*color_rgb)
                painter.setBrush(QtGui.QBrush(color))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QtCore.QPointF(pos2_x, dot_y), dot_radius, dot_radius)
                painter.restore()
        
        # 3. Draw Edited dot (Position 3)
        if shape and shape.is_edited:
            painter.save()
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            edited_color_rgb = self.config.get("traffic_light_colors", {}).get("edited", [0, 255, 0])
            painter.setBrush(QtGui.QBrush(QtGui.QColor(*edited_color_rgb)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QtCore.QPointF(pos3_x, dot_y), dot_radius, dot_radius)
            painter.restore()
        
        # 4. Draw Difficult dot (Position 4 - Leftmost)
        if shape and hasattr(shape, 'difficult') and shape.difficult:
            painter.save()
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            difficult_color_rgb = self.config.get("traffic_light_colors", {}).get("difficult", [128, 0, 128])
            painter.setBrush(QtGui.QBrush(QtGui.QColor(*difficult_color_rgb)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QtCore.QPointF(pos4_x, dot_y), dot_radius, dot_radius)
            painter.restore()


class ObjectManagerDialog(QtWidgets.QDialog):
    order_changed = QtCore.pyqtSignal(list)
    selection_changed = QtCore.pyqtSignal(list)
    item_double_clicked = QtCore.pyqtSignal(object)
    apply_to_all_requested = QtCore.pyqtSignal(list, bool)
    edit_requested = QtCore.pyqtSignal()
    delete_requested = QtCore.pyqtSignal()
    union_requested = QtCore.pyqtSignal()

    def __init__(self, items, parent=None):
        super(ObjectManagerDialog, self).__init__(parent)
        self.main_window = parent
        self.setWindowTitle(self.tr("标签页管理器"))
        self.resize(355, 452)
        # 设置窗口标志：移除帮助按钮，添加最小化按钮
        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.WindowMinimizeButtonHint |
            QtCore.Qt.WindowMaximizeButtonHint |
            QtCore.Qt.WindowCloseButtonHint
        )

        # Get config from parent
        self.config = parent._config if parent and hasattr(parent, '_config') else {}

        # Restore window position and size
        self.restore_window_position()

        # ========== 属性编辑面板 ==========
        self.properties_group = QtWidgets.QGroupBox(self.tr("选中矩形属性"))
        properties_layout = QtWidgets.QVBoxLayout()

        # 标签显示（只读）
        label_layout = QtWidgets.QHBoxLayout()
        label_layout.setSpacing(5)  # 减小间距
        label_text = QtWidgets.QLabel(self.tr("标签:"))
        label_text.setFixedWidth(40)  # 固定标签文字宽度
        label_layout.addWidget(label_text)
        self.label_combo = QtWidgets.QComboBox()
        self.label_combo.setEditable(True)
        self.label_combo.setPlaceholderText(self.tr("输入或选择标签"))
        label_layout.addWidget(self.label_combo)
        properties_layout.addLayout(label_layout)

        # 位置
        properties_layout.addWidget(QtWidgets.QLabel(self.tr("位置:")))
        pos_layout = QtWidgets.QHBoxLayout()
        pos_layout.addWidget(QtWidgets.QLabel("X:"))
        self.x_spinbox = QtWidgets.QDoubleSpinBox()
        self.x_spinbox.setRange(-999999, 999999)
        self.x_spinbox.setDecimals(2)
        pos_layout.addWidget(self.x_spinbox)
        pos_layout.addWidget(QtWidgets.QLabel("Y:"))
        self.y_spinbox = QtWidgets.QDoubleSpinBox()
        self.y_spinbox.setRange(-999999, 999999)
        self.y_spinbox.setDecimals(2)
        pos_layout.addWidget(self.y_spinbox)
        properties_layout.addLayout(pos_layout)

        # 尺寸
        properties_layout.addWidget(QtWidgets.QLabel(self.tr("尺寸:")))
        size_layout = QtWidgets.QHBoxLayout()
        size_layout.addWidget(QtWidgets.QLabel("W:"))
        self.w_spinbox = QtWidgets.QDoubleSpinBox()
        self.w_spinbox.setRange(0, 999999)
        self.w_spinbox.setDecimals(2)
        size_layout.addWidget(self.w_spinbox)
        size_layout.addWidget(QtWidgets.QLabel("H:"))
        self.h_spinbox = QtWidgets.QDoubleSpinBox()
        self.h_spinbox.setRange(0, 999999)
        self.h_spinbox.setDecimals(2)
        size_layout.addWidget(self.h_spinbox)
        properties_layout.addLayout(size_layout)

        # 中心点
        properties_layout.addWidget(QtWidgets.QLabel(self.tr("中心点:")))
        center_layout = QtWidgets.QHBoxLayout()
        center_layout.addWidget(QtWidgets.QLabel("CX:"))
        self.cx_spinbox = QtWidgets.QDoubleSpinBox()
        self.cx_spinbox.setRange(-999999, 999999)
        self.cx_spinbox.setDecimals(2)
        center_layout.addWidget(self.cx_spinbox)
        center_layout.addWidget(QtWidgets.QLabel("CY:"))
        self.cy_spinbox = QtWidgets.QDoubleSpinBox()
        self.cy_spinbox.setRange(-999999, 999999)
        self.cy_spinbox.setDecimals(2)
        center_layout.addWidget(self.cy_spinbox)
        properties_layout.addLayout(center_layout)

        # 旋转角度
        self.rotation_label = QtWidgets.QLabel(self.tr("旋转角度: (仅旋转矩形)"))
        properties_layout.addWidget(self.rotation_label)
        rotation_layout = QtWidgets.QHBoxLayout()
        self.rotation_spinbox = QtWidgets.QDoubleSpinBox()
        self.rotation_spinbox.setWrapping(True)
        self.rotation_spinbox.setRange(0, 359)
        self.rotation_spinbox.setDecimals(2)
        rotation_layout.addWidget(self.rotation_spinbox)
        properties_layout.addLayout(rotation_layout)

        # 新建矩形按钮
        self.btn_create_rect = QtWidgets.QPushButton(self.tr("新建矩形"))
        self.btn_create_rect.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        properties_layout.addWidget(self.btn_create_rect)

        self.properties_group.setLayout(properties_layout)

        # 存储当前选中的shape和属性
        self.current_shape = None
        self._updating_from_shape = False  # 标记是否正在从shape更新UI

        # ========== 分类控制区域 ==========
        # Left side: Category controls
        self.category_list = LabelCategoryWidget()
        categories = sorted(list(set(item.shape().label for item in items)))
        for category in categories:
            self.category_list.add_category(category)
        
        self.btn_move_category_top = QtWidgets.QPushButton(self.tr("置顶分类"))
        self.btn_move_category_bottom = QtWidgets.QPushButton(self.tr("置底分类"))
        self.btn_delete_by_category = QtWidgets.QPushButton(self.tr("按分类删除"))
        self.btn_delete_by_category.setStyleSheet("color: red;")
        self.btn_edit_label = QtWidgets.QPushButton(self.tr("修改标签"))
        self.apply_all_checkbox = QtWidgets.QCheckBox(self.tr("应用到全部"))
        self.btn_select_all = QtWidgets.QPushButton(self.tr("全选标签"))

        # Right side: Full object list with drag-drop
        self.list_widget = ObjectListWidget()
        self.list_widget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.list_widget.setDefaultDropAction(QtCore.Qt.MoveAction)
        self.list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.list_widget.installEventFilter(self)
        
        # Apply traffic light delegate to show status indicators
        self.traffic_light_delegate = TrafficLightDelegate(self, self.config)
        self.list_widget.setItemDelegate(self.traffic_light_delegate)

        for item in items:
            new_item = QtWidgets.QListWidgetItem(item.text())
            new_item.setBackground(item.background())
            new_item.setData(QtCore.Qt.UserRole, item.shape())
            new_item.setFlags(item.flags() & ~QtCore.Qt.ItemIsUserCheckable) # No checkbox
            self.list_widget.addItem(new_item)

        # Create buttons for object list operations
        self.btn_move_up = QtWidgets.QPushButton(self.tr("上移"))
        self.btn_move_down = QtWidgets.QPushButton(self.tr("下移"))
        self.btn_delete_selected = QtWidgets.QPushButton(self.tr("删除选中"))
        self.btn_delete_selected.setStyleSheet("color: red;")
        self.btn_move_top = QtWidgets.QPushButton(self.tr("置顶"))
        self.btn_move_bottom = QtWidgets.QPushButton(self.tr("置底"))

        # Layouts - 三列布局
        # 最左侧：属性编辑面板 - 使用容器widget以便完全隐藏
        self.properties_container = QtWidgets.QWidget()
        v_layout_leftmost = QtWidgets.QVBoxLayout(self.properties_container)
        v_layout_leftmost.setContentsMargins(0, 0, 0, 0)
        v_layout_leftmost.addWidget(self.properties_group)
        v_layout_leftmost.addStretch()
        # 默认隐藏属性面板
        self.properties_container.hide()

        # 中间：分类控制区域 - 使用容器widget并设置固定宽度
        self.middle_container = QtWidgets.QWidget()
        self.middle_container.setFixedWidth(160)  # 固定宽度，防止展开后变宽
        v_layout_middle = QtWidgets.QVBoxLayout(self.middle_container)
        v_layout_middle.setContentsMargins(0, 0, 0, 0)
        v_layout_middle.addWidget(QtWidgets.QLabel(self.tr("分类整体排序")))
        v_layout_middle.addWidget(self.category_list)

        # 按钮区域 - 2列布局
        # 第1排：置顶分类 | 置底分类
        h_button_layout_1 = QtWidgets.QHBoxLayout()
        h_button_layout_1.addWidget(self.btn_move_category_top)
        h_button_layout_1.addWidget(self.btn_move_category_bottom)
        v_layout_middle.addLayout(h_button_layout_1)

        # 第2排：修改标签 | 按分类删除
        h_button_layout_2 = QtWidgets.QHBoxLayout()
        h_button_layout_2.addWidget(self.btn_edit_label)
        h_button_layout_2.addWidget(self.btn_delete_by_category)
        v_layout_middle.addLayout(h_button_layout_2)

        # 第3排：全选标签 | 删除选中
        h_button_layout_3 = QtWidgets.QHBoxLayout()
        h_button_layout_3.addWidget(self.btn_select_all)
        h_button_layout_3.addWidget(self.btn_delete_selected)
        v_layout_middle.addLayout(h_button_layout_3)

        # 第4排：上移 | 下移
        h_button_layout_4 = QtWidgets.QHBoxLayout()
        h_button_layout_4.addWidget(self.btn_move_up)
        h_button_layout_4.addWidget(self.btn_move_down)
        v_layout_middle.addLayout(h_button_layout_4)

        # 第5排：置顶 | 置底
        h_button_layout_5 = QtWidgets.QHBoxLayout()
        h_button_layout_5.addWidget(self.btn_move_top)
        h_button_layout_5.addWidget(self.btn_move_bottom)
        v_layout_middle.addLayout(h_button_layout_5)

        # 第6排：锁定标签 | 解锁标签
        self.btn_lock_labels = QtWidgets.QPushButton(self.tr("锁定标签"))
        self.btn_unlock_labels = QtWidgets.QPushButton(self.tr("解锁标签"))
        h_button_layout_6 = QtWidgets.QHBoxLayout()
        h_button_layout_6.addWidget(self.btn_lock_labels)
        h_button_layout_6.addWidget(self.btn_unlock_labels)
        v_layout_middle.addLayout(h_button_layout_6)

        # 第7排：应用到全部 和 展开/收起属性面板按钮
        h_button_layout_7 = QtWidgets.QHBoxLayout()
        self.btn_toggle_properties = QtWidgets.QPushButton(self.tr("▶"))  # 默认隐藏，箭头向右
        self.btn_toggle_properties.setFixedWidth(24)
        self.btn_toggle_properties.clicked.connect(self._toggle_properties_panel)
        h_button_layout_7.addWidget(self.btn_toggle_properties)
        h_button_layout_7.addWidget(self.apply_all_checkbox)
        h_button_layout_7.addStretch()
        v_layout_middle.addLayout(h_button_layout_7)
        v_layout_middle.addStretch()

        # 最右侧：对象列表
        v_layout_right = QtWidgets.QVBoxLayout()
        v_layout_right.addWidget(QtWidgets.QLabel(self.tr("对象列表 (可拖拽排序)")))
        v_layout_right.addWidget(self.list_widget)

        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.addWidget(self.properties_container)  # 最左侧：属性面板容器
        main_layout.addWidget(self.middle_container)      # 中间：分类和按钮（固定宽度）
        main_layout.addLayout(v_layout_right, 1)          # 最右侧：对象列表（占用剩余空间）

        # Connections
        self.list_widget.order_changed.connect(self._emit_order_changed)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list_widget.itemSelectionChanged.connect(self._on_internal_selection_changed)
        self.list_widget.customContextMenuRequested.connect(self._pop_list_menu)
        
        self.category_list.category_selection_changed.connect(self._on_category_selection_changed)
        self.category_list.category_double_clicked.connect(self._on_category_double_clicked)
        self.btn_move_category_top.clicked.connect(lambda: self.reorder_by_category(move_to_top=True))
        self.btn_move_category_bottom.clicked.connect(lambda: self.reorder_by_category(move_to_top=False))
        self.btn_delete_by_category.clicked.connect(self.delete_by_category)

        self.btn_select_all.clicked.connect(self.select_all_items)
        self.btn_move_up.clicked.connect(lambda: self.move_items(-1))
        self.btn_move_down.clicked.connect(lambda: self.move_items(1))
        self.btn_delete_selected.clicked.connect(self.delete_requested.emit)
        self.btn_move_top.clicked.connect(self.move_to_top)
        self.btn_move_bottom.clicked.connect(self.move_to_bottom)
        self.btn_edit_label.clicked.connect(self.edit_requested.emit)
        self.btn_lock_labels.clicked.connect(self.lock_selected_labels)
        self.btn_unlock_labels.clicked.connect(self.unlock_selected_labels)

        # 实时更新连接
        self.x_spinbox.valueChanged.connect(self._on_position_changed)
        self.y_spinbox.valueChanged.connect(self._on_position_changed)
        self.w_spinbox.valueChanged.connect(self._on_size_changed)
        self.h_spinbox.valueChanged.connect(self._on_size_changed)
        self.cx_spinbox.valueChanged.connect(self._on_center_changed)
        self.cy_spinbox.valueChanged.connect(self._on_center_changed)
        self.rotation_spinbox.valueChanged.connect(self._on_rotation_changed)
        self.btn_create_rect.clicked.connect(self._on_create_rectangle)

        self.update_button_states()

        # Add shortcut for selecting all items
        self.select_all_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+A"), self)
        self.select_all_shortcut.activated.connect(self.select_all_items)

    def eventFilter(self, source, event):
        if source is self.list_widget and event.type() == QtCore.QEvent.KeyPress:
            # Ctrl+E: Edit label
            if (event.key() == QtCore.Qt.Key_E and
                event.modifiers() == QtCore.Qt.ControlModifier):
                if self.list_widget.selectedItems():
                    self.edit_requested.emit()
                return True

            # Delete or Backspace: Delete selected items
            if event.key() in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace):
                if self.list_widget.selectedItems():
                    self.delete_requested.emit()
                return True

        return super(ObjectManagerDialog, self).eventFilter(source, event)

    def _pop_list_menu(self, point):
        if not self.list_widget.selectedItems():
            return

        menu = QtWidgets.QMenu()
        edit_action = menu.addAction(utils.new_icon('edit'), self.tr("编辑标签 (Ctrl+E)"))
        delete_action = menu.addAction(utils.new_icon('cancel'), self.tr("删除标签 (Delete)"))
        union_action = menu.addAction(utils.new_icon('union'), self.tr("合并选中"))

        union_action.setEnabled(len(self.list_widget.selectedItems()) > 1)

        action = menu.exec_(self.list_widget.mapToGlobal(point))

        if action == edit_action:
            self.edit_requested.emit()
        elif action == delete_action:
            self.delete_requested.emit()
        elif action == union_action:
            self.union_requested.emit()

    def move_items(self, offset):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return

        # Store selected shapes before any modification
        selected_shapes = [item.data(QtCore.Qt.UserRole) for item in selected_items]

        # Sort items by row to move them correctly
        selected_items.sort(key=lambda x: self.list_widget.row(x), reverse=(offset > 0))

        for item in selected_items:
            current_row = self.list_widget.row(item)
            new_row = current_row + offset
            if 0 <= new_row < self.list_widget.count():
                taken_item = self.list_widget.takeItem(current_row)
                self.list_widget.insertItem(new_row, taken_item)

        self._emit_order_changed()
        # After the entire refresh cycle triggered by the signal is complete,
        # restore the selection.
        QtCore.QTimer.singleShot(0, lambda: self.sync_selection(selected_shapes))

    def move_to_top(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return
        
        selected_shapes = [item.data(QtCore.Qt.UserRole) for item in selected_items]
        selected_items.sort(key=lambda x: self.list_widget.row(x))

        for i, item in enumerate(selected_items):
            current_row = self.list_widget.row(item)
            taken_item = self.list_widget.takeItem(current_row)
            self.list_widget.insertItem(i, taken_item)

        self._emit_order_changed()
        QtCore.QTimer.singleShot(0, lambda: self.sync_selection(selected_shapes))

    def move_to_bottom(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return

        selected_shapes = [item.data(QtCore.Qt.UserRole) for item in selected_items]
        selected_items.sort(key=lambda x: self.list_widget.row(x), reverse=True)
        
        count = self.list_widget.count()
        for i, item in enumerate(selected_items):
            current_row = self.list_widget.row(item)
            taken_item = self.list_widget.takeItem(current_row)
            self.list_widget.insertItem(count - 1 - i, taken_item)

        self._emit_order_changed()
        QtCore.QTimer.singleShot(0, lambda: self.sync_selection(selected_shapes))

    def reorder_by_category(self, move_to_top):
        checked_categories = self.category_list.get_checked_categories()
        if not checked_categories:
            QtWidgets.QMessageBox.warning(self, self.tr("无选中分类"), self.tr("请先在左侧选择要操作的分类。"))
            return

        if self.apply_all_checkbox.isChecked():
            self.apply_to_all_requested.emit(checked_categories, move_to_top)
            return

        selected_items_data = []
        other_items_data = []

        # 1. Read all item data into memory
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            shape = item.data(QtCore.Qt.UserRole)
            item_data = {
                'text': item.text(),
                'background': item.background(),
                'shape': shape,
                'flags': item.flags()
            }
            if shape.label in checked_categories:
                selected_items_data.append(item_data)
            else:
                other_items_data.append(item_data)

        if not selected_items_data:
            return

        # 2. Determine the new order
        if move_to_top:
            new_items_data = selected_items_data + other_items_data
        else:
            new_items_data = other_items_data + selected_items_data
        
        # 3. Repopulate the list widget
        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        for data in new_items_data:
            new_item = QtWidgets.QListWidgetItem(data['text'])
            new_item.setBackground(data['background'])
            new_item.setData(QtCore.Qt.UserRole, data['shape'])
            new_item.setFlags(data['flags'])
            self.list_widget.addItem(new_item)
        
        self.list_widget.blockSignals(False)
        self._emit_order_changed()

    def _emit_order_changed(self):
        """Emit the order_changed signal with the current order of shapes."""
        if not self.apply_all_checkbox.isChecked():
            self.order_changed.emit(self.get_ordered_shapes())

    def get_ordered_shapes(self):
        shapes = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            shapes.append(item.data(QtCore.Qt.UserRole))
        return shapes

    def update_items(self, items):
        """Clear and repopulate the lists with new items."""
        self.list_widget.blockSignals(True)
        self.category_list.blockSignals(True)

        try:
            current_selection = [item.data(QtCore.Qt.UserRole) for item in self.list_widget.selectedItems()]

            self.list_widget.clear()
            self.category_list.clear()

            if not items:
                return

            categories = sorted(list(set(item.shape().label for item in items)))
            for category in categories:
                self.category_list.add_category(category)

            # 更新标签下拉列表（带颜色）
            self.label_combo.blockSignals(True)
            current_text = self.label_combo.currentText()
            self.label_combo.clear()

            # 为每个标签添加颜色
            for category in categories:
                # 查找该标签的颜色
                color = None
                for item in items:
                    if item.shape().label == category:
                        color = item.background().color()
                        break

                # 添加带颜色的项
                self.label_combo.addItem(category)
                if color:
                    index = self.label_combo.count() - 1
                    self.label_combo.setItemData(index, color, QtCore.Qt.BackgroundRole)

            if current_text:
                self.label_combo.setCurrentText(current_text)
            self.label_combo.blockSignals(False)

            for item in items:
                new_item = QtWidgets.QListWidgetItem(item.text())
                new_item.setBackground(item.background())
                new_item.setData(QtCore.Qt.UserRole, item.shape())
                new_item.setFlags(item.flags() & ~QtCore.Qt.ItemIsUserCheckable)
                self.list_widget.addItem(new_item)

            # Restore selection
            self.sync_selection(current_selection)

        finally:
            self.list_widget.blockSignals(False)
            self.category_list.blockSignals(False)
            # Sync selection from canvas if no local selection is maintained
            if not self.list_widget.selectedItems() and self.main_window and hasattr(self.main_window, "canvas"):
                 self.sync_selection(self.main_window.canvas.selected_shapes)


    def _on_internal_selection_changed(self):
        selected_shapes = []
        for item in self.list_widget.selectedItems():
            selected_shapes.append(item.data(QtCore.Qt.UserRole))
        self.selection_changed.emit(selected_shapes)
        self.update_button_states()
        self._update_properties_panel(selected_shapes)

    def update_button_states(self):
        """Update the enabled state of the buttons based on selection."""
        has_selection = bool(self.list_widget.selectedItems())
        count = self.list_widget.count()
        
        self.btn_move_up.setEnabled(has_selection)
        self.btn_move_down.setEnabled(has_selection)
        self.btn_move_top.setEnabled(has_selection)
        self.btn_move_bottom.setEnabled(has_selection)
        self.btn_delete_selected.setEnabled(has_selection)
        self.btn_edit_label.setEnabled(has_selection)
        self.btn_lock_labels.setEnabled(has_selection)
        self.btn_unlock_labels.setEnabled(has_selection)

        if has_selection:
            selected_rows = [self.list_widget.row(item) for item in self.list_widget.selectedItems()]
            if min(selected_rows) == 0:
                self.btn_move_up.setEnabled(False)
                self.btn_move_top.setEnabled(False)
            if max(selected_rows) == count - 1:
                self.btn_move_down.setEnabled(False)
                self.btn_move_bottom.setEnabled(False)

    def _on_item_double_clicked(self, item):
        shape = item.data(QtCore.Qt.UserRole)
        self.item_double_clicked.emit(shape)

    def sync_selection(self, shapes_to_select):
        self.list_widget.blockSignals(True)
        self.list_widget.clearSelection()
        if shapes_to_select:
            for shape in shapes_to_select:
                for i in range(self.list_widget.count()):
                    item = self.list_widget.item(i)
                    if item.data(QtCore.Qt.UserRole) == shape:
                        item.setSelected(True)
                        self.list_widget.scrollToItem(item)
                        break
        self.list_widget.blockSignals(False)
        self.update_button_states()
        # 更新属性面板以反映画布选择
        self._update_properties_panel(shapes_to_select if shapes_to_select else [])

    def restore_window_position(self):
        """Restore window position and size from settings."""
        settings = QtCore.QSettings()
        geometry = settings.value("object_manager_dialog/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        else:
            # Default position if no settings are found (center of parent)
            if self.parent():
                parent_geometry = self.parent().geometry()
                x = parent_geometry.x() + (parent_geometry.width() - self.width()) // 2
                y = parent_geometry.y() + (parent_geometry.height() - self.height()) // 2
                self.move(x, y)

    def save_window_position(self):
        """Save current window position and size to settings."""
        settings = QtCore.QSettings()
        settings.setValue("object_manager_dialog/geometry", self.saveGeometry())

    def _toggle_properties_panel(self):
        """切换属性面板的显示/隐藏状态"""
        # 固定宽度：隐藏时355，展开时585
        WIDTH_COLLAPSED = 355
        WIDTH_EXPANDED = 585
        
        if self.properties_container.isVisible():
            # 隐藏整个容器widget
            self.properties_container.hide()
            self.btn_toggle_properties.setText("▶")
            # 先设置最大宽度限制，再resize
            self.setMaximumWidth(WIDTH_COLLAPSED)
            self.resize(WIDTH_COLLAPSED, self.height())
            # 恢复最大宽度为无限制（允许用户手动拉大）
            self.setMaximumWidth(16777215)
        else:
            # 显示容器
            self.properties_container.show()
            self.btn_toggle_properties.setText("◀")
            self.resize(WIDTH_EXPANDED, self.height())

    def show(self):
        """Override show to restore from minimized state."""
        if self.isMinimized():
            self.showNormal()
        super(ObjectManagerDialog, self).show()

    def hide(self):
        """Override hide to handle shortcut toggle on minimized window."""
        if self.isMinimized():
            self.showNormal()  # Restore instead of hiding
        else:
            super(ObjectManagerDialog, self).hide() # Hide normally

    def closeEvent(self, event):
        """Handle the window close event."""
        self.save_window_position()
        super(ObjectManagerDialog, self).closeEvent(event)

    def hideEvent(self, event):
        """Handle the window hide event."""
        self.save_window_position()
        super(ObjectManagerDialog, self).hideEvent(event)

    def select_all_items(self):
        """Select all items in the list widget and all shapes on canvas."""
        # Select all items in the list widget
        self.list_widget.selectAll()

        # Also select all shapes on canvas if main_window is available
        if self.main_window and hasattr(self.main_window, 'canvas'):
            self.main_window.canvas.select_all_visible_shapes()

    def _on_category_double_clicked(self, category_name):
        """双击分类时，自动勾选该分类并弹出修改标签对话框"""
        # 1. 先取消所有分类的勾选
        for i in range(self.category_list.count()):
            item = self.category_list.item(i)
            if item.checkState() == QtCore.Qt.Checked:
                item.setCheckState(QtCore.Qt.Unchecked)
        
        # 2. 勾选双击的分类
        self.category_list.set_category_checked(category_name, True)
        
        # 3. 选中该分类的所有标签
        self._on_category_selection_changed(category_name, True)
        
        # 4. 触发修改标签对话框
        self.edit_requested.emit()

    def _on_category_selection_changed(self, category_name, is_checked):
        """Select/deselect all shapes of a given category in the list widget and on the canvas."""
        # Block signals to prevent excessive updates while changing selection
        self.list_widget.blockSignals(True)

        # Add or remove items from the current selection based on the checkbox action
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            shape = item.data(QtCore.Qt.UserRole)
            if shape.label == category_name:
                item.setSelected(is_checked)  # Select or deselect the item

        self.list_widget.blockSignals(False)

        # Manually trigger the internal selection changed logic to ensure all states are updated
        self._on_internal_selection_changed()

        # Explicitly set focus to the list widget to ensure it captures keyboard events.
        self.list_widget.setFocus()

    def delete_by_category(self):
        """Deletes all shapes that belong to the checked categories without confirmation."""
        checked_categories = self.category_list.get_checked_categories()
        if not checked_categories:
            return

        if not (self.main_window and hasattr(self.main_window, 'canvas')):
            return

        shapes_to_delete = []
        for shape in self.main_window.canvas.shapes:
            if shape.label in checked_categories:
                shapes_to_delete.append(shape)

        if shapes_to_delete:
            # 1. Select the shapes to be deleted.
            self.selection_changed.emit(shapes_to_delete)
            # 2. Request the deletion of the selection.
            # Use a QTimer to ensure the selection signal is processed before the deletion signal.
            QtCore.QTimer.singleShot(0, self.delete_requested.emit)

    # ========== 属性编辑面板方法 ==========

    def _update_properties_panel(self, selected_shapes):
        """更新属性编辑面板显示选中矩形的属性"""
        if len(selected_shapes) == 1:
            shape = selected_shapes[0]

            # 保存当前选中的shape
            self.current_shape = shape

            # 启用所有控件
            self.x_spinbox.setEnabled(True)
            self.y_spinbox.setEnabled(True)
            self.w_spinbox.setEnabled(True)
            self.h_spinbox.setEnabled(True)
            self.cx_spinbox.setEnabled(True)
            self.cy_spinbox.setEnabled(True)

            # 显示标签 - 查找对应的列表项以获取完整文本和颜色
            label_text = shape.label
            label_color = None
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                if item.data(QtCore.Qt.UserRole) == shape:
                    label_text = item.text()  # 获取完整文本，如 "14 qipao(8)"
                    label_color = item.background()  # 获取背景颜色
                    break

            self.label_combo.setCurrentText(label_text)
            if label_color:
                # 设置背景颜色
                palette = self.label_combo.palette()
                palette.setColor(QtGui.QPalette.Base, label_color.color())
                self.label_combo.setPalette(palette)

            # 计算边界框
            if shape.points:
                rect = self._get_shape_rect(shape)
                if rect:
                    # 标记正在从shape更新UI，避免触发实时更新
                    self._updating_from_shape = True

                    # 设置位置和尺寸
                    self.x_spinbox.setValue(rect.left())
                    self.y_spinbox.setValue(rect.top())
                    self.w_spinbox.setValue(rect.width())
                    self.h_spinbox.setValue(rect.height())
                    self.cx_spinbox.setValue(rect.center().x())
                    self.cy_spinbox.setValue(rect.center().y())

                    # 保存当前宽高比
                    if rect.height() > 0:
                        self.current_aspect_ratio = rect.width() / rect.height()

                    self._updating_from_shape = False

            # 旋转角度（仅旋转矩形）
            if shape.shape_type in ['rotation', 'rotation3']:
                self.rotation_spinbox.setEnabled(True)

                # 计算旋转角度
                if hasattr(shape, 'direction') and shape.direction is not None:
                    import math
                    angle_degrees = math.degrees(shape.direction) % 360
                    self._updating_from_shape = True
                    self.rotation_spinbox.setValue(angle_degrees)
                    self._updating_from_shape = False
                else:
                    self._updating_from_shape = True
                    self.rotation_spinbox.setValue(0)
                    self._updating_from_shape = False
            else:
                self.rotation_spinbox.setEnabled(False)
                self._updating_from_shape = True
                self.rotation_spinbox.setValue(0)
                self._updating_from_shape = False

        else:
            # 多选或未选中，禁用所有控件
            self._clear_properties_panel()

    def _clear_properties_panel(self):
        """清空属性编辑面板（但保持启用状态以便新建矩形）"""
        self.current_shape = None

        self.label_combo.setCurrentText("")
        self.label_combo.lineEdit().setPlaceholderText(self.tr("输入或选择标签"))

        # 重置背景颜色为默认
        palette = self.label_combo.palette()
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor(255, 255, 255))  # 白色
        self.label_combo.setPalette(palette)

        self.x_spinbox.setValue(0)
        self.y_spinbox.setValue(0)
        self.w_spinbox.setValue(0)
        self.h_spinbox.setValue(0)
        self.cx_spinbox.setValue(0)
        self.cy_spinbox.setValue(0)
        self.rotation_spinbox.setValue(0)

        # 保持所有输入框启用，以便用户可以输入坐标新建矩形
        self.label_combo.setEnabled(True)
        self.x_spinbox.setEnabled(True)
        self.y_spinbox.setEnabled(True)
        self.w_spinbox.setEnabled(True)
        self.h_spinbox.setEnabled(True)
        self.cx_spinbox.setEnabled(True)
        self.cy_spinbox.setEnabled(True)
        self.rotation_spinbox.setEnabled(False)  # 旋转角度仅在编辑旋转矩形时启用

    # ========== 实时更新方法 ==========

    def _on_position_changed(self):
        """位置改变时实时更新shape"""
        if self._updating_from_shape or not self.current_shape:
            return

        new_x = self.x_spinbox.value()
        new_y = self.y_spinbox.value()

        # 计算当前边界框
        from PyQt5.QtCore import QRectF, QPointF
        rect = self._get_shape_rect(self.current_shape)
        if not rect:
            return

        # 计算偏移量
        dx = new_x - rect.left()
        dy = new_y - rect.top()

        # 移动所有点
        new_points = [QPointF(p.x() + dx, p.y() + dy) for p in self.current_shape.points]
        self.current_shape.points = new_points

        # 更新中心点显示
        self._update_center_display()
        self._update_canvas()

    def _on_size_changed(self):
        """尺寸改变时实时更新shape"""
        if self._updating_from_shape or not self.current_shape:
            return

        new_w = self.w_spinbox.value()
        new_h = self.h_spinbox.value()

        # 计算当前边界框
        from PyQt5.QtCore import QRectF, QPointF
        rect = self._get_shape_rect(self.current_shape)
        if not rect or rect.width() == 0 or rect.height() == 0:
            return

        # 计算缩放比例
        scale_x = new_w / rect.width()
        scale_y = new_h / rect.height()

        # 缩放所有点（相对于左上角）
        new_points = []
        for point in self.current_shape.points:
            scaled_x = rect.left() + (point.x() - rect.left()) * scale_x
            scaled_y = rect.top() + (point.y() - rect.top()) * scale_y
            new_points.append(QPointF(scaled_x, scaled_y))

        self.current_shape.points = new_points

        # 更新中心点显示
        self._update_center_display()
        self._update_canvas()

    def _on_center_changed(self):
        """中心点改变时实时更新shape"""
        if self._updating_from_shape or not self.current_shape:
            return

        new_cx = self.cx_spinbox.value()
        new_cy = self.cy_spinbox.value()

        # 计算当前边界框
        from PyQt5.QtCore import QRectF, QPointF
        rect = self._get_shape_rect(self.current_shape)
        if not rect:
            return

        # 计算偏移量
        dx = new_cx - rect.center().x()
        dy = new_cy - rect.center().y()

        # 移动所有点
        new_points = [QPointF(p.x() + dx, p.y() + dy) for p in self.current_shape.points]
        self.current_shape.points = new_points

        # 更新位置显示
        self._update_position_display()
        self._update_canvas()

    def _on_rotation_changed(self):
        """旋转角度改变时实时更新shape"""
        if self._updating_from_shape or not self.current_shape:
            return

        if self.current_shape.shape_type not in ['rotation', 'rotation3']:
            return

        new_rotation = self.rotation_spinbox.value()
        import math
        angle_radians = math.radians(new_rotation)

        # 使用canvas.set_shape_rotation来实时更新画布（与CTRL+E对话框相同的方式）
        if self.main_window and hasattr(self.main_window, 'canvas'):
            self.main_window.canvas.set_shape_rotation(self.current_shape, angle_radians)
            self.main_window.set_dirty()

    def _on_create_rectangle(self):
        """新建矩形"""
        # 获取标签
        label = self.label_combo.currentText().strip()
        if not label:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("警告"),
                self.tr("请输入标签名称！")
            )
            return

        # 获取坐标和尺寸
        x = self.x_spinbox.value()
        y = self.y_spinbox.value()
        w = self.w_spinbox.value()
        h = self.h_spinbox.value()

        # 检查尺寸
        if w <= 0 or h <= 0:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("警告"),
                self.tr("宽度和高度必须大于0！")
            )
            return

        # 创建矩形的四个点 (左上, 右上, 右下, 左下)
        from PyQt5.QtCore import QPointF
        from views.labeling.shape import Shape

        shape = Shape(shape_type="rectangle")
        shape.label = label
        shape.add_point(QPointF(x, y))           # 左上
        shape.add_point(QPointF(x + w, y))       # 右上
        shape.add_point(QPointF(x + w, y + h))   # 右下
        shape.add_point(QPointF(x, y + h))       # 左下
        shape.close()

        # 添加到画布和标签列表
        if self.main_window:
            # 添加到画布
            if hasattr(self.main_window, 'canvas'):
                self.main_window.canvas.shapes.append(shape)
                self.main_window.canvas.store_shapes()

            # 添加到标签列表（这会触发所有必要的更新）
            if hasattr(self.main_window, 'add_label'):
                self.main_window.add_label(shape)

            # 更新画布显示
            if hasattr(self.main_window, 'canvas'):
                self.main_window.canvas.update()

            # 选中新创建的矩形
            if hasattr(self.main_window, 'canvas'):
                self.main_window.canvas.select_shapes([shape])

            # 刷新对象管理器列表
            if hasattr(self.main_window, 'label_list'):
                self.update_items([item for item in self.main_window.label_list])

    def _get_shape_rect(self, shape):
        """获取shape的边界框"""
        if not shape or not shape.points:
            return None

        from PyQt5.QtCore import QRectF

        # 获取所有点的x和y坐标
        x_coords = [p.x() for p in shape.points]
        y_coords = [p.y() for p in shape.points]

        if not x_coords or not y_coords:
            return None

        # 计算边界框
        min_x = min(x_coords)
        max_x = max(x_coords)
        min_y = min(y_coords)
        max_y = max(y_coords)

        # 创建矩形：左上角坐标 + 宽高
        rect = QRectF(min_x, min_y, max_x - min_x, max_y - min_y)
        return rect

    def _update_center_display(self):
        """更新中心点显示"""
        x = self.x_spinbox.value()
        y = self.y_spinbox.value()
        w = self.w_spinbox.value()
        h = self.h_spinbox.value()

        self.cx_spinbox.blockSignals(True)
        self.cy_spinbox.blockSignals(True)
        self.cx_spinbox.setValue(x + w / 2)
        self.cy_spinbox.setValue(y + h / 2)
        self.cx_spinbox.blockSignals(False)
        self.cy_spinbox.blockSignals(False)

    def _update_position_display(self):
        """更新位置显示"""
        rect = self._get_shape_rect(self.current_shape)
        if not rect:
            return

        self.x_spinbox.blockSignals(True)
        self.y_spinbox.blockSignals(True)
        self.x_spinbox.setValue(rect.left())
        self.y_spinbox.setValue(rect.top())
        self.x_spinbox.blockSignals(False)
        self.y_spinbox.blockSignals(False)

    def _update_canvas(self):
        """更新画布"""
        if self.main_window and hasattr(self.main_window, 'canvas'):
            self.main_window.canvas.update()
            self.main_window.set_dirty()

    def update_properties_from_canvas(self):
        """从画布更新属性面板（当形状在画布上移动或旋转时调用）"""
        if not self.current_shape:
            return

        # 标记正在从shape更新UI，避免触发实时更新
        self._updating_from_shape = True

        # 计算边界框
        if self.current_shape.points:
            rect = self._get_shape_rect(self.current_shape)
            if rect:
                # 更新位置和尺寸
                self.x_spinbox.setValue(rect.left())
                self.y_spinbox.setValue(rect.top())
                self.w_spinbox.setValue(rect.width())
                self.h_spinbox.setValue(rect.height())
                self.cx_spinbox.setValue(rect.center().x())
                self.cy_spinbox.setValue(rect.center().y())

        # 更新旋转角度（仅旋转矩形）
        if self.current_shape.shape_type in ['rotation', 'rotation3']:
            if hasattr(self.current_shape, 'direction') and self.current_shape.direction is not None:
                import math
                angle_degrees = math.degrees(self.current_shape.direction) % 360
                self.rotation_spinbox.setValue(angle_degrees)

        self._updating_from_shape = False

    def lock_selected_labels(self):
        """锁定选中的标签"""
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return

        # 锁定所有选中的shape
        for item in selected_items:
            shape = item.data(QtCore.Qt.UserRole)
            if shape:
                # 设置手动锁定标记
                shape.is_manually_locked = True
                # 清除会话解锁标记（如果有）
                if hasattr(shape, 'is_session_unlocked'):
                    shape.is_session_unlocked = False

        # 更新画布和列表显示
        if self.main_window and hasattr(self.main_window, 'canvas'):
            self.main_window.canvas.update()
            self.main_window.set_dirty()

        # 刷新列表以显示锁定状态的信号灯
        self.list_widget.viewport().update()

    def unlock_selected_labels(self):
        """解锁选中的标签"""
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return

        # 解锁所有选中的shape
        for item in selected_items:
            shape = item.data(QtCore.Qt.UserRole)
            if shape:
                # 清除手动锁定标记
                shape.is_manually_locked = False
                # 设置会话解锁标记（用于显示蓝色信号灯）
                shape.is_session_unlocked = True

        # 更新画布和列表显示
        if self.main_window and hasattr(self.main_window, 'canvas'):
            self.main_window.canvas.update()
            self.main_window.set_dirty()

        # 刷新列表以显示解锁状态的信号灯
        self.list_widget.viewport().update()
