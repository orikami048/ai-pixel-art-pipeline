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

    # 1. Background removal
    if remove_bg:
        nobg = rembg.remove(raw_rgba, post_process_mask=True)
        arr = np.array(nobg)
    else:
        arr = np.array(raw_rgba)

    # 2. Defringe and alpha erosion (if image has alpha)
    has_alpha = np.any(arr[:, :, 3] < 255)
    if has_alpha:
        alpha = arr[:, :, 3]
        mask = alpha >= 120
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

    # 7. 4x Nearest-Neighbor HD Preview
    preview_4x = native_img.resize((target_size * 4, target_size * 4), Image.Resampling.NEAREST)

    return native_img, preview_4x
