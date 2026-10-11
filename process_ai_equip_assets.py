"""
Pipeline: Convert High-Concept AI Artifact Images to True-Pixel Game Assets
--------------------------------------------------------------------------
1. Deep Learning Background Removal (rembg)
2. Connected Component Isolated Debris Filtering (cv2)
3. Tight Bounding Box Auto-Centering onto 96x96 Canvas
4. Color Quantization to Authentic 16-Bit Pixel Palette
5. Strict 1px Orthogonal Solid Pixel Outline (Pixel-Perfect)
6. 10-Tier Quality System Generation (凡/良/灵/玄/地/天/宝/仙/神/混沌)
"""

import os
from PIL import Image
import numpy as np
import rembg
import cv2


TIER_CONFIGS = {
    'fan':   {'name': '凡品', 'hue_shift': 0,    'sat_mult': 0.12, 'val_mult': 0.82, 'tint': [140, 140, 145]},     # 凡铁砂石
    'liang': {'name': '良品', 'hue_shift': -25,  'sat_mult': 0.55, 'val_mult': 0.92, 'tint': [110, 175, 130]},     # 素青灵木
    'ling':  {'name': '灵品', 'hue_shift': 15,   'sat_mult': 1.05, 'val_mult': 1.05, 'tint': [60, 215, 200]},      # 碧波温玉
    'xuan':  {'name': '玄品', 'hue_shift': 45,   'sat_mult': 1.15, 'val_mult': 1.0,  'tint': [60, 120, 245]},      # 幽蓝玄溟
    'di':    {'name': '地品', 'hue_shift': 85,   'sat_mult': 1.10, 'val_mult': 1.0,  'tint': [180, 75, 230]},       # 幽冥绛紫
    'tian':  {'name': '天品', 'hue_shift': -70,  'sat_mult': 1.25, 'val_mult': 1.10, 'tint': [250, 85, 45]},       # 离火赤天
    'bao':   {'name': '宝品', 'hue_shift': -50,  'sat_mult': 1.35, 'val_mult': 1.15, 'tint': [255, 200, 40]},      # 万宝灿金
    'xian':  {'name': '仙品', 'hue_shift': 0,    'sat_mult': 1.0,  'val_mult': 1.0,  'tint': None},                 # 顶级原画
    'shen':  {'name': '神品', 'hue_shift': 105,  'sat_mult': 1.35, 'val_mult': 1.20, 'tint': [245, 95, 255]},      # 太虚紫金
    'chaos': {'name': '混沌', 'hue_shift': -130, 'sat_mult': 1.35, 'val_mult': 1.25, 'tint': [160, 95, 255]},      # 鸿蒙混元
}


def add_solid_pixel_outline(rgba_arr: np.ndarray, outline_color=(18, 20, 26)) -> np.ndarray:
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


def remove_isolated_noise_pixels(rgba_arr: np.ndarray, min_area: int = 25) -> np.ndarray:
    """Filter out floating specks/debris from background removal."""
    alpha = rgba_arr[:, :, 3]
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats((alpha > 0).astype(np.uint8))
    out = rgba_arr.copy()
    for i in range(1, num_labels):
        if stats[i, cv2.CC_STAT_AREA] <= min_area:
            out[labels == i] = 0
    return out


