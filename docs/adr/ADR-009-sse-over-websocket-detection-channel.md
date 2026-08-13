# ADR-009：偵測結果通道採 SSE 而非 WebSocket

| 欄位 | 內容 |
|------|------|
| **狀態** | 已接受 (Accepted) |
| **日期** | 2026-08-13 |
| **決策者** | 開發團隊 |
| **相關 ADR** | [ADR-004](ADR-004-global-vars-cross-thread.md) |
| **相關 PRD** | [rtsp_relay_sse_detection_overlay_prd.md](../prd/rtsp_relay_sse_detection_overlay_prd.md) |

---

## 情境與問題

系統需要在 RTSP 模式下將 YOLO 背景推論的偵測結果（bounding box 座標、類別、信心度、原始幀尺寸）即時推送至瀏覽器前端，供 Canvas 疊加繪製偵測框使用。

此通訊通道具備以下特性：
- 資料流向為固定的「伺服器 → 瀏覽器」（單向推送）。
- 推送頻率由推論速率與抓幀速率決定（~2–10 Hz）。
- 每次 Payload 為小型 JSON 結構（< 2 KB）。
- 瀏覽器端需要在網路短暫中斷後自動重新連線。

需要決定使用 Server-Sent Events (SSE) 還是 WebSocket 實作該推送通道。

---

## 決策選項

### 選項 A（已採用）：Server-Sent Events (SSE)

Flask 以 `Response(generate(), mimetype='text/event-stream')` 實作生成器，輪詢全域 `LATEST_DETECTIONS` 並 yield 更新事件。瀏覽器端使用原生 `EventSource` API 訂閱。

### 選項 B：WebSocket (flask-socketio)

引入 `flask-socketio` 與 `simple-websocket` 依賴。背景推論執行緒呼叫 `socketio.emit()` 推送事件，瀏覽器端使用 socket.io.js 客戶端程式庫。

---

## 決策

**採用選項 A（Server-Sent Events, SSE）。**

---

## 理由

1. **零額外依賴**：Flask 3.x 原生支援 SSE 串流回應，`requirements.txt` 無需新增任何套件。WebSocket 方案需引入 `flask-socketio` 及其底層依賴，增加套件體積與維護複雜度。
2. **單向模型完全契合**：偵測結果的資料流向永遠是伺服器至瀏覽器，SSE 完美契合單向 Event Stream 模型。WebSocket 的雙向通道能力在此場景屬於過度設計。
3. **瀏覽器內建自動重連**：`EventSource` 在連線中斷時自動以指數退避重新連線，不需要撰寫額外重連邏輯。
4. **Threading 模式相容**：Flask 在 `threaded=True` 模式下，SSE 生成器於獨立執行緒中運行，與標準多執行緒模型完全相容，不需要 gevent 或 eventlet 猴子補丁（monkey patching）。
5. **PyInstaller 打包友善**：SSE 不依賴 C 擴展模組或非標準事件迴圈，在 PyInstaller `--onefile` 打包部署（Raspberry Pi 5 ARM64）時無額外 Hook 問題。

---

## 取捨與風險

- **無法進行前端至伺服器反向推送**：若未來需要前端透過此通道發送控制指令，SSE 無法滿足需求。但現有架構已透過 Flask REST POST 端點處理設定更新，反向推送並非必要。
- **HTTP/1.1 連線數限制**：瀏覽器對同一 Origin 的 HTTP/1.1 連線數上限通常為 6。同時開啟 `/video_feed`（MJPEG）與 `/detections_feed`（SSE）共佔用 2 個持久連線，仍在安全範圍內。
- **僅支援文字格式**：SSE 訊息必須為 UTF-8 文字。偵測結果結構為 JSON 字串，此限制不構成影響。
