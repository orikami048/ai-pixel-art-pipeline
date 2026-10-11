"""
TruePixel Equipment Engine
--------------------------
Generates production-grade 32x32 retro pixel art game icons for all 8 equipment slots:
1. weapon   (飞剑 / Flying Sword)
2. armor    (法袍 / Celestial Robe)
3. head     (冠簪 / Lotus Hairpin & Crown)
4. hand     (护腕 / Dragonscale Bracers)
5. foot     (法靴 / Cloud-Treading Boots)
6. offhand  (法镜 / Bagua Mirror)
7. necklace (灵佩 / Jade Pendant)
8. ring     (须弥 / Sumeru Ring)

Each across 6 standard Cultivation qualities:
- fan   (凡品: 灰铁黑石)
- ling  (灵品: 碧玉青竹)
- xuan  (玄品: 寒铁幽蓝)
- bao   (宝品: 紫霄灵晶)
- xian  (仙品: 朱赤真炎)
- shen  (神品: 太虚璀璨金)

Outputs:
- 32x32 native pixel PNGs
- 96x96 (3x nearest-neighbor) crisp HD pixel PNGs
- Unified equip spritesheet
"""

import os
from PIL import Image
import numpy as np


def add_solid_pixel_outline(rgba_arr: np.ndarray, outline_color=(20, 18, 26)) -> np.ndarray:
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


# 10阶修仙品质色彩与背景粒子矩阵 (Ten Cultivation Quality Tiers & Background Particle Colors)
TIER_SPECS = {
    1: {
        "id": "fan",
        "name": "一阶·凡品",
        "particle_color": "140, 140, 140",      # 灰白凡铁微屑
        "particle_hex": "#8c8c8c",
        "hi": (215, 218, 222), "mid": (145, 150, 158), "dark": (85, 90, 98),
        "gem": (175, 160, 145), "trim": (120, 110, 95)
    },
    2: {
        "id": "liang",
        "name": "二阶·良品",
        "particle_color": "82, 196, 26",        # 苍翠草木生机
        "particle_hex": "#52c41a",
        "hi": (210, 245, 185), "mid": (90, 185, 45), "dark": (45, 110, 22),
        "gem": (195, 235, 120), "trim": (70, 140, 35)
    },
    3: {
        "id": "ling",
        "name": "三阶·灵品",
        "particle_color": "19, 194, 194",       # 碧灵青翠玉光
        "particle_hex": "#13c2c2",
        "hi": (185, 250, 225), "mid": (45, 180, 145), "dark": (22, 105, 82),
        "gem": (120, 245, 220), "trim": (160, 220, 110)
    },
    4: {
        "id": "xuan",
        "name": "四阶·玄品",
        "particle_color": "22, 119, 255",       # 幽蓝寒铁星屑
        "particle_hex": "#1677ff",
        "hi": (195, 235, 255), "mid": (42, 130, 225), "dark": (18, 70, 140),
        "gem": (130, 225, 255), "trim": (110, 175, 235)
    },
    5: {
        "id": "di",
        "name": "五阶·地品",
        "particle_color": "212, 136, 6",        # 地脉真金厚土
        "particle_hex": "#d48806",
        "hi": (255, 235, 185), "mid": (205, 125, 20), "dark": (125, 75, 10),
        "gem": (255, 210, 80), "trim": (165, 100, 15)
    },
    6: {
        "id": "tian",
        "name": "六阶·天品",
        "particle_color": "114, 46, 209",       # 紫霄东来天罡
        "particle_hex": "#722ed1",
        "hi": (245, 215, 255), "mid": (145, 60, 225), "dark": (80, 22, 138),
        "gem": (210, 140, 255), "trim": (185, 110, 240)
    },
    7: {
        "id": "bao",
        "name": "七阶·宝品",
        "particle_color": "235, 47, 150",       # 琉璃琼楼宝霞
        "particle_hex": "#eb2f96",
        "hi": (255, 215, 240), "mid": (220, 45, 135), "dark": (135, 20, 80),
        "gem": (255, 130, 195), "trim": (245, 95, 175)
    },
    8: {
        "id": "xian",
        "name": "八阶·仙品",
        "particle_color": "245, 34, 45",        # 焚天朱雀真炎
        "particle_hex": "#f5222d",
        "hi": (255, 215, 205), "mid": (230, 50, 40), "dark": (140, 18, 20),
        "gem": (255, 215, 0), "trim": (255, 140, 50)
    },
    9: {
        "id": "shen",
        "name": "九阶·神品",
        "particle_color": "250, 173, 20",       # 太古太阳真金
        "particle_hex": "#faad14",
        "hi": (255, 255, 220), "mid": (245, 180, 25), "dark": (160, 105, 10),
        "gem": (255, 255, 255), "trim": (255, 225, 120)
    },
    10: {
        "id": "chaos",
        "name": "十阶·混沌",
        "particle_color": "190, 80, 255",       # 鸿蒙太虚混沌紫金
        "particle_hex": "#be50ff",
        "hi": (255, 245, 255), "mid": (180, 55, 245), "dark": (50, 15, 90),
        "gem": (80, 240, 255), "trim": (255, 215, 90)
    }
}

