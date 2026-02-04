import math
from dataclasses import dataclass
from typing import Dict, List, Optional

import sip
from PyQt5 import QtCore, QtGui, QtWidgets

from anylabeling.services.tag_sorting import (
    LineGuide,
    SortOptions,
    available_spatial_modes,
    sort_shapes,
)

SPATIAL_MODE_LABELS = {
    "LEFT_TO_RIGHT": "横向（从左到右）",
    "RIGHT_TO_LEFT": "横向（从右到左）",
    "X_THEN_Y": "日漫横向优先（先右左，后上下）",
    "Y_THEN_X": "日漫纵向优先（先右左分栏，栏内上下）",
    "LINE_GUIDES": "使用自定义排序线",
}


LINE_COLOR = QtGui.QColor(46, 204, 113)
LINE_HIGHLIGHT_COLOR = QtGui.QColor(241, 196, 15)
RECT_COLOR = QtGui.QColor(52, 152, 219)
RECT_FILL_COLOR = QtGui.QColor(52, 152, 219, 60)
HANDLE_FILL = QtGui.QColor(236, 240, 241)
HANDLE_BORDER = QtGui.QColor(52, 73, 94)
HANDLE_SIZE = 18.0
LABEL_COLOR = QtGui.QColor(236, 240, 241)
ARROW_COLOR = QtGui.QColor(46, 204, 113)
MIN_RECT_SIZE = 60.0
LINE_WIDTH = 12.0
HIGHLIGHT_LINE_WIDTH = 14.0


class GuideRectItem(QtWidgets.QGraphicsRectItem):
    def __init__(self, widget_parent) -> None:
        super().__init__()
        self.widget_parent = widget_parent
        self.record: Optional["GuideRecord"] = None  # 使用字符串类型注解
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, False)

    def set_record(self, record: "GuideRecord") -> None:  # 使用字符串类型注解
        self.record = record

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        if event.button() == QtCore.Qt.LeftButton and self.record:
            self.widget_parent.select_record(self.record)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        if event.buttons() & QtCore.Qt.LeftButton and self.record:
            delta = event.scenePos() - event.lastScenePos()
            self.widget_parent.move_line(self.record, delta)
            event.accept()
        else:
            super().mouseMoveEvent(event)


class GuideLineItem(QtWidgets.QGraphicsLineItem):
    def __init__(self, widget: "TagSortGuideWidget") -> None:
        super().__init__()
        self.widget = widget
        self.record: Optional["GuideRecord"] = None
        pen = QtGui.QPen(LINE_COLOR, LINE_WIDTH, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
        self.setPen(pen)
        self.setZValue(4)
        self.setCursor(QtGui.QCursor(QtCore.Qt.SizeAllCursor))
        self.setAcceptedMouseButtons(QtCore.Qt.LeftButton)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, False)

    def set_record(self, record: "GuideRecord") -> None:
        self.record = record

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        if self.widget.is_draw_mode:
            event.ignore()
            return
        if self.record:
            self.widget.select_record(self.record)
        event.accept()

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        if self.widget.is_draw_mode:
            event.ignore()
            return
        if self.record and event.buttons() & QtCore.Qt.LeftButton:
            delta = event.scenePos() - event.lastScenePos()
            self.widget.move_line(self.record, delta)
            event.accept()
        else:
            event.ignore()

    def mouseDoubleClickEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        if self.widget.is_draw_mode:
            event.ignore()
            return
        if self.record:
            self.widget.flip_direction(self.record)
            event.accept()
        else:
            event.ignore()


 


class EndpointHandle(QtWidgets.QGraphicsEllipseItem):
    def __init__(self, widget: "TagSortGuideWidget", role: str) -> None:
        super().__init__(-HANDLE_SIZE / 2.0, -HANDLE_SIZE / 2.0, HANDLE_SIZE, HANDLE_SIZE)
        self.widget = widget
        self.role = role
        self.record: Optional["GuideRecord"] = None
        self.setBrush(QtGui.QBrush(HANDLE_FILL))
        self.setPen(QtGui.QPen(HANDLE_BORDER, 2))
        self.setZValue(6)
        self.setCursor(QtGui.QCursor(QtCore.Qt.CrossCursor))
        self.setAcceptedMouseButtons(QtCore.Qt.LeftButton)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, False)

    def set_record(self, record: "GuideRecord") -> None:
        self.record = record

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        if self.widget.is_draw_mode:
            event.ignore()
            return
        if self.record:
            self.widget.select_record(self.record)
        event.accept()

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        if self.widget.is_draw_mode:
            event.ignore()
            return
        if self.record and event.buttons() & QtCore.Qt.LeftButton:
            self.widget.move_endpoint(self.record, self.role, event.scenePos())
            event.accept()
        else:
            event.ignore()


class EditablePreviewRect(QtWidgets.QGraphicsRectItem):
    def __init__(self, widget: "TagSortGuideWidget", shape_data: dict, order: int, center: QtCore.QPointF) -> None:
        width, height = 60, 45
        super().__init__(center.x() - width/2, center.y() - height/2, width, height)
        self.widget = widget
        self.shape_data = shape_data
        self.original_order = order
        self.custom_order: Optional[int] = None
        self.center_pos = center

        # 设置样式
        self.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 240)))  # 白色背景
        self.setPen(QtGui.QPen(QtGui.QColor(0, 100, 200), 3))  # 蓝色边框
        self.setZValue(9)

        # 创建数字标签 - 不作为子项，独立定位
        self.label = QtWidgets.QGraphicsSimpleTextItem(str(order))
        font = QtGui.QFont()
        font.setPointSize(24)
        font.setBold(True)
        font.setFamily("Arial")
        self.label.setFont(font)
        self.label.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0)))  # 黑色文字

        # 居中对齐数字 - 使用绝对坐标
        text_rect = self.label.boundingRect()
        self.label.setPos(
            center.x() - text_rect.width() / 2,
            center.y() - text_rect.height() / 2
        )
        self.label.setZValue(10)  # 确保在矩形之上

    def mouseDoubleClickEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        if self.widget.is_draw_mode:
            event.ignore()
            return

        # 获取当前序号
        current_text = self.label.text()
        dialog = QtWidgets.QInputDialog(self.widget)
        dialog.setWindowTitle("修改预览序号")
        dialog.setLabelText("请输入新的序号:")
        dialog.setTextValue(current_text)
        dialog.setIntRange(1, 999)
        dialog.setInputMode(QtWidgets.QInputDialog.IntInput)

        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            new_number = dialog.intValue()
            if new_number > 0:
                self.widget._update_preview_order(self, new_number)

        event.accept()

    def update_number(self, new_number: int) -> None:
        """更新显示的数字"""
        self.custom_order = new_number
        self.label.setText(str(new_number))

        # 重新计算数字位置以保持居中
        text_rect = self.label.boundingRect()
        self.label.setPos(
            self.center_pos.x() - text_rect.width() / 2,
            self.center_pos.y() - text_rect.height() / 2
        )


class EditablePreviewLabel(QtWidgets.QGraphicsSimpleTextItem):
    def __init__(self, widget: "TagSortGuideWidget", shape_data: dict, order: int) -> None:
        super().__init__(str(order))
        self.widget = widget
        self.shape_data = shape_data
        self.original_order = order
        self.custom_order: Optional[int] = None

        font = QtGui.QFont()
        font.setPointSize(24)
        font.setBold(True)
        font.setFamily("Arial")
        self.setFont(font)
        self.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0)))  # 黑色文字

    def mouseDoubleClickEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        if self.widget.is_draw_mode:
            event.ignore()
            return

        # 获取当前序号
        current_text = self.text()
        dialog = QtWidgets.QInputDialog(self.widget)
        dialog.setWindowTitle("修改预览序号")
        dialog.setLabelText("请输入新的序号:")
        dialog.setTextValue(current_text)
        dialog.setIntRange(1, 999)
        dialog.setInputMode(QtWidgets.QInputDialog.IntInput)

        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            new_number = dialog.intValue()
            if new_number > 0:
                self.custom_order = new_number
                self.setText(str(new_number))
                # 通知widget序号已修改
                self.widget._on_preview_order_changed()

        event.accept()


