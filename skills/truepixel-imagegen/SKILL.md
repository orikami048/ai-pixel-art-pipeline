---
name: truepixel-imagegen
description: 生成可以直接进游戏引擎的像素风美术资产（道具图标、角色、UI 面板/按钮/九宫格边框、地图图块、特效、场景背景）。用 Gemini 的生图工具（generate_image）按本 skill 的提示词规则出图，再用本地 TruePixel 管线（python -m truepixel）抠图、还原真像素、拆分、统一调色板，并按检查清单验收。用户说"生成像素素材 / 像素风图标 / UI 边框 / 美术资源 / sprite"时使用。
---

# TruePixel 生图：像素风游戏素材

生图模型画出来的"像素风"其实是**伪像素**：一个"像素"是 5×5 左右的模糊色块，网格会漂移，边缘有抗锯齿和光晕。
它不能直接进引擎。可用素材 = **能被后处理的原图** + **TruePixel 管线**。本 skill 两步都管。

> 游戏自己的美术风格 skill（配色、题材、材质，例如 `pantheon-art-crafter`）决定**画什么**；
> 本 skill 决定**怎么画才能变成素材**。两者冲突时（背景色、发光、阴影、描边），以本 skill 为准。

---

## 1. 六条硬规则（每次出图前逐条对照）

1. **一张图只画一个物体。** 要三种状态的按钮，就出三张图，或者只出一张、其余状态交给引擎做。
   例外：同一套小图标可以放在一张图里，但必须写 `arranged in a grid with wide empty gaps between them, not touching`。
2. **背景必须是纯品红 `#FF00FF`。** 主体里有紫色、粉色、洋红色时，改用纯绿 `#00FF00`，此时主体里不能有亮绿色。
   发光特效例外，用纯黑背景（见 3.6）。
3. **不能有任何超出物体轮廓的效果。** 外发光、光晕、投影、地面阴影、光线、粒子、烟雾都不行。
   这些半透明像素抠完会变成一圈实心杂色，后处理修不了。需要发光就在引擎里用 shader 或 modulate 做。
4. **负面要求必须写成完整的否定句。** 不能把 `glow, blur, shadow` 光秃秃地写进提示词，模型会照着画。
   写 `Do not add any glow...`；如果生图工具有单独的 negative prompt 栏，就把词填到那一栏。
5. **正交平视，扁平 2D。** 不要透视、不要 3D 渲染、不要写实光影。图标可以用 3/4 俯视，但视角要固定。
6. **说清楚像素有多大。** 写明 `about N art-pixels wide`。1024 宽的图里 N 最好不超过 200，这样每个像素 ≥ 5 个图片像素，后处理才量得准。

## 2. 基础提示词骨架（英文写给模型，中文是说明）

```text
Pixel art game asset: [ONE 物体, 关键特征].
[类型修饰：见第 3 节]
Style: chunky visible square pixels on a strict consistent grid, about [N] art-pixels wide,
hard pixel edges, continuous 1px dark outline around the silhouette, flat color shading with
[3-5] tones per material, light from top-left, limited palette of [16-32] colors.
[游戏风格：配色、材质、题材，来自项目自己的风格 skill]
Composition: single object, centered, flat 2D [orthographic front view | 3/4 top-down view],
wide empty margin on all sides (at least 10% of the image).
Background: the entire background is one flat, uniform, solid magenta color #FF00FF,
with nothing else on it.
Do not add any glow, aura, bloom, light rays, drop shadow, ground shadow, particles, smoke,
or any effect outside the object's outline. Do not use anti-aliasing, blur, soft edges,
gradients or semi-transparent pixels. No text, no watermark, no frame around the image.
```

如果生图工具支持参考图：**附上一张已经验收通过的素材**，并加一句
`Match the exact pixel size, outline style and palette of the reference image.` 这是让整批素材风格统一最有效的办法。

## 3. 按类型的修饰段

### 3.1 道具 / 装备图标（引擎尺寸 32~96）
```text
Game item icon, [物体], chunky slightly squat proportions, 3/4 view from slightly above,
fills about 80% of the frame, one vivid accent color, tiny white specular highlights.
```
- N = 引擎尺寸（例如 64），处理用 `single --size 64`。

### 3.2 角色 / 怪物（单帧）
```text
Full-body game character sprite, [角色], standing idle pose facing right, clear readable
silhouette, head about 1/3 of body height (chibi), feet flat at the bottom.
```
- 动画帧另说：要求 `3x3 grid of animation frames, same character, same size, same position in each cell`，处理用 `sheet`。

