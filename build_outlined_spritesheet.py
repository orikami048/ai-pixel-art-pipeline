"""
生产级 96x96 纯正像素闭合硬描边（Solid Pixel Outline）8 帧序列图生成器
-------------------------------------------------------------------------
1. 全局绝对中轴锁定 (Fixed Anchor)：保证人物、莲座在 8 帧中 100% 等大，无抖动
2. 形态学精准剥离 AI 背景过渡脏色
3. Pixel-Perfect 1px 闭合深黑硬描边 (Solid Dark Outline)：打造顶级独立像素游戏清晰立挺质感
4. 滤除孤立浮空杂点噪点
5. 导出规范 1x8 序列大图 (Native: 768x96, 3x Retina: 2304x288)
"""

import os
from PIL import Image
import numpy as np
import cv2
import rembg


def add_solid_pixel_outline(rgba_arr: np.ndarray, outline_color=(18, 20, 26)) -> np.ndarray:
    """
    给透明 PNG 的实体非透明区域外缘施加严格 1px 闭合像素硬描边。
    """
    h, w = rgba_arr.shape[:2]
    alpha = rgba_arr[:, :, 3]

    # 4 邻域检测边界
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
    return out


def remove_isolated_noise_pixels(rgba_arr: np.ndarray, min_area: int = 6) -> np.ndarray:
    """
    清除周围散落的孤立杂色飞屑，保持剪影整洁利落。
    """
    alpha = rgba_arr[:, :, 3]
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats((alpha > 0).astype(np.uint8))
    out = rgba_arr.copy()
    for i in range(1, num_labels):
        if stats[i, cv2.CC_STAT_AREA] <= min_area:
            out[labels == i] = 0
    return out


def build_outlined_spritesheet(src_sheet_path: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    sheet = Image.open(src_sheet_path).convert("RGBA")
    sw, sh = sheet.size
    cell_w = sw // 3
    cell_h = sh // 3

    print(f"[Outliner Engine] 原始九宫格尺寸: {sw}x{sh}, 单格: {cell_w}x{cell_h}")

    # 第一阶段：剥离背景与侵蚀去脏
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    raw_clean_cells = []

    for idx in range(8):
        c = idx % 3
        r = idx // 3
        cell = sheet.crop((c * cell_w, r * cell_h, (c + 1) * cell_w, (r + 1) * cell_h))
        print(f"[{idx+1}/8] 正在提取与清洗单帧...")

        nobg = rembg.remove(cell, post_process_mask=True)
        arr = np.array(nobg)
        alpha = arr[:, :, 3]
        mask = alpha >= 120
        alpha_clean = np.where(mask, 255, 0).astype(np.uint8)
        alpha_eroded = cv2.erode(alpha_clean, kernel, iterations=1)

        arr[:, :, 3] = alpha_eroded
        arr[alpha_eroded == 0, :3] = 0
        raw_clean_cells.append(Image.fromarray(arr, mode="RGBA"))

    # 第二阶段：锁定全局中轴基准 (与第0帧人物严格等大)
    f0_bbox = raw_clean_cells[0].getbbox()
    f0_w = f0_bbox[2] - f0_bbox[0]
    f0_h = f0_bbox[3] - f0_bbox[1]
    target_char_size = 80
    scale = target_char_size / max(f0_w, f0_h)

    fixed_base_y = 93
    fixed_center_x = 48
    f0_center_x = (f0_bbox[0] + f0_bbox[2]) / 2.0
    f0_bottom_y = f0_bbox[3]

    outlined_frames = []

    for idx, c_img in enumerate(raw_clean_cells):
        print(f"[{idx+1}/8] 施加闭合硬描边与 96x96 映射...")
        cur_w = int(c_img.width * scale)
        cur_h = int(c_img.height * scale)
        scaled = c_img.resize((cur_w, cur_h), Image.Resampling.BILINEAR)

        paste_x = int(fixed_center_x - (f0_center_x * scale))
        paste_y = int(fixed_base_y - (f0_bottom_y * scale))

        frame_canvas = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        frame_canvas.paste(scaled, (paste_x, paste_y), mask=scaled)

        # 二值化
        arr_96 = np.array(frame_canvas)
        a_96 = arr_96[:, :, 3]
        m_96 = a_96 >= 128
        arr_96[:, :, 3] = np.where(m_96, 255, 0)
        arr_96[~m_96, :3] = 0

        # 色板量化
        clean_p = Image.fromarray(arr_96, mode="RGBA")
        r, g, b, a = clean_p.split()
        rgb = Image.merge("RGB", (r, g, b))
        q_rgb = rgb.quantize(colors=32, method=Image.Quantize.MEDIANCUT).convert("RGB")
        quantized = Image.merge("RGBA", (*q_rgb.split(), a))

        # 核心步：添加工业级闭合深黑硬描边
        outlined_arr = add_solid_pixel_outline(np.array(quantized))
        # 清除小飞屑
        final_arr = remove_isolated_noise_pixels(outlined_arr, min_area=6)
        final_frame = Image.fromarray(final_arr, mode="RGBA")

        # 存单帧
        final_frame.save(os.path.join(output_dir, f"frame_{idx}_outlined.png"))
        outlined_frames.append(final_frame)

    # 第三阶段：合并为 8 帧序列大图
    native_sheet = Image.new("RGBA", (96 * 8, 96), (0, 0, 0, 0))
    for i, f in enumerate(outlined_frames):
        native_sheet.paste(f, (i * 96, 0))

    out_sheet_path = os.path.join(output_dir, "meditation_sheet_outlined_96.png")
    native_sheet.save(out_sheet_path, "PNG")

    # 3x 高分屏版本
    hd_3x = native_sheet.resize((96 * 8 * 3, 96 * 3), Image.Resampling.NEAREST)
    out_3x_path = os.path.join(output_dir, "meditation_sheet_outlined_3x.png")
    hd_3x.save(out_3x_path, "PNG")

    print(f"\n[SUCCESS] 闭合黑描边 8 帧大图已输出:")
    print(f" -> 原生: {out_sheet_path}")
    print(f" -> 3x 高清: {out_3x_path}")


if __name__ == "__main__":
    src = r"C:\Users\kami\.gemini\antigravity\brain\067e7c08-6455-4684-9322-ed102a0b15e0\anime_girl_meditating_sprite_sheet_1791693652207.jpg"
    out = r"D:\projects\xiuxian-game\textures\true_pixel_outlined"
    build_outlined_spritesheet(src, out)
