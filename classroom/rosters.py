"""讀取 rosters/*.json（每班一個座位表）。"""
import json

from .config import ROSTERS


def load_all():
    classes = []
    for f in sorted(ROSTERS.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        d.setdefault("id", f.stem)
        d.setdefault("className", f.stem)
        classes.append(d)
    return classes


def save(d):
    ROSTERS.mkdir(exist_ok=True)
    (ROSTERS / f"{d['id']}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def problems(d):
    """回傳座位表的問題（座號重複、同一格兩人、超出範圍）。"""
    out = []
    nos = [s["no"] for s in d["seats"]]
    dup = sorted({n for n in nos if nos.count(n) > 1})
    if dup:
        out.append(f"座號重複 {dup}")
    pos = [(s["row"], s["col"]) for s in d["seats"]]
    if len(pos) != len(set(pos)):
        out.append("有兩位學生在同一格")
    out += [f"{s['no']} {s['name']} 的位置超出範圍" for s in d["seats"]
            if not (1 <= s["row"] <= d["rows"] and 1 <= s["col"] <= d["cols"])]
    return out
