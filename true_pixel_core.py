"""
TruePixel Core Engine
---------------------
Production-Grade AI to True-Pixel Conversion Pipeline:
1. AI Background Removal (rembg)
2. Alpha Morphology & Defringing
3. Isolated Floating Noise Debris Filter
4. Bounding Box Centering & Scale to Target Resolution
5. 16-Bit Color Palette Quantization
6. Strict 1px Orthogonal Solid Pixel Outline (Pixel-Perfect)
7. Nearest-Neighbor Integer Scaling (2x / 4x / 8x for display)
"""

import io
from typing import Tuple, Optional
from PIL import Image
import numpy as np
import cv2
import rembg


def add_solid_pixel_outline(rgba_arr: np.ndarray, outline_color: Tuple[int, int, int] = (18, 20, 26)) -> np.ndarray:
    """Apply strict 1px orthogonal solid pixel outline to alpha boundaries."""
    h, w = rgba_arr.shape[:2]
    alpha = rgba_arr[:, :, 3]

    edge_mask = np.zeros((h, w), dtype=bool)
    for y in range(h):
        for x in range(w):
            if alpha[y, x] > 0:
                for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w:
                        if alpha[ny, nx] == 0:
                            edge_mask[y, x] = True
                            break
                    else:
                        edge_mask[y, x] = True
                        break

    out = rgba_arr.copy()
    out[edge_mask, 0] = outline_color[0]
    out[edge_mask, 1] = outline_color[1]
    out[edge_mask, 2] = outline_color[2]
    out[edge_mask, 3] = 255
    return out


def remove_isolated_noise_pixels(rgba_arr: np.ndarray, min_area: int = 18) -> np.ndarray:
    """Filter out isolated floating debris and single-pixel specks from AI background removal."""
    if min_area <= 0:
        return rgba_arr
    alpha = rgba_arr[:, :, 3]
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats((alpha > 0).astype(np.uint8))
    out = rgba_arr.copy()
    for i in range(1, num_labels):
        if stats[i, cv2.CC_STAT_AREA] <= min_area:
            out[labels == i] = 0
    return out


_REMBG_SESSION = None

def get_rembg_session():
    global _REMBG_SESSION
    if _REMBG_SESSION is None:
        _REMBG_SESSION = rembg.new_session("u2net")
    return _REMBG_SESSION

