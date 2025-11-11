# -*- encoding: utf-8 -*-

import html

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, pyqtSignal

from .escapable_qlist_widget import EscapableQListWidget
from .. import utils


class SelectionIndicatorDelegate(QtWidgets.QStyledItemDelegate):
    """自定义委托，用于在选中的标签上绘制红点标识"""

    def paint(self, painter, option, index):
        # 先调用父类绘制默认内容
        super().paint(painter, option, index)

        # 如果item被选中，在右侧绘制红点
        if option.state & QtWidgets.QStyle.State_Selected:
            painter.save()

            # 设置抗锯齿
            painter.setRenderHint(QtGui.QPainter.Antialiasing)

            # 绘制红色圆点
            painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 0, 0)))  # 红色
            painter.setPen(Qt.NoPen)

            # 计算红点位置（右侧居中）
            dot_radius = 4
            dot_x = option.rect.right() - dot_radius * 2 - 5
            dot_y = option.rect.center().y()

            painter.drawEllipse(QtCore.QPointF(dot_x, dot_y), dot_radius, dot_radius)

            painter.restore()


class UniqueLabelQListWidget(EscapableQListWidget):
    # A signal that is emitted when the visibility of a label changes.
    label_visibility_changed = pyqtSignal(str, bool)  # label, visible
    # 新增：选中项变化信号
    selection_changed = pyqtSignal()
    labels_ordered = pyqtSignal(list)
    # 新增：右键菜单信号
    delete_current_page_shapes = pyqtSignal(str)  # 删除本页所有该标签的矩形
    delete_all_label_shapes = pyqtSignal(str)  # 删除所有图片中该标签的矩形和标签
    change_label_color = pyqtSignal(str)  # 修改标签颜色
    # 批量操作信号
    batch_delete_current_page_shapes = pyqtSignal(list)  # 批量删除本页所有选中标签的矩形
    batch_delete_all_label_shapes = pyqtSignal(list)  # 批量删除所有图片中选中标签的矩形和标签
    batch_change_label_color = pyqtSignal(list)  # 批量修改标签颜色

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        # Set the selection mode to ExtendedSelection (Ctrl+Click for multi-select, Click for single select)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QtWidgets.QAbstractItemView.NoDragDrop)

        # Connect the itemChanged signal to the on_item_changed slot.
        self.itemChanged.connect(self.on_item_changed)
        # 连接选中变化信号
        self.itemSelectionChanged.connect(self.on_selection_changed)

        # 设置右键菜单
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        # 设置自定义委托以绘制选中标识
        self.setItemDelegate(SelectionIndicatorDelegate(self))

    def mousePressEvent(self, event):
        # 只有在未按下Ctrl/Shift时，点击空白才清除选择，保证Ctrl/Shift多选原生行为
        if not self.indexAt(event.pos()).isValid():
            modifiers = QtWidgets.QApplication.keyboardModifiers()
            if not (modifiers & Qt.ControlModifier or modifiers & Qt.ShiftModifier):
                self.clearSelection()

        # 调用父类方法处理点击事件
        super().mousePressEvent(event)

        # 确保选中状态正确同步
        self.on_selection_changed()

    def focusOutEvent(self, event):
        """失去焦点时清除选中状态"""
        self.clearSelection()
        super().focusOutEvent(event)

    def find_items_by_label(self, label):
        """Find all items with the given label."""
        items = []
        for row in range(self.count()):
            item = self.item(row)
            if item.data(Qt.UserRole) == label:
                items.append(item)
        return items

    def create_item_from_label(self, label):
        """Create a new QListWidgetItem for the given label."""
        item = QtWidgets.QListWidgetItem()
        item.setData(Qt.UserRole, label)
        # Use a checkbox to control the visibility of the label.
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)  # Initially visible
        return item

    def set_item_label(self, item, label, color=None, opacity=128):
        """设置标签项的文本和颜色（仅影响显示，不影响选中/勾选状态）"""
        item.setText(label)
        if color is not None:
            background_color = QtGui.QColor(*color, opacity)
            item.setBackground(background_color)

    def update_item_color(self, label, color, opacity=255):
        """更新所有同名标签项的颜色（不影响选中/勾选状态）"""
        items = self.find_items_by_label(label)
        for item in items:
            background_color = QtGui.QColor(*color, opacity)
            item.setBackground(background_color)

    def remove_items_by_label(self, label):
        """Remove all items with the given label."""
        items = self.find_items_by_label(label)
        for item in items:
            row = self.row(item)
            self.takeItem(row)

    def on_item_changed(self, item):
        """checkbox勾选变化时，仅发可见性信号，不影响选中高亮"""
        label = item.data(Qt.UserRole)
        is_visible = item.checkState() == Qt.Checked
        self.label_visibility_changed.emit(label, is_visible)

    def get_visible_labels(self):
        """Get a list of all visible labels."""
        visible_labels = []
        for row in range(self.count()):
            item = self.item(row)
            if item.checkState() == Qt.Checked:
                visible_labels.append(item.data(Qt.UserRole))
        return visible_labels

    def get_hidden_labels(self):
        """Get a list of all hidden labels."""
        hidden_labels = []
        for row in range(self.count()):
            item = self.item(row)
            if item.checkState() == Qt.Unchecked:
                hidden_labels.append(item.data(Qt.UserRole))
        return hidden_labels

    def select_all_labels(self):
        """Select all items in the list."""
        self.selectAll()

    def deselect_all_labels(self):
        """Deselect all items in the list."""
        self.clearSelection()

    def invert_selection(self):
        """Invert the selection of all items in the list."""
        for row in range(self.count()):
            item = self.item(row)
            item.setSelected(not item.isSelected())

    def show_all_labels(self):
        """Set all labels to be visible."""
        for row in range(self.count()):
            item = self.item(row)
            item.setCheckState(Qt.Checked)

    def hide_all_labels(self):
        """Set all labels to be hidden."""
        for row in range(self.count()):
            item = self.item(row)
            item.setCheckState(Qt.Unchecked)

    def invert_visibility(self):
        """Invert the visibility of all labels."""
        for row in range(self.count()):
            item = self.item(row)
            item.setCheckState(
                Qt.Checked
                if item.checkState() == Qt.Unchecked
                else Qt.Unchecked
            )

    def on_selection_changed(self):
        # 选中项变化时发射信号
        self.selection_changed.emit()

    def show_context_menu(self, position):
        """显示右键菜单（支持多选批量操作）"""
        # 获取点击位置的item
        item = self.itemAt(position)
        if not item:
            return

        # 获取当前选中的items
        selected_items = self.selectedItems()

        # 如果右键点击的item不在已选中的items中，则清除其他选中并只选中这个item
        # 如果右键点击的item已经在选中列表中（多选状态），则保持当前选中状态
        if item not in selected_items:
            # 右键点击的item未被选中，清除其他选中并只选中这个item
            self.clearSelection()
            item.setSelected(True)
            selected_items = [item]

        selected_labels = [item.data(Qt.UserRole) for item in selected_items]
        is_multi_select = len(selected_labels) > 1

        # 创建菜单
        menu = QtWidgets.QMenu(self)

        # 添加菜单项（根据是否多选调整文本）
        if is_multi_select:
            delete_page_action = menu.addAction(
                utils.new_icon('delete'),
                self.tr(f"删除本页所有选中标签 ({len(selected_labels)}个)")
            )
            delete_all_action = menu.addAction(
                utils.new_icon('cancel'),
                self.tr(f"删除选中标签(所有图片) ({len(selected_labels)}个)")
            )
            menu.addSeparator()
            change_color_action = menu.addAction(
                utils.new_icon('color'),
                self.tr(f"批量修改颜色 ({len(selected_labels)}个)")
            )
        else:
            label = selected_labels[0]
            delete_page_action = menu.addAction(
                utils.new_icon('delete'),
                self.tr("删除本页所有该标签")
            )
            delete_all_action = menu.addAction(
                utils.new_icon('cancel'),
                self.tr("删除该标签(所有图片)")
            )
            menu.addSeparator()
            change_color_action = menu.addAction(
                utils.new_icon('color'),
                self.tr("修改颜色")
            )

        # 显示菜单并获取选择的动作
        action = menu.exec_(self.mapToGlobal(position))

        # 处理选择的动作
        if action == delete_page_action:
            if is_multi_select:
                # 批量操作：发送批量信号
                self.batch_delete_current_page_shapes.emit(selected_labels)
            else:
                # 单个操作
                self.delete_current_page_shapes.emit(selected_labels[0])
        elif action == delete_all_action:
            if is_multi_select:
                # 批量操作：发送批量信号
                self.batch_delete_all_label_shapes.emit(selected_labels)
            else:
                # 单个操作
                self.delete_all_label_shapes.emit(selected_labels[0])
        elif action == change_color_action:
            if is_multi_select:
                # 批量操作：发送批量信号
                self.batch_change_label_color.emit(selected_labels)
            else:
                # 单个操作
                self.change_label_color.emit(selected_labels[0])

    def get_ordered_labels(self):
        labels = []
        for i in range(self.count()):
            item = self.item(i)
            labels.append(item.data(Qt.UserRole))
        return labels

    def update_label_order(self):
        ordered_labels = self.get_ordered_labels()
        self.labels_ordered.emit(ordered_labels)
