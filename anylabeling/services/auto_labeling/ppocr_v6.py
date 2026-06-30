import os
import sys
import time

import cv2
import numpy as np
import onnxruntime as ort

from PyQt5 import QtCore
from PyQt5.QtCore import QCoreApplication

from .ppocr_v4 import Args, PPOCRv4
from .types import AutoLabelingResult
from .utils.ppocr_utils.text_system import TextSystem
from .utils.ppocr_utils.text_system import get_rotate_crop_image
from anylabeling.views.labeling.shape import Shape
from anylabeling.views.labeling.utils.opencv import qt_img_to_rgb_cv_img
from anylabeling.views.labeling.logger import logger


class PPOCRv6(PPOCRv4):
    """PaddlePaddle OCR-v6"""

    class Meta:
        required_config_names = [
            "type",
            "name",
            "display_name",
            "det_model_path",
            "rec_model_path",
            "rec_char_dict_path",
        ]
        widgets = ["button_run", "button_recog_selected", "button_recog_all", "button_filter_classes", "toggle_use_existing_boxes", "button_detect_only", "toggle_preserve_existing_annotations", "toggle_rotation", "toggle_filter_non_rotated", "toggle_batch_detect_only"]
        output_modes = PPOCRv4.Meta.output_modes
        default_output_mode = PPOCRv4.Meta.default_output_mode

    def __init__(self, model_config, on_message) -> None:
        super(PPOCRv4, self).__init__(model_config, on_message)

        self.replace = True
        self.use_rotation = False
        self.filter_non_rotated = False

        self.det_net = self.load_model("det_model_path")
        self.rec_net = self.load_model("rec_model_path")
        self.drop_score = self.config.get("drop_score", 0.5)
        self.use_angle_cls = False
        self.current_dir = os.path.dirname(__file__)
        self.rec_char_dict_path = self.config["rec_char_dict_path"]
        if not os.path.isabs(self.rec_char_dict_path):
            config_dir = os.path.dirname(self.config["config_file"])
            self.rec_char_dict_path = os.path.abspath(
                os.path.join(config_dir, self.rec_char_dict_path)
            )
        if not os.path.isfile(self.rec_char_dict_path):
            raise FileNotFoundError(
                QCoreApplication.translate(
                    "Model",
                    "Model path not found: {model_path}",
                ).format(model_path=self.rec_char_dict_path)
            )

        # 初始化 TextSystem 并缓存，避免每次 predict_shapes 重复创建
        self.text_system = self._init_text_system()

        # 预热 ONNX：用一张小图跑一次识别，初始化 CUDA 内核
        dummy = np.zeros((48, 320, 3), dtype=np.uint8)
        self.text_system.text_recognizer([dummy])

        # 关键优化：ONNX 只计算最终输出，不计算中间特征图（性能差距 10-100 倍）
        if hasattr(self.text_system, 'text_recognizer'):
            rec = self.text_system.text_recognizer
            rec.output_tensors = [n.name for n in rec.predictor.get_outputs()]
        if hasattr(self.text_system, 'text_detector'):
            det = self.text_system.text_detector
            det.output_tensors = [n.name for n in det.predictor.get_outputs()]

    def load_model(self, model_name):
        """重写 load_model，使用优化后的 ONNX 会话选项"""
        model_abs_path = self.get_model_abs_path(self.config, model_name)
        model_task = os.path.splitext(
            os.path.basename(self.config[model_name])
        )[0]
        if not model_abs_path or not os.path.isfile(model_abs_path):
            raise FileNotFoundError(
                QCoreApplication.translate(
                    "Model",
                    f"Could not download or initialize {model_task} model.",
                )
            )

        # 开启全部图优化 + 内存模式（快速项目同款设置）
        sess_opts = ort.SessionOptions()
        sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_opts.enable_mem_pattern = True
        if "OMP_NUM_THREADS" in os.environ:
            sess_opts.inter_op_num_threads = int(
                os.environ["OMP_NUM_THREADS"]
            )

        from anylabeling.app_info import __preferred_device__
        providers = ["CPUExecutionProvider"]
        if __preferred_device__ == "GPU":
            providers = [
                (
                    "CUDAExecutionProvider",
                    {
                        "cudnn_conv_algo_search": "HEURISTIC",
                        "device_id": 0,
                    },
                )
            ]

        net = ort.InferenceSession(
            model_abs_path,
            providers=providers,
            sess_options=sess_opts,
        )
        return net

    def parse_args(self):
        args = Args(
            use_onnx=True,
            # params for prediction engine
            use_gpu=True,
            use_xpu=False,
            use_npu=False,
            ir_optim=True,
            use_tensorrt=False,
            min_subgraph_size=15,
            precision="fp32",
            gpu_mem=500,
            gpu_id=0,
            # params for text detector
            page_num=0,
            det_algorithm="DB",
            det_model=self.det_net,
            det_limit_side_len=self.config.get("det_limit_side_len", 1280),
            det_limit_type=self.config.get("det_limit_type", "max"),
            det_box_type="quad",
            # DB params
            det_db_thresh=self.config.get("det_db_thresh", 0.1),
            det_db_box_thresh=self.config.get("det_db_box_thresh", 0.05),
            det_db_unclip_ratio=self.config.get("det_db_unclip_ratio", 2.0),
            max_batch_size=10,
            use_dilation=False,
            det_db_score_mode="fast",
            # EAST params
            det_east_score_thresh=0.8,
            det_east_cover_thresh=0.1,
            det_east_nms_thresh=0.2,
            # SAST params
            det_sast_score_thresh=0.5,
            det_sast_nms_thresh=0.2,
            # PSE params
            det_pse_thresh=0,
            det_pse_box_thresh=0.85,
            det_pse_min_area=16,
            det_pse_scale=1,
            # FCE params
            scales=[8, 16, 32],
            alpha=1.0,
            beta=1.0,
            fourier_degree=5,
            # params for text recognizer
            rec_algorithm="SVTR_LCNet",
            rec_model=self.rec_net,
            rec_image_inverse=True,
            rec_image_shape=self.config.get("rec_image_shape", "3, 48, 320"),
            rec_batch_num=6,
            max_text_length=self.config.get("max_text_length", 25),
            rec_char_dict_path=self.rec_char_dict_path,
            use_space_char=True,
            drop_score=self.drop_score,
            # params for e2e
            e2e_algorithm="PGNet",
            e2e_model_dir="",
            e2e_limit_side_len=768,
            e2e_limit_type="max",
            # PGNet params
            e2e_pgnet_score_thresh=0.5,
            e2e_char_dict_path=os.path.join(
                self.current_dir, "configs/ppocr/ppocr_ic15_dict.txt"
            ),
            e2e_pgnet_valid_set="totaltext",
            e2e_pgnet_mode="fast",
            # params for text classifier
            use_angle_cls=False,
            cls_model=None,
            cls_image_shape="3, 48, 192",
            label_list=["0", "180"],
            cls_batch_num=6,
            cls_thresh=0.9,
            enable_mkldnn=False,
            cpu_threads=10,
            use_pdserving=False,
            warmup=False,
            # SR params
            sr_model_dir="",
            sr_image_shape="3, 32, 128",
            sr_batch_num=1,
        )
        return args

    def _init_text_system(self):
        """创建并返回 TextSystem 实例（模型加载时调用一次）"""
        args = self.parse_args()
        return TextSystem(args)

    def predict_shapes(self, image, image_path=None):
        """
        Predict shapes from image
        """

        if image is None:
            return []

        # 优先使用 OpenCV 直接读文件（BGR），避免 QImage→RGB→BGR 重复转换
        t0 = time.time()
        try:
            if image_path and os.path.exists(image_path):
                image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            else:
                image = qt_img_to_rgb_cv_img(image, image_path)
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        except Exception as e:  # noqa
            logger.warning("Could not inference model")
            logger.warning(e)
            return []
        if image is None:
            return []
        t1 = time.time()

        dt_boxes, rec_res, scores = self.text_system(image)
        t2 = time.time()

        print(f"[全图检测+OCR] {self.config.get('name', 'ppocr_v6')} → [框识别耗时] 读图={t1-t0:.3f}s  推理={t2-t1:.3f}s  总={t2-t0:.3f}s")
        sys.stdout.flush()
        print(os.path.basename(image_path) if image_path else "image")
        for i in range(len(dt_boxes)):
            box = np.array(dt_boxes[i]).astype(np.float32).tolist()
            text = rec_res[i][0]
            score = float(scores[i])
            print(f"[{i+1:02d}] [{box}, ('{text}', {score})]")
        print()

        results = [
            {
                "description": rec_res[i][0],
                "points": np.array(dt_boxes[i]).astype(np.int32).tolist(),
                "score": float(scores[i]),
            }
            for i in range(len(dt_boxes))
        ]

        shapes = []
        for i, res in enumerate(results):
            score = res["score"]
            points = res["points"]
            description = res["description"]
            # 旋转关：自动过滤旋转框，只留水平框
            if not self.use_rotation and self._is_rotated_box(points):
                continue
            # 旋转开+过滤开：只留旋转框，过滤水平框
            if self.use_rotation and self.filter_non_rotated and not self._is_rotated_box(points):
                continue
            is_rotated = self.use_rotation and self._is_rotated_box(points)
            direction = 0.0
            if is_rotated:
                import math
                dx = points[1][0] - points[0][0]
                dy = points[1][1] - points[0][1]
                direction = math.atan2(dy, dx)  # 弧度
                if direction < 0:
                    direction += 2 * math.pi
            shape = Shape(
                label="OCRZX" if is_rotated else "OCR",
                score=score,
                shape_type="rotation" if is_rotated else "rectangle",
                direction=direction,
                description=description,
            )
            pt1, pt2, pt3, pt4 = points
            if not is_rotated:
                pt2 = [pt3[0], pt1[1]]
                pt4 = [pt1[0], pt3[1]]
            shape.add_point(QtCore.QPointF(*pt1))
            shape.add_point(QtCore.QPointF(*pt2))
            shape.add_point(QtCore.QPointF(*pt3))
            shape.add_point(QtCore.QPointF(*pt4))
            shapes.append(shape)

        result = AutoLabelingResult(shapes, replace=self.replace)
        return result

    def set_auto_labeling_preserve_existing_annotations_state(self, state):
        self.replace = not state

    def set_auto_labeling_rotation_state(self, state):
        self.use_rotation = state

    def set_auto_labeling_filter_non_rotated(self, state):
        self.filter_non_rotated = state

    def _is_rotated_box(self, points):
        """判断框是否为旋转框（非水平/垂直）
        取顶边(pt1→pt2)角度，对90°取模，超过阈值视为旋转
        """
        import math
        pt1, pt2, pt3, pt4 = points
        dx = pt2[0] - pt1[0]
        dy = pt2[1] - pt1[1]
        if abs(dx) < 1 and abs(dy) < 1:
            return False  # 无效边
        angle = abs(math.degrees(math.atan2(dy, dx)))
        # 对90°取模，靠近0°或90°的视为非旋转
        angle_mod = angle % 90
        if angle_mod > 45:
            angle_mod = 90 - angle_mod
        return angle_mod > 0

    def predict_shapes_detect_only(self, image, image_path=None):
        """仅检测文字区域，不 OCR 识别"""
        if image is None:
            return AutoLabelingResult([], replace=True)

        t0 = time.time()
        try:
            if image_path and os.path.exists(image_path):
                image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            else:
                image = qt_img_to_rgb_cv_img(image, image_path)
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        except Exception:
            return AutoLabelingResult([], replace=True)
        if image is None:
            return AutoLabelingResult([], replace=True)
        t1 = time.time()

        dt_boxes = self.text_system.text_detector(image)
        t2 = time.time()
        if dt_boxes is None:
            dt_boxes = []

        fname = os.path.basename(image_path) if image_path else "image"
        print(f"\n[仅检测] {fname} → 读图={t1-t0:.3f}s  检测={t2-t1:.3f}s  总={t2-t0:.3f}s  共{len(dt_boxes)}个框")
        sys.stdout.flush()

        shapes = []
        for i, box in enumerate(dt_boxes):
            pts = np.array(box).astype(np.int32).tolist()
            # 旋转关：自动过滤旋转框，只留水平框
            if not self.use_rotation and self._is_rotated_box(pts):
                continue
            # 旋转开+过滤开：只留旋转框，过滤水平框
            if self.use_rotation and self.filter_non_rotated and not self._is_rotated_box(pts):
                continue
            is_rotated = self.use_rotation and self._is_rotated_box(pts)
            direction = 0.0
            if is_rotated:
                import math
                dx = pts[1][0] - pts[0][0]
                dy = pts[1][1] - pts[0][1]
                direction = math.atan2(dy, dx)  # 弧度
                if direction < 0:
                    direction += 2 * math.pi
            shape = Shape(
                label="OCRZX" if is_rotated else "OCR",
                score=0.0,
                shape_type="rotation" if is_rotated else "rectangle",
                direction=direction,
                description="",
            )
            pt1, pt2, pt3, pt4 = pts
            if not is_rotated:
                pt2 = [pt3[0], pt1[1]]
                pt4 = [pt1[0], pt3[1]]
            shape.add_point(QtCore.QPointF(*pt1))
            shape.add_point(QtCore.QPointF(*pt2))
            shape.add_point(QtCore.QPointF(*pt3))
            shape.add_point(QtCore.QPointF(*pt4))
            shapes.append(shape)

        return AutoLabelingResult(shapes, replace=self.replace)

    def predict_shapes_from_boxes(self, image, boxes, image_path=None):
        """
        对给定框区域进行 OCR 识别。
        全图 DBNet 拆分框内文本行后再逐行识别，保证排序正确。
        boxes: 列表，每个元素为 4 个点的坐标 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        """
        if image is None or not boxes:
            return AutoLabelingResult([], replace=False), {}

        t0 = time.time()
        try:
            if image_path and os.path.exists(image_path):
                image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            else:
                image = qt_img_to_rgb_cv_img(image, image_path)
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        except Exception as e:
            logger.warning("Could not load image for box recognition")
            logger.warning(e)
            return AutoLabelingResult([], replace=False), {}
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
            return AutoLabelingResult([], replace=False), {}

        has_detector = hasattr(self.text_system, 'text_detector') and self.text_system.text_detector is not None

        # 全图 DBNet 检测文本行
        all_det_boxes = []
        if has_detector:
            try:
                all_det_boxes = self.text_system.text_detector(image)
                if all_det_boxes is None:
                    all_det_boxes = []
            except Exception:
                all_det_boxes = []

        # 按用户框收集内部 DBNet 行
        final_boxes = []
        box_mapping = []
        for i, user_box in enumerate(np_boxes):
            ux1 = user_box[:, 0].min(); uy1 = user_box[:, 1].min()
            ux2 = user_box[:, 0].max(); uy2 = user_box[:, 1].max()
            box_w = ux2 - ux1; box_h = uy2 - uy1
            is_vertical = box_h > box_w

            lines = []
            for db_pts in all_det_boxes:
                if len(db_pts) < 4:
                    continue
                dbx1 = db_pts[:, 0].min(); dby1 = db_pts[:, 1].min()
                dbx2 = db_pts[:, 0].max(); dby2 = db_pts[:, 1].max()
                if dbx1 >= ux1 and dbx2 <= ux2 and dby1 >= uy1 and dby2 <= uy2:
                    lines.append(np.array(db_pts, dtype=np.float32))

            if len(lines) > 1:
                if is_vertical:
                    lines.sort(key=lambda b: (-b[:, 0].min(), b[:, 1].min()))
                else:
                    lines.sort(key=lambda b: b[:, 1].min())
                final_boxes.extend(lines)
                box_mapping.append((i, True, len(lines)))
            else:
                final_boxes.append(user_box)
                box_mapping.append((i, False, 1))

        # 裁剪每行并识别
        img_crop_list = []
        for pts in final_boxes:
            try:
                if len(pts) == 4:
                    ordered = np.zeros((4, 2), dtype=np.float32)
                    s = pts.sum(axis=1); d = np.diff(pts, axis=1)
                    ordered[0] = pts[np.argmin(s)]; ordered[2] = pts[np.argmax(s)]
                    ordered[1] = pts[np.argmin(d)]; ordered[3] = pts[np.argmax(d)]
                    pts = ordered
                crop = get_rotate_crop_image(image, pts)
                img_crop_list.append(crop)
            except Exception as e:
                logger.warning(f"Failed to crop box: {e}")
                img_crop_list.append(np.ones((48, 16, 3), dtype=np.uint8) * 255)

        if not img_crop_list:
            return AutoLabelingResult([], replace=False), {}

        rec_res = self.text_system.text_recognizer(img_crop_list)
        t_rec = time.time()

        shapes = []
        result_idx = 0
        for orig_idx, is_multi, sub_count in box_mapping:
            if is_multi and result_idx + sub_count <= len(rec_res):
                line_texts = []
                max_score = 0.0
                for j in range(result_idx, result_idx + sub_count):
                    line_texts.append(rec_res[j][0])
                    max_score = max(max_score, float(rec_res[j][1]))
                text = "\n".join(line_texts)
                score = max_score
            else:
                text = rec_res[result_idx][0]
                score = float(rec_res[result_idx][1])

            pts = boxes[orig_idx]
            is_rotated = self.use_rotation and self._is_rotated_box(pts)
            direction = 0.0
            if is_rotated:
                import math
                dx = pts[1][0] - pts[0][0]
                dy = pts[1][1] - pts[0][1]
                direction = math.atan2(dy, dx)
                if direction < 0:
                    direction += 2 * math.pi
            shape = Shape(
                label="OCRZX" if is_rotated else "OCR",
                score=score,
                shape_type="rotation" if is_rotated else "rectangle",
                direction=direction,
                description=text,
            )
            pt1, pt2, pt3, pt4 = pts
            if not is_rotated:
                pt2 = [pt3[0], pt1[1]]
                pt4 = [pt1[0], pt3[1]]
            shape.add_point(QtCore.QPointF(*pt1))
            shape.add_point(QtCore.QPointF(*pt2))
            shape.add_point(QtCore.QPointF(*pt3))
            shape.add_point(QtCore.QPointF(*pt4))
            shapes.append(shape)
            result_idx += sub_count

        timing = {
            "读图": t_load - t0,
            "裁剪+识别": t_rec - t_load,
            "总": t_rec - t0,
        }
        return AutoLabelingResult(shapes, replace=False), timing

    def unload(self):
        del self.text_system
        del self.det_net
        del self.rec_net