def process_image(
    input_image: Image.Image,
    target_size: int = 96,
    color_count: int = 32,
    remove_bg: bool = True,
    apply_outline: bool = True,
    outline_color: Tuple[int, int, int] = (18, 20, 26),
    noise_filter_area: int = 18,
    erosion_iter: int = 1
) -> Tuple[Image.Image, Image.Image]:
    """
    Main processing pipeline.
    Returns:
        (native_pixel_image, preview_4x_image)
    """
    raw_rgba = input_image.convert("RGBA")

    # Safety: downsample excessively huge inputs to max 1024px before background removal
    w, h = raw_rgba.size
    if max(w, h) > 1024:
        factor = 1024.0 / max(w, h)
        raw_rgba = raw_rgba.resize((int(w * factor), int(h * factor)), Image.Resampling.LANCZOS)

    # 1. Background removal
    if remove_bg:
        session = get_rembg_session()
        # post_process_mask=False 避免大面积连通域形态学腐蚀吃掉发光光环与火焰
        nobg = rembg.remove(raw_rgba, session=session, post_process_mask=False)
        arr = np.array(nobg)

        # 智能色彩保底保护 (Smart Foreground Rescue)：
        # 当原图具有统一纯色/暗色背景，但 AI 抠图模型将强光晕/角色误判为背景吃掉时，自动基于背景色差恢复前景
        raw_arr = np.array(raw_rgba)
        corner_pixels = np.vstack([
            raw_arr[:15, :15, :3].reshape(-1, 3),
            raw_arr[:15, -15:, :3].reshape(-1, 3),
            raw_arr[-15:, :15, :3].reshape(-1, 3),
            raw_arr[-15:, -15:, :3].reshape(-1, 3)
        ])
        bg_color = np.median(corner_pixels, axis=0)
        # 背景一致性校验：四个角标准差较低说明是统一纯色/中性背景
        bg_std = np.std(corner_pixels, axis=0).mean()
        if bg_std < 25:
            color_dist = np.linalg.norm(raw_arr[:, :, :3] - bg_color, axis=2)
            # 色差显著大于背景且被 rembg 误降透明度/清零RGB的像素，予以保底唤醒并恢复原色
            mistakenly_erased = (color_dist > 25) & (arr[:, :, 3] < 120)
            if np.any(mistakenly_erased):
                arr[mistakenly_erased, :3] = raw_arr[mistakenly_erased, :3]
                arr[mistakenly_erased, 3] = np.clip(color_dist[mistakenly_erased] * 5, 180, 255).astype(np.uint8)
    else:
        arr = np.array(raw_rgba)

    # 2. Defringe and alpha erosion (if image has alpha)
    has_alpha = np.any(arr[:, :, 3] < 255)
    if has_alpha:
        alpha = arr[:, :, 3]
        mask = alpha >= 100
        alpha_clean = np.where(mask, 255, 0).astype(np.uint8)

        if erosion_iter > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
            alpha_clean = cv2.erode(alpha_clean, kernel, iterations=erosion_iter)

        arr[:, :, 3] = alpha_clean
        arr[alpha_clean == 0, :3] = 0

        # Filter isolated noise
        arr = remove_isolated_noise_pixels(arr, min_area=noise_filter_area)

    clean_img = Image.fromarray(arr, mode="RGBA")
    bbox = clean_img.getbbox()
    if bbox:
        cropped = clean_img.crop(bbox)
    else:
        cropped = clean_img

    # 3. Fit into target square canvas preserving aspect ratio
    cw, ch = cropped.size
    # Reserve 2px margin (1px each side) only if outline is needed, maximizing sprite detail
    margin = 2 if apply_outline else 0
    fit_size = max(1, target_size - margin)
    scale = fit_size / max(cw, ch)
    nw = max(1, int(round(cw * scale)))
    nh = max(1, int(round(ch * scale)))

    # High quality downsampling before quantization
    resized = cropped.resize((nw, nh), Image.Resampling.LANCZOS)

    # 4. Color Palette Quantization
    if has_alpha:
        r, g, b, a = resized.split()
        # Strictly binarize alpha to eliminate fuzzy Lanczos edges for authentic solid pixel art
        a_arr = np.array(a)
        a_clean_mask = np.where(a_arr >= 128, 255, 0).astype(np.uint8)
        a_clean = Image.fromarray(a_clean_mask, mode="L")

        rgb = Image.merge("RGB", (r, g, b))
        q_rgb = rgb.quantize(colors=color_count, method=Image.Quantize.MEDIANCUT).convert("RGB")
        quantized = Image.merge("RGBA", (*q_rgb.split(), a_clean))
    else:
        quantized = resized.convert("RGB").quantize(colors=color_count, method=Image.Quantize.MEDIANCUT).convert("RGBA")

    # 5. Center onto target canvas
    canvas = Image.new("RGBA", (target_size, target_size), (0, 0, 0, 0))
    offset_x = (target_size - nw) // 2
    offset_y = (target_size - nh) // 2
    canvas.paste(quantized, (offset_x, offset_y), quantized)

    # 6. Strict 1px Solid Pixel Outline
    if apply_outline and has_alpha:
        c_arr = np.array(canvas)
        outlined_arr = add_solid_pixel_outline(c_arr, outline_color=outline_color)
        native_img = Image.fromarray(outlined_arr, mode="RGBA")
    else:
        native_img = canvas

    # 7. Nearest-Neighbor HD Preview (clamped to max 2048 to prevent excessive payload)
    preview_scale = 4 if target_size <= 256 else (2 if target_size <= 512 else 1)
    preview_w = target_size * preview_scale
    preview_4x = native_img.resize((preview_w, preview_w), Image.Resampling.NEAREST)

    return native_img, preview_4x


