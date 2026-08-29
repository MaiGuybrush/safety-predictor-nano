# 01 — PTS 時間戳提取與 ISO 8601 毫秒日誌記錄 (PTS Ingestion & Millisecond Event Logging)

**What to build:**
在 AI 影像推論過程中，直接擷取影像串流訊框的原生 Presentation Timestamp (PTS) 秒數。當偵測到目標並產生事件記錄（EventStart, EventFrame, EventEnd）時，日誌中的 `timestamp` 欄位全面改用由 PTS 轉換而成之 ISO 8601 UTC 毫秒字串（如 `2026-08-29T07:36:04.404Z`）。若串流無有效 PTS 資訊（或數值 <= 0），系統自動 Fallback 至系統 Epoch 時間，確保時間戳不中斷且精確對齊 NVR 錄影時序。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] 串流取訊框模組在擷取每一幀時同步提取 PTS 浮點秒數，若 PTS <= 0 或無效則 fallback 至系統時間。
- [ ] 推論主迴圈與事件生成函式接收訊框對應之 PTS 浮點秒數。
- [ ] 事件日誌中的 `EventStart`、`EventFrame`、`EventEnd` 之 `timestamp` 欄位格式改為精確至毫秒之 ISO 8601 UTC 字串（`YYYY-MM-DDTHH:MM:SS.mmmZ`）。
- [ ] 撰寫單元測試驗證傳入 PTS 時產生的時間戳精確度，以及傳入無效 PTS 時的 fallback 機制。
