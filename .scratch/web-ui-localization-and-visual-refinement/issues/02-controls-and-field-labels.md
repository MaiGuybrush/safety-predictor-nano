# 02 — 全站控制項、按鈕與表單欄位中文化 (Controls, Buttons & Form Field Labels Localization)

**What to build:**
頂部狀態列與控制按鈕中文化與去中括號；全站表單欄位標籤精簡（去除多餘的大寫英文代碼後綴），保留標準技術縮寫（FPS、CPU、RTSP、UMS、ONNX、NCNN、ROI、API Key 等）；來源切換按鈕、清單動作、儲存按鈕與串流編號中文化與去括號。

**Blocked by:** 01 — 樣式系統與章節標題視覺強調升級 (Styles, Section Headers & Accent Badges)

**Status:** ready-for-agent

- [ ] 頂部狀態列標籤：`MODEL` ➔ `模型`、`PATH` ➔ `路徑`、`CORES` ➔ `核心數`。
- [ ] 頂部按鈕：`[ TOGGLE_CONFIG ]` ➔ `切換面板`、`[ SYNC_MODELS ]` ➔ `同步模型`。
- [ ] 模型來源切換：`[ 本地檔案 LOCAL ]` ➔ `本地檔案`、`[ UMS 雲端同步 UMS_SYNC ]` ➔ `UMS 雲端同步`。
- [ ] 串流操作與送出按鈕：`+ 新增串流 ADD_STREAM` ➔ `+ 新增串流`、`[ EXECUTE_UPDATE ]` ➔ `儲存並套用設定`。
- [ ] 串流清單與監視列編號：`[ STREAM #${idx} ]` ➔ `串流 #${idx}`。
- [ ] 表單欄位標籤精簡：去除 `(CONF_THRESHOLD)`、`(MODEL_PATH)`、`(PROJECT)`、`(MODEL)`、`(VERSION)`、`(MODEL_FORMAT)`、`(MODE)`、`(VIDEO_PATH)`、`(FAB PRESETS)`、`(UMS_BASE_URLS)`、`(ENABLED)`、`(SEC)`、`(LABEL)`、`(CAMERA_ID)`、`(OVERRIDE_MODEL)`、`(RESOLVED MODEL)` 等後綴。
- [ ] 保留標準技術縮寫：FPS、CPU、RTSP、UMS、ONNX、NCNN、ROI、API Key 等。
- [ ] 驗證表單 POST payload 欄位名稱與後端相容性不變。