### 3.3 UI 面板 / 对话框 / 九宫格边框（最容易出问题）
```text
Game UI panel frame, ONE single empty rectangular plaque, perfectly symmetrical left-right
and top-bottom, orthographic front view, aspect ratio about [3:1].
Decorative ornaments ONLY in the four corners; the edges between the corners are straight,
plain and uniform so they can be stretched; the center is a flat plain fill with no texture.
Border about [3-4] art-pixels thick.
```
- **只生成常态。** 悬停、选中、发光状态在引擎里做：Godot 用 `modulate` 调色，或者给 NinePatchRect 加描边/发光 shader。
- 如果一定要另一种颜色的状态，就单独出一张，写 `same frame, border recolored to [颜色], no glow`，不能写 glowing。
- N 约 160（宽）。处理用 `native`，然后在 Godot 里把 NinePatchRect 的 patch margin 设成角花的宽度。

### 3.4 按钮 / 图标按钮
同 3.3，额外要求 `pill-shaped / rounded rectangle button, no text on it`。文字在引擎里叠加，不要画进图里。

### 3.5 地图图块（不抠背景）
```text
Seamless tileable [草地/石砖] texture, top-down view, fills the entire canvas edge to edge,
no border, no outline, no background, pattern continues across all four edges.
```
- 这一类**不用品红背景**。处理用 `single --keep-bg --no-outline --size 16/32`。

### 3.6 发光特效（剑气、火焰、雷光）
```text
Pixel art [特效] effect, bright saturated colors fading out, on a pure black background #000000,
no object, effect only.
```
- 这是唯一允许有光晕的类型，背景用**纯黑**。处理用 `single --vfx`。

### 3.7 场景背景（全屏）
- 满画布，不抠背景。写 `full scene, fills the entire canvas, [16:9]`。处理用 `hd`。

## 4. 出图后：跑 TruePixel 管线

管线仓库：`D:\projects\ai-pixel-art-pipeline`（Windows 下先执行 `$env:PYTHONIOENCODING="utf-8"`）。

| 素材类型 | 命令 |
|---|---|
| UI 面板、按钮、九宫格，一张图里有多个物体，任何**不是正方形**的东西 | `python -m truepixel native raw.png 输出目录 --name 名字 --preview 4` |
| 固定尺寸的道具/角色图标 | `python -m truepixel single raw.png out.png --size 64 --preview 8` |
| 地图图块 | `python -m truepixel single raw.png out.png --size 32 --keep-bg --no-outline` |
| 发光特效 | `python -m truepixel single raw.png out.png --vfx --size 96` |
| 3×3 动画帧 | `python -m truepixel sheet raw.png sheet.png --rows 3 --cols 3 --frames 8 --size 96` |
| 场景背景 | `python -m truepixel hd raw.png out.png` |

- 整批素材统一颜色：加 `--palette 项目调色板.png`。
- 原图存进 `raw/`，按 `用途_名称_变体` 命名，例如 `ui_panel_dialog.png`。

## 5. 验收清单（每张都要过，不过就重新出图，不要硬修）

`native` 会输出一行，例如 `背景：magenta；色块 5.12px，吻合度 0.74；1 个物体`。逐项检查：

| 检查项 | 合格 | 不合格时怎么改提示词 |
|---|---|---|
| 背景 | `magenta` 或 `green` | 出现 `flat`/`rembg`/`none`：模型没听话。把背景那句挪到提示词**最前面**，并且再写一遍 |
| 吻合度 | ≥ 0.25（真 AI 图一般 0.5~0.8） | 偏低：像素太小（< 4px）或太糊，或网格太乱。减小 N、强调 `chunky square pixels on a strict grid`；或者手动加 `--pixel-size` |
| 物体数 | 和预期一致 | 多了：有飞屑、光晕或物体被拆开了，检查发光/阴影；少了：几个物体挨在一起了，要求 `wide gaps` |
| 预览图边缘 | 没有粉色或白色的毛边，没有一圈光晕 | 有：边缘有光晕或抗锯齿，加强第 3 条硬规则重新出图。图实在想保留时，可以加 `--peel 3~5` 剥掉外圈（会吃掉同样厚度的真边框，剥完要看预览） |
| 尺寸比例 | 面板宽高比正确，左右对称 | 不对称：写 `perfectly symmetrical`，或者只用一半、在引擎里镜像 |
| 九宫格 | 四条边的中段是直的、均匀的 | 中段有花纹：写 `ornaments ONLY in the four corners` |

验收时**一定要看 `_preview/` 里的放大预览图**，不要只看命令输出。

## 6. 进 Godot 的设置

- 导入：Filter = Nearest，Mipmaps 关闭（或者项目设置里把默认纹理过滤设成 Nearest）。
- 面板：用 `NinePatchRect`，四个 patch margin 等于角花的像素宽度。
- 缩放：只用整数倍（2x、3x、4x），否则像素会大小不一。
- 发光、悬停、选中：`modulate` / `self_modulate`，或者 shader。不要为这些状态再出图。

## 7. 和用户沟通

- 出图前先确认：素材类型、引擎里的尺寸、要几种状态（并说明状态建议在引擎里做）。
- 交付时给出：原图路径、成品路径、`native`/`single` 的输出那一行、放大预览图。
- 某张图连续 3 次过不了验收，就停下来告诉用户卡在哪一项，不要一直重试。
