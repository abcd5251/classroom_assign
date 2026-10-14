# 🏫 課堂積分教室

上課用的點名＋加扣分小遊戲。拍一張班級座位表，就會自動變成可以點的教室，下課匯出 CSV。

## 快速開始

**雙擊 `start.command`** — 會先匯入新的座位表照片，再用瀏覽器打開頁面。

或直接用瀏覽器打開 `index.html`（不需要架伺服器、不需要網路）。

## 新增一個班級

1. 把座位表照片放進 `images/`，**檔名 = 班級名稱**（例如 `907.HEIC`、`801.jpg`）
2. 雙擊 `start.command`（或在終端機執行 `python3 import_seating.py`）
3. 頁面左上角的選單就會出現新班級

第一次使用自動辨識前，需要：

```bash
pip3 install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...     # 建議寫進 ~/.zshrc
```

照片辨識只會跑一次（已經有 `rosters/<班級>.json` 的不會重跑），每張照片會產生一點 API 費用。

### 辨識錯字怎麼辦

- **單一座位**：頁面上按「✏️ 編輯」→ 點該座位修改（只存在這台電腦的瀏覽器）
- **永久修正**：直接改 `rosters/<班級>.json`，再執行 `python3 import_seating.py --rebuild`

| 指令 | 作用 |
|---|---|
| `python3 import_seating.py` | 辨識新照片 + 重新打包 |
| `python3 import_seating.py --rebuild` | 只把 `rosters/*.json` 重新打包（改完 json 後用） |
| `python3 import_seating.py --force` | 所有照片重新辨識（會覆蓋手動改過的 json） |

## 上課操作

| 動作 | 方法 |
|---|---|
| 點名 | 「✅ 全部到齊」→ 再把沒來的同學點選後按「缺席」（或按 `X`） |
| 加分／扣分 | 點學生 → 大按鈕或理由標籤；`1` `2` `3` 切換 1/2/5 分；鍵盤 `+` `-` |
| 抽人回答 | 「🎲 抽籤」 |
| 按錯了 | 「↶ 復原」或 `Ctrl/⌘ + Z` |
| 下課 | 「⬇ 匯出 CSV」→ 「🧹 新課堂」清空分數 |

分數會自動存在**這台電腦的瀏覽器**裡（重新整理不會不見），但換電腦或清除瀏覽器資料就會消失，記得匯出 CSV。

CSV 欄位：班級、座號、姓名、職稱、座位、出席狀態、加分次數／總計、扣分次數／總計、淨分、加分明細、扣分明細（Excel 直接開不會亂碼）。

## ☁️ 下課自動寫進 Google Sheet

按右上角「☁️ 下課上傳」，就會把這堂課每位同學的淨分（加分 − 扣分）寫進試算表：

| 座號 | 姓名 | 10/13 | 10/20 | … |
|---|---|---|---|---|
| 1 | 王小明 | 3 | | |
| 4 | 林小美 | 6 | -1 | |

- 每個班級一個分頁（`913`、`906`…），第一次上傳時自動建立
- 每次上課新增一欄日期；滑鼠移到格子上可看到加扣分明細
- 同一堂課重複上傳只會**更新**，不會重複加分；同一天上兩堂會相加
- 隱藏分頁 `_上課紀錄` 保存每次上傳的原始資料

### 第一次設定（約 3 分鐘）

> Google Cloud 的「API 金鑰」不能寫入試算表，所以改用 Apps Script，不需要金鑰。

1. 打開要存成績的 Google 試算表 → 選單「擴充功能」→「Apps Script」
2. 把 `google-apps-script/Code.gs` 整個貼上，把第一行的 `TOKEN` 改成自己的密碼 → 💾 存檔
3. 右上角「部署」→「新增部署作業」→ 齒輪選「**網頁應用程式**」
   - 執行身分：**我**　／　誰可以存取：**所有人** → 部署 → 依指示授權
4. 複製「網頁應用程式網址」（`https://script.google.com/macros/s/…/exec`）
5. 在課堂積分教室按「⚙️」，貼上網址和密碼 → 「🔌 測試連線」→ 儲存

之後如果修改了 `Code.gs`，要到「部署」→「管理部署作業」→ ✏️ → 版本選「新版本」再部署，網址不變。

## 專案結構

```
classroom_assign/
├── start.command        # 雙擊啟動
├── index.html           # 頁面骨架
├── assets/
│   ├── style.css        # 外觀
│   └── app.js           # 互動邏輯（點名、加扣分、抽籤、匯出）
├── images/              # ← 放座位表照片
├── rosters/             # 每班一個 json（辨識結果，可手動修改）※ 不進 git
├── rosters.js           # 自動產生，頁面讀的就是它；請勿手改 ※ 不進 git
├── import_seating.py    # 照片 → json → rosters.js
├── google-apps-script/
│   └── Code.gs          # 貼到 Google 試算表的 Apps Script（寫入成績）
└── requirements.txt
```

> `images/`、`rosters/`、`rosters.js`、`.env` 含學生個資或金鑰，已列在 `.gitignore`，只存在本機。換電腦時請另外複製，或重新放照片執行 `import_seating.py`。

### 座位座標規則

`rosters/*.json` 裡每位學生：

```json
{ "no": 21, "name": "陳大文", "role": "班長", "row": 4, "col": 5 }
```

`row` / `col` 以**紙本座位表上看到的位置**為準：`row 1` = 紙上最上面一排（離講台最遠），`col 1` = 最左邊。頁面預設的「座位表視角」跟紙本一模一樣（講台在下方）。

### 想改加扣分理由

編輯 `assets/app.js` 最上面的 `PLUS_REASONS` / `MINUS_REASONS`。
