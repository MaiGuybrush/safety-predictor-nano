# On-Demand Streaming, Lightweight Decoding & Frontend Idle Disconnect Map

## Notes & Decisions
- **隨選串流與連線計數 (Active Stream Tracking)**：在 `web_ui.py` 中以執行緒安全計數器追蹤活躍的 `/video_feed` 連線。
- **主迴圈延遲編碼 (Lazy JPEG Encoding)**：當無連線時，`main.py` 主迴圈完全跳過 `compose_grid` 與 `cv2.imencode`，消除 ~100Hz 的 JPEG 壓縮浪費。
- **輕量封包解碼分離 (Decoupled Grab/Retrieve)**：`StreamHandler` 持續以 `cap.grab()` 排水防延遲；無人觀看時僅在推論抽樣週期呼叫 `cap.retrieve()`，有人觀看時恢復全速解碼。
- **前端智慧閒置與分頁斷線**：透過 Page Visibility API（分頁切換/縮小）與 5 分鐘 User Idle Timer 於無人使用時清空 `img.src` 關閉連線並顯示省電休眠遮罩；操作時無縫喚醒。
- **消除 ROI 重複計算**：推論後統一單次計算多邊形裁剪與 `in_zone`，事件管線直接沿用。

## Tickets
- [01-backend-client-tracker-and-lazy-encoding.md](issues/01-backend-client-tracker-and-lazy-encoding.md) (Status: resolved)
- [02-stream-handler-decoupled-decoding.md](issues/02-stream-handler-decoupled-decoding.md) (Status: resolved)
- [03-frontend-smart-idle-and-visibility-disconnect.md](issues/03-frontend-smart-idle-and-visibility-disconnect.md) (Status: resolved)
- [04-roi-deduplication-and-e2e-verification.md](issues/04-roi-deduplication-and-e2e-verification.md) (Status: resolved)
