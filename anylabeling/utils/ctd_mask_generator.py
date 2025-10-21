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

        for idx, label_data in enumerate(yolo_labels):
            # YOLO格式: class x_center y_center width height (归一化坐标)
            x_center, y_center, width, height = label_data[1:]

            # 转换为像素坐标
            x_center_px = int(x_center * img_w)
            y_center_px = int(y_center * img_h)
            width_px = int(width * img_w)
            height_px = int(height * img_h)

            # 应用大小调整
            width_px = int(width_px * size_scale)
            height_px = int(height_px * size_scale)

            # 计算矩形框
            x1 = x_center_px - width_px // 2
            y1 = y_center_px - height_px // 2
            x2 = x_center_px + width_px // 2
            y2 = y_center_px + height_px // 2

            # 应用方向延伸
            x1 -= extend_left
            x2 += extend_right
            y1 -= extend_top
            y2 += extend_bottom

            # 边界检查
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(img_w, x2)
            y2 = min(img_h, y2)

            print(f"[CTD] 处理区域 {idx+1}/{len(yolo_labels)}: [{x1},{y1},{x2},{y2}]", flush=True)

            # 裁剪区域
            crop = img[y1:y2, x1:x2]
            if crop.size == 0:
                print(f"[CTD] 区域 {idx+1} 为空，跳过", flush=True)
                continue

            # 使用CTD检测文字区域 - 正确的调用方式
            print(f"[CTD] 调用CTD模型检测区域 {idx+1}...", flush=True)
            mask_crop, mask_refined_crop, blk_list = model(crop, refine_mode=0, keep_undetected_mask=False)

            print(f"[CTD] 区域 {idx+1} 检测完成，检测到 {len(blk_list) if blk_list is not None else 0} 个文字块", flush=True)

            # 将检测到的掩膜合并到全图掩膜中
            # mask_refined_crop已经是掩膜了，不需要再处理blk_list
            if mask_refined_crop is not None and mask_refined_crop.size > 0:
                # 将crop区域的掩膜复制到全图掩膜的对应位置
                mask[y1:y2, x1:x2] = np.maximum(mask[y1:y2, x1:x2], mask_refined_crop)

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
            # 简化轮廓
            epsilon = 0.01 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)

            # 转换为点列表
            points = []
            for point in approx:
                x, y = point[0]
                points.append([int(x), int(y)])

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
