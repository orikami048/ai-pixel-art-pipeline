"""
运行：python -m unittest discover -s tests -v
不依赖 rembg：测试里强制使用纯色背景抠图，保证在任何机器上结果一致。
"""
import base64
import io
import json
import os
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from truepixel import background, ops  # noqa: E402
from truepixel.pipeline import composite_layers, process_hd_pixel, process_image, process_sheet, process_vfx_image  # noqa: E402

background.rembg_available = lambda: False  # 测试一律走纯色背景抠图


def sword_on_white(size=512) -> Image.Image:
    """模拟 AI 原图：白底、带模糊边缘的红色宝剑形状。"""
    im = Image.new("RGB", (size, size), (250, 250, 248))
    d = ImageDraw.Draw(im)
    d.polygon([(256, 40), (290, 330), (222, 330)], fill=(200, 40, 40))
    d.rectangle([180, 330, 332, 350], fill=(150, 110, 40))
    d.rectangle([244, 350, 268, 460], fill=(90, 60, 30))
    return im


def outline_reference(rgba, color):
    """旧版的逐像素循环实现，用来验证向量化版本结果完全一致。"""
    h, w = rgba.shape[:2]
    a = rgba[:, :, 3]
    edge = np.zeros((h, w), bool)
    for y in range(h):
        for x in range(w):
            if a[y, x] > 0:
                for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    ny, nx = y + dy, x + dx
                    if not (0 <= ny < h and 0 <= nx < w) or a[ny, nx] == 0:
                        edge[y, x] = True
                        break
    out = rgba.copy()
    out[edge, :3] = color
    out[edge, 3] = 255
    return out


class OpsTest(unittest.TestCase):

    def test_outline_matches_legacy_loop(self):
        rng = np.random.default_rng(0)
        for _ in range(20):
            arr = rng.integers(0, 255, (24, 31, 4), dtype=np.uint8)
            arr[:, :, 3] = np.where(rng.random((24, 31)) > 0.4, 255, 0)
            np.testing.assert_array_equal(ops.add_outline(arr, (1, 2, 3)), outline_reference(arr, (1, 2, 3)))

    def test_remove_specks(self):
        arr = np.zeros((20, 20, 4), np.uint8)
        arr[2:10, 2:10] = 255   # 64 像素，保留
        arr[15, 15] = 255       # 1 像素飞屑，删除
        out = ops.remove_specks(arr, 5)
        self.assertEqual(out[15, 15, 3], 0)
        self.assertEqual(out[5, 5, 3], 255)

    def test_palette_mapping(self):
        pal = np.array([[0, 0, 0], [255, 0, 0]], np.int32)
        arr = np.zeros((2, 2, 4), np.uint8)
        arr[0, 0] = (240, 10, 10, 255)
        arr[0, 1] = (20, 20, 20, 255)
        out = ops.map_to_palette(arr, pal)
        self.assertEqual(tuple(out[0, 0, :3]), (255, 0, 0))
        self.assertEqual(tuple(out[0, 1, :3]), (0, 0, 0))
        self.assertEqual(out[1, 1, 3], 0)

    def test_parse_hex(self):
        self.assertEqual(ops.parse_hex_color("#12141a"), (18, 20, 26))