class EditableLabelItem(QtWidgets.QGraphicsSimpleTextItem):
    def __init__(self, widget: "TagSortGuideWidget") -> None:
        super().__init__()
        self.widget = widget
        self.record: Optional["GuideRecord"] = None
        self.original_number: int = 1

    def set_record(self, record: "GuideRecord") -> None:
        self.record = record

    def mouseDoubleClickEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        if self.widget.is_draw_mode or not self.record:
            event.ignore()
            return

        # 获取当前序号
        current_text = self.text()
        dialog = QtWidgets.QInputDialog(self.widget)
        dialog.setWindowTitle("修改序号")
        dialog.setLabelText("请输入新的序号:")
        dialog.setTextValue(current_text)
        dialog.setIntRange(1, 999)
        dialog.setInputMode(QtWidgets.QInputDialog.IntInput)

        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            new_number = dialog.intValue()
            if new_number > 0:
                self.widget.change_guide_number(self.record, new_number)

        event.accept()


@dataclass
class GuideRecord:
    line_item: GuideLineItem
    arrow_item: QtWidgets.QGraphicsPolygonItem
    label_item: EditableLabelItem
    label_background: QtWidgets.QGraphicsRectItem  # 添加标签背景
    endpoint_handles: Dict[str, EndpointHandle]
    rect_item: GuideRectItem  # 矩形控制范围
    rect_handles: Dict[str, EndpointHandle]  # 矩形控制点
    start: QtCore.QPointF
    end: QtCore.QPointF
    rect: QtCore.QRectF  # 矩形控制范围
    custom_number: Optional[int] = None  # 自定义序号
    control_point: Optional[QtCore.QPointF] = None  # 弯曲控制点
    is_curved: bool = False  # 是否为弯曲线条


