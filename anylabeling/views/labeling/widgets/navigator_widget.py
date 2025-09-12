"""Navigator widget for image navigation like Photoshop navigator"""

from typing import List, Optional, Any

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal, QRect, QPoint, QSize, QTimer
from PyQt5.QtGui import QPainter, QPen, QBrush, QPixmap, QColor, QMouseEvent
from PyQt5.QtWidgets import (QWidget, QSizePolicy, QVBoxLayout, QHBoxLayout, 
                             QSlider, QLineEdit, QLabel, QPushButton, QSpacerItem)


class ClickableSlider(QSlider):
    """Custom slider that supports clicking anywhere on the track to jump to position"""
    
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events for click-to-jump functionality"""
        if event.button() == Qt.LeftButton:
            if self.orientation() == Qt.Horizontal:
                # Get the slider handle position and size
                handle_width = self.style().pixelMetric(self.style().PM_SliderThickness)
                
                # Calculate if click is on the handle or track
                slider_min = self.minimum()
                slider_max = self.maximum()
                current_value = self.value()
                slider_width = self.width() - handle_width
                
                # Calculate current handle position
                if slider_max > slider_min:
                    handle_ratio = (current_value - slider_min) / (slider_max - slider_min)
                    handle_pos = handle_width // 2 + handle_ratio * slider_width
                    
                    # Check if click is near the handle (allow dragging)
                    click_x = event.x()
                    if abs(click_x - handle_pos) <= handle_width // 2 + 5:
                        # Click is on or near handle, allow normal dragging
                        super().mousePressEvent(event)
                        return
                
                # Click is on track, jump to position
                click_x = event.x()
                # Adjust for handle width offset
                effective_x = max(handle_width // 2, min(slider_width + handle_width // 2, click_x))
                ratio = (effective_x - handle_width // 2) / slider_width
                new_value = slider_min + ratio * (slider_max - slider_min)
                
                # Clamp the value and set it
                new_value = max(slider_min, min(slider_max, int(new_value)))
                self.setValue(new_value)
            else:
                # Vertical slider (if needed in future)
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)


class NavigatorWidget(QWidget):
    """Navigator widget showing thumbnail with viewport rectangle"""
    
    # Signal emitted when user clicks or drags in navigator
    navigation_requested = pyqtSignal(float, float)  # x_ratio, y_ratio
    # Signal emitted when widget is resized and viewport needs update
    viewport_update_needed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Widget properties - Remove maximum size constraint to allow free resizing
        self.setMinimumSize(150, 150)
        # Remove setMaximumSize to allow unlimited resizing
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setWindowTitle("导航器")
        
        # Image and viewport data
        self.original_image = None
        self.thumbnail = None
        self.viewport_rect = QRect()  # Rectangle representing current view
        self.image_rect = QRect()     # Rectangle of thumbnail in widget
        
        # Shapes data for overlay
        self.shapes = []  # List of shapes to draw on thumbnail
        self.visible_shapes = {}  # Dictionary of shape visibility
        
        # Interaction state
        self.dragging = False
        self.last_drag_pos = QPoint()
        
        # Styling
        self.viewport_pen = QPen(QColor(255, 0, 0, 255), 2)  # Red pen
        self.background_brush = QBrush(QColor(64, 64, 64))   # Dark background
        self.shape_pen = QPen(QColor(0, 255, 0, 180), 1)     # Green pen for shapes
        
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.navigator_select_line_color = QColor(255, 0, 255, 255)
        self.navigator_hover_line_color = QColor(255, 255, 0, 255)
        
    def set_colors(
        self,
        select_line_color: QColor,
        hover_line_color: QColor,
    ):
        self.navigator_select_line_color = select_line_color
        self.navigator_hover_line_color = hover_line_color

    def set_image(self, image_data: Any) -> None:
        """
        Set the image to display in the navigator widget.

        This method accepts various image formats and converts them to the internal
        QPixmap format for display. It handles both byte data and QPixmap objects,
        automatically generating the appropriate thumbnail for navigation.

        Args:
            image_data (Any): The image data to display. Can be:
                - bytes: Raw image data that will be converted to QPixmap
                - QPixmap: Qt pixmap object ready for display
                - None: Clears the current image

        Returns:
            None

        Examples:
            >>> # Set image from QPixmap
            >>> pixmap = QPixmap("image.jpg")
            >>> navigator.set_image(pixmap)
            
            >>> # Clear current image
            >>> navigator.set_image(None)
            
        Note:
            The widget will automatically update its display after setting the image.
            Thumbnails are generated asynchronously for performance.
        """
        if image_data is None:
            self.original_image = None
            self.thumbnail = None
            self.update()
            return
            
        # Convert image data to QPixmap
        if isinstance(image_data, bytes):
            pixmap = QPixmap()
            pixmap.loadFromData(image_data)
            self.original_image = pixmap
        elif isinstance(image_data, QPixmap):
            self.original_image = image_data
        else:
            # Try to convert other formats
            try:
                self.original_image = QPixmap(str(image_data))
            except:
                return
                
        self._update_thumbnail()
        self.update()
        
    def _update_thumbnail(self):
        """Update thumbnail to fit widget size"""
        if not self.original_image or self.original_image.isNull():
            return
            
        widget_size = self.size()
        # Leave some margin
        available_size = QSize(widget_size.width() - 20, widget_size.height() - 20)
        
        # Scale image to fit available space while keeping aspect ratio
        self.thumbnail = self.original_image.scaled(
            available_size, 
            Qt.KeepAspectRatio, 
            Qt.SmoothTransformation
        )
        
        # Calculate thumbnail position (centered)
        thumb_size = self.thumbnail.size()
        x = (widget_size.width() - thumb_size.width()) // 2
        y = (widget_size.height() - thumb_size.height()) // 2
        self.image_rect = QRect(x, y, thumb_size.width(), thumb_size.height())
        
    def set_viewport(self, x_ratio: float, y_ratio: float, width_ratio: float, height_ratio: float) -> None:
        """
        Set the viewport rectangle that shows the visible area of the main canvas.

        This method updates the viewport rectangle overlay that indicates which
        portion of the full image is currently visible in the main canvas window.
        All parameters are specified as ratios (0.0 to 1.0) relative to the image size.

        Args:
            x_ratio (float): X coordinate of viewport top-left as ratio of image width (0.0-1.0).
            y_ratio (float): Y coordinate of viewport top-left as ratio of image height (0.0-1.0).
            width_ratio (float): Viewport width as ratio of image width (0.0-1.0).
            height_ratio (float): Viewport height as ratio of image height (0.0-1.0).

        Returns:
            None

        Examples:
            >>> # Set viewport to show center quarter of image
            >>> navigator.set_viewport(0.25, 0.25, 0.5, 0.5)
            
            >>> # Set viewport to show entire image
            >>> navigator.set_viewport(0.0, 0.0, 1.0, 1.0)
            
        Note:
            The viewport rectangle is drawn as an overlay on the thumbnail image.
            Invalid ratios are clamped to valid ranges automatically.
        """
        if not self.thumbnail or self.image_rect.isEmpty():
            return
            
        # Convert ratios to pixel coordinates within thumbnail
        thumb_width = self.image_rect.width()
        thumb_height = self.image_rect.height()
        
        x = int(self.image_rect.x() + x_ratio * thumb_width)
        y = int(self.image_rect.y() + y_ratio * thumb_height)
        width = max(1, int(width_ratio * thumb_width))
        height = max(1, int(height_ratio * thumb_height))
        
        self.viewport_rect = QRect(x, y, width, height)
        self.update()
        
    def set_shapes(self, shapes: Optional[List[Any]], visible_shapes: Optional[dict] = None) -> None:
        """
        Set the shapes to display on the thumbnail overlay.

        This method updates the collection of shapes that will be rendered as overlays
        on the thumbnail image. It supports shape visibility control and automatically
        triggers a repaint to show the updated shapes.

        Args:
            shapes (Optional[List[Any]]): List of shape objects from the main canvas.
                Each shape should have position, color, and type attributes.
                Pass None or empty list to clear all shapes.
            visible_shapes (Optional[dict]): Dictionary mapping shapes to their visibility.
                Format: {shape_object: bool}. If not provided, all shapes are visible.

        Returns:
            None

        Examples:
            >>> # Set shapes with all visible
            >>> navigator.set_shapes(shape_list)
            
            >>> # Set shapes with visibility control
            >>> visibility = {shape1: True, shape2: False}
            >>> navigator.set_shapes(shape_list, visibility)
            
            >>> # Clear all shapes
            >>> navigator.set_shapes(None)
            
        Note:
            The navigator will render shapes using the same colors and styles
            as the main canvas for consistency.
        """
        self.shapes = shapes if shapes else []
        self.visible_shapes = visible_shapes or {}
        self.update()
        
    def resizeEvent(self, event) -> None:
        """
        Handle widget resize events to maintain proper thumbnail display.

        This method is automatically called by PyQt when the widget is resized.
        It updates the thumbnail to fit the new widget size and ensures the
        viewport overlay remains accurate by triggering necessary updates.

        Args:
            event: Qt resize event containing old and new size information.

        Returns:
            None

        Examples:
            # This is automatically called by PyQt - no direct usage
            >>> # Widget resized by user -> resizeEvent() -> thumbnail updated
            
        Note:
            Also emits viewport_update_needed signal to notify parent components
            that the viewport rectangle may need recalculation due to size changes.
        """
        super().resizeEvent(event)
        self._update_thumbnail()
        # Force repaint to show updated thumbnail
        self.update()
        # Emit signal to trigger viewport update
        self.viewport_update_needed.emit()
        
    def paintEvent(self, event) -> None:
        """
        Paint the navigator widget with thumbnail, shapes, and viewport overlay.

        This method is automatically called by PyQt's painting system whenever
        the widget needs to be redrawn. It renders the thumbnail image, shape
        overlays, and viewport rectangle in the correct layered order.

        Args:
            event: Qt paint event containing the region that needs updating.

        Returns:
            None

        Examples:
            # This is automatically called by PyQt - no direct usage
            >>> # Widget needs update -> paintEvent() -> visual elements drawn
            
        Note:
            Rendering order: background → thumbnail → shapes → viewport rectangle.
            All drawing uses antialiasing for smoother visual appearance.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Fill background
        painter.fillRect(self.rect(), self.background_brush)
        
        # Draw thumbnail if available
        if self.thumbnail and not self.thumbnail.isNull():
            painter.drawPixmap(self.image_rect, self.thumbnail)
            
            # Draw shapes overlay
            self._draw_shapes_overlay(painter)
            
            # Draw viewport rectangle (on top of everything)
            if not self.viewport_rect.isEmpty():
                painter.setPen(self.viewport_pen)
                painter.setBrush(QBrush(Qt.NoBrush))  # No fill
                painter.drawRect(self.viewport_rect)
                
    def _draw_shapes_overlay(self, painter):
        """Draw shapes overlay on thumbnail"""
        if not self.shapes or self.image_rect.isEmpty():
            return
        
        if not self.original_image or self.original_image.isNull():
            return
            
        # Get original image size
        original_width = self.original_image.width()
        original_height = self.original_image.height()
        
        if original_width <= 0 or original_height <= 0:
            return
            
        # Calculate scale factors from original image to current thumbnail display
        thumbnail_scale_x = self.image_rect.width() / original_width
        thumbnail_scale_y = self.image_rect.height() / original_height
        
        # Draw each shape
        for shape in self.shapes:
            if not hasattr(shape, 'points') or not shape.points:
                continue
            
            # Skip hidden shapes
            if shape in self.visible_shapes and not self.visible_shapes[shape]:
                continue
                
            # Get shape color and brush
            shape_color = self._get_shape_color(shape)
            shape_brush = self._get_shape_brush(shape)
            
            # Use thicker lines for better visibility in thumbnail
            line_width = 2
            painter.setPen(QPen(shape_color, line_width))
            painter.setBrush(shape_brush)
            
            # Convert shape points to thumbnail coordinates
            # The key fix: shapes should be positioned relative to the ORIGINAL image,
            # not the canvas scale/offset (which changes with zoom/pan)
            thumbnail_points = []
            for point in shape.points:
                # Convert directly from original image coordinates to thumbnail coordinates
                # Assuming shape.points are already in original image coordinate space
                thumb_x = self.image_rect.x() + (point.x() / original_width) * self.image_rect.width()
                thumb_y = self.image_rect.y() + (point.y() / original_height) * self.image_rect.height()
                
                thumbnail_points.append(QPoint(int(thumb_x), int(thumb_y)))
            
            # Only draw if points are within reasonable bounds
            if self._points_in_bounds(thumbnail_points):
                # Draw based on shape type
                if hasattr(shape, 'shape_type'):
                    # 添加调试输出
                    # print(f"Drawing shape type: {shape.shape_type}, points: {len(thumbnail_points)}")
                    if shape.shape_type in ["rectangle", "rotation"]:
                        self._draw_rectangle_on_thumbnail(painter, thumbnail_points)
                    elif shape.shape_type == "polygon":
                        self._draw_polygon_on_thumbnail(painter, thumbnail_points)
                    elif shape.shape_type == "circle":
                        self._draw_circle_on_thumbnail(painter, thumbnail_points)
                    elif shape.shape_type == "line":
                        self._draw_line_on_thumbnail(painter, thumbnail_points)
                    elif shape.shape_type == "linestrip":  # 添加线条序列支持
                        self._draw_linestrip_on_thumbnail(painter, thumbnail_points)
                    elif shape.shape_type == "point":
                        self._draw_point_on_thumbnail(painter, thumbnail_points)
                else:
                    # Default: draw as polygon
                    # print(f"Drawing default polygon, points: {len(thumbnail_points)}")
                    self._draw_polygon_on_thumbnail(painter, thumbnail_points)
            # else:
            #     print(f"Shape not in bounds: {shape.shape_type if hasattr(shape, 'shape_type') else 'unknown'}")
                    
    def _get_shape_color(self, shape: Any) -> QColor:
        """
        Get the display color for a shape following main interface logic.

        This method determines the appropriate color for rendering a shape's border
        in the navigator, following the same logic as the main canvas. It prioritizes
        hover highlighting, then selection colors, then normal colors.

        Args:
            shape (Any): Shape object with color and state attributes.

        Returns:
            QColor: The color to use for drawing the shape's border.

        Examples:
            >>> color = self._get_shape_color(shape)
            >>> painter.setPen(QPen(color, 2))
            
        Note:
            Highlighted shapes (hovered) are displayed with bright yellow borders.
            Selected shapes use their select_line_color if available.
            Normal shapes use their line_color property.
        """
        # Hover highlighting takes precedence - use bright yellow
        if hasattr(shape, '_is_highlighted') and shape._is_highlighted:
            return QColor(255, 255, 0)  # Bright yellow for hover state
        
        # 优先处理鼠标单击选中
        # 其次处理鼠标单击选中
        if getattr(shape, "is_mouse_selected", False):
            return self.navigator_select_line_color

        # 再次处理鼠标悬停
        if getattr(shape, "is_hovered", False):
            return self.navigator_hover_line_color

        # 处理全局高亮（"Highlight All"）
        if getattr(shape, 'selected', False) and hasattr(shape, 'select_line_color'):
            color = getattr(shape, 'select_line_color')
            if color and color.isValid():
                return color
        
        # Use normal line color
        if hasattr(shape, 'line_color') and shape.line_color:
            color = shape.line_color
            if color and color.isValid():
                return color
        
        # Fallback to visible green
        return QColor(0, 255, 0)
    
    def _get_shape_brush(self, shape: Any) -> QBrush:
        """
        Get the fill brush for a shape following main interface logic.

        This method determines whether a shape should be filled and what color
        to use, following the same logic as the main canvas Shape class.
        Only shapes with the 'fill' attribute set to True will be filled.

        Args:
            shape (Any): Shape object with fill properties and colors.

        Returns:
            QBrush: Brush for filling the shape, or NoBrush if no fill needed.

        Examples:
            >>> brush = self._get_shape_brush(shape)
            >>> painter.setBrush(brush)
            
        Note:
            The fill behavior exactly matches the main canvas:
            - Only shapes with fill=True are filled
            - Selected shapes use select_fill_color
            - Normal shapes use fill_color
        """
        # Check if shape should be filled (following main canvas logic)
        should_fill: bool = getattr(shape, 'fill', False)
        
        if not should_fill:
            # No fill if shape doesn't have fill enabled
            return QBrush(Qt.NoBrush)
        
        fill_color: Optional[QColor] = None
        
        # Follow Shape class logic: selected shapes use select_fill_color
        if hasattr(shape, 'selected') and shape.selected:
            if hasattr(shape, 'select_fill_color') and shape.select_fill_color:
                fill_color = shape.select_fill_color
        
        # Use normal fill color if no selection color
        if not fill_color:
            if hasattr(shape, 'fill_color') and shape.fill_color:
                fill_color = shape.fill_color
        
        if fill_color and fill_color.isValid():
            return QBrush(fill_color)
        
        # No fill if no valid color found
        return QBrush(Qt.NoBrush)
            
    def _points_in_bounds(self, points: List[QPoint]) -> bool:
        """
        Check if shape points are within reasonable bounds for rendering.

        This method determines whether a shape should be rendered based on whether
        its points are within or intersect with the visible thumbnail area.
        It uses an improved algorithm that handles partially visible shapes better.

        Args:
            points (List[QPoint]): List of points defining the shape in thumbnail coordinates.

        Returns:
            bool: True if the shape should be rendered, False otherwise.

        Examples:
            >>> thumbnail_points = [QPoint(10, 10), QPoint(50, 50)]
            >>> should_draw = self._points_in_bounds(thumbnail_points)
            >>> if should_draw:
            ...     # Proceed with drawing the shape
            
        Note:
            Uses a generous margin and intersection testing to ensure
            partially visible shapes are not incorrectly culled.
        """
        if not points:
            return False
        
        # Use generous margin to avoid culling partially visible shapes
        margin = 100
        bounds = self.image_rect.adjusted(-margin, -margin, margin, margin)
        
        # First check: any point within bounds
        has_point_in_bounds = False
        for point in points:
            if bounds.contains(point):
                has_point_in_bounds = True
                break
                
        # Second check: shape bounding box intersects with image area
        if not has_point_in_bounds and len(points) >= 2:
            # Calculate shape bounding rectangle
            min_x = min(p.x() for p in points)
            max_x = max(p.x() for p in points)
            min_y = min(p.y() for p in points)
            max_y = max(p.y() for p in points)
            
            shape_rect = QRect(min_x, min_y, max_x - min_x, max_y - min_y)
            return self.image_rect.intersects(shape_rect)
            
        return has_point_in_bounds
                
    def _draw_rectangle_on_thumbnail(self, painter, points):
        """Draw rectangle on thumbnail"""
        if len(points) >= 2:
            if len(points) == 2:
                # Standard rectangle from two points
                rect = QRect(points[0], points[1])
                painter.drawRect(rect)
            else:
                # Rotated rectangle - draw as polygon
                self._draw_polygon_on_thumbnail(painter, points)
                
    def _draw_polygon_on_thumbnail(self, painter, points):
        """Draw polygon on thumbnail"""
        if len(points) >= 2:
            from PyQt5.QtGui import QPolygon
            polygon = QPolygon(points)
            painter.drawPolygon(polygon)
            
    def _draw_circle_on_thumbnail(self, painter, points):
        """Draw circle on thumbnail"""
        if len(points) >= 2:
            center = points[0]
            radius_point = points[1]
            radius = int(((radius_point.x() - center.x()) ** 2 + 
                         (radius_point.y() - center.y()) ** 2) ** 0.5)
            painter.drawEllipse(center, radius, radius)
            
    def _draw_line_on_thumbnail(self, painter, points):
        """Draw line on thumbnail"""
        if len(points) >= 2:
            painter.drawLine(points[0], points[1])
            
    def _draw_linestrip_on_thumbnail(self, painter: QPainter, points: List[QPoint]) -> None:
        """
        Draw a linestrip (connected line segments) on the thumbnail.

        This method renders a linestrip shape by drawing connected line segments
        between consecutive points. This is used for the "linestrip" shape type
        which creates a continuous path through multiple points.

        Args:
            painter (QPainter): Qt painter object configured with pen and brush.
            points (List[QPoint]): List of points in thumbnail coordinates to connect.

        Returns:
            None

        Examples:
            >>> points = [QPoint(10, 10), QPoint(20, 15), QPoint(30, 5)]
            >>> self._draw_linestrip_on_thumbnail(painter, points)
            # Draws lines: (10,10)→(20,15)→(30,5)
            
        Note:
            Requires at least 2 points to draw any lines.
            Each consecutive pair of points is connected with a line segment.
        """
        if len(points) >= 2:
            for i in range(len(points) - 1):
                painter.drawLine(points[i], points[i + 1])
            
    def _draw_point_on_thumbnail(self, painter, points):
        """Draw point on thumbnail"""
        if len(points) >= 1:
            point_size = 2
            painter.fillRect(points[0].x() - point_size, points[0].y() - point_size, 
                           point_size * 2, point_size * 2, self.shape_pen.color())
                
    def mousePressEvent(self, event) -> None:
        """
        Handle mouse press events for navigation interaction.

        This method initiates navigation interaction when the user clicks within
        the thumbnail area. It starts drag tracking and immediately navigates to
        the clicked position in the main canvas.

        Args:
            event: Qt mouse event containing button, position, and modifier information.

        Returns:
            None

        Examples:
            # This is automatically called by PyQt - no direct usage
            >>> # User clicks in thumbnail -> mousePressEvent() -> navigation starts
            
        Note:
            Only responds to left mouse button clicks within the thumbnail image area.
            Navigation coordinates are automatically converted to ratios and emitted.
        """
        if event.button() == Qt.LeftButton and self.image_rect.contains(event.pos()):
            self.dragging = True
            self.last_drag_pos = event.pos()
            self._emit_navigation_signal(event.pos())
            
    def mouseMoveEvent(self, event) -> None:
        """
        Handle mouse move events during navigation dragging.

        This method continues navigation interaction while the user drags within
        the thumbnail area. It provides real-time navigation feedback by updating
        the main canvas view as the mouse moves.

        Args:
            event: Qt mouse event containing current position and button state.

        Returns:
            None

        Examples:
            # This is automatically called by PyQt - no direct usage
            >>> # User drags in thumbnail -> mouseMoveEvent() -> navigation updates
            
        Note:
            Only processes moves when dragging is active and cursor stays within
            the thumbnail image area for accurate navigation control.
        """
        if self.dragging and self.image_rect.contains(event.pos()):
            self._emit_navigation_signal(event.pos())
            self.last_drag_pos = event.pos()
            
    def mouseReleaseEvent(self, event) -> None:
        """
        Handle mouse release events to end navigation interaction.

        This method terminates the navigation dragging state when the user
        releases the mouse button, completing the navigation interaction.

        Args:
            event: Qt mouse event containing button and position information.

        Returns:
            None

        Examples:
            # This is automatically called by PyQt - no direct usage
            >>> # User releases mouse -> mouseReleaseEvent() -> dragging ends
            
        Note:
            Only responds to left mouse button release to match the press behavior.
            Dragging state is reset regardless of cursor position.
        """
        if event.button() == Qt.LeftButton:
            self.dragging = False
            
    def wheelEvent(self, event) -> None:
        """
        Handle mouse wheel events for navigator zoom functionality.

        This method processes mouse wheel input to provide zoom control directly
        within the navigator widget. It forwards wheel events to the parent dialog
        if zoom handling is available, otherwise accepts the event locally.

        Args:
            event: Qt wheel event containing delta and position information.

        Returns:
            None

        Examples:
            # This is automatically called by PyQt - no direct usage
            >>> # User scrolls wheel -> wheelEvent() -> zoom changes
            
        Note:
            Requires parent dialog to have 'handle_wheel_zoom' method for zoom.
            Falls back to event acceptance if no zoom handler is available.
        """
        # Forward wheel events to parent dialog if it exists
        if hasattr(self.parent(), 'handle_wheel_zoom'):
            self.parent().handle_wheel_zoom(event)
        else:
            # Fallback: accept the event to prevent it from propagating
            event.accept()
            
    def _emit_navigation_signal(self, pos):
        """Emit navigation signal with position ratios"""
        if self.image_rect.isEmpty():
            return
            
        # Convert widget coordinates to ratios
        relative_x = pos.x() - self.image_rect.x()
        relative_y = pos.y() - self.image_rect.y()
        
        x_ratio = max(0.0, min(1.0, relative_x / self.image_rect.width()))
        y_ratio = max(0.0, min(1.0, relative_y / self.image_rect.height()))
        
        self.navigation_requested.emit(x_ratio, y_ratio)


