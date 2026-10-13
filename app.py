"""
TruePixel Studio - Web Application Server
==========================================
Launch single-command GUI:
    python app.py
Open: http://localhost:7860
"""

import http.server
import socketserver
import json
import base64
import io
import os
import sys
import zipfile
import webbrowser
import numpy as np
from PIL import Image
from true_pixel_core import process_image, process_vfx_image, composite_layers

# Force UTF-8 on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PORT = 7860
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
EXAMPLES_DIR = os.path.join(BASE_DIR, "examples")


class TruePixelHandler(http.server.SimpleHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            with open(os.path.join(WEB_DIR, "index.html"), "rb") as f:
                self.wfile.write(f.read())
            return
        elif self.path.startswith("/examples/"):
            rel_path = self.path[len("/examples/"):]
            file_path = os.path.join(EXAMPLES_DIR, rel_path)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                self.send_response(200)
                if file_path.endswith(".jpg") or file_path.endswith(".jpeg"):
                    self.send_header("Content-Type", "image/jpeg")
                elif file_path.endswith(".png"):
                    self.send_header("Content-Type", "image/png")
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
                return

        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/process":
            self.handle_process()
        elif self.path == "/api/download_zip":
            self.handle_download_zip()
        else:
            self.send_error(404, "Endpoint not found")

    def handle_process(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))

            mode = data.get("mode", "solid")  # 'solid' | 'vfx' | 'composite'
            target_size = int(data.get("target_size", 96))
            color_count = int(data.get("color_count", 32))
            remove_bg = bool(data.get("remove_bg", True))
            apply_outline = bool(data.get("apply_outline", True))
            outline_color = tuple(data.get("outline_color", [18, 20, 26]))
            noise_area = int(data.get("noise_area", 18))
            glow_intensity = float(data.get("glow_intensity", 1.15))
            blend_mode = str(data.get("blend_mode", "additive"))
            offset_x = int(data.get("offset_x", 0))
            offset_y = int(data.get("offset_y", 0))
            layer_order = str(data.get("layer_order", "vfx_on_top"))

            def b64_to_pil(b64_str):
                if not b64_str:
                    return None
                if "," in b64_str:
                    b64_str = b64_str.split(",", 1)[1]
                return Image.open(io.BytesIO(base64.b64decode(b64_str)))

            def pil_to_b64(pil_img):
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

            if mode == "composite":
                layer1_pil = b64_to_pil(data.get("layer1_base64", ""))
                layer2_pil = b64_to_pil(data.get("layer2_base64", ""))
                if layer1_pil is None or layer2_pil is None:
                    single_pil = b64_to_pil(data.get("image_base64", ""))
                    if single_pil is None:
                        raise ValueError("双层合体模式需要提供图层 1 (实体) 和图层 2 (特效)！")
                    layer1_pil = single_pil
                    layer2_pil = single_pil

                solid_native, _ = process_image(
                    input_image=layer1_pil,
                    target_size=target_size,
                    color_count=color_count,
                    remove_bg=remove_bg,
                    apply_outline=apply_outline,
                    outline_color=outline_color,
                    noise_filter_area=noise_area
                )

                vfx_native, _ = process_vfx_image(
                    input_image=layer2_pil,
                    target_size=target_size,
                    color_count=color_count,
                    glow_gain=glow_intensity
                )

                comp_native = composite_layers(
                    solid_img=solid_native,
                    vfx_img=vfx_native,
                    glow_intensity=glow_intensity,
                    blend_mode=blend_mode,
                    offset_x=offset_x,
                    offset_y=offset_y,
                    layer_order=layer_order
                )

                preview_scale = 4 if target_size <= 256 else (2 if target_size <= 512 else 1)
                preview_w = target_size * preview_scale
                preview_4x = comp_native.resize((preview_w, preview_w), Image.Resampling.NEAREST)

                native_img = comp_native
                raw_w, raw_h = layer1_pil.size
                extra_payload = {
                    "layer1_base64": pil_to_b64(solid_native),
                    "layer2_base64": pil_to_b64(vfx_native)
                }

            elif mode == "vfx":
                raw_pil = b64_to_pil(data.get("image_base64", ""))
                if raw_pil is None:
                    raise ValueError("请提供发光特效图像！")
                raw_w, raw_h = raw_pil.size
                native_img, preview_4x = process_vfx_image(
                    input_image=raw_pil,
                    target_size=target_size,
                    color_count=color_count,
                    glow_gain=glow_intensity
                )
                extra_payload = {}

            else:  # 'solid'
                raw_pil = b64_to_pil(data.get("image_base64", ""))
                if raw_pil is None:
                    raise ValueError("请提供实体道具图像！")
                raw_w, raw_h = raw_pil.size
                native_img, preview_4x = process_image(
                    input_image=raw_pil,
                    target_size=target_size,
                    color_count=color_count,
                    remove_bg=remove_bg,
                    apply_outline=apply_outline,
                    outline_color=outline_color,
                    noise_filter_area=noise_area
                )
                extra_payload = {}

            b64_native = pil_to_b64(native_img)
            b64_4x = pil_to_b64(preview_4x)

            # Count actual unique colors
            arr_np = np.array(native_img)
            unique_colors = len(np.unique(arr_np.reshape(-1, 4), axis=0))

            response_data = {
                "success": True,
                "mode": mode,
                "native_base64": b64_native,
                "preview4x_base64": b64_4x,
                "target_size": target_size,
                "raw_width": raw_w,
                "raw_height": raw_h,
                "actual_colors": min(unique_colors, color_count),
                **extra_payload
            }

            resp_bytes = json.dumps(response_data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)

        except Exception as e:
            import traceback
            traceback.print_exc()
            err_msg = json.dumps({"error": str(e)}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err_msg)))
            self.end_headers()
            self.wfile.write(err_msg)

    def handle_download_zip(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
            items = data.get("items", [])

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for idx, item in enumerate(items):
                    name = item.get("name") or f"asset_{idx}"
                    native_b64 = item.get("native_base64", "")
                    if native_b64:
                        if "," in native_b64:
                            native_b64 = native_b64.split(",", 1)[1]
                        zf.writestr(f"native_pixel/{name}_native.png", base64.b64decode(native_b64))

                    preview_b64 = item.get("preview4x_base64", "")
                    if preview_b64:
                        if "," in preview_b64:
                            preview_b64 = preview_b64.split(",", 1)[1]
                        zf.writestr(f"preview_4x/{name}_preview4x.png", base64.b64decode(preview_b64))

            zip_bytes = zip_buffer.getvalue()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", 'attachment; filename="true_pixel_assets.zip"')
            self.send_header("Content-Length", str(len(zip_bytes)))
            self.end_headers()
            self.wfile.write(zip_bytes)

        except Exception as e:
            self.send_error(500, f"Zip error: {str(e)}")


class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


def run_server(port=PORT):
    while port < 7900:
        try:
            server = ThreadingHTTPServer(("0.0.0.0", port), TruePixelHandler)
            print("=" * 60)
            print(f" 🎨 TruePixel Studio Web GUI is LIVE!")
            print(f" -> Access URL: http://localhost:{port}/")
            print(f" -> Localhost:  http://127.0.0.1:{port}/")
            print("=" * 60)
            # Auto-open browser in 0.6 seconds
            try:
                import threading
                threading.Timer(0.6, lambda p=port: webbrowser.open(f"http://localhost:{p}/")).start()
            except Exception:
                pass
            break
        except OSError:
            port += 1

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[TruePixel Studio] Server stopped.")
        server.server_close()


if __name__ == "__main__":
    run_server()
