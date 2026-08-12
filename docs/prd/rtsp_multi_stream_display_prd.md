# PRD：RTSP 多路串流即時顯示偵測框

**專案**：Argus Safety Predictor Nano  
**狀態**：Ready for Agent  
**標籤**：`ready-for-agent`, `streaming`, `web-ui`, `multi-stream`

---

## Problem Statement

Argus Safety Predictor Nano 在 `rtsp` 模式下，主推論迴圈會從各路 RTSP 串流取幀、執行 YOLO 推論，並將偵測結果寫入日誌。然而，推論完成後**從未將帶有偵測框的影像推入 Web UI**，導致瀏覽器在 RTSP 模式下打開 `/video_feed` 只看到空白畫面，無法即時確認偵測效果。

此外，目前設定格式（`rtsp_streams`）只允許指定 URL 字串，無法為不同攝影機指派不同的偵測模型，限制了多場景、多任務的部署彈性。若每路串流都各自載入一份模型實例而未做資源共享，也會在多路使用相同模型的情境下造成不必要的記憶體浪費。

---

## Solution

在 RTSP 推論迴圈中補上影像標注與 MJPEG 輸出邏輯，使 Web UI 能即時顯示帶有偵測框的畫面。同時升級設定格式，支援每路串流指定各自的模型，並在模型路徑相同時自動共用同一個 `InferenceEngine` 實例，避免重複載入。推論採 Round-Robin 排程，確保每路串流在多路並行時仍能獲得穩定的有效 FPS。

---

## User Stories

1. 作為操作人員，我希望在瀏覽器開啟 Web UI 時能即時看到 RTSP 攝影機的畫面，以便確認系統正確連線且攝影機有畫面輸出。
2. 作為操作人員，我希望在即時畫面上看到 YOLO 偵測框與類別標籤，以便即時確認偵測結果是否符合預期。
3. 作為操作人員，我希望偵測框能顯示類別名稱與信心度分數，以便判斷偵測品質。
4. 作為操作人員，我希望在 RTSP 來源未連線或串流尚未就緒時，Web UI 顯示「NO SIGNAL」佔位畫面而非空白，以便判斷是系統問題還是串流問題。
5. 作為操作人員，我希望多路 RTSP 串流的畫面以 Grid 方式合排顯示在同一個視訊區塊中，以便一眼掌握所有攝影機狀態。
6. 作為操作人員，我希望每路串流的畫面上顯示自訂的攝影機標籤（如「CAM_01」），以便快速識別攝影機位置。
7. 作為操作人員，我希望 RTSP 模式與影片（video）模式都能在 Web UI 顯示視訊區塊，不因模式不同而消失。
8. 作為部署工程師，我希望在 `config.yaml` 中為每路 RTSP 串流獨立指定模型檔案，以便讓不同場景的攝影機使用最適合的偵測模型。
9. 作為部署工程師，我希望設定格式支援向下相容，在不修改現有 `rtsp_streams` 字串格式的情況下，系統仍能正常運作並使用全域 `model_path` 作為 fallback。
10. 作為部署工程師，我希望多路串流使用相同模型時，系統只載入一份模型實例，以節省 Raspberry Pi 5 有限的記憶體資源。
11. 作為部署工程師，我希望每路串流在多路並行推論時仍能維持穩定的有效 FPS，不因串流數增加而大幅下降。
12. 作為部署工程師，我希望修改 `config.yaml` 中的串流設定後，系統能熱重載並重建串流與引擎對應關係，不需要手動重啟。
13. 作為部署工程師，我希望熱重載時若模型路徑未改變，系統能重用已快取的 Engine 實例，不重複載入模型。
14. 作為系統管理員，我希望原有的影片（video）模式播放與偵測框顯示功能在本次修改後完全不受影響。
15. 作為系統管理員，我希望 MJPEG 串流的畫面品質（JPEG 壓縮率）可在程式碼層面調整，以便在頻寬與畫質之間取得平衡。

---

## Implementation Decisions

### 1. Config Schema 版本遷移（`rtsp_streams` → `streams`）

新增 `streams` 欄位，接受物件列表格式，每個物件包含：

```
{ url: str, model: str (optional), label: str (optional) }
```

`config_manager` 新增 `get_stream_configs()` 方法，統一回傳標準化的串流設定列表。解析優先順序：
- 若存在 `streams` 欄位（物件列表），解析之。
- 否則 fallback 至舊版 `rtsp_streams`（字串列表），每條 URL 使用全域 `model_path`。
- 每條串流若未指定 `model`，同樣 fallback 至全域 `model_path`。

此設計確保既有設定檔無需修改即可繼續運作（向下相容）。

### 2. Per-Stream Model Assignment（每路綁定獨立模型）

系統啟動及熱重載時，依照 `get_stream_configs()` 的結果，為每路串流建立對應的 `InferenceEngine` 實例。`StreamHandler` 與 `InferenceEngine` 以 tuple 的形式配對，構成 `stream_units` 列表供主迴圈使用。

### 3. Engine Instance Cache（相同模型共用實例）

建立 `engine_cache: dict[str, InferenceEngine]`，以模型路徑（`model_path`）為 key。建立 `stream_units` 時，若 `engine_cache` 中已有相同路徑的實例，直接重用，不重新載入模型。熱重載時重建 cache，但只對路徑有變化的模型才重新載入。

