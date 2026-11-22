---
name: live2d-character-workflow
description: Create editable Live2D Cubism models and looping animations from a character illustration. Use for 立绘拆层、遮挡补画、Live2D 建模、视线与头发绑定、手持道具、修复循环顿感、原生工程交付或透明帧配景。Includes portable Python tools for PSD assembly, warp binding, motion curves and background video composition.
license: MIT
---

# 从立绘制作可编辑的 Live2D 角色

使用 Python 3.10 以上、Pillow 和 psd-tools。原生工程在 Cubism Editor 5 中编辑和验收，视频导出需要配有 libx264 的 FFmpeg。

先确定要交付的动作、支撑点、镜头构图、是否循环，以及用户后续想自行调哪几项。沿用用户指定的角色设计、节奏和表情，参考视频用于分析姿势与时间。记录中性姿势、最深下沉、最高点、复位前后和重要接触帧。

1. **准备画稿。** 先定前后遮挡顺序，拆出需要相对运动的部件，补画活动后会露出的皮肤、衣料、书封或后发，保留原画透明度和画布坐标。手与袖口、左右手与书、虹膜与眼睑各自分层。用 `scripts/layers_psd.py` 组装可编辑 PSD。对照整图和两种底色检查轮廓。
2. **建立模型。** 在 Cubism 导入 PSD 和保存中性 `.cmo3`。为躯干、肩颈、上臂、手、头发和配饰设置有实际意义的支点。使用编辑器，或在新保存的中性模型上用 `scripts/bind_model.py` 生成独立可调的父子变形器。调到每个端点并检查网格、遮挡和脚底。精细的眼皮、指形及衣褶在 Cubism 内调整网格与关键形。
3. **制作动作。** 先定重心和节拍，再做膝、腰、肩与手的换向。给眼睛写明确目标。让内发贴近头部，外束和发尾稍后回摆。用 `scripts/motion_keys.py` 生成带时间和曲线的动作文件，在 Cubism 模型轨上导入并保存 `.can3`。角色专项处理见[绘制、绑定和动作验收](references/art-and-motion.md)。
4. **配景与导出。** 从已保存的正式场景导出一轮透明 PNG。把指定背景置于角色下方，用 `scripts/compose.py` 按指定速度和循环数写出 MP4。向用户标明展示速度和原工程帧率。
5. **交付并验收。** 将 PSD、模型、动画放入可移动的工程目录，重新打开模型和动画，改一个参数、移动一个时间线关键帧并预览。原速连续看至少三轮，再对照关节、头发、眼睛与手部的局部。交付可编辑源文件与带背景视频，预览与源文件分别命名。

从[练习与命令](references/tools.md)开始。阅读、棒球、掌机三种动作的拆分思路见[绘制、绑定和动作验收](references/art-and-motion.md)。
