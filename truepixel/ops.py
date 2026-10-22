"""
底层像素操作：所有脚本共用这一份实现，不要在别处再复制。

约定：函数接收和返回 numpy RGBA 数组（uint8, HxWx4）或 PIL Image，类型写在签名里。
"""
from __future__ import annotations

from typing import Optional, Sequence, Tuple

import numpy as np
from PIL import Image

Color = Tuple[int, int, int]
DEFAULT_OUTLINE: Color = (18, 20, 26)


# ---------------------------------------------------------------- 描边 / 去噪

def edge_mask(alpha: np.ndarray) -> np.ndarray:
    """不透明像素中，4 邻域里有透明像素（或位于画布边缘）的那些。"""
    solid = alpha > 0
    padded = np.pad(solid, 1, constant_values=False)
    all_neighbours_solid = (
        padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:]
    )
    return solid & ~all_neighbours_solid


def add_outline(rgba: np.ndarray, color: Color = DEFAULT_OUTLINE) -> np.ndarray:
    """1px 正交闭合描边：把剪影最外圈像素涂成描边色（内描边，不改变剪影大小）。"""
    mask = edge_mask(rgba[:, :, 3])
    out = rgba.copy()
    out[mask, :3] = color
    out[mask, 3] = 255
    return out


def remove_specks(rgba: np.ndarray, min_area: int = 18) -> np.ndarray:
    """删除面积 <= min_area 的孤立不透明连通块（抠图残留的飞屑）。"""
    if min_area <= 0:
        return rgba
    import cv2

    n, labels, stats, _ = cv2.connectedComponentsWithStats((rgba[:, :, 3] > 0).astype(np.uint8))
    small = np.zeros(n, dtype=bool)
    small[1:] = stats[1:, cv2.CC_STAT_AREA] <= min_area
    out = rgba.copy()
    out[small[labels]] = 0
    return out


# ---------------------------------------------------------------- 透明度

def harden_alpha(rgba: np.ndarray, threshold: int = 100, erode: int = 1) -> np.ndarray:
    """透明度二值化，可选再向内腐蚀 erode 圈以切掉暗色毛边；透明像素 RGB 清零。"""
    out = rgba.copy()
    a = np.where(out[:, :, 3] >= threshold, 255, 0).astype(np.uint8)
    if erode > 0:
        import cv2

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        a = cv2.erode(a, kernel, iterations=erode)
    out[:, :, 3] = a
    out[a == 0, :3] = 0
    return out


def binarize_alpha(img: Image.Image, threshold: int = 128, zero_rgb: bool = False) -> Image.Image:
    """透明度只留 0/255。zero_rgb=True 时顺便把透明像素的 RGB 清零。"""
    arr = np.array(img.convert("RGBA"))
    keep = arr[:, :, 3] >= threshold
    arr[:, :, 3] = np.where(keep, 255, 0)
    if zero_rgb:
        arr[~keep, :3] = 0
    return Image.fromarray(arr, "RGBA")


# ---------------------------------------------------------------- 颜色

def load_palette(path: str) -> np.ndarray:
    """读取调色板 PNG（每个不同的不透明颜色算一色），返回 Nx3 int 数组。"""
    pal = np.array(Image.open(path).convert("RGBA")).reshape(-1, 4)
    pal = pal[pal[:, 3] > 0, :3]
    _, idx = np.unique(pal, axis=0, return_index=True)
    return pal[np.sort(idx)].astype(np.int32)


def map_to_palette(rgba: np.ndarray, palette: np.ndarray) -> np.ndarray:
    """把每个不透明像素替换为调色板里欧氏距离最近的颜色。"""
    out = rgba.copy()
    opaque = out[:, :, 3] > 0
    px = out[opaque, :3].astype(np.int32)
    if len(px):
        d = ((px[:, None, :] - palette[None, :, :]) ** 2).sum(axis=2)
        out[opaque, :3] = palette[d.argmin(axis=1)].astype(np.uint8)
    return out


def quantize(img: Image.Image, colors: int = 32, palette: Optional[np.ndarray] = None) -> Image.Image:
    """减色：给了 palette 就映射到它，否则 median-cut 到 colors 色。透明度原样保留。"""
    img = img.convert("RGBA")
    if palette is not None:
        return Image.fromarray(map_to_palette(np.array(img), palette), "RGBA")
    r, g, b, a = img.split()
    q = Image.merge("RGB", (r, g, b)).quantize(colors=colors, method=Image.Quantize.MEDIANCUT).convert("RGB")
    return Image.merge("RGBA", (*q.split(), a))


def count_colors(img: Image.Image) -> int:
    arr = np.array(img.convert("RGBA")).reshape(-1, 4)
    arr = arr[arr[:, 3] > 0]
    return 0 if len(arr) == 0 else len(np.unique(arr, axis=0))


# ---------------------------------------------------------------- 尺寸 / 构图

def crop_to_content(img: Image.Image) -> Image.Image:
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


def fit_size(w: int, h: int, box: int) -> Tuple[int, int]:
    scale = box / max(w, h)
    return max(1, int(round(w * scale))), max(1, int(round(h * scale)))


def paste_centered(img: Image.Image, size: int) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
    return canvas


def limit_size(img: Image.Image, max_side: int = 1024) -> Image.Image:
    """超大原图先缩到 max_side 以内，加快抠图。"""
    w, h = img.size
    if max(w, h) <= max_side:
        return img
    f = max_side / max(w, h)
    return img.resize((int(w * f), int(h * f)), Image.Resampling.LANCZOS)


def preview(img: Image.Image, scale: Optional[int] = None) -> Image.Image:
    """最近邻放大预览。scale 为空时沿用旧规则：<=256 放大 4 倍，<=512 放大 2 倍。"""
    if scale is None:
        side = max(img.size)
        scale = 4 if side <= 256 else (2 if side <= 512 else 1)
    return img.resize((img.width * scale, img.height * scale), Image.Resampling.NEAREST)


def corner_samples(arr: np.ndarray, k: int = 15) -> np.ndarray:
    """四个角各取 k×k 像素，返回 Nx3（或 NxC）样本，用于估计背景色。"""
    c = arr.shape[2]
    return np.vstack([
        arr[:k, :k].reshape(-1, c), arr[:k, -k:].reshape(-1, c),
        arr[-k:, :k].reshape(-1, c), arr[-k:, -k:].reshape(-1, c),
    ])


def parse_hex_color(s: str) -> Color:
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def as_color(v: Sequence[int]) -> Color:
    return (int(v[0]), int(v[1]), int(v[2]))
