import torch
import cv2
import numpy as np

# 尝试导入 YOLO 库查看版本
try:
    import ultralytics
    yolo_ver = ultralytics.__version__
except ImportError:
    yolo_ver = "未安装"

print("-" * 30)
print(f"Numpy 版本:   {np.__version__}")
print(f"OpenCV 版本:  {cv2.__version__}")
print(f"PyTorch 版本: {torch.__version__}")
print(f"YOLO 版本:    {yolo_ver}")
print("-" * 30)

# 检查显卡
if torch.cuda.is_available():
    print(f"✅ CUDA 状态:  可用")
    print(f"🚀 显卡型号:    {torch.cuda.get_device_name(0)}")
    print(f"🔢 显卡数量:    {torch.cuda.device_count()}")
else:
    print(f"❌ CUDA 状态:  不可用 (正在使用 CPU)")

print("-" * 30)