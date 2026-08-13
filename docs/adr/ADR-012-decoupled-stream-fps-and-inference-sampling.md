# ADR-012：串流畫面 FPS 與推論抽樣率解耦及過時方框 UI 提示

| 欄位 | 內容 |
|------|------|
| **狀態** | 已接受 (Accepted) |
| **日期** | 2026-08-13 |
| **決策者** | 開發團隊 |
| **相關 ADR** | [ADR-008](ADR-008-round-robin-inference-scheduling.md), [ADR-009](ADR-009-sse-over-websocket-detection-channel.md), [ADR-010](ADR-010-client-side-canvas-detection-overlay.md) |
| **相關 PRD** | [fps_decoupling_and_dynamic_canvas_overlay_prd.md](../prd/fps_decoupling_and_dynamic_canvas_overlay_prd.md) |

---

## 情境與問題

舊版實作中，設定檔參數 `fps_limit`（如 2 FPS）同時控制了 RTSP 串流接收迴圈 (`StreamHandler`) 與 YOLO 推論迴圈。在 `StreamHandler` 中使用 `time.sleep(1.0 / fps_limit)` (0.5 秒) 會導致：
1. **慢動作與時間累積延遲**：RTSP 攝影機持續以 30 FPS 發送影格，OpenCV 解碼緩衝區（Buffer）不斷積壓舊影格。`cap.read()` 每次僅按順序讀取下一影格，導致前端畫面呈現 1/15 倍速慢動作與嚴重的即時性延遲。
2. **主畫面與單路焦點畫框未解耦**：無法維持「主畫面乾淨純淨」與「點選特定單路時方能繪製方框」之使用者體驗。
3. **缺乏抽檢狀態提示**：當推論頻率較低（如 2 FPS）而影片為 30 FPS 時，使用者無法辨識方框為「當前即時推論」還是「過期抽檢結果」。

---

## 決策

採用**「解耦解碼與推論頻率 + 時間點抽檢 + 前端動態 Canvas 畫框與過時提示」**架構：

1. **RTSP 解碼流維持 30 FPS 原速**：`StreamHandler` 取消 `time.sleep(1.0 / fps_limit)`，維持極速清空 OpenCV Buffer，保持前端 30 FPS 零延遲順暢度。
2. **獨立推檢排程器 (Inference Sampler)**：`_inference_worker` 依據每路串流獨立的 `last_infer_time` 與 `fps_limit` 進行時間點抽檢推論。
3. **全站純淨畫質與單路 Canvas 繪圖**：伺服器端（Python OpenCV）完全不繪製任何方框。主畫面顯示純淨影像，僅單路視窗觸發前端 HTML5 Canvas 訂閱 SSE (`/detections_feed`) 畫框。
4. **過時方框 UI 提示訊號**：前端 Canvas 檢查 `detObj.ts`，若偵測結果距今大於 0.15 秒，繪製虛線框 (`setLineDash([4, 4])`) 並附加 `[SAMPLED]` 標籤。

---

## 理由

1. **徹底解決慢動作與延遲**：讓 `cap.read()` 保持全速解碼，解決了 OpenCV RTSP 緩衝區積壓導致慢動作的根因。
2. **極致省電與算力控管**：YOLO 推論精確遵循 `fps_limit` 抽檢，維持嵌入式設備（Raspberry Pi 5）低 CPU 佔用率。
3. **優異的使用者視覺體驗**：主畫面維持清晰無遮擋；單路視窗下透過虛線與 `[SAMPLED]` 標籤，讓使用者對「畫面即時性」與「推論抽檢性」有清晰明確的視覺認知。

---

## 取捨與風險

- **低推論 FPS 下的目標位移**：當物件快速移動且 `fps_limit` 設定極低（如 1 FPS）時，過時方框可能會暫時落後移動目標，直到下一次推檢到達。透由虛線與 `[SAMPLED]` 標籤可顯式告知使用者此現象。
