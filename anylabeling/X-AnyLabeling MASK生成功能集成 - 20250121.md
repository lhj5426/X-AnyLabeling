# X-AnyLabeling MASK生成功能集成 - 20250121

## 概述

本功能将BallonsTranslator的CTD（Comic Text Detector）掩膜生成功能集成到X-AnyLabeling中，实现在标注工具内直接生成文字掩膜，用于漫画/图片翻译工作流。

## 功能入口

**菜单位置**：工具 (Tools) → MASK生成

## 主要特性

### 1. 四种生成方式

#### ① CTD生成多边形
- **输入**：JSON文件中的矩形/旋转框标注
- **处理**：在每个标注框内使用CTD模型检测文字区域
- **输出**：多边形轮廓保存到JSON文件 + 显示在画布上
- **用途**：精确提取文字区域边界，方便后续编辑

#### ② 从标注框生成
- **输入**：JSON文件中的矩形/旋转框标注
- **处理**：直接将矩形框区域填充为掩膜
- **输出**：PNG掩膜图片（保存到 `mask/` 子目录）
- **用途**：快速生成简单矩形掩膜，不依赖CTD模型

#### ③ 使用CTD生成
- **输入**：JSON文件中的矩形/旋转框标注
- **处理**：在每个标注框内使用CTD模型检测文字区域
- **输出**：PNG掩膜图片（保存到 `mask/` 子目录）
- **用途**：高质量文字掩膜生成，适合翻译软件使用

#### ④ 导出PNG
- **输入**：JSON文件中的多边形标注（通常由①生成）
- **处理**：将多边形区域填充为掩膜
- **输出**：PNG掩膜图片
- **用途**：将编辑后的多边形轮廓导出为最终掩膜

### 2. 生成范围

- **当前页面**：只处理当前打开的图片
- **所有页面**：批量处理文件列表中的所有图片
  - 显示实时进度条
  - 详细日志输出每个文件的处理状态
  - 自动跳过无JSON/无标注的文件
  - 统计成功/跳过/失败数量

### 3. 掩膜参数调整

#### 整体大小
- 范围：20% - 500%
- 默认：100%
- 作用：膨胀或腐蚀掩膜区域

#### 方向延伸
- **向上延伸**：0-100像素，向上扩展掩膜区域
- **向下延伸**：0-100像素，向下扩展掩膜区域
- **向左延伸**：0-100像素，向左扩展掩膜区域
- **向右延伸**：0-100像素，向右扩展掩膜区域

#### 掩膜输出格式

##### BallonsTranslator格式（默认）
- 黑色背景（0, 0, 0）
- 白色文字区域（255, 255, 255）
- 不透明PNG图片

##### ImageTrans格式
- 透明背景（Alpha = 0）
- 自定义文字区域颜色（RGB可调）
- 自定义透明度（0-100%）
- 带Alpha通道的PNG图片

### 4. CTD模型配置

#### 默认模型路径
```
D:\BallonsTranslator\BallonsTranslator\data\models\comictextdetector.pt
```

#### 自定义模型
- 点击"浏览"按钮选择其他CTD模型文件
- 点击"重置"恢复默认路径

## 技术特性

### ✅ 已实现功能

1. **中文路径支持**
   - 使用PIL读取图片（支持Unicode路径）
   - 使用cv2.imencode + buffer.tofile保存PNG（支持中文路径）

2. **异步处理**
   - 单页模式使用QThread后台线程
   - 避免UI冻结，可实时查看日志

3. **批量处理优化**
   - 预加载CTD模型（只加载一次）
   - 循环中复用模型实例
   - 大幅提升批量处理速度

4. **用户体验**
   - 所有反馈在日志窗口显示，无弹窗打断
   - 实时进度条显示批量处理进度
   - 详细日志记录每个步骤和错误信息

5. **格式兼容**
   - BallonsTranslator格式：标准黑白掩膜
   - ImageTrans格式：透明背景+自定义颜色

## 使用流程示例

### 流程一：生成精确多边形轮廓

1. 在X-AnyLabeling中用矩形框标注文字区域
2. 打开"MASK生成"工具
3. 选择"当前页面"或"所有页面"
4. 调整参数（可选）
5. 点击"CTD生成多边形"
6. 等待处理完成，多边形自动显示在画布上
7. 可手动编辑多边形轮廓
8. 点击"导出PNG"生成最终掩膜

### 流程二：直接生成PNG掩膜