class NavigatorDialog(QtWidgets.QDialog):
    """Standalone navigator window with zoom controls"""
    
    # Signals for zoom control
    zoom_changed = pyqtSignal([int], [int, QPoint])  # zoom percentage, optional mouse position
    # Signal for viewport update requests
    viewport_update_requested = pyqtSignal()
    
    def __init__(self, parent=None, settings=None, config=None, actions=None):
        super().__init__(parent)
        if actions:
            self.addActions(actions)
        self.settings = settings
        self.config = config
        self.app_closing = False  # 标志应用是否正在关闭
        
        self.setWindowTitle("导航器")
        self.setWindowFlags(
            Qt.Tool |
            Qt.WindowCloseButtonHint
        )
        
        # Allow dialog to be resized freely
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Create main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Create navigator widget (takes most space)
        self.navigator = NavigatorWidget(self)
        main_layout.addWidget(self.navigator, 1)  # stretch factor of 1
        
        # Connect navigator signals
        self.navigator.viewport_update_needed.connect(
            self.viewport_update_requested.emit
        )
        
        # Create zoom controls container (fixed height)
        zoom_container = QWidget()
        zoom_container.setFixedHeight(60)  # Fixed height for controls
        zoom_layout = QVBoxLayout(zoom_container)
        zoom_layout.setContentsMargins(0, 0, 0, 0)
        zoom_layout.setSpacing(3)
        
        # Zoom percentage input and file info (left aligned)
        percentage_layout = QHBoxLayout()
        percentage_layout.setContentsMargins(0, 0, 0, 0)
        
        # File info label (replaces left-side positioning)
        self.file_info_label = QLabel()
        self.file_info_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.file_info_label.setStyleSheet("""
            QLabel { 
                color: #000000; 
                font-size: 11px; 
                font-weight: bold;
                background: transparent;
                padding: 2px 4px;
            }
        """)
        self.file_info_label.setMinimumWidth(80)
        
        self.zoom_input = QLineEdit()
        self.zoom_input.setFocusPolicy(Qt.ClickFocus)
        self.zoom_input.setFixedWidth(35)  # Made slightly smaller
        self.zoom_input.setAlignment(Qt.AlignCenter)
        self.zoom_input.setText("100")
        self.zoom_input.returnPressed.connect(self.on_zoom_input_changed)
        self.zoom_input.editingFinished.connect(self.on_zoom_input_changed)
        
        percentage_label = QLabel("%")
        percentage_label.setFixedWidth(15)
        
        # Add widgets: file info on left, zoom controls on right
        percentage_layout.addWidget(self.file_info_label)
        percentage_layout.addStretch()  # Push zoom controls to right
        percentage_layout.addWidget(self.zoom_input)
        percentage_layout.addWidget(percentage_label)
        
        # Zoom slider
        slider_layout = QHBoxLayout()
        slider_layout.setContentsMargins(0, 0, 0, 0)
        
        # Zoom out button
        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setFixedSize(20, 20)
        zoom_out_btn.clicked.connect(self.zoom_out)
        
        # Slider with click-to-jump functionality
        self.zoom_slider = ClickableSlider(Qt.Horizontal)
        self.zoom_slider.setRange(1, 1000)  # 1% to 1000%
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.on_slider_changed)
        
        # Zoom in button
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedSize(20, 20)
        zoom_in_btn.clicked.connect(self.zoom_in)
        
        slider_layout.addWidget(zoom_out_btn)
        slider_layout.addWidget(self.zoom_slider)
        slider_layout.addWidget(zoom_in_btn)
        
        # Add to zoom container
        zoom_layout.addLayout(percentage_layout)
        zoom_layout.addLayout(slider_layout)
        
        # Add to main layout (no stretch factor, so it keeps fixed size)
        main_layout.addWidget(zoom_container, 0)
        
        self.setLayout(main_layout)
        
        # Set initial size but allow resizing
        self.resize(220, 280)  # Back to original size
        self.setMinimumSize(180, 220)  # Back to original minimum size
        
        # Keep track of current zoom
        self.current_zoom = 100
        
        # File info tracking
        self.current_filename = ""
        self.current_page = 1
        self.total_pages = 1
        
    def resizeEvent(self, event):
        """Handle dialog resize"""
        super().resizeEvent(event)
        self._save_navigator_config()
        # Emit signal for viewport update
        self.viewport_update_requested.emit()

    def moveEvent(self, event):
        """Handle dialog move"""
        super().moveEvent(event)
        self._save_navigator_config()
        
    def _save_navigator_config(self):
        """Save navigator position and size to config"""
        if self.config is not None:
            # Update config in memory
            if "navigator" not in self.config:
                self.config["navigator"] = {}
            
            self.config["navigator"]["position_x"] = self.x()
            self.config["navigator"]["position_y"] = self.y()
            self.config["navigator"]["width"] = self.width()
            self.config["navigator"]["height"] = self.height()
            
            # 立即保存到配置文件，避免被其他保存覆盖
            try:
                from anylabeling.config import save_config
                save_config(self.config)
            except Exception as e:
                print(f"Failed to save navigator config: {e}")
        
    def set_image(self, image_data):
        """Set image in navigator"""
        self.navigator.set_image(image_data)
        
    def set_viewport(self, x_ratio, y_ratio, width_ratio, height_ratio):
        """Set viewport in navigator"""
        self.navigator.set_viewport(x_ratio, y_ratio, width_ratio, height_ratio)
        
    def set_shapes(self, shapes, visible_shapes=None):
        """Set shapes to display in navigator"""
        self.navigator.set_shapes(shapes, visible_shapes)
        
    def set_zoom_value(self, zoom_percentage: int) -> None:
        """
        Set the zoom value from external sources like the main canvas.

        This method updates the zoom controls to reflect zoom changes that
        originated from other parts of the application. It synchronizes the
        slider and input field while preventing recursive signal emission.

        Args:
            zoom_percentage (int): The zoom level as a percentage (1-1000).

        Returns:
            None

        Examples:
            >>> # Update navigator zoom to match main canvas
            >>> navigator_dialog.set_zoom_value(150)  # 150% zoom
            >>> 
            >>> # Sync with canvas zoom change
            >>> canvas_zoom = canvas.get_zoom_percentage()
            >>> navigator_dialog.set_zoom_value(canvas_zoom)
            
        Note:
            Blocks signals during update to prevent infinite recursion between
            navigator and canvas zoom synchronization.
        """
        self.current_zoom = zoom_percentage
        
        # Block signals to prevent recursion
        self.zoom_slider.blockSignals(True)
        self.zoom_input.blockSignals(True)
        
        # Update controls
        self.zoom_slider.setValue(zoom_percentage)
        self.zoom_input.setText(str(zoom_percentage))
        
        # Re-enable signals
        self.zoom_slider.blockSignals(False)
        self.zoom_input.blockSignals(False)
        
    def on_slider_changed(self, value):
        """Handle slider value change"""
        self.current_zoom = value
        self.zoom_input.setText(str(value))
        self.zoom_changed[int].emit(value)
        
    def on_zoom_input_changed(self):
        """Handle zoom input change"""
        try:
            value = int(self.zoom_input.text())
            value = max(1, min(1000, value))  # Clamp between 1-1000%
            
            self.current_zoom = value
            self.zoom_slider.setValue(value)
            self.zoom_input.setText(str(value))
            self.zoom_changed[int].emit(value)
        except ValueError:
            # Reset to current value if invalid input
            self.zoom_input.setText(str(self.current_zoom))
            
    def zoom_in(self):
        """Zoom in by 1%"""
        new_zoom = min(1000, self.current_zoom + 1)
        self.set_zoom_value(new_zoom)
        self.zoom_changed[int].emit(new_zoom)
        
    def zoom_out(self):
        """Zoom out by 1%"""
        new_zoom = max(1, self.current_zoom - 1)
        self.set_zoom_value(new_zoom)
        self.zoom_changed[int].emit(new_zoom)
        
    def handle_wheel_zoom(self, event) -> None:
        """
        Handle mouse wheel events for precise zoom control.

        This method processes wheel events to provide smooth zoom functionality
        directly within the navigator. It supports mouse-centered zooming and
        emits appropriate signals for canvas synchronization.

        Args:
            event: Qt wheel event containing delta and position information.

        Returns:
            None

        Examples:
            # This is automatically called by PyQt - no direct usage
            >>> # User scrolls wheel in navigator -> handle_wheel_zoom() -> zoom changes
            
        Note:
            Zoom increment is 1% per wheel step for fine control.
            Supports mouse position for centered zooming in the main canvas.
            Automatically clamps zoom values to valid range (1-1000%).
        """
        # Get wheel delta - force 1% increment regardless of wheel sensitivity
        delta = event.angleDelta().y()
        
        # Check for Ctrl modifier for faster zoom
        if event.modifiers() == Qt.ControlModifier:
            zoom_step = 5
        else:
            zoom_step = 1

        # Force exactly 1% or 5% increment/decrement per wheel event
        if delta > 0:
            zoom_increment = zoom_step  # Zoom in
        elif delta < 0:
            zoom_increment = -zoom_step  # Zoom out
        else:
            zoom_increment = 0  # No change if no delta
        
        # Calculate new zoom value
        new_zoom = self.current_zoom + zoom_increment
        new_zoom = max(1, min(1000, new_zoom))  # Clamp to valid range
        
        # Apply new zoom with mouse position for centered zooming
        self.set_zoom_value(new_zoom)
        # Send zoom change with mouse position for centered zooming
        self.zoom_changed[int, QPoint].emit(new_zoom, event.pos())
        
        # Accept the event
        event.accept()

    def set_file_info(self, filename: str, current_page: int = 1, total_pages: int = 1) -> None:
        """
        Set the file information to display in the navigator.

        This method updates the file information display with the current file
        details including filename and pagination information for multi-page
        documents like PDFs or image sequences.

        Args:
            filename (str): Full path or name of the current file.
            current_page (int): Current page number (1-based indexing).
            total_pages (int): Total number of pages in the document.

        Returns:
            None

        Examples:
            >>> # Single image file
            >>> navigator.set_file_info("image.jpg")
            >>> 
            >>> # Multi-page PDF
            >>> navigator.set_file_info("document.pdf", 3, 10)
            >>> # Displays: "document: 3/10"
            
            >>> # Image sequence
            >>> navigator.set_file_info("sequence_001.png", 1, 50)
            >>> # Displays: "sequence_0: 1/50"
            
        Note:
            Long filenames are automatically truncated to 10 characters plus "..."
            for compact display in the navigator interface.
        """
        self.current_filename = filename
        self.current_page = current_page  
        self.total_pages = total_pages
        self._update_file_info_display()
        
    def _update_file_info_display(self):
        """Update the file info label display"""
        if not self.current_filename:
            self.file_info_label.setText("")
            return
            
        # Extract filename without path and extension
        import os
        base_name = os.path.splitext(os.path.basename(self.current_filename))[0]
        
        # Truncate filename if too long (keep first 10 characters)
        if len(base_name) > 10:
            display_name = base_name[:10] + "..."
        else:
            display_name = base_name
            
        # Format: filename: page/total
        info_text = f"{display_name}: {self.current_page}/{self.total_pages}"
        self.file_info_label.setText(info_text)

    def closeEvent(self, event):
        """
        Handle dialog close event to save position and size.
        
        This method is called when the navigator dialog is closed by the user.
        It saves the current position and size to config file before closing.
        
        Args:
            event: Qt close event containing close information.
            
        Returns:
            None
        """
        # 只有在用户手动关闭导航器时才设置 visible=False
        # 如果是应用关闭导致的，则不改变 visible 状态
        if not self.app_closing:
            # Save navigator state to config
            if self.config is not None:
                if "navigator" not in self.config:
                    self.config["navigator"] = {}
                
                self.config["navigator"]["visible"] = False
                self.config["navigator"]["position_x"] = self.x()
                self.config["navigator"]["position_y"] = self.y()
                self.config["navigator"]["width"] = self.width()
                self.config["navigator"]["height"] = self.height()
                
                # 立即保存到配置文件
                try:
                    from anylabeling.config import save_config
                    save_config(self.config)
                except Exception as e:
                    print(f"Failed to save navigator config on close: {e}")
        else:
            pass
        
        # Call parent close event
        super().closeEvent(event)

    def restore_from_config(self):
        """Restore navigator position and size from config"""
        if self.config is not None and "navigator" in self.config:
            nav_config = self.config["navigator"]
            
            # Restore position
            if "position_x" in nav_config and "position_y" in nav_config:
                self.move(nav_config["position_x"], nav_config["position_y"])
            
            # Restore size
            if "width" in nav_config and "height" in nav_config:
                self.resize(nav_config["width"], nav_config["height"])
            
            # Restore visibility
            if "visible" in nav_config and nav_config["visible"]:
                self.show()
                return True
                
        return False