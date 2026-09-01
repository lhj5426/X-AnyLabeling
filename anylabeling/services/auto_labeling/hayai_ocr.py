import os
import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image
from transformers import PreTrainedTokenizerFast
from transformers.models.siglip2 import Siglip2ImageProcessorFast
from PyQt5.QtCore import QPointF

from .model import Model
from .types import AutoLabelingResult
from anylabeling.views.labeling.shape import Shape


class HayaiOCR(Model):
    """Hayai OCR v2.1 ONNX recognizer for existing/selected regions."""

    class Meta:
        required_config_names = ["type", "name", "display_name", "encoder_model_path", "prefill_model_path", "decode_model_path"]
        # Hayai is crop-level OCR only: no detector and no box-splitting or
        # batch recognition of existing annotations.
        widgets = ["button_run", "button_recog_selected", "button_filter_classes", "input_conf", "edit_conf"]
        output_modes = {"rectangle": "Rectangle"}
        default_output_mode = "rectangle"

    def __init__(self, model_config, on_message=None):
        super().__init__(model_config, on_message)
        self.root = Path(__file__).resolve().parents[3]
        def path(key):
            p = Path(self.config[key]); return p if p.is_absolute() else self.root / p
        self.encoder = ort.InferenceSession(str(path("encoder_model_path")), providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        self.prefill = ort.InferenceSession(str(path("prefill_model_path")), providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        self.decode = ort.InferenceSession(str(path("decode_model_path")), providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        self.processor = Siglip2ImageProcessorFast.from_pretrained(str(path("preprocessor_config_path").parent))
        self.tokenizer = PreTrainedTokenizerFast.from_pretrained(str(path("tokenizer_path").parent))
        self.max_new_tokens = int(self.config.get("max_new_tokens", 128))
        self.ocr_threshold = float(self.config.get("ocr_threshold", 0.0))
        self.replace = False
        # AnyLabeling filter dialog writes a list of labels here.  Hayai is a
        # recognizer, so filtering is applied to existing shapes before OCR.
        self.filter_classes = None
        self.batch_mode = False

    def _ocr(self, pil):
        x = self.processor(images=[pil], max_num_patches=256, return_tensors="pt")
        shapes = x.spatial_shapes.numpy()
        visual = self.encoder.run(None, {"pixel_values": x.pixel_values.numpy(), "pixel_attention_mask": x.pixel_attention_mask.numpy(), "spatial_shapes": shapes})[0]
        bos = self.tokenizer.bos_token_id or 1; eos = self.tokenizer.eos_token_id; pad = self.tokenizer.pad_token_id or eos
        out = self.prefill.run(None, {"visual_features": visual, "bos_token": np.array([[bos]], np.int64)}); logits, *cache = out
        def choose(row):
            row = row.astype(np.float64); row -= row.max()
            p = np.exp(row); p /= p.sum()
            idx = int(np.argmax(p)); return idx, float(p[idx])
        first, first_score = choose(logits[0, -1])
        ids = [bos, first]; scores = [first_score]
        for step in range(1, self.max_new_tokens):
            f = np.arange(0, 32, 2, dtype=np.float32); f = np.outer(np.asarray([step], np.float32), 1 / (10000.0 ** (f / 32))); f = np.concatenate([f, f], -1)
            q = {"token": np.array([[ids[-1]]], np.int64), "cos_step": np.cos(f).astype(np.float32)[None], "sin_step": np.sin(f).astype(np.float32)[None]}
            for i in range(12): q[f"past_key_{i}"] = cache[2*i]; q[f"past_value_{i}"] = cache[2*i+1]
            z = self.decode.run(None, q); logits, *cache = z; n, token_score = choose(logits[0, -1])
            if n in (eos, pad): break
            ids.append(n); scores.append(token_score)
        text = self.tokenizer.decode(ids[1:], skip_special_tokens=True)
        return text, (float(np.mean(scores)) if scores else 0.0)

    def predict_shapes(self, image, filename=None):
        if filename and os.path.isfile(filename):
            pil = Image.open(filename).convert("RGB")
        elif isinstance(image, np.ndarray):
            pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        else:
            pil = image
        text, score = self._ocr(pil)
        if not self.batch_mode:
            print(f"[Hayai OCR] text confidence: {score:.4f} (threshold: {self.ocr_threshold:.4f})")
        h, w = np.asarray(image).shape[:2] if isinstance(image, np.ndarray) else (pil.height, pil.width)
        if score < self.ocr_threshold:
            text = ""
        shape = Shape(label="text", score=None, shape_type="rectangle", description=text)
        shape.points = [QPointF(0, 0), QPointF(w, 0), QPointF(w, h), QPointF(0, h)]
        shape.ocr_confidence = score
        return AutoLabelingResult([shape], replace=self.replace)

    @staticmethod
    def _points(box):
        pts = np.asarray(box, dtype=np.float32)
        if pts.ndim == 3:
            pts = pts.reshape(-1, 2)
        if pts.shape[0] < 4:
            x1, y1 = pts.min(axis=0); x2, y2 = pts.max(axis=0)
            pts = np.array([[x1,y1],[x2,y1],[x2,y2],[x1,y2]], np.float32)
        return pts

    def _crop(self, bgr, box):
        pts = self._points(box)
        x1 = max(0, int(np.floor(pts[:, 0].min())))
        y1 = max(0, int(np.floor(pts[:, 1].min())))
        x2 = min(bgr.shape[1], int(np.ceil(pts[:, 0].max())) + 1)
        y2 = min(bgr.shape[0], int(np.ceil(pts[:, 1].max())) + 1)
        if x2 <= x1 or y2 <= y1:
            return Image.new("RGB", (1, 1), "white")
        return Image.fromarray(cv2.cvtColor(bgr[y1:y2, x1:x2], cv2.COLOR_BGR2RGB))

    def predict_shapes_from_boxes(self, image, boxes, image_path=None):
        """Recognize each supplied AnyLabeling shape box (no detection stage)."""
        t0 = time.time()
        if image is None or not boxes:
            return AutoLabelingResult([], replace=False), {}
        if image_path:
            bgr = cv2.imdecode(np.fromfile(image_path, np.uint8), cv2.IMREAD_COLOR)
        elif isinstance(image, np.ndarray):
            bgr = image
        else:
            bgr = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
        t_loaded = time.time()
        shapes = []
        for box in boxes:
            pts = self._points(box)
            text, score = self._ocr(self._crop(bgr, pts))
            if score < self.ocr_threshold:
                text = ""
            shape = Shape(label="text", score=None, shape_type="rectangle", description=text)
            shape.points = [QPointF(float(x), float(y)) for x, y in pts]
            shape.ocr_confidence = score
            shapes.append(shape)
        t_done = time.time()
        return AutoLabelingResult(shapes, replace=False), {
            "读图": t_loaded - t0,
            "裁剪+识别": t_done - t_loaded,
            "总": t_done - t0,
        }

    def set_auto_labeling_filter_classes(self, classes):
        self.filter_classes = classes

    def set_auto_labeling_conf(self, value):
        self.ocr_threshold = float(value)

    def unload(self):
        """Release ONNX sessions when AnyLabeling switches models."""
        self.encoder = None
        self.prefill = None
        self.decode = None
        self.processor = None
        self.tokenizer = None
