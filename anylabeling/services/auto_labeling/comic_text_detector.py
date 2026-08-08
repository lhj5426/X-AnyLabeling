import math
import numpy as np

from PyQt5.QtCore import QCoreApplication, QPointF

from .model import Model
from .types import AutoLabelingResult
from anylabeling.views.labeling.shape import Shape
from anylabeling.views.labeling.logger import logger

from .ctd import CTDInference


def _is_rotated_box(points):
    """Check if a 4-point quadrilateral is truly rotated (not 0/90/180/270)."""
    if len(points) < 4:
        return False
    pt1, pt2 = points[0], points[1]
    dx = pt2[0] - pt1[0]
    dy = pt2[1] - pt1[1]
    if abs(dx) < 1 and abs(dy) < 1:
        return False
    angle = abs(math.degrees(math.atan2(dy, dx)))
    angle_mod = angle % 90
    if angle_mod > 45:
        angle_mod = 90 - angle_mod
    return angle_mod > 0


class ComicTextDetector(Model):
    class Meta:
        required_config_names = [
            "model_path",
            "type",
            "name",
            "display_name",
        ]
        widgets = [
            "button_run",
            "input_conf",
            "edit_conf",
            "input_iou",
            "edit_iou",
            "toggle_end2end",
            "toggle_preserve_existing_annotations",
            "toggle_rotation",
            "toggle_filter_non_rotated",
            "button_filter_classes",
        ]
        output_modes = {
            "rectangle": QCoreApplication.translate("Model", "Rectangle"),
        }
        default_output_mode = "rectangle"

    def __init__(self, model_config, on_message):
        super().__init__(model_config, on_message)
        model_abs_path = self.get_model_abs_path(model_config, "model_path")
        if model_abs_path is None:
            raise FileNotFoundError(
                QCoreApplication.translate(
                    "Model", "Model file not found: {path}"
                ).format(path=model_config.get("model_path", "unknown"))
            )

        detect_size = model_config.get("detect_size", 1024)
        device = model_config.get("device", "cpu")
        if device == "cuda":
            import torch
            if not torch.cuda.is_available():
                logger.warning("CUDA not available, falling back to CPU")
                device = "cpu"

        self.model = CTDInference(
            model_path=model_abs_path,
            detect_size=detect_size,
            device=device,
            half=False,
            conf_thresh=model_config.get("conf_thresh", 0.4),
            nms_thresh=model_config.get("nms_thresh", 0.35),
            db_thresh=model_config.get("db_thresh", 0.3),
            db_box_thresh=model_config.get("db_box_thresh", 0.6),
        )

        self.classes = ["text_block", "text_line"]
        self.max_shapes = int(model_config.get("max_shapes", 300))

        # UI control state
        self.replace = True
        self.conf_thres = float(model_config.get("conf_threshold", 0.4))
        self.iou_thres = float(model_config.get("iou_threshold", 0.5))
        self.end2end = model_config.get("end2end", False)
        self.use_rotation = model_config.get("use_rotation", False)
        self.filter_non_rotated = model_config.get("filter_non_rotated", False)
        self.filter_classes = None  # set by apply_filter_classes

    def set_auto_labeling_conf(self, value):
        self.conf_thres = value
        self.model.conf_thresh = value
        self.model.db_box_thresh = value

    def set_auto_labeling_iou(self, value):
        self.iou_thres = value
        self.model.nms_thresh = value

    def set_auto_labeling_end2end_state(self, state):
        self.end2end = state

    def set_auto_labeling_preserve_existing_annotations_state(self, state):
        self.replace = not state

    def set_auto_labeling_rotation_state(self, state):
        self.use_rotation = state

    def set_auto_labeling_filter_non_rotated(self, state):
        self.filter_non_rotated = state

    def predict_shapes(self, image, filename=None):
        if image is None:
            return AutoLabelingResult([], replace=self.replace)

        import cv2
        import os

        if isinstance(image, str) and os.path.isfile(image):
            img = cv2.imdecode(np.fromfile(image, dtype=np.uint8), cv2.IMREAD_COLOR)
        elif isinstance(image, np.ndarray):
            img = image
        else:
            qimage = self.load_image_from_filename(filename)
            if qimage is None:
                return AutoLabelingResult([], replace=self.replace)
            img = self._qimage_to_bgr(qimage)

        if img is None or img.size == 0:
            return AutoLabelingResult([], replace=self.replace)

        blk_bboxes, blk_confs, lines, line_scores = self.model(img)

        shapes = []

        # YOLOv5 text-block rectangles (always axis-aligned)
        for i in range(len(blk_bboxes)):
            if self.use_rotation and self.filter_non_rotated:
                # text_block is always axis-aligned from YOLO; drop when filtering non-rotated
                continue
            x1, y1, x2, y2 = blk_bboxes[i].tolist()
            shape = Shape(
                label="text_block",
                score=float(blk_confs[i]),
                shape_type="rectangle",
                description="",
            )
            shape.add_point(QPointF(x1, y1))
            shape.add_point(QPointF(x2, y1))
            shape.add_point(QPointF(x2, y2))
            shape.add_point(QPointF(x1, y2))
            shapes.append(shape)

        # DB text-line quadrilaterals
        for idx, line in enumerate(lines):
            pts = line.reshape(4, 2)
            pts_list = pts.tolist()
            is_rot = _is_rotated_box(pts_list)
            line_score = float(line_scores[idx]) if idx < len(line_scores) else 0.0

            # Rotation switch filtering
            if not self.use_rotation and is_rot:
                # Drop rotated boxes when rotation is off
                continue
            if self.use_rotation and self.filter_non_rotated and not is_rot:
                # Drop non-rotated boxes when filtering them out
                continue

            if self.use_rotation:
                # Output as rotation shape with direction
                pt1, pt2 = pts_list[0], pts_list[1]
                dx = pt2[0] - pt1[0]
                dy = pt2[1] - pt1[1]
                dir_angle = math.atan2(dy, dx)
                if dir_angle < 0:
                    dir_angle += 2 * math.pi

                shape = Shape(
                    label="text_line",
                    score=line_score,
                    shape_type="rotation",
                    direction=dir_angle,
                    description="",
                )
                for pt in pts_list:
                    shape.add_point(QPointF(float(pt[0]), float(pt[1])))
            else:
                # Axis-aligned rectangle from min/max bbox
                x1 = int(np.min(pts[:, 0]))
                y1 = int(np.min(pts[:, 1]))
                x2 = int(np.max(pts[:, 0]))
                y2 = int(np.max(pts[:, 1]))
                if x2 <= x1 or y2 <= y1:
                    continue
                shape = Shape(
                    label="text_line",
                    score=line_score,
                    shape_type="rectangle",
                    description="",
                )
                shape.add_point(QPointF(x1, y1))
                shape.add_point(QPointF(x2, y1))
                shape.add_point(QPointF(x2, y2))
                shape.add_point(QPointF(x1, y2))
            shapes.append(shape)

        # Apply class filter (button_filter_classes sets self.filter_classes to list[int] or None)
        if self.filter_classes is not None:
            allowed = {self.classes[i] for i in self.filter_classes}
            shapes = [s for s in shapes if s.label in allowed]

        # Limit max shapes
        if len(shapes) > self.max_shapes:
            shapes = shapes[:self.max_shapes]

        return AutoLabelingResult(shapes, replace=self.replace)

    def unload(self):
        if self.model is not None:
            del self.model
            self.model = None
            import gc
            gc.collect()

    @staticmethod
    def _qimage_to_bgr(qimage):
        qimage = qimage.convertToFormat(4)
        ptr = qimage.bits()
        ptr.setsize(qimage.byteCount())
        arr = np.array(ptr).reshape(qimage.height(), qimage.width(), 4)
        return arr[..., [2, 1, 0]].copy()