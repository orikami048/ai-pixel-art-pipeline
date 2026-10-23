"""
伪像素网格还原：AI 生成的"像素风"图其实是把小图放大后再加了模糊和噪点，
每个"像素"是一个 s×s 的色块，而且网格常常不均匀、会漂移。

这里先估计色块边长 s，再沿着边缘能量逐条追踪网格线（允许漂移），
最后每个格子取中位色，得到原生分辨率的真像素图。
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
from PIL import Image


def edge_profile(rgba: np.ndarray, axis: int, interior_only: bool = False) -> np.ndarray:
    """
    相邻两列（axis=1）或两行（axis=0）之间的颜色差总和。
    返回长度 n-1 的数组：第 i 个值是第 i 和第 i+1 列之间的边缘强度。
    透明像素按黑色计，并把透明度也算进去，这样剪影边缘也算网格线。
    interior_only：只算两侧都不透明的边。估计周期时用，免得剪影外缘的强边把
    "物体高度"当成周期。
    """
    a = rgba[:, :, 3:4].astype(np.float32) / 255.0
    x = np.concatenate([rgba[:, :, :3].astype(np.float32) * a, rgba[:, :, 3:4].astype(np.float32)], axis=2)
    d = np.abs(np.diff(x, axis=axis)).sum(axis=2)
    if interior_only:
        solid = rgba[:, :, 3] > 0
        d = d * ((solid[:, 1:] & solid[:, :-1]) if axis == 1 else (solid[1:] & solid[:-1]))
    return d.sum(axis=0 if axis == 1 else 1)


def estimate_period(profile: np.ndarray, min_s: float = 2.0, max_s: Optional[float] = None) -> Tuple[float, float]:
    """
    用自相关估计网格周期。返回 (周期, 置信度 0~1)。
    置信度低（< 0.15 左右）说明图里没有明显的伪像素网格。
    """
    n = len(profile)
    if n < 8:
        return 1.0, 0.0
    # 剪影外缘的边特别强，会让"物体高度"变成最强的周期；削掉尖峰只看规律
    p = profile - profile.mean()
    denom = float((p * p).sum())
    if denom <= 0:
        return 1.0, 0.0
    max_lag = int(min(max_s or 64, n // 3))
    lags = np.arange(max_lag + 2)
    ac = np.array([(p[: n - k] * p[k:]).sum() / max(1, n - k) for k in lags]) * n / denom

    lo = max(2, int(np.floor(min_s)))
    peaks = [k for k in range(lo, max_lag + 1) if ac[k] > 0 and ac[k] >= ac[k - 1] and ac[k] >= ac[k + 1]]
    if not peaks:
        return 1.0, 0.0
    best = max(ac[k] for k in peaks)
    # 周期的整数倍也会出峰，取第一个够高的峰
    k = next(k for k in peaks if ac[k] >= 0.6 * best)

    # 用后面的倍数峰把周期精确到小数：s ≈ 第 m 个峰的位置 / m。
    # 每找到一个峰就更新估计，下一个倍数按新估计去找，否则小数周期（如 3.5）会越找越偏。
    # 整数峰 k 只是粗估（周期 3.5 时峰会落在 3 或 4）。在 k 附近按 0.01 扫小数周期，
    # 每个候选 s 的得分 = 自相关在 s、2s、3s… 处（线性插值）的平均值：所有倍数一起投票，
    # 一个纹理造成的假峰带不偏结果。
    cands = np.arange(max(float(lo) - 0.5, k - 1.0), k + 1.0 + 1e-9, 0.01)
    cands = cands[cands >= 1.5]
    best_s, best_score = float(k), -np.inf
    for s in cands:
        m = np.arange(1, int(max_lag // s) + 1)
        if len(m) == 0:
            continue
        score = float(np.interp(m * s, lags, ac).mean())
        if score > best_score:
            best_s, best_score = float(s), score
    return best_s, float(np.clip(ac[k], 0.0, 1.0))


def track_lines(profile: np.ndarray, s: float, search: float = 0.35) -> List[int]:
    """
    从最强的一条边开始，向两侧每隔约 s 找一条网格线：
    预期位置 ±search·s 内有明显边缘就对齐到它，没有就按预期位置放（背景区）。
    返回网格线坐标（像素边界，含 0 和 n）。
    """
    n = len(profile) + 1  # 像素数
    if s <= 1.0:
        return list(range(n + 1))
    strong = 0.15 * float(np.percentile(profile, 99)) if len(profile) else 0.0
    anchor = int(np.argmax(profile)) + 1 if len(profile) else 0
    r = max(1, int(round(s * search)))

    def walk(start: int, direction: int) -> List[int]:
        out, x = [], float(start)
        while True:
            exp = x + direction * s
            if (direction > 0 and exp > n - 0.5 * s) or (direction < 0 and exp < 0.5 * s):
                break
            c = int(round(exp))
            lo, hi = max(1, c - r), min(n - 1, c + r)
            if lo > hi:
                break
            seg = profile[lo - 1:hi]
            j = int(np.argmax(seg))
            x = float(lo + j) if seg[j] > strong else exp
            out.append(int(round(x)))
        return out

    lines = sorted(set([0, n, anchor] + walk(anchor, 1) + walk(anchor, -1)))
    # 去掉挤在一起的线（< s/2）
    cleaned = [lines[0]]
    for v in lines[1:]:
        if v - cleaned[-1] >= max(1, s * 0.5) or v == n:
            if v == n and n - cleaned[-1] < s * 0.5 and len(cleaned) > 1:
                cleaned[-1] = n
            else:
                cleaned.append(v)
    return cleaned


def sample_cells(rgba: np.ndarray, xs: List[int], ys: List[int], inset: float = 0.25) -> np.ndarray:
    """每个格子取内部（四周各缩进 inset）像素的中位色；透明度按多数决定（0/255）。"""
    out = np.zeros((len(ys) - 1, len(xs) - 1, 4), np.uint8)
    for j in range(len(ys) - 1):
        y0, y1 = ys[j], ys[j + 1]
        dy = int((y1 - y0) * inset)
        for i in range(len(xs) - 1):
            x0, x1 = xs[i], xs[i + 1]
            dx = int((x1 - x0) * inset)
            cell = rgba[y0 + dy:max(y0 + dy + 1, y1 - dy), x0 + dx:max(x0 + dx + 1, x1 - dx)].reshape(-1, 4)
            solid = cell[cell[:, 3] >= 128]
            if len(solid) * 2 >= len(cell):
                out[j, i, :3] = np.median(solid[:, :3], axis=0)
                out[j, i, 3] = 255
    return out


def detect_scale(rgba: np.ndarray) -> Tuple[float, float]:
    """估计整张图的色块边长（横竖分别估计，取置信度高的那个）。返回 (s, 置信度)。"""
    sx, cx = estimate_period(edge_profile(rgba, 1, interior_only=True))
    sy, cy = estimate_period(edge_profile(rgba, 0, interior_only=True))
    if abs(sx - sy) <= 0.15 * max(sx, sy):
        return (sx * cx + sy * cy) / max(1e-6, cx + cy), max(cx, cy)
    lo, hi = sorted([(sx, cx), (sy, cy)])
    ratio = hi[0] / max(lo[0], 1e-6)
    if lo[1] >= 0.15 and abs(ratio - round(ratio)) < 0.15:  # 一个是另一个的整数倍：取小的
        return lo
    return (sx, cx) if cx >= cy else (sy, cy)


def grid_fit(rgba: np.ndarray, s: float) -> float:
    """
    验证网格是否真的存在：内部边缘能量有多少落在追踪到的网格线附近（窗口 w 个边界），
    再和"随便画线也能碰上"的比例 w/s 比。伪像素图约 0.5~0.9，原生像素图接近 0。
    窗口随 s 缩小：s 很小时 ±1px 就把所有位置都盖住了，比不出差别。
    """
    if s < 2.5:
        return 0.0
    w = 1 if s < 4 else 3
    import cv2

    rgba = rgba.copy()
    rgba[:, :, :3] = cv2.medianBlur(np.ascontiguousarray(rgba[:, :, :3]), 3)  # 去掉逐像素噪点，色块边缘不受影响
    scores = []
    for axis in (1, 0):
        full, inner = edge_profile(rgba, axis), edge_profile(rgba, axis, interior_only=True)
        inner = np.maximum(inner - np.percentile(inner, 25), 0.0)  # 扣掉噪点造成的均匀底噪
        total = float(inner.sum())
        if total <= 0:
            continue
        near = np.zeros(len(inner), bool)
        lo_off = (w - 1) // 2 + 1  # 网格线 x 对应边界 x-1；w=3 时取 x-2..x，w=2 取 x-1..x，w=1 只取 x-1
        for x in track_lines(full, s)[1:-1]:
            near[max(0, x - lo_off):min(len(inner), x - lo_off + w)] = True
        chance = min(1.0, w / s)
        scores.append((float(inner[near].sum()) / total - chance) / max(1e-6, 1.0 - chance))
    return float(np.clip(np.mean(scores), 0.0, 1.0)) if scores else 0.0


def to_native(rgba: np.ndarray, s: float) -> Tuple[np.ndarray, List[int], List[int]]:
    """按色块边长 s 还原成原生像素。返回 (原生 RGBA, 竖线坐标, 横线坐标)。"""
    if s <= 1.05:
        return rgba.copy(), list(range(rgba.shape[1] + 1)), list(range(rgba.shape[0] + 1))
    xs = track_lines(edge_profile(rgba, 1), s)
    ys = track_lines(edge_profile(rgba, 0), s)
    return sample_cells(rgba, xs, ys), xs, ys


def grid_overlay(rgba: np.ndarray, xs: List[int], ys: List[int], color=(255, 0, 255, 255)) -> Image.Image:
    """调试用：把追踪到的网格线画在原图上，肉眼检查有没有对齐。"""
    arr = rgba.copy()
    for x in xs[1:-1]:
        arr[:, min(x, arr.shape[1] - 1)] = color
    for y in ys[1:-1]:
        arr[min(y, arr.shape[0] - 1), :] = color
    return Image.fromarray(arr, "RGBA")
