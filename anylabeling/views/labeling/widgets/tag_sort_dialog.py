import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import sip
from PyQt5 import QtCore, QtGui, QtWidgets

from anylabeling.config import get_config, save_config
from anylabeling.services.tag_sorting import (
    LineGuide,
    SortOptions,
    available_spatial_modes,
    build_scanline_plan,
    is_sortable_shape,
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
ORDER_ARROW_COLOR = QtGui.QColor(255, 140, 0, 220)
ORDER_ARROW_WIDTH = 3.0
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


class GuideLineItem(QtWidgets.QGraphicsPathItem):
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

    def setLine(self, x1: float, y1: float, x2: float, y2: float) -> None:
        path = QtGui.QPainterPath(QtCore.QPointF(x1, y1))
        path.lineTo(x2, y2)
        self.setPath(path)

    def set_points(self, points: List[QtCore.QPointF]) -> None:
        if len(points) < 2:
            return
        path = QtGui.QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        self.setPath(path)

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
    path: List[QtCore.QPointF] = field(default_factory=list)


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

        self.scan_animation_button = QtWidgets.QToolButton()
        self.scan_animation_button.setText(self.tr("动态检测"))
        self.scan_animation_button.setToolTip(self.tr("播放当前排序规则的实际检测过程"))
        self.scan_animation_button.clicked.connect(self.toggle_scan_animation)

        self.horizontal_scan_label = QtWidgets.QLabel(self.tr("横向检测距离:"))
        self.horizontal_scan_spinbox = QtWidgets.QSpinBox()
        self.horizontal_scan_spinbox.setRange(1, 200)
        self.horizontal_scan_spinbox.setValue(12)
        self.horizontal_scan_spinbox.setSuffix("px")
        self.horizontal_scan_spinbox.setToolTip(self.tr("横向扫描取样之间的距离"))

        self.vertical_scan_label = QtWidgets.QLabel(self.tr("纵向检测距离:"))
        self.vertical_scan_spinbox = QtWidgets.QSpinBox()
        self.vertical_scan_spinbox.setRange(1, 200)
        self.vertical_scan_spinbox.setValue(12)
        self.vertical_scan_spinbox.setSuffix("px")
        self.vertical_scan_spinbox.setToolTip(self.tr("纵向扫描取样之间的距离"))

        # 添加线条粗细设置
        self.line_width_label = QtWidgets.QLabel(self.tr("线条粗细:"))
        self.line_width_spinbox = QtWidgets.QSpinBox()
        self.line_width_spinbox.setRange(4, 30)
        self.line_width_spinbox.setValue(int(LINE_WIDTH))
        self.line_width_spinbox.setSuffix("px")
        self.line_width_spinbox.valueChanged.connect(self.update_line_width)

        self._order_list_syncing = False

        self.controls_widget = QtWidgets.QWidget(self)
        button_row = QtWidgets.QHBoxLayout(self.controls_widget)
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(6)
        button_row.addWidget(self.draw_mode_button)
        button_row.addWidget(self.scan_animation_button)
        button_row.addWidget(self.horizontal_scan_label)
        button_row.addWidget(self.horizontal_scan_spinbox)
        button_row.addWidget(self.vertical_scan_label)
        button_row.addWidget(self.vertical_scan_spinbox)
        button_row.addWidget(self.line_width_label)
        button_row.addWidget(self.line_width_spinbox)
        button_row.addStretch(1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.view, 1)

        self.background_item: Optional[QtWidgets.QGraphicsPixmapItem] = None
        self.shape_items: List[QtWidgets.QGraphicsRectItem] = []
        self.guides: List[GuideRecord] = []
        self.selected_record: Optional[GuideRecord] = None
        # The path-reorder stroke is temporary. It must not create the old
        # persistent guide line/arrow/rectangle objects.
        self._active_path_guide: Optional[LineGuide] = None
        self.image_width = 0.0
        self.image_height = 0.0
        self.is_draw_mode = False
        self._draw_start: Optional[QtCore.QPointF] = None
        self._draw_path: List[QtCore.QPointF] = []
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

        self._scan_timer = QtCore.QTimer(self)
        self._scan_timer.setInterval(16)
        self._scan_timer.timeout.connect(self._advance_scan_animation)
        self._scan_events = []
        self._scan_event_index = 0
        self._scan_recorded_ids = set()
        self._scan_order = 1
        self._scan_x = 0.0
        self._scan_y = 0.0
        self._scan_hold_ticks = 0
        self._scan_vertical_item = None
        self._scan_horizontal_item = None

        # 预设排序可视化相关
        self.spatial_preview_items: List[QtWidgets.QGraphicsItem] = []
        self.spatial_preview_enabled = True
        self.zoom_mode = "fit"


    def take_controls_widget(self) -> QtWidgets.QWidget:
        controls = self.controls_widget
        self.layout().removeWidget(controls)
        controls.setParent(None)
        return controls

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
        self.is_draw_mode = enabled
        if enabled:
            # Drawing mode is path-reorder mode. Remove any old persistent
            # guide visuals before accepting the new temporary stroke.
            if self.guides or self._active_path_guide is not None:
                self.clear_guides()
            self.view.viewport().setCursor(QtCore.Qt.CrossCursor)
            self.select_record(None)
        else:
            self.view.viewport().unsetCursor()
            self._clear_preview()

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
                self._draw_path = [self._draw_start]
                self._start_preview(self._draw_start)
                return True
            if event.type() == QtCore.QEvent.MouseMove and self._draw_start is not None:
                pos = self.view.mapToScene(event.pos())
                if not self._draw_path or (pos - self._draw_path[-1]).manhattanLength() >= 3:
                    self._draw_path.append(self._clamp_point(pos))
                self._update_preview(pos)
                return True
            if event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton:
                if self._draw_start is not None:
                    self._finish_preview(self.view.mapToScene(event.pos()))
                self._draw_start = None
                self._draw_path = []
                return True
        return super().eventFilter(obj, event)

    def _start_preview(self, pos: QtCore.QPointF) -> None:
        self._clear_preview()
        self._preview_line = QtWidgets.QGraphicsPathItem()
        pen = QtGui.QPen(LINE_COLOR, self.current_line_width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        self._preview_line.setPen(pen)
        self._preview_line.setZValue(10)
        self.scene.addItem(self._preview_line)

    def _update_preview(self, pos: QtCore.QPointF) -> None:
        if not self._preview_line or not self._draw_path:
            return
        path = QtGui.QPainterPath(self._draw_path[0])
        for point in self._draw_path[1:]:
            path.lineTo(point)
        if (not self._draw_path or (pos - self._draw_path[-1]).manhattanLength() >= 1):
            path.lineTo(pos)
        self._preview_line.setPath(path)

    def _finish_preview(self, pos: QtCore.QPointF) -> None:
        self._clear_preview()
        if self.image_width <= 0 or self.image_height <= 0:
            return
        start = self._draw_start or pos
        if (start - pos).manhattanLength() < 12.0:
            center_y = self.image_height / 2.0
            start = QtCore.QPointF(self.image_width * 0.2, center_y)
            pos = QtCore.QPointF(self.image_width * 0.8, center_y)
        path = list(self._draw_path)
        if len(path) < 2:
            path = [start, pos]

        # Keep only a normalized, invisible data path. Do not call add_guide:
        # that method creates the old persistent line, arrow, rectangle and
        # handles, which are not part of path reorder.
        self.clear_guides()
        self._active_path_guide = LineGuide(
            start=(start.x() / self.image_width, start.y() / self.image_height),
            end=(pos.x() / self.image_width, pos.y() / self.image_height),
            rect=(0.0, 0.0, 1.0, 1.0),
            path=[(point.x() / self.image_width, point.y() / self.image_height) for point in path],
        )
        current = self.preview_options or SortOptions()
        self.set_spatial_preview_options(SortOptions(
            exception_label=current.exception_label,
            prioritize_exception_label=current.prioritize_exception_label,
            spatial_mode="LINE_GUIDES",
            line_guides=[self._active_path_guide],
            exclude_labels=list(current.exclude_labels),
        ))

    # ------------------------------------------------------------------
    # Scene helpers
    # ------------------------------------------------------------------
    def load_pixmap(
        self,
        pixmap: Optional[QtGui.QPixmap],
        shapes: Optional[List[dict]] = None,
        guides: Optional[List[LineGuide]] = None,
    ) -> None:
        self._stop_scan_animation(remove_lines=True)
        # 先清除所有预览元素，避免场景切换时的冲突
        self._clear_spatial_preview_items()
        self._clear_overlay_items()

        self.scene.clear()
        self.guides.clear()
        self._active_path_guide = None
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
                path_points = [
                    QtCore.QPointF(point[0] * self.image_width, point[1] * self.image_height)
                    for point in (getattr(guide, "path", None) or [])
                ]
                self.add_guide(start, end, rect, path_points=path_points)
                if self.guides and getattr(guide, "order", None) is not None:
                    self.guides[-1].custom_number = int(guide.order)
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
        for shape in self.shapes_data:
            rect = self._shape_rect(shape)
            if not rect:
                continue
            rgb = shape.get("_sort_color") or (0, 174, 255)
            color = QtGui.QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]))
            pen = QtGui.QPen(color, 2)
            pen.setCosmetic(True)
            fill = QtGui.QColor(color)
            fill.setAlpha(35)

            # Keep rotated rectangles rotated in the sorting preview. The
            # bounding rectangle is still used for ordering and label placement.
            if shape.get("shape_type") == "rotation":
                points = self._shape_points(shape)
                item = QtWidgets.QGraphicsPolygonItem(QtGui.QPolygonF(points))
            else:
                item = QtWidgets.QGraphicsRectItem(rect)
            item.setPen(pen)
            item.setBrush(QtGui.QBrush(fill))
            item.setZValue(1)
            self.scene.addItem(item)
            self.shape_items.append(item)

            label_item = QtWidgets.QGraphicsSimpleTextItem(str(shape.get("label") or ""))
            font = QtGui.QFont()
            font.setPointSize(9)
            font.setBold(True)
            label_item.setFont(font)
            label_item.setBrush(QtGui.QBrush(color))
            label_item.setPos(rect.left(), max(0.0, rect.top() - label_item.boundingRect().height()))
            label_item.setZValue(2)
            self.scene.addItem(label_item)
            self.shape_items.append(label_item)

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

        self._create_spatial_preview_for_mode(self.preview_options.spatial_mode)

    def _create_spatial_preview_for_mode(self, spatial_mode: str) -> None:
        """为指定的空间排序模式创建预览"""
        if not spatial_mode or not self.shapes_data:
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
            priority_labels=self.preview_options.priority_labels,
            horizontal_scan_distance=self.preview_options.horizontal_scan_distance,
            vertical_scan_distance=self.preview_options.vertical_scan_distance,
        )

        # 使用与画布网格完全一致的扫描线排序计划，避免“预览箭头”和
        # 实际写入顺序使用两套不同算法。
        image_size = (self.image_width, self.image_height) if self.image_width > 0 and self.image_height > 0 else None
        if self.preview_options.spatial_mode == "RIGHT_TO_LEFT":
            sorted_shapes, scanlines = build_scanline_plan(
                self.shapes_data,
                self.preview_options.spatial_mode,
                image_size,
                self.preview_options.normalized_exclude_labels(),
                self.preview_options.priority_labels,
                self.preview_options.horizontal_scan_distance,
                self.preview_options.vertical_scan_distance,
            )
        else:
            sorted_shapes = sort_shapes(self.shapes_data, temp_options, image_size=image_size)
            scanlines = []

        # 获取排除标签集合 - 直接从dialog获取
        parent_dialog = self.window()
        exclude_set = set()
        hide_numbers = False

        if parent_dialog and hasattr(parent_dialog, "hide_numbers_checkbox"):
            hide_numbers = parent_dialog.hide_numbers_checkbox.isChecked()
            if hide_numbers:
                exclude_set = set(self.preview_options.normalized_exclude_labels())

        # 调试信息（已注释，如需调试可取消注释）
        # print(f"所有shapes数量: {len(self.shapes_data)}")
        # print(f"排序后shapes数量: {len(sorted_shapes)}")
        # print(f"排除标签: {list(exclude_set)}")
        # print(f"序号显示时跳过排除标签: {hide_numbers}")

        visible_shapes = []
        for shape in sorted_shapes:
            center = self._shape_center(shape)
            if not center:
                continue
            label = shape.get("label", "")
            if hide_numbers and label in exclude_set:
                continue
            visible_shapes.append((shape, center))

        # The full # grid remains available to the algorithm as calculation
        # data, but is intentionally hidden from the final sorting canvas.
        for display_order, (shape, center) in enumerate(visible_shapes, start=1):
            self._create_simple_order_label(center, display_order, shape)

    def toggle_scan_animation(self) -> None:
        if self._scan_timer.isActive():
            self._stop_scan_animation(remove_lines=True)
            self._rebuild_spatial_preview()
            return
        self._start_scan_animation()

    def _start_scan_animation(self) -> None:
        if (
            not self.preview_options
            or not self.shapes_data
            or self.image_width <= 0
            or self.image_height <= 0
        ):
            return

        excluded = set(self.preview_options.normalized_exclude_labels())
        sorted_shapes = sort_shapes(
            self.shapes_data,
            self.preview_options,
            image_size=(self.image_width, self.image_height),
        )
        candidates = []
        for shape in sorted_shapes:
            if shape.get("label") in excluded:
                continue
            rect = self._shape_rect(shape)
            center = self._shape_center(shape)
            if rect is None or center is None:
                continue
            candidates.append({
                "shape": shape,
                "rect": rect,
                "center": center,
                "index": len(candidates),
            })
        if not candidates:
            return

        self._clear_spatial_preview_items()
        self._scan_events = candidates
        self._scan_event_index = 0
        self._scan_recorded_ids = set()
        self._scan_order = 1
        self._scan_mode = self.preview_options.spatial_mode
        # Each target gets a fresh crosshair starting at the right edge.
        # The scan direction is always right-to-left; it never reuses the
        # previous target's x position.
        if self._scan_mode == "LEFT_TO_RIGHT":
            self._scan_x = 0.0
        else:
            self._scan_x = float(self.image_width)
        self._scan_y = float(candidates[0]["center"].y())
        self._scan_hold_ticks = 0

        pen = QtGui.QPen(QtGui.QColor(255, 70, 40, 235), 2.4)
        pen.setCosmetic(True)
        self._scan_vertical_item = QtWidgets.QGraphicsLineItem()
        self._scan_horizontal_item = QtWidgets.QGraphicsLineItem()
        for item in (self._scan_vertical_item, self._scan_horizontal_item):
            item.setPen(pen)
            item.setZValue(30)
            self.scene.addItem(item)
        self._update_scan_crosshair()
        self.scan_animation_button.setText(self.tr("停止检测"))
        self._scan_timer.start()


    @staticmethod
    def _move_towards(current: float, target: float, step: float) -> float:
        if abs(target - current) <= step:
            return target
        return current + step if target > current else current - step

    def _advance_scan_animation(self) -> None:
        if self._scan_event_index >= len(self._scan_events):
            self._stop_scan_animation(remove_lines=True)
            return
        if self._scan_hold_ticks > 0:
            self._scan_hold_ticks -= 1
            return

        # Replay the exact static order. Every target gets a new crosshair
        # at the right edge, which then moves only from right to left until it
        # reaches the target. This prevents any rightward return movement.
        event = self._scan_events[self._scan_event_index]
        animation_step = 8.0
        mode = self._scan_mode
        if mode == "LEFT_TO_RIGHT":
            target_x = event["rect"].left()
        elif mode == "Y_THEN_X":
            target_x = event["center"].x()
        else:
            target_x = event["rect"].right()
        target_y = event["rect"].top() if mode == "Y_THEN_X" else event["center"].y()

        # Animation speed stays fixed. Detection distance only quantizes the
        # horizontal/vertical sampling position of the crosshair.
        self._scan_y = target_y
        self._scan_x = self._move_towards(self._scan_x, target_x, animation_step)
        self._update_scan_crosshair()

        if abs(self._scan_x - target_x) <= 0.01:
            self._create_simple_order_label(
                event["center"], self._scan_event_index + 1, event["shape"]
            )
            self._scan_event_index += 1
            self._scan_hold_ticks = 6
            if self._scan_event_index < len(self._scan_events):
                # Reset for the next independent right-to-left scan line.
                self._scan_x = 0.0 if self._scan_mode == "LEFT_TO_RIGHT" else float(self.image_width)

    def _update_scan_crosshair(self) -> None:
        if self._scan_vertical_item is not None:
            self._scan_vertical_item.setLine(
                self._scan_x, 0.0, self._scan_x, self.image_height
            )
        if self._scan_horizontal_item is not None:
            self._scan_horizontal_item.setLine(
                0.0,
                self._scan_y,
                self.image_width,
                self._scan_y,
            )

    def _stop_scan_animation(self, remove_lines: bool = True) -> None:
        if hasattr(self, "_scan_timer"):
            self._scan_timer.stop()
        if hasattr(self, "scan_animation_button"):
            self.scan_animation_button.setText(self.tr("动态检测"))
        if remove_lines:
            for item in (
                getattr(self, "_scan_vertical_item", None),
                getattr(self, "_scan_horizontal_item", None),
            ):
                if item is None:
                    continue
                try:
                    if item.scene() == self.scene:
                        self.scene.removeItem(item)
                except RuntimeError:
                    pass
            self._scan_vertical_item = None
            self._scan_horizontal_item = None
        self._scan_events = []
        self._scan_event_index = 0
        self._scan_recorded_ids = set()
        self._scan_order = 1
        self._scan_hold_ticks = 0

    def _create_grid_line(self, start: QtCore.QPointF, end: QtCore.QPointF) -> None:
        """Draw one thin line of the full-page calculation grid."""
        if QtCore.QLineF(start, end).length() < 2.0:
            return
        grid_color = QtGui.QColor(ORDER_ARROW_COLOR)
        grid_color.setAlpha(72)
        item = QtWidgets.QGraphicsLineItem(QtCore.QLineF(start, end))
        pen = QtGui.QPen(grid_color, 0.8, QtCore.Qt.SolidLine, QtCore.Qt.FlatCap)
        pen.setCosmetic(True)
        item.setPen(pen)
        item.setZValue(7)
        self.scene.addItem(item)
        self.spatial_preview_items.append(item)

    def _create_grid_direction_arrow(self) -> None:
        """Show the reading direction once without covering every grid cell."""
        if self.image_width <= 0 or self.image_height <= 0:
            return
        y = max(18.0, min(self.image_height - 18.0, self.image_height * 0.08))
        start = QtCore.QPointF(self.image_width * 0.72, y)
        tip = QtCore.QPointF(self.image_width * 0.28, y)
        shaft = QtWidgets.QGraphicsLineItem(QtCore.QLineF(start, tip))
        pen = QtGui.QPen(ORDER_ARROW_COLOR, 3.0, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
        pen.setCosmetic(True)
        shaft.setPen(pen)
        shaft.setZValue(8)
        self.scene.addItem(shaft)
        self.spatial_preview_items.append(shaft)

        head_length = 16.0
        head_width = 9.0
        base = QtCore.QPointF(tip.x() + head_length, tip.y())
        arrow = QtWidgets.QGraphicsPolygonItem(QtGui.QPolygonF([
            tip,
            QtCore.QPointF(base.x(), base.y() - head_width),
            QtCore.QPointF(base.x(), base.y() + head_width),
        ]))
        arrow.setBrush(QtGui.QBrush(ORDER_ARROW_COLOR))
        arrow.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        arrow.setZValue(9)
        self.scene.addItem(arrow)
        self.spatial_preview_items.append(arrow)

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
        self._stop_scan_animation(remove_lines=True)
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
            self.zoom_mode = "fit"
            self.view.fitInView(self.scene.sceneRect(), QtCore.Qt.KeepAspectRatio)

    def fit_height(self) -> None:
        if self.image_height <= 0:
            return
        self.zoom_mode = "height"
        self.view.resetTransform()
        scale = max(self.view.viewport().height() - 4, 1) / self.image_height
        self.view.scale(scale, scale)

    def fit_width(self) -> None:
        if self.image_width <= 0:
            return
        self.zoom_mode = "width"
        self.view.resetTransform()
        scale = max(self.view.viewport().width() - 4, 1) / self.image_width
        self.view.scale(scale, scale)

    def zoom_100(self) -> None:
        self.zoom_mode = "100"
        self.view.resetTransform()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.zoom_mode == "height":
            self.fit_height()
        elif self.zoom_mode == "width":
            self.fit_width()
        elif self.zoom_mode == "fit":
            self._fit_view()

    # ------------------------------------------------------------------
    def add_guide(
        self,
        start: Optional[QtCore.QPointF] = None,
        end: Optional[QtCore.QPointF] = None,
        rect: Optional[QtCore.QRectF] = None,
        path_points: Optional[List[QtCore.QPointF]] = None,
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
            path=list(path_points or []),
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
        self._active_path_guide = None
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
        record.path = [point + translation for point in record.path]
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
        if len(record.path) >= 2:
            record.line_item.set_points(record.path)
        else:
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
        return bool(self.guides) or self._active_path_guide is not None

    def serialize_guides(self) -> List[LineGuide]:
        if self._active_path_guide is not None:
            return [self._active_path_guide]
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
                    path=[(p.x() / self.image_width, p.y() / self.image_height) for p in record.path],
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
        self.resize(1180, 760)
        self.setMinimumSize(1000, 650)

        # 保存排序线条设置，用于翻页继承
        self._saved_guides = None

        # Reuse the application's shared configuration so the priority label
        # order survives closing and reopening the dialog.
        self._config = getattr(parent, "_config", None)
        if not isinstance(self._config, dict):
            self._config = get_config()

        self.guide_widget = TagSortGuideWidget(self)
        # 连接guides变化信号，实时保存排序线条设置
        self.guide_widget.guides_changed.connect(self._on_guides_changed)
        self.guide_widget.horizontal_scan_spinbox.valueChanged.connect(
            self._on_sort_parameter_changed
        )
        self.guide_widget.vertical_scan_spinbox.valueChanged.connect(
            self._on_sort_parameter_changed
        )

        self.exclude_label_edit = QtWidgets.QLineEdit("other")
        self.exclude_label_edit.setPlaceholderText(self.tr("示例: 标签1, 标签2"))
        self.priority_label_edit = QtWidgets.QLineEdit()
        self.priority_label_edit.setPlaceholderText(
            self.tr("示例: 先检测的标签1, 标签2")
        )
        saved_priority_labels = self._config.get("priority_labels", "")
        if isinstance(saved_priority_labels, (list, tuple)):
            saved_priority_labels = ",".join(str(label) for label in saved_priority_labels)
        self.priority_label_edit.setText(str(saved_priority_labels or ""))
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
        self.priority_label_edit.textChanged.connect(self._on_sort_parameter_changed)
        self.exclude_keep_checkbox.stateChanged.connect(self._on_sort_parameter_changed)
        self.exclude_locked_checkbox.stateChanged.connect(self._on_sort_parameter_changed)
        self.hide_numbers_checkbox.stateChanged.connect(self._on_sort_parameter_changed)


        sort_group = QtWidgets.QGroupBox(self.tr("排序设置"))
        sort_form = QtWidgets.QFormLayout(sort_group)
        sort_form.addRow(self.tr("排除标签"), self.exclude_label_edit)
        sort_form.addRow(self.tr("检测标签顺序"), self.priority_label_edit)
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

        self._log_messages: List[str] = []

        self.run_current_button = QtWidgets.QPushButton(self.tr("对当前页面排序"))
        self.run_range_button = QtWidgets.QPushButton(self.tr("对指定范围排序"))
        self.run_all_button = QtWidgets.QPushButton(self.tr("对全部页面排序"))
        self.log_button = QtWidgets.QPushButton(self.tr("查看日志"))

        action_row = QtWidgets.QHBoxLayout()
        action_row.addWidget(self.run_current_button)
        action_row.addWidget(self.run_range_button)
        action_row.addWidget(self.run_all_button)
        action_row.addStretch(1)
        action_row.addWidget(self.log_button)

        # Match RegionBatchDeleteDialog: the image preview is the main area,
        # and all operation controls live in a compact bottom panel.
        self.preview_scroll_area = QtWidgets.QScrollArea(self)
        self.preview_scroll_area.setWidget(self.guide_widget)
        self.preview_scroll_area.setWidgetResizable(True)
        self.preview_scroll_area.setAlignment(QtCore.Qt.AlignCenter)
        self.preview_scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)

        self.fit_height_button = QtWidgets.QPushButton(self.tr("适应高度"), self)
        self.fit_width_button = QtWidgets.QPushButton(self.tr("适应宽度"), self)
        self.zoom_100_button = QtWidgets.QPushButton(self.tr("100%"), self)
        self.fit_height_button.clicked.connect(self.guide_widget.fit_height)
        self.fit_width_button.clicked.connect(self.guide_widget.fit_width)
        self.zoom_100_button.clicked.connect(self.guide_widget.zoom_100)

        bottom_panel = QtWidgets.QWidget(self)
        bottom_layout = QtWidgets.QVBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(4)
        tool_row = QtWidgets.QHBoxLayout()
        tool_row.setSpacing(6)
        tool_row.addWidget(self.fit_height_button)
        tool_row.addWidget(self.fit_width_button)
        tool_row.addWidget(self.zoom_100_button)
        tool_row.addWidget(self.guide_widget.take_controls_widget())
        bottom_layout.addLayout(tool_row)

        settings_row = QtWidgets.QHBoxLayout()
        settings_row.setSpacing(6)
        settings_row.addWidget(QtWidgets.QLabel(self.tr("排除标签"), self))
        settings_row.addWidget(self.exclude_label_edit, 1)
        settings_row.addWidget(QtWidgets.QLabel(self.tr("检测标签顺序"), self))
        settings_row.addWidget(self.priority_label_edit, 1)
        settings_row.addWidget(self.exclude_keep_checkbox)
        settings_row.addWidget(self.exclude_locked_checkbox)
        settings_row.addWidget(self.hide_numbers_checkbox)
        settings_row.addWidget(QtWidgets.QLabel(self.tr("排序方式"), self))
        settings_row.addWidget(self.spatial_mode_combo)
        settings_row.addWidget(QtWidgets.QLabel(self.tr("范围"), self))
        settings_row.addWidget(self.start_spinbox)
        settings_row.addWidget(self.end_spinbox)
        bottom_layout.addLayout(settings_row)

        action_row.setSpacing(6)
        bottom_layout.addLayout(action_row)
        self.progress_bar.setVisible(False)
        bottom_layout.addWidget(self.progress_bar)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(6)
        main_layout.addWidget(self.preview_scroll_area, 1)
        main_layout.addWidget(bottom_panel, 0)

        self.run_current_button.clicked.connect(lambda: self._emit_request("current"))
        self.run_range_button.clicked.connect(lambda: self._emit_request("range"))
        self.run_all_button.clicked.connect(lambda: self._emit_request("all"))
        self.log_button.clicked.connect(self._show_log_dialog)

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
        # Freehand path reorder is page-local and must never be inherited.
        self._saved_guides = None

    def _on_spatial_mode_changed(self) -> None:
        """当空间排序模式改变时触发"""
        # 更新预览
        self._update_preview_for_current_options()

    def _on_sort_parameter_changed(self) -> None:
        """当排序参数改变时触发"""
        self._save_priority_labels_config()
        # 更新预览
        self._update_preview_for_current_options()

    def _save_priority_labels_config(self) -> None:
        """Persist the normalized priority label order in the shared config."""
        normalized = ",".join(self._collect_priority_labels())
        if self._config.get("priority_labels", "") == normalized:
            return
        self._config["priority_labels"] = normalized
        save_config(self._config)

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
            priority_labels=self._collect_priority_labels(),
            horizontal_scan_distance=float(self.guide_widget.horizontal_scan_spinbox.value()),
            vertical_scan_distance=float(self.guide_widget.vertical_scan_spinbox.value()),
        )

    def _collect_priority_labels(self) -> List[str]:
        text = self.priority_label_edit.text().strip()
        if not text:
            return []
        for sep in (chr(10), chr(9), ";", "；", "、", "，"):
            text = text.replace(sep, ",")
        result = []
        for part in text.split(","):
            label = part.strip()
            if label and label not in result:
                result.append(label)
        return result

    def _emit_request(self, scope: str) -> None:
        options = self._collect_sort_options()
        if options.spatial_mode == "LINE_GUIDES" and not self.guide_widget.has_guides():
            QtWidgets.QMessageBox.information(
                self,
                self.tr("缺少排序线"),
                self.tr("当前排序方式为“使用自定义排序线”，请在右侧视图中至少绘制一条排序线。"),
            )
            return

        self._log_messages.clear()
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
        # Path reorder is a one-shot action for the current page. Never carry
        # its stroke into another page or recreate it as a persistent guide.
        self._saved_guides = None

        if not pixmap or pixmap.isNull():
            self.guide_widget.load_pixmap(None, shapes=[], guides=None)
            return

        prepared_shapes = []
        parent = self.parent()
        for shape in shapes or []:
            # The sorting tool handles text rectangles only. Polygon masks
            # and other shape types are intentionally hidden from this view.
            if not is_sortable_shape(shape):
                continue
            prepared = dict(shape)
            if parent and hasattr(parent, "_get_rgb_by_label"):
                try:
                    prepared["_sort_color"] = parent._get_rgb_by_label(prepared.get("label", ""))
                except Exception:
                    pass
            prepared_shapes.append(prepared)

        # A new page always starts without a reorder path.
        self.guide_widget.load_pixmap(pixmap, shapes=prepared_shapes, guides=None)

        # 更新空间排序预览
        self._update_preview_for_current_options()

    def _update_saved_guides(self) -> None:
        """路径重排只作用于当前页，不保存跨页排序线。"""
        self._saved_guides = None

    def clear_saved_guides(self) -> None:
        """清除保存的排序线条设置"""
        self._saved_guides = None

    def _show_log_dialog(self) -> None:
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(self.tr("排序日志"))
        dialog.resize(720, 420)
        layout = QtWidgets.QVBoxLayout(dialog)
        viewer = QtWidgets.QPlainTextEdit(dialog)
        viewer.setReadOnly(True)
        viewer.setPlainText(chr(10).join(self._log_messages))
        layout.addWidget(viewer, 1)
        close_button = QtWidgets.QPushButton(self.tr("关闭"), dialog)
        close_button.clicked.connect(dialog.accept)
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close_button)
        layout.addLayout(row)
        dialog.exec_()

    def append_log(self, message: str) -> None:
        self._log_messages.append(str(message))
        if len(self._log_messages) > 1000:
            del self._log_messages[:-1000]

    def set_busy(self, busy: bool) -> None:
        for widget in (
            self.run_current_button,
            self.run_range_button,
            self.run_all_button,
            self.exclude_label_edit,
            self.priority_label_edit,
            self.exclude_keep_checkbox,
            self.spatial_mode_combo,
            self.guide_widget,
            self.guide_widget.draw_mode_button,
            self.guide_widget.scan_animation_button,
            self.guide_widget.horizontal_scan_spinbox,
            self.guide_widget.vertical_scan_spinbox,
        ):
            widget.setDisabled(busy)
        self.progress_bar.setVisible(busy)
        if busy:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)

    def set_progress(self, processed: int, total: int) -> None:
        self.progress_bar.setVisible(total > 0)
        if total <= 0:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(min(processed, total))

    def reset(self) -> None:
        self.set_busy(False)
        self._log_messages.clear()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
