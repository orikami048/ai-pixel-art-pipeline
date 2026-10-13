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
from true_pixel_core import process_image

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

            raw_b64 = data.get("image_base64", "")
            if "," in raw_b64:
                raw_b64 = raw_b64.split(",", 1)[1]

            image_bytes = base64.b64decode(raw_b64)
            raw_pil = Image.open(io.BytesIO(image_bytes))
            raw_w, raw_h = raw_pil.size

            target_size = int(data.get("target_size", 96))
            color_count = int(data.get("color_count", 32))
            remove_bg = bool(data.get("remove_bg", True))
            apply_outline = bool(data.get("apply_outline", True))
            outline_color = tuple(data.get("outline_color", [18, 20, 26]))
            noise_area = int(data.get("noise_area", 18))

            native_img, preview_4x = process_image(
                input_image=raw_pil,
                target_size=target_size,
                color_count=color_count,
                remove_bg=remove_bg,
                apply_outline=apply_outline,
                outline_color=outline_color,
                noise_filter_area=noise_area
            )

            # Convert results to Base64 PNGs
            buf_native = io.BytesIO()
            native_img.save(buf_native, format="PNG")
            b64_native = "data:image/png;base64," + base64.b64encode(buf_native.getvalue()).decode("utf-8")

            buf_4x = io.BytesIO()
            preview_4x.save(buf_4x, format="PNG")
            b64_4x = "data:image/png;base64," + base64.b64encode(buf_4x.getvalue()).decode("utf-8")

            # Count actual unique colors
            arr_np = np.array(native_img)
            unique_colors = len(np.unique(arr_np.reshape(-1, 4), axis=0))

            response_data = {
                "success": True,
                "native_base64": b64_native,
                "preview4x_base64": b64_4x,
                "target_size": target_size,
                "raw_width": raw_w,
                "raw_height": raw_h,
                "actual_colors": min(unique_colors, color_count)
            }

            resp_bytes = json.dumps(response_data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)

        except Exception as e:
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
