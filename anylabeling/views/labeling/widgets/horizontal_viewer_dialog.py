from PyQt5 import QtCore, QtGui, QtWidgets
import os

from ..label_file import LabelFile
from ..shape import Shape

# Fixed base height for the scene. 
SCENE_BASE_HEIGHT = 1000

class ImageLoaderSignals(QtCore.QObject):
    loaded = QtCore.pyqtSignal(str, QtGui.QImage, float, list, float) # path, image, aspect_ratio, shapes, scale_factor

class ImageLoader(QtCore.QRunnable):
    def __init__(self, path, target_height):
        super().__init__()
        self.path = path
        self.target_height = target_height
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
                target_width = int(self.target_height * aspect_ratio)
                reader.setScaledSize(QtCore.QSize(target_width, self.target_height))
                scale_factor = self.target_height / orig_size.height()
                
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
                reader.setScaledSize(QtCore.QSize(w, h))
            
            image = reader.read()
            if not image.isNull():
                self.signals.loaded.emit(self.path, image, 1.0, [], 1.0)
        except Exception:
            pass

class HorizontalThumbnailItem(QtWidgets.QGraphicsPixmapItem):
    def __init__(self, path, height, labeling_widget=None, parent=None):
        super().__init__(parent)
        self.path = path
        self.base_height = height
        self.labeling_widget = labeling_widget
        self.loaded = False
        self.loading = False
        self.aspect_ratio = 0.75 
        self.selected = False
        self.setShapeMode(QtWidgets.QGraphicsPixmapItem.BoundingRectShape)
        self.setTransformationMode(QtCore.Qt.SmoothTransformation)
        self.shapes = []
        self.scale_factor = 1.0
        self.show_annotations = False
        self.fill_annotations = False
        self.update_placeholder()
        
    def update_placeholder(self):
        w = int(self.base_height * self.aspect_ratio)
        pix = QtGui.QPixmap(w, self.base_height)
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

    def get_width(self):
        return self.pixmap().width()

    def set_selected(self, selected):
        if self.selected != selected:
            self.selected = selected
            if selected:
                effect = QtWidgets.QGraphicsDropShadowEffect()
                effect.setBlurRadius(25)
                effect.setColor(QtGui.QColor("#ffaa00"))
                effect.setOffset(0, 0)
                self.setGraphicsEffect(effect)
                self.setZValue(1) 
            else:
                self.setGraphicsEffect(None)
                self.setZValue(0)
            self.update()

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        
        # Draw Annotations
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
        
        # Draw Selection Border
        if self.selected:
            pen = QtGui.QPen(QtGui.QColor("#ffaa00"))
            pen.setWidth(4) 
            pen.setJoinStyle(QtCore.Qt.MiterJoin)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            rect = self.boundingRect()
            painter.drawRect(rect.adjusted(2, 2, -2, -2))

