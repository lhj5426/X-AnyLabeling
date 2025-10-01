"""This module defines Canvas widget - the core component for drawing image labels"""

import math
from copy import deepcopy
from typing import List, Optional, Union, Any
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QWheelEvent

from anylabeling.services.auto_labeling.types import AutoLabelingMode
from anylabeling.views.labeling.utils.colormap import label_colormap

from .. import utils
from ..shape import Shape

CURSOR_DEFAULT = QtCore.Qt.ArrowCursor
CURSOR_POINT = QtCore.Qt.PointingHandCursor  # 恢复为默认，用于顶点
CURSOR_DRAW = QtCore.Qt.CrossCursor
CURSOR_MOVE = None   # 将在Canvas初始化时创建 - 拖拽矩形本体时
CURSOR_GRAB = None   # 将在Canvas初始化时创建 - 接触矩形本体时
CURSOR_ROTATION3 = None  # 将在Canvas初始化时创建 - rotation3模式专用

# 自定义鼠标指针路径
CUSTOM_CURSOR_GRAB_PATH = r"J:\文件夹存放\鼠标指针文件\1111\GoogleDot-Blue-Windows\Arrow.cur"
CUSTOM_CURSOR_MOVE_PATH = r"J:\文件夹存放\鼠标指针文件\1111\GoogleDot-Blue-Windows\Link.cur"
CUSTOM_CURSOR_ROTATION3_PATH = r"J:\Downloads\鼠标指针X个\Cyan Ring\Cross.cur"

AUTO_DECODE_DELAY_MS = 100
MAX_AUTO_DECODE_MARKS = 42
AUTO_DECODE_MOVE_THRESHOLD = 5.0
MOVE_SPEED = 0.5
LARGE_ROTATION_INCREMENT = 0.0087
SMALL_ROTATION_INCREMENT = 0.001745

LABEL_COLORMAP = label_colormap()


def get_overlap_color(config: dict) -> QtGui.QColor:
    """
    Get the overlap color from configuration settings.

    This function retrieves the overlap color configuration from the application
    settings and returns a QColor object. The overlap color is used to highlight
    areas where multiple shapes of the same label overlap on the canvas.

    Args:
        config (dict): Configuration dictionary containing shape settings.
            Should have structure: config["shape"]["overlap_color"] = [R, G, B, A]

    Returns:
        QtGui.QColor: Color object for rendering shape overlaps with RGBA values.

    Examples:
        >>> config = {"shape": {"overlap_color": [255, 165, 0, 120]}}
        >>> color = get_overlap_color(config)
        >>> print(color.red(), color.green(), color.blue(), color.alpha())
        # Output: 255 165 0 120

    Note:
        If overlap_color is not found in config, returns default orange color.
        Color values should be in range 0-255 for RGB and alpha components.
    """
    try:
        overlap_rgba = config.get("shape", {}).get("overlap_color", [255, 165, 0, 120])
        return QtGui.QColor(*overlap_rgba)
    except (KeyError, TypeError, ValueError):
        # Fallback to default orange color if config is malformed
        return QtGui.QColor(255, 165, 0, 120)


