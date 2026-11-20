"""用 Google 服務帳戶把每堂課的淨分寫進試算表：每班一個分頁，每次上課一欄日期。"""
import json
from datetime import datetime

from .config import ROOT, env

LOG_SHEET = "_上課紀錄"
LOG_HEAD = ["上傳時間", "班級", "日期", "課堂ID", "座號", "姓名", "職稱", "出席", "加分", "扣分", "淨分", "加分明細", "扣分明細"]
STATUS = {"present": "已到", "absent": "缺席", "none": "未點名"}
GREEN, RED, BLACK = {"red": .12, "green": .56, "blue": .24}, {"red": .85, "green": .19, "blue": .15}, {"red": 0, "green": 0, "blue": 0}
HEADER_BG = {"red": 1, "green": .945, "blue": .76}


class UserError(Exception):
    """要直接顯示給老師看的錯誤訊息。"""


_book = None


def book():
    """打開 .env 指定的試算表（第一次之後會重複使用）。"""
    global _book
    if _book:
        return _book
    import gspread
    key = ROOT / (env("GOOGLE_SERVICE_ACCOUNT_FILE") or "service-account.json")
    sheet = env("GOOGLE_SHEET_ID")
    if not key.exists():
        raise UserError(f"找不到服務帳戶金鑰 {key.name}，請照 README 下載後放進專案資料夾")
    if not sheet:
        raise UserError("請在 .env 填 GOOGLE_SHEET_ID（試算表網址）")
    email = json.loads(key.read_text()).get("client_email", "服務帳戶")
    gc = gspread.service_account(filename=str(key))
    try:
        _book = gc.open_by_url(sheet) if sheet.startswith("http") else gc.open_by_key(sheet)
    except (gspread.exceptions.SpreadsheetNotFound, gspread.exceptions.APIError, PermissionError) as e:
        raise UserError(f"打不開試算表。請在試算表按「共用」，加入 {email}，權限選「編輯者」。（{e}）")
    return _book


def get_ws(sh, title, head, frozen_cols=0):
    import gspread
    try:
        return sh.worksheet(title), False
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title, rows=100, cols=max(len(head), 26))
        ws.update([head], "A1")
        ws.format("1:1", {"textFormat": {"bold": True}})
        ws.freeze(rows=1, cols=frozen_cols)
        return ws, True


# ── 安全原則 ──────────────────────────────────────────────────────────────
# 1. 紀錄分頁只「往下新增」，從不清除或改寫舊紀錄。同一堂課重複上傳時，以最後一次上傳為準。
# 2. 班級分頁不排序、不刪列、不改別人的格式；新日期欄只開在整欄都空白的地方。
# 3. 分數格只有在「目前內容 = 這個程式上次寫的內容」（或原本是空的）時才會更新；
#    老師手動改過、或不是這個程式寫的格子一律跳過，並回報給老師。
# ────────────────────────────────────────────────────────────────────────


def _no(v):
    try:
        return int(float(str(v).strip()))
    except ValueError:
        return None


def _col(r, i):
    return r[i] if i < len(r) else ""


def _latest(log_rows):
    """每堂課（課堂ID）只取最後一次上傳的那批紀錄。"""
    last = {}
    for r in log_rows:
        last[_col(r, 3)] = max(last.get(_col(r, 3), ""), _col(r, 0))
    return [r for r in log_rows if _col(r, 0) == last[_col(r, 3)]]


def day_sums(log_rows, cls, date):
    """某班某天每位同學的淨分與明細（同一天上兩堂課會相加）。"""
    sums = {}
    for r in _latest(log_rows):
        n = _no(_col(r, 4))
        if _col(r, 1) != cls or _col(r, 2) != date or n is None:
            continue
        x = sums.setdefault(n, {"net": 0, "notes": []})
        x["net"] += _no(_col(r, 10)) or 0
        detail = "、".join(t for t in (_col(r, 11), _col(r, 12)) if t)
        if detail:
            x["notes"].append(detail)
    return {n: {"net": x["net"], "note": "\n".join(x["notes"])} for n, x in sums.items()}


def _same(value, note, x):
    """格子的內容是不是剛好等於 x（None 代表空白格）。"""
    if x is None:
        return not str(value).strip() and not str(note).strip()
    return _no(value) == x["net"] and str(note).strip() == x["note"].strip()


