# 🏫 課堂積分教室

上課用的點名＋加扣分小遊戲。拍一張班級座位表就會變成可以點的教室，下課一鍵寫進 Google Sheet。

## 啟動

第一次（建立虛擬環境並安裝套件）：

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

之後每次：

```bash
source venv/bin/activate
python3 main.py
```

啟動後終端機會顯示狀態，瀏覽器會自動打開 http://127.0.0.1:8000 ：

```
🏫 課堂積分教室
   網址          http://127.0.0.1:8000/
   班級          906（30 人）、913（30 人）
   Google Sheet  ✅ xxx@xxx.iam.gserviceaccount.com
   照片辨識      ✅ 已設定

   上課期間請不要關閉這個視窗；按 Ctrl+C 停止。
```

**上課期間不要關掉這個終端機視窗**，下課後按 `Ctrl + C` 停止。

| 指令 | 作用 |
|---|---|
| `python3 main.py` | 辨識新照片 → 啟動網頁 |
| `python3 main.py --port 8080` | 換 port 啟動 |
| `python3 main.py --no-open` | 啟動但不自動開瀏覽器 |
| `python3 main.py import` | 只辨識 `images/` 裡新增或換過的照片 |
| `python3 main.py import --force` | 全部照片重新辨識（會覆蓋手動改過的 json） |
| `python3 main.py check` | 檢查設定（班級、Google Sheet、API 金鑰） |

## 設定 `.env`

複製 `.env.example` 成 `.env`：

```
ANTHROPIC_API_KEY=sk-ant-...                       # 照片辨識用，只有新增班級需要
GOOGLE_SHEET_ID=https://docs.google.com/spreadsheets/d/xxxxxxxx/edit
GOOGLE_SERVICE_ACCOUNT_FILE=service-account.json
```

## 新增一個班級

1. 把座位表照片放進 `images/`，**檔名 = 班級名稱**（例如 `907.HEIC`、`801.jpg`）
2. 執行 `python3 main.py`（或 `python3 main.py import`）
3. 網頁左上角選單就會出現新班級

程式執行期間也可以直接把照片放進 `images/`，或替換某班的照片（檔名不變），幾秒內就會自動辨識，網頁也會自動更新。

照片只會辨識一次（已經有 `rosters/<班級>.json` 的不會重跑），每張照片會產生一點 API 費用。

**辨識錯字**：直接改 `rosters/<班級>.json`，重新整理網頁就生效。臨時修改也可以在網頁上按「✏️ 編輯」（只存在這台電腦的瀏覽器）。

## 上課操作

| 動作 | 方法 |
|---|---|
| 點名 | 「✅ 全部到齊」→ 再把沒來的同學點選後按「缺席」（或按 `X`） |
| 加分／扣分 | 點學生 → 大按鈕或理由標籤；`1` `2` `3` 切換 1/2/5 分；鍵盤 `+` `-` |
| 抽人回答 | 「🎲 抽籤」 |
| 按錯了 | 「↶ 復原」或 `Ctrl/⌘ + Z` |
| 下課 | 「☁️ 下課上傳」寫進 Google Sheet（也可以「⬇ CSV」匯出）→ 上傳後可選擇開始新課堂 |

分數會自動存在**這台電腦的瀏覽器**裡（重新整理不會不見），但換電腦或清除瀏覽器資料就會消失，記得下課上傳。

CSV 欄位：班級、座號、姓名、職稱、座位、出席狀態、加分次數／總計、扣分次數／總計、淨分、加分明細、扣分明細（Excel 直接開不會亂碼）。

## ☁️ 下課寫進 Google Sheet

按「☁️ 下課上傳」，就會把這堂課每位同學的淨分（加分 − 扣分）寫進試算表：

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

7. 執行 `python3 main.py check` 確認，啟動後在網頁按「⚙️」測試連線

## 專案結構

```
classroom_assign/
├── main.py              # 唯一入口：python3 main.py
├── classroom/           # 後端（Python）
│   ├── config.py        # 路徑、讀取 .env
│   ├── rosters.py       # 讀寫 rosters/*.json
│   ├── seating.py       # 座位表照片 → json（Claude 辨識）
│   ├── sheets.py        # 寫入 Google Sheet
│   └── server.py        # 本機網頁伺服器與 API
├── web/                 # 前端（瀏覽器看到的頁面）
│   ├── index.html
│   ├── style.css
│   └── app.js           # 點名、加扣分、抽籤、匯出、上傳
├── images/              # ← 放座位表照片          ※ 不進 git
├── rosters/             # 每班一個 json（可手動修改）※ 不進 git
├── .env                 # 金鑰與試算表網址         ※ 不進 git
└── service-account.json # Google 服務帳戶金鑰      ※ 不進 git
```

伺服器只接受這台電腦（127.0.0.1）連線，而且只提供 `web/` 裡的檔案，`.env`、金鑰和名單 json 不會被網頁讀到。

### 座位座標規則

`rosters/*.json` 裡每位學生：

```json
{ "no": 21, "name": "陳大文", "role": "班長", "row": 4, "col": 5 }
```

`row` / `col` 以**紙本座位表上看到的位置**為準：`row 1` = 紙上最上面一排（離講台最遠），`col 1` = 最左邊。頁面預設的「座位表視角」跟紙本一模一樣（講台在下方）。

### 想改加扣分理由

編輯 `web/app.js` 最上面的 `PLUS_REASONS` / `MINUS_REASONS`，重新整理網頁即可。