class HorizontalViewerDialog(QtWidgets.QDialog):
    image_switched = QtCore.pyqtSignal(str)
    open_vertical_viewer = QtCore.pyqtSignal(str)

    def __init__(self, image_list, current_filename=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("横向滚动看图")
        self.resize(1200, 800)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowMinMaxButtonsHint | QtCore.Qt.WindowCloseButtonHint)
        
        self.image_list = image_list
        self.current_filename = current_filename
        self.labeling_widget = parent # Store parent (LabelingWidget) reference
        self.items_map = {} 
        self.items_list = [] 
        self.view_scale = 1.0
        self.fit_height_mode = True
        self.thread_pool = QtCore.QThreadPool()
        self.thread_pool.setMaxThreadCount(4) 
        
        # UI Setup
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        layout.addWidget(self.splitter)
        
        # Graphics View
        self.scene = QtWidgets.QGraphicsScene()
        self.scene.setBackgroundBrush(QtGui.QBrush(QtGui.QColor("#1e1e1e")))
        
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.view.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.view.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.view.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        self.view.setViewportUpdateMode(QtWidgets.QGraphicsView.BoundingRectViewportUpdate)
        self.view.setOptimizationFlags(
            QtWidgets.QGraphicsView.DontAdjustForAntialiasing | 
            QtWidgets.QGraphicsView.DontSavePainterState
        )
        try:
            self.view.setViewport(QtWidgets.QOpenGLWidget())
        except:
            pass
            
        self.view.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.view.setFocusPolicy(QtCore.Qt.StrongFocus)
        
        self.view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.show_context_menu)
        
        self.splitter.addWidget(self.view)
        
        # Thumbnail List
        self.thumbnail_list = QtWidgets.QListWidget()
        # Removed setFixedHeight to allow splitter resizing and prevent empty space
        self.thumbnail_list.setMinimumHeight(100)
        self.thumbnail_list.setIconSize(QtCore.QSize(100, 100))
        self.thumbnail_list.setSpacing(5)
        self.thumbnail_list.setViewMode(QtWidgets.QListWidget.IconMode)
        self.thumbnail_list.setFlow(QtWidgets.QListWidget.LeftToRight)
        self.thumbnail_list.setWrapping(False)
        self.thumbnail_list.setResizeMode(QtWidgets.QListWidget.Adjust)
        self.thumbnail_list.setDragDropMode(QtWidgets.QAbstractItemView.NoDragDrop)
        self.thumbnail_list.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.thumbnail_list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.thumbnail_list.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                border: none;
                outline: none;
            }
            QListWidget::item {
                color: #aaaaaa;
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #444444;
                color: #ffffff;
                border: 1px solid #007acc;
                border-radius: 4px;
            }
            /* Horizontal Scrollbar styling */
            QScrollBar:horizontal {
                border: none;
                background: #2b2b2b;
                height: 10px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #666666;
                min-width: 20px;
                border-radius: 4px;
                margin: 2px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """)
        self.thumbnail_list.itemClicked.connect(self.on_thumbnail_clicked)
        self.thumbnail_list.setVisible(False) # Default hidden
        self.splitter.addWidget(self.thumbnail_list)
        
        self.splitter.setStretchFactor(0, 1)
        
        self.view.horizontalScrollBar().valueChanged.connect(self.on_scroll)
        self.view.horizontalScrollBar().valueChanged.connect(self.on_scroll)
        self.view.installEventFilter(self)
        self.thumbnail_list.installEventFilter(self)
        self.thumbnail_list.viewport().installEventFilter(self)
        
        self.populated = False
        self.closing = False
        
        self.scroll_timer = QtCore.QTimer()
        self.scroll_timer.setSingleShot(True)
        self.scroll_timer.setInterval(50)
        self.scroll_timer.timeout.connect(self.process_scroll_update)
        
        self.sync_scroll_enabled = False
        self.show_annotations = False
        self.fill_annotations = False
        self.thumbnails_visible = False
        
        self.layout_timer = QtCore.QTimer()
        self.layout_timer.setSingleShot(True)
        self.layout_timer.setInterval(50)
        self.layout_timer.timeout.connect(self.relayout_items)
        
        self.fit_width_mode = False
        self.fit_height_mode = True

    def showEvent(self, event):
        super().showEvent(event)
        if not self.populated:
            QtCore.QTimer.singleShot(50, self.populate_scene)
            self.populated = True
        QtCore.QTimer.singleShot(100, self.view.setFocus)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit_height_mode or self.fit_width_mode:
            QtCore.QTimer.singleShot(0, self.update_view_transform)

    def eventFilter(self, obj, event):
        if (obj == self.thumbnail_list or obj == self.thumbnail_list.viewport()) and event.type() == QtCore.QEvent.Wheel:
            delta = event.angleDelta().y()
            if delta == 0:
                delta = event.angleDelta().x()
            if delta != 0:
                hbar = self.thumbnail_list.horizontalScrollBar()
                # Standard mouse wheel scrolls vertically, map this to horizontal scroll
                # Usually negative delta means scroll down/right, positive means up/left
                # We want scroll down (negative) to move right (increase value)
                hbar.setValue(hbar.value() - delta) 
                event.accept()
                return True
        
        if obj == self.view and event.type() == QtCore.QEvent.Wheel:
            if event.modifiers() & QtCore.Qt.ControlModifier:
                if event.angleDelta().y() > 0:
                    self.zoom_in()
                else:
                    self.zoom_out()
            else:
                # Force horizontal scrolling regardless of vertical scrollbar
                delta = event.angleDelta().y()
                if delta != 0:
                    hbar = self.view.horizontalScrollBar()
                    hbar.setValue(hbar.value() - delta)
            event.accept()
            return True

        if obj == self.view and event.type() == QtCore.QEvent.Resize:
            if self.fit_height_mode or self.fit_width_mode:
                self.update_view_transform()
            QtCore.QTimer.singleShot(100, self.check_visible_items)
        return super().eventFilter(obj, event)

    def populate_scene(self):
        self.scene.clear()
        self.thumbnail_list.clear()
        self.items_map = {}
        self.items_list = []
        self.current_selected_item = None
        
        x_offset = 0
        spacing = 0 
        
        # Populate thumbnails
        for i, path in enumerate(self.image_list):
            filename = os.path.basename(path)
            # For horizontal list, text is below icon
            item = QtWidgets.QListWidgetItem(f"{i+1} {filename}")
            item.setData(QtCore.Qt.UserRole, path)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.thumbnail_list.addItem(item)
            
            loader = ThumbnailLoader(path, 100)
            loader.signals.loaded.connect(lambda p, img, r, s, sc, it=item: self.on_thumbnail_loaded(p, img, it))
            self.thread_pool.start(loader)
        
        for path in self.image_list:
            item = HorizontalThumbnailItem(path, SCENE_BASE_HEIGHT, labeling_widget=self.labeling_widget)
            item.show_annotations = self.show_annotations
            item.fill_annotations = self.fill_annotations
            item.setPos(x_offset, 0)
            self.scene.addItem(item)
            self.items_map[path] = item
            self.items_list.append(item)
            
            x_offset += item.get_width() + spacing
            
        self.scene.setSceneRect(0, 0, x_offset, SCENE_BASE_HEIGHT)
        self.update_view_transform()
        
        if self.current_filename and self.current_filename in self.items_map:
            item = self.items_map[self.current_filename]
            self.view.centerOn(item)
            
        self.check_visible_items()
        self.update_title_progress()

    def on_thumbnail_loaded(self, path, image, item):
        if self.closing: return
        try:
             item.setIcon(QtGui.QIcon(QtGui.QPixmap.fromImage(image)))
        except RuntimeError:
             pass

    def jump_to_image(self, filename):
        if filename in self.items_map:
            view_item = self.items_map[filename]
            self.view.centerOn(view_item)
            self.current_filename = filename
            self.process_scroll_update()

    def on_thumbnail_clicked(self, item):
        path = item.data(QtCore.Qt.UserRole)
        if path in self.items_map:
            view_item = self.items_map[path]
            self.view.centerOn(view_item)
            self.process_scroll_update() # Update selection immediately

    def show_context_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        
        zoom_in_action = menu.addAction("放大 (+)")
        zoom_in_action.triggered.connect(self.zoom_in)
        zoom_out_action = menu.addAction("缩小 (-)")
        zoom_out_action.triggered.connect(self.zoom_out)
        actual_size_action = menu.addAction("实际尺寸 (100%)")
        actual_size_action.triggered.connect(self.set_actual_size)
        
        menu.addSeparator()
        fit_height_action = menu.addAction("适应高度")
        fit_height_action.setCheckable(True)
        fit_height_action.setChecked(self.fit_height_mode)
        fit_height_action.triggered.connect(self.set_fit_height)
        
        fit_width_action = menu.addAction("适应宽度")
        fit_width_action.setCheckable(True)
        fit_width_action.setChecked(self.fit_width_mode)
        fit_width_action.triggered.connect(self.set_fit_width)
        
        menu.addSeparator()
        
        # Annotation Toggles
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
        thumb_action = menu.addAction("显示缩略图")
        thumb_action.setCheckable(True)
        thumb_action.setChecked(self.thumbnails_visible)
        thumb_action.triggered.connect(self.toggle_thumbnails)
        
        menu.addSeparator()
        refresh_action = menu.addAction("刷新")
        refresh_action.triggered.connect(self.reload_scene)
        
        menu.addSeparator()
        open_vert_action = menu.addAction("用垂直滚动看图打开")
        open_vert_action.triggered.connect(self.trigger_open_vertical_viewer)
        
        item = self.view.itemAt(pos)
        if isinstance(item, HorizontalThumbnailItem):
            menu.addSeparator()
            action = menu.addAction("切换到此图片")
            action.triggered.connect(lambda: self.switch_to_image(item.path))
            
        menu.exec_(self.view.mapToGlobal(pos))

    def toggle_sync_scroll(self):
        self.sync_scroll_enabled = not self.sync_scroll_enabled

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

    def update_image_list(self, new_image_list, current_filename=None):
        """更新图片列表（当主界面打开新文件夹时调用）"""
        self.image_list = new_image_list
        if current_filename:
            self.current_filename = current_filename
        self.reload_scene()
    
    def reload_scene(self):
        # Clear cache and reload
        self.populate_scene()

    def toggle_thumbnails(self):
        self.thumbnails_visible = not self.thumbnails_visible
        self.thumbnail_list.setVisible(self.thumbnails_visible)
        if self.thumbnails_visible:
            # Set initial size for thumbnails if opening
            # Give it enough space for the 100px icons + text + scrollbar (approx 160px)
            total_height = self.splitter.height()
            thumb_height = 160
            self.splitter.setSizes([total_height - thumb_height, thumb_height])
            
            # Sync when showing
            self.process_scroll_update()
        
        # Force update view transform after layout change to ensure fit height is correct
        # We use a timer to allow the layout to settle (splitter resize, etc.)
        if self.fit_height_mode:
             QtCore.QTimer.singleShot(50, self.update_view_transform)
             QtCore.QTimer.singleShot(150, self.update_view_transform) # Double check
        else:
             QtCore.QTimer.singleShot(50, self.update_view_transform)

    def switch_to_image(self, path):
        self.image_switched.emit(path)

    def trigger_open_vertical_viewer(self):
        center_item = self.get_center_item()
        if center_item:
            self.open_vertical_viewer.emit(center_item.path)
        elif self.current_filename:
            self.open_vertical_viewer.emit(self.current_filename)
        else:
            if self.image_list:
                self.open_vertical_viewer.emit(self.image_list[0])

    def update_view_transform(self):
        viewport_height = self.view.viewport().height()
        viewport_width = self.view.viewport().width()
        if viewport_height < 10: return
        
        if self.fit_height_mode:
            self.view_scale = viewport_height / SCENE_BASE_HEIGHT
        elif self.fit_width_mode:
            center_item = self.get_center_item()
            if center_item:
                target_scale = viewport_width / center_item.get_width()
                self.view_scale = target_scale
            else:
                self.view_scale = 1.0
        
        transform = QtGui.QTransform()
        transform.scale(self.view_scale, self.view_scale)
        self.view.setTransform(transform)

    def get_center_item(self):
        viewport_center_x = self.view.viewport().width() / 2
        scene_center_pt = self.view.mapToScene(int(viewport_center_x), 0)
        scene_x = scene_center_pt.x()
        
        closest_idx = -1
        closest_dist = float('inf')
        
        for i, item in enumerate(self.items_list):
            item_center = item.pos().x() + item.get_width() / 2
            dist = abs(item_center - scene_x)
            if dist < closest_dist:
                closest_dist = dist
                closest_idx = i
            if dist > closest_dist and closest_idx != -1:
                break
        
        if closest_idx != -1:
            return self.items_list[closest_idx]
        return None

    def set_fit_height(self):
        self.fit_height_mode = True
        self.fit_width_mode = False
        self.update_view_transform()
        self.check_visible_items()

    def set_fit_width(self):
        self.fit_height_mode = False
        self.fit_width_mode = True
        self.update_view_transform()
        self.check_visible_items()

    def set_actual_size(self):
        self.fit_height_mode = False
        self.fit_width_mode = False
        center_item = self.get_center_item()
        if center_item:
             reader = QtGui.QImageReader(center_item.path)
             s = reader.size()
             if s.isValid():
                 scale = s.height() / SCENE_BASE_HEIGHT
                 self.view_scale = scale
        self.update_view_transform()
        self.check_visible_items()

    def zoom_in(self):
        self.fit_height_mode = False
        self.fit_width_mode = False
        self.view_scale *= 1.2
        self.update_view_transform()
        self.check_visible_items()

    def zoom_out(self):
        self.fit_height_mode = False
        self.fit_width_mode = False
        self.view_scale /= 1.2
        self.update_view_transform()
        self.check_visible_items()

    def wheelEvent(self, event):
        # If mouse is over thumbnail list, let it handle the scroll
        if self.thumbnail_list.isVisible() and self.thumbnail_list.underMouse():
            super().wheelEvent(event)
            return
        
        # Main view scroll is now handled in eventFilter to ensure priority
        super().wheelEvent(event)

    def on_scroll(self):
        if self.closing: return
        if not self.scroll_timer.isActive():
            self.scroll_timer.start()

    def process_scroll_update(self):
        if self.closing: return
        self.check_visible_items()
        self.update_title_progress()

    def update_title_progress(self):
        viewport_center_x = self.view.viewport().width() / 2
        scene_center_pt = self.view.mapToScene(int(viewport_center_x), 0)
        scene_x = scene_center_pt.x()
        
        closest_idx = -1
        closest_dist = float('inf')
        
        for i, item in enumerate(self.items_list):
            item_center = item.pos().x() + item.get_width() / 2
            dist = abs(item_center - scene_x)
            if dist < closest_dist:
                closest_dist = dist
                closest_idx = i
            if dist > closest_dist and closest_idx != -1:
                break
                
        if closest_idx != -1:
            self.setWindowTitle(f"横向滚动看图 - {closest_idx + 1}/{len(self.image_list)}")
            
            new_item = self.items_list[closest_idx]
            if self.current_selected_item != new_item:
                if self.current_selected_item:
                    self.current_selected_item.set_selected(False)
                new_item.set_selected(True)
                self.current_selected_item = new_item
            
            if self.thumbnails_visible:
                self.thumbnail_list.blockSignals(True)
                self.thumbnail_list.setCurrentRow(closest_idx)
                self.thumbnail_list.scrollToItem(self.thumbnail_list.item(closest_idx))
                self.thumbnail_list.blockSignals(False)

    def check_visible_items(self):
        if self.closing or not self.items_list: return
        
        viewport_rect = self.view.viewport().rect()
        scene_rect = self.view.mapToScene(viewport_rect).boundingRect()
        left = scene_rect.left()
        right = scene_rect.right()
        
        for item in self.items_list:
            try:
                ix = item.pos().x()
                iw = item.boundingRect().width()
                if ix + iw < left: continue 
                if ix > right: break 
                
                if not item.loaded and not item.loading:
                    self.load_image(item)
            except RuntimeError:
                continue

    def load_image(self, item):
        item.loading = True
        loader = ImageLoader(item.path, SCENE_BASE_HEIGHT)
        loader.signals.loaded.connect(lambda p, i, r, s, sc: self.on_image_loaded(p, i, r, s, sc, item))
        self.thread_pool.start(loader)

    def on_image_loaded(self, path, image, aspect_ratio, shapes, scale_factor, item):
        if self.closing: return
        try:
            if item.path != path: return
        except RuntimeError:
            return
        
        old_width = item.get_width()
        item.set_image(image, aspect_ratio)
        item.set_shapes(shapes, scale_factor)
        new_width = item.get_width()
        
        if abs(new_width - old_width) > 1:
            self.request_relayout()

    def request_relayout(self):
        if not self.layout_timer.isActive():
            self.layout_timer.start()

    def relayout_items(self):
        if self.closing: return
        x_offset = 0
        spacing = 0
        
        for item in self.items_list:
            item.setPos(x_offset, 0)
            x_offset += item.boundingRect().width() + spacing
            
        self.scene.setSceneRect(0, 0, x_offset, SCENE_BASE_HEIGHT)

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
                    self.view.centerOn(next_item)
                    self.process_scroll_update()

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
                    self.view.centerOn(prev_item)
                    self.process_scroll_update()

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
        super().closeEvent(event)
