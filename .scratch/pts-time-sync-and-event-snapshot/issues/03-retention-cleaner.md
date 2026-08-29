# 03 — 事件資料留存週期配置與過期自動清理機制 (Event Retention Policy & Periodic Cleaner)

**What to build:**
系統支援自訂事件資料留存天數（`event_retention_days`，預設 30 天），並於 Web UI「日誌與系統設定」介面提供輸入欄位與保存功能。系統啟動時與每 24 小時定期啟動獨立背景 Daemon 執行緒，掃描 `recordings/{camera_id}/` 下的 `events/` 與 `snapshots/` 目錄，自動比對檔案修改時間（mtime）並清除超過保存期限的舊檔案，避免邊緣儲存裝置空間耗盡。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] `config.yaml`、`config_manager.py` 與 Web UI 支援讀取、驗證與儲存 `event_retention_days`（預設 30 天，允許值 >= 1）。
- [ ] 實作過期清理函式，遍歷 `recordings/{camera_id}/` 底下的事件日誌（`.jsonl`）與截圖（`.jpg`），刪除修改時間超過 `event_retention_days * 86400` 秒之檔案。
- [ ] 在主程式啟動獨立清理 Daemon 執行緒，於啟動時執行一次並每 24 小時週期性執行。
- [ ] 撰寫單元測試驗證過期檔案刪除、未過期檔案保留以及 Web UI 設定持久化。
