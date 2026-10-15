"""座位表照片 → rosters/<檔名>.json（用 Claude 辨識，需要 .env 的 ANTHROPIC_API_KEY）。"""
import base64
import json
import subprocess
import tempfile
from pathlib import Path

from . import rosters
from .config import IMAGES, ROSTERS, env

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


def pending(force=False):
    """還沒有名單的照片（force=True 則全部）。"""
    photos = sorted(p for p in IMAGES.glob("*") if p.suffix.lower() in EXTS)
    return [p for p in photos if force or not (ROSTERS / f"{p.stem}.json").exists()]


def import_photos(force=False):
    todo = pending(force)
    if not todo:
        print("沒有新的座位表照片（用 --force 可重新辨識全部）")
        return 0
    if not env("ANTHROPIC_API_KEY"):
        print(f"⚠️  有 {len(todo)} 張新照片，但 .env 沒有 ANTHROPIC_API_KEY，先略過辨識")
        return 0
    import anthropic
    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    done = 0
    for p in todo:
        print(f"🔍 辨識 {p.name} …")
        try:
            d = extract(client, p)
        except anthropic.AuthenticationError:
            print("  ❌ ANTHROPIC_API_KEY 無效，請檢查 .env")
            break
        except (anthropic.APIError, RuntimeError, json.JSONDecodeError) as e:
            print(f"  ❌ {p.name} 失敗：{e}")
            continue
        d = {"id": p.stem, "className": p.stem, "rows": d["rows"], "cols": d["cols"],
             "source": f"images/{p.name}", "seats": sorted(d["seats"], key=lambda s: (s["row"], s["col"]))}
        for msg in rosters.problems(d):
            print(f"  ⚠️  {msg}，請手動檢查 rosters/{p.stem}.json")
        rosters.save(d)
        print(f"  ✓ {len(d['seats'])} 位學生 → rosters/{p.stem}.json")
        done += 1
    return done
