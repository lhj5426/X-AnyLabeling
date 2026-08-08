import numpy as np
import cv2
import torch
from pathlib import Path
from typing import Union, Tuple

from .basemodel import TextDetBase, TextDetBaseDNN
from .yolov5.yolov5_utils import non_max_suppression
from .db_utils import SegDetectorRepresenter


def letterbox(im, new_shape=(640, 640), color=(0, 0, 0), auto=False, scaleFill=False, scaleup=True, stride=128):
    """Resize and pad image while meeting stride-multiple constraints."""
    shape = im.shape[:2]
    if not isinstance(new_shape, tuple):
        new_shape = (new_shape, new_shape)
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    if not scaleup:
        r = min(r, 1.0)
    ratio = r, r
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
    if auto:
        dw, dh = np.mod(dw, stride), np.mod(dh, stride)
    elif scaleFill:
        dw, dh = 0.0, 0.0
        new_unpad = (new_shape[1], new_shape[0])
        ratio = new_shape[1] / shape[1], new_shape[0] / shape[0]
    dh, dw = int(dh), int(dw)
    if shape[::-1] != new_unpad:
        im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    im = cv2.copyMakeBorder(im, 0, dh, 0, dw, cv2.BORDER_CONSTANT, value=color)
    return im, ratio, (dw, dh)


def preprocess_img(img, detect_size=(1024, 1024), device='cpu', bgr2rgb=True, half=False, to_tensor=True):
    if isinstance(detect_size, int):
        detect_size = (detect_size, detect_size)
    if bgr2rgb:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img_in, ratio, (dw, dh) = letterbox(img, new_shape=detect_size, auto=False, stride=64)
    if to_tensor:
        img_in = img_in.transpose((2, 0, 1))[::-1]
        img_in = np.array([np.ascontiguousarray(img_in)]).astype(np.float32) / 255
        img_in = torch.from_numpy(img_in).to(device)
        if half:
            img_in = img_in.half()
    return img_in, ratio, int(dw), int(dh)


def postprocess_mask(img: Union[torch.Tensor, np.ndarray], thresh=None):
    if isinstance(img, torch.Tensor):
        img = img.squeeze_()
        if img.device != 'cpu':
            img = img.detach().cpu()
        img = img.numpy()
    else:
        img = img.squeeze()
    if thresh is not None:
        img = img > thresh
    img = img * 255
    return img.astype(np.uint8)


def postprocess_yolo(det, conf_thresh, nms_thresh, resize_ratio, sort_func=None):
    det = non_max_suppression(det, conf_thresh, nms_thresh)[0]
    if det.device != 'cpu':
        det = det.detach_().cpu().numpy()
    det[..., [0, 2]] = det[..., [0, 2]] * resize_ratio[0]
    det[..., [1, 3]] = det[..., [1, 3]] * resize_ratio[1]
    if sort_func is not None:
        det = sort_func(det)
    bboxes = det[..., 0:4].astype(np.int32)
    confs = np.round(det[..., 4], 3)
    cls = det[..., 5].astype(np.int32)
    return bboxes, cls, confs


class CTDInference:
    """
    Simplified CTD inference engine for X-AnyLabeling.
    Returns: text-block bboxes (YOLOv5 output) + text-line quadrilaterals (DB output).
    """

    def __init__(self, model_path, detect_size=1024, device='cpu', half=False,
                 conf_thresh=0.4, nms_thresh=0.35, db_thresh=0.3, db_box_thresh=0.6):
        self.detect_size = detect_size
        self.device = device
        self.half = half
        self.conf_thresh = conf_thresh
        self.nms_thresh = nms_thresh
        self.db_box_thresh = db_box_thresh

        if Path(model_path).suffix == '.onnx':
            self.net = TextDetBaseDNN(1024, model_path)
            self.backend = 'opencv'
        else:
            self.net = TextDetBase(model_path, device=self.device, act='leaky', half=self.half)
            self.backend = 'torch'

        self.seg_rep = SegDetectorRepresenter(thresh=db_thresh)

    @torch.no_grad()
    def __call__(self, img: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Args:
            img: BGR image (H, W, 3)
        Returns:
            blk_bboxes: (N, 4) [x1, y1, x2, y2] int32 — text block rectangles from YOLOv5 head
            blk_confs:  (N,)   float32 — confidence scores
            lines:      (M, 4, 2) int64 — text line quadrilaterals from DB head
        """
        im_h, im_w = img.shape[:2]
        img_in, ratio, dw, dh = preprocess_img(img, bgr2rgb=False,
                                                detect_size=self.detect_size,
                                                device=self.device, half=self.half,
                                                to_tensor=(self.backend == 'torch'))

        if self.backend == 'torch':
            blks, mask, lines_map = self.net(img_in)
            mask = mask.squeeze()
            resize_ratio = (im_w / (self.detect_size - dw), im_h / (self.detect_size - dh))
            blk_bboxes, blk_cls, blk_confs = postprocess_yolo(blks, self.conf_thresh,
                                                                self.nms_thresh, resize_ratio)
            mask = mask[..., :mask.shape[0] - dh, :mask.shape[1] - dw]
            lines_map = lines_map[..., :lines_map.shape[2] - dh, :lines_map.shape[3] - dw]
        else:
            blobs = cv2.dnn.blobFromImage(img_in if isinstance(img_in, np.ndarray) else img,
                                           scalefactor=1 / 255.0, size=(1024, 1024))
            self.net.model.setInput(blobs)
            blks, mask, lines_map = self.net.model.forward(self.net.uoln)
            if mask.shape[1] == 2:
                mask, lines_map = lines_map, mask
            mask = mask.squeeze()
            resize_ratio = (im_w / (1024 - dw), im_h / (1024 - dh))
            blk_bboxes, blk_cls, blk_confs = postprocess_yolo(blks, self.conf_thresh,
                                                                self.nms_thresh, resize_ratio)
            mask = mask[..., :mask.shape[0] - dh, :mask.shape[1] - dw]
            lines_map = lines_map[..., :lines_map.shape[2] - dh, :lines_map.shape[3] - dw]

        # DB postprocessing: text line quadrilaterals
        lines, scores = self.seg_rep(None, lines_map, height=im_h, width=im_w)
        idx = np.where(scores[0] > self.db_box_thresh)
        lines, scores = lines[0][idx], scores[0][idx]
        if lines.size == 0:
            lines = np.empty((0, 4, 2), dtype=np.int64)
            line_scores = np.empty((0,), dtype=np.float32)
        else:
            lines = lines.astype(np.int64)
            line_scores = np.asarray(scores, dtype=np.float32)

        return blk_bboxes, blk_confs, lines, line_scores
