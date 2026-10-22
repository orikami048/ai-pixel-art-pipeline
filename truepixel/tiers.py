"""
修仙装备十阶品质变色：从一张"仙品"母版生成其余 9 个品阶的配色变体。
只改主体颜色，描边（接近黑色的像素）保持不变。
"""
from __future__ import annotations

import os
from typing import Dict, List

import numpy as np
from PIL import Image

from . import ops

# 色相偏移以 OpenCV HSV（0~179）为单位
TIERS: Dict[str, dict] = {
    "fan":   {"name": "凡品", "hue_shift": 0,    "sat_mult": 0.12, "val_mult": 0.82, "tint": (140, 140, 145)},  # 凡铁砂石
    "liang": {"name": "良品", "hue_shift": -25,  "sat_mult": 0.55, "val_mult": 0.92, "tint": (110, 175, 130)},  # 素青灵木
    "ling":  {"name": "灵品", "hue_shift": 15,   "sat_mult": 1.05, "val_mult": 1.05, "tint": (60, 215, 200)},   # 碧波温玉
    "xuan":  {"name": "玄品", "hue_shift": 45,   "sat_mult": 1.15, "val_mult": 1.0,  "tint": (60, 120, 245)},   # 幽蓝玄溟
    "di":    {"name": "地品", "hue_shift": 85,   "sat_mult": 1.10, "val_mult": 1.0,  "tint": (180, 75, 230)},   # 幽冥绛紫
    "tian":  {"name": "天品", "hue_shift": -70,  "sat_mult": 1.25, "val_mult": 1.10, "tint": (250, 85, 45)},    # 离火赤天
    "bao":   {"name": "宝品", "hue_shift": -50,  "sat_mult": 1.35, "val_mult": 1.15, "tint": (255, 200, 40)},   # 万宝灿金
    "xian":  {"name": "仙品", "hue_shift": 0,    "sat_mult": 1.0,  "val_mult": 1.0,  "tint": None},             # 母版原色
    "shen":  {"name": "神品", "hue_shift": 105,  "sat_mult": 1.35, "val_mult": 1.20, "tint": (245, 95, 255)},   # 太虚紫金
    "chaos": {"name": "混沌", "hue_shift": -130, "sat_mult": 1.35, "val_mult": 1.25, "tint": (160, 95, 255)},   # 鸿蒙混元
}
MASTER_TIER = "xian"
SLOTS = ["weapon", "armor", "offhand", "head", "hand", "foot", "necklace", "ring"]


def recolor_tier(master: Image.Image, tier: str, outline_color: ops.Color = ops.DEFAULT_OUTLINE) -> Image.Image:
    import cv2

    cfg = TIERS[tier]
    arr = np.array(master.convert("RGBA"))
    if tier == MASTER_TIER:
        return Image.fromarray(arr, "RGBA")

    rgb = np.ascontiguousarray(arr[:, :, :3])
    solid = arr[:, :, 3] > 0
    is_outline = (rgb[:, :, 0] <= 24) & (rgb[:, :, 1] <= 24) & (rgb[:, :, 2] <= 28) & solid
    body = solid & ~is_outline

    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(np.float32)
    if cfg["hue_shift"]:
        hsv[body, 0] = (hsv[body, 0] + cfg["hue_shift"]) % 180
    hsv[body, 1] = np.clip(hsv[body, 1] * cfg["sat_mult"], 0, 255)
    hsv[body, 2] = np.clip(hsv[body, 2] * cfg["val_mult"], 0, 255)
    recolored = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)

    if cfg["tint"] is not None:
        blended = recolored.astype(np.float32) * 0.72 + np.array(cfg["tint"], np.float32) * 0.28
        recolored[body] = np.clip(blended[body], 0, 255).astype(np.uint8)

    out = arr.copy()
    out[body, :3] = recolored[body]
    return Image.fromarray(ops.add_outline(out, outline_color), "RGBA")


def generate_tiers(master_path: str, out_dir: str, slot: str) -> List[str]:
    """输出 <slot>_<tier>.png × 10 到 out_dir，返回文件路径列表。"""
    master = Image.open(master_path)
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for tier in TIERS:
        p = os.path.join(out_dir, f"{slot}_{tier}.png")
        recolor_tier(master, tier).save(p)
        paths.append(p)
    return paths
