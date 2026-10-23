# TruePixel Studio 🎨

> 把 AI（Midjourney / DALL·E / Imagen / Stable Diffusion / Gemini）生成的"伪像素"图，转换成可以直接放进游戏引擎的**真像素**透明 PNG 和精灵表。
> 有拖拽式网页工作室，也有命令行和批处理。

## 解决什么问题

| AI 原图的问题 | TruePixel 的处理 |
|---|---|
| 背景不干净，抠完有 1~2px 灰黑毛边 | rembg 抠图 → 透明度二值化 → 形态学腐蚀切掉暗边 |
| 抠图把光晕、细剑尖误删 | 纯色背景时按色差把误删的前景找回来 |
| 抠图残留零星飞屑 | 连通域面积过滤 |
| 不是真像素：分辨率高、抗锯齿、颜色多 | 裁到主体 → 等比缩放居中 → 减色或映射到统一调色板 |
| 轮廓不清楚 | 1px 正交闭合描边 |
| 动画帧大小不一、角色抖动 | 精灵表固定锚点：全部帧按第 0 帧的比例和脚底中心对齐 |
| 每个品阶都要重新画 | 仙品母版一键变色出十阶品质 |
| 伪像素：一个"像素"其实是 5×5 的模糊色块，网格还会漂移 | 自动检测色块大小、逐条追踪网格线，每格取中位色还原成原生像素（`native`） |
| 品红/绿幕底抠完有一圈粉边 | 色键抠像 + 边缘去溢色，镂空处也能删干净 |
| UI 面板不是正方形、一张图里画了好几个 | 原生分辨率输出，按连通域自动拆成多张 |

## 安装

```bash
pip install -r requirements.txt          # 含 rembg（AI 抠图，首次运行会下载 u2net 模型）
# 或者作为包安装，得到 truepixel 命令：
pip install -e ".[ai]"
```

不装 rembg 也能用：会退回到"按四角颜色做色差抠图"，对纯色背景的原图通常足够。

## 网页工作室

```bash
python -m truepixel serve        # 或双击 start_web.bat，或 python app.py
```

浏览器打开 http://127.0.0.1:7860 。支持拖拽 / 粘贴 / 批量、实时调参、三种模式（实体道具 / 发光特效 / 双层合体）、最近邻放大预览、一键打包 ZIP。
想让局域网里的手机访问：`python -m truepixel serve --host 0.0.0.0`。

## 命令行

```bash
# 单张：96x96、32 色、去背景、描边
python -m truepixel single 原图.png 成品.png --size 96 --colors 32 --preview 8

# 统一调色板 / 地图图块（不去背景不描边）/ 发光特效
python -m truepixel single 原图.png 成品.png --size 32 --palette palette.png
python -m truepixel single 草地.png tile.png --size 16 --keep-bg --no-outline
python -m truepixel single 剑气.png aura.png --vfx --size 96

# UI 面板 / 一张图多个物体：按原生像素还原，不缩放成正方形，自动拆分
python -m truepixel native ui_panels.png 输出目录 --preview 4          # 自动检测色块大小
python -m truepixel native ui_panels.png 输出目录 --pixel-size 5 --palette palette.png
python -m truepixel native glow_panel.png 输出目录 --peel 4                # 剥掉画成实心的外发光

# 按素材清单批量处理（见下文）
python -m truepixel batch asset_list.json

# 3x3 九宫格动画 → 1x8 横向精灵表（每帧 96x96，另存 3 倍高清版）
python -m truepixel sheet 九宫格.jpg sheet.png --rows 3 --cols 3 --frames 8 --size 96 --hd 3

# 仙品母版 → 十阶品质（凡/良/灵/玄/地/天/宝/仙/神/混沌）
python -m truepixel tiers weapon_xian.png 输出目录 --slot weapon
```

旧命令 `python true_pixel.py --input a.png --output b.png --size 64 --colors 24` 仍然可用，会自动转换成新命令。

## 批处理清单

`asset_list.json`（路径都相对清单所在目录）：

```json
{
  "defaults": { "raw_dir": "raw", "out_dir": "assets", "palette": "assets/palette.png",
                "max_colors": 16, "preview_scale": 8 },
  "assets": [
    { "name": "weapon_sword_xian", "folder": "equip", "size": 96, "content_size": 78,
      "kind": "sprite", "prompt": "给生图模型的提示词" },
    { "name": "tile_grass_01", "folder": "tiles", "size": 16, "kind": "tile" }
  ]
}
```

- 原图放在 `raw/<name>.png|jpg|webp`，输出到 `assets/<folder>/<name>.png`。
- `kind`：`sprite` 去背景+描边；`tile` 铺满整格；`vfx` 发光特效；`native` 原生分辨率还原（不需要 `size`，多个物体另存 `<name>_0.png`…）。
- 每个素材可以用 `options` 覆盖任意 `process_image` 参数。
- 只处理新的或原图更新过的素材（`--force` 全部重做，`--only a b` 只做指定的）。
- 输出 `assets/_preview/_contact_sheet.png` 总览图和 `batch_report.md` 报告。

## 生图提示词模板

完整规则和分类模板见 [skills/truepixel-imagegen/SKILL.md](skills/truepixel-imagegen/SKILL.md)。最短版：

```text
Pixel art game asset, [物体], flat 2D orthographic view, chunky visible square pixels on a
consistent grid, hard edges, 1px dark outline, flat color shading, centered with wide empty margin.
The entire background is one flat uniform solid magenta color (#FF00FF).
Do not add any glow, aura, drop shadow, or light effect outside the object.
```

- 背景用**品红 #FF00FF**（主体有紫/粉色时改用绿幕 #00FF00），会自动走色键。
- 不要把 `glow, blur, shadow` 这类词直接写进正向提示：没有否定语境时模型会照着画。
- 发光状态、悬停高亮交给引擎（shader / modulate），不要生成带外发光的图。
- 发光特效（剑气、火焰）例外：用 `on a pure black background`，走 `--vfx`。

## Python 接口

```python
from truepixel import process_image, process_vfx_image, composite_layers, process_sheet
native, preview = process_image(Image.open("raw.png"), target_size=96, color_count=32)
```

`from true_pixel_core import process_image` 这种旧写法也还能用。

## 目录结构

```text
truepixel/
  ops.py          底层像素操作（描边、去飞屑、透明度、调色板、缩放）——唯一实现
  background.py   背景移除（rembg + 纯色背景保底）
  pipeline.py     实体 / 特效 / 双层合成 / 精灵表
  tiers.py        十阶品质变色
  batch.py        素材清单批处理 + 总览图 + 报告
  cli.py          命令行
  server.py       网页工作室后端
web/index.html    网页前端（原生 HTML/CSS/JS）
scripts/          一次性/专用脚本（程序化生成 32px 装备、装备母版流水线）
tests/            python -m unittest discover -s tests
examples/         示例原图
app.py, true_pixel.py, true_pixel_core.py   旧入口的兼容层
```

## 开发

```bash
python -m unittest discover -s tests -v
```

协作约定、设计决策和踩坑记录见 [AGENTS.md](AGENTS.md)。

## License

MIT