class TagSortGuideWidget(QtWidgets.QWidget):
    guides_changed = QtCore.pyqtSignal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)  # 允许接收键盘焦点
        self.scene = QtWidgets.QGraphicsScene(self)
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.view.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)
        self.view.setDragMode(QtWidgets.QGraphicsView.NoDrag)
        self.view.viewport().installEventFilter(self)

        self.draw_mode_button = QtWidgets.QToolButton()
        self.draw_mode_button.setText(self.tr("绘图"))
        self.draw_mode_button.setCheckable(True)
        self.draw_mode_button.setToolTip(self.tr("绘制排序线模式：按住并拖动即可画线"))
        self.draw_mode_button.toggled.connect(self.set_draw_mode)

        self.select_mode_button = QtWidgets.QToolButton()
        self.select_mode_button.setText(self.tr("选择并移动"))
        self.select_mode_button.setCheckable(True)
        self.select_mode_button.setChecked(True)  # 默认选择模式
        self.select_mode_button.setToolTip(self.tr("选择移动模式：选择并移动线条"))
        self.select_mode_button.toggled.connect(self.set_select_mode)

        # 添加线条粗细设置
        self.line_width_label = QtWidgets.QLabel(self.tr("线条粗细:"))
        self.line_width_spinbox = QtWidgets.QSpinBox()
        self.line_width_spinbox.setRange(4, 30)
        self.line_width_spinbox.setValue(int(LINE_WIDTH))
        self.line_width_spinbox.setSuffix("px")
        self.line_width_spinbox.valueChanged.connect(self.update_line_width)

        self.remove_button = QtWidgets.QPushButton(self.tr("删除选中"))
        self.clear_button = QtWidgets.QPushButton(self.tr("清空全部"))

        self._order_list_syncing = False

        button_row = QtWidgets.QHBoxLayout()
        button_row.addWidget(self.draw_mode_button)
        button_row.addWidget(self.select_mode_button)
        button_row.addSpacing(12)
        button_row.addWidget(self.line_width_label)
        button_row.addWidget(self.line_width_spinbox)
        button_row.addSpacing(12)
        for button in (self.remove_button, self.clear_button):
            button_row.addWidget(button)
        button_row.addStretch(1)

        content_layout = QtWidgets.QHBoxLayout()
        content_layout.setSpacing(12)
        content_layout.addWidget(self.view, 1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(content_layout, 1)
        layout.addLayout(button_row)

        self.background_item: Optional[QtWidgets.QGraphicsPixmapItem] = None
        self.shape_items: List[QtWidgets.QGraphicsRectItem] = []
        self.guides: List[GuideRecord] = []
        self.selected_record: Optional[GuideRecord] = None
        self.image_width = 0.0
        self.image_height = 0.0
        self.is_draw_mode = False
        self._draw_start: Optional[QtCore.QPointF] = None
        self._preview_line: Optional[QtWidgets.QGraphicsLineItem] = None
        self._preview_arrow: Optional[QtWidgets.QGraphicsPolygonItem] = None
        self._preview_rect: Optional[QtWidgets.QGraphicsRectItem] = None
        self._preview_label: Optional[QtWidgets.QGraphicsSimpleTextItem] = None
        self._preview_label_background: Optional[QtWidgets.QGraphicsRectItem] = None
        self.current_line_width = LINE_WIDTH  # 当前线条宽度
        self.shapes_data: List[dict] = []
        self.overlay_items: List[QtWidgets.QGraphicsItem] = []
        self.preview_options: Optional[SortOptions] = None
        self.preview_labels: List[EditablePreviewRect] = []  # 存储可编辑的预览标签

        # 预设排序可视化相关
        self.spatial_preview_items: List[QtWidgets.QGraphicsItem] = []
        self.spatial_preview_enabled = True

        self.remove_button.clicked.connect(self.remove_selected)
        self.clear_button.clicked.connect(self.clear_guides)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """处理键盘快捷键"""
        # 先检查是否有输入框获得焦点，如果有，不处理翻页
        focused_widget = QtWidgets.QApplication.focusWidget()
        if isinstance(focused_widget, (QtWidgets.QLineEdit, QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit)):
            super().keyPressEvent(event)
            return

        # 如果按下A或D键且没有修饰键，转发给父窗口进行翻页
        if event.modifiers() == QtCore.Qt.NoModifier:
            if event.key() in (QtCore.Qt.Key_A, QtCore.Qt.Key_D, QtCore.Qt.Key_Left, QtCore.Qt.Key_Right):
                # 转发翻页事件到主窗口
                parent = self.parent()
                while parent and not hasattr(parent, 'open_next_image'):
                    parent = parent.parent()
                if parent:
                    QtWidgets.QApplication.sendEvent(parent, event)
                    event.accept()
                    return

        # 对于其他按键，调用父类的处理方法
        super().keyPressEvent(event)

    def update_line_width(self, width: int) -> None:
        """更新当前线条宽度"""
        self.current_line_width = float(width)
        # 更新所有现有线条的宽度
        for record in self.guides:
            pen = record.line_item.pen()
            pen.setWidthF(self.current_line_width)
            record.line_item.setPen(pen)
        # 如果有选中的线条，也要更新高亮状态的宽度
        if self.selected_record:
            self._set_highlight(self.selected_record, True)

    # ------------------------------------------------------------------
    # Draw mode helpers
    # ------------------------------------------------------------------
    def set_draw_mode(self, enabled: bool) -> None:
        if enabled:
            # 如果启用绘制模式，关闭选择模式
            self.select_mode_button.blockSignals(True)
            self.select_mode_button.setChecked(False)
            self.select_mode_button.blockSignals(False)

        self.is_draw_mode = enabled
        if enabled:
            self.view.viewport().setCursor(QtCore.Qt.CrossCursor)
            self.select_record(None)  # 取消当前选择
        else:
            self.view.viewport().unsetCursor()
            self._clear_preview()
            # 如果没有启用绘制模式且没有启用选择模式，默认启用选择模式
            if not self.select_mode_button.isChecked():
                self.select_mode_button.blockSignals(True)
                self.select_mode_button.setChecked(True)
                self.select_mode_button.blockSignals(False)

    def set_select_mode(self, enabled: bool) -> None:
        if enabled:
            # 如果启用选择模式，关闭绘制模式
            self.draw_mode_button.blockSignals(True)
            self.draw_mode_button.setChecked(False)
            self.draw_mode_button.blockSignals(False)

            self.is_draw_mode = False
            self.view.viewport().unsetCursor()
            self._clear_preview()
        else:
            # 如果没有启用选择模式且没有启用绘制模式，默认启用绘制模式
            if not self.draw_mode_button.isChecked():
                self.draw_mode_button.blockSignals(True)
                self.draw_mode_button.setChecked(True)
                self.draw_mode_button.blockSignals(False)
                self.set_draw_mode(True)

    def _clear_preview(self) -> None:
        """清除所有预览元素"""
        for item in [self._preview_line, self._preview_arrow, self._preview_rect,
                     self._preview_label, self._preview_label_background]:
            if item:
                self.scene.removeItem(item)
        self._preview_line = None
        self._preview_arrow = None
        self._preview_rect = None
        self._preview_label = None
        self._preview_label_background = None

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if obj is self.view.viewport() and self.is_draw_mode:
            if event.type() == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
                self._draw_start = self.view.mapToScene(event.pos())
                self._start_preview(self._draw_start)
                return True
            if event.type() == QtCore.QEvent.MouseMove and self._draw_start is not None:
                self._update_preview(self.view.mapToScene(event.pos()))
                return True
            if event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton:
                if self._draw_start is not None:
                    self._finish_preview(self.view.mapToScene(event.pos()))
                self._draw_start = None
                return True
        return super().eventFilter(obj, event)

    def _start_preview(self, pos: QtCore.QPointF) -> None:
        self._clear_preview()

        # 创建预览线条
        pen = QtGui.QPen(LINE_COLOR, self.current_line_width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
        self._preview_line = self.scene.addLine(pos.x(), pos.y(), pos.x(), pos.y(), pen)
        self._preview_line.setZValue(10)

        # 创建预览箭头
        self._preview_arrow = QtWidgets.QGraphicsPolygonItem()
        self._preview_arrow.setBrush(QtGui.QBrush(ARROW_COLOR))
        self._preview_arrow.setPen(QtGui.QPen(ARROW_COLOR))
        self._preview_arrow.setZValue(11)
        self.scene.addItem(self._preview_arrow)

        # 创建预览矩形区域
        self._preview_rect = QtWidgets.QGraphicsRectItem()
        self._preview_rect.setBrush(QtGui.QBrush(RECT_FILL_COLOR))
        self._preview_rect.setPen(QtGui.QPen(RECT_COLOR, 2, QtCore.Qt.DashLine))
        self._preview_rect.setZValue(9)
        self.scene.addItem(self._preview_rect)

        # 创建预览序号标签背景
        self._preview_label_background = QtWidgets.QGraphicsRectItem()
        self._preview_label_background.setBrush(QtGui.QBrush(QtGui.QColor(255, 0, 0, 200)))
        self._preview_label_background.setPen(QtGui.QPen(QtCore.Qt.transparent))
        self._preview_label_background.setZValue(11)
        self.scene.addItem(self._preview_label_background)

        # 创建预览序号标签
        self._preview_label = QtWidgets.QGraphicsSimpleTextItem()
        font = QtGui.QFont()
        font.setPointSize(32)
        font.setBold(True)
        self._preview_label.setFont(font)
        self._preview_label.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))
        self._preview_label.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        self._preview_label.setText(str(len(self.guides) + 1))
        self._preview_label.setZValue(12)
        self.scene.addItem(self._preview_label)

    def _update_preview(self, pos: QtCore.QPointF) -> None:
        if not self._preview_line or not self._draw_start:
            return

        start = self._draw_start
        end = pos

        # 根据拖拽直接计算矩形大小，不要固定尺寸
        preview_rect = QtCore.QRectF(start, end).normalized()

        # 确保最小尺寸
        if preview_rect.width() < MIN_RECT_SIZE:
            center_x = preview_rect.center().x()
            preview_rect.setLeft(center_x - MIN_RECT_SIZE / 2.0)
            preview_rect.setRight(center_x + MIN_RECT_SIZE / 2.0)
        if preview_rect.height() < MIN_RECT_SIZE:
            center_y = preview_rect.center().y()
            preview_rect.setTop(center_y - MIN_RECT_SIZE / 2.0)
            preview_rect.setBottom(center_y + MIN_RECT_SIZE / 2.0)

        # 确保矩形在边界内
        preview_rect = self._sanitize_rect(preview_rect)
        rect_center = preview_rect.center()

        # 箭头横跨整个矩形的长度（根据拖拽方向）
        dx = end.x() - start.x()
        dy = end.y() - start.y()

        arrow_margin = 10.0
        if abs(dx) > abs(dy):
            # 水平方向为主，箭头横跨矩形宽度
            preview_start = QtCore.QPointF(preview_rect.left() + arrow_margin, rect_center.y())
            preview_end = QtCore.QPointF(preview_rect.right() - arrow_margin, rect_center.y())
            if dx < 0:  # 向左拖拽，箭头向左
                preview_start, preview_end = preview_end, preview_start
        else:
            # 垂直方向为主，箭头横跨矩形高度
            preview_start = QtCore.QPointF(rect_center.x(), preview_rect.top() + arrow_margin)
            preview_end = QtCore.QPointF(rect_center.x(), preview_rect.bottom() - arrow_margin)
            if dy < 0:  # 向上拖拽，箭头向上
                preview_start, preview_end = preview_end, preview_start

        # 更新预览矩形
        self._preview_rect.setRect(preview_rect)

        # 更新预览线条
        self._preview_line.setLine(QtCore.QLineF(preview_start, preview_end))

        # 计算并更新预览箭头
        dx = preview_end.x() - preview_start.x()
        dy = preview_end.y() - preview_start.y()
        length = max(1.0, math.hypot(dx, dy))
        if length > 1e-6:
            angle = math.atan2(dy, dx)
            arrow_length = max(24.0, min(50.0, length * 0.25))
            tip = preview_end
            left = QtCore.QPointF(
                tip.x() - arrow_length * math.cos(angle) + arrow_length * 0.5 * math.sin(angle),
                tip.y() - arrow_length * math.sin(angle) - arrow_length * 0.5 * math.cos(angle),
            )
            right = QtCore.QPointF(
                tip.x() - arrow_length * math.cos(angle) - arrow_length * 0.5 * math.sin(angle),
                tip.y() - arrow_length * math.sin(angle) + arrow_length * 0.5 * math.cos(angle),
            )
            self._preview_arrow.setPolygon(QtGui.QPolygonF([tip, left, right]))

        # 更新预览标签位置和背景
        label_pos = QtCore.QPointF(preview_rect.left() + 18.0, preview_rect.top() + 18.0)
        self._preview_label.setPos(label_pos)

        # 计算并设置预览背景矩形的大小和位置
        if self._preview_label_background:
            text_rect = self._preview_label.boundingRect()
            padding = 8.0
            background_rect = QtCore.QRectF(
                -padding, -padding,
                text_rect.width() + 2 * padding,
                text_rect.height() + 2 * padding
            )
            self._preview_label_background.setRect(background_rect)
            self._preview_label_background.setPos(label_pos)

    def _finish_preview(self, pos: QtCore.QPointF) -> None:
        self._clear_preview()
        if self.image_width <= 0 or self.image_height <= 0:
            return
        start = self._draw_start or pos
        if (start - pos).manhattanLength() < 12.0:
            center_y = self.image_height / 2.0
            start = QtCore.QPointF(self.image_width * 0.2, center_y)
            pos = QtCore.QPointF(self.image_width * 0.8, center_y)
        self.add_guide(start, pos)
        # 不再自动关闭绘制模式，保持连续绘制
        # self.draw_mode_button.setChecked(False)

    # ------------------------------------------------------------------
    # Scene helpers
    # ------------------------------------------------------------------
    def load_pixmap(
        self,
        pixmap: Optional[QtGui.QPixmap],
        shapes: Optional[List[dict]] = None,
        guides: Optional[List[LineGuide]] = None,
    ) -> None:
        # 先清除所有预览元素，避免场景切换时的冲突
        self._clear_spatial_preview_items()
        self._clear_overlay_items()

        self.scene.clear()
        self.guides.clear()
        self._refresh_order_list()
        self._clear_shape_items()

        # 重新初始化列表，确保没有残留引用
        self.spatial_preview_items = []
        self.overlay_items = []
        self.shapes_data = shapes or []
        self.selected_record = None
        self.background_item = None
        self.image_width = 0.0
        self.image_height = 0.0
        self._draw_start = None
        self._clear_preview()

        if not pixmap or pixmap.isNull():
            return

        self.background_item = self.scene.addPixmap(pixmap)
        self.background_item.setZValue(0)
        self.image_width = float(pixmap.width())
        self.image_height = float(pixmap.height())
        self.scene.setSceneRect(0, 0, self.image_width, self.image_height)
        self._draw_shape_items()

        if guides:
            for guide in guides:
                start = QtCore.QPointF(guide.start[0] * self.image_width, guide.start[1] * self.image_height)
                end = QtCore.QPointF(guide.end[0] * self.image_width, guide.end[1] * self.image_height)
                # 恢复保存的矩形尺寸
                rect = QtCore.QRectF(
                    guide.rect[0] * self.image_width,
                    guide.rect[1] * self.image_height,
                    guide.rect[2] * self.image_width,
                    guide.rect[3] * self.image_height
                )
                self.add_guide(start, end, rect)
        self._update_indices()
        self._rebuild_spatial_preview()
        self._fit_view()

    def _clear_shape_items(self) -> None:
        for item in self.shape_items:
            if item is None or sip.isdeleted(item):
                continue
            self.scene.removeItem(item)
        self.shape_items.clear()

    def _draw_shape_items(self) -> None:
        self._clear_shape_items()
        if not self.shapes_data:
            return
        pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 70), 1, QtCore.Qt.DotLine)
        pen.setCosmetic(True)
        brush = QtGui.QBrush(QtCore.Qt.NoBrush)
        for shape in self.shapes_data:
            rect = self._shape_rect(shape)
            if not rect:
                continue
            item = QtWidgets.QGraphicsRectItem(rect)
            item.setPen(pen)
            item.setBrush(brush)
            item.setZValue(1)
            self.scene.addItem(item)
            self.shape_items.append(item)

    def _shape_points(self, shape: dict) -> List[QtCore.QPointF]:
        result: List[QtCore.QPointF] = []
        for point in shape.get("points") or []:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            try:
                x = float(point[0])
                y = float(point[1])
            except (TypeError, ValueError):
                continue
            result.append(QtCore.QPointF(x, y))
        return result

    def _shape_rect(self, shape: dict) -> Optional[QtCore.QRectF]:
        points = self._shape_points(shape)
        if not points:
            return None
        xs = [p.x() for p in points]
        ys = [p.y() for p in points]
        left, right = min(xs), max(xs)
        top, bottom = min(ys), max(ys)
        width = right - left
        height = bottom - top
        if width <= 0.0 or height <= 0.0:
            return None
        return QtCore.QRectF(left, top, width, height)

    def _shape_center(self, shape: dict) -> Optional[QtCore.QPointF]:
        points = self._shape_points(shape)
        if not points:
            return None
        xs = [p.x() for p in points]
        ys = [p.y() for p in points]
        return QtCore.QPointF(sum(xs) / len(xs), sum(ys) / len(ys))

    def _clear_overlay_items(self) -> None:
        for item in self.overlay_items:
            if item is None or sip.isdeleted(item):
                continue
            try:
                # 检查item是否属于当前场景
                if item.scene() == self.scene:
                    self.scene.removeItem(item)
            except RuntimeError:
                # 忽略已经被删除的图形项
                pass
        self.overlay_items.clear()

    def _clear_spatial_preview_items(self) -> None:
        """清除空间排序预览元素"""
        # 清除预览标签记录
        self.preview_labels.clear()

        for item in self.spatial_preview_items:
            if item is None or sip.isdeleted(item):
                continue
            try:
                # 检查item是否属于当前场景
                if item.scene() == self.scene:
                    self.scene.removeItem(item)
            except RuntimeError:
                # 忽略已经被删除的图形项
                pass
        self.spatial_preview_items.clear()

    def _rebuild_spatial_preview(self) -> None:
        """重建空间排序预览"""
        self._clear_spatial_preview_items()

        if not self.spatial_preview_enabled or not self.preview_options:
            return

        # 只在非排序线模式下显示预设排序预览
        if getattr(self.preview_options, 'spatial_mode', None) == 'LINE_GUIDES':
            return

        self._create_spatial_preview_for_mode(self.preview_options.spatial_mode)

    def _create_spatial_preview_for_mode(self, spatial_mode: str) -> None:
        """为指定的空间排序模式创建预览"""
        if not spatial_mode or not self.shapes_data:
            return

        # 只在非排序线模式下显示预设排序预览
        if spatial_mode == "LINE_GUIDES":
            return

        # 使用正确的排序逻辑
        self._create_simple_order_preview(spatial_mode)

    def _create_simple_order_preview(self, spatial_mode: str) -> None:
        """创建简单的序号预览，使用正确的排序算法"""
        if not self.shapes_data or not self.preview_options:
            return

        # 使用空的排除标签进行排序，让所有标签都参与排序
        temp_options = SortOptions(
            exclude_labels=[],  # 不排除任何标签，全部参与排序
            prioritize_exception_label=False,
            spatial_mode=self.preview_options.spatial_mode,
            line_guides=self.preview_options.line_guides,
        )

        # 使用正确的排序函数，所有shapes都参与排序
        image_size = (self.image_width, self.image_height) if self.image_width > 0 and self.image_height > 0 else None
        sorted_shapes = sort_shapes(self.shapes_data, temp_options, image_size=image_size)

        # 获取排除标签集合 - 直接从dialog获取
        parent_dialog = self.parent()
        exclude_set = set()
        hide_numbers = False

        if parent_dialog and hasattr(parent_dialog, 'hide_numbers_checkbox') and hasattr(parent_dialog, 'exclude_label_edit'):
            hide_numbers = parent_dialog.hide_numbers_checkbox.isChecked()
            if hide_numbers:
                exclude_labels = parent_dialog._collect_exclude_labels()
                exclude_set = set(exclude_labels)

        # 调试信息（已注释，如需调试可取消注释）
        # print(f"所有shapes数量: {len(self.shapes_data)}")
        # print(f"排序后shapes数量: {len(sorted_shapes)}")
        # print(f"排除标签: {list(exclude_set)}")
        # print(f"序号显示时跳过排除标签: {hide_numbers}")

        # 显示序号，但跳过排除的标签
        display_order = 1
        for shape in sorted_shapes:
            center = self._shape_center(shape)
            if not center:
                continue

            label = shape.get("label", "")

            # 检查是否应该跳过显示序号
            should_skip = False
            if hide_numbers and exclude_set:
                for exclude_label in exclude_set:
                    if exclude_label and exclude_label in label:
                        should_skip = True
                        break

            if should_skip:
                # print(f"跳过显示序号: 标签='{label}' (包含排除标签)")
                continue

            # print(f"显示序号 {display_order}: 标签='{label}'")
            self._create_simple_order_label(center, display_order, shape)
            display_order += 1

    def _create_simple_order_label(self, center: QtCore.QPointF, order: int, shape_data: dict) -> None:
        """创建可编辑的序号标签，模仿日漫软件的样式"""
        # 创建可点击的矩形整体
        rect_item = EditablePreviewRect(self, shape_data, order, center)
        self.scene.addItem(rect_item)
        self.scene.addItem(rect_item.label)  # 单独添加数字标签到场景
        self.spatial_preview_items.append(rect_item)
        self.spatial_preview_items.append(rect_item.label)  # 也添加到预览项目列表
        self.preview_labels.append(rect_item)

    def set_spatial_preview_options(self, options: SortOptions) -> None:
        """设置空间预览选项并更新预览"""
        self.preview_options = options
        self._rebuild_spatial_preview()

    def _update_preview_order(self, rect_item: EditablePreviewRect, new_number: int) -> None:
        """更新预览序号，确保唯一性"""
        old_number = int(rect_item.label.text())

        # 检查是否已经存在相同的序号
        existing_item = None
        for item in self.preview_labels:
            if item != rect_item and int(item.label.text()) == new_number:
                existing_item = item
                break

        # 如果存在相同序号，交换序号
        if existing_item:
            existing_item.update_number(old_number)

        # 更新当前项的序号
        rect_item.update_number(new_number)

    def get_custom_order_mapping(self) -> Dict[dict, int]:
        """获取用户自定义的序号映射"""
        mapping = {}
        for rect_item in self.preview_labels:
            if rect_item.custom_order is not None:
                mapping[rect_item.shape_data] = rect_item.custom_order
        return mapping

    def _fit_view(self) -> None:
        if self.image_width > 0 and self.image_height > 0:
            self.view.fitInView(self.scene.sceneRect(), QtCore.Qt.KeepAspectRatio)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit_view()

    # ------------------------------------------------------------------
    def add_guide(
        self,
        start: Optional[QtCore.QPointF] = None,
        end: Optional[QtCore.QPointF] = None,
        rect: Optional[QtCore.QRectF] = None,
    ) -> None:
        if self.image_width <= 0 or self.image_height <= 0:
            return
        if start is None or end is None:
            center_y = self.image_height / 2.0
            start = QtCore.QPointF(self.image_width * 0.2, center_y)
            end = QtCore.QPointF(self.image_width * 0.8, center_y)
        start = self._clamp_point(start)
        end = self._clamp_point(end)
        if start == end:
            end = QtCore.QPointF(start.x() + 1.0, start.y())

        line_item = GuideLineItem(self)
        pen = QtGui.QPen(LINE_COLOR, self.current_line_width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
        line_item.setPen(pen)
        arrow_item = QtWidgets.QGraphicsPolygonItem()
        arrow_item.setBrush(QtGui.QBrush(ARROW_COLOR))
        arrow_item.setPen(QtGui.QPen(ARROW_COLOR))
        arrow_item.setZValue(5)

        label_item = EditableLabelItem(self)
        font = QtGui.QFont()
        font.setPointSize(32)  # 从18增加到32
        font.setBold(True)
        label_item.setFont(font)
        label_item.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))  # 白色文字
        label_item.setPen(QtGui.QPen(QtCore.Qt.NoPen))  # 确保没有边框
        label_item.setZValue(7)

        # 创建标签背景
        label_background = QtWidgets.QGraphicsRectItem()
        label_background.setBrush(QtGui.QBrush(QtGui.QColor(255, 0, 0, 200)))  # 红色半透明背景
        label_background.setPen(QtGui.QPen(QtCore.Qt.transparent))
        label_background.setZValue(6)

        endpoints = {
            "start": EndpointHandle(self, "start"),
            "end": EndpointHandle(self, "end"),
        }

        # 创建矩形控制范围 - 设置为可点击
        rect_item = GuideRectItem(self)
        rect_item.setBrush(QtGui.QBrush(RECT_FILL_COLOR))
        rect_item.setPen(QtGui.QPen(RECT_COLOR, 2, QtCore.Qt.DashLine))
        rect_item.setZValue(2)

        # 创建矩形控制点
        rect_handles = {
            "left": EndpointHandle(self, "left"),
            "right": EndpointHandle(self, "right"),
            "top": EndpointHandle(self, "top"),
            "bottom": EndpointHandle(self, "bottom"),
        }

        # 初始化矩形范围 - 优先使用传入的rect，否则使用用户拖拽的实际大小
        if rect is not None:
            initial_rect = rect
        else:
            initial_rect = QtCore.QRectF(start, end).normalized()

            # 确保最小尺寸
            if initial_rect.width() < MIN_RECT_SIZE:
                center_x = initial_rect.center().x()
                initial_rect.setLeft(center_x - MIN_RECT_SIZE / 2.0)
                initial_rect.setRight(center_x + MIN_RECT_SIZE / 2.0)
            if initial_rect.height() < MIN_RECT_SIZE:
                center_y = initial_rect.center().y()
                initial_rect.setTop(center_y - MIN_RECT_SIZE / 2.0)
                initial_rect.setBottom(center_y + MIN_RECT_SIZE / 2.0)

        # 确保矩形在图像边界内
        initial_rect = self._sanitize_rect(initial_rect)

        record = GuideRecord(
            line_item=line_item,
            arrow_item=arrow_item,
            label_item=label_item,
            label_background=label_background,
            endpoint_handles=endpoints,
            rect_item=rect_item,
            rect_handles=rect_handles,
            start=start,
            end=end,
            rect=initial_rect,
        )
        line_item.set_record(record)
        label_item.set_record(record)
        rect_item.set_record(record)  # 设置矩形项目的record关联
        for handle in endpoints.values():
            handle.set_record(record)
        for handle in rect_handles.values():
            handle.set_record(record)

        self.scene.addItem(line_item)
        self.scene.addItem(arrow_item)
        self.scene.addItem(rect_item)
        self.scene.addItem(label_background)
        self.scene.addItem(label_item)
        for handle in endpoints.values():
            self.scene.addItem(handle)
        for handle in rect_handles.values():
            self.scene.addItem(handle)

        self.guides.append(record)
        self._update_indices()
        self.select_record(record)
        self.guides_changed.emit()

    def change_guide_number(self, record: GuideRecord, new_number: int) -> None:
        """修改指定guide的序号"""
        if not record or new_number <= 0:
            return

        # 设置自定义序号
        record.custom_number = new_number

        # 立即更新显示
        record.label_item.setText(str(new_number))

        # 更新标签背景大小和位置
        rect = record.rect
        label_pos = QtCore.QPointF(rect.left() + 18.0, rect.top() + 18.0)
        record.label_item.setPos(label_pos)

        text_rect = record.label_item.boundingRect()
        padding = 8.0
        background_rect = QtCore.QRectF(
            -padding, -padding,
            text_rect.width() + 2 * padding,
            text_rect.height() + 2 * padding
        )
        record.label_background.setRect(background_rect)
        record.label_background.setPos(label_pos)

        self._refresh_order_list()
        self.guides_changed.emit()

    def _clamp_point(self, point: QtCore.QPointF) -> QtCore.QPointF:
        x = max(0.0, min(self.image_width, point.x()))
        y = max(0.0, min(self.image_height, point.y()))
        return QtCore.QPointF(x, y)

    def _sanitize_rect(self, rect: QtCore.QRectF) -> QtCore.QRectF:
        """确保矩形在图像边界内且有最小尺寸"""
        left = max(0.0, min(rect.left(), self.image_width - MIN_RECT_SIZE))
        top = max(0.0, min(rect.top(), self.image_height - MIN_RECT_SIZE))
        right = max(left + MIN_RECT_SIZE, min(rect.right(), self.image_width))
        bottom = max(top + MIN_RECT_SIZE, min(rect.bottom(), self.image_height))
        return QtCore.QRectF(left, top, right - left, bottom - top)


    def remove_selected(self) -> None:
        if not self.selected_record:
            return
        record = self.selected_record
        for item in [
            record.line_item,
            record.arrow_item,
            record.rect_item,
            record.label_background,
            record.label_item,
            *record.endpoint_handles.values(),
            *record.rect_handles.values(),
        ]:
            self.scene.removeItem(item)
        self.guides.remove(record)
        self.select_record(None)
        self._update_indices()
        self.guides_changed.emit()

    def clear_guides(self) -> None:
        while self.guides:
            record = self.guides.pop()
            for item in [
                record.line_item,
                record.arrow_item,
                record.rect_item,
                record.label_background,
                record.label_item,
                *record.endpoint_handles.values(),
                *record.rect_handles.values(),
            ]:
                self.scene.removeItem(item)
        self.select_record(None)
        self._refresh_order_list()
        self.guides_changed.emit()

    def select_record(self, record: Optional[GuideRecord]) -> None:
        if self.selected_record is record:
            return
        if self.selected_record:
            self._set_highlight(self.selected_record, False)
        self.selected_record = record
        if record:
            self._set_highlight(record, True)
        self._sync_order_list_selection()

    def _set_highlight(self, record: GuideRecord, active: bool) -> None:
        color = LINE_HIGHLIGHT_COLOR if active else LINE_COLOR
        line_width = self.current_line_width + 2.0 if active else self.current_line_width
        record.line_item.setPen(QtGui.QPen(color, line_width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))

        # 设置矩形边框显示
        rect_color = LINE_HIGHLIGHT_COLOR if active else RECT_COLOR
        record.rect_item.setPen(QtGui.QPen(rect_color, 2, QtCore.Qt.DashLine))

        for handle in record.endpoint_handles.values():
            handle.setBrush(QtGui.QBrush(LINE_HIGHLIGHT_COLOR if active else HANDLE_FILL))
        for handle in record.rect_handles.values():
            handle.setBrush(QtGui.QBrush(LINE_HIGHLIGHT_COLOR if active else HANDLE_FILL))

    def _refresh_order_list(self) -> None:
        pass

    def _sync_order_list_selection(self) -> None:
        pass

    def _on_order_list_changed(self) -> None:
        pass

    def _on_order_list_selection_changed(self) -> None:
        pass

    def move_line(self, record: GuideRecord, delta: QtCore.QPointF) -> None:
        if delta.manhattanLength() <= 0.0:
            return
        rect = record.rect
        min_dx = -rect.left()
        max_dx = self.image_width - rect.right()
        min_dy = -rect.top()
        max_dy = self.image_height - rect.bottom()
        dx = max(min(delta.x(), max_dx), min_dx)
        dy = max(min(delta.y(), max_dy), min_dy)
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return
        translation = QtCore.QPointF(dx, dy)
        record.start += translation
        record.end += translation
        record.rect = record.rect.translated(translation)
        self._update_record_visuals(record)
        self.guides_changed.emit()

    def move_endpoint(self, record: GuideRecord, role: str, scene_pos: QtCore.QPointF) -> None:
        point = self._clamp_point(scene_pos)

        # 只允许矩形控制点，不允许箭头端点控制
        if role in ["left", "right", "top", "bottom"]:
            # 矩形控制点：调整矩形大小，箭头保持在中心
            rect = record.rect
            if role == "left":
                new_width = rect.right() - point.x()
                if new_width >= MIN_RECT_SIZE:
                    rect.setLeft(point.x())
            elif role == "right":
                new_width = point.x() - rect.left()
                if new_width >= MIN_RECT_SIZE:
                    rect.setRight(point.x())
            elif role == "top":
                new_height = rect.bottom() - point.y()
                if new_height >= MIN_RECT_SIZE:
                    rect.setTop(point.y())
            elif role == "bottom":
                new_height = point.y() - rect.top()
                if new_height >= MIN_RECT_SIZE:
                    rect.setBottom(point.y())

            # 确保矩形在边界内
            record.rect = self._sanitize_rect(rect)

            self._update_record_visuals(record)
            self.guides_changed.emit()
        # 忽略箭头端点的拖拽 - start和end不处理


    def flip_direction(self, record: GuideRecord) -> None:
        record.start, record.end = record.end, record.start
        self._update_record_visuals(record)
        self.guides_changed.emit()

    def _update_record_visuals(self, record: GuideRecord) -> None:
        rect = record.rect
        rect_center = rect.center()

        # 计算箭头方向（保持用户设定的方向）
        arrow_vector = record.end - record.start
        arrow_length = math.hypot(arrow_vector.x(), arrow_vector.y())

        # 箭头横跨整个矩形，根据用户绘制时的方向确定
        arrow_margin = 10.0

        if arrow_length > 1e-6:
            direction = arrow_vector / arrow_length

            # 判断主要是水平还是垂直方向
            if abs(direction.x()) > abs(direction.y()):
                # 水平方向为主，箭头横跨矩形宽度
                record.start = QtCore.QPointF(rect.left() + arrow_margin, rect_center.y())
                record.end = QtCore.QPointF(rect.right() - arrow_margin, rect_center.y())
                if direction.x() < 0:  # 向左，翻转箭头
                    record.start, record.end = record.end, record.start
            else:
                # 垂直方向为主，箭头横跨矩形高度
                record.start = QtCore.QPointF(rect_center.x(), rect.top() + arrow_margin)
                record.end = QtCore.QPointF(rect_center.x(), rect.bottom() - arrow_margin)
                if direction.y() < 0:  # 向上，翻转箭头
                    record.start, record.end = record.end, record.start
        else:
            # 默认水平箭头，横跨整个矩形宽度
            record.start = QtCore.QPointF(rect.left() + arrow_margin, rect_center.y())
            record.end = QtCore.QPointF(rect.right() - arrow_margin, rect_center.y())

        record.rect_item.setRect(rect)
        record.line_item.setLine(record.start.x(), record.start.y(), record.end.x(), record.end.y())

        # 计算并更新箭头
        dx = record.end.x() - record.start.x()
        dy = record.end.y() - record.start.y()
        length = max(1.0, math.hypot(dx, dy))
        if length > 1e-6:
            angle = math.atan2(dy, dx)
            arrow_length = max(24.0, min(50.0, length * 0.25))
            tip = record.end
            left = QtCore.QPointF(
                tip.x() - arrow_length * math.cos(angle) + arrow_length * 0.5 * math.sin(angle),
                tip.y() - arrow_length * math.sin(angle) - arrow_length * 0.5 * math.cos(angle),
            )
            right = QtCore.QPointF(
                tip.x() - arrow_length * math.cos(angle) - arrow_length * 0.5 * math.sin(angle),
                tip.y() - arrow_length * math.sin(angle) + arrow_length * 0.5 * math.cos(angle),
            )
            record.arrow_item.setPolygon(QtGui.QPolygonF([tip, left, right]))

        # 隐藏箭头端点控制点，不允许改变方向
        for role, handle in record.endpoint_handles.items():
            handle.setPos(record.start if role == "start" else record.end)
            handle.setVisible(False)  # 隐藏端点控制

        # 更新矩形控制点位置
        record.rect_handles["left"].setPos(rect.left(), rect.center().y())
        record.rect_handles["right"].setPos(rect.right(), rect.center().y())
        record.rect_handles["top"].setPos(rect.center().x(), rect.top())
        record.rect_handles["bottom"].setPos(rect.center().x(), rect.bottom())

        # 使用自定义序号或默认索引
        if record.custom_number is not None:
            display_number = record.custom_number
        else:
            display_number = self.guides.index(record) + 1 if record in self.guides else 1

        record.label_item.setText(str(display_number))

        # 更新标签和背景位置
        label_pos = QtCore.QPointF(rect.left() + 18.0, rect.top() + 18.0)
        record.label_item.setPos(label_pos)

        # 计算并设置背景矩形的大小和位置
        text_rect = record.label_item.boundingRect()
        padding = 8.0  # 背景四周的边距
        background_rect = QtCore.QRectF(
            -padding, -padding,
            text_rect.width() + 2 * padding,
            text_rect.height() + 2 * padding
        )
        record.label_background.setRect(background_rect)
        record.label_background.setPos(label_pos)

    def _update_indices(self) -> None:
        for record in self.guides:
            self._update_record_visuals(record)
        self._refresh_order_list()

    def has_guides(self) -> bool:
        return bool(self.guides)

    def serialize_guides(self) -> List[LineGuide]:
        if self.image_width <= 0 or self.image_height <= 0:
            return []
        guides: List[LineGuide] = []
        for record in self.guides:
            rect = record.rect
            guides.append(
                LineGuide(
                    start=(record.start.x() / self.image_width, record.start.y() / self.image_height),
                    end=(record.end.x() / self.image_width, record.end.y() / self.image_height),
                    rect=(
                        rect.left() / self.image_width,
                        rect.top() / self.image_height,
                        rect.width() / self.image_width,
                        rect.height() / self.image_height,
                    ),
                    order=record.custom_number,
                )
            )
        return guides


