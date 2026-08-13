# PRD：RTSP 直接轉發 + SSE 前端偵測框疊加

**專案**：Argus Safety Predictor Nano  
**狀態**：Ready for Agent  
**標籤**：`ready-for-agent`, `streaming`, `web-ui`, `sse`, `multi-stream`

---

## Problem Statement

Argus Safety Predictor Nano 在 RTSP 模式下，原架構將推論（YOLO）與影像標注（繪框）耦合在同一個同步主迴圈中。由於 CPU 推論每幀需 ~150–500ms，導致：
1. Web UI 畫面更新速率退化至 2–5 FPS，發生嚴重卡頓。
2. 推論與顯示無法解耦，即使使用者只想「確認 RTSP 訊號源是否正常」，也必須承擔完整推論的 CPU 成本。
3. 伺服器端合成帶偵測框的影像（double JPEG compression：H.264 RTSP → OpenCV decode → 標注 → JPEG encode），畫質比本地影片模式更差。

---

## Solution

採三層解耦管線設計：
1. **MJPEG Relay（低成本訊號轉發）**：伺服器端只做 RTSP decode → 原始 JPEG encode，不做標注與繪框。目標是讓瀏覽器能流暢確認 RTSP 訊號源健康狀態。
2. **背景推論執行緒（daemon thread）**：Round-Robin 推論各路串流，偵測結果寫入模組全域 `LATEST_DETECTIONS` dict，完全不阻塞顯示管線。
3. **SSE 偵測事件頻道 + Canvas 前端疊加**：瀏覽器用原生 `EventSource` API 訂閱 `/detections_feed`，收到 JSON 偵測結果後以 `<canvas>` 絕對定位於 MJPEG `<img>` 上方即時繪製偵測框。伺服器端零圖像標注與繪圖成本。

多路串流時，`/video_feed` 顯示純幀 Grid（無標注，極低 CPU 開銷）。使用者點擊 Grid 中的任一路影像，開啟全螢幕覆蓋層，顯示該路的即時 MJPEG（透過獨立端點 `/video_feed/<stream_id>`）並啟動 Canvas 偵測框疊加。

---

## User Stories

1. 作為操作人員，我希望在 RTSP 模式下能即時看到流暢的攝影機畫面（≥12 FPS），而不是卡頓的畫面，以便快速確認 RTSP 訊號源是否正常。
2. 作為操作人員，我希望多路 RTSP 串流的影像以 Grid 方式排列顯示，以便一眼確認所有攝影機的連線狀態。
3. 作為操作人員，我希望點擊 Grid 中的任一路攝影機影像，能以全螢幕覆蓋層的方式放大該路畫面，以便進行細節確認。
4. 作為操作人員，我希望在全螢幕模式下能看到該路攝影機的即時偵測框疊加在畫面上，以便驗證 YOLO 模型針對該場景的偵測效果。
5. 作為操作人員，我希望偵測框顯示類別 ID 與信心度，以便評估偵測品質。
6. 作為操作人員，我希望點擊全螢幕覆蓋層的任意位置即可關閉全螢幕，以便快速回到 Grid 概覽視圖。
7. 作為操作人員，我希望 RTSP 來源斷線時，對應的 Grid 格位顯示靜止的最後一幀（或 NO SIGNAL），系統不會崩潰。
8. 作為操作人員，我希望系統在沒有人瀏覽 Web UI 的情況下持續在背景推論並寫入偵測 log，以便事後查閱偵測記錄。
9. 作為部署工程師，我希望 SSE 偵測頻道不需要安裝額外的 Python 套件（如 flask-socketio），以降低部署複雜度與維護成本。
10. 作為部署工程師，我希望 RTSP relay 的 JPEG 編碼品質可配置（預設 85），以便在不同網路環境下平衡畫質與頻寬。
11. 作為部署工程師，我希望每路串流有獨立的 `/video_feed/<stream_id>` 端點，以便全螢幕模式精確訂閱單路影像來源。
12. 作為部署工程師，我希望熱重載 `config.yaml` 時，推論執行緒與 relay 迴圈都能正確重建串流配置，不需要重啟程序。
13. 作為系統管理員，我希望本地影片（video）模式（影片播放與伺服器端繪框）在本次修改後完全不受影響。
14. 作為系統管理員，我希望 RTSP 模式的 Grid 視圖本身不顯示偵測框（純幀拼接），以降低伺服器 CPU 開銷。
15. 作為系統管理員，我希望偵測到目標時只需寫入 detection log，不需要任何主動推播 alert 通知。

---

## Implementation Decisions

### 1. 架構分層：Relay / Inference / SSE 三層解耦

