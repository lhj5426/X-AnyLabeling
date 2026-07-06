# X-AnyLabeling Hmogai 定制版 分析报告

> 分析路径：`D:\Ddown\X-AnyLabeling-Hmogai260702`
> 分析时间：2026-07-03

---

## 一、项目概览

这是 **X-AnyLabeling v3.2.2** 的深度定制分支，重命名为 **`Hmogai_260702_X-AnyLabeling`**，专门面向 **漫画/图像 OCR 标注与翻译** 工作流。

| 项目属性 | 值 |
|:---|:---|
| 基础版本 | X-AnyLabeling v3.2.2 (2025-08-31) |
| 应用名称 | `Hmogai_260702_X-AnyLabeling` |
| 技术栈 | Python 3.10+ / PyQt5 / ONNX Runtime / PyTorch (CUDA 11.8) |
| 推理设备 | GPU 优先 |
| 许可证 | GPL-3.0 (上游) + 商业授权约束 |
| 核心代码量 | shape.py (1,418行) + canvas.py (10,466行) + label_widget.py (19,449行) = **31,333 行** |

---

## 二、定制内容全景

### 2.1 漫画专用标签体系

`biaoqian.txt` 定义了 6 类标注标签，完全围绕漫画文字区域设计：

```
balloon       — 气泡（对话框）
qipao         — 气泡（另一种）
shuqing       — 竖斜（竖排倾斜文字）
changfangtiao — 长方条（条状文字区域）
hengxie       — 横斜（横排倾斜文字）
other         — 其他
```

**数字快捷键映射**（从配置文件提取）：

| 快捷键 | 标签 | 绘制模式 |
|:---:|:---|:---|
| 1 | qipao | rectangle（矩形） |
| 2 | balloon | rectangle |
| 3 | changfangtiao | rectangle |
| 4 | other | rectangle |
| 5 | shuqing | **rotation3**（三次点击旋转矩形） |
| 6 | hengxie | **rotation3** |
| 7 | other | **rotation3** |

---

### 2.2 自定义形状类型：rotation3 / rectangle3

原版 X-AnyLabeling 支持 `rectangle`、`rotation`（旋转框）、`polygon` 等形状。此定制版新增：

- **`rotation3`** — 三次点击创建旋转矩形（快捷键 H），区别于原版的两点+拖拽旋转模式
- **`rectangle3`** — 关联矩形类型，配合 `rectangle3_width_dialog.py` 控制宽度
- 在 `shape.py` 中完整实现了 rotation3 的创建、渲染、碰撞检测、安全边界逻辑

相关文件：
- `anylabeling/views/labeling/shape.py` — 形状定义与渲染
- `anylabeling/views/labeling/widgets/rectangle3_width_dialog.py` — 宽度设置对话框

---

### 2.3 OCR 文本替换系统

**核心文件**：`ocr_text_replace.py` + `ocr_text_replace.json`

这是一个完整的 OCR 后处理替换引擎：

- **表格化 UI**：标签 | 关键词 | 替换为 | 正则开关 | 大小写开关
- **按标签过滤**：替换规则绑定到特定标签类型（如只对 `balloon` 标签的 OCR 结果替换）
- **正则支持**：每条规则可独立开启正则模式
- **外部 JSON 持久化**：规则存储在项目根目录 `ocr_text_replace.json`，关闭对话框时自动保存
- **搜索过滤**：支持按标签/关键词/替换文本搜索规则
- **颜色标记**：标签列背景色与软件内标签颜色同步

当前规则示例（`ocr_text_replace.json`）：
```json
[{"label": "OCR", "keyword": "耳", "sub": "傻逼", "use_reg": false, "case_sens": false}]
```

---

### 2.4 字符渲染规则系统

**核心文件**：`char_render_dialog.py` + `char_render_rules.json`

针对 OCR 识别后的文字，按字符级别控制渲染：

- 每个字符可独立设置：**旋转角度**、**X 偏移**、**Y 偏移**、**字间距**
- 按标签类型分组（balloon / qipao / shuqing / changfangtiao / hengxie）
- 用于在画布上精确叠加翻译/替换文字

