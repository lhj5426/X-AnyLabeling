import copy
import math
from typing import List, Optional, Dict, Any, Union

from PyQt5 import QtCore, QtGui

from . import utils
from ..labeling.logger import logger

# TODO(unknown):
# - [opt] Store paths instead of creating new ones at each paint.


DEFAULT_LINE_COLOR = QtGui.QColor(0, 255, 0, 128)  # bf hovering
DEFAULT_FILL_COLOR = QtGui.QColor(255, 168, 0, 100)  # hovering - 橙色半透明
DEFAULT_SELECT_LINE_COLOR = QtGui.QColor(255, 255, 255)  # selected
DEFAULT_CANVAS_SELECT_LINE_COLOR = QtGui.QColor(255, 0, 0)  # mouse selected
DEFAULT_CANVAS_HOVER_LINE_COLOR = QtGui.QColor(0, 255, 255)  # mouse hovered
DEFAULT_SELECT_FILL_COLOR = QtGui.QColor(255, 0, 0, 155)  # selected - 红色半透明
DEFAULT_VERTEX_FILL_COLOR = QtGui.QColor(0, 255, 0, 255)  # hovering
DEFAULT_HVERTEX_FILL_COLOR = QtGui.QColor(255, 255, 255, 255)  # hovering


class Shape:
    """Shape data type"""

    # Render handles as squares
    P_SQUARE = 0

    # Render handles as circles
    P_ROUND = 1

    # Flag for the handles we would move if dragging
    MOVE_VERTEX = 0

    # Flag for all other handles on the current shape
    NEAR_VERTEX = 1

    KEYS = [
        "label",
        "score",
        "points",
        "group_id",
        "difficult",
        "shape_type",
        "flags",
        "description",
        "attributes",
    ]

    # The following class variables influence the drawing of all shape objects.
    line_color = DEFAULT_LINE_COLOR
    fill_color = DEFAULT_FILL_COLOR
    select_line_color = DEFAULT_SELECT_LINE_COLOR
    canvas_select_line_color = DEFAULT_CANVAS_SELECT_LINE_COLOR
    canvas_hover_line_color = DEFAULT_CANVAS_HOVER_LINE_COLOR
    select_fill_color = DEFAULT_SELECT_FILL_COLOR
    vertex_fill_color = DEFAULT_VERTEX_FILL_COLOR
    hvertex_fill_color = DEFAULT_HVERTEX_FILL_COLOR
    point_type = P_ROUND
    point_size = 4
    scale = 1.5
    # Base line width
    line_width = 2.0
    # Additional configurable line widths for different interaction states
    # Fallbacks will use line_width if not overridden via config
    select_line_width = None
    canvas_select_line_width = None
    canvas_hover_line_width = None

    def __init__(
        self,
        label=None,
        score=None,
        line_color=None,
        shape_type=None,
        flags=None,
        group_id=None,
        description=None,
        difficult=False,
        direction=0,
        attributes={},
        kie_linking=[],
    ):
        self.label = label
        self.score = score
        self.group_id = group_id
        self.description = description
        self.difficult = difficult
        self.kie_linking = kie_linking
        self.points = []
        self.fill = True
        self.selected = True
        self.is_mouse_selected = False
        self.is_hovered = False
        self.shape_type = shape_type
        self.flags = flags
        self.other_data = {}
        self.attributes = attributes
        self.cache_label = None
        self.cache_description = None
        self.visible = True

        # Rotation setting
        self.direction = direction
        self.center = None
        self.show_degrees = True

        self._highlight_index = None
        self._highlight_mode = self.NEAR_VERTEX
        self._highlight_settings = {
            self.NEAR_VERTEX: (4, self.P_ROUND),
            self.MOVE_VERTEX: (1.5, self.P_SQUARE),
        }

        self._vertex_fill_color = None

        self._closed = False

        if line_color is not None:
            # Override the class line_color attribute
            # with an object attribute. Currently this
            # is used for drawing the pending line a different color.
            self.line_color = line_color
        self.shape_type = shape_type

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the shape to a dictionary representation for serialization.

        This method creates a complete dictionary representation of the shape
        containing all essential properties, points, and metadata. The dictionary
        format is suitable for JSON serialization and file storage.

        Returns:
            Dict[str, Any]: Dictionary containing all shape data with keys:
                - label: Shape label text
                - score: Confidence score if available
                - points: List of (x, y) coordinate tuples
                - group_id: Group identifier for related shapes
                - description: Text description
                - difficult: Boolean indicating difficult annotation
                - shape_type: Type string (polygon, rectangle, etc.)
                - flags: Dictionary of boolean flags
                - attributes: Custom attribute dictionary
                - kie_linking: Key information extraction links
                - direction: Rotation angle for rotated rectangles
                - other custom data from other_data dict

        Examples:
            >>> shape = Shape(label="cat", shape_type="rectangle")
            >>> shape_dict = shape.to_dict()
            >>> print(shape_dict["label"])  # "cat"
            >>> print(shape_dict["shape_type"])  # "rectangle"
            
        Note:
            Points are converted from QPointF objects to (x, y) tuples.
            Rotation shapes include additional 'direction' field.
        """
        dictData = {
            "label": self.label,
            "score": self.score,
            "points": [(p.x(), p.y()) for p in self.points],
            "group_id": self.group_id,
            "description": self.description,
            "difficult": self.difficult,
            "shape_type": self.shape_type,
            "flags": self.flags,
            "attributes": self.attributes,
            "kie_linking": self.kie_linking,
        }
        if self.shape_type == "rotation":
            dictData["direction"] = self.direction
        dictData = {
            **self.other_data,
            **dictData,
        }
        return dictData

    def load_from_dict(self, data: Dict[str, Any], close: bool = True) -> "Shape":
        """
        Load shape data from a dictionary representation.

        This method populates the shape with data from a dictionary, typically
        loaded from JSON files or other serialized formats. It reconstructs all
        shape properties, points, and metadata from the provided data.

        Args:
            data (Dict[str, Any]): Dictionary containing shape data with keys:
                - label: Shape label text (required)
                - score: Confidence score (optional)
                - points: List of [x, y] coordinate pairs (required)
                - group_id: Group identifier (optional)
                - description: Text description (optional, defaults to "")
                - difficult: Boolean for difficult annotation (optional, defaults to False)
                - shape_type: Type string (optional, defaults to "polygon")
                - flags: Dictionary of boolean flags (optional, defaults to {})
                - attributes: Custom attributes (optional, defaults to {})
                - kie_linking: KIE links (optional, defaults to [])
                - direction: Rotation angle for "rotation" type (optional, defaults to 0)
            close (bool): Whether to close the shape after loading (defaults to True).

        Returns:
            Shape: Self reference for method chaining.

        Examples:
            >>> shape_data = {
            ...     "label": "person",
            ...     "points": [[10, 20], [30, 40], [50, 60]],
            ...     "shape_type": "polygon"
            ... }
            >>> shape = Shape().load_from_dict(shape_data)
            >>> print(shape.label)  # "person"
            >>> print(len(shape.points))  # 3
            
        Note:
            Points are converted from [x, y] lists to QPointF objects.
            Extra data not in KEYS is stored in other_data dictionary.
        """
        self.label = data["label"]
        self.score = data.get("score")
        self.points = [QtCore.QPointF(p[0], p[1]) for p in data["points"]]
        self.group_id = data.get("group_id")
        self.description = data.get("description", "")
        self.difficult = data.get("difficult", False)
        self.shape_type = data.get("shape_type", "polygon")
        self.flags = data.get("flags", {})
        self.attributes = data.get("attributes", {})
        self.kie_linking = data.get("kie_linking", [])
        if self.shape_type == "rotation":
            self.direction = data.get("direction", 0)
        self.other_data = {k: v for k, v in data.items() if k not in self.KEYS}
        if close:
            self.close()
        return self

    @property
    def shape_type(self):
        """Get shape type (polygon, rectangle, rotation, point, line, ...)"""
        return self._shape_type

    @shape_type.setter
    def shape_type(self, value):
        """Set shape type"""
        if value is None:
            value = "polygon"
        if value not in self.get_supported_shape():
            raise ValueError(f"Unexpected shape_type: {value}")
        self._shape_type = value

    @staticmethod
    def get_supported_shape():
        return [
            "polygon",
            "rectangle",
            "rotation",
            "point",
            "line",
            "circle",
            "linestrip",
        ]

    def close(self):
        """Close the shape"""
        if self.shape_type == "rotation" and len(self.points) == 4:
            cx = (self.points[0].x() + self.points[2].x()) / 2
            cy = (self.points[0].y() + self.points[2].y()) / 2
            self.center = QtCore.QPointF(cx, cy)
        self._closed = True

    def reach_max_points(self):
        if len(self.points) >= 4:
            return True
        return False

    def add_point(self, point: QtCore.QPointF) -> None:
        """
        Add a new point to the shape.

        This method adds a point to the shape, with behavior that depends on
        the shape type. Rectangle shapes have a maximum of 4 points, while
        polygon and linestrip shapes can accept unlimited points.

        Args:
            point (QtCore.QPointF): The point to add to the shape.

        Returns:
            None

        Examples:
            >>> shape = Shape(shape_type="polygon")
            >>> shape.add_point(QtCore.QPointF(10, 20))
            >>> shape.add_point(QtCore.QPointF(30, 40))
            >>> print(len(shape.points))  # 2
            
            >>> # Rectangle shapes are limited to 4 points
            >>> rect = Shape(shape_type="rectangle")
            >>> rect.add_point(QtCore.QPointF(0, 0))
            >>> print(rect.reach_max_points())  # False (until 4 points)
            
        Note:
            For polygon shapes, adding the first point again will close the shape.
            Rectangle shapes automatically limit points to prevent overflow.
        """
        if self.shape_type == "rectangle":
            if not self.reach_max_points():
                self.points.append(point)
        else:
            if self.points and point == self.points[0]:
                self.close()
            else:
                self.points.append(point)

    def can_add_point(self) -> bool:
        """
        Check if the shape can accept additional points.

        This method determines whether the current shape type supports
        adding more points based on its geometric constraints.

        Returns:
            bool: True if more points can be added, False otherwise.

        Examples:
            >>> polygon = Shape(shape_type="polygon")
            >>> print(polygon.can_add_point())  # True
            
            >>> line_strip = Shape(shape_type="linestrip")
            >>> print(line_strip.can_add_point())  # True
            
            >>> rectangle = Shape(shape_type="rectangle")
            >>> print(rectangle.can_add_point())  # False (fixed geometry)
            
        Note:
            Only polygon and linestrip shapes support dynamic point addition.
            Other shapes have fixed geometries that don't accept new points.
        """
        return self.shape_type in ["polygon", "linestrip"]

    def pop_point(self):
        """Remove and return the last point of the shape"""
        if self.points:
            return self.points.pop()
        return None

    def insert_point(self, i, point):
        """Insert a point to a specific index"""
        self.points.insert(i, point)

    def remove_point(self, i):
        """Remove point from a specific index"""
        self.points.pop(i)

    def is_closed(self):
        """Check if the shape is closed"""
        return self._closed

    def set_open(self):
        """Set shape to open - (_close=False)"""
        self._closed = False

    def get_rect_from_line(self, pt1, pt2):
        """Get rectangle from diagonal line"""
        x1, y1 = pt1.x(), pt1.y()
        x2, y2 = pt2.x(), pt2.y()
        return QtCore.QRectF(x1, y1, x2 - x1, y2 - y1)

    def paint(self, painter: QtGui.QPainter):  # noqa: max-complexity: 18
        """Paint shape using QPainter"""
        if self.points:
            if self.is_mouse_selected:
                color = self.canvas_select_line_color
                width = (
                    self.canvas_select_line_width
                    if self.canvas_select_line_width is not None
                    else self.line_width
                )
            elif self.is_hovered:
                color = self.canvas_hover_line_color
                width = (
                    self.canvas_hover_line_width
                    if self.canvas_hover_line_width is not None
                    else self.line_width
                )
            elif self.selected:
                color = self.select_line_color
                width = (
                    self.select_line_width
                    if self.select_line_width is not None
                    else self.line_width
                )
            else:
                color = self.line_color
                width = self.line_width
            pen = QtGui.QPen(color)
            # Try using integer sizes for smoother drawing(?)
            pen.setWidth(max(1, int(round(width / self.scale))))
            painter.setPen(pen)

            line_path = QtGui.QPainterPath()
            vrtx_path = QtGui.QPainterPath()

            if self.shape_type == "rectangle":
                assert len(self.points) in [1, 2, 4]
                if len(self.points) == 2:
                    rectangle = self.get_rect_from_line(*self.points)
                    line_path.addRect(rectangle)
                if len(self.points) == 4:
                    line_path.moveTo(self.points[0])
                    for i, p in enumerate(self.points):
                        line_path.lineTo(p)
                        if self.selected:
                            self.draw_vertex(vrtx_path, i)
                    if self.is_closed() or self.label is not None:
                        line_path.lineTo(self.points[0])
            elif self.shape_type == "rotation":
                assert len(self.points) in [1, 2, 4]
                if len(self.points) == 2:
                    rectangle = self.get_rect_from_line(*self.points)
                    line_path.addRect(rectangle)
                if len(self.points) == 4:
                    line_path.moveTo(self.points[0])
                    for i, p in enumerate(self.points):
                        line_path.lineTo(p)
                        if self.selected:
                            self.draw_vertex(vrtx_path, i)
                    if self.is_closed() or self.label is not None:
                        line_path.lineTo(self.points[0])
            elif self.shape_type == "circle":
                assert len(self.points) in [1, 2]
                if len(self.points) == 2:
                    rectangle = self.get_circle_rect_from_line(self.points)
                    line_path.addEllipse(rectangle)
                if self.selected:
                    for i in range(len(self.points)):
                        self.draw_vertex(vrtx_path, i)
            elif self.shape_type == "linestrip":
                line_path.moveTo(self.points[0])
                for i, p in enumerate(self.points):
                    line_path.lineTo(p)
                    if self.selected:
                        self.draw_vertex(vrtx_path, i)
            elif self.shape_type == "point":
                assert len(self.points) == 1
                self.draw_vertex(vrtx_path, 0, True)
            else:
                line_path.moveTo(self.points[0])
                # Uncommenting the following line will draw 2 paths
                # for the 1st vertex, and make it non-filled, which
                # may be desirable.
                self.draw_vertex(vrtx_path, 0)

                for i, p in enumerate(self.points):
                    line_path.lineTo(p)
                    if self.selected:
                        self.draw_vertex(vrtx_path, i)
                if self.is_closed():
                    line_path.lineTo(self.points[0])

            painter.drawPath(line_path)
            painter.drawPath(vrtx_path)
            if self._vertex_fill_color is not None:
                painter.fillPath(vrtx_path, self._vertex_fill_color)
            if self.fill:
                color = (
                    self.select_fill_color
                    if self.selected
                    else self.fill_color
                )
                painter.fillPath(line_path, color)

    def draw_vertex(self, path, i, show_difficult=False):
        """Draw a vertex"""
        d = self.point_size / self.scale
        shape = self.point_type
        point = self.points[i]
        if i == self._highlight_index:
            size, shape = self._highlight_settings[self._highlight_mode]
            d *= size
        if self._highlight_index is not None:
            self._vertex_fill_color = self.hvertex_fill_color
        else:
            self._vertex_fill_color = self.vertex_fill_color
        if shape in (self.P_SQUARE, self.P_ROUND):
            if self.difficult and show_difficult:
                scale_factor = 1.5
                triangle_path = QtGui.QPainterPath()
                triangle_path.moveTo(
                    point.x(), point.y() - d * scale_factor / 2
                )
                triangle_path.lineTo(
                    point.x() - d * scale_factor / 2,
                    point.y() + d * scale_factor / 2,
                )
                triangle_path.lineTo(
                    point.x() + d * scale_factor / 2,
                    point.y() + d * scale_factor / 2,
                )
                triangle_path.closeSubpath()
                path.addPath(triangle_path)
                if shape == self.P_ROUND:
                    path.addPath(triangle_path)
            else:
                if shape == self.P_SQUARE:
                    path.addRect(point.x() - d / 2, point.y() - d / 2, d, d)
                elif shape == self.P_ROUND:
                    path.addEllipse(point, d / 2.0, d / 2.0)
        else:
            logger.error("Unsupported vertex shape")

    def nearest_vertex(self, point, epsilon):
        """Find the index of the nearest vertex to a point
        Only consider if the distance is smaller than epsilon
        """
        min_distance = float("inf")
        min_i = None
        for i, p in enumerate(self.points):
            dist = utils.distance(p - point)
            if dist <= epsilon and dist < min_distance:
                min_distance = dist
                min_i = i
        return min_i

    def nearest_edge(self, point, epsilon):
        """Get nearest edge index"""
        min_distance = float("inf")
        post_i = None
        for i in range(len(self.points)):
            line = [self.points[i - 1], self.points[i]]
            dist = utils.distance_to_line(point, line)
            if dist <= epsilon and dist < min_distance:
                min_distance = dist
                post_i = i
        return post_i

    def contains_point(self, point: QtCore.QPointF) -> bool:
        """
        Check if a point lies within the shape's boundaries.

        This method performs geometric hit testing to determine if a given
        point is contained within the shape's area. It uses the shape's
        path representation for accurate boundary detection.

        Args:
            point (QtCore.QPointF): The point to test for containment.

        Returns:
            bool: True if the point is inside the shape, False otherwise.

        Examples:
            >>> # Create a rectangle shape
            >>> rect = Shape(shape_type="rectangle")
            >>> rect.points = [QPointF(0, 0), QPointF(100, 100)]
            >>> 
            >>> # Test point inside rectangle
            >>> inside_point = QPointF(50, 50)
            >>> print(rect.contains_point(inside_point))  # True
            >>> 
            >>> # Test point outside rectangle
            >>> outside_point = QPointF(150, 150)
            >>> print(rect.contains_point(outside_point))  # False
            
        Note:
            Uses QPainterPath.contains() for accurate geometric calculations.
            Works with all shape types including polygons, rectangles, and circles.
        """
        return self.make_path().contains(point)

    def get_circle_rect_from_line(self, line):
        """Computes parameters to draw with `QPainterPath::addEllipse`"""
        if len(line) != 2:
            return None
        (c, _) = line
        r = line[0] - line[1]
        d = math.sqrt(math.pow(r.x(), 2) + math.pow(r.y(), 2))
        rectangle = QtCore.QRectF(c.x() - d, c.y() - d, 2 * d, 2 * d)
        return rectangle

    def make_path(self):
        """Create a path from shape"""
        if self.shape_type == "rectangle":
            path = QtGui.QPainterPath(self.points[0])
            for p in self.points[1:]:
                path.lineTo(p)
        elif self.shape_type == "circle":
            path = QtGui.QPainterPath()
            if len(self.points) == 2:
                rectangle = self.get_circle_rect_from_line(self.points)
                path.addEllipse(rectangle)
        else:
            path = QtGui.QPainterPath(self.points[0])
            for p in self.points[1:]:
                path.lineTo(p)
        return path

    def bounding_rect(self):
        """Return bounding rectangle of the shape"""
        return self.make_path().boundingRect()

    def move_by(self, offset: QtCore.QPointF) -> None:
        """
        Move all points of the shape by a specified offset.

        This method translates the entire shape by applying the same offset
        to all points, effectively moving the shape to a new position while
        maintaining its relative geometry and proportions.

        Args:
            offset (QtCore.QPointF): The translation vector to apply to all points.

        Returns:
            None

        Examples:
            >>> # Create a shape with some points
            >>> shape = Shape()
            >>> shape.points = [QPointF(10, 10), QPointF(20, 20)]
            >>> 
            >>> # Move shape 5 pixels right and 3 pixels down
            >>> offset = QPointF(5, 3)
            >>> shape.move_by(offset)
            >>> print(shape.points[0])  # QPointF(15, 13)
            >>> print(shape.points[1])  # QPointF(25, 23)
            
        Note:
            This operation modifies the shape in-place and affects all points.
            The shape's relative geometry and size remain unchanged.
        """
        self.points = [p + offset for p in self.points]

    def move_vertex_by(self, i: int, offset: QtCore.QPointF) -> None:
        """
        Move a specific vertex by an offset while keeping others fixed.

        This method moves only the vertex at the specified index, allowing
        for shape deformation and vertex-level editing. This is commonly used
        for interactive shape editing where users drag individual vertices.

        Args:
            i (int): Index of the vertex to move (0-based).
            offset (QtCore.QPointF): The translation vector for the vertex.

        Returns:
            None

        Examples:
            >>> # Create a triangle
            >>> shape = Shape()
            >>> shape.points = [QPointF(0, 0), QPointF(10, 0), QPointF(5, 10)]
            >>> 
            >>> # Move the second vertex (index 1) up by 5 pixels
            >>> shape.move_vertex_by(1, QPointF(0, -5))
            >>> print(shape.points[1])  # QPointF(10, -5)
            >>> # Other vertices remain unchanged
            >>> print(shape.points[0])  # QPointF(0, 0)
            
        Note:
            Index must be valid (0 <= i < len(points)) or IndexError will occur.
            This enables precise vertex-level shape manipulation for editing.
        """
        self.points[i] = self.points[i] + offset

    def highlight_vertex(self, i, action):
        """Highlight a vertex appropriately based on the current action

        Args:
            i (int): The vertex index
            action (int): The action
            (see Shape.NEAR_VERTEX and Shape.MOVE_VERTEX)
        """
        self._highlight_index = i
        self._highlight_mode = action

    def highlight_clear(self):
        """Clear the highlighted point"""
        self._highlight_index = None

    def copy(self) -> "Shape":
        """
        Create a deep copy of the shape.

        This method creates a completely independent copy of the shape,
        including all points, properties, and metadata. The copy can be
        modified without affecting the original shape.

        Returns:
            Shape: A new Shape instance that is a deep copy of this shape.

        Examples:
            >>> original = Shape(label="cat", shape_type="rectangle")
            >>> original.points = [QPointF(0, 0), QPointF(10, 10)]
            >>> 
            >>> # Create independent copy
            >>> copied = original.copy()
            >>> copied.label = "dog"  # Doesn't affect original
            >>> print(original.label)  # Still "cat"
            >>> print(copied.label)    # Now "dog"
            
        Note:
            Uses deep copy to ensure complete independence between shapes.
            All nested objects (points, attributes, etc.) are also copied.
        """
        return copy.deepcopy(self)

    def __len__(self):
        return len(self.points)

    def __getitem__(self, key):
        return self.points[key]

    def __setitem__(self, key, value):
        self.points[key] = value