class Canvas(
    QtWidgets.QWidget
):  # pylint: disable=too-many-public-methods, too-many-instance-attributes
    """Canvas widget to handle label drawing"""

    zoom_request = QtCore.pyqtSignal(int, QtCore.QPoint)
    scroll_request = QtCore.pyqtSignal(float, int, int)
    # [Feature] support for automatically switching to editing mode
    # when the cursor moves over an object
    mode_changed = QtCore.pyqtSignal()
    new_shape = QtCore.pyqtSignal()
    show_shape = QtCore.pyqtSignal(int, int, QtCore.QPointF)
    selection_changed = QtCore.pyqtSignal(list)
    shape_moved = QtCore.pyqtSignal()
    shape_rotated = QtCore.pyqtSignal()
    drawing_polygon = QtCore.pyqtSignal(bool)
    vertex_selected = QtCore.pyqtSignal(bool)
    auto_labeling_marks_updated = QtCore.pyqtSignal(list)
    auto_decode_requested = QtCore.pyqtSignal(list)
    auto_decode_finish_requested = QtCore.pyqtSignal()
    shape_hover_changed = QtCore.pyqtSignal()  # 新增信号：形状hover状态变化

    CREATE, EDIT = 0, 1

    # polygon, rectangle, rotation, line, or point
    _create_mode = "polygon"

    _fill_drawing = False

    def __init__(self, *args, **kwargs):
        """
        Initialize the Canvas widget with configuration and interaction settings.

        This constructor sets up the canvas for image labeling with customizable
        parameters for interaction behavior, shape editing, and visual appearance.
        It initializes the drawing state, input handling, and rendering settings.

        Args:
            *args: Variable length argument list passed to parent QWidget.
            **kwargs: Arbitrary keyword arguments including:
                epsilon (float): Mouse sensitivity for shape selection (default: 10.0).
                double_click (str): Double-click behavior - None or "close" (default: "close").
                num_backups (int): Number of shape state backups to maintain (default: 10).
                wheel_rectangle_editing (dict): Settings for mouse wheel rectangle editing.
                config (dict): Application configuration dictionary for colors and settings.
                parent: Parent widget reference for accessing application state.

        Returns:
            None

        Examples:
            >>> canvas = Canvas(
            ...     epsilon=15.0,
            ...     double_click="close",
            ...     config={"shape": {"overlap_color": [255, 0, 0, 100]}},
            ...     parent=main_window
            ... )

        Note:
            The config parameter is used to customize overlap colors and other
            visual settings. If not provided, default values are used.
        """
        self.epsilon = kwargs.pop("epsilon", 10.0)
        self.double_click = kwargs.pop("double_click", "close")
        if self.double_click not in [None, "close"]:
            raise ValueError(
                f"Unexpected value for double_click event: {self.double_click}"
            )
        self.num_backups = kwargs.pop("num_backups", 10)
        self.wheel_rectangle_editing = kwargs.pop(
            "wheel_rectangle_editing", {}
        )
        self.enable_wheel_rectangle_editing = self.wheel_rectangle_editing.get(
            "enable", False
        )
        self.rect_adjust_step = self.wheel_rectangle_editing.get(
            "adjust_step", 2.0
        )
        self.rect_scale_step = self.wheel_rectangle_editing.get(
            "scale_step", 2.0
        )
        self.fast_rect_adjust_step = self.wheel_rectangle_editing.get(
            "fast_adjust_step", 10.0
        )
        self.parent = kwargs.pop("parent")
        
        # Get configuration for colors and settings
        self._config = kwargs.pop("config", {})
        
        # Initialize overlap color from configuration
        self.overlap_color = get_overlap_color(self._config)
        # Initialize overlap display toggle (default: enabled)
        self.show_overlap = True
        
        super().__init__(*args, **kwargs)
        # Initialise local state.
        self.mode = self.EDIT
        self.is_auto_labeling = False
        self.is_move_editing = False
        self.auto_labeling_mode: AutoLabelingMode = None
        self.shapes = []
        self.shapes_backups = []
        self.current = None
        self.selected_shapes = []  # save the selected shapes here
        self.selected_shapes_copy = []

        # Alt+drag selection box state
        self.selection_box_mode = False
        self.selection_box_start = QtCore.QPoint()
        self.selection_box_end = QtCore.QPoint()
        self.selection_box = None

        # Shift+drag path selection state
        self.path_selection_mode = False
        self.path_selection_points = []
        self.path_highlighted_shapes = set()  # Shapes highlighted during path selection
        # self.line represents:
        #   - create_mode == 'polygon': edge from last point to current
        #   - create_mode == 'rectangle': diagonal line of the rectangle
        #   - create_mode == 'line': the line
        #   - create_mode == 'point': the point
        self.line = Shape()
        # For rotation3 mode: store the center line (from green dot to red arrow)
        self.center_line = Shape()
        self.prev_point = QtCore.QPoint()
        self.prev_pan_point = QtCore.QPoint()
        self.prev_move_point = QtCore.QPoint()
        self.offsets = QtCore.QPointF(), QtCore.QPointF()
        self.scale = 1.0
        self.pixmap = QtGui.QPixmap()
        self.visible = {}
        self._hide_backround = False
        self.hide_backround = False
        self.h_hape = None
        self.prev_h_shape = None
        self.h_vertex = None
        self.prev_h_vertex = None
        self.h_edge = None
        self.prev_h_edge = None
        self.moving_shape = False
        self.rotating_shape = False
        self.snapping = True
        self.h_shape_is_selected = False
        self.h_shape_is_hovered = None
        self.allowed_oop_shape_types = ["rotation"]
        self._painter = QtGui.QPainter()
        self._cursor = CURSOR_DEFAULT
        
        # 初始化自定义鼠标指针
        self._init_custom_cursors()
        # Menus:
        # 0: right-click without selection and dragging of shapes
        # 1: right-click with selection and dragging of shapes
        self.menus = (QtWidgets.QMenu(), QtWidgets.QMenu())
        # Set widget options.
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.WheelFocus)
        self.show_groups = False
        self.show_texts = True
        self.show_labels = True
        self.show_scores = True
        self.show_degrees = False
        self.show_attributes = True
        self.show_linking = True
        self.show_order = True

        # Set cross line options.
        self.cross_line_show = True
        self.cross_line_width = 2.0
        self.cross_line_color = "#00FF00"
        self.cross_line_opacity = 0.5
        self.cross_line_style = "dash"  # "solid" or "dash"

        self.is_loading = False
        self.loading_text = self.tr("Loading...")
        self.loading_angle = 0

        # Auto mask decode mode
        self.auto_decode_mode = False
        self.auto_decode_timer = QTimer()
        self.auto_decode_timer.timeout.connect(self.on_auto_decode_timeout)
        self.auto_decode_timer.setSingleShot(True)
        self.auto_decode_tracklet = []
        self.last_mouse_pos = None

    def set_loading(self, is_loading: bool, loading_text: Optional[str] = None) -> None:
        """
        Set the canvas loading state with optional loading text.

        This method controls the loading display state of the canvas, showing
        a loading indicator and optional text message to users. When enabled,
        the canvas displays loading feedback instead of normal content.

        Args:
            is_loading (bool): Whether to show loading state (True) or normal state (False).
            loading_text (Optional[str]): Custom loading message to display.
                If None, uses the existing loading_text or a default message.

        Returns:
            None

        Examples:
            >>> # Show loading with default text
            >>> canvas.set_loading(True)
            
            >>> # Show loading with custom message
            >>> canvas.set_loading(True, "Processing image...")
            
            >>> # Hide loading state
            >>> canvas.set_loading(False)
            
        Note:
            Automatically triggers a canvas repaint to show/hide the loading display.
            Loading state blocks normal canvas interaction until disabled.
        """
        self.is_loading = is_loading
        if loading_text:
            self.loading_text = loading_text
        self.update()

    def set_auto_labeling_mode(self, mode: AutoLabelingMode) -> None:
        """
        Set the auto-labeling mode for automated shape detection and creation.

        This method configures the canvas for automatic labeling functionality,
        enabling AI-powered shape detection and creation. It switches between
        manual and automatic labeling modes with appropriate UI updates.

        Args:
            mode (AutoLabelingMode): The auto-labeling mode to activate:
                - AutoLabelingMode.NONE: Disable auto-labeling, return to manual mode
                - Other modes: Enable auto-labeling with specific shape types

        Returns:
            None

        Examples:
            >>> from anylabeling.services.auto_labeling.types import AutoLabelingMode
            >>> 
            >>> # Enable auto-labeling for rectangles
            >>> canvas.set_auto_labeling_mode(AutoLabelingMode.RECTANGLE)
            >>> 
            >>> # Disable auto-labeling
            >>> canvas.set_auto_labeling_mode(AutoLabelingMode.NONE)
            
        Note:
            When enabled, automatically switches to the appropriate drawing mode
            and notifies the parent widget to update the UI accordingly.
        """
        if mode == AutoLabelingMode.NONE:
            self.is_auto_labeling = False
            self.auto_labeling_mode = mode
        else:
            self.is_auto_labeling = True
            self.auto_labeling_mode = mode
            self.create_mode = mode.shape_type
            self.parent.toggle_draw_mode(
                False, mode.shape_type, disable_auto_labeling=False
            )

    def set_auto_decode_mode(self, enabled: bool):
        """Set auto decode mode"""
        if self.auto_decode_mode and not enabled:
            self.reset_auto_decode_state()
        self.auto_decode_mode = enabled

    def reset_auto_decode_state(self):
        """Reset auto decode state"""
        if self.auto_decode_timer.isActive():
            self.auto_decode_timer.stop()
        self.auto_decode_tracklet.clear()
        self.last_mouse_pos = None

    def fill_drawing(self):
        """Get option to fill shapes by color"""
        return self._fill_drawing

    def set_fill_drawing(self, value):
        """Set shape filling option"""
        self._fill_drawing = value

    @property
    def create_mode(self):
        """Create mode for canvas - Modes: polygon, rectangle, rotation, circle,..."""
        return self._create_mode

    @create_mode.setter
    def create_mode(self, value):
        """Set create mode for canvas"""
        if value not in [
            "polygon",
            "rectangle",
            "rotation",
            "rotation3",
            "circle",
            "line",
            "point",
            "linestrip",
        ]:
            raise ValueError(f"Unsupported create_mode: {value}")
        self._create_mode = value

        # Set custom cursor for rotation3 mode
        if value == "rotation3":
            self.un_highlight()
            self.setCursor(CURSOR_ROTATION3)

    def store_shapes(self):
        """Store shapes for restoring later (Undo feature)"""
        shapes_backup = []
        for shape in self.shapes:
            shapes_backup.append(shape.copy())
        if len(self.shapes_backups) > self.num_backups:
            self.shapes_backups = self.shapes_backups[-self.num_backups - 1 :]
        self.shapes_backups.append(shapes_backup)

    def store_moving_shape(self):
        """Store a moving shape"""
        if self.moving_shape:
            moving_shapes = (
                [self.h_hape] + self.selected_shapes
                if self.h_hape and self.h_hape not in self.selected_shapes
                else self.selected_shapes.copy()
            )
            for shape in moving_shapes:
                if shape in self.shapes:
                    index = self.shapes.index(shape)
                    if (
                        len(self.shapes_backups) > 0
                        and index < len(self.shapes_backups[-1])
                        and self.shapes_backups[-1][index].points
                        != self.shapes[index].points
                    ):
                        self.store_shapes()
                        self.shape_moved.emit()
                        break

            self.moving_shape = False

    @property
    def is_shape_restorable(self):
        """Check if shape can be restored from backup"""
        # We save the state AFTER each edit (not before) so for an
        # edit to be undoable, we expect the CURRENT and the PREVIOUS state
        # to be in the undo stack.
        if len(self.shapes_backups) < 2:
            return False
        return True

    def restore_shape(self):
        """Restore/Undo a shape"""
        # This does _part_ of the job of restoring shapes.
        # The complete process is also done in app.py::undoShapeEdit
        # and app.py::load_shapes and our own Canvas::load_shapes function.
        if not self.is_shape_restorable:
            return
        self.shapes_backups.pop()  # latest

        # The application will eventually call Canvas.load_shapes which will
        # push this right back onto the stack.
        shapes_backup = self.shapes_backups.pop()
        self.shapes = shapes_backup
        self.selected_shapes = []
        for shape in self.shapes:
            shape.selected = False
        self.update()

    def enterEvent(self, _):
        """Mouse enter event"""
        self.override_cursor(self._cursor)

    def leaveEvent(self, _):
        """Mouse leave event"""
        self.store_moving_shape()
        self.un_highlight()
        # 发射hover状态变化信号
        self.shape_hover_changed.emit()
        self.restore_cursor()

    def focusOutEvent(self, _):
        """Window out of focus event"""
        self.restore_cursor()

    def is_visible(self, shape: Shape) -> bool:
        """
        Check if a shape should be visible based on current display settings.

        This method determines whether a shape should be rendered on the canvas
        by checking the current visibility mode and the shape's properties.
        It supports different visibility modes for showing/hiding shapes.

        Args:
            shape (Shape): The shape to check for visibility.

        Returns:
            bool: True if the shape should be displayed, False otherwise.

        Examples:
            >>> shape = Shape(label="cat")
            >>> if canvas.is_visible(shape):
            ...     # Shape will be rendered
            ...     canvas.draw_shape(shape)
            
        Note:
            Visibility can be controlled by various factors including shape
            properties, current mode settings, and user preferences.
        """
        return self.visible.get(shape, True)

    def drawing(self) -> bool:
        """
        Check if the canvas is currently in drawing mode.

        This property indicates whether the user is actively drawing a new shape.
        Drawing mode is active when creating new shapes but not when editing
        existing shapes or in selection mode.

        Returns:
            bool: True if currently drawing a new shape, False otherwise.

        Examples:
            >>> if canvas.drawing():
            ...     print("User is creating a new shape")
            >>> else:
            ...     print("User is in selection or edit mode")
            
        Note:
            Drawing mode affects cursor appearance, available actions, and
            how mouse events are interpreted by the canvas.
        """
        return self.mode == self.CREATE

    def editing(self) -> bool:
        """
        Check if the canvas is currently in editing mode.

        This property indicates whether the user is editing an existing shape,
        such as moving vertices, resizing, or repositioning shapes. Editing
        mode is distinct from drawing mode and selection mode.

        Returns:
            bool: True if currently editing a shape, False otherwise.

        Examples:
            >>> if canvas.editing():
            ...     print("User is modifying an existing shape")
            ...     # Enable vertex manipulation tools
            >>> else:
            ...     print("User is not editing")
            
        Note:
            Editing mode enables vertex highlighting, shape manipulation,
            and other editing-specific interactions with existing shapes.
        """
        return self.mode == self.EDIT

    def set_auto_labeling(self, value=True):
        """Set auto labeling mode"""
        self.is_auto_labeling = value
        if self.auto_labeling_mode is None:
            self.auto_labeling_mode = AutoLabelingMode.NONE
            self.parent.toggle_draw_mode(
                True, "rectangle", disable_auto_labeling=True
            )

    def update_overlap_color(self, config: dict) -> None:
        """
        Update the overlap color from new configuration settings.

        This method updates the canvas overlap color when configuration changes,
        allowing real-time customization of overlap visualization without
        requiring application restart.

        Args:
            config (dict): Updated configuration dictionary containing shape settings.
                Should have structure: config['shape']['overlap_color'] = [R, G, B, A]

        Returns:
            None

        Examples:
            >>> new_config = {'shape': {'overlap_color': [255, 0, 0, 150]}}
            >>> canvas.update_overlap_color(new_config)
            >>> canvas.update()  # Trigger repaint to show new color

        Note:
            Automatically triggers a canvas repaint to apply the new overlap color.
            Should be called when user changes overlap color in settings.
        """
        self.overlap_color = get_overlap_color(config)
        self.update()  # Trigger repaint with new color

    def toggle_overlap_display(self) -> None:
        """
        Toggle the display of overlap regions on/off.

        This method switches the visibility of shape overlap highlighting
        and triggers a canvas repaint to apply the change immediately.

        Returns:
            None

        Example:
            >>> canvas.toggle_overlap_display()  # Toggles current state

        Note:
            The overlap display state is stored in self.show_overlap.
            When disabled, overlap regions are not drawn during paintEvent.
        """
        self.show_overlap = not self.show_overlap
        self.update()  # Trigger repaint

    def get_mode(self):
        """Get current mode"""
        if (
            self.is_auto_labeling
            and self.auto_labeling_mode != AutoLabelingMode.NONE
        ):
            return self.tr("Auto Labeling")
        if self.mode == self.CREATE:
            return self.tr("Drawing")
        elif self.mode == self.EDIT:
            return self.tr("Editing")
        else:
            return self.tr("Unknown")

    def set_editing(self, value=True):
        """Set editing mode. Editing is set to False, user is drawing"""
        self.mode = self.EDIT if value else self.CREATE
        if not value:  # Create
            self.un_highlight()
            self.deselect_shape()
            self.is_move_editing = False
            # 发射hover状态变化信号
            self.shape_hover_changed.emit()

    def un_highlight(self):
        """Unhighlight shape/vertex/edge"""
        if self.h_hape:
            self.h_hape.highlight_clear()
            self.update()
        self.prev_h_shape = self.h_hape
        self.prev_h_vertex = self.h_vertex
        self.prev_h_edge = self.h_edge
        self.h_hape = self.h_vertex = self.h_edge = None
        for shape in self.shapes:
            shape.is_hovered = False

    def selected_vertex(self):
        """Check if selected a vertex"""
        return self.h_vertex is not None

    def selected_edge(self):
        """Check if selected an edge"""
        return self.h_edge is not None

    def _should_trigger_auto_decode(self, pos):
        """Check if mouse movement exceeds threshold to trigger auto decode"""
        if not self.auto_decode_tracklet:
            return True

        last_point = self.auto_decode_tracklet[-1]["data"]
        distance = (
            (pos.x() - last_point[0]) ** 2 + (pos.y() - last_point[1]) ** 2
        ) ** 0.5
        return distance >= AUTO_DECODE_MOVE_THRESHOLD

    # QT Overload
    def mouseMoveEvent(self, ev):  # noqa: C901
        """Update line with last point and current coordinates"""
        if self.is_loading:
            return
        try:
            pos = self.transform_pos(ev.localPos())
        except AttributeError:
            return

        # Handle Alt+drag selection box mode
        if self.selection_box_mode:
            self.selection_box_end = pos
            self.repaint()
            return

        # Handle Shift+drag path selection mode
        if self.path_selection_mode:
            self.path_selection_points.append(pos)
            # Check if path intersects any shapes and highlight them
            self.update_path_highlights()
            self.repaint()
            return

        # 记录hover状态变化前的状态
        prev_hover_shape = self.h_hape

        self.prev_move_point = pos
        self.repaint()

        # Handle auto decode mode
        if (
            self.auto_decode_mode
            and self.is_auto_labeling
            and self.auto_decode_tracklet
        ):
            if self._should_trigger_auto_decode(pos):
                self.last_mouse_pos = pos
                if not self.auto_decode_timer.isActive():
                    self.auto_decode_timer.start(AUTO_DECODE_DELAY_MS)

        # Polygon drawing.
        if self.drawing():
            line_color = utils.hex_to_rgb(self.cross_line_color)
            self.line.line_color = QtGui.QColor(*line_color)
            # For rotation3, keep line as line type, not rotation3
            if self.create_mode == "rotation3":
                self.line.shape_type = "line"
            else:
                self.line.shape_type = self.create_mode

            if not self.current:
                # Use rotation3 custom cursor if in rotation3 mode
                cursor = CURSOR_ROTATION3 if self.create_mode == "rotation3" else CURSOR_DRAW
                self.override_cursor(cursor)
                return

            if self.create_mode == "rectangle":
                shape_width = int(abs(self.current[0].x() - pos.x()))
                shape_height = int(abs(self.current[0].y() - pos.y()))
                self.show_shape.emit(shape_width, shape_height, pos)

            color = QtGui.QColor(0, 0, 255)
            if (
                self.out_off_pixmap(pos)
                and self.create_mode not in self.allowed_oop_shape_types
            ):
                # Don't allow the user to draw outside the pixmap, except for rotation.
                # Project the point to the pixmap's edges.
                pos = self.intersection_point(self.current[-1], pos)
            elif (
                self.snapping
                and len(self.current) > 1
                and self.create_mode == "polygon"
                and self.close_enough(pos, self.current[0])
            ):
                # Attract line to starting point and
                # colorise to alert the user.
                pos = self.current[0]
                self.override_cursor(CURSOR_POINT)
                self.current.highlight_vertex(0, Shape.NEAR_VERTEX)
            elif (
                self.create_mode == "rotation"
                and len(self.current) > 0
                and self.close_enough(pos, self.current[0])
            ):
                pos = self.current[0]
                color = self.current.line_color
                self.override_cursor(CURSOR_POINT)
                self.current.highlight_vertex(0, Shape.NEAR_VERTEX)
            else:
                # Use rotation3 custom cursor if in rotation3 mode
                cursor = CURSOR_ROTATION3 if self.create_mode == "rotation3" else CURSOR_DRAW
                self.override_cursor(cursor)
            if self.create_mode in ["polygon", "linestrip"]:
                self.line[0] = self.current[-1]
                self.line[1] = pos
            elif self.create_mode == "rectangle":
                self.line.points = [self.current[0], pos]
                self.line.close()
            elif self.create_mode == "rotation":
                self.line[1] = pos
                self.line.line_color = color
            elif self.create_mode == "rotation3":
                # For rotation3 mode with three clicks
                if len(self.current.points) == 1:
                    # After first click: draw center line from start to cursor
                    self.line[0] = self.current[0]
                    self.line[1] = pos
                elif len(self.current.points) == 2:
                    # After second click: keep center line and draw width line
                    # The width line MUST be perpendicular to the center line

                    # Store center line (from green dot to red arrow)
                    self.center_line.points = [self.current[0], self.current[1]]
                    self.center_line.shape_type = "line"
                    self.center_line.line_color = color

                    # Calculate perpendicular direction
                    p0 = self.current[0]
                    p1 = self.current[1]

                    # Direction vector of center line
                    dx = p1.x() - p0.x()
                    dy = p1.y() - p0.y()

                    # Perpendicular vector (rotate 90 degrees)
                    perp_x = -dy
                    perp_y = dx

                    # Normalize perpendicular vector
                    perp_length = math.sqrt(perp_x**2 + perp_y**2)
                    if perp_length > 0:
                        perp_x /= perp_length
                        perp_y /= perp_length

                    # Project mouse position onto perpendicular line
                    # Vector from p1 to mouse
                    mouse_vec_x = pos.x() - p1.x()
                    mouse_vec_y = pos.y() - p1.y()

                    # Project onto perpendicular direction
                    projection = mouse_vec_x * perp_x + mouse_vec_y * perp_y

                    # Calculate constrained position (perpendicular to center line)
                    constrained_x = p1.x() + projection * perp_x
                    constrained_y = p1.y() + projection * perp_y
                    constrained_pos = QtCore.QPointF(constrained_x, constrained_y)

                    # Draw width line from arrow to constrained position
                    self.line[0] = self.current[1]  # Start from arrow position
                    self.line[1] = constrained_pos  # End at perpendicular point
                self.line.line_color = color
            elif self.create_mode == "circle":
                self.line.points = [self.current[0], pos]
                self.line.shape_type = "circle"
            elif self.create_mode == "line":
                self.line.points = [self.current[0], pos]
                self.line.close()
            elif self.create_mode == "point":
                self.line.points = [self.current[0]]
                self.line.close()
            self.repaint()
            self.current.highlight_clear()
            return

        # Polygon copy moving.
        if QtCore.Qt.RightButton & ev.buttons():
            if self.selected_shapes_copy and self.prev_point:
                self.override_cursor(CURSOR_MOVE)
                self.bounded_move_shapes(self.selected_shapes_copy, pos)
                self.repaint()
            elif self.selected_shapes:
                self.selected_shapes_copy = [
                    s.copy() for s in self.selected_shapes
                ]
                self.repaint()
            return

        # Polygon/Vertex moving.
        if QtCore.Qt.LeftButton & ev.buttons():
            if self.selected_vertex():
                self.is_move_editing = False
                try:
                    self.bounded_move_vertex(pos)
                    self.repaint()
                    self.moving_shape = True
                except IndexError:
                    return
                if self.h_hape.shape_type == "rectangle":
                    p1 = self.h_hape[0]
                    p2 = self.h_hape[2]
                    shape_width = int(abs(p2.x() - p1.x()))
                    shape_height = int(abs(p2.y() - p1.y()))
                    self.show_shape.emit(shape_width, shape_height, pos)
            elif self.selected_shapes and self.prev_point:
                self.override_cursor(CURSOR_MOVE)
                self.bounded_move_shapes(self.selected_shapes, pos)
                self.repaint()
                self.moving_shape = True
                if self.selected_shapes[-1].shape_type == "rectangle":
                    p1 = self.selected_shapes[-1][0]
                    p2 = self.selected_shapes[-1][2]
                    shape_width = int(abs(p2.x() - p1.x()))
                    shape_height = int(abs(p2.y() - p1.y()))
                    self.show_shape.emit(shape_width, shape_height, pos)
            else:
                if (
                    self.pixmap
                    and self.pixmap.width()
                    and self.pixmap.height()
                ):
                    self.override_cursor(CURSOR_MOVE)
                    delta = ev.localPos() - self.prev_pan_point
                    self.scroll_request.emit(
                        delta.x() / (self.pixmap.width() * self.scale),
                        Qt.Horizontal,
                        1,
                    )
                    self.scroll_request.emit(
                        delta.y() / (self.pixmap.height() * self.scale),
                        Qt.Vertical,
                        1,
                    )
                    self.repaint()
            return

        if self.editing() and self.is_move_editing:
            self.override_cursor(CURSOR_MOVE)
            if self.selected_vertex():
                try:
                    self.bounded_move_vertex(pos)
                    self.repaint()
                    self.moving_shape = True
                except IndexError:
                    return
                if self.h_hape.shape_type == "rectangle":
                    p1 = self.h_hape[0]
                    p2 = self.h_hape[2]
                    shape_width = int(abs(p2.x() - p1.x()))
                    shape_height = int(abs(p2.y() - p1.y()))
                    self.show_shape.emit(shape_width, shape_height, pos)
            else:
                self.is_move_editing = False

            return

        self.show_shape.emit(-1, -1, pos)

        # Just hovering over the canvas, 2 possibilities:
        # - Highlight shapes
        # - Highlight vertex
        # Update shape/vertex fill and tooltip value accordingly.
        self.setToolTip(self.tr(""))
        
        # 首先清除所有形状的hover状态，确保只有一个形状被hover
        for shape in self.shapes:
            shape.is_hovered = False
            
        for shape in reversed([s for s in self.shapes if self.is_visible(s)]):
            # Look for a nearby vertex to highlight. If that fails,
            # check if we happen to be inside a shape.
            index = shape.nearest_vertex(pos, self.epsilon / self.scale)
            index_edge = shape.nearest_edge(pos, self.epsilon / self.scale)
            if index is not None:
                if self.selected_vertex():
                    self.h_hape.highlight_clear()
                self.prev_h_vertex = self.h_vertex = index
                self.prev_h_shape = self.h_hape = shape
                self.prev_h_edge = self.h_edge
                self.h_edge = None
                shape.highlight_vertex(index, shape.MOVE_VERTEX)
                self.override_cursor(CURSOR_POINT)
# # #                 self.setToolTip(
# # #                     self.tr("Click & drag to move point of shape '%s'")
# # #                     % shape.label
# # #                 )
                self.setStatusTip(self.toolTip())
                self.update()
                break
            if index_edge is not None and shape.can_add_point():
                if self.selected_vertex():
                    self.h_hape.highlight_clear()
                self.prev_h_vertex = self.h_vertex
                self.h_vertex = None
                self.prev_h_shape = self.h_hape = shape
                self.prev_h_edge = self.h_edge = index_edge
                self.override_cursor(CURSOR_POINT)
# # #                 self.setToolTip(
# # #                     self.tr("Click to create point of shape '%s'")
# # #                     % shape.label
# # #                 )
                self.setStatusTip(self.toolTip())
                self.update()
                break
            if len(shape.points) > 1 and shape.contains_point(pos):
                if self.selected_vertex():
                    self.h_hape.highlight_clear()
                self.prev_h_vertex = self.h_vertex
                self.h_vertex = None
                self.prev_h_shape = self.h_hape = shape
                self.prev_h_edge = self.h_edge
                self.h_edge = None
