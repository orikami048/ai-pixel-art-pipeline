# TruePixel Engine 🎨

> **Production-Grade AI Fake-Pixel to True-Pixel Game Asset Pipeline**  
> 一键将 AI（Midjourney / DALL-E / Imagen / Stable Diffusion）生成的“伪像素”图像转化为真正纯净、可直接进游戏引擎的真像素透明 PNG、八大装备法宝矩阵与多帧精灵序列大图（Sprite Sheet）。

---

## 🌟 核心解决的技术痛点

1. **暗色黑边杂色（Dark Edge Fringing & Bleeding）**：
   - 解决原理：AI 在深色底上生成的半透明羽化边缘会导致残存 1~2px 的暗灰色噪点。本工具采用 OpenCV 图像形态学侵蚀（Alpha Erosion）结合 Decontamination 算法，彻底切除杂色黑轮廓。
2. **多帧动画尺寸忽大忽小（Frame Anchor Drift）**：
   - 解决原理：传统工具按独立包围盒裁剪，导致带特效（如灵环、火焰、雷电）的帧角色被强制缩小。本工具实行**全局绝对坐标系锁定**，保证人物身体、莲座在所有关键帧中 1:1 绝对等大。
3. **1px 闭合硬描边（Pixel-Perfect Solid Outlines）**：
   - 纯正独立复古像素游戏（Mushreb 风格）核心美学，消除平滑模糊，给实体轮廓边缘施加严格 1px 正交闭合黑色描边。
4. **十阶修仙法宝与背景粒子流光体系**：
   - 独创修仙小说法宝矩阵生成器，支持 8 大部位装备 × 10 阶品质自动化生成，并绑定对应的背景粒子色彩规范。

---

## 🔮 修仙小说顶级法宝提示词生图规范 (Prompt Engineering)

在生成修仙游戏法宝时，必须遵照以下提示词结构，确保具备**强烈的神兵辨识度**与**纯正 16-bit 像素硬边游戏道具质感**：

```text
16-bit retro pixel art game icon of a [小说法宝名称及特征], 
floating on a dark neutral background, 
[核心材质与色调: 如 cold steel blade / celestial indigo silk], 
[道家符文/阵法细节: 如 engraved ancient golden Taoist runes / Bagua yin-yang seal], 
[悬浮配饰与灵光: 如 swaying red silk tassel / floating spirit aura / lightning sparks], 
clean solid 1px dark pixel outline, high contrast vibrant retro RPG equipment item sprite, 
crisp pixelated edges, authentic pixel art game asset
```

### 经典实测提示词范例（见 `examples/`）:
1. **太虚斩仙剑** (`examples/divine_flying_sword.jpg`):
   - 寒铁冰青剑身、暗刻流金五雷真言、盘龙金吞口、悬垂血玉真丝剑穗与护身灵符、幽蓝雷芒飞旋。
2. **乾坤混元道袍** (`examples/celestial_daoist_robe.jpg`):
   - 星空幽蓝软缎、胸前金纹太极八卦印、祥云翻浪大袖、青玉佩带与朱红流苏、青碧仙雾缭绕。
3. **太阴八卦玄光镜** (`examples/bagua_spirit_mirror.jpg`):
   - 八方青铜碧玉八卦卦象外框、太极星河镜面、底悬翠玉小灵葫与辟邪流苏。

---

## 🌈 十阶品质与背景粒子色彩矩阵规范 (Ten Tiers & Particle System)

游戏装备共分为十阶，在展示时必须**按照背景粒子颜色**进行严格区分：

| 阶位 | 品阶名称 | 主色调基底 | 背景粒子颜色 (RGB / HEX) | 意象与材质 |
| :--- | :--- | :--- | :--- | :--- |
| **一阶** | **凡品** | 灰铁黑石 | `140, 140, 140` (`#8c8c8c`) | 灰白微屑、凡铁砂石 |
| **二阶** | **良品** | 苍翠林绿 | `82, 196, 26` (`#52c41a`) | 草木灵芽、生机微粒 |
| **三阶** | **灵品** | 碧青温玉 | `19, 194, 194` (`#13c2c2`) | 灵泉碧玉、幽潭水韵 |
| **四阶** | **玄品** | 幽蓝寒铁 | `22, 119, 255` (`#1677ff`) | 寒冰星屑、玄冥雷芒 |
| **五阶** | **地品** | 地脉厚土 | `212, 136, 6` (`#d48806`) | 地元真金、黄铜重山 |
| **六阶** | **天品** | 紫霄天罡 | `114, 46, 209` (`#722ed1`) | 紫气东来、天罡雷晶 |
| **七阶** | **宝品** | 琉璃琼霞 | `235, 47, 150` (`#eb2f96`) | 宝阁朱霞、赤曜灵珠 |
| **八阶** | **仙品** | 朱雀真炎 | `245, 34, 45` (`#f5222d`) | 焚天真火、赤霄仙焰 |
| **九阶** | **神品** | 太古金芒 | `250, 173, 20` (`#faad14`) | 太阳真金、九天圣晖 |
| **十阶** | **混沌** | 鸿蒙极光 | `190, 80, 255` (`#be50ff`) | 太虚极光、紫金混沌旋流 |

---

## 🚀 快速开始

### 1. 安装环境依赖
```bash
pip install rembg opencv-python pillow numpy onnxruntime
```

### 2. 自动化生成 8 大部位 × 10 阶品质装备矩阵 (80 个资产)
```bash
python generate_pixel_equipment.py
```
- 自动生成 80 个单图 PNG (32×32 纯像素与 96×96 高清Retina)
- 自动生成 10 阶装备整合精灵大图 `equip_sheet_96.png`
- 自动导出带有粒子颜色、色值与名称的 `tier_manifest.json`

### 3. 单张 AI 伪像素资产清洗转真像素
```bash
python true_pixel.py --input raw_character.png --output clean_character.png --colors 36
```

### 4. 8 帧角色动画精灵图（九宫格）坐标锁定与硬描边加持
```bash
python build_outlined_spritesheet.py
```

---

## 🛠️ 脚本结构与清单

- [`true_pixel.py`](true_pixel.py): 核心 AI 抠图、形态学腐蚀消脏边与色板规整引擎
- [`build_outlined_spritesheet.py`](build_outlined_spritesheet.py): 8 帧打坐仙子中轴对齐与 1px 闭合深黑硬描边发生器
- [`generate_pixel_equipment.py`](generate_pixel_equipment.py): 8 大部位装备 × 10 阶品质矩阵发生器
- `examples/`: 经典修仙小说法宝参考原画与大图合集

---

## 📄 License
MIT License
