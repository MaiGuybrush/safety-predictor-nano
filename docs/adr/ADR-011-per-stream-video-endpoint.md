# ADR-011：單路全螢幕模式採獨立 /video_feed/<stream_id> 端點

| 欄位 | 內容 |
|------|------|
| **狀態** | 已接受 (Accepted) |
| **日期** | 2026-08-13 |
| **決策者** | 開發團隊 |
| **相關 ADR** | [ADR-010](ADR-010-client-side-canvas-detection-overlay.md), [ADR-008](ADR-008-round-robin-inference-scheduling.md) |
| **相關 PRD** | [rtsp_relay_sse_detection_overlay_prd.md](../prd/rtsp_relay_sse_detection_overlay_prd.md) |

---

## 情境與問題

多路 RTSP 串流的 Grid 概覽視圖使用單一 `/video_feed` 端點提供合成後的 Grid 影像。當使用者點擊 Grid 中的某一路影像時，Web UI 需要開啟全螢幕覆蓋層，切換為顯示該路的原始單路畫面並疊加偵測框。

需要決定全螢幕模式的影像來源與路由架構：

### 選項 A：動態修改全域 LATEST_FRAME
當有使用者開啟單路全螢幕時，主迴圈暫停 Grid 合成，改為只將指定串流的最新幀編碼推入 `LATEST_FRAME`。`/video_feed` 端點不變。

**缺陷**：全域 `LATEST_FRAME` 無法同時服務多個模式。若有多個瀏覽器頁籤分別開啟 Grid 視圖與單路全螢幕，畫面將產生嚴重衝突與閃爍。

### 選項 B（已採用）：獨立的 /video_feed/<stream_id> 端點
新增 Flask 路由 `/video_feed/<int:stream_id>`，其 MJPEG 生成器只擷取 `stream_units[stream_id]` 的最新原始幀進行轉發。`/video_feed`（無 id）繼續穩定提供 Grid 合成影像。全螢幕開啟時，前端動態將 `<img>` 的 `src` 切換為 `/video_feed/<stream_id>`。

---

## 決策

**採用選項 B（獨立的 `/video_feed/<stream_id>` 端點）。**

---

## 理由

1. **無衝突的多頁籤與多視圖訂閱**：Grid 概覽與全螢幕單路視圖可由不同的瀏覽器頁籤同時開啟，各自訂閱需要的 MJPEG 端點，全域 `LATEST_FRAME`（Grid）不會被影響或污染。
2. **全螢幕單路畫質最佳**：獨立端點直接轉發單路原始幀，無需經過 Grid 降採樣縮放，全螢幕畫面細節最清晰。
3. **主迴圈邏輯解耦**：主迴圈永遠執行相同的 Grid 拼接任務，無需監聽「是否有使用者開啟全螢幕」。路由分發交由 Flask Web 端點處理，職責分離明確。
4. **容錯與邊界處理簡單**：若 `stream_id` 超出範圍（如熱重載移除串流），端點直接回應 `NO_SIGNAL_FRAME` 佔位圖像，不會造成主推論迴圈異常。

---

## 取捨與風險

- **HTTP/1.1 持久連線開銷**：全螢幕開啟時，瀏覽器會同時維持 `/video_feed`（Grid）+ `/video_feed/<stream_id>`（單路）+ `/detections_feed`（SSE）共 3 個持久連線。對同一 Origin 的 6 個連線限制仍在安全範圍內。全螢幕開啟時前端亦可視需要暫停主 Grid 的 `<img>` 載入以進一步節省頻寬。
