# Spec：本地影片 1.0x 原速播放與解耦推論機制

**專案**：Argus Safety Predictor Nano  
**狀態**：Ready for Agent  
**標籤**：`ready-for-agent`, `video-playback`, `threading`

---

## Problem Statement

Argus Safety Predictor Nano 在影片驗證模式（Video Mode）下，原本的執行邏輯為單一主迴圈同步執行「讀取影片幀 ➔ YOLO 推論 ➔ 畫框編碼 ➔ 格式化輸出」。在 CPU 上進行 YOLO 模型推論（如 300ms/幀）時，每一幀均需等待推論完成，導致影片播放速度嚴重被拉慢（慢動作成原速的 1/10）。

此外，Web UI 的 MJPEG 串流發送器存在固定 100ms 的延遲限制，使得畫面上上限最高僅能顯示 10 FPS。使用者在進行影片檔測試與驗證時，無法以正常的真實時間比例（1.0x 速率）觀察安全偵測系統的運作情況。

---

## Solution

引入雙執行緒解耦架構（Decoupled Architecture），新增專屬的本地影片處理模組（`VideoHandler`），將影片播放步進與背景 YOLO 物件推論完全分離：

1. **獨立播放執行緒**：依照影片檔的原始幀率（Native FPS，如 30 FPS）進行時間補償步進，並在背景將最新的辨識框即時疊加至影像中推送至 Web UI 全域串流緩衝區，確保畫面以 1.0x 原速與高流暢度播放。
2. **非同步推論迴圈**：推論引擎主迴圈依據系統設定的推論頻率（`fps_limit`）定期從 `VideoHandler` 獲取最新原始幀進行 YOLO 推論，並將檢測結果非同步寫回 `VideoHandler` 更新繪框快取。
3. **無縫循環與串流頻寬提升**：影片播放至結尾自動倒帶重播；同時將 Web UI MJPEG 串流發送間隔縮短至 30ms（支援 30 FPS 輸出）。

---

## User Stories

1. 作為一位測試工程師，我希望在影片驗證模式下影片能以 1.0x 原始速度播放，以便精確評估實際安全偵測系統的即時反應能力。
2. 作為一位測試工程師，我希望系統能自動讀取影片檔案的原始 FPS，以便不管輸入何種幀率的影片都能維持正確的播放節奏。
3. 作為一位測試工程師，我希望即使 CPU 推論速度較慢（如 5 FPS），影片播放畫面仍能維持 30 FPS 的順暢視覺體驗。
4. 作為一位測試工程師，我希望在影片播放時，畫面上標記的安全偵測框能持續更新最近一次的推論結果，以便觀察目標物體的跟蹤狀態。
5. 作為一位測試工程師，我希望當影片播放到達結尾時能夠自動無縫循環重播，以便不間斷地進行系統測試。
6. 作為一位操作人員，我希望 Web UI 串流能支援更高 FPS（如 30 FPS）的影像傳輸，以便獲得高清晰度與高順暢度的實時畫面監控。
7. 作為一位系統架構師，我希望本地影片處理器與 RTSP 串流處理器維持獨立模組，以便確保專案模組職責單一與高維護性。
8. 作為一位系統架構師，我希望影片讀取與檢測框更新過程具備執行緒安全性（Thread-Safety），以便防止多執行緒讀寫全域狀態時產生 Race Condition。

---

## Implementation Decisions

### 1. 雙執行緒解耦模組設計 (VideoHandler)
新增專屬影片處理模組，內部運行背景 Daemon Thread，獨立負責影片檔案的開啟、讀取、時間補償計算、疊加最新邊框與 JPG 編碼。

### 2. 檢測框非同步快取 (Bounding Box Caching)
`VideoHandler` 內部維護一份最新的邊框結果快取（`latest_detections`），使用 `threading.Lock` 確保主推論執行緒寫入與播放執行緒讀取時的執行緒安全性。

### 3. 原生 FPS 時間補償算法
播放執行緒透過媒體讀取介面取得影片原始 FPS（若無則預設 30 FPS），計算目標間隔 `frame_interval = 1.0 / native_fps`。每一幀計算讀取與繪製耗時 `elapsed` 後，動態暫停 `sleep_time = frame_interval - elapsed`，精確維持 1.0x 實時播放。

### 4. 無縫倒帶重播
當讀取影片幀失敗或到達影片末端（EOF）時，播放執行緒自動呼叫媒體介面重置當前幀索引至 0（`CAP_PROP_POS_FRAMES = 0`），無縫重頭播放。

### 5. Web UI 串流產生器頻率調整
將 Web UI 的 MJPEG 串流發送間隔由 0.1 秒（10 FPS 上限）調降至 0.03 秒（約 33 FPS 上限），配合 30 FPS 原速影片輸出。

---

## Testing Decisions

### 好測試的定義
測試應著重於模組的**外部公開行為**與**執行緒安全性**，而不是測試 OpenCV 的內部解碼細節。測試應確保資料在跨執行緒傳遞時的完整性與讀取邏輯。

### 測試模組與檢驗縫 (Seams)
- **`VideoHandler` 測試縫**：
  - 測試 `update_detections()` 與 `get_latest_detections()` 是否具備 Thread-Safe 拷貝隔離。
  - 使用 Mocked OpenCV 測試 `VideoHandler` 在開啟、播放與停止時的執行緒啟動與資源釋放。
- **`Web UI` 串流測試縫**：
  - 使用 Flask Test Client 驗證端點與全域 `LATEST_FRAME` 的傳輸邏輯。

### Prior Art
參考現有 `tests/test_ncnn_support.py` 中的 `unittest` 模擬風格（`unittest.mock.patch`），採用 Python 標準庫 `unittest` 進行無相依自動化測試。

---

## Out of Scope

- **音訊同步 (Audio Sync)**：本系統僅關注影像安全偵測，影片音訊解碼與播放不在支援範圍。
- **倒帶/快進/任意時間軸拖曳**：僅支援從頭播放與自動循環重播，不提供進度條拖曳控制。
- **硬體加速解碼 (Hardware Video Decoder)**：目前使用標準 CPU 軟體解碼，不引入專屬 GPU/VPU 解碼器。

---

## Further Notes

- 當系統於 Raspberry Pi 5 ARM64 平台上運行時，搭配 NCNN 後端可進一步提升推論頻率，使檢測框的更新率與原速播放更加貼合。
