# 06 — Web UI 手動同步端點 + 最近同步狀態

**What to build:** 使用者不用重開機，就能在 Web UI 觸發一次模型同步，並看得到最近一次同步的結果（成功/失敗、訊息），滿足「UMS 平台上傳新版本後想立即套用」的使用情境。

**Blocked by:** 04（需要 `model_sync.sync_all()`；不依賴 05，可與 05 平行進行）

- [x] `web_ui.py` 新增 `POST /sync_models` 端點（命名比照現有 `/model_info`、`/detections_feed` 風格），呼叫 `model_sync.sync_all()`，回傳 JSON 格式的同步結果（成功/失敗清單）
- [x] 提供讀取「最近一次同步結果」的方式（可併入 `/model_info` 既有回傳，或獨立 GET 端點，二選一即可）
- [x] `templates/index.html` 加一個觸發同步的按鈕，呼叫 `/sync_models`（僅需最小可用互動，不展開視覺設計）
- [x] 單元測試比照 `test_sse_detections.py` 的 `web_ui.app.test_client()` 模式：mock 掉 `model_sync.sync_all()`，驗證 `/sync_models` 回傳的 JSON 結構與狀態碼、驗證失敗案例也能正確回傳（不拋 500）
