#!/bin/bash
# 雙擊這個檔案即可：先匯入 images/ 裡的新座位表，再用瀏覽器打開課堂積分教室。
cd "$(dirname "$0")"
python3 import_seating.py
open index.html
