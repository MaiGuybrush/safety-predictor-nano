# Issue 04: Main Loop & Event Producer Integration

Type: task
Status: resolved
Blocked by: 02, 03

## Description
將 `compliance_engine` 與 `state_poller` 整合至主流程與事件管道：
1. **`main.py`**：
   - 啟動 `state_poller` 背景執行緒。
   - 在 YOLO 推論後，將偵測結果送入 `compliance_engine.evaluate(...)` 進行合規評估。
   - 將評估後的 enriched detections 與合規摘要推入 `web_ui.LATEST_DETECTIONS`。
2. **`event_producer.py`**：
   - 接收工安違規事件，產生對應的 `EventStart / EventEnd`。
   - 附帶當前影像截圖快照 (Snapshot) 與 ROI 多邊形資訊，送入 `argus-eventlog` 管道。

## Acceptance Criteria
- 違規事件正確產出並觸發快照存檔。
- 主推論迴圈維持既有幀率，不產生額外效能瓶頸。
- 完成整合測試 `test_compliance_e2e.py`。

## Answer
已完成主迴圈、合規引擎與事件管線整合：
1. **`main.py` 主迴圈串接**：
   - 啟動與動態更新 `GLOBAL_STATE_POLLER` 與 `ComplianceEngine`。
   - 在推論後（RTSP 與 Video 雙路徑）自動結合當前設備狀態、Zone 規則與條件矩陣執行 `compliance_engine.evaluate(...)`。
   - 將富化偵測結果 (`enriched_detections`) 與工安摘要 (`compliance_summary`) 同步寫入 `web_ui.LATEST_DETECTIONS` 與 `web_ui.LATEST_COMPLIANCE_STATUS`。
2. **`event_producer.py` 事件管道擴充**：
   - 新增 `process_compliance_events()`，支援將工安違規轉換為標準 `EventStart / EventFrame / EventEnd`。
   - 自動擷取乾淨無框之即時截圖快照 (Snapshot) 並寫入 `recordings/{camera_id}/snapshots/`。
3. **整合測試驗證**：
   - 新增 `tests/test_compliance_e2e.py`，完整涵蓋人員未戴安全帽違規截圖告警、條件式外部狀態阻隔物缺失與恢復測試；全專案單元測試全數 PASS 通過。