PALETTES = {spec["id"]: spec for spec in TIER_SPECS.values()}


def create_weapon(pal) -> np.ndarray:
    """32x32 飞剑 (Flying Sword)"""
    arr = np.zeros((32, 32, 4), dtype=np.uint8)
    
    # 剑身 (对角线 25,6 到 14,17)
    for i in range(13):
        x = 24 - i
        y = 7 + i
        # 锋刃高光 (白亮/浅色)
        arr[y, x] = (*pal["hi"], 255)
        # 剑脊 (主色)
        arr[y+1, x] = (*pal["mid"], 255)
        arr[y, x-1] = (*pal["mid"], 255)
        # 背刃暗部
        arr[y+1, x-1] = (*pal["dark"], 255)
        # 剑槽流光
        if i in [3, 4, 7, 8]:
            arr[y, x] = (*pal["gem"], 255)
    
    # 剑尖
    arr[6, 25] = (*pal["hi"], 255)
    arr[6, 26] = (255, 255, 255, 255)

    # 剑格 / 护手 (剑锷)
    arr[19, 13] = (*pal["trim"], 255)
    arr[18, 14] = (*pal["trim"], 255)
    arr[20, 12] = (*pal["gem"], 255)
    arr[17, 15] = (*pal["gem"], 255)
    arr[21, 11] = (*pal["dark"], 255)
    arr[16, 16] = (*pal["dark"], 255)

    # 剑柄
    for j in range(4):
        hx = 11 - j
        hy = 21 + j
        arr[hy, hx] = (60, 45, 35, 255)
        arr[hy, hx+1] = (*pal["trim"], 255)

    # 剑首 / 剑镡
    arr[25, 7] = (*pal["trim"], 255)
    arr[25, 6] = (*pal["gem"], 255)

    # 剑穗 (飞舞红/金灵绸)
    tassel = [(26, 6), (27, 5), (28, 5), (29, 6), (28, 7), (27, 8)]
    for ty, tx in tassel:
        arr[ty, tx] = (*pal["gem"], 255)
    arr[29, 5] = (*pal["mid"], 255)
    arr[28, 4] = (*pal["hi"], 255)

    return arr


def create_armor(pal) -> np.ndarray:
    """32x32 法袍 (Daoist Robe / Celestial Silk Armor)"""
    arr = np.zeros((32, 32, 4), dtype=np.uint8)

    # 领口与肩甲
    for x in range(12, 20):
        arr[6, x] = (*pal["trim"], 255)
    arr[7, 13] = (255, 255, 255, 255)
    arr[7, 18] = (255, 255, 255, 255)

    # 双肩与云肩
    for y in range(8, 12):
        for x in range(7, 25):
            if x < 10 or x > 21:
                arr[y, x] = (*pal["trim"], 255)
            else:
                arr[y, x] = (*pal["mid"], 255)

    # 左右大袖
    for y in range(12, 20):
        for w in range(4):
            arr[y, 6 + w] = (*pal["mid"], 255)
            arr[y, 25 - w] = (*pal["mid"], 255)
        # 袖口金边
        arr[y, 6] = (*pal["hi"], 255)
        arr[y, 25] = (*pal["dark"], 255)

    # 胸襟道袍与太极/仙印
    for y in range(12, 17):
        for x in range(11, 21):
            arr[y, x] = (*pal["mid"], 255)
    # 太极心纹
    arr[13, 15] = (*pal["gem"], 255)
    arr[13, 16] = (255, 255, 255, 255)
    arr[14, 15] = (*pal["dark"], 255)
    arr[14, 16] = (*pal["gem"], 255)

    # 束腰玉带
    for x in range(10, 22):
        arr[17, x] = (*pal["trim"], 255)
        arr[18, x] = (*pal["dark"], 255)
    arr[17, 15] = (*pal["gem"], 255)
    arr[17, 16] = (*pal["gem"], 255)

    # 下摆仙裙与流云纹
    for y in range(19, 27):
        half_w = 4 + (y - 19) // 2
        for x in range(16 - half_w, 16 + half_w):
            if (x + y) % 3 == 0:
                arr[y, x] = (*pal["hi"], 255)
            elif (x - y) % 4 == 0:
                arr[y, x] = (*pal["dark"], 255)
            else:
                arr[y, x] = (*pal["mid"], 255)

    # 裙摆金边
    for x in range(9, 23):
        arr[26, x] = (*pal["trim"], 255)

    return arr