当前规则示例：
```json
[
  {"char": "傻", "label": "OCR", "rotate": 90, "offset_x": 0, "offset_y": 0, "spacing": 0},
  {"char": "逼", "label": "OCR", "rotate": 0, "offset_x": 15, "offset_y": 0, "spacing": 0}
]
```

---

### 2.5 秒级转发器（fast_send）

**核心文件**：`anylabeling/fast_send.py`

Windows 专用的单实例通信机制：

- 使用 `EnumWindows` + `SendMessage(WM_COPYDATA)` 向已运行的主窗口发送图片路径
- 精确匹配窗口标题（`Hmogai_260702_X-AnyLabeling`）+ 窗口类名（Qt 前缀且非 Dialog）
- 解决了多子窗口（横向/垂直/瀑布流 viewer）打开时 `FindWindowW` 找错窗口的问题
- 配合 Directory Opus 等看图软件实现「看图切换 → 一键发送到标注工具」

批处理入口：
- `yolov26环境C盘DirectoryOpus看图切换用.bat` — 从 Directory Opus 发送图片路径

---

### 2.6 个性化一键脚本

| 脚本 | 功能 |
|:---|:---|
| `根目录下双击一键设置常高亮等个性化X-AnyLabeling.py` | shape 默认选中+填充、移动速度 0.5、旋转步长微调、移除所有 ToolTip |
| `根目录下双击一键设置但是不设置高亮等个性化X-AnyLabeling.py` | 同上但不设常高亮 |
| `一键修GPU和日期号.bat` | 从文件夹名提取日期写入 `__appname__`，强制 GPU 模式 |
| `检测是否能运行GPU.py` | GPU 可用性检测 |
| `运行自检环境版本GPU是否可用.py` | 环境版本自检 |

具体修改值：
- `MOVE_SPEED` = 0.5（原版 1.0）
- `LARGE_ROTATION_INCREMENT` = 0.0087（约 0.5°）
- `SMALL_ROTATION_INCREMENT` = 0.001745（约 0.1°）
- `self.selected` = True（默认选中）
- `self.fill` = True（默认填充）

---

### 2.7 大量自定义 Widget（对比上游新增/增强）

以下 widget 在标准 X-AnyLabeling 中**不存在或大幅增强**：

**标注辅助工具**：
- `alignment_dialog.py` — 对齐工具（角度标签 shuqing/hengxie 专用）
- `angle_correction_dialog.py` — 角度校正
- `rectangle3_width_dialog.py` — rotation3 宽度设置
- `rectangle_scale_dialog.py` — 矩形缩放
- `rectangle_spacing_guide.py` — 矩形间距引导
- `expand_margins_dialog.py` — 边距扩展
- `safety_border_settings_dialog.py` — 安全边框设置
- `smart_guides_dialog.py` — 智能参考线
- `dual_color_tool_dialog.py` — 双色工具
- `containment_detection_dialog.py` — 包含检测
- `region_batch_delete_dialog.py` — 区域批量删除
- `merge_dialog.py` — 合并

**标签管理**：
- `label_order_dialog.py` — 标签排序
- `label_sync_dialog.py` — 标签同步
- `label_tool_dialog.py` — 标签工具
- `label_selection_dialog.py` — 标签选择
- `label_toggle_shortcut_dialog.py` — 标签切换快捷键
- `tag_sort_dialog.py` — 标签排序
- `filter_classes_dialog.py` — 类别过滤
- `color_manager_dialog.py` — 颜色管理器
- `object_manager_dialog.py` — 对象管理器

**视图/浏览**：
- `horizontal_viewer_dialog.py` — 水平查看器
- `vertical_viewer_dialog.py` — 垂直查看器
- `thumbnail_viewer_dialog.py` — 缩略图查看器
- `overview_dialog.py` — 总览
- `animated_webp_support.py` / `animated_webp_view.py` — 动画 WebP 支持
- `page_text_dialog.py` — 页面文本

**画布增强**：
- `crosshair_settings_dialog.py` — 十字光标设置
- `magnifier_settings_dialog.py` — 放大镜设置
- `highlight_settings_dialog.py` — 高亮设置
- `wheel_settings_dialog.py` — 滚轮设置（矩形滚轮编辑）
- `brightness_contrast_dialog.py` — 亮度对比度
- `brush` 画笔工具（遮罩编辑）
- `zoom_widget.py` — 缩放控件
- `navigator_widget.py` — 导航器