class PipelineTest(unittest.TestCase):

    def test_sprite_is_true_pixel(self):
        native, prev = process_image(sword_on_white(), target_size=32, color_count=16)
        arr = np.array(native)
        self.assertEqual(native.size, (32, 32))
        self.assertEqual(set(np.unique(arr[:, :, 3])), {0, 255})      # 无半透明
        self.assertLessEqual(ops.count_colors(native), 17)             # 16 色 + 描边
        self.assertEqual(prev.size, (128, 128))
        self.assertTrue((arr[ops.edge_mask(arr[:, :, 3]), :3] == (18, 20, 26)).all())  # 外圈全是描边色

    def test_palette_applies_to_outline_too(self):
        pal = np.array([[0, 0, 0], [200, 40, 40], [150, 110, 40], [90, 60, 30]], np.int32)
        native, _ = process_image(sword_on_white(), 32, 16, palette=pal)
        used = {tuple(c) for c in np.array(native).reshape(-1, 4) if c[3]}
        self.assertTrue(used <= {(*c, 255) for c in map(tuple, pal)})

    def test_tile_fills_canvas(self):
        tile = Image.fromarray(np.random.default_rng(1).integers(0, 255, (256, 256, 3), dtype=np.uint8))
        native, _ = process_image(tile, 16, 16, remove_bg=False, apply_outline=False)
        self.assertTrue((np.array(native)[:, :, 3] == 255).all())

    def test_content_size(self):
        native, _ = process_image(sword_on_white(), target_size=96, content_size=78)
        x0, y0, x1, y1 = native.getbbox()
        self.assertLessEqual(max(x1 - x0, y1 - y0), 78)

    def test_vfx_keeps_soft_alpha(self):
        im = Image.new("RGB", (200, 200), (0, 0, 0))
        ImageDraw.Draw(im).ellipse([50, 50, 150, 150], fill=(90, 160, 255))
        native, _ = process_vfx_image(im, 48)
        self.assertEqual(native.size, (48, 48))
        self.assertTrue(np.array(native)[:, :, 3].max() > 0)

    def test_screen_solid_on_top_uses_each_channel(self):
        """旧版 bug：screen + solid_on_top 时 G、B 通道误用了 R 通道。"""
        solid = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        vfx = Image.new("RGBA", (4, 4), (0, 0, 255, 255))   # 纯蓝光
        out = np.array(composite_layers(solid, vfx, glow_intensity=1.0, blend_mode="screen",
                                        layer_order="solid_on_top"))
        self.assertEqual(out[0, 0, 0], 0)
        self.assertEqual(out[0, 0, 2], 255)

    def test_sheet_fixed_anchor(self):
        """各帧脚底和中心对齐：同样大小的角色，每帧 bbox 一致。"""
        sheet = Image.new("RGB", (300, 300), (255, 255, 255))
        d = ImageDraw.Draw(sheet)
        for i in range(9):
            c, r = i % 3, i // 3
            d.rectangle([c * 100 + 30, r * 100 + 20, c * 100 + 70, r * 100 + 90], fill=(40, 90, 200))
        strip, frames = process_sheet(sheet, frames=8, frame_size=48, outline=True)
        self.assertEqual(strip.size, (48 * 8, 48))
        boxes = {f.getbbox() for f in frames}
        self.assertEqual(len(boxes), 1)
        self.assertEqual(next(iter(boxes))[3], 48 - 3)  # 脚底在 baseline


class BatchTest(unittest.TestCase):

    def test_batch_end_to_end(self):
        from truepixel import batch

        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "raw"))
            sword_on_white().save(os.path.join(d, "raw", "item_sword.png"))
            with open(os.path.join(d, "asset_list.json"), "w", encoding="utf-8") as f:
                json.dump({"defaults": {"max_colors": 16},
                           "assets": [{"name": "item_sword", "folder": "items", "size": 32},
                                      {"name": "item_missing", "folder": "items", "size": 16}]}, f)
            res = {r.name: r.status for r in batch.run(os.path.join(d, "asset_list.json"), log=lambda *_: None)}
            self.assertEqual(res, {"item_sword": "done", "item_missing": "missing"})
            self.assertTrue(os.path.exists(os.path.join(d, "assets", "items", "item_sword.png")))
            self.assertTrue(os.path.exists(os.path.join(d, "assets", "_preview", "_contact_sheet.png")))
            self.assertTrue(os.path.exists(os.path.join(d, "batch_report.md")))
            # 第二次运行：原图没变，跳过
            res2 = {r.name: r.status for r in batch.run(os.path.join(d, "asset_list.json"), log=lambda *_: None)}
            self.assertEqual(res2["item_sword"], "fresh")



    def test_hd_pixel_keeps_colors_and_upscales_2k(self):
        # 验证高清 2K 模式：保留原色（无滤色）、点对点硬边放大到 2K
        im = Image.new("RGB", (320, 180), (120, 180, 240))
        d = ImageDraw.Draw(im)
        # 绘制彩条渐变测试，确保原色不被破坏
        for i in range(10):
            d.rectangle([i * 30, 0, (i + 1) * 30, 180], fill=(i * 20, 255 - i * 15, 100 + i * 12))
        
        hd_img, low_res = process_hd_pixel(im, target_size=2048, grid_size=320)
        self.assertEqual(hd_img.width, 2048)
        self.assertEqual(hd_img.height, int(round(180 * (2048 / 320))))
        # 确保无滤色（颜色数丰富，未被强制压缩至16/32色）
        self.assertGreater(ops.count_colors(hd_img), 8)

