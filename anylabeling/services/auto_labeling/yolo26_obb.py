from PyQt5.QtCore import QCoreApplication

from .__base__.yolo import YOLO


class YOLO26_OBB(YOLO):
    """YOLO26-OBB - End-to-end oriented bounding box detection with optional NMS mode"""

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
            "rotation": QCoreApplication.translate("Model", "Rotation"),
        }
        default_output_mode = "rotation"