def process_vfx_image(
    input_image: Image.Image,
    target_size: int = 96,
    color_count: int = 32,
    black_threshold: int = 15,
    glow_gain: float = 1.15
) -> Tuple[Image.Image, Image.Image]:
    """
    Extract glowing VFX sprite (Aura / Lightning / Magic Flame) from pure black, dark,
    or chroma-green background.
    Uses Luminance-to-Alpha + Unmultiply & De-spill algorithms.
    Preserves 100% subtle lightning arcs and star sparks without dark edge bleed or black outlines.
    """
    img_rgb = input_image.convert("RGB")
    arr = np.array(img_rgb, dtype=np.float32)
    h, w = arr.shape[:2]
    r = arr[:, :, 0]
    g = arr[:, :, 1]
    b = arr[:, :, 2]

    # Sample corners to detect background type
    corners = np.vstack([
        arr[0:min(10, h), 0:min(10, w)].reshape(-1, 3),
        arr[0:min(10, h), max(0, w-10):w].reshape(-1, 3),
        arr[max(0, h-10):h, 0:min(10, w)].reshape(-1, 3),
        arr[max(0, h-10):h, max(0, w-10):w].reshape(-1, 3)
    ])
    bg_mean = np.median(corners, axis=0)

    # Detect chroma green screen: G is high and significantly dominates R & B
    is_chroma_green = (bg_mean[1] > 120 and bg_mean[1] > bg_mean[0] + 40 and bg_mean[1] > bg_mean[2] + 40)

    if is_chroma_green:
        # Chroma green de-spill & alpha extraction
        dist = np.linalg.norm(arr - bg_mean, axis=2)
        alpha = np.clip((dist - 18.0) / 45.0 * 255.0 * glow_gain, 0.0, 255.0)

        # De-spill excess green on foreground pixels
        g_max_other = np.maximum(r, b)
        g_clean = np.where(alpha > 0, np.minimum(g, g_max_other * 1.25 + 15), g)
        r_clean = r
        b_clean = b
    else:
        # Standard black/dark background VFX extraction (Luminance to Alpha + Unmultiply)
        luma = 0.299 * r + 0.587 * g + 0.114 * b
        bg_luma = 0.299 * bg_mean[0] + 0.587 * bg_mean[1] + 0.114 * bg_mean[2]
        effective_thresh = max(black_threshold, bg_luma + 5)

        alpha = np.clip((luma - effective_thresh) / np.maximum(1.0, 255.0 - effective_thresh) * 255.0 * glow_gain, 0.0, 255.0)

        # Unmultiply colors to eliminate dark halos from fading into black
        safe_a = np.maximum(alpha / 255.0, 1e-4)
        r_clean = np.clip(r / safe_a, 0.0, 255.0)
        g_clean = np.clip(g / safe_a, 0.0, 255.0)
        b_clean = np.clip(b / safe_a, 0.0, 255.0)

    rgba_out = np.dstack([r_clean, g_clean, b_clean, alpha]).astype(np.uint8)
    clean_img = Image.fromarray(rgba_out, mode="RGBA")

    bbox = clean_img.getbbox()
    if bbox:
        cropped = clean_img.crop(bbox)
    else:
        cropped = clean_img

    cw, ch = cropped.size
    fit_size = target_size
    scale = fit_size / max(cw, ch)
    nw = max(1, int(round(cw * scale)))
    nh = max(1, int(round(ch * scale)))

    resized = cropped.resize((nw, nh), Image.Resampling.LANCZOS)

    # Color quantization while preserving smooth glow alpha
    r_c, g_c, b_c, a_c = resized.split()
    rgb_temp = Image.merge("RGB", (r_c, g_c, b_c))
    q_rgb = rgb_temp.quantize(colors=color_count, method=Image.Quantize.MEDIANCUT).convert("RGB")
    quantized = Image.merge("RGBA", (*q_rgb.split(), a_c))

    # Center onto target canvas
    canvas = Image.new("RGBA", (target_size, target_size), (0, 0, 0, 0))
    offset_x = (target_size - nw) // 2
    offset_y = (target_size - nh) // 2
    canvas.paste(quantized, (offset_x, offset_y), quantized)

    preview_scale = 4 if target_size <= 256 else (2 if target_size <= 512 else 1)
    preview_w = target_size * preview_scale
    preview_4x = canvas.resize((preview_w, preview_w), Image.Resampling.NEAREST)

    return canvas, preview_4x