class ServerTest(unittest.TestCase):

    def _b64(self, img):
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    def test_api_process_solid(self):
        from truepixel.server import handle_process

        res = handle_process({"mode": "solid", "image_base64": self._b64(sword_on_white(256)),
                              "target_size": 32, "color_count": 16})
        self.assertTrue(res["success"])
        self.assertEqual(res["target_size"], 32)
        for k in ("native_base64", "preview4x_base64", "raw_width", "raw_height", "actual_colors"):
            self.assertIn(k, res)

    def test_api_process_solid_scale(self):
        from truepixel.server import handle_process, _b64_to_pil

        # 50% scale
        res_small = handle_process({"mode": "solid", "image_base64": self._b64(sword_on_white(256)),
                                    "target_size": 64, "solid_scale": 50})
        # 100% scale
        res_normal = handle_process({"mode": "solid", "image_base64": self._b64(sword_on_white(256)),
                                     "target_size": 64, "solid_scale": 100})
        
        img_small = _b64_to_pil(res_small["native_base64"])
        img_normal = _b64_to_pil(res_normal["native_base64"])
        bbox_small = img_small.getbbox()
        bbox_normal = img_normal.getbbox()
        
        w_small = bbox_small[2] - bbox_small[0]
        w_normal = bbox_normal[2] - bbox_normal[0]
        self.assertLess(w_small, w_normal)
        self.assertAlmostEqual(w_small / w_normal, 0.5, delta=0.15)

    def test_api_process_composite(self):
        from truepixel.server import handle_process

        glow = Image.new("RGB", (128, 128), (0, 0, 0))
        ImageDraw.Draw(glow).ellipse([20, 20, 108, 108], fill=(120, 200, 255))
        res = handle_process({"mode": "composite", "layer1_base64": self._b64(sword_on_white(256)),
                              "layer2_base64": self._b64(glow), "target_size": 48, "blend_mode": "screen",
                              "layer_order": "solid_on_top"})
        self.assertIn("layer1_base64", res)
        self.assertIn("layer2_base64", res)

    def test_examples_path_traversal_blocked(self):
        from truepixel.server import EXAMPLES_DIR, _safe_join

        self.assertIsNone(_safe_join(EXAMPLES_DIR, "../truepixel/server.py"))


class LegacyCliTest(unittest.TestCase):

    def test_old_flags_translate(self):
        sys.path.insert(0, ROOT)
        import true_pixel

        self.assertEqual(true_pixel._translate(["--input", "a.png", "--output", "b.png", "--size", "64", "-c", "24"]),
                         ["single", "a.png", "b.png", "--size", "64", "--colors", "24"])
        self.assertEqual(true_pixel._translate(["-i", "s.png", "-o", "o.png", "--sheet", "--rows", "3"]),
                         ["sheet", "s.png", "o.png", "--rows", "3"])

    def test_true_pixel_core_shim(self):
        import true_pixel_core

        self.assertTrue(callable(true_pixel_core.process_image))
        self.assertTrue(callable(true_pixel_core.add_solid_pixel_outline))


if __name__ == "__main__":
    unittest.main()
