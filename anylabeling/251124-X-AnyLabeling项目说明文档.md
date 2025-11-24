# X-AnyLabeling 项目技术文档

**文档版本：** 251124
**项目版本：** 3.2.2 (Hmogai_1123 定制版)
**文档生成日期：** 2025年11月24日
**应用名称：** Hmogai_1123_X-AnyLabeling
**项目描述：** Advanced Auto Labeling Solution with Added Features

---

## 📑 目录

1. [项目概述](#项目概述)
2. [核心架构](#核心架构)
3. [技术栈](#技术栈)
4. [项目结构](#项目结构)
5. [核心模块详解](#核心模块详解)
6. [AI模型系统](#ai模型系统)
7. [UI组件系统](#ui组件系统)
8. [配置系统](#配置系统)
9. [标注形状系统](#标注形状系统)
10. [最新功能特性](#最新功能特性)
11. [开发指南](#开发指南)
12. [部署与运行](#部署与运行)

---

## 项目概述

### 项目定位

X-AnyLabeling 是一个基于 PyQt5 的**智能图像标注工具**，专注于计算机视觉数据集的创建和管理。本项目是 CVHub520/X-AnyLabeling 的定制化分支，针对图像翻译、漫画标注等特定场景进行了深度优化。

### 核心特点

- **80+ AI模型集成**：支持 YOLO 系列、SAM 系列、Grounding-DINO 等主流模型
- **多种标注模式**：矩形、多边形、旋转矩形、rotation3、圆形、线条、点等
- **智能辅助系统**：智能辅助线、间距线、吸附功能、十字线等
- **高级查看器**：横向/垂直滚动看图、导航器、缩略图预览
- **批量处理能力**：支持文件夹批量标注、批量转换、批量修改
- **丰富的导出格式**：COCO、YOLO、VOC、DOTA、LabelMe 等
- **可扩展架构**：插件式模型系统、配置驱动的UI


### 应用场景

1. **计算机视觉数据集创建**
   - 目标检测数据集标注
   - 实例分割数据集标注
   - 关键点检测数据集标注

2. **图像翻译预处理**
   - 漫画文本框检测
   - 倾斜文本区域标注
   - 气泡对话框标注

3. **OCR数据准备**
   - 文档文本区域标注
   - 表格结构标注
   - 手写文字标注

4. **工业检测**
   - 缺陷检测标注
   - 产品质量检测
   - 零件识别标注

---

## 核心架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│                    Application Entry                     │
│                       (app.py)                           │
│  - 应用初始化                                             │
│  - 配置加载                                               │
│  - 多语言支持                                             │
│  - 自动更新检查                                           │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
┌───────▼────────┐       ┌────────▼────────┐
│  Views (UI层)  │◄─────►│  Services (业务) │
│   - PyQt5 UI   │       │   - AI模型       │
│   - 51个组件   │       │   - 数据处理     │
└───────┬────────┘       └────────┬────────┘
        │                         │
        │                         │
┌───────▼──────────────┐  ┌───────▼──────────────┐
│  labeling/           │  │  auto_labeling/      │
│  - label_widget.py   │  │  - model_manager.py  │
│  - canvas.py         │  │  - 80+ 模型文件      │
│  - shape.py          │  │  - engines/          │
│  - 51个widgets       │  │  - trackers/         │
└──────────────────────┘  └──────────────────────┘
         │                         │
         └────────┬────────────────┘
                  │
     ┌────────────▼────────────────┐
     │   Resources & Configs        │
     │  - 172+ YAML模型配置         │
     │  - 图标和翻译资源             │
     │  - xanylabeling_config.yaml  │
     └──────────────────────────────┘
```

### 设计模式

1. **MVC架构**
   - Model: Shape、LabelFile 等数据模型
   - View: 各种 Widget 和 Dialog
   - Controller: LabelWidget 作为主控制器

2. **插件式模型系统**
   - 模型通过 YAML 配置动态加载
   - 统一的模型接口 (Model 基类)
   - 支持本地和远程模型

3. **信号槽机制**
   - PyQt5 信号槽实现组件通信
   - 解耦UI和业务逻辑
   - 支持异步操作

4. **配置驱动**
   - YAML 配置文件驱动功能
   - 用户配置与默认配置合并
   - 运行时配置热更新

---

## 技术栈

### 前端框架

| 技术 | 版本 | 用途 |
|-----|------|------|
| **PyQt5** | 5.15.7 | GUI框架 |
| **PyQtWebEngine** | 5.15.7 | Web内容渲染 |
| **qimage2ndarray** | 1.10.0 | 图像格式转换 |

### AI/深度学习

| 技术 | 版本 | 用途 |
|-----|------|------|
| **ONNX** | ≥1.13.1 | 模型格式标准 |
| **ONNX Runtime** | ≥1.16.0 | 推理引擎 |
| **OpenCV** | ≥4.7.0 | 图像处理 |
| **NumPy** | ≤1.26.4 | 数值计算 |

### 数据处理

| 技术 | 版本 | 用途 |
|-----|------|------|
| **PyYAML** | - | 配置文件解析 |
| **Pillow** | ≥7.1.2 | 图像I/O |
| **Shapely** | - | 几何运算 |
| **pyclipper** | - | 多边形裁剪 |

### 其他工具

| 技术 | 版本 | 用途 |
|-----|------|------|
| **natsort** | 8.1.0 | 自然排序 |
| **tqdm** | - | 进度条 |
| **termcolor** | 1.1.0 | 终端彩色输出 |

---

## 项目结构


### 目录结构

```
X-AnyLabeling-Hmogai1123/
├── anylabeling/                    # 主包目录
│   ├── __init__.py
│   ├── app.py                      # 应用入口 (253行)
│   ├── app_info.py                 # 应用元信息
│   ├── config.py                   # 配置管理系统 (152行)
│   ├── checks.py                   # 系统检查
│   ├── utils.py                    # 通用工具函数
│   │
│   ├── views/                      # 视图层 (UI组件)
│   │   ├── mainwindow.py           # 主窗口 (49行)
│   │   │
│   │   ├── labeling/               # 标注模块
│   │   │   ├── label_widget.py     # 核心标注界面 (~10000行)
│   │   │   ├── canvas.py           # 画布组件
│   │   │   ├── shape.py            # 形状数据结构
│   │   │   ├── label_file.py       # 文件I/O
│   │   │   ├── label_converter.py  # 格式转换器
│   │   │   ├── logger.py           # 日志系统
│   │   │   │
│   │   │   ├── widgets/            # 51个UI组件
│   │   │   │   ├── auto_labeling_widget.py      # AI自动标注控制面板
│   │   │   │   ├── canvas.py                    # 画布组件（绘图和交互）
│   │   │   │   ├── navigator_widget.py          # 导航器小部件
│   │   │   │   ├── navigator_dialog.py          # 导航器对话框
│   │   │   │   ├── horizontal_viewer_dialog.py  # 横向查看器
│   │   │   │   ├── vertical_viewer_dialog.py    # 垂直查看器
│   │   │   │   ├── rectangle_scale_dialog.py    # 矩形缩放工具
│   │   │   │   ├── smart_guides_dialog.py       # 智能辅助线
│   │   │   │   ├── object_manager_dialog.py     # 对象管理器
│   │   │   │   ├── overview_dialog.py           # 统计总览
│   │   │   │   ├── merge_dialog.py              # 合并工具
│   │   │   │   ├── tag_sort_dialog.py           # 标签排序
│   │   │   │   ├── label_tool_dialog.py         # 标签工具
│   │   │   │   ├── mask_generator_dialog.py     # 掩膜生成器
│   │   │   │   ├── segmentation_dialog.py       # 分割工具
│   │   │   │   ├── alignment_dialog.py          # 对齐工具
│   │   │   │   ├── color_manager_dialog.py      # 颜色管理器
│   │   │   │   ├── shortcut_manager_dialog.py   # 快捷键管理
│   │   │   │   ├── keymap_dialog.py             # 键位映射
│   │   │   │   ├── wheel_settings_dialog.py     # 滚轮设置
│   │   │   │   ├── rectangle3_width_dialog.py   # Rectangle3宽度
│   │   │   │   ├── page_text_dialog.py          # 页面文本
│   │   │   │   ├── highlight_settings_dialog.py # 高亮设置
│   │   │   │   ├── expand_margins_dialog.py     # 边距扩展
│   │   │   │   ├── file_filter_dialog.py        # 文件过滤
│   │   │   │   ├── zoom_widget.py               # 缩放控件
│   │   │   │   ├── toolbar.py                   # 工具栏
│   │   │   │   ├── label_dialog.py              # 标签对话框
│   │   │   │   ├── label_list_widget.py         # 标签列表
│   │   │   │   ├── unique_label_qlist_widget.py # 唯一标签列表
│   │   │   │   ├── brightness_contrast_dialog.py
│   │   │   │   ├── chatbot_dialog.py            # AI聊天机器人
│   │   │   │   ├── vqa_dialog.py                # 视觉问答
│   │   │   │   └── ... (共51个文件)
│   │   │   │
│   │   │   ├── chatbot/            # 聊天机器人模块
│   │   │   ├── vqa/                # VQA模块
│   │   │   └── utils/              # UI工具函数
│   │   │
│   │   ├── mainwindow_widgets/     # 主窗口组件
│   │   │   └── traffic_light_dialog.py  # 红绿灯对话框
│   │   │
│   │   ├── training/               # 训练模块
│   │   │   └── ultralytics_dialog.py
│   │   │
│   │   └── common/                 # 通用组件
│   │       └── toaster.py          # 提示消息
│   │
│   ├── services/                   # 服务层 (业务逻辑)
│   │   ├── auto_labeling/          # AI自动标注服务
│   │   │   ├── __init__.py         # 模型注册表
│   │   │   ├── model_manager.py    # 模型管理器 (2102行)
│   │   │   ├── model.py            # 模型基类
│   │   │   ├── types.py            # 数据类型定义
│   │   │   ├── lru_cache.py        # LRU缓存
│   │   │   │
│   │   │   ├── engines/            # 推理引擎
│   │   │   │   ├── build_onnx_engine.py
│   │   │   │   └── build_dnn_engine.py
│   │   │   │
│   │   │   ├── trackers/           # 目标跟踪器
│   │   │   │   ├── bot_sort.py
│   │   │   │   └── byte_tracker.py
│   │   │   │
│   │   │   ├── pose/               # 姿态估计
│   │   │   ├── utils/              # 工具函数
│   │   │   │   ├── sahi/           # SAHI实现
│   │   │   │   └── ppocr/          # PaddleOCR
│   │   │   │
│   │   │   └── [80个模型文件]      # 具体模型实现
│   │   │       ├── yolov5.py, yolov8.py, yolov11.py
│   │   │       ├── yolo12.py
│   │   │       ├── segment_anything.py
│   │   │       ├── segment_anything_2.py
│   │   │       ├── grounding_dino.py
│   │   │       ├── grounding_sam.py
│   │   │       ├── florence2.py
│   │   │       ├── rtdetr.py, rtdetrv2.py
│   │   │       ├── ppocr_v4.py
│   │   │       ├── rmbg.py
│   │   │       ├── depth_anything.py
│   │   │       └── ...
│   │   │
│   │   ├── auto_training/          # 自动训练服务
│   │   ├── merger.py               # 数据合并
│   │   ├── tag_sorting.py          # 标签排序
│   │   └── importers.py            # 数据导入
│   │
│   ├── configs/                    # 配置文件
│   │   ├── xanylabeling_config.yaml  # 主配置文件
│   │   └── auto_labeling/          # 模型配置 (172个YAML)
│   │       ├── yolov8s.yaml
│   │       ├── yolov11s.yaml
│   │       ├── yolo12n.yaml
│   │       ├── sam2_hiera_base.yaml
│   │       ├── grounding_dino_*.yaml
│   │       └── ...
│   │
│   ├── resources/                  # 静态资源
│   │   ├── images/                 # 图标和图片
│   │   ├── translations/           # 翻译文件
│   │   │   ├── zh_CN.qm
│   │   │   └── en_US.qm
│   │   └── resources.py            # Qt资源文件
│   │
│   └── utils/                      # 工具模块
│       └── ctd_mask_generator.py   # CTD掩膜生成器
│
├── docs/                           # 文档目录 (50+个文档)
│   ├── 251124-X-AnyLabeling项目说明文档.md
│   ├── rotation3-完整项目总结-中文版.md
│   ├── 矩形缩放工具-实现文档.md
│   ├── 矩形间距线功能-实现文档.md
│   ├── 智能辅助线功能说明.md
│   ├── 文件过滤功能说明.md
│   ├── 最近打开文件夹功能说明.md
│   ├── 窗口最小化功能添加说明.md
│   └── ...
│
├── requirements.txt                # Python依赖
├── requirements-gpu.txt            # GPU版本依赖
├── requirements-macos.txt          # macOS依赖
└── README.md                       # 项目说明

```

### 关键统计数据

- **Python文件总数**: 200+
- **UI组件数量**: 51个
- **AI模型实现**: 80个
- **模型配置文件**: 172个YAML
- **文档数量**: 50+个
- **代码总行数**: ~50,000行
- **最大单文件**: label_widget.py (~10,000行)

---

## 核心模块详解

### 1. 应用入口 (app.py)

**职责**:
- 应用程序初始化
- 命令行参数解析
- 配置加载与合并
- 多语言支持
- 自动更新检查
- 主窗口创建

**关键代码**:
```python
def main():
    # 1. 解析命令行参数
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset-config", ...)
    parser.add_argument("--logger-level", ...)
    args = parser.parse_args()
    
    # 2. 加载配置
    config = get_config(config_file_or_yaml, config_from_args)
    
    # 3. 强制中文界面
    config["language"] = "zh_CN"
    
    # 4. 创建Qt应用
    app = QtWidgets.QApplication(sys.argv)
    
    # 5. 加载翻译
    translator = QtCore.QTranslator()
    translator.load(":/languages/translations/zh_CN.qm")
    app.installTranslator(translator)
    
    # 6. 创建主窗口
    win = MainWindow(app, config, filename, output_file, output_dir)
    
    # 7. 启动应用
    win.showMaximized()
    sys.exit(app.exec())
```

**特点**:
- 支持命令行参数覆盖配置
- 自动检测并迁移旧配置文件
- 延迟2秒后检查更新
- 强制使用中文界面


### 2. 配置系统 (config.py)

**职责**:
- 配置文件加载与合并
- 配置验证
- 配置持久化
- 默认配置管理

**配置优先级**:
```
命令行参数 > 用户配置文件 > 默认配置
```

**配置文件路径**:
- 默认配置: `configs/xanylabeling_config.yaml`
- 用户配置: `~/.YSGxanylabelingrc`

**关键函数**:
```python
def get_config(config_file_or_yaml, config_from_args):
    # 1. 加载默认配置
    config = get_default_config()
    
    # 2. 加载指定配置文件
    if config_file_or_yaml and exists(config_file_or_yaml):
        with open(config_file_or_yaml) as f:
            user_config = yaml.safe_load(f)
        update_dict(config, user_config)
    
    # 3. 加载用户配置文件
    user_config_file = "~/.YSGxanylabelingrc"
    if exists(user_config_file):
        with open(user_config_file) as f:
            user_config = yaml.safe_load(f)
        update_dict(config, user_config)
    
    # 4. 应用命令行参数
    if config_from_args:
        update_dict(config, config_from_args)
    
    # 5. 保存合并后的配置
    save_config(config)
    
    return config
```

**配置合并策略**:
- 使用 `_merge_prefer_non_null` 保留用户非空值
- 递归合并嵌套字典
- 特殊处理 `label_toggle_shortcuts` 以支持删除操作

### 3. 主标注界面 (label_widget.py)

**规模**: ~10,000行代码

**职责**:
- 标注界面主控制器
- 文件管理 (打开/保存/导入/导出)
- 形状管理 (创建/编辑/删除)
- AI模型调用
- 快捷键处理
- UI组件协调

**核心类**:
```python
class LabelingWidget(QtWidgets.QWidget):
    # 信号定义
    next_files_changed = QtCore.pyqtSignal(list)
    shape_list_changed = QtCore.pyqtSignal()
    
    def __init__(self, parent, config, filename, output, output_file, output_dir):
        # 初始化配置
        self._config = config
        
        # 初始化UI组件
        self.canvas = Canvas(...)
        self.label_list = LabelListWidget()
        self.unique_label_list = UniqueLabelQListWidget()
        
        # 初始化对话框
        self.horizontal_viewer_dialog = None
        self.vertical_viewer_dialog = None
        self.rectangle_scale_dialog = None
        self.smart_guides_dialog = None
        # ... 更多对话框
        
        # 初始化状态
        self.image_list = []
        self.filename = None
        self.dirty = False
        
    # 核心方法
    def load_file(self, filename):
        """加载图像文件"""
        
    def save_file(self, filename):
        """保存标注文件"""
        
    def import_image_folder(self, dirpath):
        """导入图像文件夹"""
        
    def open_horizontal_viewer(self):
        """打开横向查看器"""
        
    def open_vertical_viewer(self):
        """打开垂直查看器"""
```

**关键功能**:
1. **文件管理**
   - 支持单文件和文件夹导入
   - 自动扫描图像文件
   - 支持递归子文件夹
   - 文件过滤功能

2. **形状管理**
   - 支持9种形状类型
   - 形状创建/编辑/删除
   - 形状复制/粘贴/复制
   - 形状分组/联合

3. **AI集成**
   - 模型选择和加载
   - 自动标注
   - 批量处理
   - 结果审核

4. **查看器集成**
   - 横向滚动看图
   - 垂直滚动看图
   - 导航器
   - 缩略图预览

### 4. 画布系统 (canvas.py)

**职责**:
- 图像渲染
- 形状绘制
- 鼠标交互
- 辅助线显示
- 缩放和平移

**关键特性**:
1. **绘制模式**
   - CREATE: 创建新形状
   - EDIT: 编辑现有形状
   - PASTE: 粘贴预览模式

2. **交互功能**
   - 鼠标拖拽创建形状
   - 顶点拖拽编辑
   - 滚轮缩放
   - 右键菜单

3. **辅助系统**
   - 智能辅助线 (对齐)
   - 间距线 (测距)
   - 十字线 (精确定位)
   - 吸附功能

4. **视觉反馈**
   - 悬停高亮
   - 选中高亮
   - 重叠检测
   - 虚影预览

### 5. 形状系统 (shape.py)

**支持的形状类型**:
```python
SHAPE_TYPES = [
    "rectangle",    # 矩形
    "polygon",      # 多边形
    "rotation",     # 旋转矩形 (拖拽式)
    "rotation3",    # 旋转矩形 (三点式)
    "circle",       # 圆形
    "line",         # 直线
    "point",        # 点
    "linestrip",    # 折线
    "rectangle3",   # 三点矩形
]
```

**Shape类结构**:
```python
class Shape:
    # 类变量 (影响所有形状)
    line_color = DEFAULT_LINE_COLOR
    fill_color = DEFAULT_FILL_COLOR
    select_line_color = DEFAULT_SELECT_LINE_COLOR
    highlighting_enabled = False
    alpha_idle = 50
    alpha_highlight = 180
    point_size = 10
    square_size = 10
    line_width = 4
    
    # 实例变量
    def __init__(self, label, score, shape_type, ...):
        self.label = label
        self.score = score
        self.shape_type = shape_type
        self.points = []
        self.group_id = None
        self.description = ""
        self.attributes = {}
        self.is_edited = False
        self.is_session_unlocked = False
        self.selected = False
        self.fill = True
        
    # 核心方法
    def make_path(self):
        """生成QPainterPath用于绘制"""
        
    def contains_point(self, point):
        """判断点是否在形状内"""
        
    def move_by(self, offset):
        """移动形状"""
        
    def move_vertex_by(self, i, offset):
        """移动顶点"""
```

**形状特性**:
- 支持标签、分数、分组ID
- 支持自定义属性
- 支持编辑状态标记
- 支持会话解锁状态
- 支持KIE链接

---

## AI模型系统

### 模型管理器 (model_manager.py)

**规模**: 2102行代码

**职责**:
- 模型生命周期管理
- 模型加载/卸载
- 推理执行
- 缓存管理
- 批量处理

**核心类**:
```python
class ModelManager(QObject):
    # 信号定义
    new_model_status = pyqtSignal(str)
    model_loaded = pyqtSignal(str)
    prediction_started = pyqtSignal()
    prediction_finished = pyqtSignal(AutoLabelingResult, str)
    
    def __init__(self):
        self.loaded_model_config = None
        self.model = None
        self.model_configs = []
        self.lru_cache = LRUCache()
        
    def load_model(self, model_id):
        """加载指定模型"""
        config = self.model_configs[model_id]
        model_class = MODELS[config["type"]]
        self.model = model_class(config, self.on_message)
        
    def predict(self, image, filename):
        """执行预测"""
        # 1. 检查缓存
        cache_key = self._get_cache_key(image, filename)
        if cache_key in self.lru_cache:
            return self.lru_cache[cache_key]
        
        # 2. 执行推理
        result = self.model.predict_shapes(image, filename)
        
        # 3. 缓存结果
        self.lru_cache[cache_key] = result
        
        return result
```

### 模型基类 (model.py)

**Model基类**:
```python
class Model(ABC):
    class Meta:
        required_config_names = []
        widgets = ["button_run"]
        output_modes = {}
        default_output_mode = None
        
    def __init__(self, config_path, on_message):
        self.config = self.load_config(config_path)
        self.on_message = on_message
        
    @abstractmethod
    def predict_shapes(self, image, filename=None):
        """预测形状 - 子类必须实现"""
        pass
        
    def preprocess(self, image):
        """预处理图像"""
        pass
        
    def postprocess(self, outputs):
        """后处理输出"""
        pass
```

### 支持的模型类型

**检测模型** (30+):
- YOLO系列: v5, v6, v7, v8, v9, v10, v11, v12
- YOLO变体: YOLO-NAS, YOLOX, Gold-YOLO, DAMO-YOLO
- DETR系列: RT-DETR, RT-DETRv2, RF-DETR, DFine
- 其他: CLRNet, DocLayout-YOLO

**分割模型** (15+):
- SAM系列: SAM, SAM2, SAM-HQ, Mobile-SAM, Edge-SAM
- EfficientViT-SAM, SAM-Med2D
- YOLO分割: YOLOv5-Seg, YOLOv8-Seg, YOLOv11-Seg

**姿态估计** (5+):
- YOLOv8-Pose, YOLOv11-Pose
- RTMDet-Pose, DWPose

**OCR模型** (3+):
- PPOCRv4 (中文/英文)
- Japan PPOCR (日文)
- License Plate OCR (车牌)

**视觉-语言模型** (7+):
- Grounding-DINO
- Florence2
- RAM, RAM++
- GeCo, OpenVision

**其他模型** (10+):
- 分类: YOLOv5-CLS, YOLOv8-CLS, YOLOv11-CLS
- 背景移除: RMBG v1.4, v2.0
- 深度估计: Depth-Anything, Depth-Anything v2
- 边缘检测: UPN

### 模型配置示例

**YOLOv8配置** (yolov8s.yaml):
```yaml
type: yolov8
name: yolov8s
display_name: YOLOv8s Object Detection
model_path: https://github.com/.../yolov8s.onnx
input_width: 640
input_height: 640
stride: 32
nms_threshold: 0.45
confidence_threshold: 0.25
classes:
  - person
  - bicycle
  - car
  # ... 80 classes
```

**SAM2配置** (sam2_hiera_base.yaml):
```yaml
type: segment_anything_2
name: sam2_hiera_base
display_name: SAM2 Hiera Base
encoder_model_path: path/to/encoder.onnx
decoder_model_path: path/to/decoder.onnx
```

---

## UI组件系统

### 组件分类

**1. 查看器组件** (2个)
- `horizontal_viewer_dialog.py`: 横向滚动看图
- `vertical_viewer_dialog.py`: 垂直滚动看图

**2. 工具对话框** (15+个)
- `rectangle_scale_dialog.py`: 矩形缩放工具
- `smart_guides_dialog.py`: 智能辅助线工具
- `object_manager_dialog.py`: 对象管理器
- `overview_dialog.py`: 统计总览
- `merge_dialog.py`: 合并工具
- `tag_sort_dialog.py`: 标签排序工具
- `label_tool_dialog.py`: 标签工具
- `mask_generator_dialog.py`: 掩膜生成器
- `segmentation_dialog.py`: 分割工具
- `alignment_dialog.py`: 对齐工具
- `color_manager_dialog.py`: 颜色管理器
- `expand_margins_dialog.py`: 边距扩展工具
- `file_filter_dialog.py`: 文件过滤器
- `page_text_dialog.py`: 页面文本工具
- `highlight_settings_dialog.py`: 高亮设置

**3. 设置对话框** (5+个)
- `shortcut_manager_dialog.py`: 快捷键管理器
- `keymap_dialog.py`: 键位映射
- `wheel_settings_dialog.py`: 滚轮设置
- `rectangle3_width_dialog.py`: Rectangle3宽度设置
- `brightness_contrast_dialog.py`: 亮度对比度

**4. 导航组件** (2个)
- `navigator_widget.py`: 导航器小部件
- `navigator_dialog.py`: 导航器对话框

**5. AI相关** (3个)
- `auto_labeling_widget.py`: AI标注控制面板
- `chatbot_dialog.py`: AI聊天机器人
- `vqa_dialog.py`: 视觉问答

**6. 标签管理** (5+个)
- `label_dialog.py`: 标签编辑对话框
- `label_list_widget.py`: 标签列表
- `unique_label_qlist_widget.py`: 唯一标签列表
- `label_filter_combo_box.py`: 标签过滤下拉框
- `label_toggle_shortcut_dialog.py`: 标签切换快捷键

**7. 基础组件** (10+个)
- `canvas.py`: 画布
- `zoom_widget.py`: 缩放控件
- `toolbar.py`: 工具栏
- `popup.py`: 弹出提示
- `searchable_model_dropdown.py`: 可搜索模型下拉框
- `model_dropdown_widget.py`: 模型下拉组件


### 横向/垂直查看器详解

**功能特点**:
1. **图片浏览**
   - 横向/垂直滚动浏览所有图片
   - 缩略图列表预览
   - 快速跳转到指定图片

2. **显示模式**
   - 适应高度/宽度
   - 实际尺寸
   - 自定义缩放

3. **标注显示**
   - 显示/隐藏标注
   - 填充/不填充标注
   - 标注颜色继承主界面

4. **同步功能**
   - 同步滚动模式
   - 与主界面联动
   - 图片切换同步

5. **窗口管理**
   - 最小化自动还原
   - 窗口间切换
   - 刷新功能

**最新优化** (2024-11-24):
```python
# 窗口最小化自动还原
if self.horizontal_viewer_dialog.isMinimized():
    self.horizontal_viewer_dialog.showNormal()
self.horizontal_viewer_dialog.raise_()
self.horizontal_viewer_dialog.activateWindow()

# 打开新文件夹自动刷新
if hasattr(self, 'horizontal_viewer_dialog') and self.horizontal_viewer_dialog:
    self.horizontal_viewer_dialog.update_image_list(self.image_list, self.image_path)
```

### 矩形缩放工具详解

**功能特点**:
1. **缩放操作**
   - 按比例缩放矩形
   - 支持宽度/高度独立缩放
   - 支持累乘模式

2. **批量处理**
   - 当前页面批量缩放
   - 指定页面范围缩放
   - 全部文件缩放

3. **还原功能**
   - 记录缩放历史
   - 支持还原到原始尺寸
   - 显示缩放次数统计

4. **分辨率计算器**
   - 根据目标分辨率计算缩放比例
   - 支持宽度/高度基准
   - 实时预览计算结果

### 智能辅助线系统

**功能特点**:
1. **对齐辅助**
   - 水平/垂直对齐线
   - 边缘对齐检测
   - 中心对齐检测

2. **吸附功能**
   - 可配置吸附距离
   - 独立控制4个方向吸附
   - 粘贴模式独立吸附设置

3. **视觉反馈**
   - 辅助线颜色可配置
   - 透明度可调
   - 显示距离可配置

4. **性能优化**
   - 最大辅助线数量限制
   - 显示距离阈值
   - 只检测可见形状

**配置项**:
```yaml
smart_guides_enabled: true
smart_guides_enable_snap: true
smart_guides_show_horizontal: true
smart_guides_show_vertical: true
smart_guides_line_width: 2.0
smart_guides_line_color: [255, 0, 255]
smart_guides_opacity: 0.8
smart_guides_display_distance: 100
smart_guides_snap_distance: 10
smart_guides_max_lines: 10
smart_guides_snap_left: true
smart_guides_snap_right: true
smart_guides_snap_top: true
smart_guides_snap_bottom: true
```

### 间距线系统

**功能特点**:
1. **距离测量**
   - 矩形间水平/垂直距离
   - 实时显示距离数值
   - 文字背景半透明

2. **显示控制**
   - 可配置显示距离阈值
   - 最大检测矩形数量
   - 仅选中矩形测距模式

3. **视觉样式**
   - 线条颜色可配置
   - 线条宽度可调
   - 文字背景色可配置

**配置项**:
```yaml
spacing_guide_enabled: true
spacing_guide_line_width: 2.0
spacing_guide_line_color: [0, 255, 255]
spacing_guide_text_bg_color: [0, 0, 0, 150]
spacing_guide_opacity: 0.8
spacing_guide_display_distance: 500
spacing_guide_snap_distance: 10
spacing_guide_max_shapes: 0
```

---

## 配置系统

### 主配置文件 (xanylabeling_config.yaml)

**配置分类**:

**1. 基础设置**
```yaml
language: zh_CN              # 界面语言
model_hub: github            # 模型源 (github/modelscope)
auto_save: true              # 自动保存
store_data: false            # 存储图像数据到JSON
keep_prev: false             # 保留上一帧标注
```

**2. 显示设置**
```yaml
show_groups: false           # 显示分组
show_texts: true             # 显示文本
show_labels: true            # 显示标签
show_scores: true            # 显示分数
show_degrees: false          # 显示角度
show_shapes: true            # 显示形状
show_linking: true           # 显示链接
show_attributes: true        # 显示属性
show_order: true             # 显示序号
```

**3. 颜色设置**
```yaml
default_shape_color: [0, 255, 0]
shape_color: auto            # auto/manual/null
manually_edited_color: '#0000FF'  # 手动编辑颜色

traffic_light_colors:
  selected: [255, 0, 0]      # 选中 - 红色
  edited: [0, 255, 0]        # 编辑 - 绿色
  locked: [255, 255, 0]      # 锁定 - 黄色
  unlocked: [0, 0, 255]      # 解锁 - 蓝色
```

**4. 形状样式**
```yaml
shape:
  line_color: [0, 255, 0, 128]
  fill_color: [220, 220, 220, 150]
  vertex_fill_color: [0, 255, 0, 255]
  select_line_color: [255, 255, 255, 255]
  canvas_select_line_color: [255, 0, 0, 255]
  canvas_hover_line_color: [0, 255, 255, 255]
  overlap_color: [255, 165, 0, 120]
  point_size: 10
  square_size: 10
  line_width: 4
  shape_fill_alpha_idle: 50
  shape_fill_alpha_highlight: 180
```

**5. 画布设置**
```yaml
epsilon: 10.0                # 顶点捕捉距离
canvas:
  double_click: close        # 双击行为
  num_backups: 10            # 撤销步数
  
  # 滚轮矩形编辑
  wheel_rectangle_editing:
    adjust_step_h: 1.0
    adjust_step_v: 1.0
    shift_adjust_step_h: 5.0
    shift_adjust_step_v: 5.0
    fast_adjust_step_h: 10.0
    fast_adjust_step_v: 10.0
    scale_step_h: 3.0
    scale_step_v: 3.0
  
  # 十字线
  crosshair:
    show: true
    style: dash              # dash/solid
    width: 2.0
    color: "#00FF00"
    opacity: 0.5
```

**6. 快捷键设置**
```yaml
shortcuts:
  open: Ctrl+I
  save: Ctrl+S
  open_dir: Ctrl+U
  open_next: [D, Ctrl+Shift+D]
  open_prev: [A, Ctrl+Shift+A]
  create_rectangle: [R, Ctrl+R]
  create_polygon: [P, Ctrl+N]
  create_rotation: O
  create_rotation3: H
  delete_polygon: Delete
  copy_polygon: Ctrl+C
  paste_polygon: Ctrl+V
  undo: Ctrl+Z
  zoom_in: [Ctrl++, Ctrl+=]
  zoom_out: Ctrl+-
  # ... 更多快捷键
```

**7. 辅助线设置**
```yaml
# 智能辅助线
smart_guides_enabled: true
smart_guides_enable_snap: true
smart_guides_show_horizontal: true
smart_guides_show_vertical: true
smart_guides_line_width: 2.0
smart_guides_line_color: [255, 0, 255]
smart_guides_opacity: 0.8
smart_guides_display_distance: 100
smart_guides_snap_distance: 10
smart_guides_max_lines: 10

# 间距线
spacing_guide_enabled: true
spacing_guide_line_width: 2.0
spacing_guide_line_color: [0, 255, 255]
spacing_guide_opacity: 0.8
spacing_guide_display_distance: 500
```

**8. 高亮设置**
```yaml
highlight_positive: ""       # 正向高亮标签
highlight_negative: ""       # 负向高亮标签
highlight_mixed_mode: false  # 混合模式
highlight_enabled_by_default: true
locked_labels: ""            # 锁定标签
pin_labels: ""               # 固定标签
no_highlight_labels: ""      # 不高亮标签
```

### 用户配置文件 (~/.YSGxanylabelingrc)

**特点**:
- 自动生成
- 保留用户修改
- 与默认配置合并
- 支持热更新

**配置合并逻辑**:
```python
def _merge_prefer_non_null(target, source):
    """优先保留source中的非空值"""
    if not isinstance(target, dict) or not isinstance(source, dict):
        return source if source is not None else target
    
    result = dict(target)
    for key, src_val in source.items():
        tgt_val = result.get(key)
        if isinstance(tgt_val, dict) and isinstance(src_val, dict):
            result[key] = _merge_prefer_non_null(tgt_val, src_val)
        else:
            result[key] = tgt_val if src_val is None else src_val
    return result
```

---

## 标注形状系统

### 支持的形状类型

**1. Rectangle (矩形)**
- 创建方式: 点击起点 → 拖拽 → 释放
- 编辑方式: 拖拽顶点、边缘、中点
- 应用场景: 水平/垂直目标检测

**2. Polygon (多边形)**
- 创建方式: 连续点击添加顶点 → 双击/Enter完成
- 编辑方式: 拖拽顶点、添加/删除顶点
- 应用场景: 不规则形状分割

**3. Rotation (旋转矩形 - 拖拽式)**
- 创建方式: 点击中心 → 拖拽确定大小和角度
- 编辑方式: 拖拽顶点、旋转手柄
- 应用场景: 倾斜目标检测

**4. Rotation3 (旋转矩形 - 三点式)**
- 创建方式: 点击起点 → 点击确定长度 → 点击确定宽度
- 特点: 自动垂直约束、"工"字参考线
- 应用场景: 精确文本区域标注

**5. Rectangle3 (三点矩形)**
- 创建方式: 三次点击确定矩形
- 特点: 支持自定义宽度
- 应用场景: 特定宽度的矩形标注

**6. Circle (圆形)**
- 创建方式: 点击中心 → 拖拽确定半径
- 编辑方式: 拖拽边缘调整半径
- 应用场景: 圆形目标检测

**7. Line (直线)**
- 创建方式: 点击起点 → 点击终点
- 编辑方式: 拖拽端点
- 应用场景: 车道线、边界线

**8. Point (点)**
- 创建方式: 单击添加点
- 编辑方式: 拖拽点
- 应用场景: 关键点检测、地标检测

**9. LineStrip (折线)**
- 创建方式: 连续点击添加点 → 双击/Enter完成
- 编辑方式: 拖拽点、添加/删除点
- 应用场景: 复杂路径标注

### 形状属性

**基础属性**:
```python
{
    "label": "person",           # 标签名称
    "score": 0.95,               # 置信度分数
    "points": [[x1,y1], [x2,y2]], # 顶点坐标
    "shape_type": "rectangle",   # 形状类型
    "group_id": 1,               # 分组ID
    "description": "描述文本",    # 描述
    "difficult": false,          # 困难样本标记
    "is_edited": true,           # 手动编辑标记
    "flags": {},                 # 标志位
    "attributes": {},            # 自定义属性
    "kie_linking": []            # KIE链接
}
```

### 形状操作

**创建操作**:
- 快捷键创建 (R/P/O/H等)
- 工具栏按钮创建
- 数字快捷键 (0-9可配置)

**编辑操作**:
- 拖拽顶点移动
- 拖拽边缘调整
- 拖拽中点添加顶点
- Backspace删除最后顶点
- Delete删除形状

**批量操作**:
- 全选/反选/取消选择
- 批量删除
- 批量修改标签
- 批量修改分组ID
- 批量修改属性

**高级操作**:
- 形状联合 (Union)
- 形状分组 (Group)
- 形状复制 (Duplicate)
- 形状复制粘贴 (Copy/Paste)

---

## 最新功能特性

### 最新更新

**1. 查看器窗口最小化优化**
- 问题: 窗口最小化后切换仍保持最小化状态
- 解决: 自动检测并还原最小化窗口
- 影响: 横向/垂直查看器、窗口间切换

**2. 查看器自动刷新**
- 问题: 打开新文件夹后查看器不更新
- 解决: 自动调用 `update_image_list()` 刷新
- 影响: 横向/垂直查看器

### 近期功能更新

**1. 文件过滤功能**
- 按标注状态过滤 (已标注/未标注)
- 按手动编辑状态过滤
- 按标签过滤
- 按分组ID过滤

**2. 最近打开文件夹**
- 记录最近打开的文件夹
- 快速访问历史文件夹
- 最多记录10个

**3. 文件夹导入性能优化**
- 批量插入文件列表
- 延迟加载颜色状态
- 后台线程加载
- 显著提升大文件夹加载速度

**4. 手动编辑标记功能**
- 自动标记手动编辑的文件
- 蓝色显示手动编辑文件
- 支持批量清除编辑标记
- 形状级别编辑标记

**5. 红绿灯功能增强**
- 选中状态: 红色
- 编辑状态: 绿色
- 锁定状态: 黄色
- 解锁状态: 蓝色

**6. 高亮常驻功能**
- 正向/负向标签高亮
- 混合模式支持
- 锁定标签保护
- 固定标签功能

**7. 统计总览搜索**
- 标签搜索过滤
- 实时统计更新
- 支持正则表达式

**8. 矩形缩放工具增强**
- 累乘模式
- 还原功能
- 缩放次数统计
- 分辨率计算器
- 动态页面范围

**9. 间距线功能**
- 仅选中矩形测距
- 颜色管理器集成
- 透明度可调

**10. 粘贴模式独立开关**
- 辅助线独立控制
- 吸附独立控制
- 虚影透明度可调


**11. Rotation3模式增强**
- 十字线自动切换
- 旋转十字线
- 角度显示
- 自定义鼠标指针

**12. 边距扩展工具**
- 批量扩展矩形边距
- 支持四个方向独立设置
- 页面范围选择
- 实时预览

**13. 标签工具功能**
- 双色标签转换
- 批量标签修改
- 标签还原功能

**14. 十字线功能增强**
- 快捷键切换
- 透明度隔离
- 样式可配置 (实线/虚线)

**15. 导航窗修复**
- 修复显示问题
- 优化性能
- 改进交互

---

## 开发指南

### 环境搭建

**1. 克隆项目**
```bash
git clone https://github.com/your-repo/X-AnyLabeling-Hmogai1123.git
cd X-AnyLabeling-Hmogai1123/anylabeling
```

**2. 创建虚拟环境**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

**3. 安装依赖**
```bash
# CPU版本
pip install -r requirements.txt

# GPU版本 (推荐)
pip install -r requirements-gpu.txt

# macOS版本
pip install -r requirements-macos.txt
```

**4. 运行应用**
```bash
python app.py
```

### 添加新模型

**步骤1: 创建模型类**

文件: `services/auto_labeling/your_model.py`

```python
from typing import List
from .model import Model
from .types import AutoLabelingResult

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
            "rectangle": "Rectangle",
        }
        default_output_mode = "rectangle"
    
    def __init__(self, config_path, on_message):
        super().__init__(config_path, on_message)
        # 加载模型
        self.net = self.load_onnx_model(self.config["model_path"])
    
    def predict_shapes(self, image, filename=None):
        """执行预测"""
        # 1. 预处理
        input_tensor = self.preprocess(image)
        
        # 2. 推理
        outputs = self.net.run(None, {self.net.get_inputs()[0].name: input_tensor})
        
        # 3. 后处理
        shapes = self.postprocess(outputs, image.shape)
        
        # 4. 返回结果
        return AutoLabelingResult(shapes, replace=True)
    
    def preprocess(self, image):
        """预处理图像"""
        # 实现预处理逻辑
        pass
    
    def postprocess(self, outputs, image_shape):
        """后处理输出"""
        # 实现后处理逻辑
        pass
```

**步骤2: 注册模型**

文件: `services/auto_labeling/__init__.py`

```python
from .your_model import YourModel

MODELS = {
    # ... 现有模型
    "your_model": YourModel,
}
```

**步骤3: 创建配置文件**

文件: `configs/auto_labeling/your_model.yaml`

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

**步骤4: 测试模型**
1. 启动应用
2. 选择模型: "Your Model v1"
3. 加载图像
4. 点击"运行 (i)"
5. 验证结果

### 添加新UI组件

**步骤1: 创建组件类**

文件: `views/labeling/widgets/your_widget.py`

```python
from PyQt5 import QtWidgets, QtCore

class YourWidget(QtWidgets.QDialog):
    # 定义信号
    value_changed = QtCore.pyqtSignal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Your Widget")
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QtWidgets.QVBoxLayout()
        
        # 添加控件
        self.label = QtWidgets.QLabel("Label:")
        self.input = QtWidgets.QLineEdit()
        self.button = QtWidgets.QPushButton("OK")
        
        layout.addWidget(self.label)
        layout.addWidget(self.input)
        layout.addWidget(self.button)
        
        self.setLayout(layout)
        
        # 连接信号
        self.button.clicked.connect(self.on_ok_clicked)
    
    def on_ok_clicked(self):
        """处理OK按钮点击"""
        value = self.input.text()
        self.value_changed.emit(value)
        self.accept()
```

**步骤2: 集成到主界面**

文件: `views/labeling/label_widget.py`

```python
from .widgets.your_widget import YourWidget

class LabelingWidget(QtWidgets.QWidget):
    def __init__(self, ...):
        # ...
        self.your_widget = None
    
    def open_your_widget(self):
        """打开你的组件"""
        if not self.your_widget:
            self.your_widget = YourWidget(self)
            self.your_widget.value_changed.connect(self.on_value_changed)
        
        self.your_widget.show()
    
    def on_value_changed(self, value):
        """处理值变化"""
        print(f"Value changed: {value}")
```

**步骤3: 添加菜单项/工具栏按钮**

```python
# 创建动作
your_action = action(
    self.tr("Your Widget"),
    self.open_your_widget,
    "icon_name",
    "Ctrl+Y",
    tip=self.tr("Open your widget"),
)

# 添加到菜单
tools_menu.addAction(your_action)

# 添加到工具栏
toolbar.addAction(your_action)
```

### 代码规范

**1. Python代码风格**
- 遵循 PEP 8
- 使用4空格缩进
- 类名使用 PascalCase
- 函数名使用 snake_case
- 常量使用 UPPER_CASE

**2. 文档字符串**
```python
def function_name(param1, param2):
    """
    简短描述
    
    详细描述 (可选)
    
    Args:
        param1 (type): 参数1描述
        param2 (type): 参数2描述
    
    Returns:
        type: 返回值描述
    
    Raises:
        ExceptionType: 异常描述
    """
    pass
```

**3. 类型注解**
```python
from typing import List, Dict, Optional

def process_shapes(shapes: List[Shape]) -> Dict[str, int]:
    """处理形状列表"""
    pass

def get_config(key: str) -> Optional[str]:
    """获取配置值"""
    pass
```

**4. 信号命名**
```python
class MyWidget(QtWidgets.QWidget):
    # 信号使用 snake_case
    value_changed = QtCore.pyqtSignal(object)
    item_selected = QtCore.pyqtSignal(str)
    operation_finished = QtCore.pyqtSignal()
```

**5. 配置文件**
- 使用 YAML 格式
- 使用小写字母和下划线
- 添加注释说明
- 保持层次结构清晰

### 调试技巧

**1. 日志输出**
```python
from anylabeling.views.labeling.logger import logger

logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

**2. 设置日志级别**
```bash
python app.py --logger-level debug
```

**3. 使用断点**
```python
import pdb; pdb.set_trace()  # Python调试器
```

**4. PyQt调试**
```python
# 打印对象信息
print(f"Object: {obj}")
print(f"Type: {type(obj)}")
print(f"Dir: {dir(obj)}")

# 检查信号连接
print(f"Receivers: {obj.receivers(obj.signal_name)}")
```

### 性能优化

**1. 图像加载优化**
- 使用线程池异步加载
- 实现LRU缓存
- 按需加载可见图像

**2. UI渲染优化**
- 使用 `blockSignals()` 批量操作
- 延迟更新UI
- 使用 `QTimer.singleShot()` 异步更新

**3. 模型推理优化**
- 使用GPU加速
- 批量处理
- 结果缓存

**4. 内存管理**
- 及时释放不用的对象
- 使用弱引用
- 定期清理缓存

---

## 部署与运行

### 开发环境运行

**直接运行**:
```bash
cd anylabeling
python app.py
```

**带参数运行**:
```bash
# 打开指定文件
python app.py image.jpg

# 打开文件夹
python app.py /path/to/folder

# 指定输出目录
python app.py --output /path/to/output

# 指定配置文件
python app.py --config custom_config.yaml

# 设置日志级别
python app.py --logger-level debug

# 重置配置
python app.py --reset-config

# 禁用自动更新检查
python app.py --no-auto-update-check
```

### 打包发布

**使用PyInstaller**:

```bash
# 安装PyInstaller
pip install pyinstaller

# 打包为单个可执行文件
pyinstaller --onefile --windowed \
    --name X-AnyLabeling \
    --icon resources/images/icon.ico \
    --add-data "configs:configs" \
    --add-data "resources:resources" \
    app.py

# 打包为文件夹
pyinstaller --onedir --windowed \
    --name X-AnyLabeling \
    --icon resources/images/icon.ico \
    --add-data "configs:configs" \
    --add-data "resources:resources" \
    app.py
```

**Windows打包**:
```bash
pyinstaller X-AnyLabeling.spec
```

**macOS打包**:
```bash
pyinstaller --windowed \
    --name X-AnyLabeling \
    --icon resources/images/icon.icns \
    --add-data "configs:configs" \
    --add-data "resources:resources" \
    app.py
```

**Linux打包**:
```bash
pyinstaller --onefile \
    --name X-AnyLabeling \
    --add-data "configs:configs" \
    --add-data "resources:resources" \
    app.py
```

### 系统要求

**最低要求**:
- 操作系统: Windows 10/11, macOS 10.15+, Ubuntu 20.04+
- Python: 3.8+
- 内存: 8GB RAM
- 硬盘: 2GB 可用空间

**推荐配置**:
- 操作系统: Windows 11, macOS 12+, Ubuntu 22.04+
- Python: 3.10+
- 内存: 16GB RAM
- 显卡: NVIDIA GPU (支持CUDA)
- 硬盘: 10GB 可用空间 (包含模型文件)

### 常见问题

**Q1: 模型加载失败**
- 检查模型文件路径
- 检查ONNX Runtime版本
- 查看日志错误信息

**Q2: 界面显示异常**
- 检查PyQt5版本
- 更新显卡驱动
- 尝试禁用硬件加速

**Q3: 性能问题**
- 使用GPU版本
- 减少同时加载的图像数量
- 降低图像分辨率

**Q4: 配置不生效**
- 检查配置文件路径
- 删除 `~/.YSGxanylabelingrc` 重新生成
- 使用 `--reset-config` 重置

**Q5: 快捷键冲突**
- 打开快捷键管理器
- 修改冲突的快捷键
- 保存配置

---

## 附录

### 快捷键列表

**文件操作**:
- `Ctrl+I`: 打开图像
- `Ctrl+U`: 打开文件夹
- `Ctrl+S`: 保存
- `Ctrl+Shift+S`: 另存为
- `Ctrl+W`: 关闭
- `Ctrl+Q`: 退出

**导航**:
- `D` / `Ctrl+Shift+D`: 下一张
- `A` / `Ctrl+Shift+A`: 上一张
- `Ctrl+Shift+D`: 下一张未标注
- `Ctrl+Shift+A`: 上一张未标注

**创建形状**:
- `R` / `Ctrl+R`: 创建矩形
- `P` / `Ctrl+N`: 创建多边形
- `O`: 创建旋转矩形
- `H`: 创建rotation3

**编辑操作**:
- `Ctrl+C`: 复制形状
- `Ctrl+V`: 粘贴形状
- `Ctrl+D`: 复制形状
- `Delete`: 删除形状
- `Ctrl+Z`: 撤销
- `Backspace`: 删除最后顶点
- `Ctrl+E`: 编辑标签
- `Ctrl+J`: 编辑形状

**视图操作**:
- `Ctrl+F`: 适应窗口
- `Ctrl+Shift+F`: 适应宽度
- `Ctrl++` / `Ctrl+=`: 放大
- `Ctrl+-`: 缩小
- `Ctrl+0`: 实际尺寸
- `Ctrl+H`: 隐藏/显示形状

**选择操作**:
- `Ctrl+A`: 全选 (画布)
- `Alt+T`: 全选形状
- `Alt+S`: 取消选择
- `Alt+I`: 反选形状
- `Alt+F`: 切换高亮

**工具**:
- `Ctrl+T`: 对象管理器
- `Ctrl+G`: 统计总览
- `Ctrl+M`: 自动运行
- `Ctrl+Shift+A`: AI自动标注
- `Ctrl+Shift+M`: 边距扩展
- `Ctrl+Shift+X`: 分割工具
- `Ctrl+Shift+R`: 对齐工具
- `Ctrl+Shift+H`: 切换十字线
- `Alt+Z`: 显示导航器

**其他**:
- `G`: 分组选中形状
- `U`: 取消分组
- `M`: 联合选中形状
- `S`: 隐藏选中形状
- `W`: 显示隐藏形状
- `N`: 循环标签
- `Space`: 编辑标签

### 支持的文件格式

**图像格式**:
- JPEG (.jpg, .jpeg)
- PNG (.png)
- BMP (.bmp)
- TIFF (.tif, .tiff)
- WebP (.webp)

**标注格式**:
- JSON (X-AnyLabeling格式)
- COCO JSON
- YOLO TXT
- Pascal VOC XML
- LabelMe JSON
- DOTA TXT

**导出格式**:
- COCO JSON
- YOLO TXT
- Pascal VOC XML
- LabelMe JSON
- DOTA TXT
- MASK PNG

### 项目链接

- **GitHub**: https://github.com/CVHub520/X-AnyLabeling
- **文档**: 项目 `docs/` 目录
- **问题反馈**: GitHub Issues

### 更新日志

**v3.2.2**
- ✅ 修复查看器窗口最小化问题
- ✅ 添加查看器自动刷新功能
- ✅ 优化窗口切换体验

**v3.2.1**
- ✅ 添加文件过滤功能
- ✅ 添加最近打开文件夹
- ✅ 优化文件夹导入性能
- ✅ 添加手动编辑标记
- ✅ 增强红绿灯功能
- ✅ 添加高亮常驻功能

**v3.2.0**
- ✅ 添加rotation3模式
- ✅ 添加智能辅助线
- ✅ 添加间距线功能
- ✅ 添加矩形缩放工具
- ✅ 添加横向/垂直查看器

---

## 结语

X-AnyLabeling 是一个功能强大、高度可扩展的图像标注工具。本文档详细介绍了项目的架构、核心模块、配置系统和开发指南。

如有问题或建议，欢迎通过 GitHub Issues 反馈。

**文档维护**: Hmogai_1123

---

**文档结束**
