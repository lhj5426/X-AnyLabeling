"""
CTD掩膜生成器 - 在BallonsTranslator环境中运行
此脚本被subprocess调用，在BallonsTranslator conda环境中执行
"""

import sys
import os
import json
import argparse
import cv2
import numpy as np


def generate_mask_from_yolo(image_path, yolo_labels, model_path, output_path, params):
    """
    使用CTD模型从YOLO标签生成掩膜

    Args:
        image_path: 图片路径
        yolo_labels: YOLO标签列表 [(class, x_center, y_center, width, height), ...]
        model_path: CTD模型路径
        output_path: 输出掩膜路径
        params: 参数字典 {'size_scale': 1.0, 'extend_top': 0, 'extend_bottom': 0, ...}
    """
    try:
        print(f"[CTD] 开始生成掩膜...", flush=True)
        print(f"[CTD] 图片路径: {image_path}", flush=True)
        print(f"[CTD] 模型路径: {model_path}", flush=True)
        print(f"[CTD] 输出路径: {output_path}", flush=True)
        print(f"[CTD] YOLO标签数量: {len(yolo_labels)}", flush=True)

        # 添加BallonsTranslator路径
        ballons_path = r"D:\BallonsTranslator\BallonsTranslator"
        if ballons_path not in sys.path:
            sys.path.insert(0, ballons_path)

        # 导入CTD模块
        print("[CTD] 导入CTD模块...", flush=True)
        from modules.textdetector.ctd import CTDModel
        import torch

        # 加载模型
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"[CTD] 加载模型... (设备: {device})", flush=True)
        model = CTDModel(model_path, detect_size=1024, device=device)
        print("[CTD] 模型加载完成", flush=True)

        # 读取图片
        print("[CTD] 读取图片...", flush=True)
        img = cv2.imread(image_path)
        if img is None:
            return {"success": False, "error": f"无法读取图片: {image_path}"}

        # 确保图像为3通道BGR格式
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif len(img.shape) == 3 and img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)

        img_h, img_w = img.shape[:2]
        print(f"[CTD] 图片尺寸: {img_w}x{img_h}", flush=True)

        # 创建掩膜图
        mask = np.zeros((img_h, img_w), dtype=np.uint8)

        # 获取参数
        size_scale = params.get('size_scale', 1.0)
        extend_top = params.get('extend_top', 0)
        extend_bottom = params.get('extend_bottom', 0)
        extend_left = params.get('extend_left', 0)
        extend_right = params.get('extend_right', 0)

        # 处理每个YOLO标签框
        mask_regions = []
        print(f"[CTD] 开始处理 {len(yolo_labels)} 个标签框...", flush=True)

        # 1. 全图文字检测 - 获取高质量文字掩膜
        print("[CTD] 正在进行全图文字检测（提供完整上下文）...", flush=True)
        # 使用传入的检测尺寸或默认
        detect_size = params.get('detect_size', 1024)
        mask_full, mask_refined_full, blk_list = model(img, refine_mode=0, keep_undetected_mask=False)

        if mask_refined_full is None or mask_refined_full.size == 0:
            print("[CTD] ⚠️ 全图未检测到文字区域", flush=True)
            mask = np.zeros((img_h, img_w), dtype=np.uint8)
        else:
            print(f"[CTD] 检测完成，找到 {len(blk_list) if blk_list is not None else 0} 个文字块", flush=True)
            
            # 确保掩膜大小与原图匹配
            if mask_refined_full.shape[:2] != (img_h, img_w):
                mask_refined_full = cv2.resize(mask_refined_full, (img_w, img_h))

            # 2. 创建YOLO框过滤掩膜
            print(f"[CTD] 正在应用 {len(yolo_labels)} 个标注框过滤...", flush=True)
            box_filter = np.zeros((img_h, img_w), dtype=np.uint8)
            for label_data in yolo_labels:
                x_center, y_center, width, height = label_data[1:]
                x1 = int((x_center - width / 2) * img_w)
                y1 = int((y_center - height / 2) * img_h)
                x2 = int((x_center + width / 2) * img_w)
                y2 = int((y_center + height / 2) * img_h)
                
                # 限制范围
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(img_w, x2), min(img_h, y2)
                
                cv2.rectangle(box_filter, (x1, y1), (x2, y2), 255, -1)

            # 3. 过滤全图掩膜
            mask = cv2.bitwise_and(mask_refined_full, box_filter)

        # 对掩膜进行后处理：应用膨胀操作来扩展掩膜区域
        # 1. 根据size_scale计算膨胀量（使用独立工具的算法）
        if size_scale != 1.0:
            if size_scale > 1.0:
                # 膨胀：kernel_size = int((factor - 1.0) * 10) + 1
                kernel_size = int((size_scale - 1.0) * 10) + 1
                print(f"[CTD] 整体大小 {int(size_scale*100)}%，膨胀核大小 {kernel_size}", flush=True)
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                mask = cv2.dilate(mask, kernel, iterations=1)
            else:
                # 腐蚀：kernel_size = int((1.0 - factor) * 10) + 1
                kernel_size = int((1.0 - size_scale) * 10) + 1
                print(f"[CTD] 整体大小 {int(size_scale*100)}%，腐蚀核大小 {kernel_size}", flush=True)
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
                mask = cv2.erode(mask, kernel, iterations=1)

        # 2. 应用方向延伸参数（使用像素移位方法）
        if extend_top > 0 or extend_bottom > 0 or extend_left > 0 or extend_right > 0:
            print(f"[CTD] 应用方向延伸: 上{extend_top} 下{extend_bottom} 左{extend_left} 右{extend_right}", flush=True)
            h, w = mask.shape
            result_mask = mask.copy()

            # 向上单向延伸
            if extend_top > 0:
                for i in range(1, int(extend_top) + 1):
                    shifted = np.zeros_like(mask)
                    if i < h:
                        shifted[:-i, :] = mask[i:, :]
                        result_mask = np.maximum(result_mask, shifted)

            # 向下单向延伸
            if extend_bottom > 0:
                for i in range(1, int(extend_bottom) + 1):
                    shifted = np.zeros_like(mask)
                    if i < h:
                        shifted[i:, :] = mask[:-i, :]
                        result_mask = np.maximum(result_mask, shifted)

            # 向左单向延伸
            if extend_left > 0:
                for i in range(1, int(extend_left) + 1):
                    shifted = np.zeros_like(mask)
                    if i < w:
                        shifted[:, :-i] = mask[:, i:]
                        result_mask = np.maximum(result_mask, shifted)

            # 向右单向延伸
            if extend_right > 0:
                for i in range(1, int(extend_right) + 1):
                    shifted = np.zeros_like(mask)
                    if i < w:
                        shifted[:, i:] = mask[:, :-i]
                        result_mask = np.maximum(result_mask, shifted)

            mask = result_mask
            print(f"[CTD] ✅ 方向延伸完成", flush=True)

        # 根据格式生成不同的掩膜图
        print(f"[CTD] 生成掩膜图...", flush=True)
        mask_format = params.get('format', 'ballons')
        text_color = params.get('text_color', [255, 255, 255])  # RGB
        text_alpha = params.get('text_alpha', 255)  # 0-255

        if mask_format == 'imagetrans':
            print(f"[CTD] 使用ImageTrans格式（透明背景 + RGB{text_color}, Alpha={text_alpha}）", flush=True)
            # ImageTrans格式：透明背景 + 自定义颜色文字区域
            # 创建4通道图像（BGRA）
            mask_rgba = np.zeros((img_h, img_w, 4), dtype=np.uint8)

            # 将掩膜区域填充为指定颜色和透明度
            mask_indices = mask > 127
            mask_rgba[mask_indices] = [text_color[2], text_color[1], text_color[0], text_alpha]  # BGRA

            # 保存为PNG（支持透明度）
            cv2.imwrite(output_path, mask_rgba)
            print(f"[CTD] ImageTrans掩膜已保存: {output_path}", flush=True)
        else:
            print(f"[CTD] 使用BallonsTranslator格式（黑背景 + 白色文字）", flush=True)
            # BallonsTranslator格式：黑背景 + 白色文字区域
            # mask已经是黑背景白字，直接保存
            cv2.imwrite(output_path, mask)
            print(f"[CTD] BallonsTranslator掩膜已保存: {output_path}", flush=True)

        # 提取轮廓（用于多边形显示）
        print(f"[CTD] 提取多边形轮廓...", flush=True)
        contours = []
        mask_binary = (mask > 127).astype(np.uint8)
        contour_list, _ = cv2.findContours(mask_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        print(f"[CTD] 找到 {len(contour_list)} 个轮廓", flush=True)

        for cnt in contour_list:
            # 使用更平滑的epsilon值（0.005）并保留浮点精度
            epsilon = 0.005 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)

            # 转换为点列表，使用float点
            points = [[float(point[0][0]), float(point[0][1])] for point in approx]

            if len(points) >= 3:  # 至少3个点才能构成多边形
                contours.append(points)

        print(f"[CTD] 提取了 {len(contours)} 个有效多边形轮廓", flush=True)
        print(f"[CTD] ✅ 掩膜生成完成！", flush=True)

        return {
            "success": True,
            "mask_path": output_path,
            "contours": contours,
            "regions": [],  # 不再需要regions
            "device": device
        }

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[CTD] ❌ 错误: {str(e)}", flush=True)
        print(error_trace, flush=True)
        return {
            "success": False,
            "error": str(e),
            "traceback": error_trace
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', required=True, help='图片路径')
    parser.add_argument('--labels', required=True, help='YOLO标签JSON字符串')
    parser.add_argument('--model', required=True, help='CTD模型路径')
    parser.add_argument('--output', required=True, help='输出掩膜路径')
    parser.add_argument('--params', default='{}', help='参数JSON字符串')

    args = parser.parse_args()

    # 解析JSON参数
    yolo_labels = json.loads(args.labels)
    params = json.loads(args.params)

    # 生成掩膜
    result = generate_mask_from_yolo(
        args.image,
        yolo_labels,
        args.model,
        args.output,
        params
    )

    # 输出JSON结果
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
