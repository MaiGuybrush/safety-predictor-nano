# 04 — ROI 計算去重構與完整 E2E 效能回歸驗證

Type: task
Status: unclaimed
Labels: ready-for-agent, Kind/Feature

## Goal
消除 `_inference_worker` 與 `event_producer.process_detections` 之間的 ROI 多邊形相交重複計算，並執行完整單元測試與效能驗證。

## Details
- `event_producer.py`:
  - `process_detections` 移除多餘的 `_is_inside_zone` 重複過濾，直接依據傳入 detection 物件的 `in_zone` 旗標產生事件。
- 執行整體回歸測試（含 config manager, video handler, inference engine, event producer, web ui）。
- 驗證低功耗模式下 `.jsonl` 事件輸出與推論準確性 100% 維持正常。
