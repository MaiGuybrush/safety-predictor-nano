# Spec: 隨選串流與輕量解碼節能架構 (On-Demand Streaming, Lightweight Decoding & Frontend Idle Disconnect)

## Problem Statement

目前 Argus Safety Predictor Nano 在邊緣設備（Raspberry Pi 5 / 嵌入式 CPU 環境）運作時，CPU 佔用率過高（從基準版本更新後顯著增加），主要肇因於以下架構問題：

1. **RTSP 串流解碼過度運算 (Over-Decoding)**：
   - 系統為避免 RTSP 攝影機 30 FPS 推流造成 OpenCV 緩衝區積壓與畫面延遲，將 `StreamHandler` 改為全速擷取 (`sleep(0.001)`)。
   - 即使系統設定的推論頻率僅為 2 FPS（甚至攝影機無告警事件），底層仍全速對每一影格執行完整的 H.264/H.265 軟體像素解碼與色彩空間轉換，造成龐大且無效的 CPU 運算。

2. **主迴圈無條件執行高頻 JPEG 編碼 (Unconditional JPEG Compression)**：
   - 後端主迴圈固定以每秒約 100 次（`time.sleep(0.01)`）的頻率無條件執行多路影像 `cv2.resize`、`compose_grid` 網格拼接以及 `cv2.imencode('.jpg', ...)` JPEG 壓縮。
   - 即使完全沒有任何使用者或瀏覽器連線至 Web UI 觀看即時畫面，該編碼迴圈依然全速空轉消耗 CPU。

3. **前端畫面長期閒置未釋放連線 (Unattended Streaming Leaks)**：
   - 使用者在瀏覽器開啟 Web UI 後，若離開座位、切換至其他分頁或鎖定螢幕，瀏覽器會持續保持 MJPEG (`/video_feed`) 長連線，導致後端持續處於高負載串流狀態，無法進入節能模式。

4. **重複的幾何相交運算 (Duplicate ROI Evaluation)**：
   - 在推論完成後，後端在推論執行緒與事件產生模組中重複執行了兩次多邊形相交裁剪運算。

---

## Solution

採用**「隨選即時串流 (On-Demand Streaming) + 輕量解碼抽樣 (Lightweight Grab/Retrieve Decoupling) + 前端智慧閒置中斷 (Client-Side Idle & Visibility Disconnect)」**的完整節能架構：

1. **解碼層：`grab()` 與 `retrieve()` 分離**：
   - `StreamHandler` 背景執行緒持續以 `cap.grab()` 輕量提取網路封包並維護 H.264 參考幀上下文，徹底避免 TCP 緩衝區積壓與破圖。
   - 當「無使用者觀看」時：僅在推論抽樣週期（如 2 FPS）才呼叫一次 `cap.retrieve()` 進行完整像素解碼供 YOLO 推論；其餘影格跳過像素解碼。
   - 當「有使用者觀看」時：恢復全速 `cap.retrieve()`，提供流暢的即時影像。

2. **後端編碼層：隨選延遲編碼 (Lazy JPEG Encoding)**：
   - 後端即時追蹤是否有活躍的視訊串流連線 (`active_stream_clients > 0`)。
   - 當無活躍連線時，主迴圈完全跳過 `compose_grid` 與 `cv2.imencode`，消除常駐 100 FPS 的空轉壓縮負載。

3. **前端層：分頁可見性與使用者閒置自動斷線 (Smart Disconnect & Wakeup)**：
   - **分頁切換偵測 (Page Visibility)**：當使用者切換至其他分頁或最小化瀏覽器時，前端立即清空 `img.src` 關閉串流連線；切回分頁時自動秒級恢復。
   - **閒置超時偵測 (Idle Timeout)**：當使用者在頁面上超過指定時間（預設 5 分鐘）無滑鼠/鍵盤動作時，自動中斷串流並顯示半透明省電休眠遮罩；使用者晃動滑鼠或點擊任意處立即喚醒並恢復播放。

4. **推論層：消除 ROI 重複計算**：
   - 推論完成後統一由單一函數計算並附加 `in_zone` 狀態，事件模組直接沿用，避免重複 Sutherland-Hodgman 多邊形裁剪。

