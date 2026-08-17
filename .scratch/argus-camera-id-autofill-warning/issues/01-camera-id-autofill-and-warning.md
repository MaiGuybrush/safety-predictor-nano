# Issue 01: Web UI Camera ID 自動帶入與不一致警告實作

Type: task
Status: resolved

**Role:** ready-for-agent

**What to build:**
1. 在 `templates/index.html` 中實作 `parseArgusCameraId(url)` 前端解析函式。
2. 在 `templates/index.html` 的 `STREAM_DETAIL_INSPECTOR` 中新增 `detail-camid-warning` 警示容器與 `[ 還原為預設 ID ]` 按鈕。
3. 實作智慧自動填入、清空自動重設、即時不一致警示與一鍵還原機制。
4. 在 `test_web_ui_config_save.py` 新增測試案例，驗證 UI 渲染與設定存取。

**Acceptance criteria:**
- [x] 輸入 Argus Agent URL（包含 `cam-xxx`）時自動帶入 `camera_id`。
- [x] 手動修改 `camera_id` 為不一致的值時，下方即時顯示警告文字與還原按鈕。
- [x] 點擊還原按鈕能立即將 `camera_id` 恢復為 `cam-xxx` 並隱藏警告。
- [x] 清空 `camera_id` 且 URL 仍為 Argus 格式時，自動補回 `cam-xxx`。
- [x] 單元測試通過。

## Answer
已於 `templates/index.html` 實作前端 `parseArgusCameraId`、`validateCameraIdConsistency`、`restoreArgusCameraId` 與 `onDetailCameraIdBlur`，於 `STREAM_DETAIL_INSPECTOR` 設置警示面板與一鍵還原按鈕，並於 `test_web_ui_config_save.py` 完成單元測試驗證（87/87 pass）。
