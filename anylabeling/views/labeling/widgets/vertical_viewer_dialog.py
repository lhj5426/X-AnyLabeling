from PyQt5 import QtCore, QtGui, QtWidgets
import os
import json

from ..label_file import LabelFile
from ..shape import Shape

# Fixed base width for the scene in vertical mode.
SCENE_BASE_WIDTH = 1000

# 顶点大小
VERTEX_SIZE = 8

class ImageLoaderSignals(QtCore.QObject):
    loaded = QtCore.pyqtSignal(str, QtGui.QImage, float, list, float) # path, image, aspect_ratio, shapes, scale_factor

class ImageLoader(QtCore.QRunnable):
    def __init__(self, path, target_width):
        super().__init__()
        self.path = path
        self.target_width = target_width
        self.signals = ImageLoaderSignals()

    def run(self):
        try:
            reader = QtGui.QImageReader(self.path)
            reader.setAutoTransform(True)
            
            orig_size = reader.size()
            scale_factor = 1.0
            shapes = []
            
            if orig_size.isValid():
                aspect_ratio = orig_size.width() / orig_size.height()
                target_height = int(self.target_width / aspect_ratio)
                reader.setScaledSize(QtCore.QSize(self.target_width, target_height))
                scale_factor = self.target_width / orig_size.width()
                
                image = reader.read()
                
                # Load shapes from JSON if exists
                json_path = os.path.splitext(self.path)[0] + ".json"
                if os.path.exists(json_path):
                    try:
                        label_file = LabelFile(json_path)
                        shapes = label_file.shapes
                    except Exception:
                        pass
                
                if not image.isNull():
                    self.signals.loaded.emit(self.path, image, aspect_ratio, shapes, scale_factor)
            else:
                image = reader.read()
                if not image.isNull():
                    aspect_ratio = image.width() / image.height()
                    self.signals.loaded.emit(self.path, image, aspect_ratio, [], 1.0)
        except Exception:
            pass

class ThumbnailLoader(QtCore.QRunnable):
    def __init__(self, path, target_size):
        super().__init__()
        self.path = path
        self.target_size = target_size
        self.signals = ImageLoaderSignals()

    def run(self):
        try:
            reader = QtGui.QImageReader(self.path)
            reader.setAutoTransform(True)
            
            orig_size = reader.size()
            if orig_size.isValid():
                aspect_ratio = orig_size.width() / orig_size.height()
                if aspect_ratio > 1:
                    w = self.target_size
                    h = int(self.target_size / aspect_ratio)
                else:
                    h = self.target_size
                    w = int(self.target_size * aspect_ratio)
                
                # Ensure minimum size of 1 to avoid errors
                w = max(1, w)
                h = max(1, h)
                reader.setScaledSize(QtCore.QSize(w, h))
            
            image = reader.read()
            if not image.isNull():
                self.signals.loaded.emit(self.path, image, 1.0, [], 1.0)
        except Exception:
            pass

class DividerItem(QtWidgets.QGraphicsItem):
    def __init__(self, width, index, total, parent=None):
        super().__init__(parent)
        self.width = width
        self.text_str = f" {index}/{total} "
        self.font = QtGui.QFont("Arial", 10)
        
        fm = QtGui.QFontMetrics(self.font)
        self.text_width = fm.horizontalAdvance(self.text_str)
        self.text_height = fm.height()
        
        # 背景框（紧凑）
        self.bg_rect = QtCore.QRectF(
            -self.text_width / 2 - 4,
            -self.text_height / 2,
            self.text_width + 8,
            self.text_height
        )

    def boundingRect(self):
        return QtCore.QRectF(-50000, -10, 100000, 20)

    def paint(self, painter, option, widget):
        scale = painter.transform().m11()
        if scale == 0: scale = 1.0
        inv_scale = 1.0 / scale
        
        # 计算文字区域在场景中的宽度（用于断开线条）
        text_half_width = (self.text_width / 2 + 6) * inv_scale
        center_x = self.width / 2
        
        # 画分隔线（在文字两侧，不穿过文字）
        pen = QtGui.QPen(QtGui.QColor("#555555"))
        pen.setWidth(1)
        pen.setCosmetic(True) 
        painter.setPen(pen)
        painter.drawLine(-50000, 0, int(center_x - text_half_width), 0)
        painter.drawLine(int(center_x + text_half_width), 0, 50000, 0)
        
        painter.save()
        painter.translate(self.width / 2, 0)
        painter.scale(inv_scale, inv_scale)
        
        # 画背景框
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QBrush(QtGui.QColor("#1e1e1e")))
        painter.drawRect(self.bg_rect)
        
        # 画文字
        painter.setPen(QtGui.QPen(QtGui.QColor("#aaaaaa")))
        painter.setFont(self.font)
        painter.drawText(self.bg_rect, QtCore.Qt.AlignCenter, self.text_str)
        
        painter.restore()

class ThumbnailDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.padding = 5
        self.text_height = 20
        self.font = QtGui.QFont("Arial", 9)
        self.font_metrics = QtGui.QFontMetrics(self.font)

    def paint(self, painter, option, index):
        painter.save()
        
        rect = option.rect
        
        # Draw Selection
        if option.state & QtWidgets.QStyle.State_Selected:
            painter.fillRect(rect, QtGui.QColor("#444444"))
            pen = QtGui.QPen(QtGui.QColor("#007acc"))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(rect.adjusted(1,1,-1,-1))
        
        # Data
        text = index.data(QtCore.Qt.DisplayRole)
        icon = index.data(QtCore.Qt.DecorationRole)
        
        # Layout
        # Text at top
        text_rect = QtCore.QRect(rect.left() + self.padding, rect.top() + self.padding, 
                                 rect.width() - 2*self.padding, self.text_height)
        
        # Image below
        img_rect = QtCore.QRect(rect.left() + self.padding, text_rect.bottom() + self.padding,
                                rect.width() - 2*self.padding, rect.height() - self.text_height - 2*self.padding)
        
        # Draw Text
        painter.setPen(QtGui.QColor("#eeeeee"))
        painter.setFont(self.font)
        elided_text = self.font_metrics.elidedText(text, QtCore.Qt.ElideRight, text_rect.width())
        painter.drawText(text_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, elided_text)
        
        # Draw Image
        if icon and not icon.isNull():
            # Scale pixmap to fit img_rect while keeping aspect ratio
            pixmap = icon.pixmap(img_rect.size())
            scaled_pixmap = pixmap.scaled(img_rect.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            
            # Center image
            x = img_rect.left() + (img_rect.width() - scaled_pixmap.width()) / 2
            y = img_rect.top() + (img_rect.height() - scaled_pixmap.height()) / 2
            
            painter.drawPixmap(int(x), int(y), scaled_pixmap)
            
        painter.restore()

class VerticalThumbnailItem(QtWidgets.QGraphicsPixmapItem):
    def __init__(self, path, width, labeling_widget=None, parent=None):
        super().__init__(parent)
        self.path = path
        self.base_width = width
        self.labeling_widget = labeling_widget
        self.loaded = False
        self.loading = False
        self.aspect_ratio = 0.75 
        self.setShapeMode(QtWidgets.QGraphicsPixmapItem.BoundingRectShape)
        self.setTransformationMode(QtCore.Qt.SmoothTransformation)
        self.shapes = []
        self.scale_factor = 1.0
        self.show_annotations = False # Default Closed
        self.fill_annotations = False
        self.update_placeholder()
        
    def update_placeholder(self):
        h = int(self.base_width / self.aspect_ratio)
        pix = QtGui.QPixmap(self.base_width, h)
        pix.fill(QtGui.QColor("#2b2b2b")) 
        self.setPixmap(pix)

    def set_image(self, image, ratio):
        self.aspect_ratio = ratio
        self.setPixmap(QtGui.QPixmap.fromImage(image))
        self.loaded = True
        self.loading = False

    def set_shapes(self, shapes, scale_factor):
        self.shapes = shapes
        self.scale_factor = scale_factor
        self.update()

    def get_height(self):
        return self.pixmap().height()

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        if self.shapes and self.show_annotations:
            painter.save()
            painter.scale(self.scale_factor, self.scale_factor)
            
            for shape in self.shapes:
                if not shape.points:
                    continue
                
                # 1. Get Color
                color = QtGui.QColor(0, 255, 0) # Default Green
                if self.labeling_widget:
                    try:
                        # Try to get color from main widget
                        if shape.label:
                            rgb = self.labeling_widget._get_rgb_by_label(shape.label)
                            if rgb:
                                color = QtGui.QColor(*rgb)
                    except Exception:
                        pass
                
                # 2. Setup Pen and Brush
                pen = QtGui.QPen(color)
                pen.setWidth(2)
                pen.setCosmetic(True) # Width remains constant regardless of scale
                painter.setPen(pen)
                
                # Fill color
                if self.fill_annotations:
                    fill_color = QtGui.QColor(color)
                    fill_color.setAlpha(128) # 50% opacity
                    painter.setBrush(QtGui.QBrush(fill_color))
                else:
                    painter.setBrush(QtCore.Qt.NoBrush)
                
                # 3. Create Path
                if shape.shape_type == "point" and len(shape.points) > 0:
                    # Special handling for points: draw a small circle
                    point_radius = 4
                    path = QtGui.QPainterPath()
                    path.addEllipse(shape.points[0], point_radius, point_radius)
                    # Ensure points are filled so they are visible
                    painter.setBrush(QtGui.QBrush(color))
                else:
                    try:
                        path = shape.make_path()
                    except AttributeError:
                        path = QtGui.QPainterPath()
                        if len(shape.points) > 0:
                            path.moveTo(shape.points[0])
                            for p in shape.points[1:]:
                                path.lineTo(p)
                    
                    if shape.shape_type in ["polygon", "rectangle", "rotation", "rotation3", "rectangle3"]:
                        path.closeSubpath()
                
                # 4. Draw Path (No vertices)
                painter.drawPath(path)
                
            painter.restore()

class CustomGraphicsView(QtWidgets.QGraphicsView):
    ctrlWheelZoomIn = QtCore.pyqtSignal()
    ctrlWheelZoomOut = QtCore.pyqtSignal()
    
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
    
    def wheelEvent(self, event):
        if event.modifiers() & QtCore.Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta == 0:
                delta = event.pixelDelta().y()
            
            if delta > 0:
                self.ctrlWheelZoomIn.emit()
            elif delta < 0:
                self.ctrlWheelZoomOut.emit()
            event.accept()
            return
        super().wheelEvent(event)

class VerticalViewerDialog(QtWidgets.QDialog):
    image_switched = QtCore.pyqtSignal(str)
    open_horizontal_viewer = QtCore.pyqtSignal(str)

    def __init__(self, image_list, current_filename=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("垂直滚动看图")
        self.resize(1200, 800)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowMinMaxButtonsHint | QtCore.Qt.WindowCloseButtonHint)
        
        self.image_list = image_list
        self.current_filename = current_filename
        self.labeling_widget = parent # Store parent (LabelingWidget) reference
        self.items_map = {} 
        self.items_list = [] 
        self.dividers_list = []
        layout = QtWidgets.QVBoxLayout(self) # Assuming 'layout' was missing its definition
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Thumbnail List
        self.thumbnail_list = QtWidgets.QListWidget()
        self.thumbnail_list.setFixedWidth(115) # Fixed width, no resizing
        self.thumbnail_list.setIconSize(QtCore.QSize(100, 100))
        self.thumbnail_list.setSpacing(5)
        self.thumbnail_list.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                border: none;
                outline: none;
            }
            /* Scrollbar styling */
            QScrollBar:vertical {
                border: none;
                background: #2b2b2b;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #666666;
                min-height: 20px;
                border-radius: 4px;
                margin: 2px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        self.thumbnail_list.setItemDelegate(ThumbnailDelegate(self.thumbnail_list))
        self.thumbnail_list.itemClicked.connect(self.on_thumbnail_clicked)
        self.thumbnail_list.setVisible(False) # Default hidden
        
        # Main content layout
        main_h_layout = QtWidgets.QHBoxLayout()
        main_h_layout.addWidget(self.thumbnail_list)

        # Graphics View
        self.scene = QtWidgets.QGraphicsScene()
        self.scene.setBackgroundBrush(QtGui.QBrush(QtGui.QColor("#1e1e1e")))
        
        self.view = CustomGraphicsView(self.scene)
        self.view.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)
        self.view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.view.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.view.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        self.view.setViewportUpdateMode(QtWidgets.QGraphicsView.SmartViewportUpdate)
        self.view.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.view.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.view.setOptimizationFlags(QtWidgets.QGraphicsView.DontSavePainterState)
        
        self.view.ctrlWheelZoomIn.connect(self.zoom_in)
        self.view.ctrlWheelZoomOut.connect(self.zoom_out)
        
        self.view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.show_context_menu)
        
        main_h_layout.addWidget(self.view)
        layout.addLayout(main_h_layout) # Add the horizontal layout to the main vertical layout
        
        self.view.verticalScrollBar().valueChanged.connect(self.on_scroll)
        self.view.installEventFilter(self)
        
        self.populated = False
        self.closing = False
        self._need_initial_center = False  # 标记是否需要初始居中

        # Initialize state variables
        self.fit_width_mode = False
        self.fit_height_mode = True
        self.view_scale = 1.0
        self.thumbnails_visible = False
        self.show_annotations = False
        self.fill_annotations = False
        self.sync_scroll_enabled = False
        self.show_dividers = True  # 显示分隔符

        # Thread pool for loading images
        self.thread_pool = QtCore.QThreadPool()
        self.thread_pool.setMaxThreadCount(4)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.populated:
            QtCore.QTimer.singleShot(50, self.populate_scene)
            self.populated = True
        QtCore.QTimer.singleShot(100, self.view.setFocus)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit_width_mode or self.fit_height_mode:
            QtCore.QTimer.singleShot(0, self.update_view_transform)

    def eventFilter(self, obj, event):
        if obj == self.view:
            # 处理键盘事件 - A/D 翻页
            if event.type() == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_D:
                    self.go_to_next_image()
                    event.accept()
                    return True
                elif event.key() == QtCore.Qt.Key_A:
                    self.go_to_prev_image()
                    event.accept()
                    return True
            elif event.type() == QtCore.QEvent.Resize:
                if self.fit_width_mode or self.fit_height_mode:
                    self.update_view_transform()
                QtCore.QTimer.singleShot(100, self.check_visible_items)
            elif event.type() == QtCore.QEvent.MouseButtonPress:
                self.view.setFocus()
        return super().eventFilter(obj, event)

    def populate_scene(self):
        self.scene.clear()
        self.thumbnail_list.clear()
        self.items_map = {}
        self.items_list = []
        self.dividers_list = []
        
        total = len(self.image_list)
        
        # Populate thumbnails
        for i, path in enumerate(self.image_list):
            filename = os.path.basename(path)
            item = QtWidgets.QListWidgetItem(f"{i+1} {filename}")
            item.setData(QtCore.Qt.UserRole, path)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.thumbnail_list.addItem(item)
            
            loader = ThumbnailLoader(path, 100)
            # Correctly handle all signal arguments to prevent 'item' from being overwritten by 'shapes' list
            # Signal: loaded(str, QImage, float, list, float) -> p, img, r, s, sc
            loader.signals.loaded.connect(lambda p, img, r, s, sc, it=item: self.on_thumbnail_loaded(p, img, it))
            self.thread_pool.start(loader)
        
        self._populate_batch = 0
        self._populate_total_batches = total
        QtCore.QTimer.singleShot(0, self._populate_batch_items)
        
    def _populate_batch_items(self):
        if self.closing: return
        
        batch_size = 50
        start_idx = self._populate_batch
        end_idx = min(start_idx + batch_size, self._populate_total_batches)
        
        y_offset = 0
        gap = 4 if self.show_dividers else 0  # 图片与分隔符之间的间距
        divider_h = 12  # 分隔符本身的高度
        total = len(self.image_list)
        
        if start_idx > 0:
            for i in range(start_idx):
                item = self.items_list[i]
                if self.show_dividers:
                    y_offset += gap + divider_h + gap  # 间距 + 分隔符 + 间距
                y_offset += item.get_height()
        
        for i in range(start_idx, end_idx):
            path = self.image_list[i]
            
            if i > 0:
                y_offset += gap  # 上一张图片底部到分隔符的间距
                divider = DividerItem(SCENE_BASE_WIDTH, i + 1, total)
                divider.setPos(0, y_offset + divider_h / 2)  # 分隔符居中
                divider.setVisible(self.show_dividers)
                self.scene.addItem(divider)
                self.dividers_list.append(divider)
                if self.show_dividers:
                    y_offset += divider_h  # 分隔符高度
                y_offset += gap  # 分隔符到下一张图片顶部的间距
            
            # Pass labeling_widget to item for color retrieval
            item = VerticalThumbnailItem(path, SCENE_BASE_WIDTH, labeling_widget=self.labeling_widget)
            item.show_annotations = self.show_annotations
            item.fill_annotations = self.fill_annotations
            item.setPos(0, y_offset)
            self.scene.addItem(item)
            self.items_map[path] = item
            self.items_list.append(item)
            
            y_offset += item.get_height()
        
        if end_idx == self._populate_total_batches:
            current_y = 0
            for i, item in enumerate(self.items_list):
                if i > 0 and self.show_dividers:
                    current_y += gap + divider_h + gap  # 间距 + 分隔符 + 间距
                current_y += item.get_height()
            
            self.scene.setSceneRect(0, 0, SCENE_BASE_WIDTH, current_y)
            
            # 标记需要初始居中
            self._need_initial_center = True
            
            # 先居中到当前图片（使用占位符位置）
            if self.current_filename and self.current_filename in self.items_map:
                self._center_on_current()
            
            # 优先加载当前图片
            if self.current_filename and self.current_filename in self.items_map:
                current_item = self.items_map[self.current_filename]
                if not current_item.loaded and not current_item.loading:
                    current_item.loading = True
                    loader = ImageLoader(current_item.path, SCENE_BASE_WIDTH)
                    loader.signals.loaded.connect(self.on_image_loaded)
                    self.thread_pool.start(loader)
            
            # 延迟检查可见项（会加载可见区域的图片）
            QtCore.QTimer.singleShot(150, self.check_visible_items)
        else:
            self._populate_batch = end_idx
            QtCore.QTimer.singleShot(0, self._populate_batch_items)

    def on_thumbnail_loaded(self, path, image, item):
        if self.closing: return
        try:
             pixmap = QtGui.QPixmap.fromImage(image)
             if isinstance(item, QtWidgets.QListWidgetItem):
                 item.setIcon(QtGui.QIcon(pixmap))
                 
                 # Calculate size hint for variable height
                 # Target width approx 100 (tight fit for 100px icons)
                 target_width = 100
                 if pixmap.width() > 0:
                     aspect = pixmap.width() / pixmap.height()
                     target_height = int(target_width / aspect)
                 else:
                     target_height = 130
                     
                 # Text (20) + Padding (5*3) + Image
                 total_height = 20 + 15 + target_height
                 item.setSizeHint(QtCore.QSize(target_width, total_height))
             
        except RuntimeError:
             pass

    def _center_on_item(self, item):
        """将指定图片的中心点对齐到视口中心"""
        item_center_x = item.pos().x() + item.boundingRect().width() / 2
        item_center_y = item.pos().y() + item.boundingRect().height() / 2
        center_point = QtCore.QPointF(item_center_x, item_center_y)
        self.view.centerOn(center_point)

    def _apply_initial_transform(self):
        """初始化时应用缩放变换，不进行居中操作"""
        viewport_width = self.view.viewport().width()
        viewport_height = self.view.viewport().height()
        if viewport_width < 10:
            return
        
        if self.fit_width_mode:
            self.view_scale = viewport_width / SCENE_BASE_WIDTH
        elif self.fit_height_mode:
            # 使用当前文件计算缩放比例
            if self.current_filename and self.current_filename in self.items_map:
                current_item = self.items_map[self.current_filename]
                target_scale = viewport_height / current_item.get_height()
                self.view_scale = target_scale
            else:
                self.view_scale = 1.0
        
        transform = QtGui.QTransform()
        transform.scale(self.view_scale, self.view_scale)
        self.view.setTransform(transform)

    def jump_to_image(self, filename):
        """Jump to a specific image, refreshing it if necessary."""
        self.current_filename = filename
        if filename in self.items_map:
            view_item = self.items_map[filename]
            self._center_on_item(view_item)
            
            # Force reload of this item to update annotations/image
            view_item.loaded = False
            view_item.loading = False
            self.check_visible_items()
            self.on_scroll()
        else:
            # If item not found, reload entire scene
            self.populate_scene()

    def on_thumbnail_clicked(self, item):
        path = item.data(QtCore.Qt.UserRole)
        if path in self.items_map:
            # 更新 current_filename，这样 relayout_items 会保持这个图片的位置
            self.current_filename = path
            view_item = self.items_map[path]
            self._center_on_item(view_item)
            idx = self.thumbnail_list.row(item)
            self.setWindowTitle(f"垂直滚动看图 - {idx + 1}/{len(self.image_list)}")

    def relayout_items(self):
        # 记录当前图片的旧位置
        old_current_y = None
        if self.current_filename and self.current_filename in self.items_map:
            current_item = self.items_map[self.current_filename]
            old_current_y = current_item.pos().y()
        
        y_offset = 0
        gap = 4 if self.show_dividers else 0  # 图片与分隔符之间的间距
        divider_height = 12  # 分隔符本身的高度
        divider_idx = 0
        for i, item in enumerate(self.items_list):
            if i > 0 and divider_idx < len(self.dividers_list):
                y_offset += gap  # 上一张图片底部到分隔符的间距
                divider = self.dividers_list[divider_idx]
                divider.setPos(0, y_offset + divider_height / 2)  # 分隔符居中
                if self.show_dividers:
                    y_offset += divider_height  # 分隔符高度
                y_offset += gap  # 分隔符到下一张图片顶部的间距
                divider_idx += 1
            item.setPos(0, y_offset)
            y_offset += item.get_height()
        self.scene.setSceneRect(0, 0, SCENE_BASE_WIDTH, y_offset)
        
        # 如果当前图片位置变化了，调整滚动位置以保持视图稳定
        if old_current_y is not None and self.current_filename in self.items_map:
            current_item = self.items_map[self.current_filename]
            new_current_y = current_item.pos().y()
            delta_y = new_current_y - old_current_y
            if abs(delta_y) > 1:
                vbar = self.view.verticalScrollBar()
                vbar.setValue(int(vbar.value() + delta_y * self.view_scale))

    def update_view_transform(self):
        viewport_width = self.view.viewport().width()
        viewport_height = self.view.viewport().height()
        if viewport_width < 10: return
        
        center_item = None
        if self.fit_width_mode:
            self.view_scale = viewport_width / SCENE_BASE_WIDTH
        elif self.fit_height_mode:
            # 使用视口中心的图片来计算缩放比例
            center_item = self.get_center_item()
            if center_item:
                target_scale = viewport_height / center_item.get_height()
                self.view_scale = target_scale
            else:
                self.view_scale = 1.0
        
        transform = QtGui.QTransform()
        transform.scale(self.view_scale, self.view_scale)
        self.view.setTransform(transform)
        
        if self.fit_height_mode and center_item:
            self._center_on_item(center_item)

    def get_center_item(self):
        viewport_center_y = self.view.viewport().height() / 2
        scene_center_pt = self.view.mapToScene(0, int(viewport_center_y))
        scene_y = scene_center_pt.y()
        
        closest_idx = -1
        closest_dist = float('inf')
        
        for i, item in enumerate(self.items_list):
            item_center = item.pos().y() + item.get_height() / 2
            dist = abs(item_center - scene_y)
            if dist < closest_dist:
                closest_dist = dist
                closest_idx = i
            if dist > closest_dist and closest_idx != -1:
                break
        
        if closest_idx != -1:
            return self.items_list[closest_idx]
        return None

    def on_scroll(self):
        if self.closing: return
        self.check_visible_items()
        center_item = self.get_center_item()
        if center_item:
             idx = self.items_list.index(center_item)
             self.setWindowTitle(f"垂直滚动看图 - {idx + 1}/{len(self.image_list)}")
             
             if self.thumbnails_visible:
                 # 只有当选中项变化时才更新
                 current_row = self.thumbnail_list.currentRow()
                 if current_row != idx:
                     self.thumbnail_list.blockSignals(True)
                     self.thumbnail_list.setCurrentRow(idx)
                     # 使用 scrollToItem 让选中项可见
                     item = self.thumbnail_list.item(idx)
                     if item:
                         self.thumbnail_list.scrollToItem(item, QtWidgets.QAbstractItemView.PositionAtCenter)
                     self.thumbnail_list.blockSignals(False)
                 self.thumbnail_list.blockSignals(False)

    def check_visible_items(self):
        if self.closing: return
        viewport_rect = self.view.viewport().rect()
        scene_rect = self.view.mapToScene(viewport_rect).boundingRect()
        
        # 找到当前可见的图片索引范围
        visible_indices = []
        for i, item in enumerate(self.items_list):
            try:
                if item.sceneBoundingRect().intersects(scene_rect):
                    visible_indices.append(i)
                    if not item.loaded and not item.loading:
                        item.loading = True
                        loader = ImageLoader(item.path, SCENE_BASE_WIDTH)
                        loader.signals.loaded.connect(self.on_image_loaded)
                        self.thread_pool.start(loader)
            except RuntimeError:
                continue
        
        # 预加载前后各5张图片
        if visible_indices:
            preload_count = 5
            min_idx = max(0, min(visible_indices) - preload_count)
            max_idx = min(len(self.items_list) - 1, max(visible_indices) + preload_count)
            
            for i in range(min_idx, max_idx + 1):
                if i not in visible_indices:
                    item = self.items_list[i]
                    try:
                        if not item.loaded and not item.loading:
                            item.loading = True
                            loader = ImageLoader(item.path, SCENE_BASE_WIDTH)
                            loader.signals.loaded.connect(self.on_image_loaded)
                            self.thread_pool.start(loader)
                    except RuntimeError:
                        continue

    def on_image_loaded(self, path, image, ratio, shapes=[], scale_factor=1.0):
        if self.closing: return
        if path in self.items_map:
            item = self.items_map[path]
            try:
                item.set_image(image, ratio)
                item.set_shapes(shapes, scale_factor)
                # relayout_items 会自动调整滚动位置以保持当前图片稳定
                self.relayout_items()
                
                # 当前图片加载完成后，应用自适应高度缩放
                if path == self.current_filename:
                    if getattr(self, '_need_initial_center', False):
                        self._need_initial_center = False
                    if self.fit_height_mode:
                        self._apply_initial_transform()
                        self._center_on_current()
            except RuntimeError:
                pass

    def show_context_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        
        zoom_in_action = menu.addAction("放大 (+)")
        zoom_in_action.triggered.connect(self.zoom_in)
        zoom_out_action = menu.addAction("缩小 (-)")
        zoom_out_action.triggered.connect(self.zoom_out)
        actual_size_action = menu.addAction("实际尺寸 (100%)")
        actual_size_action.triggered.connect(self.set_actual_size)
        
        menu.addSeparator()
        fit_width_action = menu.addAction("适应宽度")
        fit_width_action.setCheckable(True)
        fit_width_action.setChecked(self.fit_width_mode)
        fit_width_action.triggered.connect(self.set_fit_width)
        
        fit_height_action = menu.addAction("适应高度")
        fit_height_action.setCheckable(True)
        fit_height_action.setChecked(self.fit_height_mode)
        fit_height_action.triggered.connect(self.set_fit_height)
        
        menu.addSeparator()
        thumb_action = menu.addAction("显示缩略图")
        thumb_action.setCheckable(True)
        thumb_action.setChecked(self.thumbnails_visible)
        thumb_action.triggered.connect(self.toggle_thumbnails)
        
        menu.addSeparator()
        
        show_anno_action = menu.addAction("显示标注")
        show_anno_action.setCheckable(True)
        show_anno_action.setChecked(self.show_annotations)
        show_anno_action.triggered.connect(self.toggle_show_annotations)
        
        fill_anno_action = menu.addAction("填充标注")
        fill_anno_action.setCheckable(True)
        fill_anno_action.setChecked(self.fill_annotations)
        fill_anno_action.triggered.connect(self.toggle_fill_annotations)
        
        menu.addSeparator()
        
        sync_action = menu.addAction("同步滚动")
        sync_action.setCheckable(True)
        sync_action.setChecked(self.sync_scroll_enabled)
        sync_action.triggered.connect(self.toggle_sync_scroll)
        
        menu.addSeparator()
        
        divider_action = menu.addAction("显示分隔符")
        divider_action.setCheckable(True)
        divider_action.setChecked(self.show_dividers)
        divider_action.triggered.connect(self.toggle_dividers)
        
        menu.addSeparator()
        refresh_action = menu.addAction("刷新")
        refresh_action.triggered.connect(self.reload_scene)

        menu.addSeparator()
        open_horiz_action = menu.addAction("用横向滚动看图打开")
        open_horiz_action.triggered.connect(self.trigger_open_horizontal_viewer)
        
        item = self.view.itemAt(pos)
        if isinstance(item, VerticalThumbnailItem):
            menu.addSeparator()
            action = menu.addAction("切换到此图片")
            action.triggered.connect(lambda: self.switch_to_image(item.path))
            
        menu.exec_(self.view.mapToGlobal(pos))

    def update_image_list(self, new_image_list, current_filename=None):
        """更新图片列表（当主界面打开新文件夹时调用）"""
        self.image_list = new_image_list
        # 如果提供了current_filename则使用，否则重置到第一张
        if current_filename:
            self.current_filename = current_filename
        elif new_image_list:
            self.current_filename = new_image_list[0]
        else:
            self.current_filename = None
        self.reload_scene()
    
    def reload_scene(self):
        # 不再覆盖current_filename，由update_image_list设置
        self.populate_scene()

    def _center_on_current(self):
        """居中到当前文件，将图片中心点对齐到视口中心"""
        if self.current_filename and self.current_filename in self.items_map:
            item = self.items_map[self.current_filename]
            self._center_on_item(item)

    def toggle_sync_scroll(self):
        self.sync_scroll_enabled = not self.sync_scroll_enabled
    
    def toggle_dividers(self):
        """切换分隔符显示/隐藏"""
        self.show_dividers = not self.show_dividers
        # 更新所有分隔符的可见性
        for divider in self.dividers_list:
            divider.setVisible(self.show_dividers)
        # 重新布局以调整间距
        self.relayout_items()

    def toggle_thumbnails(self):
        self.thumbnails_visible = not self.thumbnails_visible
        self.thumbnail_list.setVisible(self.thumbnails_visible)
        if self.thumbnails_visible:
            # Sync selection
            center_item = self.get_center_item()
            if center_item:
                 idx = self.items_list.index(center_item)
                 self.thumbnail_list.blockSignals(True)
                 self.thumbnail_list.setCurrentRow(idx)
                 # 使用 scrollToItem 让选中项居中显示
                 item = self.thumbnail_list.item(idx)
                 if item:
                     self.thumbnail_list.scrollToItem(item, QtWidgets.QAbstractItemView.PositionAtCenter)
                 self.thumbnail_list.blockSignals(False)

    def toggle_show_annotations(self):
        self.show_annotations = not self.show_annotations
        for item in self.items_list:
            item.show_annotations = self.show_annotations
            item.update()
            
    def toggle_fill_annotations(self):
        self.fill_annotations = not self.fill_annotations
        for item in self.items_list:
            item.fill_annotations = self.fill_annotations
            item.update()

    def switch_to_image(self, path):
        self.image_switched.emit(path)
        # 切换后自动最小化窗口，方便在主界面操作
        self.showMinimized()

    def trigger_open_horizontal_viewer(self):
        center_item = self.get_center_item()
        if center_item:
            self.open_horizontal_viewer.emit(center_item.path)
        elif self.current_filename:
            self.open_horizontal_viewer.emit(self.current_filename)
        else:
            if self.image_list:
                self.open_horizontal_viewer.emit(self.image_list[0])

    def set_fit_width(self):
        self.fit_width_mode = True
        self.fit_height_mode = False
        self.update_view_transform()
        self.check_visible_items()

    def set_fit_height(self):
        self.fit_width_mode = False
        self.fit_height_mode = True
        self.update_view_transform()
        self.check_visible_items()

    def set_actual_size(self):
        self.fit_width_mode = False
        self.fit_height_mode = False
        center_item = self.get_center_item()
        if center_item:
             reader = QtGui.QImageReader(center_item.path)
             s = reader.size()
             if s.isValid():
                 scale = s.width() / SCENE_BASE_WIDTH
                 self.view_scale = scale
        self.update_view_transform()
        self.check_visible_items()

    def zoom_in(self):
        self.fit_width_mode = False
        self.fit_height_mode = False
        self.view_scale *= 1.2
        self.update_view_transform()
        self.check_visible_items()

    def zoom_out(self):
        self.fit_width_mode = False
        self.fit_height_mode = False
        self.view_scale /= 1.2
        self.update_view_transform()
        self.check_visible_items()

    def _ensure_item_loaded(self, item):
        """确保图片项已加载，如果未加载则立即加载"""
        if item and not item.loaded and not item.loading:
            item.loading = True
            loader = ImageLoader(item.path, SCENE_BASE_WIDTH)
            loader.signals.loaded.connect(self.on_image_loaded)
            self.thread_pool.start(loader)

    def go_to_next_image(self):
        """翻到下一张图片"""
        if self.sync_scroll_enabled:
            # 同步模式：通知主画布切换
            center_item = self.get_center_item()
            if center_item:
                current_idx = self.items_list.index(center_item)
                if current_idx + 1 < len(self.items_list):
                    next_path = self.items_list[current_idx + 1].path
                    self.image_switched.emit(next_path)
        else:
            # 非同步模式：自己翻页
            center_item = self.get_center_item()
            if center_item:
                current_idx = self.items_list.index(center_item)
                if current_idx + 1 < len(self.items_list):
                    next_item = self.items_list[current_idx + 1]
                    # 预加载下一张和下下张图片
                    self._ensure_item_loaded(next_item)
                    if current_idx + 2 < len(self.items_list):
                        self._ensure_item_loaded(self.items_list[current_idx + 2])
                    self._center_on_item(next_item)
                    self.on_scroll()

    def go_to_prev_image(self):
        """翻到上一张图片"""
        if self.sync_scroll_enabled:
            # 同步模式：通知主画布切换
            center_item = self.get_center_item()
            if center_item:
                current_idx = self.items_list.index(center_item)
                if current_idx - 1 >= 0:
                    prev_path = self.items_list[current_idx - 1].path
                    self.image_switched.emit(prev_path)
        else:
            # 非同步模式：自己翻页
            center_item = self.get_center_item()
            if center_item:
                current_idx = self.items_list.index(center_item)
                if current_idx - 1 >= 0:
                    prev_item = self.items_list[current_idx - 1]
                    # 预加载上一张和上上张图片
                    self._ensure_item_loaded(prev_item)
                    if current_idx - 2 >= 0:
                        self._ensure_item_loaded(self.items_list[current_idx - 2])
                    self._center_on_item(prev_item)
                    self.on_scroll()

    def event(self, event):
        """重写event方法，拦截ShortcutOverride事件以阻止主窗口快捷键"""
        if event.type() == QtCore.QEvent.ShortcutOverride:
            if event.key() in (QtCore.Qt.Key_A, QtCore.Qt.Key_D):
                event.accept()
                return True
        return super().event(event)

    def keyPressEvent(self, event):
        """处理键盘事件，支持 A/D 翻页"""
        if event.key() == QtCore.Qt.Key_D:
            self.go_to_next_image()
            event.accept()
        elif event.key() == QtCore.Qt.Key_A:
            self.go_to_prev_image()
            event.accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.closing = True
        self.thread_pool.waitForDone(1000)
        self.items_map.clear()
        self.items_list.clear()
        self.dividers_list.clear()
        super().closeEvent(event)