def composite_layers(
    solid_img: Image.Image,
    vfx_img: Image.Image,
    glow_intensity: float = 1.15,
    blend_mode: str = "additive",
    offset_x: int = 0,
    offset_y: int = 0,
    layer_order: str = "vfx_on_top"
) -> Image.Image:
    """
    Composite Layer 1 (Solid Weapon/Item) and Layer 2 (Glowing Aura/VFX) with game-engine grade blending.
    Supports movable VFX offset (offset_x, offset_y) and layer stacking order (vfx_on_top vs solid_on_top).
    """
    tw, th = solid_img.size
    if vfx_img.size != (tw, th):
        vfx_img = vfx_img.resize((tw, th), Image.Resampling.NEAREST)

    # Apply translation offset to VFX layer if requested
    if offset_x != 0 or offset_y != 0:
        vfx_shifted = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        vfx_shifted.paste(vfx_img, (offset_x, offset_y), vfx_img)
        vfx_img = vfx_shifted

    s_arr = np.array(solid_img.convert("RGBA"), dtype=np.float32)
    v_arr = np.array(vfx_img.convert("RGBA"), dtype=np.float32)

    sr, sg, sb, sa = s_arr[:, :, 0], s_arr[:, :, 1], s_arr[:, :, 2], s_arr[:, :, 3] / 255.0
    vr, vg, vb, va = v_arr[:, :, 0], v_arr[:, :, 1], v_arr[:, :, 2], (v_arr[:, :, 3] / 255.0) * glow_intensity
    va = np.clip(va, 0.0, 1.0)

    is_solid_top = (layer_order == "solid_on_top")

    if blend_mode == "additive":
        if is_solid_top:
            # Solid in front, glowing VFX shines behind and around solid
            cr = np.clip(sr * sa + vr * va * (1.0 - sa * 0.7), 0.0, 255.0)
            cg = np.clip(sg * sa + vg * va * (1.0 - sa * 0.7), 0.0, 255.0)
            cb = np.clip(sb * sa + vb * va * (1.0 - sa * 0.7), 0.0, 255.0)
            ca = np.clip(sa + va * (1.0 - sa), 0.0, 1.0) * 255.0
        else:
            # VFX illuminates on top of solid & background
            cr = np.clip(sr * sa + vr * va, 0.0, 255.0)
            cg = np.clip(sg * sa + vg * va, 0.0, 255.0)
            cb = np.clip(sb * sa + vb * va, 0.0, 255.0)
            ca = np.clip(sa + va * (1.0 - sa * 0.4), 0.0, 1.0) * 255.0
    elif blend_mode == "screen":
        if is_solid_top:
            screen_r = 255.0 * (1.0 - (1.0 - (sr * sa / 255.0)) * (1.0 - (vr * va / 255.0)))
            screen_g = 255.0 * (1.0 - (1.0 - (sg * sa / 255.0)) * (1.0 - (vr * va / 255.0)))
            screen_b = 255.0 * (1.0 - (1.0 - (sb * sa / 255.0)) * (1.0 - (vr * va / 255.0)))
            cr = sr * sa + screen_r * (1.0 - sa)
            cg = sg * sa + screen_g * (1.0 - sa)
            cb = sb * sa + screen_b * (1.0 - sa)
            ca = np.clip(sa + va * (1.0 - sa), 0.0, 1.0) * 255.0
        else:
            cr = 255.0 * (1.0 - (1.0 - (sr * sa / 255.0)) * (1.0 - (vr * va / 255.0)))
            cg = 255.0 * (1.0 - (1.0 - (sg * sa / 255.0)) * (1.0 - (vr * va / 255.0)))
            cb = 255.0 * (1.0 - (1.0 - (sb * sa / 255.0)) * (1.0 - (vr * va / 255.0)))
            ca = np.clip(sa + va, 0.0, 1.0) * 255.0
    else:  # normal alpha blend
        if is_solid_top:
            # Solid placed on top of VFX
            cr = sr * sa + vr * va * (1.0 - sa)
            cg = sg * sa + vg * va * (1.0 - sa)
            cb = sb * sa + vb * va * (1.0 - sa)
            ca = (sa + va * (1.0 - sa)) * 255.0
        else:
            # VFX placed on top of solid
            cr = vr * va + sr * sa * (1.0 - va)
            cg = vg * va + sg * sa * (1.0 - va)
            cb = vb * va + sb * sa * (1.0 - va)
            ca = (va + sa * (1.0 - va)) * 255.0

    comp = np.dstack([cr, cg, cb, ca]).astype(np.uint8)
    return Image.fromarray(comp, mode="RGBA")
