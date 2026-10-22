"""
高层处理流程：实体素材、发光特效、双层合成、动画精灵表。
web 服务、命令行和批处理都只调用这里的函数。
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
from PIL import Image

from . import ops
from .background import remove_background
from .ops import Color, DEFAULT_OUTLINE


# ================================================================ 实体素材

def process_image(
    input_image: Image.Image,
    target_size: int = 96,
    color_count: int = 32,
    remove_bg: bool = True,
    apply_outline: bool = True,
    outline_color: Color = DEFAULT_OUTLINE,
    noise_filter_area: int = 18,
    erosion_iter: int = 1,
    post_process_mask: bool = False,
    alpha_threshold: int = 100,
    palette: Optional[np.ndarray] = None,
    preview_scale: Optional[int] = None,
    content_size: Optional[int] = None,
) -> Tuple[Image.Image, Image.Image]:
    """
    AI 原图 → 真像素实体素材（武器、道具、角色、UI）。
    content_size：主体最长边占多少像素（默认 target_size，描边时留 2px）。
    例如装备图标常用 content_size=78、target_size=96，四周留出呼吸空间。
    返回 (原生尺寸成品, 最近邻放大预览)。

    步骤：抠图 → 透明度二值化+腐蚀去暗边 → 去飞屑 → 裁到内容 → 等比缩放居中
         → 减色（或映射到 palette）→ 1px 描边
    remove_bg=False 且原图无透明通道时（如地图图块），跳过抠图/描边，直接铺满画布。
    """
    raw = ops.limit_size(input_image.convert("RGBA"))
    arr = remove_background(raw, post_process_mask) if remove_bg else np.array(raw)

    has_alpha = bool(np.any(arr[:, :, 3] < 255))
    if has_alpha:
        arr = ops.harden_alpha(arr, alpha_threshold, erosion_iter)
        arr = ops.remove_specks(arr, noise_filter_area)

    content = ops.crop_to_content(Image.fromarray(arr, "RGBA"))
    box = content_size if content_size else target_size - (2 if apply_outline else 0)
    resized = content.resize(
        ops.fit_size(content.width, content.height, max(1, min(box, target_size))),
        Image.Resampling.LANCZOS,
    )
    if has_alpha:
        resized = ops.binarize_alpha(resized, 128)
    quantized = ops.quantize(resized, color_count, palette)

    native = ops.paste_centered(quantized, target_size)
    if apply_outline and has_alpha:
        native = Image.fromarray(ops.add_outline(np.array(native), outline_color), "RGBA")
        if palette is not None:
            native = Image.fromarray(ops.map_to_palette(np.array(native), palette), "RGBA")

    return native, ops.preview(native, preview_scale)


# ================================================================ 发光特效

def process_vfx_image(
    input_image: Image.Image,
    target_size: int = 96,
    color_count: int = 32,
    black_threshold: int = 15,
    glow_gain: float = 1.15,
    preview_scale: Optional[int] = None,
) -> Tuple[Image.Image, Image.Image]:
    """
    从纯黑/暗色或绿幕背景提取发光特效（剑气、雷光、火焰），保留柔和半透明光晕。
    暗背景：亮度转透明度 + 反预乘去黑边；绿幕：色差抠像 + 去绿溢色。
    """
    arr = np.array(input_image.convert("RGB"), dtype=np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    bg = np.median(ops.corner_samples(arr, 10), axis=0)

    is_green = bg[1] > 120 and bg[1] > bg[0] + 40 and bg[1] > bg[2] + 40
    if is_green:
        dist = np.linalg.norm(arr - bg, axis=2)
        alpha = np.clip((dist - 18.0) / 45.0 * 255.0 * glow_gain, 0.0, 255.0)
        g = np.where(alpha > 0, np.minimum(g, np.maximum(r, b) * 1.25 + 15), g)
    else:
        luma = 0.299 * r + 0.587 * g + 0.114 * b
        bg_luma = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]
        thresh = max(black_threshold, bg_luma + 5)
        alpha = np.clip((luma - thresh) / max(1.0, 255.0 - thresh) * 255.0 * glow_gain, 0.0, 255.0)
        safe_a = np.maximum(alpha / 255.0, 1e-4)
        r, g, b = (np.clip(c / safe_a, 0.0, 255.0) for c in (r, g, b))

    img = Image.fromarray(np.dstack([r, g, b, alpha]).astype(np.uint8), "RGBA")
    content = ops.crop_to_content(img)
    resized = content.resize(ops.fit_size(content.width, content.height, target_size), Image.Resampling.LANCZOS)
    native = ops.paste_centered(ops.quantize(resized, color_count), target_size)
    return native, ops.preview(native, preview_scale)


# ================================================================ 双层合成

def _transform_vfx(vfx: Image.Image, size: Tuple[int, int], offset_x: int, offset_y: int,
                   scale_x: float, scale_y: float, rotation: float) -> Image.Image:
    tw, th = size
    if vfx.size != size:
        vfx = vfx.resize(size, Image.Resampling.NEAREST)
    if scale_x != 1.0 or scale_y != 1.0 or rotation != 0.0:
        v = vfx.resize((max(1, int(round(tw * scale_x))), max(1, int(round(th * scale_y)))),
                       Image.Resampling.BILINEAR)
        if rotation != 0.0:
            v = v.rotate(-rotation, resample=Image.Resampling.BILINEAR, expand=True)  # 顺时针
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        canvas.paste(v, ((tw - v.width) // 2 + offset_x, (th - v.height) // 2 + offset_y), v)
        return canvas
    if offset_x or offset_y:
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        canvas.paste(vfx, (offset_x, offset_y), vfx)
        return canvas
    return vfx


def composite_layers(
    solid_img: Image.Image,
    vfx_img: Image.Image,
    glow_intensity: float = 1.15,
    blend_mode: str = "additive",
    offset_x: int = 0,
    offset_y: int = 0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    rotation: float = 0.0,
    canvas_padding: float = 0.0,
    layer_order: str = "vfx_on_top",
) -> Image.Image:
    """
    图层 1（实体）+ 图层 2（发光特效）合成。
    blend_mode: additive | screen | normal；layer_order: vfx_on_top | solid_on_top。
    canvas_padding > 0 时按比例扩大画布，防止旋转/放大的特效被裁掉。
    """
    solid_img = solid_img.convert("RGBA")
    tw, th = solid_img.size
    pad = int(round(tw * canvas_padding / 2)) if canvas_padding > 0 else 0
    if pad > 0:
        bigger = Image.new("RGBA", (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
        bigger.paste(solid_img, (pad, pad), solid_img)
        solid_img, tw, th = bigger, tw + 2 * pad, th + 2 * pad

    vfx_img = _transform_vfx(vfx_img.convert("RGBA"), (tw, th), offset_x, offset_y, scale_x, scale_y, rotation)

    s = np.array(solid_img, dtype=np.float32)
    v = np.array(vfx_img, dtype=np.float32)
    s_rgb, sa = s[:, :, :3], s[:, :, 3:4] / 255.0
    v_rgb, va = v[:, :, :3], np.clip(v[:, :, 3:4] / 255.0 * glow_intensity, 0.0, 1.0)
    solid_top = layer_order == "solid_on_top"

    if blend_mode == "additive":
        if solid_top:
            rgb = s_rgb * sa + v_rgb * va * (1.0 - sa * 0.7)
            a = sa + va * (1.0 - sa)
        else:
            rgb = s_rgb * sa + v_rgb * va
            a = sa + va * (1.0 - sa * 0.4)
    elif blend_mode == "screen":
        screen = 255.0 * (1.0 - (1.0 - s_rgb * sa / 255.0) * (1.0 - v_rgb * va / 255.0))
        if solid_top:
            rgb = s_rgb * sa + screen * (1.0 - sa)
            a = sa + va * (1.0 - sa)
        else:
            rgb = screen
            a = sa + va
    else:  # normal
        if solid_top:
            rgb = s_rgb * sa + v_rgb * va * (1.0 - sa)
            a = sa + va * (1.0 - sa)
        else:
            rgb = v_rgb * va + s_rgb * sa * (1.0 - va)
            a = va + sa * (1.0 - va)

    out = np.dstack([np.clip(rgb, 0, 255), np.clip(a, 0.0, 1.0) * 255.0]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


# ================================================================ 动画精灵表

def process_sheet(
    sheet: Image.Image,
    rows: int = 3,
    cols: int = 3,
    frames: int = 8,
    frame_size: int = 96,
    color_count: int = 32,
    outline: bool = True,
    outline_color: Color = DEFAULT_OUTLINE,
    palette: Optional[np.ndarray] = None,
    body_ratio: float = 80 / 96,
    baseline_margin: int = 3,
    speck_area: int = 6,
) -> Tuple[Image.Image, List[Image.Image]]:
    """
    AI 生成的网格动画图（如 3×3 九宫格）→ 1×N 横向真像素精灵表。

    固定锚点：所有帧都用第 0 帧的缩放比例和脚底中心点对齐，
    保证角色在每一帧里大小一致、不抖动、不漂移。
    返回 (横向精灵表, 单帧列表)。
    """
    sheet = sheet.convert("RGBA")
    cw, ch = sheet.width // cols, sheet.height // rows

    cells = []
    for i in range(frames):
        c, r = i % cols, i // cols
        cell = sheet.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch))
        arr = ops.harden_alpha(remove_background(cell, post_process_mask=True), 120, 1)
        cells.append(Image.fromarray(arr, "RGBA"))

    ref = cells[0].getbbox() or (0, 0, cw, ch)
    scale = (frame_size * body_ratio) / max(ref[2] - ref[0], ref[3] - ref[1])
    ref_cx, ref_bottom = (ref[0] + ref[2]) / 2.0, ref[3]
    paste_x = int(frame_size / 2 - ref_cx * scale)
    paste_y = int(frame_size - baseline_margin - ref_bottom * scale)

    out_frames = []
    for cell in cells:
        scaled = cell.resize((int(cell.width * scale), int(cell.height * scale)), Image.Resampling.BILINEAR)
        frame = Image.new("RGBA", (frame_size, frame_size), (0, 0, 0, 0))
        frame.paste(scaled, (paste_x, paste_y), scaled)
        frame = ops.quantize(ops.binarize_alpha(frame, 128, zero_rgb=True), color_count, palette)
        arr = np.array(frame)
        if outline:
            arr = ops.add_outline(arr, outline_color)
        arr = ops.remove_specks(arr, speck_area)
        out_frames.append(Image.fromarray(arr, "RGBA"))

    strip = Image.new("RGBA", (frame_size * frames, frame_size), (0, 0, 0, 0))
    for i, f in enumerate(out_frames):
        strip.paste(f, (i * frame_size, 0))
    return strip, out_frames