此設計在「多路串流使用相同模型」的典型部署情境下，可將記憶體佔用降低至單一模型實例。

### 4. Round-Robin 推論排程

主迴圈改為每輪只推論**一路**串流（由 `rr_index` 輪流指定），推論完成後即進入下一輪迴圈。每輪同時更新該路串流的最新標注幀，並將所有路的最新幀合成 Grid 後推入 `web_ui.LATEST_FRAME`。

此排程確保每路串流的 GPU/CPU 時間配額一致，且每路有效推論 FPS 不受串流數量乘法影響（固定為推論引擎速度上限）。

### 5. 影像繪框與 Grid 合成（Draw + Grid Pipeline）

推論完成後，對原始幀執行 `cv2.rectangle` 和 `cv2.putText` 標注偵測框與標籤，並在左上角疊加串流自訂標籤。標注後的幀以串流 URL 為 key 存入 `latest_frames` dict，持久保留至被新幀覆蓋。

Grid 合成邏輯將所有幀縮放至統一寬度（`target_w=640`），並依 `max_cols=2` 排列。不足以填滿的格位以純黑填補。

JPEG 編碼品質預設為 80，以 `cv2.IMWRITE_JPEG_QUALITY` 參數控制。

### 6. 無訊號佔位幀

`web_ui` 模組啟動時預先生成一張黑底文字 JPEG（"NO SIGNAL"），存於模組級常數。`gen_frames()` 在 `LATEST_FRAME` 為 `None` 時輸出佔位幀，使瀏覽器顯示等待訊號畫面而非無限等待。

### 7. Web UI 前端顯示條件解除

`index.html` 移除 Jinja2 `{% if mode == 'video' %}` 限制，讓視訊區塊在 RTSP 模式下同樣渲染。CSS Grid 雙欄 layout 亦移除 Jinja2 條件，對兩種模式均生效。

### 8. 熱重載對應更新

熱重載偵測邏輯擴充：若 `streams`（或 `rtsp_streams`）設定有變動，停止並清除現有 `stream_units`，依新設定重建 Engine Cache 與 `stream_units`，並清空 `latest_frames`。

---

## Testing Decisions

### 好測試的定義

測試應針對**外部可觀測行為**，而非實作細節。對本功能而言：
- 測試 `config_manager.get_stream_configs()` 的輸出格式正確性（包含新舊格式相容）。
- 測試 `/video_feed` 端點在有/無 `LATEST_FRAME` 時的 HTTP 回應行為。
- 不測試 `engine_cache` 的內部 key 結構、`rr_index` 的值或 Grid 合成的像素內容。

### 測試模組（手動驗證，因目前無自動化框架）

1. **無訊號狀態驗證**：啟動系統但不提供可連線的 RTSP 來源，瀏覽器應顯示 "NO SIGNAL" 畫面。
2. **RTSP 偵測框顯示**：提供有效 RTSP 串流，瀏覽器應顯示即時畫面且偵測框位置正確對齊目標物體。
3. **多路 Grid 顯示**：設定 2 路以上 RTSP 串流，確認畫面以 Grid 並排顯示，每路標籤正確。
4. **Per-Stream Model**：設定兩路串流各指定不同模型，確認各路偵測結果獨立（不互相污染）。
5. **Engine Cache 驗證**：設定多路串流使用相同 `model` 路徑，觀察啟動記憶體用量是否與單模型相近（透過系統工具如 `htop` 目視確認）。
6. **向下相容**：使用舊版 `rtsp_streams: [url1, url2]` 格式，確認系統正常運作。
7. **熱重載**：執行中修改 `streams` 設定（新增/移除/變更模型），確認系統自動重建串流與引擎不當機。
8. **video 模式迴歸**：切換至 `mode: video`，確認原有影片播放與偵測框功能不受影響。

---

## Out of Scope

- **每路串流的獨立 `/video_feed/<id>` 端點**：本 PRD 採 Grid 合圖於同一端點，多端點擴展留待後續。
- **網頁 UI 個別串流的 FPS / 推論時間統計**：效能指標仍由 `performance.log` 記錄，不在本次 UI 顯示範圍。
- **多 Process 架構**：模型大小與速度相近時單 Process 已足夠，多 Process 優化不在本次範圍。
- **MJPEG 以外的串流協定（WebRTC、HLS）**：維持現有 MJPEG 方式，其他協定不在本次範圍。
- **自動化測試框架建置**：測試方式維持手動驗證。
- **Grid 顯示的欄數由 UI 動態設定**：欄數固定為 `max_cols=2`，UI 調整留待後續。

---

## Further Notes

- `cv2.imencode('.jpg', grid, [cv2.IMWRITE_JPEG_QUALITY, 80])` 的品質值 80 在頻寬與畫質之間取得平衡，可視網路環境調整。
- 在 Raspberry Pi 5 上，`cv2.imencode` 對 640px 寬影像的額外 CPU 開銷估計低於 5ms，不影響推論吞吐量。
- Round-Robin 的有效每路 FPS 受限於單次推論時間，例如推論 150ms → 最高 6.7 FPS/路，與串流路數無關。
- Engine Cache 的 key 使用**字串路徑**比對，需注意相同模型若以不同路徑字串（如相對路徑與絕對路徑混用）設定，仍會被視為不同模型而各自載入。建議統一在 `config.yaml` 中使用相對路徑。
