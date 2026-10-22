"""
修仙装备母版流水线：AI 原图 → 96x96 仙品母版（主体 78px）→ 十阶品质变色。

用法：
    python scripts/process_ai_equip.py 飞剑原图.jpg D:\\projects\\xiuxian-game\\textures\\equip\\96x96 --slot weapon
    python scripts/process_ai_equip.py --tiers-only D:\\projects\\xiuxian-game\\textures\\equip\\96x96
        （对目录里已有的 <slot>_xian.png 全部重新生成十阶变体）

参数与旧版 process_ai_equip_assets.py 一致：rembg 严格蒙版、透明阈值 120、飞屑 25、36 色。
"""
import argparse
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from truepixel.pipeline import process_image  # noqa: E402
from truepixel.tiers import MASTER_TIER, SLOTS, generate_tiers  # noqa: E402


def make_master(src: str, out_dir: str, slot: str) -> str:
    native, _ = process_image(
        Image.open(src), target_size=96, content_size=78, color_count=36,
        post_process_mask=True, alpha_threshold=120, noise_filter_area=25,
    )
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{slot}_{MASTER_TIER}.png")
    native.save(path)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", nargs="?", help="AI 原图")
    ap.add_argument("out_dir")
    ap.add_argument("--slot", choices=SLOTS)
    ap.add_argument("--tiers-only", action="store_true")
    a = ap.parse_args()

    if a.tiers_only:
        for slot in SLOTS:
            master = os.path.join(a.out_dir, f"{slot}_{MASTER_TIER}.png")
            if os.path.exists(master):
                generate_tiers(master, a.out_dir, slot)
                print(f"✅ {slot}：10 阶")
        return
    if not (a.src and a.slot):
        ap.error("需要 src 和 --slot（或使用 --tiers-only）")
    master = make_master(a.src, a.out_dir, a.slot)
    generate_tiers(master, a.out_dir, a.slot)
    print(f"✅ {master} 及 10 阶变体")


if __name__ == "__main__":
    main()
