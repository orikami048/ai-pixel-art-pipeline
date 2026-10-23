# AGENTS.md：给所有在这个仓库干活的 AI（以及以后的自己）

> Claude Code 通过 `CLAUDE.md`、Antigravity 通过 `GEMINI.md` 读到这里，这是唯一的正文。
> **开工前先读完本文件；收工前把新学到的东西追加到「经验记录」。** 这样每一轮的教训都会留给下一轮，不管下一轮是谁。

## 1. 这是什么

TruePixel：把 AI 生成的"伪像素"图转成真像素游戏素材。主要服务于用户的修仙游戏
[`orikami048/xiuxian-game`](https://github.com/orikami048/xiuxian-game)（《修仙模拟器：天命心火》，纯静态 Web，国风水墨 + 像素装备/角色，素材以 96×96 为主）。

相关位置（用户的 Windows 电脑）：

| 路径 | 内容 |
|---|---|
| `D:\projects\ai-pixel-art-pipeline` | 本仓库 |
| `D:\projects\xiuxian-game` | 游戏本体，素材最终放到 `textures/`、`pixel_art/` |
| `D:\work` | 素材生产工作区：`HANDOFF.md`（Claude ↔ Antigravity 交接）、`asset_list.json`（素材清单）、`raw/`（AI 原图）、`assets/`（成品） |

## 2. 代码地图

```text
truepixel/ops.py         底层像素操作。描边、去飞屑、透明度、调色板都只在这里实现一次
truepixel/background.py  品红/绿幕色键 + rembg 抠图 + 纯色背景保底（rembg 是可选依赖，懒加载）
truepixel/grid.py        伪像素网格还原：估计色块边长、逐条追踪网格线、按格取中位色
truepixel/pipeline.py    process_image / process_vfx_image / composite_layers / process_sheet / process_native
truepixel/tiers.py       十阶品质变色
truepixel/batch.py       素材清单批处理
truepixel/cli.py         命令行：single / native / batch / sheet / tiers / hd / serve
skills/                  给生图 AI（Gemini / Antigravity）用的 skill，安装方法见 skills/README.md
truepixel/server.py      网页后端；接口和 web/index.html 绑定，不要改字段名
scripts/                 专用脚本，必须 import truepixel，不许复制函数
app.py / true_pixel.py / true_pixel_core.py   旧入口兼容层，别删（用户和别的项目还在用）
```

## 3. 硬规则

1. **不要复制粘贴像素函数。** 需要描边、去噪、减色就 `from truepixel import ops`。2.0 重构前同一个描边函数有 4 份，其中一份行为还不一样。
2. **不要硬编码本机路径**（如 `C:\Users\kami\.gemini\...`）。路径一律走命令行参数，默认值可以写，但必须能覆盖。
3. **改了任何处理逻辑都要跑测试：** `python -m unittest discover -s tests -v`。测试不依赖 rembg。
4. **有意改变输出时**，在下面「设计决策」里记一条：改了什么、为什么、对旧素材有什么影响。
5. `web/index.html` 只调用 `/api/process` 和 `/api/download_zip`；改 `server.py` 时请求字段和返回字段必须保持兼容。
6. 调试图（`debug_*.png`、`test_*_out.png`）不要提交，已在 `.gitignore`。
7. 提交信息用 `类型(范围): 说明`，例如 `fix(pipeline): ...`、`feat(cli): ...`。

## 4. 常用命令

```bash
python -m unittest discover -s tests -v            # 测试
python -m truepixel serve                          # 网页工作室 http://127.0.0.1:7860
python -m truepixel single in.png out.png --size 96
python -m truepixel native ui_panel.png out_dir --preview 4   # 原生分辨率还原 + 自动拆物体
python -m truepixel batch D:\work\asset_list.json  # 素材工作区批处理
python -m truepixel sheet grid.jpg sheet.png --rows 3 --cols 3 --frames 8 --size 96 --hd 3
python -m truepixel tiers weapon_xian.png out_dir --slot weapon
```

Windows 控制台先 `$env:PYTHONIOENCODING="utf-8"`，否则中文和 emoji 可能报编码错误。

## 5. 协作分工

- **用户**：定方向、拍板。
- **Claude**（云端会话，通过桥接读写用户电脑上的文件）：架构、重构、代码审查、素材清单与验收。已有 GitHub 推送权限（2026-10-22 起），改动推到功能分支；云端装不了 rembg 模型时，由 Antigravity 在本机验证后合并进 `main`。
- **Antigravity**（用户本地）：生图、跑命令、提交推送、维护网页前端。
- 跨项目的任务和验收写在 `D:\work\HANDOFF.md`；这个仓库自己的长期知识写在本文件。

## 6. 设计决策（按时间追加，不要删旧的）

- **2026-10-22 · Claude · v2.0 重构为 `truepixel` 包。** 原因：函数重复、CLI 与 README 不符、脚本硬编码路径。用 152 组参数对比了旧版输出：除下面两条有意修复外逐像素一致，处理速度约快 5 倍（描边从 Python 双重循环改为 numpy）。
- **2026-10-22 · Claude · 修复 screen 混合模式。** 旧版两个图层顺序下 G、B 通道都误用了 R 通道的特效值，导致蓝/绿色光效变色。用 screen 模式合成过的旧素材颜色会变。
- **2026-10-22 · Claude · 装备母版流水线改走 `process_image`。** 旧版 `process_ai_equip_assets.py` 缩放后没有二值化透明度，一张 96px 母版里有约 960 个半透明像素，不符合真像素要求。现在只有 0/255。主体尺寸 78px、36 色、阈值 120、飞屑 25 等参数不变。
- **2026-10-22 · Claude · 保留旧行为：二值化透明度时不清零透明像素的 RGB。** 这些隐藏颜色会参与 median-cut 减色。清零会让输出和旧版不一致，所以默认保留；`process_sheet` 沿用旧版的清零行为。以后如果想优化调色，可以改成只对不透明像素减色，但要记一条决策。
- **2026-10-22 · Claude · 网页服务默认只监听 127.0.0.1**，并修复了 `/examples/` 的路径穿越。需要局域网访问时用 `--host 0.0.0.0`。

- **2026-10-24 · Claude · 新增 `process_native`（命令 `native`、批处理 `kind: "native"`、网页"原生还原"模式）。** 原因：`process_image` 先 LANCZOS 缩放再减色，伪像素的色块网格对不上目标尺寸，结果发糊；而且只能输出正方形，UI 面板（3:1）、九宫格素材、一张图里多个物体都没法用。新流程按检测到的色块边长逐格取中位色，输出原生分辨率，按连通域拆物体。不影响旧模式。
- **2026-10-24 · Claude · `remove_background` 遇到四角是均匀品红/绿色时改用色键，不再走 rembg。** 原因：rembg 会把 UI 边框这类"不像物体"的主体删掉，品红底下色键更稳，还能删干净镂空处、处理边缘溢色。影响：品红/绿幕底的原图用 `single`/`batch` 重新处理，结果会和以前不同（一般更干净）。白底等其他背景行为不变。批处理报告的尺寸改为写实际宽高（正方形素材不变）。

## 7. 经验记录（踩过的坑，按时间追加）

- 测试批次必须用**真的 AI 原图**。用代码画几个色块当原图，只能证明脚本能跑，看不出抠图、描边和风格统一的问题（2026-10-22 D:\work 测试批次就因此被打回）。
- rembg 在纯色背景下容易把光晕、细剑尖当背景删掉；`background.py` 里的"前景保底"就是为此加的。`post_process_mask=True` 边缘更干净但更容易吃细节。
- 原图背景用纯白或纯色、主体居中、不要地面阴影，抠图成功率最高。发光特效用纯黑背景。
- 1px 描边是"内描边"：把剪影最外圈涂成描边色，不会让剪影变大。所以描边时缩放会预留 2px。
- 十阶变色靠"接近黑色的像素是描边"来区分描边和主体（RGB ≤ 24/24/28），母版主体里不要用这么暗的颜色，否则会被当成描边不变色。

- 伪像素网格检测：剪影外缘的边特别强，会让"物体高度"变成自相关最强的周期，所以估计周期只看两侧都不透明的内部边（`interior_only`）。判断网格是否存在不能只看自相关峰（原生像素图也总有峰），要看边缘能量有多少落在追踪出的网格线上（`grid_fit`），先 3×3 中值滤波去逐像素噪点。
- 合成测试图要有纹理：只有几条边的面板，周期本来就量不准，测出来失败不代表算法错。真实 AI 原图（examples/ 里的 1024 图）色块约 5.1px，吻合度 0.73~0.80；合成伪像素图（含 3~4px 小色块、中度模糊）≥ 0.27；原生像素图 ≤ 0.21；阈值 0.25。s < 4 时吻合度只看网格线本身那一个边界（±1px 窗口在小色块下会覆盖所有位置，比不出差别）。
- 小数周期用"谐波梳"估计：在整数首峰 ±1 内按 0.01 扫候选 s，得分是自相关在 s、2s、3s… 处插值的平均。试过两种不行的：按整数首峰的倍数找（3.5 估成 2.9），以及逐个倍数峰更新估计（一个纹理假峰就把后面全带偏，5.0 估成 4.6）。
- 色块 3~4px 在轻中度模糊下能自动检测；3~4px 再加重度模糊（σ≈1）时信息已经丢了，自动检测会失败，用 `--pixel-size` 手动指定。
- AI 原图里的外发光、投影抠不干净（半透明像素会变成一圈实心杂色）。根治要在提示词里禁止，发光状态交给引擎做（shader / modulate）；已经出了的图可以用 `native --peel N` 剥掉外圈（用户那张发光面板 N=4 合适，5 以上开始吃真边框）。
- 用户给的图可能本来就是透明底（看着像白底）。透明底时 `_strip_background` 会走 flat 分支，结果一样，但别用"背景色"去推断光晕。

## 8. 已知问题 / 以后可以做

- 实心外发光（原图里已经是不透明像素的光晕带）没法从颜色或透明度上和主体区分，只能用 `peel` 按圈剥掉，剥多了会吃掉真边框。根治靠提示词。

- 透明像素的隐藏颜色会占用减色名额（见设计决策），对小尺寸素材可能浪费 1~2 个颜色。
- 发光特效模式的"颜色数"统计包含不同透明度，数值偏大，仅供参考。
- 精灵表只支持"以第 0 帧为基准"的锚点；如果第 0 帧姿势特殊（比如蹲下），比例会不对，可以考虑加 `--ref-frame` 参数。