1. 在X-AnyLabeling中用矩形框标注文字区域
2. 打开"MASK生成"工具
3. 选择"所有页面"（批量处理）
4. 选择输出格式（BallonsTranslator或ImageTrans）
5. 调整掩膜参数（大小、延伸、颜色等）
6. 点击"使用CTD生成"
7. 等待批量处理完成
8. 掩膜PNG文件保存在各图片目录的 `mask/` 子目录中

### 流程三：快速矩形掩膜

1. 在X-AnyLabeling中用矩形框标注
2. 点击"从标注框生成"
3. 不使用CTD，直接将矩形区域填充为掩膜
4. 适合简单场景，速度最快

## 输出文件位置

### JSON文件（多边形数据）
```
原图路径：D:\images\001.jpg
JSON路径：D:\images\001.json
```

### PNG掩膜文件
```
原图路径：D:\images\001.jpg
掩膜路径：D:\images\mask\001.png
```

## 四个按钮功能对照表

| 按钮名称 | 输入源 | 使用CTD | 输出JSON | 输出PNG | 画布显示 | 适用场景 |
|---------|--------|---------|----------|---------|---------|---------|
| **CTD生成多边形** | JSON矩形框 | ✅ | ✅ | ❌ | ✅ | 需要精确编辑轮廓 |
| **从标注框生成** | JSON矩形框 | ❌ | ❌ | ✅ | ❌ | 快速生成矩形掩膜 |
| **使用CTD生成** | JSON矩形框 | ✅ | ❌ | ✅ | ❌ | 直接生成高质量掩膜 |
| **导出PNG** | JSON多边形 | ❌ | ❌ | ✅ | ❌ | 导出编辑后的轮廓 |

## 依赖环境

### 必需组件
- **X-AnyLabeling**：主程序
- **BallonsTranslator**：CTD模型来源
- **同一conda环境**：两个软件需在同一Python环境中运行

### Python依赖
- PyQt5：GUI框架
- OpenCV (cv2)：图像处理
- NumPy：数值计算
- PIL (Pillow)：图像读取
- PyTorch：CTD模型推理

### CTD模型
- 路径：`D:\BallonsTranslator\BallonsTranslator\data\models\comictextdetector.pt`
- 大小：~50MB
- 设备：自动检测CUDA/CPU

## 常见问题

### Q: 批量处理时报错"No module named 'detection'"
**A**: 确保BallonsTranslator已正确安装在 `D:\BallonsTranslator\BallonsTranslator\` 目录，且CTD模型文件存在。

### Q: 中文路径无法处理
**A**: 本功能已支持中文路径，使用PIL读取和cv2.imencode保存。如仍有问题，请检查路径中是否有特殊字符。

### Q: 处理速度慢
**A**:
- 单页模式：正常速度，使用异步处理
- 批量模式：已优化，模型只加载一次
- 建议使用CUDA加速（需要NVIDIA显卡）

### Q: 生成的掩膜不准确
**A**:
- 调整"整体大小"参数
- 调整"方向延伸"参数，扩大掩膜覆盖范围
- 使用"CTD生成多边形"手动编辑轮廓后再导出

### Q: 批量处理时某些文件跳过
**A**: 检查日志，可能原因：
- 未找到JSON文件
- JSON中没有标注
- 没有矩形或旋转框标注（需要先标注）

## 版本历史

### 2025年1月21日版本
- ✅ 集成CTD掩膜生成到X-AnyLabeling
- ✅ 支持4种生成方式
- ✅ 支持批量处理所有页面
- ✅ 支持中文路径
- ✅ 优化批量处理性能（预加载模型）
- ✅ 移除所有弹窗，统一使用日志窗口反馈
- ✅ 修复属性名错误（extend_top_spin等）
- ✅ 修复批量CTD模型导入问题
- ✅ 使用正确的CTDModel导入路径

## 开发信息

**集成时间**：2025年1月21日
**基于软件**：
- X-AnyLabeling（图片标注工具）
- BallonsTranslator（漫画翻译工具）

**主要文件**：
- `anylabeling/views/labeling/widgets/mask_generator_dialog.py`：主对话框（约1970行）
- `anylabeling/views/labeling/label_widget.py`：菜单集成

**关键类/方法**：
- `MaskGeneratorDialog`：主对话框类
- `MaskGeneratorWorker`：CTD处理线程
- `generate_mask_with_ctd_direct_current()`：单页CTD生成PNG
- `generate_mask_with_ctd_direct_all()`：批量CTD生成PNG
- `generate_mask_from_boxes_current()`：单页矩形掩膜
- `generate_mask_from_boxes_all()`：批量矩形掩膜
- `export_mask_current()`：单页导出PNG
- `export_mask_all()`：批量导出PNG

---

**使用建议**：先在少量图片上测试参数效果，确认满意后再批量处理全部文件。
