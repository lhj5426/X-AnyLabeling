# X-AnyLabeling 项目说明文档

**版本：** 3.2.2 (mogai1001 定制版)
**文档生成日期：** 2025-10-01
**应用名称：** mogai1001X-AnyLabeling
**GitHub：** https://github.com/CVHub520/X-AnyLabeling

---

## 📋 目录

1. [项目概述](#项目概述)
2. [核心功能](#核心功能)
3. [技术架构](#技术架构)
4. [主要组件说明](#主要组件说明)
5. [支持的AI模型](#支持的ai模型)
6. [技术栈](#技术栈)
7. [文件结构](#文件结构)
8. [使用场景](#使用场景)
9. [安装与运行](#安装与运行)
10. [配置说明](#配置说明)
11. [定制功能](#定制功能)
12. [开发指南](#开发指南)

---

## 项目概述

### 项目简介

X-AnyLabeling 是一个**先进的自动标注解决方案**，专为计算机视觉任务的图像标注和数据集准备而设计。本版本（mogai1001 fork）是一个定制化分支，专门优化了漫画/图像翻译工作流程，作为 BallonsTranslator 和 ImageTrans 等翻译应用的前置检测工具。

### 主要特性

- **80+ 预配置 AI 模型**：支持自动标注功能
- **多种标注类型**：矩形、多边形、旋转矩形、分割蒙版、姿态估计、OCR 等
- **内置训练功能**：支持自定义模型训练
- **多格式导出**：COCO、YOLO、Pascal VOC、LabelMe 等
- **高级可视化**：PS风格导航器、重叠检测、可配置十字准星
- **半自动化流程**：AI 生成初步标注 + 人工审核修正
- **定制化增强**：为漫画翻译工作流程优化的 UI/UX

### 应用场景

- 计算机视觉数据集创建
- 目标检测数据标注
- 实例分割数据标注
- 姿态估计数据标注
- 漫画/图像翻译预处理
- OCR 数据集准备
- 机器学习模型训练数据准备

---

## 核心功能

### 1. 多样化的标注形状

| 形状类型 | 说明 | 适用场景 |
|---------|------|---------|
| **Rectangle** | 标准矩形 | 水平/垂直目标检测 |
| **Polygon** | 多边形 | 不规则形状分割 |
| **Rotation** | 旋转矩形（拖拽式） | 倾斜目标检测 |
| **Rotation3** | 三点旋转矩形 | 精确文本区域标注 |
| **Circle** | 圆形 | 圆形目标检测 |
| **Line** | 直线 | 车道线、边界线 |
| **Point** | 关键点 | 姿态估计、地标检测 |
| **LineStrip** | 折线 | 复杂路径标注 |

### 2. AI 自动标注系统

#### 核心流程
```
1. 加载图像/视频
   ↓
2. 选择 AI 模型（如 YOLOv8、SAM）
   ↓
3. 运行自动标注
   ↓
4. 审核与编辑标注结果
   ↓
5. 导出为目标格式（COCO/YOLO/VOC）
```

#### 特色功能
- **LRU 缓存机制**：重复预测加速
- **SAHI 支持**：大图像切片推理
- **实时调参**：置信度/IoU 阈值可调
- **批量处理**：支持文件夹批量标注
- **保留现有标注**：增量标注模式
- **API 集成**：支持云端模型调用

### 3. 高级编辑功能

- **顶点编辑**：所有形状支持顶点级编辑
- **形状操作**：联合、分组、复制、粘贴、复制
- **显示控制**：隐藏/显示形状、透明度调节
- **撤销/重做**：10 步历史记录
- **标签过滤**：按标签搜索和筛选
- **快捷键系统**：数字键快速切换模式+预设标签

### 4. 数据导入导出

#### 支持格式

| 格式 | 导入 | 导出 | 说明 |
|-----|------|------|------|
| **COCO** | ✅ | ✅ | 目标检测和分割标准格式 |
| **YOLO** | ✅ | ✅ | YOLO 系列模型格式 |
| **Pascal VOC** | ✅ | ✅ | 经典目标检测格式 |
| **LabelMe** | ✅ | ✅ | 多边形标注格式 |
| **JSON** | ✅ | ✅ | 自定义 JSON 格式 |
| **DOTA** | ❌ | ✅ | 旋转目标检测格式 |

### 5. 可视化系统

- **标签颜色配置**：每个标签独立颜色
- **透明度控制**：形状填充透明度可调
- **分数显示**：显示 AI 模型置信度
- **标签文本显示**：可配置显示方式
- **形状高亮**：选中/悬停高亮
- **重叠检测**：自定义颜色显示重叠区域（橙色）

---

## 技术架构

### 整体架构（MVC 风格）

```
┌─────────────────────────────────────────────────┐
│                   App Entry                      │
│                   (app.py)                       │
└───────────────────┬─────────────────────────────┘
                    │
    ┌───────────────┴───────────────┐
    │                               │
┌───▼──────────┐           ┌───────▼────────┐
│  Views (UI)  │           │  Services      │
│   (PyQt5)    │◄─────────►│  (Business)    │
└───┬──────────┘           └───────┬────────┘
    │                              │
    │                              │
┌───▼────────────────┐    ┌────────▼───────────────┐
│  labeling/         │    │  auto_labeling/        │
│  - label_widget.py │    │  - model_manager.py    │
│  - canvas.py       │    │  - 76+ model files     │
│  - shape.py        │    │  - engines/            │
│  - 38+ widgets     │    │  - trackers/           │
└────────────────────┘    └────────────────────────┘
         │                         │
         │                         │
    ┌────▼─────────────────────────▼────┐
    │      Resources & Configs           │
    │  - 172+ YAML configs               │
    │  - Images & Translations           │
    └────────────────────────────────────┘
```

### 关键设计模式

1. **分层架构**
   - **视图层（Views）**：PyQt5 UI 组件
   - **服务层（Services）**：独立业务逻辑模块
   - **数据层（Models）**：数据结构和 AI 模型包装器

2. **插件式模型系统**
   - 模型管理器根据 YAML 配置动态加载模型
   - 支持 76 种自定义模型类型
   - 支持本地和远程模型加载

3. **多线程模型**
   - QThread 异步操作用于模型加载/推理
   - 防止重型操作期间 UI 冻结
   - 工作线程模式（信号/槽机制）

4. **配置层次结构**
   - 默认配置 → 用户配置 → CLI 参数
   - 保留用户偏好同时允许覆盖

---

## 主要组件说明

### 1. 应用核心 (`app.py`)

**功能：**
- 应用程序入口点
- 初始化 PyQt5 应用
- 配置加载与合并（默认 + 用户 + CLI）
- 多语言支持加载
- 主窗口创建与显示
- 自动更新检查
- 环境设置（线程、日志）

**代码统计：** 253 行

### 2. 配置系统 (`config.py`)

**配置来源优先级：**
```
CLI 参数 > 用户配置文件 > 默认配置
```

**配置文件路径：**
- **默认配置：** `configs/xanylabeling_config.yaml`
- **用户配置：** `~/.YSGxanylabelingrc`

**核心功能：**
- 配置验证
- 自动从旧版本迁移
- 合并策略保留用户值
- 189 个可配置选项

**代码统计：** 152 行

### 3. 视图模块 (`views/`)

#### MainWindow (`mainwindow.py`)
- 主窗口薄包装层
- 状态栏管理
- 窗口生命周期处理

**代码统计：** 49 行

#### 标注模块 (`views/labeling/`)

**核心组件：**

| 文件 | 大小 | 说明 |
|-----|------|------|
| **label_widget.py** | 264 KB | 主标注界面（约 5000+ 行） |
| **canvas.py** | ~50 KB | 绘图和交互层 |
| **shape.py** | 30 KB | 形状数据结构 |
| **label_file.py** | ~30 KB | 文件 I/O 处理 |
| **label_converter.py** | 99 KB | 格式转换器 |

**38+ 专用小部件：**

| 类别 | 小部件 | 功能 |
|-----|-------|------|
| **AI 相关** | auto_labeling_widget.py | AI 模型控制面板 |
|  | chatbot_dialog.py | AI 助手集成 |
|  | vqa_dialog.py | 视觉问答对话框 |
| **标注管理** | object_manager_dialog.py | 形状组织管理 |
|  | label_dialog.py | 标签编辑对话框 |
|  | label_list_widget.py | 标签列表显示 |
| **导航** | navigator_widget.py | PS 风格小地图 |
|  | zoom_widget.py | 缩放控制 |
| **数据处理** | merge_dialog.py | 数据合并界面 |
|  | tag_sort_dialog.py | 标签排序界面 |
| **绘图** | canvas.py | 主画布 |
|  | brightness_contrast_dialog.py | 亮度/对比度调节 |

#### 训练模块 (`views/training/`)

**核心组件：**
- **ultralytics_dialog.py** (70 KB)：YOLO 模型训练界面
- 集成的训练管道

### 4. 服务模块 (`services/`)

#### 自动标注服务 (`services/auto_labeling/`)

**核心架构：**

```
model_manager.py (2102 行)
    ├── 模型生命周期管理（加载/卸载/执行）
    ├── 线程安全操作
    ├── 缓存管理
    └── 批量处理
         │
         ├── model.py (基类)
         │    ├── AutoLabelingModel
         │    ├── Model (抽象基类)
         │    └── ModelConfig
         │
         └── [76 个具体模型实现]
              ├── yolov5.py, yolov8.py, ...
              ├── segment_anything.py
              ├── grounding_dino.py
              └── ...
```

**关键文件：**

| 文件 | 行数 | 功能 |
|-----|------|------|
| **model_manager.py** | 2102 | 模型管理核心 |
| **__init__.py** | 289 | 模型注册表 |
| **model.py** | ~500 | 模型基类 |
| **types.py** | ~200 | 数据结构定义 |
| **lru_cache.py** | ~100 | LRU 缓存实现 |

**推理引擎 (`engines/`):**
- **ONNX Runtime**：主要推理引擎
- **OpenCV DNN**：备用后端
- 多后端支持灵活性

**其他服务：**
- **auto_training/**：模型训练管道
- **merger.py** (14 KB)：合并多个来源的标注
- **tag_sorting.py** (14 KB)：标签排序与组织
- **importers.py** (4 KB)：导入各种格式数据

### 5. 配置文件 (`configs/`)

**主配置：** `xanylabeling_config.yaml` (189 行)

**模型配置：** 172+ YAML 文件

**配置结构：**
```yaml
type: yolov8                    # 模型类型
name: yolov8n                   # 模型名称
display_name: YOLOv8n           # 显示名称
model_path: path/to/model.onnx # 模型文件路径
config_file: path/to/config.yaml # 配置文件
input_width: 640                # 输入宽度
input_height: 640               # 输入高度
nms_threshold: 0.45             # NMS 阈值
confidence_threshold: 0.25      # 置信度阈值
```

**模型配置分类：**
- 检测模型（YOLO 变体、RT-DETR 等）
- 分割模型（SAM 变体）
- 姿态模型
- OCR 模型
- 分类模型

### 6. 资源模块 (`resources/`)

**内容：**
- **images/**：图标、Logo、UI 素材
- **translations/**：多语言支持文件
- **resources.py**：Qt 编译资源

---

## 支持的AI模型

### 模型统计

- **总模型类型：** 76+
- **预配置模型：** 172+ YAML 文件
- **模型文件：** 81 个 Python 实现

### 模型分类详解

#### 1. 目标检测模型（30+ 种）

| 系列 | 模型 | 特点 |
|-----|------|------|
| **YOLO v5** | n/s/m/l/x/n6/s6/m6/l6/x6 | 经典 YOLO，速度快 |
| **YOLO v6** | n/s/m/l | 工业级优化 |
| **YOLO v7** | tiny/n/s/m/l/x | 高精度 |
| **YOLO v8** | n/s/m/l/x | Ultralytics 新版 |
| **YOLO v9** | c/e/m | 可编程梯度 |
| **YOLO v10** | n/s/m/b/l/x | 端到端检测 |
| **YOLO v11** | n/s/m/l/x | 最新版本 |
| **YOLO-World** | s/m/l/v2 | 开放词汇检测 |
| **YOLO-NAS** | s/m/l | Neural Architecture Search |
| **YOLOX** | nano/tiny/s/m/l/x | Anchor-free |
| **Gold-YOLO** | n/s/m/l | 高效 YOLO |
| **DAMO-YOLO** | t/s/m/l | 阿里达摩院 |
| **RT-DETR** | l/x/h | 实时 DETR |
| **DFine** | s/m/l/x | 细粒度检测 |
| **RFDETR** | base/medium/large | 鲁棒 DETR |
| **CLRNet** | - | 车道线检测 |

#### 2. 实例分割模型（15+ 种）

| 模型 | 变体 | 特点 |
|-----|------|------|
| **SAM** | vit-b/l/h | Segment Anything Model |
| **SAM2** | tiny/small/base-plus/large | SAM 第二代 |
| **SAM-HQ** | vit-b/l/h | 高质量分割 |
| **EdgeSAM** | base/with-CLIP | 边缘设备优化 |
| **EfficientViT-SAM** | l0/l1/l2/xl0/xl1 | 高效 SAM |
| **MobileSAM** | vit-h | 移动端 SAM |
| **SAM-Med2D** | vit-b | 医学图像分割 |
| **YOLOv5-Seg** | n/s/m/l/x | YOLO 分割版 |
| **YOLOv8-Seg** | n/s/m/l/x | Ultralytics 分割 |
| **YOLOv11-Seg** | n/s/m/l/x | 最新 YOLO 分割 |

#### 3. 姿态估计模型（5+ 种）

| 模型 | 关键点数 | 应用 |
|-----|---------|------|
| **YOLOv8-Pose** | 17 | 人体姿态 |
| **YOLOv11-Pose** | 17 | 最新姿态估计 |
| **RTMDet-Pose** | 17/133 | 高性能姿态 |
| **DWPose** | 133 | 全身姿态 |

#### 4. OCR 模型（3+ 种）

| 模型 | 语言 | 特点 |
|-----|------|------|
| **PPOCRv4** | 中文/英文 | 百度 PaddleOCR v4 |
| **Japan PPOCR** | 日文 | 日语识别 |
| **License Plate OCR** | 车牌 | 车牌识别 |

#### 5. 分类模型（5+ 种）

| 模型 | 类型 | 应用 |
|-----|------|------|
| **YOLOv5-CLS** | 通用分类 | 图像分类 |
| **YOLOv8-CLS** | 通用分类 | 图像分类 |
| **YOLOv11-CLS** | 通用分类 | 最新分类 |
| **InternImage-CLS** | 通用分类 | 大规模预训练 |
| **PULC** | 属性分类 | 人/车属性识别 |

#### 6. 旋转目标检测（5+ 种）

| 模型 | 变体 | 应用 |
|-----|------|------|
| **YOLOv5-OBB** | n/s/m/l/x | YOLO 旋转检测 |
| **YOLOv8-OBB** | n/s/m/l/x | Ultralytics OBB |
| **YOLOv11-OBB** | n/s/m/l/x | 最新 OBB |
| **DocLayout-YOLO** | - | 文档布局分析 |

#### 7. 目标跟踪（10+ 种）

**支持的跟踪器：**
- BoT-SORT
- ByteTrack

**支持的任务：**
- 检测跟踪（Det + Tracker）
- 分割跟踪（Seg + Tracker）
- 旋转目标跟踪（OBB + Tracker）
- 姿态跟踪（Pose + Tracker）

| 模型系列 | 跟踪器 | 应用 |
|---------|-------|------|
| **YOLOv8-Track** | BoT-SORT/ByteTrack | 视频目标跟踪 |
| **YOLOv11-Track** | BoT-SORT/ByteTrack | 最新跟踪 |

#### 8. 视觉-语言模型（7+ 种）

| 模型 | 特点 | 能力 |
|-----|------|------|
| **Grounding-DINO** | SwinB/SwinT | 文本引导检测 |
| **Florence2** | Large/Base | 微软视觉基础模型 |
| **GeCo** | - | 生成式图像理解 |
| **OpenVision** | - | 开放域视觉 |
| **RAM** | Swin-Large | 识别任何内容 |
| **RAM++** | Swin-Large | 增强识别 |

#### 9. 特殊模型（5+ 种）

| 模型 | 功能 | 应用 |
|-----|------|------|
| **RMBG v1.4** | 背景移除 | 抠图 |
| **Depth-Anything** | 深度估计 | 单目深度 |
| **Depth-Anything v2** | 深度估计 | 改进深度 |
| **UPN** | 边缘检测 | 图像边缘 |

### 模型组合应用

**Grounding-DINO + SAM 流程：**
```
文本提示 → Grounding-DINO（检测） → 边界框 → SAM（分割） → 精确蒙版
```

**示例：**
```
输入："cat"
→ Grounding-DINO 检测所有猫的位置
→ SAM 对每个猫生成精确分割蒙版
输出：高质量实例分割结果
```

---

## 技术栈

### 前端/UI

| 技术 | 版本 | 用途 |
|-----|------|------|
| **PyQt5** | 5.15.7 | 主 GUI 框架 |
| **PyQtWebEngine** | 5.15.7 | Web 内容渲染（聊天机器人/VQA） |
| **qimage2ndarray** | 1.10.0 | Qt-NumPy 图像转换 |

### 计算机视觉/深度学习

| 技术 | 版本 | 用途 |
|-----|------|------|
| **ONNX** | ≥1.13.1 | 模型格式 |
| **ONNX Runtime** | ≥1.16.0 | 推理引擎 |
| **OpenCV** | ≥4.7.0 | 图像处理 |
| **NumPy** | ≤1.26.4 | 数值计算 |
| **Pillow** | ≥7.1.2 | 图像 I/O |
| **SciPy** | - | 科学计算 |

### 几何/数学

| 技术 | 版本 | 用途 |
|-----|------|------|
| **Shapely** | - | 几何操作 |
| **pyclipper** | - | 多边形裁剪 |
| **lapx** | 0.5.5 | 线性分配问题（跟踪） |

### 数据处理

| 技术 | 版本 | 用途 |
|-----|------|------|
| **PyYAML** | - | 配置文件 |
| **jsonlines** | - | JSON 流处理 |
| **json_repair** | - | JSON 错误恢复 |
| **natsort** | 8.1.0 | 自然排序 |
| **tqdm** | - | 进度条 |

### AI/NLP

| 技术 | 版本 | 用途 |
|-----|------|------|
| **OpenAI API** | - | ChatGPT 集成 |
| **tokenizers** | - | 文本分词 |
| **transformers** | (隐式) | 视觉-语言模型 |

### 工具

| 技术 | 版本 | 用途 |
|-----|------|------|
| **termcolor** | 1.1.0 | 彩色终端输出 |
| **markdown** | - | Markdown 渲染 |
| **importlib_metadata** | - | 包元数据 |

### 平台支持

- ✅ **Windows**（主要平台）
- ✅ **macOS**（特殊要求）
- ✅ **Linux**（支持）

---

## 文件结构

```
X-AnyLabeling-mogai1001/
├── anylabeling/                          # 主包
│   ├── __init__.py                       # 包初始化
│   ├── app.py                            # 应用入口 (253 行)
│   ├── app_info.py                       # 应用元数据 (6 行)
│   ├── config.py                         # 配置管理 (152 行)
│   ├── checks.py                         # 系统检查
│   ├── utils.py                          # 通用工具
│   │
│   ├── views/                            # 视图层（UI）
│   │   ├── __init__.py
│   │   ├── mainwindow.py                 # 主窗口 (49 行)
│   │   │
│   │   ├── labeling/                     # 标注 UI 模块
│   │   │   ├── __init__.py
│   │   │   ├── label_widget.py           # 核心小部件 (264 KB, ~5000 行)
│   │   │   ├── label_file.py             # 文件 I/O (~30 KB)
│   │   │   ├── label_converter.py        # 格式转换 (99 KB)
│   │   │   ├── shape.py                  # 形状类 (30 KB)
│   │   │   ├── logger.py                 # 日志记录器
│   │   │   ├── polygon_tracker.py        # 多边形跟踪
│   │   │   │
│   │   │   ├── widgets/                  # 38+ 小部件
│   │   │   │   ├── canvas.py             # 绘图画布 (~50 KB)
│   │   │   │   ├── navigator_widget.py   # PS 风格导航器
│   │   │   │   ├── zoom_widget.py        # 缩放控制
│   │   │   │   ├── brightness_contrast_dialog.py
│   │   │   │   ├── label_dialog.py       # 标签对话框
│   │   │   │   ├── label_list_widget.py  # 标签列表
│   │   │   │   ├── object_manager_dialog.py
│   │   │   │   ├── merge_dialog.py       # 合并对话框
│   │   │   │   ├── tag_sort_dialog.py    # 标签排序
│   │   │   │   │
│   │   │   │   ├── auto_labeling/        # AI 标注小部件
│   │   │   │   │   ├── auto_labeling_widget.py
│   │   │   │   │   ├── model_select_button.py
│   │   │   │   │   └── ...
│   │   │   │   │
│   │   │   │   ├── chatbot_dialog.py     # AI 助手
│   │   │   │   ├── vqa_dialog.py         # 视觉问答
│   │   │   │   ├── escape_worker.py
│   │   │   │   ├── label_filter_combo_box.py
│   │   │   │   ├── model_manager_dialog.py
│   │   │   │   ├── text_edit_dialog.py
│   │   │   │   └── ... (共 38+ 文件)
│   │   │   │
│   │   │   ├── chatbot/                  # 聊天机器人模块 (8 文件)
│   │   │   ├── vqa/                      # VQA 模块 (6 文件)
│   │   │   └── utils/                    # UI 工具 (15 文件)
│   │   │
│   │   ├── training/                     # 训练 UI 模块
│   │   │   ├── ultralytics_dialog.py     # YOLO 训练 (70 KB)
│   │   │   └── widgets/                  # 训练小部件
│   │   │
│   │   └── common/                       # 通用视图
│   │
│   ├── services/                         # 服务层（业务逻辑）
│   │   ├── __init__.py
│   │   │
│   │   ├── auto_labeling/                # AI 模型服务 (81 文件)
│   │   │   ├── __init__.py               # 模型注册表 (289 行)
│   │   │   ├── model_manager.py          # 模型管理核心 (2102 行!)
│   │   │   ├── model.py                  # 模型基类 (~500 行)
│   │   │   ├── types.py                  # 数据结构 (~200 行)
│   │   │   ├── lru_cache.py              # LRU 缓存 (~100 行)
│   │   │   │
│   │   │   ├── engines/                  # 推理引擎
│   │   │   │   ├── build_onnx_engine.py
│   │   │   │   └── build_dnn_engine.py
│   │   │   │
│   │   │   ├── trackers/                 # 目标跟踪器
│   │   │   │   ├── bot_sort.py
│   │   │   │   ├── byte_tracker.py
│   │   │   │   └── ...
│   │   │   │
│   │   │   ├── pose/                     # 姿态估计工具
│   │   │   │
│   │   │   ├── utils/                    # 工具函数
│   │   │   │   ├── sahi/                 # SAHI 实现
│   │   │   │   ├── ppocr/                # PaddleOCR v4
│   │   │   │   └── ...
│   │   │   │
│   │   │   └── [76 个模型文件]           # 具体模型实现
│   │   │       ├── yolov5.py, yolov8.py, yolov11.py
│   │   │       ├── segment_anything.py, segment_anything_2.py
│   │   │       ├── grounding_dino.py, grounding_sam.py
│   │   │       ├── rtmdet_pose.py, yolov8_pose.py
│   │   │       ├── ppocr_v4.py
│   │   │       ├── rmbg_14.py
│   │   │       ├── depth_anything.py
│   │   │       └── ...
│   │   │
│   │   ├── auto_training/                # 训练服务
│   │   ├── merger.py                     # 数据合并 (14 KB)
│   │   ├── tag_sorting.py                # 标签排序 (14 KB)
│   │   └── importers.py                  # 数据导入 (4 KB)
│   │
│   ├── configs/                          # 配置文件
│   │   ├── xanylabeling_config.yaml      # 主配置 (189 行)
│   │   │
│   │   └── auto_labeling/                # 模型配置 (172 文件!)
│   │       ├── yolov8n.yaml
│   │       ├── yolov8s.yaml
│   │       ├── ... (166+ YOLO 配置)
│   │       ├── sam_b.yaml
│   │       ├── sam_l.yaml
│   │       ├── ... (20+ SAM 配置)
│   │       ├── grounding_dino_*.yaml
│   │       ├── florence2_*.yaml
│   │       └── ...
│   │
│   └── resources/                        # 静态资源
│       ├── __init__.py
│       ├── resources.py                  # Qt 资源
│       ├── images/                       # 图标和图像
│       └── translations/                 # 国际化文件
│
├── docs/                                 # 文档
│   ├── rotation3-Complete-Project-Summary-EN.md
│   ├── rotation3-完整项目总结-中文版.md
│   └── ...
│
├── requirements.txt                      # 依赖项 (22 包)
├── requirements-gpu.txt                  # GPU 版本
├── requirements-macos.txt                # macOS 版本
├── pyproject.toml                        # 项目配置
├── README.md                            # 英文文档
├── README_zh-CN.md                      # 中文文档
└── CHANGELOG.md                         # 版本历史
```

### 关键统计

- **Python 文件总数：** 200+
- **模型实现：** 81 文件
- **模型配置：** 172+ YAML 文件
- **UI 小部件：** 38+ 小部件文件
- **代码行数：** ~50,000+ 行（估计）
- **最大文件：** label_widget.py (264 KB, ~5000 行)
- **支持模型类型：** 76 种

---

## 使用场景

### 场景 1：目标检测数据集创建

```
1. 加载图像文件夹
   ↓
2. 选择 YOLOv8 模型（检测）
   ↓
3. 运行自动标注（批量）
   ↓
4. 人工审核与修正
   - 删除误检
   - 添加漏检
   - 调整边界框
   ↓
5. 导出为 YOLO 格式
   ↓
6. 用于 YOLO 训练
```

### 场景 2：实例分割数据集

```
1. 加载图像
   ↓
2. 使用 Grounding-DINO + SAM 组合
   - 输入文本提示："person, car, dog"
   - Grounding-DINO 检测目标
   - SAM 生成精确蒙版
   ↓
3. 人工细化分割蒙版
   - 编辑顶点
   - 删除/添加蒙版
   ↓
4. 导出为 COCO 格式
```

### 场景 3：漫画翻译预处理（mogai1001 定制）

```
1. 加载漫画图像
   ↓
2. 使用 YOLOv8-OBB（旋转检测）
   - 自动检测文本框/气泡
   ↓
3. 使用 rotation3 模式手动精修
   - 三点创建精确旋转矩形
   - 利用"工"字参考线对齐
   ↓
4. 使用 PS 风格导航器浏览大图
   ↓
5. 导出为 DOTA/JSON 格式
   ↓
6. 导入到 BallonsTranslator
```

### 场景 4：姿态估计数据集

```
1. 加载人体图像
   ↓
2. 使用 YOLOv8-Pose 模型
   - 自动检测 17 个关键点
   ↓
3. 手动调整关键点位置
   - 拖动点标记
   - 删除/添加点
   ↓
4. 导出为 COCO-Keypoints 格式
```

### 场景 5：OCR 数据集准备

```
1. 加载文档图像
   ↓
2. 使用 PPOCRv4 模型
   - 自动检测文本区域
   - 识别文本内容
   ↓
3. 使用 rotation3 模式精修倾斜文本
   - 三点创建旋转矩形
   - 垂直约束保证矩形
   ↓
4. 编辑标签（文本内容）
   ↓
5. 导出为 OCR 训练格式
```

### 场景 6：自定义模型训练流程

```
1. 使用 X-AnyLabeling 标注数据
   ↓
2. 导出为 YOLO 格式
   ↓
3. 使用内置训练对话框
   - 选择训练参数
   - 设置 epochs、batch size
   - 选择预训练模型
   ↓
4. 开始训练
   ↓
5. 导出 ONNX 模型
   ↓
6. 添加到 X-AnyLabeling 模型库
   ↓
7. 在新数据上测试
```

---

## 安装与运行

### 系统要求

- **操作系统：** Windows 10/11, macOS 10.15+, Ubuntu 20.04+
- **Python：** 3.8+
- **内存：** 8GB+ RAM（推荐 16GB+）
- **显卡：** 支持 CUDA 的 NVIDIA GPU（可选，推荐）

### 安装步骤

#### 1. 克隆仓库
```bash
git clone https://github.com/CVHub520/X-AnyLabeling.git
cd X-AnyLabeling
```

#### 2. 创建虚拟环境
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate     # Windows
```

#### 3. 安装依赖

**CPU 版本：**
```bash
pip install -r requirements.txt
```

**GPU 版本（推荐）：**
```bash
pip install -r requirements-gpu.txt
```

**macOS 版本：**
```bash
pip install -r requirements-macos.txt
```

#### 4. 运行应用
```bash
python anylabeling/app.py
```

### 命令行参数

```bash
# 基本用法
python anylabeling/app.py [图像文件或文件夹]

# 指定输出目录
python anylabeling/app.py --output /path/to/output

# 指定配置文件
python anylabeling/app.py --config /path/to/config.yaml

# 设置日志级别
python anylabeling/app.py --logger-level debug

# 重置配置
python anylabeling/app.py --reset-config

# 禁用自动更新检查
python anylabeling/app.py --no-auto-update-check

# 预设标签
python anylabeling/app.py --labels person,car,dog

# 自动保存
python anylabeling/app.py --autosave

# 加载标签文件
python anylabeling/app.py --labels labels.txt
```

### 模型下载

**自动下载：**
- 首次使用时，模型会自动下载到 `~/.anylabeling/models/`

**手动下载：**
1. 访问模型仓库
2. 下载所需模型文件（.onnx）
3. 放置到指定路径
4. 修改配置文件中的 `model_path`

---

## 配置说明

### 主配置文件

**路径：** `~/.YSGxanylabelingrc`

**关键配置项：**

```yaml
# 显示设置
opacity: 0.5                  # 形状透明度 (0.0-1.0)
show_labels: true              # 显示标签文本
show_scores: true              # 显示置信度分数
show_text_field: true          # 显示文本字段

# 标签设置
labels:                        # 预设标签列表
  - person
  - car
  - dog
label_colors:                  # 标签颜色
  person: [255, 0, 0]         # 红色
  car: [0, 255, 0]            # 绿色
  dog: [0, 0, 255]            # 蓝色

# 自动保存
auto_save: true                # 启用自动保存
auto_save_interval: 300        # 自动保存间隔（秒）

# 画布设置
epsilon: 10.0                  # 顶点捕捉距离
edge_width: 3                  # 边缘宽度
point_size: 8                  # 点大小
crosshair_size: 30             # 十字准星大小
crosshair_width: 2             # 十字准星宽度
crosshair_opacity: 0.7         # 十字准星透明度
crosshair_color: [255, 0, 0]  # 十字准星颜色

# 高级设置
keep_prev: false               # 保留上一帧标注
store_data: true               # 将图像数据存储到 JSON
sort_labels: true              # 标签排序

# 语言设置
language: zh_CN                # 界面语言

# AI 模型设置
auto_labeling_mode: true       # 启用自动标注
auto_labeling_preserve_existing_annotations: true  # 保留现有标注
```

### 模型配置文件

**示例：YOLOv8n 配置** (`configs/auto_labeling/yolov8n.yaml`)

```yaml
type: yolov8
name: yolov8n
display_name: YOLOv8n Object Detection
model_path: https://github.com/.../yolov8n.onnx
input_width: 640
input_height: 640
stride: 32
nms_threshold: 0.45
confidence_threshold: 0.25
classes:
  - person
  - bicycle
  - car
  # ... (80 classes)
```

### 数字快捷键配置

**通过 UI 配置：**
1. 打开"工具" → "数字快捷键管理器"
2. 为数字键 0-9 配置：
   - 创建模式（polygon/rectangle/rotation/rotation3/...）
   - 预设标签（person/car/dog/...）
3. 保存配置

**示例配置：**
- **按键 1：** rotation3 模式 + "text" 标签
- **按键 2：** rectangle 模式 + "bubble" 标签
- **按键 3：** polygon 模式 + "panel" 标签

---

## 定制功能

### mogai1001 Fork 的独特增强

#### 1. rotation3 三点旋转矩形模式

**功能：**
- 三次点击创建旋转矩形（起点 → 长度 → 宽度）
- 自动垂直约束（第二条边自动垂直于第一条边）
- "工"字形参考线帮助对齐

**详细文档：**
- [rotation3-完整项目总结-中文版.md](rotation3-完整项目总结-中文版.md)
- [rotation3-Complete-Project-Summary-EN.md](rotation3-Complete-Project-Summary-EN.md)

**使用场景：**
- 精确文本区域标注
- 倾斜文本检测
- 漫画气泡标注

**技术亮点：**
- 向量投影算法保证垂直
- 缩放自适应视觉反馈
- Backspace 逐步撤销

#### 2. PS 风格导航器（Navigator）

**功能：**
- 小地图显示整体图像
- 当前视口矩形框
- 页码显示
- 点击小地图快速跳转

**优势：**
- 适合大尺寸图像（如垂直长图、漫画页）
- 快速定位标注区域
- 类似 Photoshop 导航器体验

#### 3. 增强的高亮系统

**功能：**
- 悬停高亮（默认青色）
- 选中高亮（默认红色）
- 重叠高亮（默认橙色）
- 可配置颜色

**配置：**
```yaml
highlight_hover_color: [0, 255, 255]       # 悬停：青色
highlight_selected_color: [255, 0, 0]      # 选中：红色
highlight_overlap_color: [255, 165, 0]     # 重叠：橙色
```

#### 4. 旋转矩形鼠标滚轮微调

**功能：**
- 鼠标悬停在旋转矩形边缘
- 滚动鼠标滚轮微调边界
- 支持倾斜矩形（官方版仅支持水平）

**操作：**
- 悬停在上边缘 + 滚轮：调整上边界
- 悬停在下边缘 + 滚轮：调整下边界
- 悬停在左边缘 + 滚轮：调整左边界
- 悬停在右边缘 + 滚轮：调整右边界

#### 5. 改进的标签显示

**增强：**
- 标签显示在形状外部（减少遮挡）
- 显示总序号和类别序号
  - 格式：`[总序号] 标签名 (类别序号)`
  - 示例：`[5] person (2)`
- 更紧凑的文本布局

#### 6. 交互式标签区域

**功能：**
- 标签列表区域增强交互
- 全选/反选功能
- 高亮功能
- 快速批量操作

#### 7. 可定制十字准星

**功能：**
- 精确标注用十字准星光标
- 可调颜色、宽度、透明度

**配置：**
```yaml
crosshair_enabled: true
crosshair_color: [255, 0, 0]    # 红色
crosshair_width: 2
crosshair_opacity: 0.7
crosshair_size: 30
```

---

## 开发指南

### 项目结构规范

```
anylabeling/
├── views/          # 视图层（UI）- 不应包含业务逻辑
├── services/       # 服务层（业务逻辑）- 独立于 UI
├── configs/        # 配置文件 - YAML 格式
└── resources/      # 静态资源 - 图像、翻译
```

### 添加新模型

#### 1. 创建模型类

**文件：** `services/auto_labeling/your_model.py`

```python
from typing import List
from anylabeling.services.auto_labeling.model import Model
from anylabeling.services.auto_labeling.types import AutoLabelingResult

class YourModel(Model):
    """Your model description"""

    class Meta:
        required_config_names = [
            "type",
            "name",
            "display_name",
            "model_path",
        ]
        widgets = ["button_run"]
        output_modes = {
            "rectangle": QCoreApplication.translate("Model", "Rectangle"),
        }
        default_output_mode = "rectangle"

    def __init__(self, config_path: str, on_message) -> None:
        super().__init__(config_path, on_message)
        # 初始化模型

    def predict_shapes(self, image, filename=None) -> AutoLabelingResult:
        """
        Predict shapes for the given image
        """
        # 实现预测逻辑
        # 返回 AutoLabelingResult
        pass
```

#### 2. 注册模型

**文件：** `services/auto_labeling/__init__.py`

```python
from .your_model import YourModel

MODELS = {
    # ... 现有模型
    "your_model": YourModel,
}
```

#### 3. 创建配置文件

**文件：** `configs/auto_labeling/your_model.yaml`

```yaml
type: your_model
name: your_model_v1
display_name: Your Model v1
model_path: path/to/model.onnx
input_width: 640
input_height: 640
confidence_threshold: 0.25
nms_threshold: 0.45
classes:
  - class1
  - class2
```

#### 4. 测试模型

```python
# 在 X-AnyLabeling 中
# 1. 打开应用
# 2. 点击"模型" → 选择 "Your Model v1"
# 3. 加载图像
# 4. 点击"运行 (i)"
# 5. 查看结果
```

### 添加新小部件

#### 1. 创建小部件类

**文件：** `views/labeling/widgets/your_widget.py`

```python
from PyQt5 import QtWidgets, QtCore

class YourWidget(QtWidgets.QWidget):
    # 定义信号
    value_changed = QtCore.pyqSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        # 初始化 UI
        layout = QtWidgets.QVBoxLayout()
        # 添加控件
        self.setLayout(layout)

    def set_value(self, value):
        # 设置值
        pass

    def get_value(self):
        # 获取值
        return None
```

#### 2. 集成到主界面

**文件：** `views/labeling/label_widget.py`

```python
from .widgets.your_widget import YourWidget

class MainWindow:
    def __init__(self):
        # ...
        self.your_widget = YourWidget()
        # 连接信号
        self.your_widget.value_changed.connect(self.on_value_changed)
        # 添加到布局
        self.layout.addWidget(self.your_widget)

    def on_value_changed(self, value):
        # 处理值变化
        pass
```

### 贡献指南

1. **Fork 仓库**
2. **创建功能分支：** `git checkout -b feature/your-feature`
3. **提交更改：** `git commit -m 'Add your feature'`
4. **推送到分支：** `git push origin feature/your-feature`
5. **创建 Pull Request**

### 代码风格

- **Python：** 遵循 PEP 8
- **文档字符串：** Google 风格
- **类型提示：** 尽可能使用类型注解
- **注释：** 英文注释

### 测试

```bash
# 运行测试（如果有）
python -m pytest tests/

# 代码格式检查
flake8 anylabeling/

# 类型检查
mypy anylabeling/
```

---

## 附录

### 相关文档

1. **rotation3 功能完整总结（中文）**
   - 文件：`rotation3-完整项目总结-中文版.md`
   - 内容：rotation3 功能详细技术实现

2. **rotation3 Feature Summary (English)**
   - 文件：`rotation3-Complete-Project-Summary-EN.md`
   - 内容：rotation3 feature technical implementation

3. **README（中文）**
   - 文件：`README_zh-CN.md`
   - 内容：项目基本介绍和快速开始

4. **README (English)**
   - 文件：`README.md`
   - 内容：Project introduction and quick start

5. **更新日志**
   - 文件：`CHANGELOG.md`
   - 内容：版本历史和更新记录

### 常见问题（FAQ）

**Q1：如何添加自定义标签？**

A：打开"编辑" → "标签" → 添加新标签，或在配置文件中设置 `labels` 列表。

**Q2：模型下载失败怎么办？**

A：
1. 检查网络连接
2. 手动下载模型文件
3. 修改配置文件中的 `model_path` 为本地路径

**Q3：如何使用 GPU 加速？**

A：
1. 安装 GPU 版 ONNX Runtime：`pip install onnxruntime-gpu`
2. 确保安装 CUDA 和 cuDNN
3. 应用会自动使用 GPU

**Q4：支持视频标注吗？**

A：支持，可以加载视频文件，逐帧标注。使用跟踪模型可实现半自动视频标注。

**Q5：如何导出为 YOLO 格式？**

A：
1. 完成标注
2. 点击"文件" → "导出 YOLO 标注"
3. 选择保存路径
4. 生成 `classes.txt` 和 `labels/*.txt`

**Q6：rotation3 和 rotation 有什么区别？**

A：
- **rotation**：拖拽式，点击中心后拖拽确定大小和角度
- **rotation3**：三点式，点击起点→长度→宽度，自动垂直约束

**Q7：如何批量标注多张图像？**

A：
1. 加载文件夹
2. 选择 AI 模型
3. 点击"批量处理"（或快捷键）
4. 设置参数
5. 运行批量标注

**Q8：支持多人协作标注吗？**

A：当前版本不直接支持。可通过文件共享 + 数据合并功能实现协作。

### 快捷键参考

| 快捷键 | 功能 |
|-------|------|
| **Ctrl+O** | 打开图像 |
| **Ctrl+S** | 保存标注 |
| **Ctrl+D** | 复制选中形状 |
| **Ctrl+Z** | 撤销 |
| **Ctrl+Y** | 重做 |
| **Delete** | 删除选中形状 |
| **ESC** | 取消当前创建 |
| **Backspace** | 撤销最后一个点（polygon/rotation3） |
| **Space** | 编辑标签 |
| **A** | 上一张图像 |
| **D** | 下一张图像 |
| **W** | 创建矩形 |
| **P** | 创建多边形 |
| **R** | 创建旋转矩形 |
| **I** | 运行 AI 模型 |
| **H** | 隐藏/显示形状 |
| **+/-** | 缩放 |
| **Ctrl+滚轮** | 缩放 |
| **0-9** | 数字快捷键（可配置） |

### 性能优化建议

1. **使用 GPU 加速**
   - 安装 `onnxruntime-gpu`
   - 使用 CUDA 11.x+

2. **调整图像分辨率**
   - 大图像可能导致性能下降
   - 考虑使用 SAHI（切片推理）

3. **减少标注数量**
   - 过多形状可能影响渲染性能
   - 使用对象管理器分组

4. **调整可视化设置**
   - 降低透明度
   - 隐藏不必要的视觉元素

5. **使用批量处理**
   - 批量标注比逐张标注更高效

---

## 版本信息

**当前版本：** 3.2.2 (mogai1001)
**发布日期：** 2025-09
**最后更新：** 2025-10-01

**版本历史：**
- **v3.2.2** - 稳定版本
- **v3.2.0** - 添加 rotation3 功能
- **v3.1.0** - 添加 PS 风格导航器
- **v3.0.0** - 主要架构重构
- **v2.x** - 早期版本

---

## 许可证

本项目遵循原 X-AnyLabeling 项目的许可证。

---

## 联系与支持

- **GitHub Issues：** https://github.com/CVHub520/X-AnyLabeling/issues
- **原项目：** https://github.com/CVHub520/X-AnyLabeling
- **文档：** 见项目 `docs/` 目录

---

**文档结束**
