<div align="center">
  <p>
    <a href="https://github.com/CVHub520/X-AnyLabeling/" target="_blank">
      <img alt="X-AnyLabeling" height="200px" src="https://github.com/user-attachments/assets/0714a182-92bd-4b47-b48d-1c5d7c225176"></a>
  </p>


X-AnyLabeling 魔改版 基于250903更新的源码进行魔改

由淫书馆TG频道 https://t.me/yinshuguan 

专门为

开源

https://github.com/dmMaze/BallonsTranslator

和付费

https://www.basiccat.org/zh/imagetrans/

漫画翻译工具 的前置检测而魔改的版本

漫画翻译的所有的前置检测任务都交给魔改版X-AnyLabeling

真正的漫画工具只负责OCR 翻译 嵌字 

(原版 https://github.com/CVHub520/X-AnyLabeling 已支持使用PPV5ocr 懒得移植过来 魔改版 原版双持也不是不可以)

因为使用AI编写代码 故 无法与主分支合并

本魔改服务于仅服务于 自训练模型 使用

https://github.com/lhj5426/YSG

不同类型可以分不同颜色的,你行吗

看不清是可以加深颜色的,你可以吗

每个矩形都是可以微调的,你做的到吗

可以加载不同的检测模型,你来的了吗

识别完是可以直接训练的,你能吗


魔改内容如下

1.标签区域增加交互

<img width="1538" height="851" alt="image" src="https://github.com/user-attachments/assets/e023c531-8c9e-42ea-a946-6e33ae168337" />

2.标签栏增加全选 反选 高亮 

<img width="825" height="865" alt="image" src="https://github.com/user-attachments/assets/58511b1d-9c2a-4b83-9b25-65a33c939933" />

视频演示

https://github.com/user-attachments/assets/643ec4f8-500f-4962-b9d1-8e9986331b8a

方便相邻很近的图形进行交叉微调

3.旋转矩形增加 鼠标滚轮 微调边界 （截至250910官方版仅支持水平矩形微调边界）

https://github.com/user-attachments/assets/eae1de87-9bf4-4f9e-bce3-354e74764a91

4.增加PS一样的导航器 方便处理 大尺寸图片 和 垂直图片  （提交代码 250910 官方仓库正式支持 导航器 但是去掉了 页码显示）
官方这个页码只在右下角显示 而且动不动就消失 不直观 所以我才在导航器里弄了个页数显示 毕竟眼睛一直要看导航器 可以更方便的查看页数

https://github.com/user-attachments/assets/e68ca7ea-906a-49df-90f8-3ca81b3ffb86

5.添加相同标签重叠自定义颜色 增加辨识度 特别经常复制标签的时候 重叠在一起根本看不出来复制没有 魔改之后好了 重叠颜色醒目方便区分

https://github.com/user-attachments/assets/aa42d52c-74eb-4a81-b2aa-a9c310e5e327

而且文字紧凑 相同标签重叠还可以更直观的查看重叠距离 方便微调

<img width="1014" height="675" alt="image" src="https://github.com/user-attachments/assets/bd6cec61-a89d-4843-bd6b-318352735a98" />


6.增加鼠标 悬浮 和点击时  图形边框的颜色自定义 官方在高亮的时候全是白框 
你点击也是白框根本不好区分
魔改之后就是高亮也可以正常区分 点击和 悬浮的颜色不再全是单一的白色 

https://github.com/user-attachments/assets/909e8f64-954a-466e-9d4c-e392386deb12

7.修改标签显示方向 

<img width="500" height="279" alt="image" src="https://github.com/user-attachments/assets/abacd92a-ca54-4ffa-8a77-18dc9b4c319f" />

官方这个 标签等 显示的 朝内 说真的 碍眼 

<img width="552" height="323" alt="image" src="https://github.com/user-attachments/assets/0dca0df3-9288-4d21-aaaf-e62c15110d77" />

魔改成朝外

8.增加序号 查看 总序号 和 单一标签序号

<img width="774" height="791" alt="image" src="https://github.com/user-attachments/assets/93156df6-6cdb-4057-810d-e4fe3f3d3b4d" />

并且 主界面也增加序号显示

<img width="1043" height="815" alt="image" src="https://github.com/user-attachments/assets/7bdbbf15-aaf6-4f95-9401-a03886b89bde" />

9.修改序号 在修改标签窗口增加修改序号功能 能显示不能修改 那不能啊

https://github.com/user-attachments/assets/908a5987-2c10-4bc3-a5aa-77e6969cb170

10.增加标签页面管理 排序功能 排序和修改序号还是有区别的

https://github.com/user-attachments/assets/6223e8e2-fbee-4036-997e-48cde9284345

11.增加扩展缩放 微调功能 

https://github.com/user-attachments/assets/bc4b4669-b713-464c-9cb4-f9f694e81196

同样对旋转矩形也有效

https://github.com/user-attachments/assets/a13697cb-8030-4035-aba8-bf939b6de90e

12.可自定义鼠标 悬浮到矩形 和移动矩形的 指针样式 我不喜欢系统的小手 改成自定义

https://github.com/user-attachments/assets/c5c79242-eee2-4039-9379-2743fb202082

13.修复搜索功能 官方原版 搜索框内搜索完图片 并跳转之后 清空搜索框 图片无法继续接着当前的页数位置继续往下翻页

魔改之后 可以在搜索框清空后继续连续翻页 并且增加了清空搜索框的X

https://github.com/user-attachments/assets/c64d54bc-d89d-4c5c-91c6-9098d8f01e9e

14.设置独立配置 在魔改版配置文件里增加很多新的设置项目在启动官方的时候会被覆盖

为了防止被覆盖 决定区分独立配置可以和官方共存互不影响

<img width="460" height="230" alt="image" src="https://github.com/user-attachments/assets/f0c7a957-fb7f-4413-821a-6d13d0275de3" />

<img width="909" height="285" alt="image" src="https://github.com/user-attachments/assets/7ce58294-3ca7-4db3-b53e-7e6a6f7734ee" />


15.在6.增加鼠标 悬浮 和点击时  图形边框的颜色自定义 的基础上 再增加 这个自定义边颜色 的 线条粗细的自定义

在不点击 不选中状态下 基础的矩形边框线条不变的前提下 增加 选中 和悬浮 的彩色边框厚度 大大增强视觉辨识度

本来做数据标注就是一件非常累眼睛的事情 对自己的眼睛好点 

https://github.com/user-attachments/assets/eb63145f-b88e-4945-9ad6-86a7cb14fd60

16.修改鼠标在矩形内向四周扩展改为横向扩展

因为主要为了https://github.com/lhj5426/YSG 的魔改项目

为了这盘醋包的这顿饺子 漫画都是竖条文字 居多 实际标注过程中调整左右边界比扩用的用的多为了提升效率

把向四周扩展 改完只扩展宽度方便包裹文字

https://github.com/user-attachments/assets/9abbc276-1c26-40b4-bd8e-3aec7724a5e9

17.鼠标滚轮调整四条边 添加快速调整 按住CTRL+鼠标滚轮 可以设置一个值来快速调整边界

只用滚轮是微调 按住CTRL+滚轮是快速修正

  wheel_rectangle_editing:
    adjust_step: 1
    enable: true
    fast_adjust_step: 10.0
    scale_step: 3


https://github.com/user-attachments/assets/007ed1f6-dd8a-48c2-9377-88c79a9649bc

18.面对旋转矩形无法确定下一次调整的旋转矩形 是宽度还是高度

所以增加在矩形内调整增加一个CTRL+滚轮调整高度

默认滚轮调整宽度 按住CTRL+滚轮调整高度 

https://github.com/user-attachments/assets/727cc8b5-8125-4f11-8b0f-38d4c1ada284

19.修复导航器激活焦点自动聚焦百分比输入框 让A D翻页可在导航器处于焦点时候可以使用

https://github.com/user-attachments/assets/d1406f33-a4a7-4f51-ad91-862f6ca71145

20.导航器增加CTRL+滚轮 增加快速调整功能 调整5% 默认滚轮调整为1% 

https://github.com/user-attachments/assets/28d9afd3-6d26-4a7a-9954-d41eaeaae3e4

21.优化导航器 1.导航器滚动条增加刻度 2.百分比输入框增加预设可滚动快速调整150%-500% 3.边缘收缩增大图片占比

<img width="682" height="395" alt="image" src="https://github.com/user-attachments/assets/6337f67a-4ba1-4f11-a3ab-2c2913d3a0fb" />

22.原版导入不同标签会被覆盖 我魔改成了导入不同标签不再是简单粗暴的覆盖 而是可以选择是覆盖还是合并 更灵活的导入 更人性化

https://github.com/user-attachments/assets/ed632835-25f3-43a9-ad1c-401390df9333

23.原版的后续0913更新了调整矩形时候全透明无填充色的功能

https://github.com/user-attachments/assets/3203c14a-dbd7-4927-91e7-4ef57b36ce62

我感觉不够好用我本身魔改就可以设置是否开启高亮

所以魔改填充透明度的调整开启高亮和不开启高亮设置2个不同的透明度 更灵活

https://github.com/user-attachments/assets/029b8aaa-953c-44b2-a61f-ea88d4cdcee8

填充透明度使用2个设置来控制

  shape_fill_alpha_highlight: 150

  shape_fill_alpha_idle: 30

不开启高亮时

![MouseInc_2025年09月18日11点06分31秒214](https://github.com/user-attachments/assets/204ce1a3-2b1c-45b4-9eb7-2370946940a9)

![MouseInc_2025年09月18日11点07分55秒875](https://github.com/user-attachments/assets/066f94b9-deb2-46c0-ba25-9b0e17371e76)

开启高亮时

![MouseInc_2025年09月18日11点06分48秒453](https://github.com/user-attachments/assets/6fe872c8-1d8a-4e0b-8a39-c33f9901bfcb)


24.标签页管理器不在因翻页而自动关闭 没有标注的页面也可以正常打开标签页管理器不再报错

标签也管理器增加管理CTRL+E功能 同时增加右键菜单 

https://github.com/user-attachments/assets/899d5cd3-c5f2-4100-ab4e-b33f1ae715f3

25.CTRL+E窗口增加快速调整旋转矩形角度功能 不再只依靠ZX CV来调整

可以输入数值快速调整 并且支持多选调整

https://github.com/user-attachments/assets/c1643ea5-97a8-4bdf-b094-8d9b1f581fd7

26.支持开源漫画翻译软件 https://github.com/dmMaze/BallonsTranslator 项目JSON的导出导入

https://github.com/user-attachments/assets/4712607c-8ffc-45a4-b540-facddd7caee1

27.支持付费图片翻译工具ImageTrans  https://www.basiccat.org/zh/imagetrans/ 项目文件的导入导出

https://github.com/user-attachments/assets/ec2a4ce5-4fe3-4777-849a-c082c9a51f2e

https://github.com/user-attachments/assets/65b05cf7-d7ec-405b-86c3-1453893d6488

28.增加区域合并可合并文本

https://github.com/user-attachments/assets/642f3694-0797-4c86-afdd-37a8c96908c3

29.增加双色标签工具

https://github.com/user-attachments/assets/54d9e645-58c7-49ea-807c-b41972f4c93f

30.增加漫画排序工具可视化以及排序线

https://github.com/user-attachments/assets/2b258c55-8d39-45fb-b3d4-24ec6613303e

31.标签框扩展窗口优化 增加动态颜色显示 防止填写错标签 用的时候发现没颜色视觉交互很容易填错位置

然后增加全部清零 和单独标签清零的功能 并且可以最小化了

https://github.com/user-attachments/assets/0668abdc-e630-4ec3-8e53-ec4cb5840690

32.增加多选功能 按住ALT+鼠标左键拖拽可以画框 按住SHIFT+鼠标左键可以路径模式

路径模式可以更精确选择在矩形内的矩形 路之间模式只有当线条穿过了图形的线条才会被选中

而画框多选模式和WIN的画框多选一样 无法精确操作 进入范围内的全部被选中

画框多选模式

https://github.com/user-attachments/assets/4e4451ad-3535-4f45-8636-497b068c2db8

路径多选模式

https://github.com/user-attachments/assets/63833dce-9989-4ed6-beb8-fd28f90c3496

33.给相同矩形的重叠部分高亮添加了开关按钮

https://github.com/user-attachments/assets/00f801c1-9ad3-4dd5-9271-ae3be35332bc

34.修改 创建图形时隐藏标签自动显示的问题 在没按快捷键或者 界面按钮的时候 就是应该一直隐藏 

https://github.com/user-attachments/assets/2d2e0c1a-13e7-4d77-8005-01889ad6debb

35.新的旋转矩形标注模式

https://github.com/user-attachments/assets/94d99143-0a7e-4a54-a720-40f6bc642bb8

36.增强十字线 以适应新的旋转标注模式 同时对新标注模式应用独立鼠标样式可自定义

https://github.com/user-attachments/assets/9834c8b2-05a3-4359-b932-9a542474ef16

37.新旋转矩形标注模式添加实时角度显示

https://github.com/user-attachments/assets/a43a4c71-5ec0-49dc-98d2-725835ce98aa

38.优化 最近打开的文件 原版 是只打开一张图 没啥用啊 好鸡肋 优化成 打开历史目录 并且 增加清除历史功能 历史限制在最多50个 路径长度200字符防止过长超出屏幕

https://github.com/user-attachments/assets/d163be78-69e9-42be-ac09-f7af20c94d77

39.导出增强 增加只导出手动修改的项目 同时区分 是AI推理的 还是人手动修改的 手动修改后 路径变色代表是 人修改的和AI推理区分开 

使用颜色区分 模型推理 和 人手动修改

https://github.com/user-attachments/assets/62baee8a-4204-4a56-812e-8063898eb3bf

这样区分之后 后可以 只导出 手动修改的 识别错误需要重点训练目标

https://github.com/user-attachments/assets/3cad97b1-c42e-493f-a6cf-803019fcde7e