5. **向下相容性與自適應 (Seamless Compatibility)**：
   - 未來現場攝影機若直接切換為子碼流（Sub-stream）或低幀率來源（如 2~5 FPS），程式碼完全不需任何修改即可自適應運作。

---

## User Stories

1. As a system administrator, I want the edge device (Raspberry Pi 5) to maintain low CPU usage (< 30%) during normal non-viewing periods, so that the hardware runs cool, stably, and consumes minimal power.
2. As a site operator, when no one is watching the Web UI, I want YOLO object detection and ROI intrusion evaluations to continue uninterrupted at the configured `fps_limit` (e.g. 2 FPS), so that security monitoring and `.jsonl` logging remain 100% reliable.
3. As a monitoring operator opening the Web UI, I want the live stream to display smoothly at native frame rates (25~30 FPS) without noticeable lag or accumulated buffer delay.
4. As a site technician, if my IP camera is configured with a low-resolution sub-stream or low-FPS feed in `config.yaml`, I want the system to handle it seamlessly without code modifications.
5. As a web user switching to another browser tab or minimizing the window, I want the Web UI to automatically disconnect the video stream to save edge device resources.
6. As a web user returning to the Web UI tab, I want the live video feed to automatically and instantaneously reconnect without manual refresh.
7. As a web user who leaves the monitoring page open and unattended for over 5 minutes, I want the stream to enter a sleep mode with an informative overlay prompt ("省電模式中 - 點擊任意處恢復監看").
8. As a web user in sleep mode, I want moving the mouse, touching the screen, or clicking anywhere to immediately wake up the stream and resume live playback.
9. As a developer, I want the backend Flask application to track active video stream connections in a thread-safe manner, so that backend decoding and JPEG encoding dynamically adapt to actual demand.
10. As a developer, I want the `StreamHandler` to use `cap.grab()` for lightweight packet draining and only invoke `cap.retrieve()` when required for inference sampling or active streaming.
11. As a developer, I want the main loop to completely bypass `compose_grid` and `cv2.imencode` when no video clients are connected, eliminating ~100Hz idle CPU waste.
12. As a safety auditor, I want `.jsonl` event outputs (EventStart, EventFrame, EventEnd) to remain accurate, low-latency, and unaffected by the video streaming state.
13. As a developer, I want ROI zone intersection evaluation to be computed only once per detected object per inference step, eliminating redundant geometric calculations.
14. As an operator editing settings in the Web UI, I want dynamic hot-reloading of stream configurations to seamlessly reset client trackers without dangling threads.

---

## Implementation Decisions

### 1. Backend Active Streaming Client Tracker (`web_ui.py`)
- 維護全域執行緒安全之活躍視訊連線計數器：
  - `ACTIVE_VIDEO_CLIENTS` (整數計數器，由 `threading.Lock` 保護)
  - 提供輔助函數 `is_streaming_active() -> bool`。
- 在 `/video_feed` (多路 Grid) 與 `/video_feed/<int:stream_id>` (單路) 的 Generator (`gen_frames` 與 `gen_single_stream_frames`) 中：
  - 連線建立進入迴圈前，呼叫連線增加註冊。
  - 使用 `try...finally` 區塊，當客戶端中斷連線（觸發 `GeneratorExit` 或 socket broken）時，保證執行連線減少註銷。

### 2. Main Loop Lazy JPEG Encoding (`main.py`)
- 在 `main.py` 的 RTSP 主迴圈中檢查 `web_ui.is_streaming_active()`：
  - 若為 `False`：跳過 `compose_grid` 與 `cv2.imencode('.jpg', ...)`，僅更新最新影格引用供推論執行緒使用。
  - 若為 `True`：執行 `compose_grid` 與 `cv2.imencode`，更新 `web_ui.LATEST_FRAME`。

