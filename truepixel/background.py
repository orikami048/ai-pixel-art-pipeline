"""
背景移除：品红/绿幕色键 + rembg（U2-Net）+ 纯色背景保底。

rembg 是可选依赖，只有真正要抠图时才导入。没装 rembg 时会退回到
"按四角颜色做色差抠图"，对 AI 生成的纯色背景原图通常也够用。
"""
from __future__ import annotations

from typing import Optional

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


def remove_border_background(img: Image.Image, tolerance: float = 30.0) -> np.ndarray:
    """
    纯色背景（白底等）：只删和背景色相近、并且和画布边缘连通的区域。
    和 remove_flat_background 的区别是：主体内部和背景同色的地方（白色高光等）会保留。
    """
    import cv2

    arr = np.array(img.convert("RGBA"))
    bg = np.median(corner_samples(arr[:, :, :3]), axis=0)
    near = (np.linalg.norm(arr[:, :, :3].astype(np.float32) - bg, axis=2) <= tolerance).astype(np.uint8)
    _, labels = cv2.connectedComponents(near, connectivity=4)
    border = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    border = border[border > 0]
    arr[np.isin(labels, border), 3] = 0
    return arr


# ---------------------------------------------------------------- 色键（品红 / 绿幕）

# (高通道, 低通道)：品红 = R、B 高，G 低；绿幕 = G 高，R、B 低
_KEY_CHANNELS = {"magenta": ((0, 2), (1,)), "green": ((1,), (0, 2))}


def detect_chroma(img: Image.Image) -> Optional[str]:
    """四角是均匀的品红或绿色时返回 'magenta' / 'green'，否则 None。"""
    rgb = np.array(img.convert("RGB")).astype(np.float32)
    corners = corner_samples(rgb)
    if np.std(corners, axis=0).mean() > 25:
        return None
    r, g, b = np.median(corners, axis=0)
    if r > 170 and b > 170 and g < 100:
        return "magenta"
    if g > 170 and r < 120 and b < 120:
        return "green"
    return None


def _key_excess(rgb: np.ndarray, key: str) -> np.ndarray:
    hi, lo = _KEY_CHANNELS[key]
    return rgb[:, :, list(hi)].min(axis=2) - rgb[:, :, list(lo)].max(axis=2)


def chroma_key(img: Image.Image, key: Optional[str] = None, tolerance: float = 90.0,
               edge_px: int = 2, edge_excess: float = 90.0) -> np.ndarray:
    """
    品红 / 绿幕抠像。主体里不该出现背景色，所以全图删除，不要求和边缘连通（镂空处也会删干净）。
    然后在背景边缘 edge_px 圈内处理溢色：色偏很重的像素直接删，轻的把色偏压回中性。
    """
    import cv2

    key = key or detect_chroma(img) or "magenta"
    arr = np.array(img.convert("RGBA"))
    rgb = arr[:, :, :3].astype(np.float32)
    bg = np.median(corner_samples(rgb), axis=0)
    excess = _key_excess(rgb, key)
    gone = (np.linalg.norm(rgb - bg, axis=2) <= tolerance) | (excess > 160)  # 后者兜住亮度不一的噪点背景

    if edge_px > 0:
        band = cv2.dilate(gone.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=edge_px).astype(bool) & ~gone
        gone |= band & (excess > edge_excess)
        spill = band & ~gone & (excess > 0)
        for c in _KEY_CHANNELS[key][0]:
            rgb[:, :, c] = np.where(spill, rgb[:, :, c] - excess, rgb[:, :, c])
        arr[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)

    arr[gone, 3] = 0
    return arr


def remove_background(img: Image.Image, post_process_mask: bool = False) -> np.ndarray:
    """
    返回去背景后的 RGBA 数组。

    不开 post_process_mask 时启用"前景保底"：若原图四角颜色一致（纯色背景），
    把被 rembg 误删、但和背景色差明显的像素（光晕、细剑尖等）找回来。
    """
    img = img.convert("RGBA")
    key = detect_chroma(img)
    if key:  # 品红/绿幕背景用色键，比 rembg 稳定，也不会把 UI 边框这类"不像物体"的主体删掉
        return chroma_key(img, key)
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