def create_head(pal) -> np.ndarray:
    """32x32 冠簪 (Phoenix Hairpin & Lotus Crown)"""
    arr = np.zeros((32, 32, 4), dtype=np.uint8)

    # 横贯金簪 (Hairpin needle) 从左上到右下微斜
    for i in range(20):
        x = 6 + i
        y = 17 - (i // 5)
        arr[y, x] = (*pal["trim"], 255)
        arr[y - 1, x] = (*pal["hi"], 255)

    # 簪首明珠 (Left gem tip)
    arr[16, 5] = (*pal["gem"], 255)
    arr[17, 5] = (*pal["gem"], 255)
    arr[16, 4] = (255, 255, 255, 255)

    # 莲花小道冠 (Center Lotus crown)
    # 底座
    for x in range(11, 21):
        arr[19, x] = (*pal["dark"], 255)
        arr[18, x] = (*pal["trim"], 255)

    # 莲瓣层 (花瓣拱起)
    for y in range(13, 18):
        for x in range(12, 20):
            arr[y, x] = (*pal["mid"], 255)
    # 中央主瓣峰
    arr[11, 15] = (*pal["gem"], 255)
    arr[11, 16] = (*pal["gem"], 255)
    arr[12, 15] = (*pal["hi"], 255)
    arr[12, 16] = (*pal["hi"], 255)
    arr[10, 15] = (255, 255, 255, 255)

    # 左右侧瓣
    arr[12, 13] = (*pal["mid"], 255)
    arr[12, 18] = (*pal["mid"], 255)
    arr[13, 11] = (*pal["hi"], 255)
    arr[13, 20] = (*pal["dark"], 255)

    # 垂落流苏 (Dangling tassels on right)
    tassel_y = [18, 19, 21, 23, 25, 26]
    for ty in tassel_y:
        arr[ty, 23] = (*pal["gem"], 255)
        if ty > 21:
            arr[ty, 24] = (*pal["mid"], 255)
    arr[26, 23] = (*pal["hi"], 255)

    return arr


def create_hand(pal) -> np.ndarray:
    """32x32 护腕 (Dragonscale Bracers)"""
    arr = np.zeros((32, 32, 4), dtype=np.uint8)

    # 左右双护腕呈现
    def draw_single_bracer(ox):
        # 腕甲主体
        for y in range(9, 23):
            w = 5 if y > 16 else 6
            for x in range(ox, ox + w):
                # 鳞片质感
                if (x + y) % 2 == 0:
                    arr[y, x] = (*pal["hi"], 255)
                else:
                    arr[y, x] = (*pal["mid"], 255)
            # 左侧高光，右侧暗边
            arr[y, ox] = (*pal["trim"], 255)
            arr[y, ox + w - 1] = (*pal["dark"], 255)

        # 核心真灵宝玉嵌槽
        arr[14, ox + 2] = (*pal["gem"], 255)
        arr[15, ox + 2] = (255, 255, 255, 255)
        arr[16, ox + 2] = (*pal["gem"], 255)

        # 腕带锁扣
        arr[9, ox:ox+w] = (*pal["trim"], 255)
        arr[22, ox:ox+w] = (*pal["trim"], 255)

    draw_single_bracer(8)
    draw_single_bracer(18)
    return arr


def create_foot(pal) -> np.ndarray:
    """32x32 法靴 (Cloud-Treading Boots)"""
    arr = np.zeros((32, 32, 4), dtype=np.uint8)

    def draw_boot(ox):
        # 靴筒
        for y in range(8, 20):
            for x in range(ox + 2, ox + 7):
                arr[y, x] = (*pal["mid"], 255)
            arr[y, ox + 2] = (*pal["hi"], 255)
            arr[y, ox + 6] = (*pal["dark"], 255)

        # 筒口金丝滚边
        for x in range(ox + 1, ox + 8):
            arr[8, x] = (*pal["trim"], 255)

        # 脚面与祥云翘头
        for x in range(ox, ox + 9):
            arr[20, x] = (*pal["mid"], 255)
            arr[21, x] = (*pal["mid"], 255)
            arr[22, x] = (*pal["dark"], 255)

        # 云靴翘头卷云 (祥云尖)
        arr[19, ox] = (*pal["trim"], 255)
        arr[18, ox - 1] = (*pal["gem"], 255)
        arr[19, ox - 1] = (*pal["hi"], 255)

        # 靴底轻灵白玉层
        for x in range(ox, ox + 9):
            arr[23, x] = (240, 245, 255, 255)

    draw_boot(6)
    draw_boot(17)

    # 脚下凌波灵气微尘
    arr[24, 7] = (*pal["hi"], 255)
    arr[25, 8] = (*pal["gem"], 255)
    arr[24, 21] = (*pal["hi"], 255)
    arr[25, 22] = (*pal["gem"], 255)

    return arr


def create_offhand(pal) -> np.ndarray:
    """32x32 法镜 (Bagua Spirit Mirror)"""
    arr = np.zeros((32, 32, 4), dtype=np.uint8)
    cx, cy = 16, 15

    # 八卦青铜/玄金外框 (八边形)
    for y in range(6, 25):
        for x in range(7, 26):
            dx = abs(x - cx)
            dy = abs(y - cy)
            # 八边形距离
            if dx <= 9 and dy <= 9 and (dx + dy) <= 13:
                # 外圈框
                if dx >= 7 or dy >= 7 or (dx + dy) >= 11:
                    arr[y, x] = (*pal["trim"], 255)
                elif dx >= 5 or dy >= 5:
                    arr[y, x] = (*pal["dark"], 255)
                else:
                    # 镜面水波流光 (Cyan / Gem sheen)
                    if (x + y) < 30:
                        arr[y, x] = (*pal["hi"], 255)
                    else:
                        arr[y, x] = (*pal["mid"], 255)

    # 镜面太极玄光
    arr[cy, cx] = (*pal["gem"], 255)
    arr[cy-1, cx] = (255, 255, 255, 255)
    arr[cy+1, cx] = (*pal["dark"], 255)
    arr[cy, cx-1] = (255, 255, 255, 255)

    # 镜钮与坠穗
    arr[25, cx] = (*pal["trim"], 255)
    arr[26, cx] = (*pal["trim"], 255)
    arr[27, cx-1] = (*pal["gem"], 255)
    arr[28, cx] = (*pal["gem"], 255)
    arr[27, cx+1] = (*pal["gem"], 255)

    return arr


def create_necklace(pal) -> np.ndarray:
    """32x32 灵佩 (Dragon Jade Pendant)"""
    arr = np.zeros((32, 32, 4), dtype=np.uint8)

    # 挂绳 (红丝绳/金线挂脖)
    cords = [
        (6, 12), (6, 19),
        (7, 13), (7, 18),
        (8, 14), (8, 17),
        (9, 14), (9, 17),
        (10, 15), (10, 16)
    ]
    for cy, cx in cords:
        arr[cy, cx] = (190, 45, 40, 255)

    # 金锁结 (Golden clasp)
    arr[11, 15] = (*pal["trim"], 255)
    arr[11, 16] = (*pal["trim"], 255)
    arr[12, 14] = (*pal["gem"], 255)
    arr[12, 17] = (*pal["gem"], 255)

    # 圆形龙纹玉璧 (Jade Bi Disc) 中心镂空
    cx, cy = 15, 18
    for y in range(13, 24):
        for x in range(10, 22):
            dist_sq = (x - cx) ** 2 + (y - cy) ** 2
            if 6 <= dist_sq <= 25:
                # 环形玉面
                if x < cx:
                    arr[y, x] = (*pal["hi"], 255)
                else:
                    arr[y, x] = (*pal["mid"], 255)
            elif dist_sq < 6:
                # 空心孔
                pass

    # 玉佩内金环线
    arr[18, 15] = (*pal["gem"], 255)

    # 下方悬垂丝穗
    for y in range(24, 29):
        arr[y, 14] = (*pal["gem"], 255)
        arr[y, 16] = (*pal["gem"], 255)
        if y < 27:
            arr[y, 15] = (255, 255, 255, 255)

    return arr


def create_ring(pal) -> np.ndarray:
    """32x32 须弥 (Sumeru Spatial Ring)"""
    arr = np.zeros((32, 32, 4), dtype=np.uint8)

    # 戒圈 (Ring band) 椭圆透视
    cx, cy = 16, 18
    for y in range(13, 25):
        for x in range(9, 24):
            dx = (x - cx) / 6.5
            dy = (y - cy) / 4.8
            d = dx * dx + dy * dy
            if 0.55 <= d <= 1.15:
                if y > 18:
                    arr[y, x] = (*pal["trim"], 255)
                else:
                    arr[y, x] = (*pal["hi"], 255)
            elif d > 1.15 and d < 1.35 and y > 18:
                arr[y, x] = (*pal["dark"], 255)

    # 顶置法宝巨钻/须弥灵核 (Faceted Gem on Top)
    for y in range(6, 14):
        for x in range(12, 21):
            gx = abs(x - cx)
            gy = abs(y - 10)
            if gx + gy <= 4:
                arr[y, x] = (*pal["gem"], 255)
            elif gx + gy == 5:
                arr[y, x] = (*pal["mid"], 255)

    # 钻石切面反光
    arr[8, 15] = (255, 255, 255, 255)
    arr[9, 15] = (255, 255, 255, 255)
    arr[8, 16] = (255, 255, 255, 255)

    # 闪耀星芒 (Cross sparkle)
    arr[7, 15] = (*pal["hi"], 255)
    arr[9, 13] = (*pal["hi"], 255)
    arr[9, 17] = (*pal["hi"], 255)

    return arr


GENERATORS = {
    "weapon": create_weapon,
    "armor": create_armor,
    "head": create_head,
    "hand": create_hand,
    "foot": create_foot,
    "offhand": create_offhand,
    "necklace": create_necklace,
    "ring": create_ring
}


def build_all_assets(output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    hd_dir = os.path.join(output_dir, "96x96")
    os.makedirs(hd_dir, exist_ok=True)

    slots = list(GENERATORS.keys())
    qualities = list(PALETTES.keys())

    # Big spritesheet grid: 8 rows (slots) x 6 cols (qualities)
    # Cell size 32x32 -> 192 x 256
    sheet_32 = Image.new("RGBA", (len(qualities) * 32, len(slots) * 32), (0, 0, 0, 0))

    total = 0
    for row_idx, slot in enumerate(slots):
        gen_fn = GENERATORS[slot]
        for col_idx, qual in enumerate(qualities):
            pal = PALETTES[qual]
            raw_arr = gen_fn(pal)
            
            # Apply 1px solid black pixel outline
            outlined_arr = add_solid_pixel_outline(raw_arr, outline_color=(18, 20, 26))
            img_32 = Image.fromarray(outlined_arr, mode="RGBA")

            # 1. Save 32x32 native PNG
            fname = f"{slot}_{qual}.png"
            path_32 = os.path.join(output_dir, fname)
            img_32.save(path_32, "PNG")

            # 2. Save 96x96 (3x nearest neighbor) HD pixel PNG
            img_96 = img_32.resize((96, 96), Image.NEAREST)
            path_96 = os.path.join(hd_dir, fname)
            img_96.save(path_96, "PNG")

            # 3. Paste into spritesheet
            sheet_32.paste(img_32, (col_idx * 32, row_idx * 32))
            total += 1

    sheet_32_path = os.path.join(output_dir, "equip_sheet_32.png")
    sheet_32.save(sheet_32_path, "PNG")

    sheet_96 = sheet_32.resize((sheet_32.width * 3, sheet_32.height * 3), Image.NEAREST)
    sheet_96_path = os.path.join(output_dir, "equip_sheet_96.png")
    sheet_96.save(sheet_96_path, "PNG")

    # 导出 10 阶品质与粒子特效清单 (JSON manifest for game engine)
    import json
    manifest_path = os.path.join(output_dir, "tier_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(TIER_SPECS, f, ensure_ascii=False, indent=2)

    print(f"[Done] Generated 8 slots x {len(qualities)} tiers = {total} pixel equipment assets!")
    print(f"[Exported] Single assets: {output_dir}")
    print(f"[Exported] 96x96 HD: {hd_dir}")
    print(f"[Exported] Spritesheet: {sheet_96_path}")
    print(f"[Exported] Tier Manifest: {manifest_path}")


if __name__ == "__main__":
    out = r"D:\projects\xiuxian-game\textures\equip"
    build_all_assets(out)