**OCR/文本**：
- `char_render_dialog.py` — 字符渲染规则
- `text_split_dialog.py` — 文本拆分
- `ocr_text_replace.py` — OCR 文本替换

**其他**：
- `file_dialog_preview.py` — 文件对话框预览
- `file_filter_dialog.py` — 文件过滤
- `keymap_dialog.py` — 键位映射
- `shortcut_manager_dialog.py` — 快捷键管理
- `traffic_light_dialog.py` — 红绿灯对话框
- `image_category_manager_dialog.py` — 图片类别管理
- `mask_generator_dialog.py` — 遮罩生成器
- `segmentation_dialog.py` — 分割对话框

---

### 2.8 AI 模型支持

**内置 Manga OCR 模型**（`models/manga_ocr/`）：
- `detect-20241225.ckpt` (294 MB) — 文字检测模型
- `ocr_ar_48px.ckpt` (195 MB) — OCR 识别模型
- `alphabet-all-v7.txt` — 字符集（186 KB）

**YOLO 系列模型支持**（`services/auto_labeling/`）：
- 标准：YOLOv5/6/7/8/9/10/11/12
- **定制新增：YOLO26**（`yolo26.py`, `yolo26_obb.py`, `yolo26_pose.py`, `yolo26_seg.py`）— 上游不存在
- 其他：YOLOX, YOLO-NAS, D-FINE, RT-DETR, RF-DETR, Gold_YOLO, DAMO-YOLO
- 分割：SAM, SAM-HQ, SAM-Med2D, EdgeSAM, EfficientViT-SAM, MobileSAM, SAM2
- OCR：PP-OCR v4/v6, Manga OCR
- VLM：Florence2
- 其他：Depth Anything, RMBG, RAM, CLRNet, GeCO, Grounding DINO 等

---

### 2.9 环境配置

**Conda 环境方案**：
- `xanylabeling` — 标准环境
- `yolov26` — YOLO26 专用环境（含 PyTorch 2.7.1 + CUDA 11.8）

**关键依赖**（`my_env_list.txt`）：
```
torch==2.7.1+cu118
torchvision==0.22.1+cu118
onnxruntime-gpu==1.18.1
ultralytics (最新)
PyQt5==5.15.7
numpy==1.26.4
```

**批处理启动方案**：
- `xanylabeling环境C盘.bat` / `yolov26环境C盘.bat` — 带 CMD 窗口启动
- `xanylabeling环境C盘无CMD.bat` / `yolov26环境C盘无CMD.bat` — 无 CMD 后台启动
- `水平1234 YOLOV11环境.bat` — 加载独立配置文件启动

---

## 三、架构分析

### 3.1 目录结构

```
X-AnyLabeling-Hmogai260702/
├── anylabeling/                    # 主包
│   ├── app.py                      # 入口
│   ├── app_info.py                 # 版本/名称信息
│   ├── fast_send.py                # [定制] 秒级转发器
│   ├── configs/                    # 配置
│   ├── resources/                  # 资源（图标/翻译）
│   ├── services/
│   │   ├── auto_labeling/          # AI 推理引擎（60+ 模型）
│   │   ├── auto_training/          # 自动训练（Ultralytics）
│   │   └── text_splitter/          # 文本拆分
│   └── views/
│       ├── labeling/               # 标注核心
│       │   ├── label_widget.py     # 主窗口逻辑 (19,449行)
│       │   ├── shape.py            # 形状定义 (1,418行) [定制: rotation3]
│       │   ├── label_converter.py  # 标签格式转换
│       │   ├── label_file.py       # 标签文件读写
│       │   ├── ocr_text_replace.py # [定制] OCR替换
│       │   └── widgets/
│       │       ├── canvas.py       # 画布 (10,466行) [大幅定制]
│       │       └── ...（60+ widget）
│       ├── mainwindow_widgets/
│       └── training/               # 训练界面
├── models/manga_ocr/               # [定制] 漫画OCR模型
├── tools/onnx_exporter/            # ONNX 导出工具
├── examples/                       # 示例
├── docs/                           # 文档
├── *.bat / *.py                    # [定制] 启动/个性化脚本
├── *.json                          # [定制] OCR替换/字符渲染规则
├── *.ini / *.rc                    # [定制] 配置文件
└── my_env_list*.txt                # [定制] 环境依赖快照
```

