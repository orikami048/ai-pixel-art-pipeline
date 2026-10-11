# TruePixel Engine 🎨

> **Production-Grade AI Fake-Pixel to True-Pixel Game Asset Pipeline**  
> 一键将 AI（Midjourney / DALL-E / Stable Diffusion）生成的“伪像素”图像转化为真正纯净、可直接进游戏引擎的真像素透明 PNG 与动画精灵序列图（Sprite Sheet）。

---

## 🌟 核心解决的技术痛点

1. **暗色黑边杂色（Dark Edge Fringing & Bleeding）**：
   - 解决原理：AI 在深色底上生成的半透明羽化边缘会导致残存 1~2px 的暗灰色噪点。本工具采用 OpenCV 图像形态学侵蚀（Alpha Erosion）结合 Decontamination 算法，彻底切除杂色黑轮廓。
2. **多帧动画尺寸忽大忽小（Frame Anchor Drift）**：
   - 解决原理：传统工具按独立包围盒裁剪，导致带特效（如灵环、火焰、雷电）的帧角色被强制缩小。本工具实行**全局绝对坐标系锁定**，保证人物身体、莲座在所有关键帧中 1:1 绝对等大。
3. **网格规整与色板保真（Pixel Quantization）**：
   - 自适应保留角色的面部微表情、眼睛高光与道袍细节，规整为正统复古像素风。

---

## 🚀 快速开始

### 1. 环境依赖安装
```bash
pip install rembg opencv-python pillow numpy onnxruntime
```

### 2. 单张资产转换
```bash
python true_pixel.py --input raw_character.png --output clean_character.png --colors 36
```

### 3. 多帧精灵图（九宫格/序列图）全自动对齐转换
```bash
python true_pixel.py --input anime_spritesheet.jpg --output spritesheet_clean.png --sheet --rows 3 --cols 3 --frames 8 --colors 36
```

---

## 🛠️ 参数说明

| 参数 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `--input, -i` | 必需 | 输入的 AI 伪像素图片路径 |
| `--output, -o` | 必需 | 输出的透明真像素 PNG 路径 |
| `--sheet` | False | 是否作为多帧动画精灵图（Sprite Sheet）处理 |
| `--rows` | 3 | 九宫格行数 |
| `--cols` | 3 | 九宫格列数 |
| `--frames` | 8 | 有效动画帧数 |
| `--colors, -c` | 36 | 目标限制色板数量（安全保护眼睛与微细节） |

---

## 📄 License
MIT License