class TagSortDialog(QtWidgets.QDialog):
    run_requested = QtCore.pyqtSignal(dict)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("标签排序工具"))
        self.setWindowFlags(
            self.windowFlags() |
            QtCore.Qt.WindowMaximizeButtonHint |
            QtCore.Qt.WindowMinimizeButtonHint
        )
        self.resize(840, 520)
        self.setMinimumSize(800, 480)

        # 保存排序线条设置，用于翻页继承
        self._saved_guides = None

        self.guide_widget = TagSortGuideWidget(self)
        # 连接guides变化信号，实时保存排序线条设置
        self.guide_widget.guides_changed.connect(self._on_guides_changed)

        self.exclude_label_edit = QtWidgets.QLineEdit("other")
        self.exclude_label_edit.setPlaceholderText(self.tr("示例: 标签1, 标签2"))
        self.exclude_keep_checkbox = QtWidgets.QCheckBox(self.tr("排除标签保持原顺序"))
        self.exclude_keep_checkbox.setChecked(True)
        
        # 新增：排除锁定的标签
        self.exclude_locked_checkbox = QtWidgets.QCheckBox(self.tr("排除锁定的标签"))
        self.exclude_locked_checkbox.setChecked(True)
        self.exclude_locked_checkbox.setToolTip(self.tr("勾选后，锁定的标签不参与排序"))

        # 新增：序号显示选项
        self.hide_numbers_checkbox = QtWidgets.QCheckBox(self.tr("序号显示时跳过排除标签"))
        self.hide_numbers_checkbox.setChecked(True)
        self.hide_numbers_checkbox.setToolTip(self.tr("勾选后，包含排除标签的项目不显示序号"))

        self.spatial_mode_combo = QtWidgets.QComboBox()
        for mode in available_spatial_modes():
            if mode == "NONE":
                continue
            description = SPATIAL_MODE_LABELS.get(mode, mode)
            self.spatial_mode_combo.addItem(self.tr(description), mode)
        self._select_spatial_mode("LEFT_TO_RIGHT")

        self.spatial_mode_combo.currentIndexChanged.connect(self._on_spatial_mode_changed)
        self.exclude_label_edit.textChanged.connect(self._on_sort_parameter_changed)
        self.exclude_keep_checkbox.stateChanged.connect(self._on_sort_parameter_changed)
        self.exclude_locked_checkbox.stateChanged.connect(self._on_sort_parameter_changed)
        self.hide_numbers_checkbox.stateChanged.connect(self._on_sort_parameter_changed)


        sort_group = QtWidgets.QGroupBox(self.tr("排序设置"))
        sort_form = QtWidgets.QFormLayout(sort_group)
        sort_form.addRow(self.tr("排除标签"), self.exclude_label_edit)
        sort_form.addRow("", self.exclude_keep_checkbox)
        sort_form.addRow("", self.exclude_locked_checkbox)
        sort_form.addRow("", self.hide_numbers_checkbox)
        sort_form.addRow(self.tr("空间排序方式"), self.spatial_mode_combo)

        range_group = QtWidgets.QGroupBox(self.tr("范围选择"))
        range_layout = QtWidgets.QHBoxLayout(range_group)
        self.start_spinbox = QtWidgets.QSpinBox()
        self.start_spinbox.setPrefix("从: ")
        self.end_spinbox = QtWidgets.QSpinBox()
        self.end_spinbox.setPrefix("到: ")

        total_files = 0
        current_page = 1
        if self.parent() and hasattr(self.parent(), 'file_list_widget'):
            total_files = self.parent().file_list_widget.count()
            current_index = self.parent().file_list_widget.currentRow()
            if current_index >= 0:
                current_page = current_index + 1

        if total_files > 0:
            self.start_spinbox.setRange(1, total_files)
            self.end_spinbox.setRange(1, total_files)
            self.start_spinbox.setValue(current_page)
            self.end_spinbox.setValue(total_files)

        range_layout.addWidget(self.start_spinbox)
        range_layout.addWidget(self.end_spinbox)
        range_layout.addStretch()
        range_group.setLayout(range_layout)

        sort_group.layout().addRow(range_group) # Add range group to the form layout

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)

        self.log_output = QtWidgets.QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumBlockCount(1000)
        self.log_output.setMinimumHeight(200)

        status_group = QtWidgets.QGroupBox(self.tr("执行状态"))
        status_layout = QtWidgets.QVBoxLayout(status_group)
        status_layout.addWidget(self.progress_bar)
        status_layout.addWidget(self.log_output)

        self.run_current_button = QtWidgets.QPushButton(self.tr("对当前页面排序"))
        self.run_range_button = QtWidgets.QPushButton(self.tr("对指定范围排序"))
        self.run_all_button = QtWidgets.QPushButton(self.tr("对全部页面排序"))
        self.close_button = QtWidgets.QPushButton(self.tr("关闭"))

        action_row = QtWidgets.QHBoxLayout()
        action_row.addWidget(self.run_current_button)
        action_row.addWidget(self.run_range_button)
        action_row.addWidget(self.run_all_button)
        action_row.addStretch(1)
        action_row.addWidget(self.close_button)

        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(sort_group)
        left_layout.addWidget(status_group)
        left_layout.addLayout(action_row)
        left_layout.addStretch(1)

        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(16)
        main_layout.addLayout(left_layout, 1)
        main_layout.addWidget(self.guide_widget, 1)

        self.run_current_button.clicked.connect(lambda: self._emit_request("current"))
        self.run_range_button.clicked.connect(lambda: self._emit_request("range"))
        self.run_all_button.clicked.connect(lambda: self._emit_request("all"))
        self.close_button.clicked.connect(self.reject)

        # 初始化guide_widget的方法调用
 
    def refresh_state(self, total_files: int, current_page: int) -> None:
        """刷新对话框的状态，特别是文件范围。"""
        if total_files > 0:
            self.start_spinbox.setRange(1, total_files)
            self.end_spinbox.setRange(1, total_files)
            self.start_spinbox.setValue(current_page)
            self.end_spinbox.setValue(total_files)
    
    def update_page_range(self, current_page: int, total_pages: int) -> None:
        """更新范围选择的页码范围"""
        if total_pages > 0:
            self.start_spinbox.setRange(1, total_pages)
            self.end_spinbox.setRange(1, total_pages)
            self.start_spinbox.setValue(current_page)
            self.end_spinbox.setValue(total_pages)


    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """处理键盘快捷键"""
        # 先检查是否有输入框获得焦点，如果有，不处理翻页
        focused_widget = QtWidgets.QApplication.focusWidget()
        if isinstance(focused_widget, (QtWidgets.QLineEdit, QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit)):
            super().keyPressEvent(event)
            return

        # 如果按下A或D键且没有修饰键，转发给父窗口进行翻页
        if event.modifiers() == QtCore.Qt.NoModifier:
            if event.key() in (QtCore.Qt.Key_A, QtCore.Qt.Key_D, QtCore.Qt.Key_Left, QtCore.Qt.Key_Right):
                # 转发翻页事件到主窗口
                parent = self.parent()
                while parent and not hasattr(parent, 'open_next_image'):
                    parent = parent.parent()
                if parent:
                    QtWidgets.QApplication.sendEvent(parent, event)
                    event.accept()
                    return

        # 对于其他按键，调用父类的处理方法
        super().keyPressEvent(event)

    def _select_spatial_mode(self, mode: str) -> None:
        index = self.spatial_mode_combo.findData(mode)
        if index != -1:
            self.spatial_mode_combo.setCurrentIndex(index)

    def _on_guides_changed(self) -> None:
        self._update_saved_guides()

    def _on_spatial_mode_changed(self) -> None:
        """当空间排序模式改变时触发"""
        # 更新预览
        self._update_preview_for_current_options()

    def _on_sort_parameter_changed(self) -> None:
        """当排序参数改变时触发"""
        # 更新预览
        self._update_preview_for_current_options()

    def _update_preview_for_current_options(self) -> None:
        """根据当前选项更新预览"""
        try:
            options = self._collect_sort_options()
            self.guide_widget.set_spatial_preview_options(options)
        except Exception:
            # 如果收集选项失败，清除预览
            self.guide_widget._clear_spatial_preview_items()

    def _collect_sort_options(self) -> SortOptions:
        mode = self.spatial_mode_combo.currentData()
        return SortOptions(
            exclude_labels=self._collect_exclude_labels(),
            prioritize_exception_label=self.exclude_keep_checkbox.isChecked(),
            spatial_mode=mode,
            line_guides=self.guide_widget.serialize_guides(),
        )

    def _emit_request(self, scope: str) -> None:
        options = self._collect_sort_options()
        if options.spatial_mode == "LINE_GUIDES" and not self.guide_widget.has_guides():
            QtWidgets.QMessageBox.information(
                self,
                self.tr("缺少排序线"),
                self.tr("当前排序方式为“使用自定义排序线”，请在右侧视图中至少绘制一条排序线。"),
            )
            return

        self.log_output.clear()
        payload = {"options": options, "scope": scope}

        if scope == "range":
            start_index = self.start_spinbox.value() - 1
            end_index = self.end_spinbox.value() - 1
            if start_index > end_index:
                self.append_log("错误：起始位置不能大于结束位置。")
                return
            payload["start_index"] = start_index
            payload["end_index"] = end_index

        self.run_requested.emit(payload)

    def _collect_exclude_labels(self) -> List[str]:
        text = self.exclude_label_edit.text().strip()
        exclude_labels = []
        if text:
            for sep in ('\n', '\t', ';', '；', '、'):
                text = text.replace(sep, ',')
            parts = [segment.strip() for segment in text.split(',')]
            exclude_labels = [part for part in parts if part]
        
        # 如果勾选了"排除锁定的标签"，添加锁定的标签
        if self.exclude_locked_checkbox.isChecked():
            parent = self.parent()
            if parent and hasattr(parent, '_config'):
                locked_labels_str = parent._config.get("locked_labels", "")
                if locked_labels_str:
                    locked_labels = [label.strip() for label in locked_labels_str.split(",") if label.strip()]
                    for label in locked_labels:
                        if label not in exclude_labels:
                            exclude_labels.append(label)
        
        return exclude_labels

    def _build_payload(self, scope: str) -> dict:
        options = self._collect_sort_options()
        return {"options": options, "scope": scope}

    def set_context(self, pixmap: Optional[QtGui.QPixmap], shapes: Optional[List[dict]] = None) -> None:
        # 保存当前的排序线条设置
        current_guides = self.guide_widget.serialize_guides()
        if current_guides:
            self._saved_guides = current_guides

        # 决定要恢复的guides：优先使用保存的guides，否则使用传入的guides
        restore_guides = self._saved_guides if self._saved_guides else None

        if not pixmap or pixmap.isNull():
            self.guide_widget.load_pixmap(None, shapes=[], guides=None)
            return

        # 加载新图片，并恢复保存的排序线条
        self.guide_widget.load_pixmap(pixmap, shapes=shapes or [], guides=restore_guides)

        # 更新空间排序预览
        self._update_preview_for_current_options()

    def _update_saved_guides(self) -> None:
        """实时更新保存的排序线条设置"""
        current_guides = self.guide_widget.serialize_guides()
        if current_guides:
            self._saved_guides = current_guides
        else:
            # 如果当前没有guides了，清除保存的设置
            self._saved_guides = None

    def clear_saved_guides(self) -> None:
        """清除保存的排序线条设置"""
        self._saved_guides = None

    def append_log(self, message: str) -> None:
        self.log_output.appendPlainText(message)
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def set_busy(self, busy: bool) -> None:
        for widget in (
            self.run_current_button,
            self.run_range_button,
            self.run_all_button,
            self.close_button,
            self.exclude_label_edit,
            self.exclude_keep_checkbox,
            self.spatial_mode_combo,
            self.guide_widget,
            self.guide_widget.draw_mode_button,
        ):
            widget.setDisabled(busy)
        if busy:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)

    def set_progress(self, processed: int, total: int) -> None:
        if total <= 0:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(min(processed, total))

    def reset(self) -> None:
        self.set_busy(False)
        self.log_output.clear()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