### 3. Decoupled Grab/Retrieve in Stream Ingestion (`stream_handler.py`)
- `StreamHandler` 內部維護狀態旗標與抽樣排程：
  - 核心擷取迴圈以 `cap.grab()` 快速吃掉封包保持緩衝區淨空。
  - 抽樣判斷邏輯：
    - 若 `is_streaming_active()` 為 `True`：每幀呼叫 `cap.retrieve()`，全速更新 `frame_queue` / `latest_frame`。
    - 若 `is_streaming_active()` 為 `False`：依據 `fps_limit` 時間間隔（例如 0.5s），僅在到達推論時間點時呼叫 `cap.retrieve()` 更新 `frame_queue`；其餘時間直接略過 `retrieve()`。

### 4. ROI Intersection Calculation Deduplication (`main.py` & `event_producer.py`)
- 在 `_inference_worker` 內呼叫 `event_producer._is_inside_zone()` 計算並賦予 `d["in_zone"]`。
- `event_producer.process_detections` 移除內部重複執行的 `_is_inside_zone()` 過濾迴圈，直接使用傳入之 `d.get("in_zone", False)` 進行事件分派。

### 5. Frontend Smart Inactivity & Visibility Manager (`templates/index.html`)
- **Visibility Change 監聽**：
  - 監聽 `document.addEventListener('visibilitychange', ...)`。
  - 當 `document.hidden === true` 時，調用 `pauseStream()`（清空 `img.src` 與暫停 SSE 或忽略更新）。
  - 當 `document.hidden === false` 且未處於閒置超時狀態時，調用 `resumeStream()`（重設 `img.src = '/video_feed?t=' + Date.now()`）。
- **Idle Timeout 計時器**：
  - 設定 `IDLE_TIMEOUT_MS = 5 * 60 * 1000` (5 分鐘)。
  - 監聽全域事件：`mousemove`, `mousedown`, `keydown`, `touchstart`, `scroll`。
  - 逾時觸發時，切斷串流並在影像畫面上方顯示優雅的「省電休眠中」遮罩與喚醒按鈕。
  - 偵測到任何互動時自動重置計時器；若處於休眠狀態則立即喚醒並隱藏遮罩。

---

## Testing Decisions

### What makes a good test
- 僅測試對外暴露之行為與可觀察狀態（例如 API 回應、串流計數器、CPU 抽樣次數、JSONL 事件完整性），不耦合內部私有實作細節。

### Modules & Seams to be tested
1. **API / Web UI Seam (`test_on_demand_streaming.py`)**：
   - 模擬 HTTP 客戶端連線與斷開 `/video_feed` 及 `/video_feed/0`，驗證 `web_ui.is_streaming_active()` 正確在 `True` 與 `False` 間切換。
2. **Stream Ingestion & Decoupled Decoding Seam (`test_stream_handler_decoupled.py`)**：
   - 模擬 RTSP 來源，斷言在無活躍連線時 `retrieve()` 的呼叫頻率符合 `fps_limit`（而非 30 FPS 全速），且在啟用串流時自動提升為全速解碼。
3. **Inference & Event Integrity Seam (`test_event_producer.py`)**：
   - 驗證在低解碼抽樣模式下，`_inference_worker` 仍能正確接收影格並生成完整的 `EventStart`、`EventFrame`、`EventEnd` 與 `.jsonl` 輸出。
4. **Frontend E2E / Automation Seam**：
   - 驗證 Web UI 在收到 `visibilitychange` 與閒置事件時，正確切斷連線並展示休眠遮罩。

### Prior Art
- 參考 `test_sse_detections.py` 與 `test_event_producer.py` 的測試結構。

---

## Out of Scope

- 修改 IP 攝影機硬體端韌體設定或自動透過 ONVIF 協議切換攝影機編碼參數。
- 引入 GStreamer 或 PyAV 等外部 C 語言繫結庫（維持純 Python + OpenCV 跨平台與 ARM64 單一二進位打包相容性）。
- 修改 YOLO 模型結構或重新訓練模型權重。

---

## Further Notes

- 此規格在維持即時偵測精確度與串流畫質的前提下，針對 Raspberry Pi 5 邊緣運算場景提供最高效的 CPU 減負方案。
- 設計完全相容於未來的子碼流配置與各類客製化 RTSP 攝影機來源。
