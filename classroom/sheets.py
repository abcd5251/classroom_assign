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


def write_log(sh, p):
    """把這堂課有加扣分的學生寫進隱藏的紀錄分頁；同一堂課（課堂ID）重複上傳會先刪掉舊的。回傳所有紀錄列。"""
    ws, new = get_ws(sh, LOG_SHEET, LOG_HEAD)
    if new:
        ws.hide()
    sid = str(p["sessionId"])
    rows = [r for r in ws.get_all_values()[1:] if r[3] != sid]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for s in p["students"]:
        if not s.get("plusN") and not s.get("minusN"):
            continue
        rows.append([now, str(p["className"]), str(p["date"]), sid, s["no"], s["name"], s.get("role") or "",
                     STATUS.get(s.get("status"), ""), s["plus"], s["minus"], s["net"],
                     "、".join(s.get("plusR") or []), "、".join(s.get("minusR") or [])])
    ws.batch_clear(["A2:M"])
    if len(rows) + 1 > ws.row_count:
        ws.add_rows(len(rows) + 1 - ws.row_count + 50)
    if rows:
        ws.update(rows, "A2")
    return rows


def rebuild_day(sh, cls, date, roster, log_rows):
    """依紀錄重新計算班級分頁中這一天那一欄的分數（同一天上兩堂課會相加）。"""
    from gspread.utils import rowcol_to_a1
    ws, _ = get_ws(sh, cls, ["座號", "姓名"], frozen_cols=2)
    values = ws.get_all_values()
    header = values[0] if values else ["座號", "姓名"]
    while len(header) > 2 and not header[-1]:
        header.pop()

    # 找到（或新增）日期欄
    if date in header:
        col = header.index(date) + 1
    else:
        col = len(header) + 1
        if col > ws.col_count:
            ws.add_cols(col - ws.col_count + 10)
        ws.update([[date]], rowcol_to_a1(1, col))
    ws.format(f"A1:{rowcol_to_a1(1, col)}", {"textFormat": {"bold": True}, "backgroundColor": HEADER_BG,
                                            "horizontalAlignment": "CENTER"})

    # 確保名單上每位學生都有一列，並依座號排序
    last = len(values) if values else 1
    known = {int(float(r[0])) for r in values[1:] if r and r[0].strip()}
    add = [[s["no"], s["name"]] for s in roster if int(s["no"]) not in known]
    if add:
        if last + len(add) > ws.row_count:
            ws.add_rows(last + len(add) - ws.row_count + 20)
        ws.update(add, f"A{last + 1}")
        last += len(add)
    if last < 2:
        return 0
    ws.sort((1, "asc"), range=f"A2:{rowcol_to_a1(last, ws.col_count)}")

    sums = {}
    for r in log_rows:
        if str(r[1]) != cls or str(r[2]) != date:
            continue
        x = sums.setdefault(int(float(r[4])), {"net": 0, "notes": []})
        x["net"] += int(float(r[10]))
        detail = "、".join(t for t in (r[11], r[12]) if t)
        if detail:
            x["notes"].append(detail)

    def cell(no):
        x = sums.get(no)
        color = BLACK if not x else GREEN if x["net"] > 0 else RED if x["net"] < 0 else BLACK
        c = {"note": "\n".join(x["notes"]) if x else "",
             "userEnteredFormat": {"textFormat": {"bold": True, "foregroundColor": color}, "horizontalAlignment": "CENTER"}}
        if x:
            c["userEnteredValue"] = {"numberValue": x["net"]}
        return c

    nos = [int(float(v)) for v in ws.col_values(1)[1:last] if str(v).strip()]
    sh.batch_update({"requests": [{"updateCells": {
        "start": {"sheetId": ws.id, "rowIndex": 1, "columnIndex": col - 1},
        "rows": [{"values": [cell(n)]} for n in nos],
        "fields": "userEnteredValue,note,userEnteredFormat(textFormat,horizontalAlignment)",
    }}]})
    ws.columns_auto_resize(0, 2)
    return len(sums)


def ping():
    sh = book()
    return {"ok": True, "message": f"連線成功：{sh.title}"}


def sync(p):
    sh = book()
    cls, date = str(p["className"]), str(p["date"])
    log_rows = write_log(sh, p)
    count = rebuild_day(sh, cls, date, p["students"], log_rows)
    return {"ok": True, "sheet": cls, "date": date, "count": count, "url": f"{sh.url}#gid={sh.worksheet(cls).id}"}


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
