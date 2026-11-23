# 从练习到自己的角色

所有命令均从本技能文件夹运行，输入输出路径可使用相对路径。Windows 可使用 PowerShell，macOS 与 Linux 可使用终端。需要 Python 3.10 以上；生成视频另需可运行 `ffmpeg -version` 且包含 libx264 的 FFmpeg。官方可编辑工程的打开和保存需要 Cubism Editor。[Cubism Editor](https://www.live2d.com/en/cubism/download/editor/)

## 纸吊饰练习

```sh
python -m pip install -r requirements.txt
python scripts/starter.py practice
```

生成的 `Mobile.psd` 包含 Stand、Ribbon 和 Pendant 三个图层。双击 `Swing.can3` 可在 Cubism 播放两秒循环并编辑关键帧。打开 `Mobile.cmo3`，调节 “Swing at the hanger” 观察悬绳和吊坠共同摆动，再调 “Pendant follow-through” 观察吊坠相对悬绳转动。底座保持落在原位。`keys.json` 是时间配方，`Swing.motion3.json` 可单独导入其他含有相同参数的场景。[放入模型](https://docs.live2d.com/en/cubism-editor-manual/loading-model-and-placement/) · [在动画中导入动作](https://docs.live2d.com/en/cubism-editor-manual/export-moc3-motion3-files/)

## 换成自己的画稿

1. 将补画好的透明图层放在同一画布坐标系，给需要动的部件起唯一名称。按从底到顶的顺序编写 `layers.json`。`file` 指向透明 PNG；较小的贴片使用 `xy` 指定左上角。也可给整个配方设置 `source`，用单通道的 `mask` 引用原画，白色可见、黑色透明。
2. 运行 `python scripts/layers_psd.py layers.json Character.psd`，在 Cubism 打开 PSD，检查图层顺序与网格并保存为 `Neutral.cmo3`。需要清晰转折的部位可在 Cubism 调网格。中性工程为新导入、目标图层仍挂在根节点的模型。[官方 PSD 导入说明](https://docs.live2d.com/en/cubism-editor-manual/psd-import/)
3. 在 `rig.json` 的 `controls` 数组中先写父变形器，再写子变形器。`id` 为独立的参数 ID，`name` 是面板名称，`layers` 写 Cubism 中的 ArtMesh ID。将同一图层分配给最内层控制器一次。参数有 −1、0、+1 三个关键形。
4. 运行 `python scripts/bind_model.py Neutral.cmo3 rig.json Character.cmo3 --psd Character.psd`。使用新的输出名，拖动参数检查图层、支点和可见极限。对复杂五官、非线性衣褶或局部网格，在 Cubism 继续雕刻关键形。
5. 在 `keys.json` 以原始帧率指定轨道。将自己的模型放入新建的单场景动画并保存为 `Timeline.can3`，然后运行 `python scripts/animate.py Timeline.can3 Character.cmo3 keys.json Action.can3`。输入场景应只含这个模型，目标参数轨上应尚无关键帧。该脚本保留模型的画面布局，把曲线与控制点写入新的可编辑工程。也可运行 `python scripts/motion_keys.py keys.json Action.motion3.json`，在现有场景的模型轨道名称上单击右键，导入动作为独立操作。移动工程时保持模型和动画的相对位置，在另一目录复开确认。

最小的图层清单如下。尺寸与坐标单位是源图像素。

```json
{
  "canvas": [800, 1200],
  "source": "drawing.png",
  "layers": [
    {"name": "BackHair", "file": "back-hair-painted.png", "xy": [100, 90]},
    {"name": "Head", "mask": "head-mask.png"},
    {"name": "Fringe", "file": "fringe.png"}
  ]
}
```

变形器使用整张画布的归一化坐标，左上为 (0, 0)，右下为 (1, 1)。`pivot` 指支点，`degrees` 指最大旋转角度，`move` 指最大平移占画布宽高的比例，`stretch` 指比例变化。可选的 `weight_y: [start, end]` 意为沿纵轴从零影响渐变到完全影响；倒写上下界可将足底锁住。`grid` 指水平、纵向的分段数量，`parent` 是父参数 ID。完整带数字的绑定和曲线可从练习生成的 `rig.json` 与 `keys.json` 复制。曲线支持 `smooth`、`linear` 和 `stepped`。循环在第 0 和第 N 帧使用相同值，平滑模式让接缝两侧切线一致。

## 给导出的动作叠加背景

在 Cubism 把完整周期导出为带透明度的 PNG 序列。如果端点和首帧相同，序列只收 0 到 N−1。保存帧号连续的文件到单独目录，指定实际原工程帧率。下面以 48 fps、136 帧的周期为例，在背景上按 1.5 倍速播放六轮。

```sh
python scripts/compose.py frames stadium.png preview.mp4 --fps 48 --expect 136 --speed 1.5 --loops 6 --output-fps 60
```

`--character-height` 控制整张人物画布占画面高度的比例，`--character-top` 和 `--center-x` 确定角色的位置，`--background-width` 和 `--background-bottom` 控制背景大小与底边。`--base-color` 填充背景自身留出的透明区。默认输出 864 × 1440 的静音 H.264。改 `--speed` 只改变展示成片的时间，原始工程仍可继续调整。
