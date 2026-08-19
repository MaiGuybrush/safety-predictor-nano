# CPU 消耗增加問題診斷分析報告

## 1. 診斷背景與目標

- **基準版本（舊版）**：`a3ba2a75d1cca95301973267021daae53312b11a`
- **對照版本（新版）**：最新版本 (`HEAD`)
- **問題現象**：自基準版本更新後，系統在邊緣設備（Raspberry Pi 5 / CPU 環境）上的 CPU 佔用率顯著上升。
- **分析範圍**：集中比較從 **「讀取 RTSP 訊號源 ➔ YOLO 模型推論 ➔ 判斷 ROI 交集 ➔ 輸出 `.jsonl` 結果檔案」** 完整資料流與執行緒架構的演進差異。

---

## 2. 流程架構對比

```mermaid
graph TD
    subgraph "舊版本 (a3ba2a75)"
        O_RTSP[RTSP 來源] -->|限速 capture 5fps<br/>sleep 1/fps_limit| O_Cap[StreamHandler 執行緒]
        O_Cap -->|主執行緒每 10ms 輪詢| O_Main[main.py 主迴圈]
        O_Main -->|單線程依序執行| O_Infer[InferenceEngine.infer<br/>YOLO CPU]
        O_Infer -->|字串格式化| O_Log[StatsLogger<br/>寫入 detections.log]
    end

    subgraph "新版本 (HEAD)"
        N_RTSP[RTSP 來源 (多路)] -->|全速 capture 30fps<br/>sleep 0.001s 解碼| N_Cap[StreamHandler 執行緒群]
        
        %% 主迴圈
        N_Cap -.->|無條件每 10ms 取影格| N_Main[main.py 主迴圈 ~100Hz]
        N_Main -->|縮放+拼圖| N_Grid[compose_grid]
        N_Grid -->|每秒約 100 次 JPEG 編碼| N_Jpg[cv2.imencode]
        
        %% 推論背景執行緒
        N_Cap -->|最新影格| N_Worker[_inference_worker 執行緒]
        N_Worker -->|Round-Robin 抽樣| N_Infer[InferenceEngine.infer<br/>ONNX / NCNN / PyTorch]
        N_Worker -->|第 1 次計算| N_ROI1[event_producer._is_inside_zone<br/>Sutherland-Hodgman + 面積 + 點測試]
        N_ROI1 -->|傳入 stream_zone| N_Prod[event_producer.process_detections]
        N_Prod -->|第 2 次重複計算| N_ROI2[event_producer._is_inside_zone]
        N_Prod -->|EventStart / Frame / End| N_Queue[event_queue 佇列]
        N_Queue -->|背景線程取事件| N_Writer[EventWriterService]
        N_Writer -->|寫入磁碟| N_JSONL[輸出 .jsonl 檔案]
        
        %% 心跳服務
        N_HB[HeartbeatService 執行緒群] -.->|定時發送心跳| N_Agent[argus-agent / 磁碟]
    end
```

---

## 3. 各階段關鍵差異與程式碼對照

### 3.1 讀取 RTSP 訊號源與軟體解碼 (Stream Ingestion & Decoding)

- **舊版實作 (`stream_handler.py`)**：
  在 `StreamHandler._capture_frames` 中，每讀取一幀後主動呼叫 `time.sleep(1.0 / self.fps_limit)`（例如 5 FPS 時 sleep 0.2 秒）。
  底層 OpenCV / FFmpeg 在 CPU 上的解碼工作量被嚴格限制在每秒約 5 幀。
- **新版實作 (`stream_handler.py:L70-71`)**（引入於 Commit `f68e6d9` / ADR-012）：
  為了避免 RTSP 緩衝區積壓導致即時畫面延遲，移除了按 FPS 限速的 sleep，改為：
  ```python
  self.frame_queue.put(frame)
  time.sleep(0.001)  # 全速擷取與解碼
  ```
