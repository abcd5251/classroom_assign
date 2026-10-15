#!/usr/bin/env python3
"""課堂積分教室

  python3 main.py                 啟動（先辨識新的座位表照片，再打開網頁）
  python3 main.py import          只辨識 images/ 裡的新照片
  python3 main.py import --force  全部照片重新辨識（會覆蓋手動改過的 json）
  python3 main.py check           檢查設定
"""
import argparse
import sys
import webbrowser

from classroom import rosters, seating, server, sheets
from classroom.config import env, load_env


def show_status(url=None):
    classes = rosters.load_all()
    ok, sheet_msg = sheets.status()
    pend = seating.pending()
    print()
    print("🏫 課堂積分教室")
    if url:
        print(f"   網址          {url}")
    print(f"   班級          " + ("、".join(f"{c['className']}（{len(c['seats'])} 人）" for c in classes) or "還沒有，請把座位表照片放進 images/"))
    for c in classes:
        for msg in rosters.problems(c):
            print(f"   ⚠️  {c['className']}：{msg}")
    print(f"   Google Sheet  " + (f"✅ {sheet_msg}" if ok else f"⚠️  未設定（{sheet_msg}），下課上傳無法使用"))
    print(f"   照片辨識      " + ("✅ 已設定" if env("ANTHROPIC_API_KEY") else "－ 未設定 ANTHROPIC_API_KEY（只有新增班級需要）")
          + (f"，{len(pend)} 張待辨識" if pend else ""))


def start(port, open_browser):
    seating.import_photos()
    try:
        srv = server.create(port)
    except OSError:
        sys.exit(f"❌ port {port} 已被使用（可能已經開過了），請直接打開 http://127.0.0.1:{port}/ 或改用 --port")
    url = f"http://127.0.0.1:{port}/"
    show_status(url)
    print("\n   上課期間請不要關閉這個視窗；按 Ctrl+C 停止。\n", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 已停止")


def main():
    load_env()
    p = argparse.ArgumentParser(description="課堂積分教室")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("start", help="啟動（預設）")
    for parser in (p, s):
        parser.add_argument("--port", type=int, default=int(env("PORT") or 8000))
        parser.add_argument("--no-open", action="store_true", help="不要自動打開瀏覽器")
    sub.add_parser("import", help="辨識新的座位表照片").add_argument("--force", action="store_true")
    sub.add_parser("check", help="檢查設定")
    a = p.parse_args()

    if a.cmd == "import":
        seating.import_photos(a.force)
    elif a.cmd == "check":
        show_status()
    else:
        start(a.port, not a.no_open)


if __name__ == "__main__":
    main()
