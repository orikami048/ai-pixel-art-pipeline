"""
TruePixel 网页工作室的后端（仅用标准库 http.server）。

接口与旧版 app.py 完全一致，web/index.html 无需改动：
  GET  /                 → web/index.html
  GET  /examples/<文件>   → examples/ 下的示例图
  POST /api/process      → 处理单图 / 特效 / 双层合成
  POST /api/download_zip → 打包批量结果
"""
from __future__ import annotations

import base64
import http.server
import io
import json
import mimetypes
import os
import socketserver
import threading
import traceback
import webbrowser
import zipfile

from PIL import Image

from . import ops
from .pipeline import composite_layers, process_image, process_vfx_image, process_hd_pixel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(ROOT, "web")
EXAMPLES_DIR = os.path.join(ROOT, "examples")
DEFAULT_PORT = 7860


def _b64_to_pil(s: str):
    if not s:
        return None
    if "," in s:
        s = s.split(",", 1)[1]
    return Image.open(io.BytesIO(base64.b64decode(s)))


def _pil_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _strip_b64(s: str) -> bytes:
    return base64.b64decode(s.split(",", 1)[1] if "," in s else s)


def handle_process(data: dict) -> dict:
    """/api/process 的纯函数版本，方便测试。"""
    mode = data.get("mode", "solid")
    size = int(data.get("target_size", 96))
    colors = int(data.get("color_count", 32))
    strict = bool(data.get("post_process_mask", False))
    solid_kw = dict(
        target_size=size,
        color_count=colors,
        remove_bg=bool(data.get("remove_bg", True)),
        apply_outline=bool(data.get("apply_outline", True)),
        outline_color=ops.as_color(data.get("outline_color", [18, 20, 26])),
        noise_filter_area=int(data.get("noise_area", 18)),
        post_process_mask=strict,
        alpha_threshold=int(data.get("alpha_threshold", 120 if strict else 100)),
    )
    glow = float(data.get("glow_intensity", 1.15))
    extra = {}

    if mode == "composite":
        l1 = _b64_to_pil(data.get("layer1_base64", ""))
        l2 = _b64_to_pil(data.get("layer2_base64", ""))
        if l1 is None or l2 is None:
            single = _b64_to_pil(data.get("image_base64", ""))
            if single is None:
                raise ValueError("双层合体模式需要提供图层 1 (实体) 和图层 2 (特效)！")
            l1 = l2 = single
        solid, _ = process_image(l1, **solid_kw)
        vfx, _ = process_vfx_image(l2, size, colors, glow_gain=glow)
        solid_scale = float(data.get("solid_scale", 100)) / 100.0
        native = composite_layers(
            solid, vfx, glow_intensity=glow,
            blend_mode=str(data.get("blend_mode", "additive")),
            offset_x=int(data.get("offset_x", 0)), offset_y=int(data.get("offset_y", 0)),
            scale_x=float(data.get("scale_x", 1.0)), scale_y=float(data.get("scale_y", 1.0)),
            rotation=float(data.get("rotation", 0.0)),
            canvas_padding=float(data.get("canvas_padding", 0.0)),
            layer_order=str(data.get("layer_order", "vfx_on_top")),
            solid_scale=solid_scale,
        )
        prev = ops.preview(native)
        raw_w, raw_h = l1.size
        extra = {"layer1_base64": _pil_to_b64(solid), "layer2_base64": _pil_to_b64(vfx)}
    else:
        raw = _b64_to_pil(data.get("image_base64", ""))
        if raw is None:
            raise ValueError("请提供发光特效图像！" if mode == "vfx" else "请提供实体道具图像！")
        raw_w, raw_h = raw.size
        solid_scale = float(data.get("solid_scale", 100)) / 100.0
        if solid_scale > 0 and solid_scale != 1.0:
            base_box = size - (2 if solid_kw.get("apply_outline", True) else 0)
            solid_kw["content_size"] = max(1, int(round(base_box * solid_scale)))

        if mode == "vfx":
            native, prev = process_vfx_image(raw, size, colors, glow_gain=glow)
        elif mode == "hd":
            target_hd = int(data.get("target_size", 2048))
            grid_hd = int(data.get("grid_size", 0)) or None
            pixel_hd = int(data.get("pixel_size", 0)) or None
            native, prev = process_hd_pixel(raw, target_size=target_hd, grid_size=grid_hd, pixel_size=pixel_hd)
        else:
            native, prev = process_image(raw, **solid_kw)

    return {
        "success": True,
        "mode": mode,
        "native_base64": _pil_to_b64(native),
        "preview4x_base64": _pil_to_b64(prev),
        "target_size": size,
        "raw_width": raw_w,
        "raw_height": raw_h,
        "actual_colors": min(ops.count_colors(native), colors),
        **extra,
    }


def build_zip(items: list) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, it in enumerate(items):
            name = os.path.basename(it.get("name") or f"asset_{i}")
            if it.get("native_base64"):
                zf.writestr(f"native_pixel/{name}_native.png", _strip_b64(it["native_base64"]))
            if it.get("preview4x_base64"):
                zf.writestr(f"preview_4x/{name}_preview4x.png", _strip_b64(it["preview4x_base64"]))
    return buf.getvalue()


def _safe_join(root: str, rel: str):
    """防止 /examples/../../ 之类的路径穿越。"""
    path = os.path.realpath(os.path.join(root, rel))
    return path if path.startswith(os.path.realpath(root) + os.sep) else None


class Handler(http.server.BaseHTTPRequestHandler):

    def _send(self, code: int, body: bytes, ctype: str, extra_headers=None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, obj: dict) -> None:
        self._send(code, json.dumps(obj).encode(), "application/json")

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            with open(os.path.join(WEB_DIR, "index.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if path.startswith("/examples/"):
            fp = _safe_join(EXAMPLES_DIR, path[len("/examples/"):])
            if fp and os.path.isfile(fp):
                with open(fp, "rb") as f:
                    return self._send(200, f.read(), mimetypes.guess_type(fp)[0] or "application/octet-stream")
        self.send_error(404)

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def do_POST(self):
        try:
            if self.path == "/api/process":
                self._send_json(200, handle_process(self._read_json()))
            elif self.path == "/api/download_zip":
                body = build_zip(self._read_json().get("items", []))
                self._send(200, body, "application/zip",
                           {"Content-Disposition": 'attachment; filename="true_pixel_assets.zip"'})
            else:
                self.send_error(404, "Endpoint not found")
        except Exception as e:
            traceback.print_exc()
            self._send_json(500, {"error": str(e)})


class ThreadingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


def run_server(port: int = DEFAULT_PORT, host: str = "127.0.0.1", open_browser: bool = True) -> None:
    """端口被占用时自动顺延（最多到 7899）。默认只监听本机。"""
    server = None
    while port < 7900:
        try:
            server = ThreadingServer((host, port), Handler)
            break
        except OSError:
            port += 1
    if server is None:
        raise SystemExit("7860~7899 端口全被占用")

    url = f"http://127.0.0.1:{port}/"
    print("=" * 60)
    print(f" 🎨 TruePixel Studio 已启动：{url}")
    print("=" * 60)
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[TruePixel Studio] 已停止")
        server.server_close()
    
