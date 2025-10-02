# -*- encoding: utf-8 -*-

from PyQt5 import QtWidgets, QtCore, QtGui

from .. import utils
from .label_category_widget import LabelCategoryWidget
from .object_list_widget import ObjectListWidget


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
        self.resize(520, 420)
        # 设置窗口标志：移除帮助按钮，添加最小化按钮
        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.WindowMinimizeButtonHint |
            QtCore.Qt.WindowMaximizeButtonHint |
            QtCore.Qt.WindowCloseButtonHint
        )

        # Left side: Category controls
        self.category_list = LabelCategoryWidget()
        categories = sorted(list(set(item.shape().label for item in items)))
        for category in categories:
            self.category_list.add_category(category)
        
        self.btn_move_category_top = QtWidgets.QPushButton(self.tr("置顶分类"))
        self.btn_move_category_bottom = QtWidgets.QPushButton(self.tr("置底分类"))
        self.apply_all_checkbox = QtWidgets.QCheckBox(self.tr("应用到全部"))

        # Right side: Full object list with drag-drop
        self.list_widget = ObjectListWidget()
        self.list_widget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.list_widget.setDefaultDropAction(QtCore.Qt.MoveAction)
        self.list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.list_widget.installEventFilter(self)

        for item in items:
            new_item = QtWidgets.QListWidgetItem(item.text())
            new_item.setBackground(item.background())
            new_item.setData(QtCore.Qt.UserRole, item.shape())
            new_item.setFlags(item.flags() & ~QtCore.Qt.ItemIsUserCheckable) # No checkbox
            self.list_widget.addItem(new_item)

        # Layouts
        v_layout_left = QtWidgets.QVBoxLayout()
        v_layout_left.addWidget(QtWidgets.QLabel(self.tr("分类整体排序")))
        v_layout_left.addWidget(self.category_list)
        
        h_button_layout_left = QtWidgets.QHBoxLayout()
        h_button_layout_left.addWidget(self.btn_move_category_top)
        h_button_layout_left.addWidget(self.btn_move_category_bottom)
        v_layout_left.addLayout(h_button_layout_left)
        v_layout_left.addWidget(self.apply_all_checkbox, 0, QtCore.Qt.AlignRight)
        v_layout_left.addStretch()

        v_layout_right = QtWidgets.QVBoxLayout()
        v_layout_right.addWidget(QtWidgets.QLabel(self.tr("对象列表 (可拖拽排序)")))
        v_layout_right.addWidget(self.list_widget)

        self.btn_move_up = QtWidgets.QPushButton(self.tr("上移"))
        self.btn_move_down = QtWidgets.QPushButton(self.tr("下移"))
        self.btn_move_top = QtWidgets.QPushButton(self.tr("置顶"))
        self.btn_move_bottom = QtWidgets.QPushButton(self.tr("置底"))

        h_button_layout_right = QtWidgets.QHBoxLayout()
        h_button_layout_right.addWidget(self.btn_move_up)
        h_button_layout_right.addWidget(self.btn_move_down)
        h_button_layout_right.addStretch()
        h_button_layout_right.addWidget(self.btn_move_top)
        h_button_layout_right.addWidget(self.btn_move_bottom)
        v_layout_right.addLayout(h_button_layout_right)

        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.addLayout(v_layout_left, 1)
        main_layout.addLayout(v_layout_right, 2)

        # Connections
        self.list_widget.order_changed.connect(self._emit_order_changed)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list_widget.itemSelectionChanged.connect(self._on_internal_selection_changed)
        self.list_widget.customContextMenuRequested.connect(self._pop_list_menu)
        
        self.btn_move_category_top.clicked.connect(lambda: self.reorder_by_category(move_to_top=True))
        self.btn_move_category_bottom.clicked.connect(lambda: self.reorder_by_category(move_to_top=False))

        self.btn_move_up.clicked.connect(lambda: self.move_items(-1))
        self.btn_move_down.clicked.connect(lambda: self.move_items(1))
        self.btn_move_top.clicked.connect(self.move_to_top)
        self.btn_move_bottom.clicked.connect(self.move_to_bottom)

        self.update_button_states()

        # Add shortcut for closing the dialog
        self.close_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+T"), self)
        self.close_shortcut.activated.connect(self.close)

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

    def update_button_states(self):
        """Update the enabled state of the buttons based on selection."""
        has_selection = bool(self.list_widget.selectedItems())
        count = self.list_widget.count()
        
        self.btn_move_up.setEnabled(has_selection)
        self.btn_move_down.setEnabled(has_selection)
        self.btn_move_top.setEnabled(has_selection)
        self.btn_move_bottom.setEnabled(has_selection)

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
