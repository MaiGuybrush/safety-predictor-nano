# ADR-010：偵測框由前端 Canvas 繪製而非伺服器端圖像標注

| 欄位 | 內容 |
|------|------|
| **狀態** | 已接受 (Accepted) |
| **日期** | 2026-08-13 |
| **決策者** | 開發團隊 |
| **相關 ADR** | [ADR-008](ADR-008-round-robin-inference-scheduling.md), [ADR-009](ADR-009-sse-over-websocket-detection-channel.md) |
| **相關 PRD** | [rtsp_relay_sse_detection_overlay_prd.md](../prd/rtsp_relay_sse_detection_overlay_prd.md) |

---

## 情境與問題

RTSP 模式下，系統需要在瀏覽器中呈現帶有偵測框的即時畫面。有兩種實作策略：

**策略 A（舊版實作）**：伺服器端在推論後使用 `cv2.rectangle` / `cv2.putText` 直接標注原始幀，再 JPEG encode 推入 MJPEG 串流。推論與顯示強耦合，`LATEST_FRAME` 僅在每次推論完成後更新，導致畫面更新速率退化至推論速率（~2–5 FPS）。

**策略 B（本 ADR，已採用）**：伺服器端只做低成本的 MJPEG Relay（原始幀 JPEG encode），不做任何標注。偵測結果透過 SSE 以 JSON 格式推送至瀏覽器，前端使用 HTML5 `<canvas>` 絕對定位覆蓋於 MJPEG `<img>` 上方繪製偵測框。

---

## 決策

**採用策略 B（前端 Canvas 繪圖）。**

---

## 理由

1. **顯示速率完全解耦**：MJPEG Relay 的畫面更新速率不再受 CPU 推論時間限制，可達設定的 `fps_limit`（15 FPS）。即使 YOLO 推論耗時 500ms，畫面仍流暢播放，偵測框僅有些許視覺延遲。
2. **消除二次 JPEG 壓縮損耗**：原始幀直接 JPEG encode（品質 85），不再經過標注後二次編碼。畫面細節比舊版伺服器標注更清晰。
3. **降低伺服器 CPU 負擔**：OpenCV 繪框與文字標注在 15 FPS 下約佔用 3–7.5% CPU 算力。將標注轉移至前端 Canvas 繪製，伺服器算力消耗降為零。
4. **動態座標縮放**：前端依 SSE payload 中的 `frame_w` / `frame_h` 與 `<img>` 的實際顯示尺寸計算縮放比例，偵測框能精確對齊目標物體，不受畫面響應式縮放影響。

---

## 前端座標縮放公式

```javascript
// 計算座標縮放比例
scaleX = img.clientWidth / frame_w;
scaleY = img.clientHeight / frame_h;

// 最終 Canvas 繪圖座標
rx = x1 * scaleX;
ry = y1 * scaleY;
rw = (x2 - x1) * scaleX;
rh = (y2 - y1) * scaleY;
```

---

## 取捨與風險

- **微小視覺延遲**：背景推論非同步進行，偵測框相對於最新 MJPEG 畫面可能存在 ~100–300ms 的非同步延遲。對於「 confirmation RTSP 訊號」與「觀察偵測效果」的使用場景，此延遲完全可接受。
- **依賴客戶端 JavaScript**：若瀏覽器關閉 JavaScript，偵測框將無法繪製。本系統使用場景為專用監控工作站，預設開啟 JavaScript。
