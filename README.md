# 🏫 課堂積分教室

上課用的點名＋加扣分小遊戲。拍一張班級座位表，就會自動變成可以點的教室，下課匯出 CSV。

## 快速開始

```bash
pip3 install -r requirements.txt   # 第一次
./start.command                    # 或在 Finder 雙擊
```

會先匯入新的座位表照片，再啟動本機伺服器並打開 http://127.0.0.1:8000 。**上課期間不要關掉那個終端機視窗**，下課後關掉視窗或按 `Ctrl + C` 就停止了。

只想看畫面、不需要上傳 Google Sheet 的話，也可以直接打開 `index.html`。（兩種開法的分數各存一份，請固定用同一種）

## 新增一個班級

1. 把座位表照片放進 `images/`，**檔名 = 班級名稱**（例如 `907.HEIC`、`801.jpg`）
2. 雙擊 `start.command`（或在終端機執行 `python3 import_seating.py`）
3. 頁面左上角的選單就會出現新班級

第一次使用自動辨識前，在 `.env` 加上 Claude API 金鑰（格式見 `.env.example`）：

```
ANTHROPIC_API_KEY=sk-ant-...
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

### 第一次設定：服務帳戶（約 5 分鐘）

服務帳戶就像一個「機器人帳號」，把它加進試算表的共用名單，程式就能寫入。

1. 到 [Google Cloud Console](https://console.cloud.google.com/) → 選你的專案 →「API 和服務」→「程式庫」→ 啟用 **Google Sheets API**
2. 「IAM 與管理」→「服務帳戶」→「建立服務帳戶」（名稱隨意，角色可以略過）
3. 點進剛建立的服務帳戶 →「金鑰」→「新增金鑰」→「JSON」→ 會下載一個 `.json` 檔
4. 把它改名成 `service-account.json`，放進專案資料夾（已在 `.gitignore`，不會被 commit）
5. 打開要存成績的 Google 試算表 →「共用」→ 貼上服務帳戶的 email（`xxx@xxx.iam.gserviceaccount.com`，在 json 裡的 `client_email`）→ 權限選「**編輯者**」
6. 在 `.env` 加上試算表網址：

   ```
   GOOGLE_SHEET_ID=https://docs.google.com/spreadsheets/d/xxxxxxxx/edit
   GOOGLE_SERVICE_ACCOUNT_FILE=service-account.json
   ```

7. 用 `./start.command` 打開頁面，按「⚙️」測試連線

> 原本的 Google Sheets「API 金鑰」（`GOOGLE_SHEETS_API`）只能讀不能寫，用不到，建議到 Cloud Console 刪掉。
>
> 不想跑伺服器的話，也可以改用 Apps Script（`google-apps-script/Code.gs`），直接打開 `index.html` 後按「⚙️」設定。

## 專案結構

```
classroom_assign/
├── start.command        # 雙擊啟動（匯入照片 + 開伺服器）
├── server.py            # 本機伺服器：提供網頁 + 寫入 Google Sheet
├── index.html           # 頁面骨架
├── assets/
│   ├── style.css        # 外觀
│   └── app.js           # 互動邏輯（點名、加扣分、抽籤、匯出）
├── images/              # ← 放座位表照片
├── rosters/             # 每班一個 json（辨識結果，可手動修改）※ 不進 git
├── rosters.js           # 自動產生，頁面讀的就是它；請勿手改 ※ 不進 git
├── import_seating.py    # 照片 → json → rosters.js
├── .env                 # 金鑰與試算表網址（範本：.env.example）※ 不進 git
├── service-account.json # Google 服務帳戶金鑰 ※ 不進 git
└── requirements.txt
```

> `images/`、`rosters/`、`rosters.js`、`.env`、`service-account.json` 含學生個資或金鑰，已列在 `.gitignore`，只存在本機。換電腦時請另外複製，或重新放照片執行 `import_seating.py`。

### 座位座標規則

`rosters/*.json` 裡每位學生：

```json
{ "no": 21, "name": "陳大文", "role": "班長", "row": 4, "col": 5 }
```

`row` / `col` 以**紙本座位表上看到的位置**為準：`row 1` = 紙上最上面一排（離講台最遠），`col 1` = 最左邊。頁面預設的「座位表視角」跟紙本一模一樣（講台在下方）。

### 想改加扣分理由

編輯 `assets/app.js` 最上面的 `PLUS_REASONS` / `MINUS_REASONS`。
