"""
按素材清单批量处理：raw/<name>.* → <out_dir>/<folder>/<name>.png

清单格式（JSON，路径都相对清单文件所在目录）：
{
  "defaults": {
    "raw_dir": "raw", "out_dir": "assets", "palette": "assets/palette.png",
    "max_colors": 16, "preview_scale": 8
  },
  "assets": [
    {"name": "weapon_sword_xian", "folder": "equip", "size": 96, "kind": "sprite",
     "content_size": 78, "prompt": "...", "options": {"alpha_threshold": 120}}
  ]
}

kind:
  sprite  去背景 + 描边（角色、武器、道具、UI）
  tile    不去背景、不描边，铺满整格（地图图块）
  vfx     发光特效，保留半透明光晕
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from PIL import Image, ImageDraw

from . import ops
from .pipeline import process_image, process_vfx_image

RAW_EXTS = (".png", ".jpg", ".jpeg", ".webp")
KINDS: Dict[str, dict] = {
    "sprite": dict(remove_bg=True, apply_outline=True),
    "tile": dict(remove_bg=False, apply_outline=False),
    "vfx": dict(),
}


@dataclass
class Result:
    name: str
    status: str  # done | fresh | missing | failed
    note: str = ""


def _find_raw(raw_dir: str, name: str) -> Optional[str]:
    for ext in RAW_EXTS:
        p = os.path.join(raw_dir, name + ext)
        if os.path.exists(p):
            return p
    return None


def contact_sheet(items: List[tuple], out_path: str, cell: int = 128, cols: int = 6) -> Optional[str]:
    """把 (名字, 图片路径) 拼成一张带棋盘格底的总览图，方便一眼验收。"""
    items = [(n, p) for n, p in items if os.path.exists(p)]
    if not items:
        return None
    label_h = 14
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell, rows * (cell + label_h)), (60, 60, 70, 255))
    draw = ImageDraw.Draw(sheet)
    for i, (name, path) in enumerate(items):
        x, y = (i % cols) * cell, (i // cols) * (cell + label_h)
        for cy in range(0, cell, 16):
            for cx in range(0, cell, 16):
                shade = 90 if (cx // 16 + cy // 16) % 2 else 110
                draw.rectangle([x + cx, y + cy, x + cx + 15, y + cy + 15], fill=(shade, shade, shade, 255))
        im = Image.open(path).convert("RGBA")
        s = max(1, (cell - 8) // max(im.size))
        big = im.resize((im.width * s, im.height * s), Image.Resampling.NEAREST)
        sheet.alpha_composite(big, (x + (cell - big.width) // 2, y + (cell - big.height) // 2))
        draw.text((x + 3, y + cell + 1), name[:20], fill=(230, 230, 230, 255))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    sheet.save(out_path)
    return out_path


def run(manifest_path: str, force: bool = False, only: Optional[List[str]] = None,
        log=print) -> List[Result]:
    base = os.path.dirname(os.path.abspath(manifest_path))
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    d = manifest.get("defaults", {})
    raw_dir = os.path.join(base, d.get("raw_dir", "raw"))
    out_dir = os.path.join(base, d.get("out_dir", "assets"))
    preview_dir = os.path.join(out_dir, "_preview")
    pal_path = os.path.join(base, d.get("palette", os.path.join(d.get("out_dir", "assets"), "palette.png")))
    palette = ops.load_palette(pal_path) if os.path.exists(pal_path) else None
    max_colors = int(d.get("max_colors", 16))
    pscale = int(d.get("preview_scale", 8))
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(preview_dir, exist_ok=True)

    results: List[Result] = []
    for e in manifest["assets"]:
        name, size, kind = e["name"], int(e["size"]), e.get("kind", "sprite")
        if only and name not in only:
            continue
        out = os.path.join(out_dir, e.get("folder", ""), name + ".png")
        raw = _find_raw(raw_dir, name)
        if raw is None:
            results.append(Result(name, "missing", f"需要 {os.path.relpath(raw_dir, base)}/{name}.png"))
            continue
        if not force and os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(raw):
            results.append(Result(name, "fresh"))
            continue
        try:
            src = Image.open(raw)
            opts = dict(e.get("options", {}))
            if kind == "vfx":
                native, _ = process_vfx_image(src, size, max_colors, **opts)
            else:
                native, _ = process_image(
                    src, size, max_colors, palette=palette,
                    content_size=e.get("content_size"), **{**KINDS[kind], **opts},
                )
            os.makedirs(os.path.dirname(out), exist_ok=True)
            native.save(out)
            ops.preview(native, pscale).save(os.path.join(preview_dir, name + ".png"))
            n = ops.count_colors(native)
            note = f"{size}x{size}，{n} 色" + ("（超过上限）" if n > max_colors and kind != "vfx" else "")
            results.append(Result(name, "done", note))
            log(f"✅ {name}  {note}")
        except Exception as ex:  # 单张失败不影响其他素材
            results.append(Result(name, "failed", str(ex)))
            log(f"❌ {name}  {ex}")

    contact_sheet(
        [(e["name"], os.path.join(out_dir, e.get("folder", ""), e["name"] + ".png")) for e in manifest["assets"]],
        os.path.join(preview_dir, "_contact_sheet.png"),
    )
    _write_report(os.path.join(base, "batch_report.md"), results, pal_path if palette is not None else None, base)
    return results


STATUS_ZH = {"done": "已处理", "fresh": "已是最新", "missing": "缺原图", "failed": "失败"}


def _write_report(path: str, results: List[Result], palette: Optional[str], base: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# 批处理报告\n\n生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"调色板：{os.path.relpath(palette, base) if palette else '无（各图独立减色）'}\n\n")
        f.write("| 素材 | 状态 | 说明 |\n|---|---|---|\n")
        for r in results:
            f.write(f"| {r.name} | {STATUS_ZH[r.status]} | {r.note} |\n")
        f.write("\n总览图：`assets/_preview/_contact_sheet.png`\n")
