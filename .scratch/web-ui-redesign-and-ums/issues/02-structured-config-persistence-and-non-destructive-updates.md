# 02 — 結構化 Config 持久化與非破壞式寫入 (Structured Config Persistence & Non-destructive Updates)

**What to build:** 
重構後端設定檔儲存處理邏輯，支援接收結構化串流列表（URL, Label, Camera ID, Per-stream Model/UMS）、全域與進階系統參數（Heartbeat, UMS Key, 事件日誌），確保非破壞式寫入 `config.yaml` 並在 UMS 宣告異動時自動觸發背景模型同步。

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] `web_ui.py` 重構表單與 JSON 設定儲存處理邏輯，支援結構化 `streams` 列表（每項包含 `url`、`label`、`camera_id`、`model`、`ums_model`）。
- [ ] 支援儲存進階系統參數（`ums_base_url`、`ums_api_key`、`heartbeat` 物件、`event_absence_tolerance` 等）。
- [ ] 非破壞式合併：確保未出現在表單中的頂層設定與未變更串流之擴充欄位完整保留，不發生設定洗掉。
- [ ] 若偵測到全域或個別串流之 `ums_model` 宣告有變更，在背景自動觸發 `model_sync.sync_all()` 進行非同步下載。
- [ ] 單元測試驗證結構化設定儲存之正確性，確認 `config.yaml` 內容完整且未涉及欄位不受干擾。