def write_day(sh, ws, date, roster, before, after, create):
    """更新班級分頁中 date 那欄。回傳因為內容被手動改過而跳過的同學。"""
    from gspread.utils import rowcol_to_a1
    values = ws.get_all_values() or [["座號", "姓名"]]
    width = max(len(r) for r in values)
    header = values[0] + [""] * (width - len(values[0]))

    if date in header:
        col = header.index(date) + 1
    elif not create:
        return []   # 舊日期欄已經不在了，就不動
    else:
        # 新日期欄：放在最後一個有表頭的欄之後、第一個「整欄都空白」的欄
        used = max(i for i, h in enumerate(header) if h.strip()) + 1 if any(h.strip() for h in header) else 0
        col = next((j + 1 for j in range(used, width) if not any(_col(r, j).strip() for r in values)), width + 1)
        if col > ws.col_count:
            ws.add_cols(col - ws.col_count + 10)
        ws.update([[date]], rowcol_to_a1(1, col))
        ws.format(rowcol_to_a1(1, col), {"textFormat": {"bold": True}, "backgroundColor": HEADER_BG,
                                          "horizontalAlignment": "CENTER"})

    # 名單上還沒有的同學：加在表格最下面（不排序，不移動既有的列）
    rows = {}
    for i, r in enumerate(values[1:], start=2):
        n = _no(_col(r, 0))
        if n is not None:
            rows.setdefault(n, i)
    add = [[s["no"], s["name"]] for s in roster if _no(s["no"]) not in rows]
    if add:
        first = len(values) + 1
        if first + len(add) - 1 > ws.row_count:
            ws.add_rows(first + len(add) - 1 - ws.row_count + 20)
        ws.update(add, f"A{first}")
        for k, (n, _) in enumerate(add):
            rows[_no(n)] = first + k

    notes = ws.get_notes()
    reqs, skipped = [], []
    for n in sorted(set(before) | set(after)):
        if n not in rows:
            continue
        had, want = before.get(n), after.get(n)
        i = rows[n]
        value = _col(values[i - 1], col - 1) if i <= len(values) else ""
        note = _col(notes[i - 1], col - 1) if i <= len(notes) else ""
        if _same(value, note, want) or had == want:
            continue                       # 已經是對的，或這次上傳沒改到他
        if not _same(value, note, had):
            skipped.append(n)              # 有人手動改過 → 不覆蓋
            continue
        color = BLACK if not want else GREEN if want["net"] > 0 else RED if want["net"] < 0 else BLACK
        c = {"note": want["note"] if want else "",
             "userEnteredFormat": {"textFormat": {"bold": True, "foregroundColor": color}, "horizontalAlignment": "CENTER"}}
        if want:
            c["userEnteredValue"] = {"numberValue": want["net"]}
        reqs.append({"updateCells": {
            "start": {"sheetId": ws.id, "rowIndex": i - 1, "columnIndex": col - 1},
            "rows": [{"values": [c]}],
            "fields": "userEnteredValue,note,userEnteredFormat(textFormat,horizontalAlignment)",
        }})
    if reqs:
        sh.batch_update({"requests": reqs})
    return skipped


def ping():
    sh = book()
    return {"ok": True, "message": f"連線成功：{sh.title}"}


def sync(p):
    sh = book()
    cls, date, sid = str(p["className"]), str(p["date"]), str(p["sessionId"])
    log_ws, new = get_ws(sh, LOG_SHEET, LOG_HEAD)
    if new:
        log_ws.hide()
    log_rows = log_ws.get_all_values()[1:]

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    batch = [[now, cls, date, sid, s["no"], s["name"], s.get("role") or "",
              STATUS.get(s.get("status"), ""), s["plus"], s["minus"], s["net"],
              "、".join(s.get("plusR") or []), "、".join(s.get("minusR") or [])]
             for s in p["students"] if s.get("plusN") or s.get("minusN")]
    if not batch:   # 標記「這堂課最新一次上傳沒有任何加扣分」
        batch = [[now, cls, date, sid, "", "（這次上傳沒有加扣分）"] + [""] * 7]
    after = log_rows + batch

    # 這堂課之前若用別的日期上傳過，那一欄也要一起更新（只改這個程式寫過、沒被手動改過的格子）
    old_dates = {_col(r, 2) for r in _latest(log_rows) if _col(r, 3) == sid and _col(r, 1) == cls} - {date}
    ws, created = get_ws(sh, cls, ["座號", "姓名"], frozen_cols=2)
    roster = {_no(s["no"]): s["name"] for s in p["students"]}
    skipped = []
    for d in [date, *sorted(old_dates)]:
        skipped += [f"{d} {n:02d} {roster.get(n, '')}"
                    for n in write_day(sh, ws, d, p["students"] if d == date else [],
                                       day_sums(log_rows, cls, d), day_sums(after, cls, d), create=(d == date))]
    if created:
        ws.columns_auto_resize(0, 2)

    # 分數格寫完才記錄（中途失敗的話，重新上傳一次即可，不會重複加分）
    log_ws.append_rows(batch, value_input_option="RAW", insert_data_option="INSERT_ROWS", table_range="A1")
    count = len(day_sums(after, cls, date))
    return {"ok": True, "sheet": cls, "date": date, "count": count, "skipped": skipped,
            "url": f"{sh.url}#gid={ws.id}"}


def status():
    """啟動時顯示用：只檢查設定是否齊全，不實際連線。"""
    key = ROOT / (env("GOOGLE_SERVICE_ACCOUNT_FILE") or "service-account.json")
    if not env("GOOGLE_SHEET_ID"):
        return False, ".env 沒有 GOOGLE_SHEET_ID"
    if not key.exists():
        return False, f"找不到 {key.name}"
    try:
        import gspread  # noqa: F401
    except ImportError:
        return False, "缺少套件，請先 source venv/bin/activate 再 pip install -r requirements.txt"
    return True, json.loads(key.read_text()).get("client_email", key.name)
