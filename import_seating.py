#!/usr/bin/env python3
"""把 images/ 裡的座位表照片轉成 rosters/<檔名>.json，再打包成網頁讀取的 rosters.js。

用法：
  python3 import_seating.py            # 只處理還沒有名單的新照片，然後重新打包
  python3 import_seating.py --force    # 全部照片重新辨識（會覆蓋手動修改過的 json）
  python3 import_seating.py --rebuild  # 不辨識，只把 rosters/*.json 重新打包

辨識照片需要 Claude API 金鑰：寫在 .env 的 ANTHROPIC_API_KEY=sk-ant-...
"""
import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IMAGES = ROOT / "images"
ROSTERS = ROOT / "rosters"
BUNDLE = ROOT / "rosters.js"
EXTS = {".heic", ".heif", ".jpg", ".jpeg", ".png", ".webp"}

SCHEMA = {
    "type": "object",
    "properties": {
        "rows": {"type": "integer", "description": "座位表的排數（含空位）"},
        "cols": {"type": "integer", "description": "座位表的列數（含空位）"},
        "seats": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "no": {"type": "integer", "description": "座號"},
                    "name": {"type": "string", "description": "學生姓名（繁體中文）"},
                    "role": {"type": "string", "description": "幹部職稱，沒有則為空字串"},
                    "row": {"type": "integer", "description": "第幾排，1 = 紙上最上面一排"},
                    "col": {"type": "integer", "description": "第幾列，1 = 紙上最左邊一列"},
                },
                "required": ["no", "name", "role", "row", "col"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["rows", "cols", "seats"],
    "additionalProperties": False,
}

PROMPT = """這是一張台灣國中教室的座位表照片，講台通常畫在紙的下方。
請把表格中每一個有學生的格子讀出來：座號（數字）、姓名、幹部職稱（若有）。
座標以「紙上看到的位置」為準：row 1 = 表格最上面一排，col 1 = 最左邊一列。
照片可能歪斜，請依表格線判斷每格屬於哪一排哪一列。
整排都是空白的格子不要算進 rows；中間零星的空位保留位置但不要輸出。
姓名請逐字仔細辨識罕見字，不要猜成常見字。"""


def load_env():
    f = ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def to_jpeg(path: Path) -> bytes:
    """用 macOS 內建的 sips 轉成 JPEG（HEIC 也能讀），並縮到 2400px 以內。"""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "img.jpg"
        subprocess.run(["sips", "-s", "format", "jpeg", "-Z", "2400", str(path), "--out", str(out)],
                       check=True, capture_output=True)
        return out.read_bytes()


def extract(client, path: Path) -> dict:
    data = base64.standard_b64encode(to_jpeg(path)).decode()
    response = client.beta.messages.create(
        model="claude-opus-5-5",
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}},
                {"type": "text", "text": PROMPT},
            ],
        }],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("模型拒絕處理這張圖片")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("輸出被截斷，請重試")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def validate(cid: str, d: dict):
    nos = [s["no"] for s in d["seats"]]
    dup = sorted({n for n in nos if nos.count(n) > 1})
    if dup:
        print(f"  ⚠️  {cid}：座號重複 {dup}，請手動檢查 rosters/{cid}.json")
    pos = [(s["row"], s["col"]) for s in d["seats"]]
    if len(pos) != len(set(pos)):
        print(f"  ⚠️  {cid}：有兩位學生在同一格，請手動檢查")
    for s in d["seats"]:
        if not (1 <= s["row"] <= d["rows"] and 1 <= s["col"] <= d["cols"]):
            print(f"  ⚠️  {cid}：{s['no']} {s['name']} 的位置超出範圍")


def rebuild():
    classes = []
    for f in sorted(ROSTERS.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        d.setdefault("id", f.stem)
        d.setdefault("className", f.stem)
        classes.append(d)
    BUNDLE.write_text(
        "// 由 import_seating.py 自動產生，請勿手動修改；要修正名單請改 rosters/*.json 再執行 --rebuild\n"
        "window.CLASSES = " + json.dumps(classes, ensure_ascii=False, indent=1) + ";\n",
        encoding="utf-8",
    )
    print(f"✅ 已打包 {len(classes)} 個班級 → rosters.js：" + "、".join(c["className"] for c in classes))


def main():
    args = set(sys.argv[1:])
    load_env()
    ROSTERS.mkdir(exist_ok=True)
    if "--rebuild" not in args:
        photos = sorted(p for p in IMAGES.glob("*") if p.suffix.lower() in EXTS)
        todo = [p for p in photos if "--force" in args or not (ROSTERS / f"{p.stem}.json").exists()]
        if todo:
            import anthropic
            client = anthropic.Anthropic()
            for p in todo:
                print(f"🔍 辨識 {p.name} …")
                try:
                    d = extract(client, p)
                except (anthropic.AuthenticationError, TypeError):
                    print("  ❌ 沒有可用的 Claude API 金鑰，請在 .env 加上 ANTHROPIC_API_KEY=sk-ant-...")
                    break
                except (anthropic.APIError, RuntimeError, json.JSONDecodeError) as e:
                    print(f"  ❌ {p.name} 失敗：{e}")
                    continue
                d = {"id": p.stem, "className": p.stem, "rows": d["rows"], "cols": d["cols"],
                     "source": f"images/{p.name}", "seats": sorted(d["seats"], key=lambda s: (s["row"], s["col"]))}
                validate(p.stem, d)
                (ROSTERS / f"{p.stem}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"  ✓ {len(d['seats'])} 位學生 → rosters/{p.stem}.json")
        else:
            print("沒有新的座位表照片（用 --force 可重新辨識全部）")
    rebuild()


if __name__ == "__main__":
    main()
