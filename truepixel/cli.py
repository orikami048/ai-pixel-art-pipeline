"""
命令行入口：truepixel <子命令> ...

  truepixel single  原图.png 成品.png --size 96 --colors 32
  truepixel batch   asset_list.json [--force] [--only 名字 ...]
  truepixel sheet   九宫格.png 精灵表.png --rows 3 --cols 3 --frames 8 --size 96
  truepixel tiers   weapon_xian.png 输出目录 --slot weapon
  truepixel serve   [--port 7860] [--no-browser]

没有 pip install 时也可以用：python -m truepixel <子命令> ...
"""
from __future__ import annotations

import argparse
import os
import sys

from PIL import Image


def _utf8_console() -> None:
    if sys.platform == "win32":
        for s in (sys.stdout, sys.stderr):
            try:
                s.reconfigure(encoding="utf-8")
            except Exception:
                pass


def _save(img: Image.Image, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    img.save(path)


def cmd_single(a) -> None:
    from . import ops
    from .pipeline import process_image, process_vfx_image

    src = Image.open(a.input)
    if a.vfx:
        native, prev = process_vfx_image(src, a.size, a.colors, glow_gain=a.glow)
    else:
        native, prev = process_image(
            src, a.size, a.colors,
            remove_bg=not a.keep_bg, apply_outline=not a.no_outline,
            outline_color=ops.parse_hex_color(a.outline_color),
            noise_filter_area=a.noise, erosion_iter=a.erode,
            post_process_mask=a.strict_mask, alpha_threshold=a.alpha_threshold,
            palette=ops.load_palette(a.palette) if a.palette else None,
            content_size=a.content_size,
        )
    _save(native, a.output)
    print(f"✅ {a.output}  {native.width}x{native.height}，{ops.count_colors(native)} 色")
    if a.preview:
        _save(ops.preview(native, a.preview), a.output[:-4] + f"_preview{a.preview}x.png")


def cmd_batch(a) -> None:
    from .batch import run

    results = run(a.manifest, force=a.force, only=a.only)
    counts = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    print("汇总：" + "，".join(f"{k} {v}" for k, v in counts.items()))
    if counts.get("failed"):
        sys.exit(1)


def cmd_sheet(a) -> None:
    from . import ops
    from .pipeline import process_sheet

    strip, frames = process_sheet(
        Image.open(a.input), a.rows, a.cols, a.frames, a.size, a.colors,
        outline=not a.no_outline,
        palette=ops.load_palette(a.palette) if a.palette else None,
    )
    _save(strip, a.output)
    print(f"✅ {a.output}  {strip.width}x{strip.height}（{len(frames)} 帧）")
    if a.frames_dir:
        for i, f in enumerate(frames):
            _save(f, os.path.join(a.frames_dir, f"frame_{i}.png"))
    if a.hd:
        _save(ops.preview(strip, a.hd), a.output[:-4] + f"_{a.hd}x.png")


def cmd_tiers(a) -> None:
    from .tiers import generate_tiers

    for p in generate_tiers(a.master, a.out_dir, a.slot):
        print(p)



def cmd_hd(a) -> None:
    from . import ops
    from .pipeline import process_hd_pixel

    src = Image.open(a.input)
    hd_img, low_res = process_hd_pixel(
        src,
        target_size=a.target,
        grid_size=a.grid,
        pixel_size=a.pixel_size,
    )
    _save(hd_img, a.output)
    print(f"✅ {a.output}  2K真像素完成：{hd_img.width}x{hd_img.height}（基准网格 {low_res.width}x{low_res.height}，保持原色无滤色）")
    if a.preview:
        _save(low_res, a.output[:-4] + "_grid.png")

def cmd_serve(a) -> None:
    from .server import run_server

    run_server(a.port, host=a.host, open_browser=not a.no_browser)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="truepixel", description="AI 伪像素图 → 真像素游戏素材")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("single", help="处理单张图")
    s.add_argument("input")
    s.add_argument("output")
    s.add_argument("--size", type=int, default=96, help="目标边长（默认 96）")
    s.add_argument("--content-size", type=int, help="主体最长边像素（默认铺满）")
    s.add_argument("--colors", type=int, default=32)
    s.add_argument("--palette", help="调色板 PNG，给了就统一映射到它")
    s.add_argument("--keep-bg", action="store_true", help="不去背景（地图图块）")
    s.add_argument("--no-outline", action="store_true")
    s.add_argument("--outline-color", default="#12141a")
    s.add_argument("--noise", type=int, default=18, help="去除面积 <= N 的飞屑")
    s.add_argument("--erode", type=int, default=1, help="暗边收缩圈数 0~3")
    s.add_argument("--alpha-threshold", type=int, default=100)
    s.add_argument("--strict-mask", action="store_true", help="rembg post_process_mask（边缘更干净但可能吃掉细节）")
    s.add_argument("--vfx", action="store_true", help="按发光特效处理（暗色/绿幕背景）")
    s.add_argument("--glow", type=float, default=1.15)
    s.add_argument("--preview", type=int, metavar="N", help="另存放大 N 倍预览")
    s.set_defaults(func=cmd_single)

    b = sub.add_parser("batch", help="按素材清单批量处理")
    b.add_argument("manifest")
    b.add_argument("--force", action="store_true", help="全部重新处理")
    b.add_argument("--only", nargs="*", help="只处理这些素材名")
    b.set_defaults(func=cmd_batch)

    sh = sub.add_parser("sheet", help="网格动画图 → 横向精灵表（固定锚点不抖动）")
    sh.add_argument("input")
    sh.add_argument("output")
    sh.add_argument("--rows", type=int, default=3)
    sh.add_argument("--cols", type=int, default=3)
    sh.add_argument("--frames", type=int, default=8)
    sh.add_argument("--size", type=int, default=96, help="单帧边长")
    sh.add_argument("--colors", type=int, default=32)
    sh.add_argument("--palette")
    sh.add_argument("--no-outline", action="store_true")
    sh.add_argument("--frames-dir", help="另存单帧到此目录")
    sh.add_argument("--hd", type=int, metavar="N", help="另存放大 N 倍高清版")
    sh.set_defaults(func=cmd_sheet)

    t = sub.add_parser("tiers", help="仙品母版 → 十阶品质变色")
    t.add_argument("master")
    t.add_argument("out_dir")
    t.add_argument("--slot", required=True, help="部位名，如 weapon / armor")
    t.set_defaults(func=cmd_tiers)

    
    hd = sub.add_parser("hd", help="全景背景 → 2K 高清真像素（绝无滤色，点对点锐利方块）")
    hd.add_argument("input", help="输入背景图")
    hd.add_argument("output", help="输出 2K 图像路径")
    hd.add_argument("--target", type=int, default=2048, help="目标最长边（默认 2048，即 2K）")
    hd.add_argument("--grid", type=int, help="基准像素网格最长边（如 512, 640；默认自适应）")
    hd.add_argument("--pixel-size", type=int, help="每个像素方块对应的原图像素大小（如 2, 4）")
    hd.add_argument("--preview", action="store_true", help="另存一份基准网格低清图")
    hd.set_defaults(func=cmd_hd)

    sv = sub.add_parser("serve", help="启动网页工作室")
    sv.add_argument("--port", type=int, default=7860)
    sv.add_argument("--host", default="127.0.0.1", help="0.0.0.0 可让局域网内手机访问")
    sv.add_argument("--no-browser", action="store_true")
    sv.set_defaults(func=cmd_serve)
    return p


def main(argv=None) -> None:
    _utf8_console()
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
