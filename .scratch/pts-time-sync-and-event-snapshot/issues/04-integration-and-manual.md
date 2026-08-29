# 04 — 全系統端到端整合驗證與使用手冊同步 (End-to-End System Integration & User Manual Sync)

**What to build:**
整合 PTS 時間戳同步、非同步單次截圖與資料過期清理機制進行全系統端到端情境模擬與回歸測試，確認所有功能在 RTSP 串流與本地影片模式下均能正常運作。同時更新使用者操作手冊（User Manual）與相關技術文件，確保系統構建與運行一致性。

**Blocked by:**
- 01 — PTS 時間戳提取與 ISO 8601 毫秒日誌記錄 (PTS Ingestion & Millisecond Event Logging)
- 02 — 非同步事件單次截圖與 Metadata 關聯 (Async Single Event Snapshot & Metadata Linking)
- 03 — 事件資料留存週期配置與過期自動清理機制 (Event Retention Policy & Periodic Cleaner)

**Status:** ready-for-agent

- [ ] 執行端到端模擬測試，驗證完整推論流程產生之事件日誌包含毫秒級 PTS 時間戳、對應截圖檔案存在且不重複、且檔案符合留存週期要求。
- [ ] 確保所有既有單元測試（包含推論、Web UI、日誌與串流測試）全部通過，無效能與功能回歸。
- [ ] 更新 `docs/user-manual/` 或相關文件，記錄 `event_retention_days` 設定項目與事件截圖目錄結構。
