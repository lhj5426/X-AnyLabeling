from PyQt5.QtCore import QCoreApplication

from .__base__.yolo import YOLO


class YOLO26(YOLO):
    """YOLO26 - End-to-end object detection with optional NMS mode"""

    class Meta:
        required_config_names = [
            "type",
            "name",
            "display_name",
            "model_path",
        ]
        widgets = [
            "button_run",
            "input_conf",
            "edit_conf",
            "input_iou",
            "edit_iou",
            "toggle_end2end",
            "toggle_preserve_existing_annotations",
            "button_filter_classes",
        ]
        output_modes = {
            "point": QCoreApplication.translate("Model", "Point"),
            "polygon": QCoreApplication.translate("Model", "Polygon"),
            "rectangle": QCoreApplication.translate("Model", "Rectangle"),
        }
        default_output_mode = "rectangle"