def process_ai_equip(src_path: str, out_path_96: str, target_size: int = 78, colors: int = 36):
    raw = Image.open(src_path).convert("RGBA")
    print(f"[Processing AI Raw] {src_path}...")

    # 1. AI Background Removal
    nobg = rembg.remove(raw, post_process_mask=True)
    arr = np.array(nobg)

    # 2. Threshold alpha & morphology
    alpha = arr[:, :, 3]
    mask = alpha >= 120
    alpha_clean = np.where(mask, 255, 0).astype(np.uint8)

    # 1px erosion to clear dark fringe
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    alpha_eroded = cv2.erode(alpha_clean, kernel, iterations=1)
    arr[:, :, 3] = alpha_eroded
    arr[alpha_eroded == 0, :3] = 0

    # 3. Strip isolated floating debris
    arr = remove_isolated_noise_pixels(arr, min_area=25)

    clean_img = Image.fromarray(arr, mode="RGBA")
    bbox = clean_img.getbbox()
    if bbox:
        cropped = clean_img.crop(bbox)
    else:
        cropped = clean_img

    # 4. Scale to target pixel size preserving aspect ratio
    cw, ch = cropped.size
    scale = target_size / max(cw, ch)
    nw = max(1, int(cw * scale))
    nh = max(1, int(ch * scale))
    resized = cropped.resize((nw, nh), Image.Resampling.LANCZOS)

    # 5. Palette Quantization
    r, g, b, a = resized.split()
    rgb = Image.merge("RGB", (r, g, b))
    q_rgb = rgb.quantize(colors=colors, method=Image.Quantize.MEDIANCUT).convert("RGB")
    quantized = Image.merge("RGBA", (*q_rgb.split(), a))

    # 6. Place centered onto 96x96 canvas
    canvas = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    offset_x = (96 - nw) // 2
    offset_y = (96 - nh) // 2
    canvas.paste(quantized, (offset_x, offset_y), quantized)

    # 7. Apply 1px solid black pixel outline
    c_arr = np.array(canvas)
    outlined_arr = add_solid_pixel_outline(c_arr, outline_color=(18, 20, 26))
    final_img = Image.fromarray(outlined_arr, mode="RGBA")

    os.makedirs(os.path.dirname(os.path.abspath(out_path_96)), exist_ok=True)
    final_img.save(out_path_96, "PNG")
    print(f"[Exported Master] {out_path_96}")
    return final_img


def generate_all_tiers_from_master(master_path: str, out_dir: str, slot_name: str):
    """Generate all 10 quality tier variants from the master xian image."""
    master = Image.open(master_path).convert("RGBA")
    arr = np.array(master)
    alpha = arr[:, :, 3]
    inner_mask = alpha > 0
    rgb = arr[:, :, :3]
    is_outline = (rgb[:, :, 0] <= 24) & (rgb[:, :, 1] <= 24) & (rgb[:, :, 2] <= 28) & inner_mask
    body_mask = inner_mask & (~is_outline)

    for tier_key, cfg in TIER_CONFIGS.items():
        out_file = os.path.join(out_dir, f"{slot_name}_{tier_key}.png")
        if tier_key == "xian":
            master.save(out_file)
            continue

        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(np.float32)
        if cfg['hue_shift'] != 0:
            hsv[body_mask, 0] = (hsv[body_mask, 0] + cfg['hue_shift']) % 180
        hsv[body_mask, 1] = np.clip(hsv[body_mask, 1] * cfg['sat_mult'], 0, 255)
        hsv[body_mask, 2] = np.clip(hsv[body_mask, 2] * cfg['val_mult'], 0, 255)

        recolored = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
        if cfg['tint'] is not None:
            tint = np.array(cfg['tint'], dtype=np.float32)
            recolored_float = recolored.astype(np.float32)
            blended = recolored_float * 0.72 + tint * 0.28
            recolored[body_mask] = np.clip(blended[body_mask], 0, 255).astype(np.uint8)

        out_arr = arr.copy()
        out_arr[body_mask, :3] = recolored[body_mask]
        final_arr = add_solid_pixel_outline(out_arr, outline_color=(18, 20, 26))
        Image.fromarray(final_arr).save(out_file, "PNG")


if __name__ == "__main__":
    equip_dir = r"D:\projects\xiuxian-game\textures\equip\96x96"
    slots = ['weapon', 'armor', 'offhand', 'head', 'hand', 'foot', 'necklace', 'ring']
    for s in slots:
        master_path = os.path.join(equip_dir, f"{s}_xian.png")
        if os.path.exists(master_path):
            generate_all_tiers_from_master(master_path, equip_dir, s)
    print("All 80 assets generated across 10 tiers!")