#                 if shape.group_id and shape.shape_type == "rectangle":
#                     tooltip_text = "Click & drag to move shape '{label} {group_id}'".format(
#                         label=shape.label, group_id=shape.group_id
#                     )
#                     self.setToolTip(self.tr(tooltip_text))
#                 else:
#                     self.setToolTip(
#                         self.tr("Click & drag to move shape '%s'")
#                         % shape.label
#                     )
                self.setStatusTip(self.toolTip())
                self.override_cursor(CURSOR_GRAB)
                shape.is_hovered = True
                # [Feature] Automatically highlight shape when the mouse is moved inside it
                if self.h_shape_is_hovered:
                    group_mode = (
                        int(ev.modifiers()) == QtCore.Qt.ControlModifier
                    )
                    self.select_shape_point(
                        pos, multiple_selection_mode=group_mode
                    )
                self.update()

                if shape.shape_type == "rectangle":
                    p1 = self.h_hape[0]
                    p2 = self.h_hape[2]
                    shape_width = int(abs(p2.x() - p1.x()))
                    shape_height = int(abs(p2.y() - p1.y()))
                    self.show_shape.emit(shape_width, shape_height, pos)
                break
        else:  # Nothing found, clear highlights, reset state.
            self.un_highlight()
            self.override_cursor(CURSOR_DEFAULT)
        self.vertex_selected.emit(self.h_vertex is not None)
        
        # 检查hover状态是否发生变化，如果变化则发射信号
        if prev_hover_shape != self.h_hape:
            self.shape_hover_changed.emit()

    def add_point_to_edge(self):
        """Add a point to current shape"""
        shape = self.prev_h_shape
        index = self.prev_h_edge
        point = self.prev_move_point
        if shape is None or index is None or point is None:
            return
        shape.insert_point(index, point)
        shape.highlight_vertex(index, shape.MOVE_VERTEX)
        self.h_hape = shape
        self.h_vertex = index
        self.h_edge = None
        self.moving_shape = True

    def remove_selected_point(self):
        """Remove a point from current shape"""
        shape = self.prev_h_shape
        index = self.prev_h_vertex
        if shape is None or index is None:
            return
        shape.remove_point(index)
        shape.highlight_clear()
        self.h_hape = shape
        self.prev_h_vertex = None
        self.moving_shape = True  # Save changes

    def on_auto_decode_timeout(self):
        """Handle auto decode timeout"""
        if (
            not self.auto_decode_mode
            or self.auto_labeling_mode.shape_type != AutoLabelingMode.POINT
        ):
            return

        flag = -1
        if self.auto_labeling_mode.edit_mode == AutoLabelingMode.ADD:
            flag = 1
        elif self.auto_labeling_mode.edit_mode == AutoLabelingMode.REMOVE:
            flag = 0
        if flag == -1:
            return

        if self.auto_decode_mode and self.last_mouse_pos:
            if len(self.auto_decode_tracklet) >= MAX_AUTO_DECODE_MARKS:
                self.auto_decode_tracklet.pop(0)

            marks = {
                "type": "point",
                "data": [
                    int(self.last_mouse_pos.x()),
                    int(self.last_mouse_pos.y()),
                ],
                "label": flag,
            }
            self.auto_decode_tracklet.append(marks)
            self.auto_decode_requested.emit(self.auto_decode_tracklet)

    # QT Overload
    def mousePressEvent(self, ev):  # noqa: C901
        """Mouse press event"""
        if self.is_loading:
            return
        pos = self.transform_pos(ev.localPos())

        # Alt+drag selection box mode
        if (ev.button() == QtCore.Qt.LeftButton and
            ev.modifiers() & QtCore.Qt.AltModifier and
            not self.drawing()):
            self.selection_box_mode = True
            self.selection_box_start = pos
            self.selection_box_end = pos
            return

        # Shift+drag path selection mode
        if (ev.button() == QtCore.Qt.LeftButton and
            ev.modifiers() & QtCore.Qt.ShiftModifier and
            not self.drawing()):
            self.path_selection_mode = True
            self.path_selection_points = [pos]
            self.path_highlighted_shapes = set()
            return

        if ev.button() == QtCore.Qt.LeftButton:
            if self.drawing():
                if self.current:
                    # Add point to existing shape.
                    if self.create_mode == "polygon":
                        self.current.add_point(self.line[1])
                        self.line[0] = self.current[-1]
                        if self.current.is_closed():
                            self.finalise()
                    elif self.create_mode in ["circle", "line"]:
                        assert len(self.current.points) == 1
                        self.current.points = self.line.points
                        self.finalise()
                    elif self.create_mode == "rectangle":
                        if self.current.reach_max_points() is False:
                            init_pos = self.current[0]
                            min_x = init_pos.x()
                            min_y = init_pos.y()
                            target_pos = self.line[1]
                            max_x = target_pos.x()
                            max_y = target_pos.y()
                            self.current.add_point(
                                QtCore.QPointF(max_x, min_y)
                            )
                            self.current.add_point(target_pos)
                            self.current.add_point(
                                QtCore.QPointF(min_x, max_y)
                            )
                            self.finalise()
                    elif self.create_mode == "rotation":
                        # Original two-click rotation rectangle
                        initPos = self.current[0]
                        minX = initPos.x()
                        minY = initPos.y()
                        targetPos = self.line[1]
                        maxX = targetPos.x()
                        maxY = targetPos.y()
                        self.current.add_point(QtCore.QPointF(maxX, minY))
                        self.current.add_point(targetPos)
                        self.current.add_point(QtCore.QPointF(minX, maxY))
                        self.current.add_point(initPos)
                        self.line[0] = self.current[-1]
                        if self.current.is_closed():
                            self.finalise()
                    elif self.create_mode == "rotation3":
                        # Three-click rotation rectangle creation
                        # Click 1: Start point (green dot)
                        # Click 2: End point of center line (arrow)
                        # Click 3: Width line from arrow position

                        if len(self.current.points) == 1:
                            # Second click: add end point of center line
                            self.current.add_point(self.line[1])
                            # Update line to start from the arrow (end point)
                            self.line[0] = self.current[-1]
                            self.line[1] = self.current[-1]
                        elif len(self.current.points) == 2:
                            # Third click: create width line and complete rectangle
                            # User clicks 3 points to define 3 corners, we auto-calculate the 4th
                            # p0 = point 1 (green dot) - first corner
                            # p1 = point 2 (red arrow) - second corner
                            # p2 = point 3 (third click) - third corner
                            # p3 = point 4 (auto-calculated) - fourth corner

                            p0 = self.current[0]  # Point 1
                            p1 = self.current[1]  # Point 2
                            p2 = self.line[1]     # Point 3

                            # The fourth point completes the parallelogram:
                            # point4 = point1 + (point3 - point2)
                            # This creates: p0 -> p1 -> p2 -> p3 -> back to p0
                            p3 = p0 + (p2 - p1)

                            # Set corners in order: p0 -> p1 -> p2 -> p3
                            self.current.points = [p0, p1, p2, p3]
                            self.current.shape_type = "rotation"

                            # Calculate rotation angle (direction from p0 to p1)
                            dx = p1.x() - p0.x()
                            dy = p1.y() - p0.y()
                            angle = math.atan2(dy, dx)
                            # Normalize angle to 0-2π range (atan2 returns -π to π)
                            if angle < 0:
                                angle += 2 * math.pi
                            self.current.direction = angle

                            self.current.close()
                            self.finalise()
                    elif self.create_mode == "linestrip":
                        self.current.add_point(self.line[1])
                        self.line[0] = self.current[-1]
                        if int(ev.modifiers()) == QtCore.Qt.ControlModifier:
                            self.finalise()
                    # [Feature] support for automatically switching to editing mode
                    # when the cursor moves over an object
                    if (
                        self.create_mode
                        in ["rectangle", "rotation", "rotation3", "circle", "line", "point"]
                        and not self.is_auto_labeling
                        and not self.current
                    ):
                        self.prev_pan_point = ev.localPos()
                        self.mode_changed.emit()
                elif not self.out_off_pixmap(pos):
                    # Handle auto decode mode first click
                    if self.auto_decode_mode and self.is_auto_labeling:
                        if (
                            self.auto_labeling_mode.shape_type
                            == AutoLabelingMode.POINT
                        ):
                            self.last_mouse_pos = pos
                            self.on_auto_decode_timeout()
                            return

                    # Create new shape.
                    self.current = Shape(shape_type=self.create_mode)
                    self.current.add_point(pos)
                    if self.create_mode == "point":
                        self.finalise()
                    else:
                        if self.create_mode == "circle":
                            self.current.shape_type = "circle"
                        self.line.points = [pos, pos]
                        self.set_hiding()
                        self.drawing_polygon.emit(True)
                        self.update()
                elif (
                    self.out_off_pixmap(pos)
                    and self.create_mode in self.allowed_oop_shape_types
                ):
                    # Create new shape.
                    self.current = Shape(shape_type=self.create_mode)
                    self.current.add_point(pos)
                    self.line.points = [pos, pos]
                    self.set_hiding()
                    self.drawing_polygon.emit(True)
                    self.update()
            elif self.editing():
                if self.selected_edge():
                    self.add_point_to_edge()
                elif (
                    self.selected_vertex()
                    and int(ev.modifiers()) == QtCore.Qt.ShiftModifier
                    and self.h_hape.shape_type
                    not in ["rectangle", "rotation", "line"]
                ):
                    # Delete point if: left-click + SHIFT on a point
                    self.remove_selected_point()

                if self.selected_vertex():
                    self.is_move_editing = not self.is_move_editing
                    if self.is_move_editing:
                        self.override_cursor(CURSOR_MOVE)
                    else:
                        self.override_cursor(CURSOR_POINT)

                group_mode = int(ev.modifiers()) == QtCore.Qt.ControlModifier
                self.select_shape_point(
                    pos, multiple_selection_mode=group_mode
                )
                self.prev_point = pos
                self.prev_pan_point = ev.localPos()
                self.repaint()
        elif ev.button() == QtCore.Qt.RightButton and self.editing():
            group_mode = int(ev.modifiers()) == QtCore.Qt.ControlModifier
            if not self.selected_shapes or (
                self.h_hape is not None
                and self.h_hape not in self.selected_shapes
            ):
                self.select_shape_point(
                    pos, multiple_selection_mode=group_mode
                )
                self.repaint()
            self.prev_point = pos

    # QT Overload
    def mouseReleaseEvent(self, ev):
        """Mouse release event"""
        if self.is_loading:
            return

        # Handle Alt+drag selection box completion
        if self.selection_box_mode and ev.button() == QtCore.Qt.LeftButton:
            self.complete_selection_box()
            return

        # Handle Shift+drag path selection completion
        if self.path_selection_mode and ev.button() == QtCore.Qt.LeftButton:
            self.complete_path_selection()
            return
        if ev.button() == QtCore.Qt.RightButton:
            menu = self.menus[len(self.selected_shapes_copy) > 0]
            self.restore_cursor()
            if (
                not menu.exec_(self.mapToGlobal(ev.pos()))
                and self.selected_shapes_copy
            ):
                # Cancel the move by deleting the shadow copy.
                self.selected_shapes_copy = []
                self.repaint()
        elif ev.button() == QtCore.Qt.LeftButton:
            if self.editing():
                if (
                    self.h_hape is not None
                    and self.h_shape_is_selected
                    and not self.moving_shape
                ):
                    self.selection_changed.emit(
                        [x for x in self.selected_shapes if x != self.h_hape]
                    )

        self.store_moving_shape()

    def complete_selection_box(self):
        """Complete Alt+drag selection box and select shapes within the box"""
        if not self.selection_box_mode:
            return

        # Calculate selection rectangle
        x1, y1 = self.selection_box_start.x(), self.selection_box_start.y()
        x2, y2 = self.selection_box_end.x(), self.selection_box_end.y()

        # Ensure proper rectangle bounds
        min_x, max_x = min(x1, x2), max(x1, x2)
        min_y, max_y = min(y1, y2), max(y1, y2)
        selection_rect = QtCore.QRectF(min_x, min_y, max_x - min_x, max_y - min_y)

        # Find shapes that intersect with the selection box AND are visible
        selected_shapes = []
        for shape in self.shapes:
            # Only select visible shapes
            if shape.visible and self.shape_intersects_rect(shape, selection_rect):
                selected_shapes.append(shape)

        # Update selected shapes
        self.selected_shapes = selected_shapes
        self.selection_changed.emit(self.selected_shapes)

        # Reset selection box mode
        self.selection_box_mode = False
        self.repaint()

    def shape_intersects_rect(self, shape, rect):
        """Check if a shape intersects with the selection rectangle"""
        if not shape.points:
            return False

        # Method 1: Check if any point of the shape is inside the selection rectangle
        for point in shape.points:
            if rect.contains(point):
                return True

        # Method 2: Check if any point of the selection rectangle is inside the shape
        # This handles cases where the selection box is smaller than the shape
        rect_points = [
            QtCore.QPointF(rect.left(), rect.top()),
            QtCore.QPointF(rect.right(), rect.top()),
            QtCore.QPointF(rect.right(), rect.bottom()),
            QtCore.QPointF(rect.left(), rect.bottom())
        ]

        for rect_point in rect_points:
            if self.point_in_shape(rect_point, shape):
                return True

        # Method 3: Check bounding box intersection
        xs = [p.x() for p in shape.points]
        ys = [p.y() for p in shape.points]
        shape_rect = QtCore.QRectF(
            min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
        )

        return rect.intersects(shape_rect)

    def point_in_shape(self, point, shape):
        """Check if a point is inside a shape using ray casting algorithm"""
        if not shape.points or len(shape.points) < 3:
            return False

        x, y = point.x(), point.y()
        n = len(shape.points)
        inside = False

        p1x, p1y = shape.points[0].x(), shape.points[0].y()
        for i in range(1, n + 1):
            p2x, p2y = shape.points[i % n].x(), shape.points[i % n].y()
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y

        return inside

    def update_path_highlights(self):
        """Update highlighted shapes based on current path selection"""
        if not self.path_selection_points or len(self.path_selection_points) < 2:
            return

        # Check each shape to see if the path intersects it
        for shape in self.shapes:
            if not shape.visible:
                continue

            # Check if the latest path segment intersects this shape
            latest_start = self.path_selection_points[-2]
            latest_end = self.path_selection_points[-1]

            if self.path_intersects_shape(latest_start, latest_end, shape):
                self.path_highlighted_shapes.add(shape)

    def path_intersects_shape(self, start_point, end_point, shape):
        """Check if a path segment intersects with a shape"""
        if not shape.points or len(shape.points) < 2:
            return False

        # Check if path segment intersects any edge of the shape
        for i in range(len(shape.points)):
            shape_start = shape.points[i]
            shape_end = shape.points[(i + 1) % len(shape.points)]

            if self.line_segments_intersect(start_point, end_point, shape_start, shape_end):
                return True

        # Also check if the path passes through the shape
        if self.point_in_shape(start_point, shape) or self.point_in_shape(end_point, shape):
            return True

        return False

    def line_segments_intersect(self, p1, q1, p2, q2):
        """Check if two line segments intersect"""
        def orientation(p, q, r):
            val = (q.y() - p.y()) * (r.x() - q.x()) - (q.x() - p.x()) * (r.y() - q.y())
            if val == 0:
                return 0  # colinear
            return 1 if val > 0 else 2  # clockwise or counterclockwise

        def on_segment(p, q, r):
            return (q.x() <= max(p.x(), r.x()) and q.x() >= min(p.x(), r.x()) and
                    q.y() <= max(p.y(), r.y()) and q.y() >= min(p.y(), r.y()))

        o1 = orientation(p1, q1, p2)
        o2 = orientation(p1, q1, q2)
        o3 = orientation(p2, q2, p1)
        o4 = orientation(p2, q2, q1)

        # General case
        if o1 != o2 and o3 != o4:
            return True

        # Special cases
        if (o1 == 0 and on_segment(p1, p2, q1)) or \
           (o2 == 0 and on_segment(p1, q2, q1)) or \
           (o3 == 0 and on_segment(p2, p1, q2)) or \
           (o4 == 0 and on_segment(p2, q1, q2)):
            return True

        return False

    def complete_path_selection(self):
        """Complete Shift+drag path selection and select highlighted shapes"""
        if not self.path_selection_mode:
            return

        # Select all highlighted shapes
        selected_shapes = []
        for shape in self.path_highlighted_shapes:
            if shape.visible:
                selected_shapes.append(shape)

        # Update selected shapes
        self.selected_shapes = selected_shapes
        self.selection_changed.emit(self.selected_shapes)

        # Reset path selection mode
        self.path_selection_mode = False
        self.path_selection_points = []
        self.path_highlighted_shapes.clear()
        self.repaint()

    def update_path_highlights(self):
        """Update highlighted shapes based on current path"""
        if not self.path_selection_mode or len(self.path_selection_points) < 2:
            return

        # Clear previous highlights
        self.path_highlighted_shapes.clear()

        # Check each shape for intersection with the path
        for shape in self.shapes:
            if not shape.visible:
                continue

            if self.shape_intersects_path(shape, self.path_selection_points):
                self.path_highlighted_shapes.add(shape)

    def shape_intersects_path(self, shape, path_points):
        """Check if a shape intersects with the given path"""
        if len(path_points) < 2:
            return False

        # For each path segment, check if it intersects the shape
        for i in range(len(path_points) - 1):
            start = path_points[i]
            end = path_points[i + 1]

            if self.shape_intersects_line_segment(shape, start, end):
                return True

        return False

    def shape_intersects_line_segment(self, shape, line_start, line_end):
        """Check if a shape intersects with a line segment - only true intersection, not containment"""
        if shape.shape_type in ["rectangle", "rotation"]:
            # Only check if line intersects any edge of the rectangle - no containment check
            shape_points = shape.points
            for i in range(len(shape_points)):
                p1 = shape_points[i]
                p2 = shape_points[(i + 1) % len(shape_points)]
                if self.line_segments_intersect(line_start, line_end, p1, p2):
                    return True
            return False  # Remove the containment check

        elif shape.shape_type == "polygon":
            # Only check intersection with polygon edges - no containment check
            shape_points = shape.points
            for i in range(len(shape_points)):
                p1 = shape_points[i]
                p2 = shape_points[(i + 1) % len(shape_points)]
                if self.line_segments_intersect(line_start, line_end, p1, p2):
                    return True
            return False  # Remove the containment check

        elif shape.shape_type == "circle":
            # Check intersection with circle
            center = shape.points[0]
            edge_point = shape.points[1]
            radius = ((edge_point.x() - center.x()) ** 2 + (edge_point.y() - center.y()) ** 2) ** 0.5
            return self.line_intersects_circle(line_start, line_end, center, radius)

        elif shape.shape_type in ["line", "linestrip"]:
            # Check intersection with line/linestrip
            for i in range(len(shape.points) - 1):
                p1 = shape.points[i]
                p2 = shape.points[i + 1]
                if self.line_segments_intersect(line_start, line_end, p1, p2):
                    return True

        elif shape.shape_type == "point":
            # Check if line passes close to the point
            point = shape.points[0]
            return self.point_near_line(point, line_start, line_end, threshold=5.0)

        return False

    def line_segments_intersect(self, p1, q1, p2, q2):
        """Check if two line segments intersect"""
        def orientation(p, q, r):
            """Find orientation of ordered triplet (p, q, r)"""
            val = (q.y() - p.y()) * (r.x() - q.x()) - (q.x() - p.x()) * (r.y() - q.y())
            if val == 0:
                return 0  # collinear
            return 1 if val > 0 else 2  # clockwise or counterclockwise

        def on_segment(p, q, r):
            """Check if point q lies on segment pr"""
            return (q.x() <= max(p.x(), r.x()) and q.x() >= min(p.x(), r.x()) and
                    q.y() <= max(p.y(), r.y()) and q.y() >= min(p.y(), r.y()))

        o1 = orientation(p1, q1, p2)
        o2 = orientation(p1, q1, q2)
        o3 = orientation(p2, q2, p1)
        o4 = orientation(p2, q2, q1)

        # General case
        if o1 != o2 and o3 != o4:
            return True

        # Special cases
        if (o1 == 0 and on_segment(p1, p2, q1)) or \
           (o2 == 0 and on_segment(p1, q2, q1)) or \
           (o3 == 0 and on_segment(p2, p1, q2)) or \
           (o4 == 0 and on_segment(p2, q1, q2)):
            return True

        return False

    def line_intersects_circle(self, line_start, line_end, circle_center, radius):
        """Check if line segment intersects with circle"""
        # Vector from line start to end
        dx = line_end.x() - line_start.x()
        dy = line_end.y() - line_start.y()

        # Vector from line start to circle center
        fx = line_start.x() - circle_center.x()
        fy = line_start.y() - circle_center.y()

        # Quadratic equation coefficients
        a = dx * dx + dy * dy
        b = 2 * (fx * dx + fy * dy)
        c = (fx * fx + fy * fy) - radius * radius

        discriminant = b * b - 4 * a * c
        if discriminant < 0:
            return False

        # Check if intersection points are within the line segment
        discriminant = discriminant ** 0.5
        t1 = (-b - discriminant) / (2 * a)
        t2 = (-b + discriminant) / (2 * a)

        return (0 <= t1 <= 1) or (0 <= t2 <= 1) or (t1 < 0 and t2 > 1)

    def point_near_line(self, point, line_start, line_end, threshold=5.0):
        """Check if point is near a line segment within threshold distance"""
        # Calculate distance from point to line segment
        A = point.x() - line_start.x()
        B = point.y() - line_start.y()
        C = line_end.x() - line_start.x()
        D = line_end.y() - line_start.y()

        dot = A * C + B * D
        len_sq = C * C + D * D

        if len_sq == 0:
            # Line start and end are the same point
            distance = (A * A + B * B) ** 0.5
        else:
            param = dot / len_sq
            if param < 0:
                xx = line_start.x()
                yy = line_start.y()
            elif param > 1:
                xx = line_end.x()
                yy = line_end.y()
            else:
                xx = line_start.x() + param * C
                yy = line_start.y() + param * D

            dx = point.x() - xx
            dy = point.y() - yy
            distance = (dx * dx + dy * dy) ** 0.5

        return distance <= threshold

    def point_in_polygon(self, point, polygon_points):
        """Check if point is inside polygon using ray casting algorithm"""
        x, y = point.x(), point.y()
        n = len(polygon_points)
        inside = False

        p1x, p1y = polygon_points[0].x(), polygon_points[0].y()
        for i in range(1, n + 1):
            p2x, p2y = polygon_points[i % n].x(), polygon_points[i % n].y()
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y

        return inside

    def end_move(self, copy):
        """End of move"""
        assert self.selected_shapes and self.selected_shapes_copy
        assert len(self.selected_shapes_copy) == len(self.selected_shapes)
        if copy:
            for i, shape in enumerate(self.selected_shapes_copy):
                self.shapes.append(shape)
                self.selected_shapes[i].selected = False
                self.selected_shapes[i] = shape
        else:
            for i, shape in enumerate(self.selected_shapes_copy):
                self.selected_shapes[i].points = shape.points
        self.selected_shapes_copy = []
        self.repaint()
        self.store_shapes()
        return True

    def hide_background_shapes(self, value):
        """Set hide background - hide other shapes when some shapes are selected"""
        self.hide_backround = value
        if self.selected_shapes:
            # Only hide other shapes if there is a current selection.
            # Otherwise the user will not be able to select a shape.
            self.set_hiding(True)
            self.update()

    def set_hiding(self, enable=True):
        """Set background hiding"""
        self._hide_backround = self.hide_backround if enable else False

    def can_close_shape(self):
        """Check if a shape can be closed (number of points > 2)"""
        return self.drawing() and self.current and len(self.current) > 2

    # QT Overload
    def mouseDoubleClickEvent(self, _):
        """Mouse double click event"""
        if self.is_loading:
            return

        # Handle auto decode mode double click to finish
        if (
            self.auto_decode_mode
            and self.is_auto_labeling
            and self.auto_decode_tracklet
        ):
            self.auto_decode_finish_requested.emit()
            return

        # We need at least 4 points here, since the mousePress handler
        # adds an extra one before this handler is called.
        if (
            self.double_click == "close"
            and self.can_close_shape()
            and len(self.current) > 3
        ):
            self.current.pop_point()
            self.finalise()

    def select_shapes(self, shapes):
        """Select some shapes"""
        self.set_hiding()
        self.selection_changed.emit(shapes)
        self.update()

    def select_shape_point(self, point, multiple_selection_mode):
        """Select the first shape created which contains this point."""
        if self.selected_vertex():  # A vertex is marked for selection.
            index, shape = self.h_vertex, self.h_hape
            shape.highlight_vertex(index, shape.MOVE_VERTEX)
            if shape.shape_type == "rotation":
                self.set_hiding()
                if shape not in self.selected_shapes:
                    if multiple_selection_mode:
                        self.selection_changed.emit(
                            self.selected_shapes + [shape]
                        )
                    else:
                        self.selection_changed.emit([shape])
                    self.h_shape_is_selected = False
                else:
                    self.h_shape_is_selected = True
                self.calculate_offsets(point)
                return

        else:
            for shape in reversed(self.shapes):
                if (
                    self.is_visible(shape)
                    and len(shape.points) > 1
                    and shape.contains_point(point)
                ):
                    self.set_hiding()
                    if shape not in self.selected_shapes:
                        if multiple_selection_mode:
                            self.selection_changed.emit(
                                self.selected_shapes + [shape]
                            )
                        else:
                            self.selection_changed.emit([shape])
                        self.h_shape_is_selected = False
                    else:
                        self.h_shape_is_selected = True
                    self.calculate_offsets(point)
                    return
        self.deselect_shape()

    def calculate_offsets(self, point):
        """Calculate offsets of a point to pixmap borders"""
        left = self.pixmap.width() - 1
        right = 0
        top = self.pixmap.height() - 1
        bottom = 0
        for s in self.selected_shapes:
            rect = s.bounding_rect()
            if rect.left() < left:
                left = rect.left()
            if rect.right() > right:
                right = rect.right()
            if rect.top() < top:
                top = rect.top()
            if rect.bottom() > bottom:
                bottom = rect.bottom()

        x1 = left - point.x()
        y1 = top - point.y()
        x2 = right - point.x()
        y2 = bottom - point.y()
        self.offsets = QtCore.QPointF(x1, y1), QtCore.QPointF(x2, y2)

    def get_adjoint_points(self, theta, p3, p1, index):
        a1 = math.tan(theta)
        if a1 == 0:
            if index % 2 == 0:
                p2 = QtCore.QPointF(p3.x(), p1.y())
                p4 = QtCore.QPointF(p1.x(), p3.y())
            else:
                p4 = QtCore.QPointF(p3.x(), p1.y())
                p2 = QtCore.QPointF(p1.x(), p3.y())
        else:
            a3 = a1
            a2 = -1 / a1
            a4 = -1 / a1
            b1 = p1.y() - a1 * p1.x()
            b2 = p1.y() - a2 * p1.x()
            b3 = p3.y() - a1 * p3.x()
            b4 = p3.y() - a2 * p3.x()

            if index % 2 == 0:
                p2 = self.get_cross_point(a1, b1, a4, b4)
                p4 = self.get_cross_point(a2, b2, a3, b3)
            else:
                p4 = self.get_cross_point(a1, b1, a4, b4)
                p2 = self.get_cross_point(a2, b2, a3, b3)

        return p2, p3, p4

    @staticmethod
    def get_cross_point(a1, b1, a2, b2):
        x = (b2 - b1) / (a1 - a2)
        y = (a1 * b2 - a2 * b1) / (a1 - a2)
        return QtCore.QPointF(x, y)

    def bounded_move_vertex(self, pos):
        """Move a vertex. Adjust position to be bounded by pixmap border"""
        index, shape = self.h_vertex, self.h_hape
        point = shape[index]
        if (
            self.out_off_pixmap(pos)
            and shape.shape_type not in self.allowed_oop_shape_types
        ):
            pos = self.intersection_point(point, pos)

        if shape.shape_type == "rotation":
            sindex = (index + 2) % 4
            # Get the other 3 points after transformed
            p2, p3, p4 = self.get_adjoint_points(
                shape.direction, shape[sindex], pos, index
            )
            # if (
            #     self.out_off_pixmap(p2)
            #     or self.out_off_pixmap(p3)
            #     or self.out_off_pixmap(p4)
            # ):
            #     # No need to move if one pixal out of map
            #     return
            # Move 4 pixal one by one
            shape.move_vertex_by(index, pos - point)
            lindex = (index + 1) % 4
            rindex = (index + 3) % 4
            shape[lindex] = p2
            shape[rindex] = p4
            shape.close()
            # Don't recalculate direction when resizing - only adjust size, keep original angle
        elif shape.shape_type == "rectangle":
            shift_pos = pos - point
            shape.move_vertex_by(index, shift_pos)
            left_index = (index + 1) % 4
            right_index = (index + 3) % 4
            left_shift = None
            right_shift = None
            if index % 2 == 0:
                right_shift = QtCore.QPointF(shift_pos.x(), 0)
                left_shift = QtCore.QPointF(0, shift_pos.y())
            else:
                left_shift = QtCore.QPointF(shift_pos.x(), 0)
                right_shift = QtCore.QPointF(0, shift_pos.y())
            shape.move_vertex_by(right_index, right_shift)
            shape.move_vertex_by(left_index, left_shift)
        else:
            shape.move_vertex_by(index, pos - point)

    def bounded_move_shapes(self, shapes, pos):
        """Move shapes. Adjust position to be bounded by pixmap border"""
        shape_types = []
        for shape in shapes:
            if shape.shape_type in self.allowed_oop_shape_types:
                shape_types.append(shape.shape_type)

        if self.out_off_pixmap(pos) and len(shape_types) == 0:
            return False  # No need to move
        if len(shape_types) > 0 and len(shapes) != len(shape_types):
            return False

        if len(shape_types) == 0:
            o1 = pos + self.offsets[0]
            if self.out_off_pixmap(o1):
                pos -= QtCore.QPoint(min(0, int(o1.x())), min(0, int(o1.y())))
            o2 = pos + self.offsets[1]
            if self.out_off_pixmap(o2):
                pos += QtCore.QPoint(
                    min(0, int(self.pixmap.width() - o2.x())),
                    min(0, int(self.pixmap.height() - o2.y())),
                )
        # XXX: The next line tracks the new position of the cursor
        # relative to the shape, but also results in making it
        # a bit "shaky" when nearing the border and allows it to
        # go outside of the shape's area for some reason.
        # self.calculateOffsets(self.selectedShapes, pos)
        dp = pos - self.prev_point
        if dp:
            for shape in shapes:
                shape.move_by(dp)
            self.prev_point = pos
            return True
        return False

    def rotate_point(self, p, center, theta):
        order = p - center
        cosTheta = math.cos(theta)
        sinTheta = math.sin(theta)
        pResx = cosTheta * order.x() + sinTheta * order.y()
        pResy = -sinTheta * order.x() + cosTheta * order.y()
        pRes = QtCore.QPointF(center.x() + pResx, center.y() + pResy)
        return pRes

    def bounded_rotate_shapes(self, i, shape, theta):
        """Rotate shapes. Adjust position to be bounded by pixmap border"""
        new_shape = deepcopy(shape)
        if len(shape.points) == 2:
            new_shape.points[0] = shape.points[0]
            new_shape.points[1] = QtCore.QPointF(
                (shape.points[0].x() + shape.points[1].x()) / 2,
                shape.points[0].y(),
            )
            new_shape.points.append(shape.points[1])
            new_shape.points.append(
                QtCore.QPointF(
                    shape.points[1].x(),
                    (shape.points[0].y() + shape.points[1].y()) / 2,
                )
            )
        center = QtCore.QPointF(
            (new_shape.points[0].x() + new_shape.points[2].x()) / 2,
            (new_shape.points[0].y() + new_shape.points[2].y()) / 2,
        )
        for j, p in enumerate(new_shape.points):
            pos = self.rotate_point(p, center, -theta)
            # TODO: Reserved for now
            # if self.out_off_pixmap(pos):
            #     return False  # No need to rotate
            new_shape.points[j] = pos
        new_shape.direction = (new_shape.direction + theta) % (2 * math.pi)
        self.selected_shapes[i].points = new_shape.points
        self.selected_shapes[i].direction = new_shape.direction
        return True

    def deselect_shape(self):
        """Deselect all shapes"""
        if self.selected_shapes:
            self.set_hiding(False)
            self.selection_changed.emit([])
            self.h_shape_is_selected = False
            self.update()

    def delete_selected(self):
        """Remove selected shapes"""
        deleted_shapes = []
        if self.selected_shapes:
            for shape in self.selected_shapes:
                self.shapes.remove(shape)
                deleted_shapes.append(shape)
            self.store_shapes()
            self.selected_shapes = []
            self.update()
        return deleted_shapes

    def delete_shape(self, shape):
        """Remove a specific shape"""
        if shape in self.selected_shapes:
            self.selected_shapes.remove(shape)
        if shape in self.shapes:
            self.shapes.remove(shape)
        self.store_shapes()
        self.update()

    def duplicate_selected_shapes(self):
        """Duplicate selected shapes"""
        if self.selected_shapes:
            self.selected_shapes_copy = [
                s.copy() for s in self.selected_shapes
            ]
            self.bounded_shift_shapes(self.selected_shapes_copy)
            self.end_move(copy=True)
        return self.selected_shapes

    def bounded_shift_shapes(self, shapes):
        """
        Shift shapes by an offset. Adjust positions to be bounded
        by pixmap borders
        """
        # Try to move in one direction, and if it fails in another.
        # Give up if both fail.
        point = shapes[0][0]
        offset = QtCore.QPointF(2.0, 2.0)
        self.offsets = QtCore.QPointF(), QtCore.QPointF()
        self.prev_point = point
        if not self.bounded_move_shapes(shapes, point - offset):
            self.bounded_move_shapes(shapes, point + offset)

    # QT Overload
    def _find_overlapping_areas(self, shapes):
        """找到所有相同标签的矩形之间的重叠区域"""
        overlap_regions = []
        if len(shapes) < 2:
            return overlap_regions

        for i, shape1 in enumerate(shapes):
            if shape1.shape_type not in ["rectangle", "rotation"]:
                continue
            if not hasattr(shape1, 'label') or not shape1.label:
                continue
            path1 = shape1.make_path()
            for shape2 in shapes[i + 1:]:
                if shape2.shape_type not in ["rectangle", "rotation"]:
                    continue
                if not hasattr(shape2, 'label') or not shape2.label:
                    continue
                # 检查标签是否相同
                if shape1.label != shape2.label:
                    continue
                path2 = shape2.make_path()
                # 计算两个路径的交集
                overlap_path = path1.intersected(path2)
                if not overlap_path.isEmpty():
                    overlap_regions.append(overlap_path)
        return overlap_regions

    def paintEvent(self, event):  # noqa: C901
        """Paint event for canvas"""
        if (
            self.pixmap is None
            or self.pixmap.width() == 0
            or self.pixmap.height() == 0
        ):
            super().paintEvent(event)
            return

        p = self._painter
        p.begin(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        p.setRenderHint(QtGui.QPainter.HighQualityAntialiasing)

        p.scale(self.scale, self.scale)
        p.translate(self.offset_to_center())

        p.drawPixmap(0, 0, self.pixmap)
        Shape.scale = self.scale
        
        # 找到所有重叠区域
        overlap_regions = self._find_overlapping_areas(self.shapes)

        # Draw loading/waiting screen
        if self.is_loading:
            # Draw a semi-transparent rectangle
            p.setPen(Qt.NoPen)
            p.setBrush(QtGui.QColor(0, 0, 0, 20))
            p.drawRect(self.pixmap.rect())

            # Draw a spinning wheel
            p.setPen(QtGui.QColor(255, 255, 255))
            p.setBrush(Qt.NoBrush)
            p.save()
            p.translate(self.pixmap.width() / 2, self.pixmap.height() / 2 - 50)
            p.rotate(self.loading_angle)
            p.drawEllipse(-20, -20, 40, 40)
            p.drawLine(0, 0, 0, -20)
            p.restore()
            self.loading_angle += 30
            if self.loading_angle >= 360:
                self.loading_angle = 0

            # Draw the loading text
            p.setPen(QtGui.QColor(255, 255, 255))
            p.setFont(QtGui.QFont("Arial", 20))
            p.drawText(
                self.pixmap.rect(),
                Qt.AlignCenter,
                self.loading_text,
            )
            p.end()
            self.update()
            return

        # Draw groups
        if self.show_groups:
            pen = QtGui.QPen(QtGui.QColor("#AAAAAA"), 2, Qt.SolidLine)
            p.setPen(pen)
            grouped_shapes = {}
            for shape in self.shapes:
                if not shape.visible:
                    continue
                if shape.group_id is None:
                    continue
                if shape.group_id not in grouped_shapes:
                    grouped_shapes[shape.group_id] = []
                grouped_shapes[shape.group_id].append(shape)

            for group_id in grouped_shapes:
                shapes = grouped_shapes[group_id]
                min_x = float("inf")
                min_y = float("inf")
                max_x = 0
                max_y = 0
                for shape in shapes:
                    rect = shape.bounding_rect()
                    if shape.shape_type == "point":
                        points = shape.points[0]
                        min_x = min(min_x, points.x())
                        min_y = min(min_y, points.y())
                        max_x = max(max_x, points.x())
                        max_y = max(max_y, points.y())
                    else:
                        min_x = min(min_x, rect.x())
                        min_y = min(min_y, rect.y())
                        max_x = max(max_x, rect.x() + rect.width())
                        max_y = max(max_y, rect.y() + rect.height())
                    group_color = LABEL_COLORMAP[
                        int(group_id) % len(LABEL_COLORMAP)
                    ]
                    pen.setStyle(Qt.SolidLine)
                    pen.setWidth(max(1, int(round(4.0 / Shape.scale))))
                    pen.setColor(QtGui.QColor(*group_color))
                    p.setPen(pen)

                    # Calculate the center point of the bounding rectangle
                    cx = rect.x() + rect.width() / 2
                    cy = rect.y() + rect.height() / 2
                    triangle_radius = max(1, int(round(3.0 / Shape.scale)))

                    # Define the points of the triangle
                    triangle_points = [
                        QtCore.QPointF(cx, cy - triangle_radius),
                        QtCore.QPointF(
                            cx - triangle_radius, cy + triangle_radius
                        ),
                        QtCore.QPointF(
                            cx + triangle_radius, cy + triangle_radius
                        ),
                    ]

                    # Draw the triangle
                    p.drawPolygon(triangle_points)

                pen.setStyle(Qt.DashLine)
                pen.setWidth(max(1, int(round(1.0 / Shape.scale))))
                pen.setColor(QtGui.QColor("#EEEEEE"))
                p.setPen(pen)
                wrap_rect = QtCore.QRectF(
                    min_x, min_y, max_x - min_x, max_y - min_y
                )
                p.drawRect(wrap_rect)

        # Draw KIE linking
        if self.show_linking:
            pen = QtGui.QPen(QtGui.QColor("#AAAAAA"), 2, Qt.SolidLine)
            p.setPen(pen)
            gid2point = {}
            linking_pairs = []
            group_color = (255, 128, 0)
            for shape in self.shapes:
                if not shape.visible:
                    continue

                try:
                    linking_pairs += shape.kie_linking
                except Exception:
                    pass

                if shape.group_id is None or shape.shape_type not in [
                    "rectangle",
                    "polygon",
                    "rotation",
                ]:
                    continue
                rect = shape.bounding_rect()
                cx = rect.x() + (rect.width() / 2.0)
                cy = rect.y() + (rect.height() / 2.0)
                gid2point[shape.group_id] = (cx, cy)

            for linking in linking_pairs:
                pen.setStyle(Qt.SolidLine)
                pen.setWidth(max(1, int(round(4.0 / Shape.scale))))
                pen.setColor(QtGui.QColor(*group_color))
                p.setPen(pen)
                key, value = linking
                # Adapt to the 'ungroup_selected_shapes' operation
                if key not in gid2point or value not in gid2point:
                    continue
                kp, vp = gid2point[key], gid2point[value]
                # Draw a link from key point to value point
                p.drawLine(QtCore.QPointF(*kp), QtCore.QPointF(*vp))
                # Draw the triangle arrowhead
                arrow_size = max(
                    1, int(round(10.0 / Shape.scale))
                )  # Size of the arrowhead
                angle = math.atan2(
                    vp[1] - kp[1], vp[0] - kp[0]
                )  # Angle towards the value point
                arrow_points = [
                    QtCore.QPointF(vp[0], vp[1]),
                    QtCore.QPointF(
                        vp[0] - arrow_size * math.cos(angle - math.pi / 6),
                        vp[1] - arrow_size * math.sin(angle - math.pi / 6),
                    ),
                    QtCore.QPointF(
                        vp[0] - arrow_size * math.cos(angle + math.pi / 6),
                        vp[1] - arrow_size * math.sin(angle + math.pi / 6),
                    ),
                ]
                p.drawPolygon(arrow_points)

        # 首先绘制所有形状
        for shape in self.shapes:
            if (
                shape.selected or not self._hide_backround
            ) and self.is_visible(shape):
                shape.fill = self._fill_drawing and (
                    shape.selected or shape == self.h_hape
                )
                shape.paint(p)

        # 绘制重叠区域
        if overlap_regions and self.show_overlap:
            for overlap_path in overlap_regions:
                if not overlap_path.isEmpty():
                    p.fillPath(overlap_path, self.overlap_color)

        # Draw degrees
        for shape in self.shapes:
            if (
                shape.shape_type == "rotation"
                and len(shape.points) == 4
                and self.is_visible(shape)
            ):
                d = shape.point_size / shape.scale
                center = QtCore.QPointF(
                    (shape.points[0].x() + shape.points[2].x()) / 2,
                    (shape.points[0].y() + shape.points[2].y()) / 2,
                )
                if self.show_degrees:
                    degrees = str(int(math.degrees(shape.direction))) + "°"
                    p.setFont(
                        QtGui.QFont(
                            "Arial",
                            int(max(6.0, int(round(8.0 / Shape.scale)))),
                        )
                    )
                    pen = QtGui.QPen(
                        QtGui.QColor("#FF9900"), 8, QtCore.Qt.SolidLine
                    )
                    p.setPen(pen)
                    fm = QtGui.QFontMetrics(p.font())
                    rect = fm.boundingRect(degrees)
                    p.fillRect(
                        int(rect.x() + center.x() - d),
                        int(rect.y() + center.y() + d),
                        int(rect.width()),
                        int(rect.height()),
                        QtGui.QColor("#FF9900"),
                    )
                    pen = QtGui.QPen(
                        QtGui.QColor("#FFFFFF"), 7, QtCore.Qt.SolidLine
                    )
                    p.setPen(pen)
                    p.drawText(
                        int(center.x() - d),
                        int(center.y() + d),
                        degrees,
                    )
                else:
                    cp = QtGui.QPainterPath()
                    cp.addRect(
                        int(center.x() - d / 2),
                        int(center.y() - d / 2),
                        int(d),
                        int(d),
                    )
                    p.drawPath(cp)
                    p.fillPath(cp, QtGui.QColor(255, 153, 0, 255))

        if self.current:
            # Don't paint the shape itself in rotation3 mode (only paint line with arrow)
            if self.create_mode != "rotation3":
                self.current.paint(p)

            self.line.paint(p)

            # For rotation3 mode, also paint the center line when drawing the second line
            if (self.create_mode == "rotation3" and len(self.current.points) == 2
                and len(self.center_line.points) == 2):
                self.center_line.paint(p)

            # Draw arrow for rotation3 rectangle
            if (self.create_mode == "rotation3"
                and len(self.current.points) >= 1
                and len(self.line.points) == 2):

                p.save()

                # Arrow and dot sizes should be constant in screen pixels (divide by scale)
                arrow_size = 12 / self.scale
                circle_radius = 6 / self.scale
                pen_width = 2 / self.scale

                # First step: draw green dot and red arrow for center line
                if len(self.current.points) == 1:
                    start_point = self.line.points[0]
                    end_point = self.line.points[1]

                    # Calculate direction
                    dx = end_point.x() - start_point.x()
                    dy = end_point.y() - start_point.y()
                    length = (dx**2 + dy**2) ** 0.5

                    if length > 0:
                        # Normalize
                        dx /= length
                        dy /= length

                        # Draw vertical reference line at start point (perpendicular to center line)
                        # This helps user see if the start point aligns with text
                        perp_x = -dy
                        perp_y = dx

                        # Reference line length (adjust as needed)
                        ref_line_length = 50 / self.scale

                        # Reference line at start point (green dot)
                        ref_start_begin = QtCore.QPointF(
                            start_point.x() - perp_x * ref_line_length,
                            start_point.y() - perp_y * ref_line_length
                        )
                        ref_start_end = QtCore.QPointF(
                            start_point.x() + perp_x * ref_line_length,
                            start_point.y() + perp_y * ref_line_length
                        )

                        # Draw dashed reference line at start point (red for visibility)
                        dashed_pen = QtGui.QPen(QtGui.QColor(255, 0, 0), pen_width, QtCore.Qt.DashLine)
                        p.setPen(dashed_pen)
                        p.drawLine(ref_start_begin, ref_start_end)

                        # Reference line at end point (arrow tip)
                        ref_end_begin = QtCore.QPointF(
                            end_point.x() - perp_x * ref_line_length,
                            end_point.y() - perp_y * ref_line_length
                        )
                        ref_end_end = QtCore.QPointF(
                            end_point.x() + perp_x * ref_line_length,
                            end_point.y() + perp_y * ref_line_length
                        )

                        # Draw dashed reference line at end point (red for visibility)
                        p.drawLine(ref_end_begin, ref_end_end)

                        # Arrow parameters
                        arrow_angle = 30  # degrees
                        angle_rad = math.radians(arrow_angle)

                        # Calculate arrow wings
                        left_x = end_point.x() - arrow_size * (dx * math.cos(angle_rad) + dy * math.sin(angle_rad))
                        left_y = end_point.y() - arrow_size * (dy * math.cos(angle_rad) - dx * math.sin(angle_rad))

                        right_x = end_point.x() - arrow_size * (dx * math.cos(angle_rad) - dy * math.sin(angle_rad))
                        right_y = end_point.y() - arrow_size * (dy * math.cos(angle_rad) + dx * math.sin(angle_rad))

                        # Draw arrow
                        arrow_polygon = QtGui.QPolygonF([
                            end_point,
                            QtCore.QPointF(left_x, left_y),
                            QtCore.QPointF(right_x, right_y)
                        ])

                        p.setBrush(QtGui.QBrush(QtGui.QColor(255, 0, 0)))  # Red arrow
                        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), pen_width))  # White border
                        p.drawPolygon(arrow_polygon)

                        # Draw green dot at start
                        p.setBrush(QtGui.QBrush(QtGui.QColor(0, 255, 0)))  # Green dot
                        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), pen_width))
                        p.drawEllipse(start_point, circle_radius, circle_radius)

                        # Draw angle text at start point (green dot)
                        angle_deg = math.degrees(math.atan2(dy, dx))
                        # Normalize to 0-360 range
                        if angle_deg < 0:
                            angle_deg += 360
                        angle_text = f"{angle_deg:.1f}°"

                        # Set font for angle text
                        font = QtGui.QFont()
                        font.setPointSize(int(12 / self.scale))
                        font.setBold(True)
                        p.setFont(font)

                        # Calculate text bounding box for background
                        metrics = QtGui.QFontMetrics(font)
                        text_rect = metrics.boundingRect(angle_text)
                        text_offset = 20 / self.scale
                        text_pos = QtCore.QPointF(start_point.x() + text_offset, start_point.y() - text_offset)

                        # Draw background rectangle (blue background)
                        bg_padding = 4 / self.scale
                        bg_rect = QtCore.QRectF(
                            text_pos.x() - bg_padding,
                            text_pos.y() - text_rect.height() - bg_padding,
                            text_rect.width() + 2 * bg_padding,
                            text_rect.height() + 2 * bg_padding
                        )
                        p.setBrush(QtGui.QBrush(QtGui.QColor(0, 100, 255)))  # Solid blue background
                        p.setPen(QtCore.Qt.NoPen)  # No border
                        p.drawRect(bg_rect)

                        # Draw text (white)
                        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255)))  # White text
                        p.drawText(text_pos, angle_text)

                # Second step: draw green dot, red arrow on center line, blue arrow on width line, and dashed preview
                elif len(self.current.points) == 2:
                    # Draw green dot at start of center line
                    green_point = self.current[0]
                    p.setBrush(QtGui.QBrush(QtGui.QColor(0, 255, 0)))  # Green dot
                    p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), pen_width))
                    p.drawEllipse(green_point, circle_radius, circle_radius)

                    # Draw red dot at end of center line (arrow point)
                    arrow_point = self.current[1]
                    p.setBrush(QtGui.QBrush(QtGui.QColor(255, 0, 0)))  # Red dot
                    p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), pen_width))
                    p.drawEllipse(arrow_point, circle_radius, circle_radius)

                    # Draw red arrow at end of center line
                    dx_center = arrow_point.x() - green_point.x()
                    dy_center = arrow_point.y() - green_point.y()
                    length_center = (dx_center**2 + dy_center**2) ** 0.5

                    if length_center > 0:
                        # Normalize
                        dx_center /= length_center
                        dy_center /= length_center

                        # Arrow parameters (already defined above)
                        arrow_angle = 30  # degrees
                        angle_rad = math.radians(arrow_angle)

                        # Calculate arrow wings for center line
                        left_x = arrow_point.x() - arrow_size * (dx_center * math.cos(angle_rad) + dy_center * math.sin(angle_rad))
                        left_y = arrow_point.y() - arrow_size * (dy_center * math.cos(angle_rad) - dx_center * math.sin(angle_rad))

                        right_x = arrow_point.x() - arrow_size * (dx_center * math.cos(angle_rad) - dy_center * math.sin(angle_rad))
                        right_y = arrow_point.y() - arrow_size * (dy_center * math.cos(angle_rad) + dx_center * math.sin(angle_rad))

                        # Draw arrow for center line
                        arrow_polygon = QtGui.QPolygonF([
                            arrow_point,
                            QtCore.QPointF(left_x, left_y),
                            QtCore.QPointF(right_x, right_y)
                        ])

                        p.setBrush(QtGui.QBrush(QtGui.QColor(255, 0, 0)))  # Red arrow
                        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), pen_width))  # White border
                        p.drawPolygon(arrow_polygon)

                    # Draw blue arrow at end of width line (second line)
                    if len(self.line.points) == 2:
                        width_start = self.line.points[0]
                        width_end = self.line.points[1]

                        dx_width = width_end.x() - width_start.x()
                        dy_width = width_end.y() - width_start.y()
                        length_width = (dx_width**2 + dy_width**2) ** 0.5

                        if length_width > 0:
                            # Normalize
                            dx_width /= length_width
                            dy_width /= length_width

                            # Arrow parameters (use same angle_rad)
                            # Calculate arrow wings for width line
                            left_x = width_end.x() - arrow_size * (dx_width * math.cos(angle_rad) + dy_width * math.sin(angle_rad))
                            left_y = width_end.y() - arrow_size * (dy_width * math.cos(angle_rad) - dx_width * math.sin(angle_rad))

                            right_x = width_end.x() - arrow_size * (dx_width * math.cos(angle_rad) - dy_width * math.sin(angle_rad))
                            right_y = width_end.y() - arrow_size * (dy_width * math.cos(angle_rad) + dx_width * math.sin(angle_rad))

                            # Draw arrow for width line
                            arrow_polygon2 = QtGui.QPolygonF([
                                width_end,
                                QtCore.QPointF(left_x, left_y),
                                QtCore.QPointF(right_x, right_y)
                            ])

                            p.setBrush(QtGui.QBrush(QtGui.QColor(0, 100, 255)))  # Blue arrow
                            p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), pen_width))  # White border
                            p.drawPolygon(arrow_polygon2)

                    # Draw dashed preview lines for the other two sides of rectangle
                    if len(self.line.points) == 2:
                        p0 = self.current[0]
                        p1 = self.current[1]
                        p2 = self.line[1]
                        p3 = p0 + (p2 - p1)  # Fourth corner

                        # Draw dashed lines (with scale-independent width)
                        dashed_pen = QtGui.QPen(QtGui.QColor(100, 100, 100), pen_width, QtCore.Qt.DashLine)
                        p.setPen(dashed_pen)

                        # Line from p0 to p3
                        p.drawLine(p0, p3)

                        # Line from p2 to p3
                        p.drawLine(p2, p3)

                p.restore()
        if self.selected_shapes_copy:
            for s in self.selected_shapes_copy:
                s.paint(p)

        if (
            self.fill_drawing()
            and self.create_mode == "polygon"
            and self.current is not None
            and len(self.current.points) >= 2
        ):
            drawing_shape = self.current.copy()
            drawing_shape.add_point(self.line[1])
            drawing_shape.fill = True
            drawing_shape.paint(p)

        # Draw texts
        if self.show_texts:
            text_color = "#FFFFFF"
            background_color = "#007BFF"
            p.setFont(
                QtGui.QFont(
                    "Arial", int(max(6.0, int(round(8.0 / Shape.scale))))
                )
            )
            pen = QtGui.QPen(QtGui.QColor(background_color), 8, Qt.SolidLine)
            p.setPen(pen)
            for shape in self.shapes:
                if not shape.visible:
                    continue
                description = shape.description
                if description:
                    bbox = shape.bounding_rect()
                    fm = QtGui.QFontMetrics(p.font())
                    rect = fm.boundingRect(description)
                    p.fillRect(
                        int(rect.x() + bbox.x()),
                        int(rect.y() + bbox.y()),
                        int(rect.width()),
                        int(rect.height()),
                        QtGui.QColor(background_color),
                    )
                    p.drawText(
                        int(bbox.x()),
                        int(bbox.y()),
                        description,
                    )
            pen = QtGui.QPen(QtGui.QColor(text_color), 8, Qt.SolidLine)
            p.setPen(pen)
            for shape in self.shapes:
                if not shape.visible:
                    continue
                description = shape.description
                if description:
                    bbox = shape.bounding_rect()
                    p.drawText(
                        int(bbox.x()),
                        int(bbox.y()),
                        description,
                    )

        # Draw labels
        if self.show_labels:
            p.setFont(
                QtGui.QFont(
                    "Arial", int(max(6.0, int(round(8.0 / Shape.scale))))
                )
            )
            labels = []
            shape_orders = {}
            if self.show_order:
                label_counters_for_ordering = {}
                for i, shape_in_list in enumerate(self.shapes):
                    label = shape_in_list.label
                    label_counters_for_ordering[label] = label_counters_for_ordering.get(label, 0) + 1
                    shape_orders[id(shape_in_list)] = (i + 1, label_counters_for_ordering[label])

            for shape in self.shapes:
                if not self.is_visible(shape):
                    continue
                d_react = shape.point_size / shape.scale
                d_text = 1.5
                if shape.label in [
                    "AUTOLABEL_OBJECT",
                    "AUTOLABEL_ADD",
                    "AUTOLABEL_REMOVE",
                ]:
                    continue

                label_text = ""
                if self.show_order:
                    global_order, label_order = shape_orders.get(id(shape), (0, 0))
                    if global_order > 0:
                        label_text += f"{global_order} ({label_order}) "

                label_text += (
                    (f"id:{shape.group_id} " if shape.group_id is not None else "")
                    + (f"{shape.label}")
                    + (
                        f" {float(shape.score):.2f}"
                        if (shape.score is not None and self.show_scores)
                        else ""
                    )
                )
                if not label_text.strip():
                    continue
                fm = QtGui.QFontMetrics(p.font())
                bound_rect = fm.boundingRect(label_text)
                if shape.shape_type in ["rectangle", "polygon", "rotation"]:
                    try:
                        bbox = shape.bounding_rect()
                    except IndexError:
                        continue
                    padding = 10  # Add horizontal padding to the right
                    rect = QtCore.QRect(
                        int(bbox.x()),
                        int(bbox.y() - bound_rect.height()),
                        int(bound_rect.width() + padding),
                        int(bound_rect.height()),
                    )
                    text_pos = QtCore.QPoint(
                        int(bbox.x()),
                        int(bbox.y() - d_text),
                    )
                elif shape.shape_type in [
                    "circle",
                    "line",
                    "linestrip",
                    "point",
                ]:
                    points = shape.points
                    if not points:
                        continue
                    point = points[0]
                    rect = QtCore.QRect(
                        int(point.x() + d_react),
                        int(point.y() - 15),
                        int(bound_rect.width()),
                        int(bound_rect.height()),
                    )
                    text_pos = QtCore.QPoint(
                        int(point.x()),
                        int(point.y() - 15 + bound_rect.height() - d_text),
                    )
                else:
                    continue
                labels.append((shape, rect, text_pos, label_text))

            pen = QtGui.QPen(QtGui.QColor("#FFA500"), 8, Qt.SolidLine)
            p.setPen(pen)
            for shape, rect, _, _ in labels:
                if not shape.visible:
                    continue
                p.fillRect(rect, shape.line_color)

            pen = QtGui.QPen(QtGui.QColor("#000000"), 8, Qt.SolidLine)
            p.setPen(pen)
            for _, _, text_pos, label_text in labels:
                if not shape.visible:
                    continue
                p.drawText(text_pos, label_text)

        # Draw mouse coordinates
        if self.cross_line_show:
            # Save painter state to isolate opacity settings
            p.save()

            # Determine line style (solid or dashed)
            line_style = Qt.SolidLine if self.cross_line_style == "solid" else Qt.DashLine

            pen = QtGui.QPen(
                QtGui.QColor(self.cross_line_color),
                max(1, int(round(self.cross_line_width / Shape.scale))),
                line_style,
            )
            p.setPen(pen)
            p.setOpacity(self.cross_line_opacity)

            # rotation3 mode: rotated crosshair based on edge direction
            if (self.create_mode == "rotation3" and self.current
                and len(self.current.points) >= 1 and len(self.line.points) == 2):

                # Determine which edge to follow and which position to use for crosshair center
                if len(self.current.points) == 1:
                    # First step: follow first edge direction, use actual mouse position
                    p0 = self.current[0]
                    p1 = self.line[1]  # Current mouse position
                    crosshair_center = self.prev_move_point  # Use actual mouse position
                elif len(self.current.points) == 2:
                    # Second step: follow second edge direction, use constrained position
                    p0 = self.current[1]  # First edge endpoint
                    p1 = self.line[1]  # Constrained position (perpendicular)
                    crosshair_center = self.line[1]  # Use constrained position, not mouse position
                else:
                    p0 = self.current[0]
                    p1 = self.line[1]
                    crosshair_center = self.prev_move_point

                # Calculate angle of the edge
                dx = p1.x() - p0.x()
                dy = p1.y() - p0.y()
                length = math.sqrt(dx**2 + dy**2)

                if length > 1:  # Avoid division by zero
                    # Normalize direction vector
                    dx /= length
                    dy /= length

                    # Get perpendicular direction (90° rotation)
                    perp_x = -dy
                    perp_y = dx

                    # Draw rotated crosshair at appropriate position
                    crosshair_length = max(self.pixmap.width(), self.pixmap.height()) * 2

                    # Line 1: along the edge direction
                    p.drawLine(
                        QtCore.QPointF(
                            crosshair_center.x() - dx * crosshair_length,
                            crosshair_center.y() - dy * crosshair_length
                        ),
                        QtCore.QPointF(
                            crosshair_center.x() + dx * crosshair_length,
                            crosshair_center.y() + dy * crosshair_length
                        ),
                    )

                    # Line 2: perpendicular to edge
                    p.drawLine(
                        QtCore.QPointF(
                            crosshair_center.x() - perp_x * crosshair_length,
                            crosshair_center.y() - perp_y * crosshair_length
                        ),
                        QtCore.QPointF(
                            crosshair_center.x() + perp_x * crosshair_length,
                            crosshair_center.y() + perp_y * crosshair_length
                        ),
                    )
                else:
                    # If too close to start point, draw normal crosshair
                    p.drawLine(
                        QtCore.QPointF(self.prev_move_point.x(), 0),
                        QtCore.QPointF(self.prev_move_point.x(), self.pixmap.height()),
                    )
                    p.drawLine(
                        QtCore.QPointF(0, self.prev_move_point.y()),
                        QtCore.QPointF(self.pixmap.width(), self.prev_move_point.y()),
                    )
            else:
                # Normal crosshair for other modes or initial state
                p.drawLine(
                    QtCore.QPointF(self.prev_move_point.x(), 0),
                    QtCore.QPointF(self.prev_move_point.x(), self.pixmap.height()),
                )
                p.drawLine(
                    QtCore.QPointF(0, self.prev_move_point.y()),
                    QtCore.QPointF(self.pixmap.width(), self.prev_move_point.y()),
                )

            # Restore painter state to prevent opacity from affecting other drawings
            p.restore()

        # Draw attributes
        if self.show_attributes:
            font_size = int(max(8.0, int(round(10.0 / Shape.scale))))
            font = QtGui.QFont("Arial", font_size, QtGui.QFont.Bold)
            p.setFont(font)
            attributes_list = []

            for shape in self.shapes:
                if not shape.visible:
                    continue
                if not hasattr(shape, "attributes") or not shape.attributes:
                    continue
                if shape.label in [
                    "AUTOLABEL_OBJECT",
                    "AUTOLABEL_ADD",
                    "AUTOLABEL_REMOVE",
                ]:
                    continue

                attrs_text = []
                for key, value in shape.attributes.items():
                    attrs_text.append(f"{key}: {value}")
                if not attrs_text:
                    continue

                max_attrs_per_line = 1
                attribute_lines = []
                for i in range(0, len(attrs_text), max_attrs_per_line):
                    line_attrs = attrs_text[i : i + max_attrs_per_line]
                    attribute_lines.append(" | ".join(line_attrs))

                fm = QtGui.QFontMetrics(font)
                max_width = 0
                line_heights = []
                for line in attribute_lines:
                    line_rect = fm.tightBoundingRect(line)
                    max_width = max(max_width, line_rect.width())
                    line_heights.append(fm.height())
                total_height = sum(line_heights)

                padding_x = 8
                padding_y = 2
                rect_width = max_width + 2 * padding_x
                rect_height = total_height + 2 * padding_y
                d_react = shape.point_size / shape.scale

                if shape.shape_type in ["rectangle", "polygon", "rotation"]:
                    try:
                        bbox = shape.bounding_rect()
                    except IndexError:
                        continue

                    rect = QtCore.QRect(
                        int(bbox.x()),
                        int(bbox.y() + bbox.height() + 1),
                        rect_width,
                        rect_height,
                    )

                    text_positions = []
                    y_offset = 0
                    for i, line_height in enumerate(line_heights):
                        text_pos = QtCore.QPoint(
                            int(bbox.x() + padding_x),
                            int(
                                bbox.y()
                                + bbox.height()
                                + 1
                                + padding_y
                                + y_offset
                                + fm.ascent()
                            ),
                        )
                        text_positions.append(text_pos)
                        y_offset += line_height

                elif shape.shape_type in [
                    "circle",
                    "line",
                    "linestrip",
                    "point",
                ]:
                    points = shape.points
                    if not points:
                        continue
                    point = points[0]

                    rect = QtCore.QRect(
                        int(point.x() + d_react),
                        int(point.y() + 1),
                        rect_width,
                        rect_height,
                    )

                    text_positions = []
                    y_offset = 0
                    for i, line_height in enumerate(line_heights):
                        text_pos = QtCore.QPoint(
                            int(point.x() + d_react + padding_x),
                            int(
                                point.y()
                                + 1
                                + padding_y
                                + y_offset
                                + fm.ascent()
                            ),
                        )
                        text_positions.append(text_pos)
                        y_offset += line_height
                else:
                    continue

                attributes_list.append(
                    (shape, rect, text_positions, attribute_lines)
                )

            for shape, rect, _, _ in attributes_list:
                if not shape.visible:
                    continue

                background_color = QtGui.QColor(33, 33, 33, 255)
                p.fillRect(rect, background_color)

                pen = QtGui.QPen(
                    QtGui.QColor(66, 66, 66), 1, Qt.SolidLine
                )  # Lighter grey border
                p.setPen(pen)
                p.drawRect(rect)

            pen = QtGui.QPen(
                QtGui.QColor(33, 150, 243), 1, Qt.SolidLine
            )  # Material Blue 500
            p.setPen(pen)
            p.setFont(font)

            for _, _, text_positions, attribute_lines in attributes_list:
                for i, (text_pos, line_text) in enumerate(
                    zip(text_positions, attribute_lines)
                ):
                    p.drawText(text_pos, line_text)

        # Draw Alt+drag selection box
        if self.selection_box_mode:
            self.draw_selection_box(p)

        # Draw Shift+drag path selection
        if self.path_selection_mode:
            self.draw_path_selection(p)

        p.end()

    def draw_selection_box(self, p):
        """Draw the Alt+drag selection box"""
        if not self.selection_box_mode:
            return

        # Calculate rectangle bounds
        x1, y1 = self.selection_box_start.x(), self.selection_box_start.y()
        x2, y2 = self.selection_box_end.x(), self.selection_box_end.y()

        min_x, max_x = min(x1, x2), max(x1, x2)
        min_y, max_y = min(y1, y2), max(y1, y2)

        # Create selection rectangle
        rect = QtCore.QRectF(min_x, min_y, max_x - min_x, max_y - min_y)

        # Draw selection box with dashed blue border and semi-transparent fill
        p.save()

        # Draw semi-transparent fill
        fill_color = QtGui.QColor(0, 120, 215, 30)  # Light blue with transparency
        p.setBrush(QtGui.QBrush(fill_color))
        p.setPen(Qt.NoPen)
        p.drawRect(rect)

        # Draw dashed border
        pen = QtGui.QPen(QtGui.QColor(0, 120, 215), 2, Qt.SolidLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(rect)

        p.restore()

    def draw_path_selection(self, p):
        """Draw the Shift+drag path selection and highlight intersected shapes"""
        if not self.path_selection_mode or len(self.path_selection_points) < 2:
            return

        p.save()

        # Draw the path with a different color
        pen = QtGui.QPen(QtGui.QColor(0, 191, 255), 3, Qt.SolidLine)  # Deep sky blue path
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)

        # Draw path segments
        for i in range(len(self.path_selection_points) - 1):
            start = self.path_selection_points[i]
            end = self.path_selection_points[i + 1]
            p.drawLine(start, end)

        # Draw start point with a circle (head indicator)
        if len(self.path_selection_points) > 0:
            start_point = self.path_selection_points[0]
            p.setBrush(QtGui.QBrush(QtGui.QColor(0, 191, 255)))  # Same blue color
            p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 2))  # White border
            circle_radius = 6
            p.drawEllipse(start_point, circle_radius, circle_radius)

        # Draw current end point with an arrow
        if len(self.path_selection_points) > 1:
            end_point = self.path_selection_points[-1]
            # Get the direction from the second to last point to the last point
            if len(self.path_selection_points) >= 2:
                prev_point = self.path_selection_points[-2]
                # Calculate direction vector
                dx = end_point.x() - prev_point.x()
                dy = end_point.y() - prev_point.y()
                # Calculate length
                length = (dx**2 + dy**2) ** 0.5
                if length > 0:
                    # Normalize direction
                    dx /= length
                    dy /= length

                    # Arrow head size
                    arrow_size = 12
                    arrow_angle = 30  # degrees

                    import math
                    angle_rad = math.radians(arrow_angle)

                    # Calculate arrow head points
                    # Left wing
                    left_x = end_point.x() - arrow_size * (dx * math.cos(angle_rad) + dy * math.sin(angle_rad))
                    left_y = end_point.y() - arrow_size * (dy * math.cos(angle_rad) - dx * math.sin(angle_rad))

                    # Right wing
                    right_x = end_point.x() - arrow_size * (dx * math.cos(angle_rad) - dy * math.sin(angle_rad))
                    right_y = end_point.y() - arrow_size * (dy * math.cos(angle_rad) + dx * math.sin(angle_rad))

                    # Draw filled arrow head
                    arrow_polygon = QtGui.QPolygonF([
                        end_point,
                        QtCore.QPointF(left_x, left_y),
                        QtCore.QPointF(right_x, right_y)
                    ])

                    p.setBrush(QtGui.QBrush(QtGui.QColor(0, 191, 255)))  # Blue fill
                    p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 2))  # White border
                    p.drawPolygon(arrow_polygon)

        # Highlight shapes that intersect with the path - use hover effect settings
        for shape in self.path_highlighted_shapes:
            if shape.visible:
                # Use the same hover line color and width from Shape class configuration
                hover_color = Shape.canvas_hover_line_color
                hover_width = (
                    Shape.canvas_hover_line_width
                    if Shape.canvas_hover_line_width is not None
                    else 3  # fallback width
                )

                # Apply scale adjustment like Shape class does
                scaled_width = max(1, int(round(hover_width / self.scale)))

                pen = QtGui.QPen(hover_color, scaled_width, Qt.SolidLine)
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)  # No fill, just border

                if shape.shape_type in ["rectangle", "rotation"]:
                    # Draw rectangle outline
                    path = QtGui.QPainterPath()
                    path.moveTo(shape.points[0])
                    for point in shape.points[1:]:
                        path.lineTo(point)
                    path.closeSubpath()
                    p.drawPath(path)
                elif shape.shape_type == "polygon":
                    # Draw polygon outline
                    path = QtGui.QPainterPath()
                    path.moveTo(shape.points[0])
                    for point in shape.points[1:]:
                        path.lineTo(point)
                    path.closeSubpath()
                    p.drawPath(path)
                elif shape.shape_type == "circle":
                    # Draw circle outline
                    center = shape.points[0]
                    edge = shape.points[1]
                    radius = ((edge.x() - center.x()) ** 2 + (edge.y() - center.y()) ** 2) ** 0.5
                    p.drawEllipse(center, radius, radius)

        p.restore()

    def transform_pos(self, point):
        """Convert from widget-logical coordinates to painter-logical ones."""
        return point / self.scale - self.offset_to_center()

    def offset_to_center(self):
        """Calculate offset to the center"""
        if self.pixmap is None:
            return QtCore.QPointF()
        s = self.scale
        area = super().size()
        w, h = self.pixmap.width() * s, self.pixmap.height() * s
        area_width, area_height = area.width(), area.height()
        x = (area_width - w) / (2 * s) if area_width > w else 0
        y = (area_height - h) / (2 * s) if area_height > h else 0
        return QtCore.QPointF(x, y)

    def out_off_pixmap(self, p):
        """Check if a position is out of pixmap"""
        if self.pixmap is None:
            return True
        w, h = self.pixmap.width(), self.pixmap.height()
        return not (0 <= p.x() <= w - 1 and 0 <= p.y() <= h - 1)

    def finalise(self):
        """Finish drawing for a shape"""
        assert self.current
        if (
            self.is_auto_labeling
            and self.auto_labeling_mode != AutoLabelingMode.NONE
        ):
            self.current.label = self.auto_labeling_mode.edit_mode
        # TODO(vietanhdev): Temporrally fix. Need to refactor
        if self.current.label is None:
            self.current.label = ""
        self.current.close()
        self.shapes.append(self.current)
        self.store_shapes()
        self.current = None
        self.set_hiding(False)
        self.new_shape.emit()
        self.update()
        if self.is_auto_labeling:
            self.update_auto_labeling_marks()

    def update_auto_labeling_marks(self):
        """Update the auto labeling marks"""
        marks = []
        for shape in self.shapes:
            if shape.label == AutoLabelingMode.ADD:
                if shape.shape_type == AutoLabelingMode.POINT:
                    marks.append(
                        {
                            "type": "point",
                            "data": [
                                int(shape.points[0].x()),
                                int(shape.points[0].y()),
                            ],
                            "label": 1,
                        }
                    )
                elif shape.shape_type == AutoLabelingMode.RECTANGLE:
                    marks.append(
                        {
                            "type": "rectangle",
                            "data": [
                                int(shape.points[0].x()),
                                int(shape.points[0].y()),
                                int(shape.points[2].x()),
                                int(shape.points[2].y()),
                            ],
                            "label": 1,
                        }
                    )
            elif shape.label == AutoLabelingMode.REMOVE:
                if shape.shape_type == AutoLabelingMode.POINT:
                    marks.append(
                        {
                            "type": "point",
                            "data": [
                                int(shape.points[0].x()),
                                int(shape.points[0].y()),
                            ],
                            "label": 0,
                        }
                    )
                elif shape.shape_type == AutoLabelingMode.RECTANGLE:
                    marks.append(
                        {
                            "type": "rectangle",
                            "data": [
                                int(shape.points[0].x()),
                                int(shape.points[0].y()),
                                int(shape.points[2].x()),
                                int(shape.points[2].y()),
                            ],
                            "label": 0,
                        }
                    )

        self.auto_labeling_marks_updated.emit(marks)

    def close_enough(self, p1, p2):
        """Check if 2 points are close enough (by an threshold epsilon)"""
        # d = distance(p1 - p2)
        # m = (p1-p2).manhattanLength()
        # print "d %.2f, m %d, %.2f" % (d, m, d - m)
        # divide by scale to allow more precision when zoomed in
        return utils.distance(p1 - p2) < (self.epsilon / self.scale)

    def intersection_point(self, p1, p2):
        """Cycle through each image edge in clockwise fashion,
        and find the one intersecting the current line segment.
        """
        size = self.pixmap.size()
        points = [
            (0, 0),
            (size.width() - 1, 0),
            (size.width() - 1, size.height() - 1),
            (0, size.height() - 1),
        ]
        # x1, y1 should be in the pixmap, x2, y2 should be out of the pixmap
        x1 = min(max(p1.x(), 0), size.width() - 1)
        y1 = min(max(p1.y(), 0), size.height() - 1)
        x2, y2 = p2.x(), p2.y()
        _, i, (x, y) = min(self.intersecting_edges((x1, y1), (x2, y2), points))
        x3, y3 = points[i]
        x4, y4 = points[(i + 1) % 4]
        x1, y1 = int(x1), int(y1)
        x2, y2 = int(x2), int(y2)
        x3, y3 = int(x3), int(y3)
        x4, y4 = int(x4), int(y4)
        if (x, y) == (x1, y1):
            # Handle cases where previous point is on one of the edges.
            if x3 == x4:
                return QtCore.QPoint(x3, min(max(0, y2), max(y3, y4)))
            # y3 == y4
            return QtCore.QPoint(min(max(0, x2), max(x3, x4)), y3)
        return QtCore.QPoint(int(x), int(y))

    def intersecting_edges(self, point1, point2, points):
        """Find intersecting edges.

        For each edge formed by `points', yield the intersection
        with the line segment `(x1,y1) - (x2,y2)`, if it exists.
        Also return the distance of `(x2,y2)' to the middle of the
        edge along with its index, so that the one closest can be chosen.
        """
        (x1, y1) = point1
        (x2, y2) = point2
        for i in range(4):
            x3, y3 = points[i]
            x4, y4 = points[(i + 1) % 4]
            denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
            nua = (x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)
            nub = (x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)
            if denom == 0:
                # This covers two cases:
                #   nua == nub == 0: Coincident
                #   otherwise: Parallel
                continue
            ua, ub = nua / denom, nub / denom
            if 0 <= ua <= 1 and 0 <= ub <= 1:
                x = x1 + ua * (x2 - x1)
                y = y1 + ua * (y2 - y1)
                m = QtCore.QPointF((x3 + x4) / 2, (y3 + y4) / 2)
                d = utils.distance(m - QtCore.QPointF(x2, y2))
                yield d, i, (x, y)

    # These two, along with a call to adjustSize are required for the
    # scroll area.
    # QT Overload
    def sizeHint(self):
        """Get size hint"""
        return self.minimumSizeHint()

    # QT Overload
    def minimumSizeHint(self):
        """Get minimum size hint"""
        if self.pixmap:
            return self.scale * self.pixmap.size()
        return super().minimumSizeHint()

    # QT Overload
    def wheelEvent(self, ev: QWheelEvent):
        """Mouse wheel event"""
        mods = ev.modifiers()
        delta = ev.angleDelta()
        is_ctrl_pressed = (QtCore.Qt.ControlModifier & int(mods))

        if (
            self.editing()
            and self.enable_wheel_rectangle_editing
            and len(self.selected_shapes) == 1
            and self.selected_shapes[0].shape_type in ["rectangle", "rotation"]
        ):
            try:
                pos = self.transform_pos(ev.posF())
            except AttributeError:
                pos = self.transform_pos(ev.localPos())

            shape = self.selected_shapes[0]
            wheel_up = delta.y() > 0

            # If cursor is inside the shape, scale width/height
            if shape.contains_point(pos):
                # Ctrl+scroll to adjust height, default scroll to adjust width
                adjust_height = is_ctrl_pressed
                self._scale_rectangle(shape, wheel_up, adjust_height)
                self.store_shapes()
                self.shape_moved.emit()
                self.update()
                ev.accept()
                return
            # If cursor is outside, handle edge adjustment or canvas zooming
            else:
                if is_ctrl_pressed:
                    # fast adjustment for edges
                    if shape.shape_type == "rotation":
                        self._adjust_rotation_edge(shape, pos, wheel_up, fast_mode=True)
                    else:
                        self._adjust_rectangle_edge(shape, pos, wheel_up, fast_mode=True)
                    self.store_shapes()
                    self.shape_moved.emit()
                    self.update()
                    ev.accept()
                    return
                else: # regular edge adjustment
                    if shape.shape_type == "rotation":
                        self._adjust_rotation_edge(shape, pos, wheel_up, fast_mode=False)
                    else:
                        self._adjust_rectangle_edge(shape, pos, wheel_up, fast_mode=False)
                    self.store_shapes()
                    self.shape_moved.emit()
                    self.update()
                    ev.accept()
                    return

        # Default canvas scroll/zoom behavior
        if is_ctrl_pressed:
            self.zoom_request.emit(delta.y(), ev.pos())
        else:
            self.scroll_request.emit(delta.x(), QtCore.Qt.Horizontal, 0)
            self.scroll_request.emit(delta.y(), QtCore.Qt.Vertical, 0)

        ev.accept()

    def _scale_rectangle(self, shape, scale_up, adjust_height=False):
        """Adjust rectangle width or height from center by a fixed pixel amount."""
        if len(shape.points) < 4:
            return

        if self.pixmap is None:
            return
        img_width = self.pixmap.width()
        img_height = self.pixmap.height()

        # Use scale_step as the pixel adjustment value.
        # Divided by 2 because we are adjusting from the center, moving each side.
        adjustment = self.rect_scale_step / 2.0 if scale_up else -self.rect_scale_step / 2.0

        if shape.shape_type == "rotation":
            # For rotated rectangles, the delta must be along the shape's width or height axis.
            theta = shape.direction
            if adjust_height:  # Adjust height (perpendicular to width)
                theta += math.pi / 2
                current_height_vector = shape.points[3] - shape.points[0]
                if adjustment < 0 and current_height_vector.manhattanLength() < abs(adjustment * 2):
                    return
            else:  # Adjust width
                current_width_vector = shape.points[1] - shape.points[0]
                if adjustment < 0 and current_width_vector.manhattanLength() < abs(adjustment * 2):
                    return
            
            # Create a base unit vector for the direction
            base_delta = QtCore.QPointF(math.cos(theta), math.sin(theta))
            
            # Ensure the base vector points in a canonical "outward" direction for expansion.
            p0, p1, p2, p3 = shape.points
            center = (p0 + p2) / 2.0
            
            if adjust_height:
                # For height, "outward" is opposite to the vector from center to the edge (p0, p1).
                center_to_edge = ((p0 + p1) / 2.0) - center
                if QtCore.QPointF.dotProduct(base_delta, center_to_edge) > 0:
                    base_delta *= -1
            else:  # Adjust width
                # For width, "outward" is opposite to the vector from center to the edge (p3, p0).
                center_to_edge = ((p3 + p0) / 2.0) - center
                if QtCore.QPointF.dotProduct(base_delta, center_to_edge) > 0:
                    base_delta *= -1
            
            # Apply the final adjustment, which includes the direction (scale_up/down)
            delta = adjustment * base_delta
            
            # Apply the delta to the points based on the adjusted dimension
            if adjust_height:
                new_points = [
                    shape.points[0] - delta,
                    shape.points[1] - delta,
                    shape.points[2] + delta,
                    shape.points[3] + delta,
                ]
            else:  # Adjust width
                new_points = [
                    shape.points[0] - delta,
                    shape.points[1] + delta,
                    shape.points[2] + delta,
                    shape.points[3] - delta,
                ]

        elif shape.shape_type == "rectangle":
            # For axis-aligned rectangles, the delta is simple.
            if adjust_height:
                delta = QtCore.QPointF(0, adjustment)
                new_points = [
                    shape.points[0] - delta,
                    shape.points[1] - delta,
                    shape.points[2] + delta,
                    shape.points[3] + delta,
                ]
            else:
                delta = QtCore.QPointF(adjustment, 0)
                new_points = [
                    shape.points[0] - delta,
                    shape.points[1] + delta,
                    shape.points[2] + delta,
                    shape.points[3] - delta,
                ]
        else:
            return # Not applicable to other shapes

        # Check if all new points are within the image boundaries.
        min_x = min(p.x() for p in new_points)
        max_x = max(p.x() for p in new_points)
        min_y = min(p.y() for p in new_points)
        max_y = max(p.y() for p in new_points)
        if (
            min_x < 0
            or max_x >= img_width
            or min_y < 0
            or max_y >= img_height
        ):
            return

        # If all checks pass, update the shape's points.
        for i, new_point in enumerate(new_points):
            shape.points[i] = new_point

    def _adjust_rotation_edge(self, shape, cursor_pos, move_outward, fast_mode=False):
        """Adjust the rotated rectangle edge closest to the cursor position."""
        if len(shape.points) < 4:
            return

        if self.pixmap is None:
            return
        img_width = self.pixmap.width()
        img_height = self.pixmap.height()

        # Determine the step size based on whether fast_mode is enabled
        step_value = self.fast_rect_adjust_step if fast_mode else self.rect_adjust_step
        step = step_value if move_outward else -step_value

        # Calculate distance to each edge (line segment)
        distances = {}
        edges = [(0, 1), (1, 2), (2, 3), (3, 0)]
        for i, (start_idx, end_idx) in enumerate(edges):
            p1 = shape.points[start_idx]
            p2 = shape.points[end_idx]
            dist = self._point_to_line_distance(cursor_pos, p1, p2)
            distances[i] = dist

        closest_edge_index = min(distances, key=distances.get)
        idx1, idx2 = edges[closest_edge_index]
        p1, p2 = shape.points[idx1], shape.points[idx2]

        # Calculate perpendicular direction to the edge
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        length = math.sqrt(dx * dx + dy * dy)
        if length > 0:
            # Perpendicular vector, pointing outward
            perp_dx, perp_dy = -dy / length, dx / length

            # Check if the perpendicular vector is pointing outward from the center
            center = (shape.points[0] + shape.points[2]) / 2
            edge_mid_point = QtCore.QPointF((p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2)
            
            # Vector from center to the edge's midpoint
            center_to_edge = edge_mid_point - center
            
            # Dot product to check direction alignment
            dot_product = center_to_edge.x() * perp_dx + center_to_edge.y() * perp_dy
            if dot_product < 0:
                # If the perpendicular vector is pointing inward, flip it
                perp_dx, perp_dy = -perp_dx, -perp_dy

            move_x = step * perp_dx
            move_y = step * perp_dy

            # Move only the two points of the selected edge
            new_x1 = p1.x() + move_x
            new_y1 = p1.y() + move_y
            new_x2 = p2.x() + move_x
            new_y2 = p2.y() + move_y

            # Check if new points are within bounds
            if (0 <= new_x1 < img_width and 0 <= new_y1 < img_height and
                0 <= new_x2 < img_width and 0 <= new_y2 < img_height):
                shape.points[idx1] = QtCore.QPointF(new_x1, new_y1)
                shape.points[idx2] = QtCore.QPointF(new_x2, new_y2)

    def _adjust_rectangle_edge(self, shape, cursor_pos, move_outward, fast_mode=False):
        """Adjust the rectangle edge closest to cursor position within image boundaries"""
        if len(shape.points) < 4:
            return

        rect = shape.bounding_rect()
        min_x, max_x = rect.left(), rect.right()
        min_y, max_y = rect.top(), rect.bottom()

        # Determine the step size based on whether fast_mode is enabled
        step_value = self.fast_rect_adjust_step if fast_mode else self.rect_adjust_step
        step = step_value if move_outward else -step_value

        if self.pixmap is None:
            return
        img_width = self.pixmap.width()
        img_height = self.pixmap.height()

        # Original rectangle adjustment logic
        distances = self._calculate_edge_distances(cursor_pos, min_x, max_x, min_y, max_y)
        closest_edge = self._determine_closest_edge(cursor_pos, min_x, max_x, min_y, max_y, distances)
        
        for i, point in enumerate(shape.points):
            new_point = None

            if closest_edge == "left" and abs(point.x() - min_x) < 1e-6:
                new_x = max(0, point.x() - step)
                new_point = QtCore.QPointF(new_x, point.y())
            elif closest_edge == "right" and abs(point.x() - max_x) < 1e-6:
                new_x = min(img_width - 1, point.x() + step)
                new_point = QtCore.QPointF(new_x, point.y())
            elif closest_edge == "top" and abs(point.y() - min_y) < 1e-6:
                new_y = max(0, point.y() - step)
                new_point = QtCore.QPointF(point.x(), new_y)
            elif closest_edge == "bottom" and abs(point.y() - max_y) < 1e-6:
                new_y = min(img_height - 1, point.y() + step)
                new_point = QtCore.QPointF(point.x(), new_y)

            if new_point is not None:
                shape.points[i] = new_point

    def _point_to_line_distance(self, point, line_start, line_end):
        """Calculate the distance from a point to a line segment"""
        px = point.x()
        py = point.y()
        x1 = line_start.x()
        y1 = line_start.y()
        x2 = line_end.x()
        y2 = line_end.y()
        
        A = px - x1
        B = py - y1
        C = x2 - x1
        D = y2 - y1
        
        dot = A * C + B * D
        len_sq = C * C + D * D
        
        if len_sq == 0:
            return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)
            
        param = dot / len_sq
        
        if param < 0:
            return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)
        elif param > 1:
            return math.sqrt((px - x2) ** 2 + (py - y2) ** 2)
        
        x = x1 + param * C
        y = y1 + param * D
        return math.sqrt((px - x) ** 2 + (py - y) ** 2)
        
    def _calculate_edge_distances(self, cursor_pos, min_x, max_x, min_y, max_y):
        """Calculate distances to each edge of a rectangle"""
        distances = {}
        
        if cursor_pos.x() < min_x:
            distances["left"] = min_x - cursor_pos.x()
        elif cursor_pos.x() > max_x:
            distances["right"] = cursor_pos.x() - max_x
        else:
            distances["left"] = abs(cursor_pos.x() - min_x)
            distances["right"] = abs(cursor_pos.x() - max_x)

        if cursor_pos.y() < min_y:
            distances["top"] = min_y - cursor_pos.y()
        elif cursor_pos.y() > max_y:
            distances["bottom"] = cursor_pos.y() - max_y
        else:
            distances["top"] = abs(cursor_pos.y() - min_y)
            distances["bottom"] = abs(cursor_pos.y() - max_y)
            
        return distances
        
    def _determine_closest_edge(self, cursor_pos, min_x, max_x, min_y, max_y, distances):
        """Determine the closest edge based on cursor position and distances"""
        if (
            cursor_pos.x() < min_x
            and cursor_pos.y() >= min_y
            and cursor_pos.y() <= max_y
        ):
            return "left"
        elif (
            cursor_pos.x() > max_x
            and cursor_pos.y() >= min_y
            and cursor_pos.y() <= max_y
        ):
            return "right"
        elif (
            cursor_pos.y() < min_y
            and cursor_pos.x() >= min_x
            and cursor_pos.x() <= max_x
        ):
            return "top"
        elif (
            cursor_pos.y() > max_y
            and cursor_pos.x() >= min_x
            and cursor_pos.x() <= max_x
        ):
            return "bottom"
        else:
            return min(distances, key=distances.get)

    def move_by_keyboard(self, offset):
        """Move selected shapes by an offset (using keyboard)"""
        if self.selected_shapes:
            self.bounded_move_shapes(
                self.selected_shapes, self.prev_point + offset
            )
            self.repaint()
            self.moving_shape = True

    def rotate_by_keyboard(self, theta):
        """Rotate selected shapes by an theta (using keyboard)"""
        if self.selected_shapes:
            for i, shape in enumerate(self.selected_shapes):
                if shape._shape_type == "rotation":
                    self.bounded_rotate_shapes(i, shape, theta)
                    self.repaint()
                    self.rotating_shape = True

    def set_shape_rotation(self, shape, angle_radians):
        """Set the absolute rotation of a shape to a specific angle."""
        if shape.shape_type != 'rotation' or len(shape.points) != 4:
            return

        # Get intrinsic properties from the current shape's points.
        center = (shape.points[0] + shape.points[2]) / 2.0
        width = utils.distance(shape.points[0] - shape.points[1])
        height = utils.distance(shape.points[1] - shape.points[2])

        # Define the four corners of the unrotated rectangle around the center.
        half_w, half_h = width / 2.0, height / 2.0
        canonical_points = [
            center + QtCore.QPointF(-half_w, -half_h),
            center + QtCore.QPointF(half_w, -half_h),
            center + QtCore.QPointF(half_w, half_h),
            center + QtCore.QPointF(-half_w, half_h),
        ]

        # Invert the angle for visual rotation to match user expectation
        rotation_to_apply = -angle_radians

        # Rotate these canonical points to the desired absolute angle.
        for i, p in enumerate(canonical_points):
            shape.points[i] = self.rotate_point(p, center, rotation_to_apply)

        # IMPORTANT: Store the original, non-inverted angle so the UI value is correct.
        shape.direction = angle_radians
        self.update()

    # QT Overload
    def keyPressEvent(self, ev):
        """Key press event"""
        modifiers = ev.modifiers()
        key = ev.key()
        if self.drawing():
            if key == QtCore.Qt.Key_Escape and self.current:
                self.current = None
                self.drawing_polygon.emit(False)
                self.update()
            elif key == QtCore.Qt.Key_Backspace and self.current:
                # Backspace: undo last point (go back one step)
                if self.create_mode == "rotation3":
                    if len(self.current.points) == 2:
                        # Step 2 -> Step 1: remove second point
                        self.current.points.pop()
                        # Reset line to start from first point
                        self.line[0] = self.current[0]
                        self.line[1] = self.current[0]
                        self.update()
                    elif len(self.current.points) == 1:
                        # Step 1 -> Cancel: remove all and cancel
                        self.current = None
                        self.drawing_polygon.emit(False)
                        self.update()
                elif self.create_mode in ["polygon", "linestrip"]:
                    # For polygon/linestrip, remove last point
                    if len(self.current.points) > 1:
                        self.current.points.pop()
                        self.line[0] = self.current[-1]
                        self.update()
                    elif len(self.current.points) == 1:
                        # Only one point left, cancel
                        self.current = None
                        self.drawing_polygon.emit(False)
                        self.update()
            elif key == QtCore.Qt.Key_Return and self.can_close_shape():
                self.finalise()
            elif modifiers == QtCore.Qt.AltModifier:
                self.snapping = False
        elif self.editing():
            if key == QtCore.Qt.Key_Up:
                self.move_by_keyboard(QtCore.QPointF(0.0, -MOVE_SPEED))
            elif key == QtCore.Qt.Key_Down:
                self.move_by_keyboard(QtCore.QPointF(0.0, MOVE_SPEED))
            elif key == QtCore.Qt.Key_Left:
                self.move_by_keyboard(QtCore.QPointF(-MOVE_SPEED, 0.0))
            elif key == QtCore.Qt.Key_Right:
                self.move_by_keyboard(QtCore.QPointF(MOVE_SPEED, 0.0))
            elif key == QtCore.Qt.Key_Z:
                self.rotate_by_keyboard(-LARGE_ROTATION_INCREMENT)
            elif key == QtCore.Qt.Key_X:
                self.rotate_by_keyboard(-SMALL_ROTATION_INCREMENT)
            elif key == QtCore.Qt.Key_C:
                self.rotate_by_keyboard(SMALL_ROTATION_INCREMENT)
            elif key == QtCore.Qt.Key_V:
                self.rotate_by_keyboard(LARGE_ROTATION_INCREMENT)

    # QT Overload
    def keyReleaseEvent(self, ev):
        """Key release event"""
        # Cancel selection box mode if Alt key is released
        if ev.key() == QtCore.Qt.Key_Alt and self.selection_box_mode:
            self.selection_box_mode = False
            self.repaint()
            return

        # Cancel path selection mode if Shift key is released
        if ev.key() == QtCore.Qt.Key_Shift and self.path_selection_mode:
            self.path_selection_mode = False
            self.path_highlighted_shapes.clear()
            self.repaint()
            return

        modifiers = ev.modifiers()
        if self.drawing():
            if int(modifiers) == 0:
                self.snapping = True
        elif self.editing():
            # NOTE: Temporary fix to avoid ValueError
            # when the selected shape is not in the shapes list
            if (
                (self.moving_shape or self.rotating_shape)
                and self.selected_shapes
                and self.selected_shapes[0] in self.shapes
            ):
                index = self.shapes.index(self.selected_shapes[0])
                if (
                    self.shapes_backups[-1][index].points
                    != self.shapes[index].points
                ):
                    self.store_shapes()
                    if self.moving_shape:
                        self.shape_moved.emit()
                    if self.rotating_shape:
                        self.shape_rotated.emit()

                if self.moving_shape:
                    self.moving_shape = False
                if self.rotating_shape:
                    self.rotating_shape = False

    def set_last_label(self, text, flags):
        """Set label and flags for last shape"""
        assert text
        if self.is_auto_labeling:
            self.shapes[-1].label = self.auto_labeling_mode.edit_mode
        else:
            self.shapes[-1].label = text
        self.shapes[-1].flags = flags
        self.shapes_backups.pop()
        self.store_shapes()
        return self.shapes[-1]

    def undo_last_line(self):
        """Undo last line"""
        assert self.shapes
        self.current = self.shapes.pop()
        self.current.set_open()
        if self.create_mode in ["polygon", "linestrip"]:
            self.line.points = [self.current[-1], self.current[0]]
        elif self.create_mode in ["rectangle", "line", "circle", "rotation"]:
            self.current.points = self.current.points[0:1]
        elif self.create_mode == "point":
            self.current = None
        self.drawing_polygon.emit(True)

    def undo_last_point(self):
        """Undo last point"""
        if not self.current or self.current.is_closed():
            return
        self.current.pop_point()
        if len(self.current) > 0:
            self.line[0] = self.current[-1]
        else:
            self.current = None
            self.drawing_polygon.emit(False)
        self.update()

    def load_pixmap(self, pixmap, clear_shapes=True):
        """Load pixmap"""
        self.pixmap = pixmap
        if clear_shapes:
            self.shapes = []
        self.update()

    def load_shapes(self, shapes, replace=True):
        """Load shapes"""
        if replace:
            self.shapes = list(shapes)
        else:
            self.shapes.extend(shapes)
        self.store_shapes()
        self.current = None
        self.h_hape = None
        self.h_vertex = None
        self.h_edge = None
        self.update()

    def set_shape_visible(self, shape, value):
        """Set visibility for a shape"""
        self.visible[shape] = value
        self.update()

    def current_cursor(self):
        """Current cursor"""
        cursor = QtWidgets.QApplication.overrideCursor()
        cursor = cursor.shape() if cursor else None

        return cursor

    def override_cursor(self, cursor):
        """Override cursor"""
        current_cursor = self.current_cursor()
        if current_cursor != cursor:
            self._cursor = cursor
            if current_cursor is None:
                QtWidgets.QApplication.setOverrideCursor(cursor)
            else:
                QtWidgets.QApplication.changeOverrideCursor(cursor)

    def restore_cursor(self):
        """Restore override cursor"""
        QtWidgets.QApplication.restoreOverrideCursor()

    def reset_state(self):
        """Clear shapes and pixmap"""
        self.restore_cursor()
        self.pixmap = None
        self.shapes_backups = []
        self.is_move_editing = False
        self.update()

    def set_cross_line(self, show, width, color, opacity, style="dash"):
        """Set cross line options"""
        self.cross_line_show = show
        self.cross_line_width = width
        self.cross_line_color = color
        self.cross_line_opacity = opacity
        self.cross_line_style = style
        self.update()

    def gen_new_group_id(self):
        """Generate new shape's group_id based on current shapes"""
        max_group_id = 0
        for shape in self.shapes:
            if shape.group_id is not None:
                max_group_id = max(max_group_id, shape.group_id)
        return max_group_id + 1

    def merge_group_ids(self, group_ids, new_group_id):
        """Merge multiple shapes' group_id into a new one"""
        for shape in self.shapes:
            if shape.group_id in group_ids:
                shape.group_id = new_group_id

    def group_selected_shapes(self):
        """Group selected shapes"""
        if len(self.selected_shapes) == 0:
            return

        # List all group ids for selected shapes
        group_ids = set()
        has_non_group_shape = False
        for shape in self.selected_shapes:
            if shape.group_id is not None:
                group_ids.add(shape.group_id)
            else:
                has_non_group_shape = True

        # If there is at least 1 shape having a group id,
        # use that id as the new group id. Otherwise, generate a new group_id
        new_group_id = None
        if len(group_ids) > 0:
            new_group_id = min(group_ids)
        else:
            new_group_id = self.gen_new_group_id()

        # Merge group ids
        if len(group_ids) > 1:
            self.merge_group_ids(
                group_ids=group_ids, new_group_id=new_group_id
            )
        # Assign new_group_id to non-group shapes
        if has_non_group_shape:
            for shape in self.selected_shapes:
                if shape.group_id is None:
                    shape.group_id = new_group_id

        self.update()

    def ungroup_selected_shapes(self):
        """Ungroup selected shapes"""
        if len(self.selected_shapes) == 0:
            return

        # List all group ids for selected shapes
        group_ids = set()
        for shape in self.selected_shapes:
            if shape.group_id is not None:
                group_ids.add(shape.group_id)

        for group_id in group_ids:
            for shape in self.shapes:
                if shape.group_id == group_id:
                    shape.group_id = None

        self.update()

    def _init_custom_cursors(self):
        """初始化自定义鼠标指针"""
        global CURSOR_GRAB, CURSOR_MOVE, CURSOR_ROTATION3

        try:
            # 创建自定义接触矩形指针
            CURSOR_GRAB = QtGui.QCursor(QtGui.QPixmap(CUSTOM_CURSOR_GRAB_PATH))
        except Exception:
            # 如果自定义指针文件不存在，回退到默认指针
            CURSOR_GRAB = QtCore.Qt.OpenHandCursor

        try:
            # 创建自定义移动指针
            CURSOR_MOVE = QtGui.QCursor(QtGui.QPixmap(CUSTOM_CURSOR_MOVE_PATH))
        except Exception:
            # 如果自定义指针文件不存在，回退到默认指针
            CURSOR_MOVE = QtCore.Qt.ClosedHandCursor

        try:
            # 创建自定义rotation3指针
            CURSOR_ROTATION3 = QtGui.QCursor(QtGui.QPixmap(CUSTOM_CURSOR_ROTATION3_PATH))
        except Exception:
            # 如果自定义指针文件不存在，回退到十字指针
            CURSOR_ROTATION3 = QtCore.Qt.CrossCursor
