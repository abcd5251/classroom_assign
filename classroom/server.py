"""本機網頁伺服器：提供 web/ 的頁面，以及 /api/classes、/api/ping、/api/sync。只接受這台電腦連線。"""
import json
import traceback
from http.server import HTTPServer, SimpleHTTPRequestHandler

from . import rosters, sheets
from .config import WEB


class Handler(SimpleHTTPRequestHandler):
    origins = ()

    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(WEB), **k)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/classes":
            return self.reply(rosters.load_all())
        super().do_GET()

    def do_POST(self):
        origin = self.headers.get("Origin")
        if origin and origin not in self.origins:
            return self.send_error(403)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if self.path == "/api/ping":
                out = sheets.ping()
            elif self.path == "/api/sync":
                out = sheets.sync(body)
                print(f"☁️  已寫入 Google Sheet：{out['sheet']} 班 {out['date']}，{out['count']} 位同學", flush=True)
            else:
                return self.send_error(404)
        except sheets.UserError as e:
            print(f"❌ {e}", flush=True)
            out = {"ok": False, "error": str(e)}
        except Exception as e:
            traceback.print_exc()
            out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        self.reply(out)

    def reply(self, obj):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")   # 改了 web/ 的檔案，重新整理就生效
        super().end_headers()

    def log_message(self, *a):
        pass


def create(port):
    Handler.origins = (f"http://127.0.0.1:{port}", f"http://localhost:{port}")
    return HTTPServer(("127.0.0.1", port), Handler)
