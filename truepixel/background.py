"""
背景移除：rembg（U2-Net）+ 纯色背景保底。

rembg 是可选依赖，只有真正要抠图时才导入。没装 rembg 时会退回到
"按四角颜色做色差抠图"，对 AI 生成的纯色背景原图通常也够用。
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from .ops import corner_samples

_SESSION = None


def rembg_available() -> bool:
    try:
        import rembg  # noqa: F401
        return True
    except ImportError:
        return False


def _session():
    global _SESSION
    if _SESSION is None:
        import rembg
        _SESSION = rembg.new_session("u2net")
    return _SESSION


def remove_flat_background(img: Image.Image, tolerance: float = 25.0) -> np.ndarray:
    """不依赖模型：四角颜色一致时，把和背景色差 <= tolerance 的像素设为透明。"""
    arr = np.array(img.convert("RGBA"))
    bg = np.median(corner_samples(arr[:, :, :3]), axis=0)
    dist = np.linalg.norm(arr[:, :, :3].astype(np.float32) - bg, axis=2)
    arr[:, :, 3] = np.where(dist > tolerance, arr[:, :, 3], 0)
    return arr


def remove_background(img: Image.Image, post_process_mask: bool = False) -> np.ndarray:
    """
    返回去背景后的 RGBA 数组。

    不开 post_process_mask 时启用"前景保底"：若原图四角颜色一致（纯色背景），
    把被 rembg 误删、但和背景色差明显的像素（光晕、细剑尖等）找回来。
    """
    img = img.convert("RGBA")
    if not rembg_available():
        return remove_flat_background(img)

    import rembg
    arr = np.array(rembg.remove(img, session=_session(), post_process_mask=post_process_mask))

    if not post_process_mask:
        raw = np.array(img)
        corners = corner_samples(raw[:, :, :3])
        if np.std(corners, axis=0).mean() < 25:
            bg = np.median(corners, axis=0)
            dist = np.linalg.norm(raw[:, :, :3] - bg, axis=2)
            lost = (dist > 25) & (arr[:, :, 3] < 120)
            if np.any(lost):
                arr[lost, :3] = raw[lost, :3]
                arr[lost, 3] = np.clip(dist[lost] * 5, 180, 255).astype(np.uint8)
    return arr