- **推論執行緒（daemon thread）**：以 Round-Robin 方式持續對各路串流執行 YOLO，結果寫入模組全域 `LATEST_DETECTIONS`。
- **Relay 迴圈（main thread）**：獨立地將各路最新原始幀合成純幀 Grid，JPEG encode（品質 85）寫入 `LATEST_FRAME`。兩者完全不相依，互不阻塞。
- **SSE 端點**：以 20Hz 輪詢 `LATEST_DETECTIONS` 的 timestamp，有更新才推送給瀏覽器。

### 2. SSE 取代 WebSocket

偵測結果通道採 Server-Sent Events（Flask 原生 `text/event-stream` 回應），而非 WebSocket。
- **零額外依賴**：Flask 原生支援，`requirements.txt` 無需新增套件。
- **單向推送符合需求**：偵測資料只需伺服器→瀏覽器單向傳輸。
- **自動重連**：瀏覽器原生 `EventSource` API 內建連線中斷自動重連機制。
- **PyInstaller 友善**：不需要 async event loop 或 gevent/eventlet 猴子補丁。

### 3. SSE Payload 結構

每次推送為一個 JSON 陣列，包含有更新的串流偵測結果：
```json
[
  {
    "stream_url": "rtsp://...",
    "stream_index": 0,
    "label": "CAM_01",
    "detections": [
      {"cls": 0, "conf": 0.89, "xyxy": [[10, 20, 100, 200]]}
    ],
    "frame_w": 1920,
    "frame_h": 1080,
    "ts": 1770800000.123
  }
]
```

### 4. 前端 Canvas 偵測框座標縮放

Canvas 絕對定位覆蓋於 MJPEG `<img>` 之上（`pointer-events: none`）。依 MJPEG 的顯示尺寸（`img.clientWidth` / `img.clientHeight`）與 SSE payload 中的 `frame_w` / `frame_h` 計算縮放比例，將偵測框像素座標轉換為 Canvas 繪圖座標。

### 5. 每路串流獨立端點 `/video_feed/<stream_id>`

全螢幕單路模式下，前端動態修改 `<img>` 的 `src` 為 `/video_feed/<stream_id>`（`stream_id` 為串流索引）。伺服器新增此端點，只轉發對應串流的最新原始幀（無需 Grid 合成）。

### 6. 全螢幕覆蓋層 UI

使用 CSS `position: fixed`，`z-index` 設定為高層級，覆蓋整個 viewport。內含 MJPEG `<img>` 與 `<canvas>` 疊加層。點擊覆蓋層任意位置即可關閉（回到 Grid 視圖）。

### 7. MJPEG Relay 品質與速率

JPEG 編碼品質統一設定為 `85`（`cv2.IMWRITE_JPEG_QUALITY`）。`fps_limit` 沿用現有機制控制 `StreamHandler` 抓幀速率，自然限制背景推論與 Relay 轉發速率。

### 8. Video 模式向下相容

本地影片（video）模式繼續使用 `VideoHandler` 原有架構（伺服器端繪框），不引入 SSE。`/video_feed` 在 video 模式下繼續服務含偵測框標注的畫面。

---

## Testing Decisions

### 好測試的定義

測試方針針對外部可觀測行為，不測試內部實作細節：
- 測試 `/detections_feed` 端點的回應標頭與 JSON payload 結構。
- 測試 `LATEST_DETECTIONS` 結構填寫完整性（含 `frame_w`, `frame_h`, `ts`, `stream_index`）。
- 測試獨立端點 `/video_feed/<stream_id>` 的 MJPEG 串流輸出。
- 不測試 Canvas 畫布的像素點、SSE 推送的毫秒級精確時間。

### 測試項目

1. **單元測試 (`test_sse_detections.py`)**：驗證 `LATEST_DETECTIONS` 結構與 `/detections_feed` SSE 端點邏輯。
2. **手動驗證**：
   - 啟動系統，RTSP 模式下 Web UI 畫面流暢（≥12 FPS）。
   - 點擊 Grid 任意串流，開啟全螢幕視圖，畫面正確載入且出現綠色偵測框。
   - 點擊全螢幕關閉，回到 Grid 視圖。
   - DevTools → Network 確認 `/detections_feed` 為 `text/event-stream`。
   - 切換至 video 模式，驗證本地影片播放與繪框功能不受影響。

---

## Out of Scope

- Grid 視圖上的偵測框疊加（Grid 本身不顯示偵測框）
- WebSocket 雙向通訊
- 瀏覽器推播 Alert / 通知機制
- HLS / WebRTC 串流協定
- 多 Process 架構
- Grid 欄位 UI 動態設定

---

## Further Notes

- Raspberry Pi 5 在此架構下，Relay 轉發（~5% CPU/路）與背景推論（~80% CPU）加總約佔 1 個 CPU 核心，剩餘 3 個核心仍有充裕算力處理其他任務。
- `frame_w` / `frame_h` 在 SSE payload 中傳遞，確保前端即使不知道 RTSP 的原始解析度，也能精確計算座標縮放率。
