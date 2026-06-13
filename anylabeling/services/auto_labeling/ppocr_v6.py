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
        widgets = ["button_run", "button_recog_selected", "button_recog_all", "button_filter_classes", "toggle_use_existing_boxes", "button_detect_only"]
        output_modes = PPOCRv4.Meta.output_modes
        default_output_mode = PPOCRv4.Meta.default_output_mode

    def __init__(self, model_config, on_message) -> None:
        super(PPOCRv4, self).__init__(model_config, on_message)

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
                        "cudnn_conv_algo_search": "DEFAULT",
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
        output = []
        for i in range(len(dt_boxes)):
            box = np.array(dt_boxes[i]).astype(np.float32).tolist()
            text = rec_res[i][0]
            score = float(scores[i])
            output.append([box, (text, score)])
        print(output)
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
            shape = Shape(
                label="text",
                score=score,
                shape_type="rectangle",
                group_id=int(i),
                description=description,
            )
            pt1, pt2, pt3, pt4 = points
            pt2 = [pt3[0], pt1[1]]
            pt4 = [pt1[0], pt3[1]]
            shape.add_point(QtCore.QPointF(*pt1))
            shape.add_point(QtCore.QPointF(*pt2))
            shape.add_point(QtCore.QPointF(*pt3))
            shape.add_point(QtCore.QPointF(*pt4))
            shapes.append(shape)

        result = AutoLabelingResult(shapes, replace=True)
        return result

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
            shape = Shape(
                label="balloon",
                score=0.0,
                shape_type="rectangle",
                group_id=int(i),
                description="",
            )
            pt1, pt2, pt3, pt4 = pts
            pt2 = [pt3[0], pt1[1]]
            pt4 = [pt1[0], pt3[1]]
            shape.add_point(QtCore.QPointF(*pt1))
            shape.add_point(QtCore.QPointF(*pt2))
            shape.add_point(QtCore.QPointF(*pt3))
            shape.add_point(QtCore.QPointF(*pt4))
            shapes.append(shape)

        return AutoLabelingResult(shapes, replace=True)

    def predict_shapes_from_boxes(self, image, boxes, image_path=None):
        """
        只对给定框区域进行 OCR 识别，跳过全图检测。
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

        # 对每个框裁剪图片区域
        img_crop_list = []
        valid_indices = []
        for i, box in enumerate(boxes):
            try:
                pts = np.array(box, dtype=np.float32)
                crop = get_rotate_crop_image(image, pts)
                img_crop_list.append(crop)
                valid_indices.append(i)
            except Exception as e:
                logger.warning(f"Failed to crop box {i}: {e}")

        if not img_crop_list:
            return AutoLabelingResult([], replace=False), {}

        # 只跑识别器，跳过检测器
        rec_res = self.text_system.text_recognizer(img_crop_list)
        t_rec = time.time()

        shapes = []
        for i, idx in enumerate(valid_indices):
            text = rec_res[i][0]
            score = float(rec_res[i][1])
            shape = Shape(
                label="balloon",
                score=score,
                shape_type="rectangle",
                group_id=int(idx),
                description=text,
            )
            pt1, pt2, pt3, pt4 = boxes[idx]
            pt2 = [pt3[0], pt1[1]]
            pt4 = [pt1[0], pt3[1]]
            shape.add_point(QtCore.QPointF(*pt1))
            shape.add_point(QtCore.QPointF(*pt2))
            shape.add_point(QtCore.QPointF(*pt3))
            shape.add_point(QtCore.QPointF(*pt4))
            shapes.append(shape)

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
