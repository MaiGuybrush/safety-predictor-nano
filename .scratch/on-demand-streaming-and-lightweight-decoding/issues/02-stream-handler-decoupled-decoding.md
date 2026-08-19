# 02 — StreamHandler 輕量封包解碼分離 (Decoupled Grab & Retrieve)

Type: task
Status: unclaimed
Labels: ready-for-agent, Kind/Feature

## Goal
重構 `StreamHandler._capture_frames`，使其在無人觀看時分離 `cap.grab()` 與 `cap.retrieve()`，以極低 CPU 消耗排水防延遲，並精確依據推論間隔（`fps_limit`）進行像素解碼。

## Details
- `StreamHandler`:
  - 核心迴圈持續以 `cap.grab()` 抓取網路封包，防止 TCP 緩衝區積壓。
  - 檢查是否有活躍連線（`web_ui.is_streaming_active()`）：
    - 若有連線：每幀呼叫 `cap.retrieve()`，更新最新影格。
    - 若無連線：僅在符合 `1.0 / fps_limit` 時間間隔時呼叫 `cap.retrieve()` 更新影格供推論執行緒讀取，其餘影格跳過像素解碼。
- 撰寫單元測試模擬解碼計數，驗證無連線時 `retrieve()` 呼叫次數相對於 `grab()` 大幅降低。
