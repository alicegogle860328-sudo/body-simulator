身態模擬器｜GitHub 版本

一、專案結構
app.py
food_database.csv
requirements.txt
images/female_body_progression.gif
images/male_body_progression.gif

二、GitHub 放置方式
1. 建立 GitHub repository。
2. 將 app.py、food_database.csv、requirements.txt 上傳到根目錄。
3. 建立 images 資料夾，把兩個 GIF 放進 images。
4. 如果用 Streamlit Community Cloud，Main file 選 app.py。

三、GIF 檔名請完全保持
female_body_progression.gif
male_body_progression.gif

四、食物資料庫
food_database.csv 共 10,000 筆，包含原本資料與擴充資料。擴充資料是飲食紀錄用途的估算值，實際營養標示仍應以食品包裝或正式營養資料為準。

五、這次依需求保留/調整
- 原本 10 張 PNG 不再使用。
- 保留 Before / After。
- 刪除「📈 歷史熱量圖表」分頁。
- 保留「🍱 三餐紀錄」「💧 水分與日常追蹤」。
- 「🤖 今天這樣吃好嗎」改為全天營養 + 長期體態模擬 + 漸進式 GIF + Before/After。
- 目標體重下方新增目標期限與減重建議。
