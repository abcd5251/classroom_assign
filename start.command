#!/bin/bash
# 雙擊這個檔案即可：先匯入 images/ 裡的新座位表，再啟動本機伺服器並打開課堂積分教室。
# 上課期間不要關閉視窗；下課後關掉視窗或按 Ctrl+C 就會停止。
cd "$(dirname "$0")"
python3 import_seating.py
python3 server.py