- **CPU 衝擊評估：【極高（主要耗能點）】**
  若攝影機以 1080p @ 30 FPS 發送 H.264/H.265 串流，CPU 必須**全速解碼每一幀**。單路串流的 CPU 解碼運算量增加了約 **5 ~ 6 倍**；多路串流時呈線性倍數疊加。

---

### 3.2 主執行緒迴圈與影像處理 (Main Loop & JPEG Grid Encoding)

- **舊版實作 (`main.py`)**：
  在 `mode == 'rtsp'` 下，主迴圈只單純從串流取得影格進行推論，**完全不進行任何影像縮放、網格拼接或 JPEG 編碼**。
- **新版實作 (`main.py:L467-483`)**（引入於 Commit `82319c6` / `933919c`）：
  主迴圈以每 10ms 一次（`time.sleep(0.01)`，理論上限 100 FPS）的速度無條件執行多路影像拼接與 JPEG 壓縮：
  ```python
  if mode == 'rtsp':
      if stream_units:
          for unit in stream_units:
              handler = unit["handler"]
              frame = handler.get_latest_frame()
              if frame is not None:
                  unit["latest_raw_frame"] = frame
                  latest_frames[unit["url"]] = frame
          
          active_frames = [latest_frames[u["url"]] for u in stream_units if u["url"] in latest_frames]
          if active_frames:
              grid_img = compose_grid(active_frames, target_width=640) # 多路 cv2.resize 與 NumPy 矩陣拼接
              if grid_img is not None:
                  ret_enc, buffer = cv2.imencode('.jpg', grid_img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                  if ret_enc:
                      web_ui.LATEST_FRAME = buffer.tobytes()
  ```
- **CPU 衝擊評估：【極高（常駐無效消耗）】**
  **即使完全沒有任何使用者打開瀏覽器查看 Web UI**，主迴圈依然持續以近 100 FPS 全速執行多路影像的 `cv2.resize`（雙線性插值縮放）與 `cv2.imencode`（JPEG 壓縮編碼）。

---

### 3.3 推論排程與執行緒競爭 (Inference Scheduling & Context Switching)

- **舊版實作**：
  單線程順序執行（主執行緒輪詢 ➔ 呼叫 `engine.infer()` ➔ 寫日誌）。
- **新版實作**：
  - 推論改至獨立背景執行緒 `_inference_worker`，採用 Round-Robin 排程與時間戳抽樣（`fps_limit`）。
  - 支援多後端（ONNX / NCNN / PyTorch）與每路串流獨立模型快取。
- **CPU 衝擊評估：【中等】**
  執行緒數量大幅增加：$N$ 個 `StreamHandler` 擷取執行緒 + 1 個推論執行緒 + 1 個主迴圈編碼執行緒 + 1 個 `EventWriter` 執行緒 + $N$ 個 `Heartbeat` 執行緒 + Flask 執行緒群。在 Raspberry Pi 5 僅有 4 個 CPU 核心的環境下，引發嚴重的 CPU 核心競爭與 Context Switching 開銷。

---

### 3.4 ROI 危險區域交集運算 (ROI Intersection Evaluation)

- **舊版實作**：
  無任何 ROI 概念，直接將所有 detections 輸出。
- **新版實作 (`event_producer._is_inside_zone`)**（引入於 Commit `1ead44e` / `8c9c0d8`）：
  支援 `center` 與 `intersect` 模式。在 `intersect` 模式下進行 Sutherland-Hodgman 4 邊多邊形裁剪（`_clip_polygon`）、多邊形面積計算（`_polygon_area`）、四頂點與中心點 `cv2.pointPolygonTest`。
- **重複計算問題**：
  1. `main.py:L169-170`：在推論完成後，先遍歷一次 formatted_detections 計算 `d["in_zone"]`：
     ```python
     for d in formatted_detections:
         d["in_zone"] = event_producer._is_inside_zone(d, poly, w, h, trigger_mode=t_mode, sensitivity=sens)
     ```
  2. `event_producer.py:L140-143`：傳入 `event_producer.process_detections` 後，又對同一批 detections 重複計算了一次 `_is_inside_zone`：
     ```python
     detections = [
         d for d in detections 
         if _is_inside_zone(d, polygon, frame_w, frame_h, trigger_mode=trigger_mode, sensitivity=sensitivity)
     ]
     ```
