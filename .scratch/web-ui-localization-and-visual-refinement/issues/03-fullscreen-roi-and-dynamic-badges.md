# 03 — 全螢幕 ROI 警戒區編輯器與即時狀態標籤本地化 (Fullscreen ROI Editor & Live Dynamic Badges)

**What to build:**
全螢幕 ROI 警戒區編輯器內所有操作按鈕與輸入提示全數中文化並去除中括號；即時影像標籤與動態警戒區狀態標籤本地化；畫布繪圖與告警回饋機制維持正常運作，通過所有測試。

**Blocked by:** 02 — 全站控制項、按鈕與表單欄位中文化 (Controls, Buttons & Form Field Labels Localization)

**Status:** ready-for-agent

- [ ] 全螢幕 ROI 編輯器按鈕中文化：`[ 編輯區域 EDIT_ZONE ]` ➔ `編輯警戒區`、`[ 封閉 CLOSE ]` ➔ `封閉多邊形`、`[ 清除 CLEAR ]` ➔ `清除區域`、`[ 儲存 SAVE ]` ➔ `儲存警戒區`、`[ 取消 CANCEL ]` ➔ `取消`、`[ EXIT_FULLSCREEN ✕ ]` ➔ `關閉全螢幕 ✕`。
- [ ] 全螢幕控制項標籤：`ZONE_NAME` placeholder ➔ `警戒區域名稱 (選填)`、`中心點 (Center)` ➔ `物件中心點 (Center)`、`相交重疊 (Intersect)` ➔ `邊界框相交重疊 (Intersect)`、`敏感度:` ➔ `重疊敏感度:`。
- [ ] 即時狀態標籤中文化：`● LIVE_FEED` ➔ `● 即時影像`、`● VIDEO_FILE_FEED` ➔ `● 影片來源`、`[ ROI: INACTIVE ]` / `[ ZONE: INACTIVE ]` ➔ `警戒區：未設定`、`[ ROI: ACTIVE ]` / `[ ZONE: ACTIVE ]` ➔ `警戒區：已啟用`、`[ ZONE: ALARM TRIGGERED ]` ➔ `警戒區：觸發告警`。
- [ ] 畫布 Canvas 繪圖與告警邊框標記文字中文化，保持即時幾何判定正常。
- [ ] 更新 `test_web_ui_fullscreen_alarm.py` 與 `test_web_ui_config_save.py`，完成全套 87+ 單元測試驗證。
