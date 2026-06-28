"""
Manga OCR model for X-AnyLabeling.
Combines DBNet+ResNet34 text detector and 48px autoregressive Transformer OCR.
Ported from manga-image-translator (zyddnys).
"""

import gc
import math
import os
import time

import cv2
import einops
import numpy as np
import torch
from PyQt5 import QtCore

from anylabeling.app_info import __preferred_device__
from anylabeling.views.labeling.utils.opencv import qt_img_to_rgb_cv_img
from anylabeling.views.labeling.shape import Shape

from .model import Model
from .types import AutoLabelingResult
from .manga_ocr_arch.dbnet_resnet34 import TextDetection
from .manga_ocr_arch.model_48px import OCR
from .manga_ocr_arch.dbnet_utils import SegDetectorRepresenter
from .manga_ocr_arch.craft_utils import adjustResultCoordinates
from .manga_ocr_arch.imgproc import resize_aspect_ratio
from .manga_ocr_arch.text_region import extract_text_region, sort_quadrilateral_points


class MangaOCR(Model):
    """Manga OCR model combining DBNet detection and 48px Transformer OCR."""

    class Meta:
        required_config_names = [
            "type",
            "name",
            "display_name",
            "det_model_path",
            "ocr_model_path",
            "ocr_char_dict_path",
        ]
        widgets = [
            "button_run",
            "button_recog_selected",
            "button_recog_all",
            "button_filter_classes",
            "toggle_use_existing_boxes",
            "button_detect_only",
            "button_color_only",
            "button_recog_color",
            "toggle_preserve_existing_annotations",
            "toggle_rotation",
            "toggle_filter_non_rotated",
            "toggle_batch_detect_only",
            "toggle_color_mode",
        ]
        output_modes = {
            "rectangle": "Rectangle",
            "rotation": "Rotation",
        }
        default_output_mode = "rectangle"

    def __init__(self, model_config, on_message=None):
        super().__init__(model_config, on_message)

        # Project root: 4 levels up from this file
        # anylabeling/services/auto_labeling/manga_ocr.py → project root
        self._project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )
        print(f"[MangaOCR] 项目根目录: {self._project_root}")

        # Determine device
        if __preferred_device__ == "GPU" and torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"
        print(f"[MangaOCR] 设备: {self.device}")

        # Load DBNet detector
        det_model_path = self._resolve_model_path("det_model_path")
        print(f"[MangaOCR] 检测模型路径: {det_model_path}")
        print(f"[MangaOCR] 检测模型存在: {os.path.exists(det_model_path) if det_model_path else False}")
        if not det_model_path or not os.path.exists(det_model_path):
            raise FileNotFoundError(f"Detection model not found: {det_model_path}")
        self.on_message(f"Loading DBNet detector from {det_model_path}...")
        self.det_model = TextDetection()
        sd = torch.load(det_model_path, map_location="cpu")
        if isinstance(sd, dict) and "model" in sd:
            sd = sd["model"]
        self.det_model.load_state_dict(sd)
        self.det_model.eval()
        if self.device == "cuda":
            self.det_model = self.det_model.to(self.device)

        # Load 48px OCR model
        ocr_model_path = self._resolve_model_path("ocr_model_path")
        dict_path = self._resolve_model_path("ocr_char_dict_path")
        print(f"[MangaOCR] OCR模型路径: {ocr_model_path}")
        print(f"[MangaOCR] OCR模型存在: {os.path.exists(ocr_model_path) if ocr_model_path else False}")
        print(f"[MangaOCR] 字典路径: {dict_path}")
        print(f"[MangaOCR] 字典存在: {os.path.exists(dict_path) if dict_path else False}")
        if not ocr_model_path or not os.path.exists(ocr_model_path):
            raise FileNotFoundError(f"OCR model not found: {ocr_model_path}")
        dict_path = self._resolve_model_path("ocr_char_dict_path")
        if not dict_path or not os.path.exists(dict_path):
            raise FileNotFoundError(f"Dictionary not found: {dict_path}")

        self.on_message(f"Loading 48px OCR model from {ocr_model_path}...")
        with open(dict_path, "r", encoding="utf-8") as fp:
            self.dictionary = [s[:-1] for s in fp.readlines()]

        self.ocr_model = OCR(self.dictionary, 768)
        sd = torch.load(ocr_model_path, map_location="cpu", weights_only=False)
        if isinstance(sd, dict) and "state_dict" in sd:
            sd = sd["state_dict"]
        cleaned_sd = {}
        for k, v in sd.items():
            if k.startswith("model."):
                cleaned_sd[k[6:]] = v
            else:
                cleaned_sd[k] = v
        self.ocr_model.load_state_dict(cleaned_sd)
        self.ocr_model.eval()
        if self.device == "cuda":
            self.ocr_model = self.ocr_model.to(self.device)

        # Read config parameters
        self.detect_size = int(self.config.get("detect_size", 2048))
        self.text_threshold = float(self.config.get("text_threshold", 0.5))
        self.box_threshold = float(self.config.get("box_threshold", 0.7))
        self.unclip_ratio = float(self.config.get("unclip_ratio", 2.3))
        self.ocr_threshold = float(self.config.get("ocr_threshold", 0.2))
        self.text_height = 48
        self.max_chunk_size = 16

        self.replace = True
        self.use_rotation = False
        self.filter_non_rotated = False
        self.color_mode = False  # Toggle: when True, 运行 uses color-only instead of OCR
        self.on_message("Manga OCR model loaded successfully.")

    def _resolve_model_path(self, config_key):
        """Resolve model path: absolute path if exists, else relative to project root.
        Makes the model portable — follows the software directory."""
        path = self.config.get(config_key, "")
        if not path:
            return None
        # URL: defer to base class for download
        if path.startswith(("http://", "https://")):
            return self.get_model_abs_path(self.config, config_key)
        # Absolute path that exists: use directly
        if os.path.isabs(path) and os.path.exists(path):
            return path
        # Relative path: resolve against project root
        abs_path = os.path.normpath(os.path.join(self._project_root, path))
        if os.path.exists(abs_path):
            return abs_path
        # Fallback: try get_model_abs_path (relative to config file dir)
        try:
            return self.get_model_abs_path(self.config, config_key)
        except Exception:
            return abs_path  # Return the computed path so error message is helpful

    def _load_image(self, image, filename=None):
        """Load image as BGR numpy array."""
        if filename:
            try:
                image = cv2.imdecode(np.fromfile(filename, dtype=np.uint8), -1)
                if image is None:
                    image = qt_img_to_rgb_cv_img(image)
                    image = image[:, :, ::-1]
            except Exception:
                image = qt_img_to_rgb_cv_img(image)
                image = image[:, :, ::-1]
        else:
            image = qt_img_to_rgb_cv_img(image)
            image = image[:, :, ::-1]
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        elif len(image.shape) == 3 and image.shape[2] == 4:
            # RGBA → BGR with proper alpha blending
            image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
        # Ensure uint8
        if image.dtype != np.uint8:
            image = image.astype(np.uint8)
        return image

    def _run_detection(self, image):
        """Run DBNet detection on the image. Returns list of (boxes, scores)."""
        # Bilateral filter
        img_filtered = cv2.bilateralFilter(image, 17, 80, 80)

        # Resize maintaining aspect ratio
        img_resized, ratio, _, _, _ = resize_aspect_ratio(
            img_filtered, self.detect_size, cv2.INTER_LINEAR, mag_ratio=1
        )
        img_resized_h, img_resized_w = img_resized.shape[:2]

        # Normalize and convert to tensor
        img_tensor = torch.from_numpy(img_resized).float() / 127.5 - 1.0
        img_tensor = einops.rearrange(img_tensor, "H W C -> 1 C H W")
        img_tensor = img_tensor.to(self.device)

        # Forward pass
        with torch.no_grad():
            db, mask = self.det_model(img_tensor)
        db = db.sigmoid().cpu()

        # Extract boxes
        det = SegDetectorRepresenter(
            self.text_threshold, self.box_threshold, unclip_ratio=self.unclip_ratio
        )
        boxes_batch, scores_batch = det(
            {"shape": [(img_resized_h, img_resized_w)]}, db
        )
        boxes = boxes_batch[0] if len(boxes_batch) > 0 else []
        scores = scores_batch[0] if len(scores_batch) > 0 else []

        if len(boxes) == 0:
            return [], []

        # Filter out zero-area boxes
        valid_boxes = []
        valid_scores = []
        for i, box in enumerate(boxes):
            if box is not None and len(box) > 0:
                pts = np.array(box, dtype=np.float32)
                if pts.shape[0] >= 4:
                    valid_boxes.append(pts.reshape(-1, 2))
                    valid_scores.append(float(scores[i]))

        if len(valid_boxes) == 0:
            return [], []

        # Adjust coordinates back to original image size
        # Use uniform resize ratio (both dimensions scaled identically, padding excluded)
        inv_ratio = 1.0 / ratio
        adjusted_boxes = []
        adjusted_scores = []
        for i, box in enumerate(valid_boxes):
            adjusted = box.copy()
            adjusted[:, 0] *= inv_ratio
            adjusted[:, 1] *= inv_ratio
            # Filter out zero-width/zero-height boxes
            x_min, y_min = adjusted.min(axis=0)
            x_max, y_max = adjusted.max(axis=0)
            if int(x_max - x_min) < 2 or int(y_max - y_min) < 2:
                continue
            adjusted_boxes.append(adjusted)
            adjusted_scores.append(valid_scores[i])

        return adjusted_boxes, adjusted_scores

    def _run_color_only(self, image, boxes):
        """Fast color-only: backbone + encoder + 1 decoder step, no beam search.
        Returns list of (fg_color, bg_color) for each box."""
        if len(boxes) == 0:
            return []

        # Extract text regions
        regions = []
        for box in boxes:
            region, _ = extract_text_region(image, box, self.text_height)
            regions.append(region)

        # Sort by width for efficient batching
        perm = sorted(range(len(regions)), key=lambda x: regions[x].shape[1])

        results = [None] * len(boxes)
        for i in range(0, len(perm), self.max_chunk_size):
            indices = perm[i:i + self.max_chunk_size]
            valid_regions = [regions[idx] for idx in indices]
            valid_widths = [r.shape[1] for r in valid_regions]

            N = len(indices)
            max_width = max(valid_widths)
            max_width = (max_width + 3) // 4 * 4

            region_array = np.zeros((N, self.text_height, max_width, 3), dtype=np.uint8)
            for j, r in enumerate(valid_regions):
                W = r.shape[1]
                region_array[j, :, :W, :] = r

            # BGR → RGB
            region_array = region_array[:, :, :, ::-1].copy()

            img_tensor = (torch.from_numpy(region_array).float() - 127.5) / 127.5
            img_tensor = einops.rearrange(img_tensor, "N H W C -> N C H W")
            img_tensor = img_tensor.to(self.device)

            with torch.no_grad():
                fg_pred, bg_pred, fg_ind_pred, bg_ind_pred = self.ocr_model.infer_color_only(
                    img_tensor, valid_widths
                )

            for j in range(N):
                has_fg = (fg_ind_pred[j, 1] > fg_ind_pred[j, 0]).item()
                has_bg = (bg_ind_pred[j, 1] > bg_ind_pred[j, 0]).item()

                if has_fg:
                    fr = int(np.clip(fg_pred[j, 0].item() * 255, 0, 255))
                    fg = int(np.clip(fg_pred[j, 1].item() * 255, 0, 255))
                    fb = int(np.clip(fg_pred[j, 2].item() * 255, 0, 255))
                    fg_color = (fr, fg, fb)
                    fg_lum = 0.299 * fr + 0.587 * fg + 0.114 * fb
                    bg_color = (0, 0, 0) if fg_lum > 190 else (255, 255, 255)
                else:
                    fg_color = None
                    bg_color = None

                results[indices[j]] = (fg_color, bg_color)

        return results

    def _run_ocr(self, image, boxes):
        """Run 48px OCR on detected text regions.
        Returns list of (text, prob, fg_color, bg_color) for each box."""
        if len(boxes) == 0:
            return []

        # Extract text regions
        regions = []
        directions = []
        for box in boxes:
            region, direction = extract_text_region(image, box, self.text_height)
            regions.append(region)
            directions.append(direction)

        # Sort by width for efficient batching
        perm = sorted(range(len(regions)), key=lambda x: regions[x].shape[1])

        results = [None] * len(boxes)
        for i in range(0, len(perm), self.max_chunk_size):
            indices = perm[i:i + self.max_chunk_size]
            valid_regions = [regions[idx] for idx in indices]
            valid_widths = [r.shape[1] for r in valid_regions]

            N = len(indices)
            max_width = max(valid_widths)
            # Align to multiple of 4
            max_width = (max_width + 3) // 4 * 4

            region_array = np.zeros((N, self.text_height, max_width, 3), dtype=np.uint8)
            for j, r in enumerate(valid_regions):
                W = r.shape[1]
                region_array[j, :, :W, :] = r

            # Convert BGR to RGB: model was trained on RGB images
            region_array = region_array[:, :, :, ::-1].copy()

            img_tensor = (torch.from_numpy(region_array).float() - 127.5) / 127.5
            img_tensor = einops.rearrange(img_tensor, "N H W C -> N C H W")
            img_tensor = img_tensor.to(self.device)

            with torch.no_grad():
                ret = self.ocr_model.infer_beam_batch_tensor(
                    img_tensor, valid_widths, beams_k=5, max_seq_length=255
                )

            for j, (pred_chars_index, prob, fg_pred, bg_pred, fg_ind_pred, bg_ind_pred) in enumerate(ret):
                if prob < self.ocr_threshold:
                    results[indices[j]] = ("", prob, None, None)
                    continue
                seq = []
                # Color accumulators
                fr_sum, fg_sum, fb_sum = 0, 0, 0
                br_sum, bg_sum_, bb_sum = 0, 0, 0
                fr_cnt, br_cnt = 0, 0
                has_fg = (fg_ind_pred[:, 1] > fg_ind_pred[:, 0])
                has_bg = (bg_ind_pred[:, 1] > bg_ind_pred[:, 0])
                for chid, c_fg, c_bg, h_fg, h_bg in zip(
                    pred_chars_index, fg_pred, bg_pred, has_fg, has_bg
                ):
                    ch = self.dictionary[chid]
                    if ch == "<S>":
                        continue
                    if ch == "</S>":
                        break
                    if ch == "<SP>":
                        ch = " "
                    seq.append(ch)
                    if h_fg.item():
                        fr_sum += int(np.clip(c_fg[0].item() * 255, 0, 255))
                        fg_sum += int(np.clip(c_fg[1].item() * 255, 0, 255))
                        fb_sum += int(np.clip(c_fg[2].item() * 255, 0, 255))
                        fr_cnt += 1
                    if h_bg.item():
                        br_sum += int(np.clip(c_bg[0].item() * 255, 0, 255))
                        bg_sum_ += int(np.clip(c_bg[1].item() * 255, 0, 255))
                        bb_sum += int(np.clip(c_bg[2].item() * 255, 0, 255))
                        br_cnt += 1
                    elif h_fg.item():
                        br_sum += int(np.clip(c_fg[0].item() * 255, 0, 255))
                        bg_sum_ += int(np.clip(c_fg[1].item() * 255, 0, 255))
                        bb_sum += int(np.clip(c_fg[2].item() * 255, 0, 255))
                        br_cnt += 1
                txt = "".join(seq)

                # Model input is RGB (BGR→RGB converted at input), model outputs RGB
                fg_color = (
                    fr_sum // fr_cnt,
                    fg_sum // fr_cnt,
                    fb_sum // fr_cnt,
                ) if fr_cnt > 0 else None

                # Background color: high contrast — pure fg luminance decision
                # 浅色字→纯黑底(0,0,0), 深色字→纯白底(255,255,255)
                if fg_color:
                    fg_lum = 0.299 * fg_color[0] + 0.587 * fg_color[1] + 0.114 * fg_color[2]
                    bg_color = (0, 0, 0) if fg_lum > 190 else (255, 255, 255)
                else:
                    bg_color = None
                results[indices[j]] = (txt, prob, fg_color, bg_color)

        return results

    def _create_shape(self, box, score, text, direction, fg_color=None, bg_color=None):
        """Create a Shape object from a detection box and OCR text.
        Matches PPOCRv6 behavior: axis-aligned rectangle for 0/90/180/270°,
        rotation shape only for truly tilted boxes."""
        sorted_pts, _ = sort_quadrilateral_points(box)

        # Description: just the text, colors go to attributes
        desc = text or ""

        # Build attributes with color info
        attributes = {}
        if fg_color:
            attributes["fg"] = list(fg_color)
        if bg_color:
            attributes["bg"] = list(bg_color)

        # Determine if box is truly rotated (tilted, not 0/90/180/270)
        pts_list = box.tolist() if hasattr(box, "tolist") else list(box)
        is_rotated = self._is_rotated_box(pts_list) if len(pts_list) >= 4 else False

        # Label: OCRZX only for truly rotated boxes, OCR for everything else
        label = "OCRZX" if is_rotated else "OCR"

        pt1, pt2, pt3, pt4 = [list(p) for p in sorted_pts[:4]]

        if is_rotated:
            # Rotated: keep original points, use rotation shape with direction
            dx = pt2[0] - pt1[0]
            dy = pt2[1] - pt1[1]
            dir_angle = math.atan2(dy, dx)
            if dir_angle < 0:
                dir_angle += 2 * math.pi

            shape = Shape(
                label=label,
                score=score,
                shape_type="rotation",
                direction=dir_angle,
                description=desc,
                attributes=attributes,
            )
        else:
            # Not rotated: snap to axis-aligned rectangle (like PPOCRv6)
            pt2 = [pt3[0], pt1[1]]
            pt4 = [pt1[0], pt3[1]]
            shape = Shape(
                label=label,
                score=score,
                shape_type="rectangle",
                direction=0.0,
                description=desc,
                attributes=attributes,
            )

        for pt in [pt1, pt2, pt3, pt4]:
            shape.add_point(QtCore.QPointF(float(pt[0]), float(pt[1])))

        return shape

    def predict_shapes(self, image, filename=None):
        """Full pipeline: OCR (text + color) on existing detection boxes.
        Detection is handled by YOLO — this model only does OCR + color extraction."""
        if image is None:
            return AutoLabelingResult([], replace=self.replace)

        t0 = time.time()
        image = self._load_image(image, filename)
        t_load = time.time()

        # Detection
        boxes, scores = self._run_detection(image)
        t_det = time.time()
        if len(boxes) == 0:
            fname = os.path.basename(filename) if filename else "image"
            print(f"\n[全图检测+OCR] {fname} → 读图={t_load-t0:.3f}s  检测={t_det-t_load:.3f}s  共0个框")
            return AutoLabelingResult([], replace=self.replace)

        # OCR
        ocr_results = self._run_ocr(image, boxes)
        t_ocr = time.time()

        # Create shapes with rotation filtering
        shapes = []
        for i, (box, score) in enumerate(zip(boxes, scores)):
            text, prob, fg_color, bg_color = (
                ocr_results[i] if i < len(ocr_results) and ocr_results[i]
                else ("", 0.0, None, None)
            )
            pts_list = box.tolist() if hasattr(box, "tolist") else list(box)
            if len(pts_list) >= 4:
                if not self.use_rotation and self._is_rotated_box(pts_list):
                    continue
                if self.use_rotation and self.filter_non_rotated and not self._is_rotated_box(pts_list):
                    continue
            shape = self._create_shape(box, score, text, None, fg_color, bg_color)
            shapes.append(shape)

        fname = os.path.basename(filename) if filename else "image"
        print(f"\n[全图检测+OCR] {fname} → 读图={t_load-t0:.3f}s  检测={t_det-t_load:.3f}s  OCR={t_ocr-t_det:.3f}s  总={t_ocr-t0:.3f}s  共{len(shapes)}个框")
        for i, shape in enumerate(shapes):
            pts = [[p.x(), p.y()] for p in shape.points]
            attrs = shape.attributes or {}
            print(f"[{i+1:02d}] [{pts}, ('{shape.description}', {shape.score}), {attrs}]")

        return AutoLabelingResult(shapes, replace=self.replace)

    def predict_shapes_detect_only(self, image, image_path=None):
        """Detection only: detect text regions without OCR."""
        if image is None:
            return AutoLabelingResult([], replace=self.replace)

        t0 = time.time()
        image = self._load_image(image, image_path)
        t_load = time.time()

        boxes, scores = self._run_detection(image)
        t_det = time.time()
        if len(boxes) == 0:
            fname = os.path.basename(image_path) if image_path else "image"
            print(f"\n[仅检测] {fname} → 读图={t_load-t0:.3f}s  检测={t_det-t_load:.3f}s  共0个框")
            return AutoLabelingResult([], replace=self.replace)

        shapes = []
        for box, score in zip(boxes, scores):
            # Rotation filtering (same as PPOCRv6)
            pts_list = box.tolist() if hasattr(box, "tolist") else list(box)
            if len(pts_list) >= 4:
                if not self.use_rotation and self._is_rotated_box(pts_list):
                    continue
                if self.use_rotation and self.filter_non_rotated and not self._is_rotated_box(pts_list):
                    continue
            shape = self._create_shape(box, score, "", None)
            shapes.append(shape)

        fname = os.path.basename(image_path) if image_path else "image"
        print(f"\n[仅检测] {fname} → 读图={t_load-t0:.3f}s  检测={t_det-t_load:.3f}s  总={t_det-t0:.3f}s  共{len(shapes)}个框")

        return AutoLabelingResult(shapes, replace=self.replace)

    def predict_shapes_color_only(self, image, image_path=None):
        """Detection + color extraction only — no OCR text recognition (much faster)."""
        if image is None:
            return AutoLabelingResult([], replace=self.replace)

        t0 = time.time()
        image = self._load_image(image, image_path)
        t_load = time.time()

        # Detection
        boxes, scores = self._run_detection(image)
        t_det = time.time()
        if len(boxes) == 0:
            fname = os.path.basename(image_path) if image_path else "image"
            print(f"\n[仅颜色] {fname} → 读图={t_load-t0:.3f}s  检测={t_det-t_load:.3f}s  共0个框")
            return AutoLabelingResult([], replace=self.replace)

        # Color-only (fast: 1 decoder step, no beam search)
        color_results = self._run_color_only(image, boxes)
        t_color = time.time()

        shapes = []
        for i, (box, score) in enumerate(zip(boxes, scores)):
            fg_color, bg_color = (
                color_results[i] if i < len(color_results) and color_results[i]
                else (None, None)
            )
            shape = self._create_shape(box, score, "", None, fg_color, bg_color)
            shapes.append(shape)

        fname = os.path.basename(image_path) if image_path else "image"
        print(f"\n[仅颜色] {fname} → 读图={t_load-t0:.3f}s  检测={t_det-t_load:.3f}s  颜色={t_color-t_det:.3f}s  总={t_color-t0:.3f}s  共{len(shapes)}个框")
        for i, shape in enumerate(shapes):
            pts = [[p.x(), p.y()] for p in shape.points]
            attrs = shape.attributes or {}
            print(f"[{i+1:02d}] [{pts}, ('', 0.0), {attrs}]")

        return AutoLabelingResult(shapes, replace=self.replace)

    def predict_shapes_color_only_from_boxes(self, image, boxes, image_path=None):
        """Fast color extraction on existing boxes — no detection, no OCR."""
        if image is None or len(boxes) == 0:
            return AutoLabelingResult([], replace=False)

        t0 = time.time()
        image = self._load_image(image, image_path)
        t_load = time.time()

        np_boxes = []
        for box in boxes:
            if isinstance(box, (list, np.ndarray)):
                pts = np.array(box, dtype=np.float32)
                if pts.shape == (4, 2):
                    np_boxes.append(pts)
                elif pts.shape == (4, 1, 2):
                    np_boxes.append(pts.reshape(-1, 2))

        if len(np_boxes) == 0:
            return AutoLabelingResult([], replace=False)

        color_results = self._run_color_only(image, np_boxes)
        t_color = time.time()

        shapes = []
        for i, (box, cr) in enumerate(zip(np_boxes, color_results)):
            fg_color, bg_color = cr if cr else (None, None)
            shape = self._create_shape(box, 0.0, "", None, fg_color, bg_color)
            shapes.append(shape)

        fname = os.path.basename(image_path) if image_path else "image"
        print(f"\n[仅颜色-已有框] {fname} → 读图={t_load-t0:.3f}s  颜色={t_color-t_load:.3f}s  总={t_color-t0:.3f}s  共{len(shapes)}个框")
        for i, shape in enumerate(shapes):
            attrs = shape.attributes or {}
            print(f"[{i+1:02d}] [('', 0.0), {attrs}]")

        return AutoLabelingResult(shapes, replace=False)

    def predict_shapes_from_boxes(self, image, boxes, image_path=None):
        """OCR recognition from user-provided boxes."""
        if image is None or len(boxes) == 0:
            return AutoLabelingResult([], replace=False), {}

        t0 = time.time()
        image = self._load_image(image, image_path)
        t_load = time.time()

        # Convert boxes to numpy arrays
        np_boxes = []
        for box in boxes:
            if isinstance(box, (list, np.ndarray)):
                pts = np.array(box, dtype=np.float32)
                if pts.shape == (4, 2):
                    np_boxes.append(pts)
                elif pts.shape == (4, 1, 2):
                    np_boxes.append(pts.reshape(-1, 2))

        if len(np_boxes) == 0:
            return AutoLabelingResult([], replace=False), {}

        # Run OCR
        ocr_results = self._run_ocr(image, np_boxes)
        t_rec = time.time()

        # Create shapes (no rotation filtering - user explicitly selected these boxes)
        shapes = []
        for i, (box, ocr_res) in enumerate(zip(np_boxes, ocr_results)):
            text, prob, fg_color, bg_color = (
                ocr_res if ocr_res else ("", 0.0, None, None)
            )
            shape = self._create_shape(box, prob, text, None, fg_color, bg_color)
            shapes.append(shape)

        timing = {
            "读图": t_load - t0,
            "裁剪+识别": t_rec - t_load,
            "总": t_rec - t0,
        }
        return AutoLabelingResult(shapes, replace=False), timing

    def set_auto_labeling_preserve_existing_annotations_state(self, state):
        self.replace = not state

    def set_auto_labeling_rotation_state(self, state):
        self.use_rotation = state

    def set_auto_labeling_filter_non_rotated(self, state):
        self.filter_non_rotated = state

    def _is_rotated_box(self, points):
        """Determine if a box is rotated (not axis-aligned).
        Ported from PPOCRv6 - checks edge angle against 0/90 degrees.
        """
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

    def unload(self):
        del self.det_model
        del self.ocr_model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