- **CPU 衝擊評估：【中等】**
  重複進行多邊形頂點計算與裁剪，在偵測框數量多時增加無謂運算。

---

### 3.5 輸出 `.jsonl` 結果檔案 (Event Pipeline & JSONL Generation)

- **舊版實作**：
  直接呼叫 Python 內建 logging 將格式化文字附加寫入 `detections.log`（同步 I/O）。
- **新版實作 (`event_producer.py` & `argus_eventlog`)**（引入於 Commit `a842066` / ADR-014）：
  - 狀態機維護 `EventStart`、`EventFrame`、`EventEnd` 物件生命週期。
  - 將事件放入執行緒安全的 `event_queue`。
  - 背景獨立執行緒 `EventWriterService` 不斷從 queue 取出物件，序列化為 JSON 字串並依鏡頭目錄寫入 `.jsonl` 檔案。
- **CPU 衝擊評估：【低 ~ 中等】**
  非主要效能瓶頸，開銷主要在 JSON 序列化與磁碟寫入。

---

## 4. 可疑問題排名與假說 (Ranked Falsifiable Hypotheses)

| 排名 | 可疑根因 | 機制描述 | 可證偽預測 (Falsifiable Prediction) |
| :--- | :--- | :--- | :--- |
| **1 🔴** | **`StreamHandler` 解碼幀率由 5 FPS 變為 30 FPS 全速解碼** | 為了防延遲移除 sleep，導致 OpenCV / FFmpeg 在 CPU 上以 25~30 FPS 全速解碼 H.264 影格。 | 若在 `_capture_frames` 中測量單純 `cap.read()` 佔用的 CPU 時間，會發現軟體解碼佔據了 Process 大部分的 CPU 時間。串流數越多，CPU 負載呈線性暴增。 |
| **2 🔴** | **`main.py` 主迴圈常駐以 ~100 FPS 高頻進行無效的 Grid 縮放與 JPEG 壓縮** | 無論是否有 Web UI 客戶端連線，主迴圈每 10ms 無條件做多路 `cv2.resize` 與 `cv2.imencode`。 | 若測量 `compose_grid` + `cv2.imencode` 的呼叫次數，每秒高達近 100 次。若暫時在主迴圈停用 JPEG 編碼或改為有連線時才觸發，常駐 CPU 佔用率將顯著下降。 |
| **3 🟡** | **多執行緒競爭 (Thread Contention on 4 Cores)** | 系統存在 $N$ 個 Capture 執行緒、推論執行緒、主迴圈編碼、EventWriter、Heartbeat 等大量密集執行緒，頻繁 sleep(0.001) / sleep(0.01)。 | 在 4 核心環境下 Context Switching 次數極高，降低執行緒輪詢頻率能直接降低 CPU 消耗。 |
| **4 🟡** | **ROI 多邊形交集運算重複執行** | 在 `_inference_worker` 與 `event_producer.process_detections` 重複執行了兩次相同的 Sutherland-Hodgman 多邊形裁剪運算。 | 重構為單次判斷後，推論執行緒的每幀平均處理時間將有些微改善。 |

---

## 5. 後續驗證與分析建議

1. **非侵入式 Profiling**：
   使用 `py-spy`（例如 `py-spy top --pid <PID>` 或產出 Flamegraph 火焰圖），在不修改程式碼的情況下精確驗證 `cap.read()` 與 `cv2.imencode` 的 CPU 耗時佔比。
2. **依據數據驗證假說**：
   根據火燄圖確認第 1 名與第 2 名假說是否為主要熱點，再行研議針對解碼與 JPEG 串流機制的最佳化方案。
