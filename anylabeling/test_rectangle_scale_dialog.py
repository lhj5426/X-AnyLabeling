"""
测试矩形缩放工具对话框
"""
import sys
from PyQt5 import QtWidgets
from views.labeling.widgets.rectangle_scale_dialog import RectangleScaleDialog


def main():
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建对话框
    dialog = RectangleScaleDialog()
    
    # 设置一些测试数据
    dialog.update_image_info(2560, 1440)
    dialog.update_shapes_info(5)
    
    # 显示对话框
    dialog.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

