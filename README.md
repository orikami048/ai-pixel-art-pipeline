# TruePixel Studio 🎨

> **Production-Grade AI Fake-Pixel to True-Pixel Game Asset Pipeline**  
> 一键将 AI（Midjourney / DALL-E / Imagen / Stable Diffusion）生成的“伪像素”图像转化为真正纯净、可直接导入游戏引擎（Unity / Unreal / Godot / Cocos）的真像素透明 PNG 与精灵图资产。支持开箱即用的拖拽式 Web 交互界面与批量导出。

---

## 🌟 核心解决的技术痛点

1. **暗色黑边杂色（Dark Edge Fringing & Bleeding）**：
   - AI 在生成像素道具时常自带渐变半透明羽化边缘与背景污染，导致直接抠图后出现 1~2px 灰黑噪点圈。本引擎采用 OpenCV 图像形态学侵蚀（Alpha Erosion）结合 Decontamination 算法，彻底切除杂色伪边。
2. **AI“伪像素”平滑与混色（Fake Pixel Quantization）**：
   - AI 生成图并非真正像素，而是带有抗锯齿抗混叠的连续高分图像。本引擎提供智能色彩聚类降阶（Median Cut / Color Palette Quantization），还原 8/16/24/32 经典复古色板。
3. **1px 闭合硬描边（Pixel-Perfect Solid Outlines）**：
   - 提取实体不透明区域的边缘拓扑，施加严格 1px 经典正交（Orthogonal 4-Connectivity）闭合黑色描边，确保纯正复古独立游戏（Chucklefish / Terraria 风格）的高对比度边缘辨识度。
4. **孤立噪点过滤与画幅居中对齐（De-noising & Centering）**：
   - 自动滤除 AI 背景剥离后残留的零星孤立悬浮像素（Speckle Filter），并自动计算实体最小包围盒并在目标画布（如 32×32、64×64）中完成自适应等比缩放与居中。

---

## 🖥️ 现代化拖拽式 Web 前端 (TruePixel Web Studio)

内置零外部重量级依赖（无需安装 Node.js/Vue，直接基于 Python 原生轻量服务）的沉浸式暗黑游戏风 Web 控制台。

### 一键启动
```bash
python app.py
```
终端启动后在浏览器打开：**`http://localhost:7860`**

### 前端功能特性
- **🖱️ 拖拽即生成**：支持单图直接拖拽到画布、剪贴板粘贴或文件选择，毫秒级即时处理。
- **📦 批量处理托盘**：支持多张图片同时拖入，排队批量转换并一键打包下载 ZIP。
- **🎛️ 实时参数调优**：
  - **目标分辨率**：`32×32`（经典复古背包图标）、`48×48`、`64×64`（推荐）、`96×96`、`128×128`
  - **复古色板限制**：`8` ~ `64` 色滑块实时限制，还原真实硬件限制调色盘
  - **AI 智能去背景**：基于 rembg 深度学习模型自动剥离背景
  - **暗边切除强度**：`0` ~ `3px` 形态学收缩
  - **1px 闭合描边开关**：可自由开关并指定描边颜色（默认 `#000000` 纯黑）
  - **孤立噪点过滤**：自动清除 `< 15px` 的悬空杂色噪点
- **🔍 像素级对齐缩放预览**：支持 `1x`、`2x`、`4x`、`8x` 最近邻无损缩放（Nearest-Neighbor）并提供棋盘格透明底与原图/成品同屏对比。

---

## 🎨 通用游戏像素美术生图规范 (Universal Prompt Engineering)

AI 模型生图时，推荐使用以下结构化提示词模板，确保生成物具备**清晰的道具轮廓、高对比度与纯净背景**：

```text
16-bit retro pixel art game sprite of [道具/角色/怪物名称及特征], 
isolated on a dark neutral background, 
[核心材质与色调: 如 silver steel / glowing azure / crimson leather], 
[核心细节: 如 glowing runes / brass trim / ornate details], 
clean solid 1px dark pixel outline, high contrast vibrant retro RPG inventory icon, 
crisp pixelated edges, authentic pixel art game asset
```

### 经典品类提示词范例

| 资产类别 | 推荐 Prompt 片段 | 推荐目标分辨率 |
| :--- | :--- | :--- |
| **武器 (Weapon)** | `16-bit retro pixel art game sprite of a heavy steel greatsword with a glowing blue gem in the hilt, dark background, clean solid 1px pixel outline, authentic retro RPG item` | `64×64` 或 `96×96` |
| **防具 (Armor)** | `16-bit retro pixel art game icon of an ornate knight chestplate armor, golden trims, polished steel plate, dark neutral background, crisp pixelated edges` | `64×64` |
| **药水 (Potion)** | `16-bit retro pixel art potion bottle filled with swirling red health elixir, glass cork, vibrant bubbles, dark neutral background, clean pixel outline` | `32×32` 或 `48×48` |
| **宝箱 (Chest)** | `16-bit retro pixel art treasure chest, wooden planks with sturdy iron bands, glowing golden keyhole, dark background, crisp edges` | `48×48` 或 `64×64` |
| **法杖 (Staff)** | `16-bit retro pixel art wizard staff, twisted dark wood topped with a floating arcane purple crystal orb, emitting slight sparks, dark background` | `64×64` 或 `96×96` |

---

## 🚀 快速开始

### 1. 安装环境依赖
```bash
pip install -r requirements.txt
```
*(主要包含 `rembg`, `opencv-python`, `pillow`, `numpy`, `onnxruntime`)*

### 2. 启动图形化 Web UI
```bash
python app.py
```
访问 `http://localhost:7860` 体验完整交互。

### 3. 命令行 (CLI) 批处理与单图转换
```bash
# 单图转换（自动去背、居中缩放到 64px、限定 24 色并添加 1px 闭合描边）
python true_pixel.py --input raw_icon.png --output clean_icon.png --size 64 --colors 24
```

### 4. 角色动画序列大图整合 (Sprite Sheet)
```bash
python build_outlined_spritesheet.py
```

---

## 🛠️ 项目目录结构

```text
ai-pixel-art-pipeline/
├── app.py                     # Web Studio 后端服务 (轻量 HTTP Server)
├── true_pixel_core.py         # 核心像素处理引擎 (形态学去背、色板规整、1px描边)
├── true_pixel.py              # CLI 命令行处理入口
├── web/
│   └── index.html             # 现代化拖拽式像素工作室前端 (原生 HTML5 + CSS + JS)
├── build_outlined_spritesheet.py # 动画帧序列坐标对齐与拼图脚本
├── examples/                  # 示例参考原画与输出成果
├── requirements.txt           # Python 依赖项
└── README.md                  # 项目文档
```

---

## 📄 License
MIT License