### 3.2 数据流

```
图片输入（Directory Opus / 文件对话框）
  ↓ fast_send.py (WM_COPYDATA) 或直接打开
主窗口 (label_widget.py)
  ↓ AI 自动标注
模型推理 (YOLO26 / Manga OCR / SAM / ...)
  ↓ 检测文字区域 + OCR识别
画布渲染 (canvas.py)
  ↓ shape.py (rotation3 / rectangle)
标注数据 (JSON)
  ↓ ocr_text_replace.py (文本替换)
  ↓ char_render_rules (字符渲染)
最终标注文件 + 画布叠加文字
```

---

## 四、与上游差异总结

| 维度 | 上游 X-AnyLabeling v3.2.2 | Hmogai 定制版 |
|:---|:---|:---|
| 应用名称 | X-AnyLabeling | Hmogai_260702_X-AnyLabeling |
| 标签体系 | 通用（可自定义） | 漫画专用 6 类（balloon/qipao/shuqing/...） |
| 形状类型 | rectangle/rotation/polygon/... | + **rotation3** / **rectangle3** |
| OCR 后处理 | 无 | **完整替换引擎**（正则+标签过滤+外部JSON） |
| 字符渲染 | 无 | **逐字符渲染规则**（旋转/偏移/间距） |
| 单实例通信 | 标准方式 | **WM_COPYDATA 秒级转发**（EnumWindows 精确定位） |
| 查看器 | 基本缩略图 | **水平/垂直/瀑布流三视图** + 动画WebP |
| 画布交互 | 标准 | **滚轮编辑矩形** + 十字光标 + 放大镜 + PS式平移 |
| YOLO 版本 | 到 YOLO12 | + **YOLO26**（4个变体） |
| Manga OCR | 无内置模型 | **内置检测+识别模型** (500MB) |
| 个性化 | 手动配置 | **一键脚本**（高亮/速度/旋转步长/ToolTip） |
| Widget 数量 | ~30 | **60+**（新增 30+ 定制对话框） |
| 配置文件 | .xanylabelingrc | + ini 三件套（config/dock/window）+ 多套 .rc |

---

## 五、代码质量与风险

### 优点
1. **功能极其丰富**：覆盖了漫画标注从检测→识别→替换→渲染的完整链路
2. **工程化程度高**：一键脚本、多环境管理、外部 JSON 配置解耦
3. **性能优化**：GPU 优先、秒级转发、滚轮微调
4. **用户友好**：数字快捷键、颜色标记、搜索过滤

### 风险点
1. **单文件过大**：`label_widget.py` 19,449 行、`canvas.py` 10,466 行，维护困难
2. **无版本管理**：目录下无 `.git`，定制修改无 diff 追踪，升级上游困难
3. **编码混乱**：`一键修GPU和日期号.bat` 内中文字符在 GBK→UTF-8 转换中出现乱码
4. **硬编码路径**：批处理中含 `C:\ProgramData\miniconda3\pythonw.exe` 等绝对路径
5. **规则文件含敏感内容**：`ocr_text_replace.json` 和 `char_render_rules.json` 包含不雅词汇
6. **YOLO26 来源不明**：非 Ultralytics 官方版本，需确认模型来源与兼容性
7. **许可证合规**：GPL-3.0 要求开源修改，商业使用需授权

---

## 六、改进建议

1. **引入 Git**：初始化仓库并 fork 上游，用分支管理定制修改，方便跟踪与合并上游更新
2. **拆分大文件**：将 `label_widget.py` 和 `canvas.py` 按功能模块拆分
3. **修复编码**：批处理文件统一 UTF-8 BOM 或使用 Python 脚本替代
4. **配置外部化**：将硬编码路径（miniconda 路径、配置路径）提取为环境变量
5. **清理敏感数据**：移除示例 JSON 中的不雅词汇，改用中性示例
6. **文档化定制**：记录所有相对上游的修改点，便于版本升级时 rebase
7. **模型管理**：将 manga_ocr 模型路径配置化，避免打包时体积过大
8. **单元测试**：为 rotation3 形状、OCR 替换引擎、fast_send 等核心定制编写测试
