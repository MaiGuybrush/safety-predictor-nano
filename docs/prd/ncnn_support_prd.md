# PRD：新增 NCNN 模型格式支援（float32 / int8）

**專案**：Argus Safety Predictor Nano  
**狀態**：Ready for Agent  
**標籤**：`ready-for-agent`, `performance`, `inference`

---

## Problem Statement

Argus Safety Predictor Nano 目前僅支援 PyTorch `.pt` 格式模型，透過 `ultralytics` 在 CPU 上執行推論。在 Raspberry Pi 5 ARM64 平台上，此方式的推論延遲約為 300–500ms／幀，導致系統無法滿足即時安全偵測的低延遲需求，並且對 CPU 資源消耗極高。

NCNN 是一套由騰訊開源、針對 ARM NEON 指令集深度優化的推論框架，能將同一模型的推論時間縮短至原本的 1/3 至 1/7。目前系統架構無法載入 NCNN 格式（`.param` + `.bin` 資料夾），使用者即便手動完成模型轉換，也無法讓系統使用轉換後的模型。

---

## Solution

修改推論引擎，使其能夠根據 `config.yaml` 中的 `model_path` 自動識別模型格式：
- 若 `model_path` 指向 `.pt` 檔案，沿用現有 PyTorch 推論路徑（行為不變）。
- 若 `model_path` 指向一個資料夾（NCNN 格式，由 `ultralytics` 匯出），自動切換至 NCNN 後端。

NCNN 後端透過 `ultralytics` 的 NCNN 包裝層執行推論，同時支援 float32 與 int8 量化格式（兩者使用相同程式碼，差異僅在模型檔案本身）。此外，新增 Web UI 模型狀態列，讓操作人員可即時確認目前載入的後端與模型資訊。

---

## User Stories

1. 作為一位部署工程師，我希望系統在 Raspberry Pi 5 上以更低延遲完成 YOLO 目標偵測，以便滿足即時安全監控的需求。
2. 作為一位部署工程師，我希望只需修改 `config.yaml` 的 `model_path` 欄位即可切換至 NCNN 模型，不需要修改任何程式碼。
3. 作為一位部署工程師，我希望系統支援 NCNN float32 格式模型，以便在不犧牲太多精準度的情況下獲得明顯效能提升。
4. 作為一位部署工程師，我希望系統支援 NCNN int8 量化格式模型，以便在效能要求最嚴苛的場景下獲得最大推論速度。
5. 作為一位部署工程師，我希望切換至 NCNN 後，偵測結果的輸出格式與 PyTorch 後端完全相同，以便下游的日誌與繪框邏輯不受影響。
6. 作為一位部署工程師，我希望 NCNN 後端的推論使用 `cpu_cores` 設定的核心數作為執行緒數，以便充分利用 RPi 5 的多核心效能。
7. 作為一位部署工程師，我希望在修改 `config.yaml` 後系統能熱重載推論引擎（包含後端類型切換），不需要手動重啟應用程式。
8. 作為一位操作人員，我希望在 Web UI 上看到目前載入的模型後端類型（PyTorch 或 NCNN），以便確認系統確實使用了正確的推論後端。
9. 作為一位操作人員，我希望在 Web UI 上看到目前的模型路徑與 CPU 核心數，以便快速掌握系統目前的執行設定。
10. 作為一位操作人員，我希望 Web UI 的模型資訊每隔幾秒自動更新，以便在熱重載發生後即時反映新狀態。
11. 作為一位系統管理員，我希望現有的 `.pt` PyTorch 工作流程在新增 NCNN 支援後完全不受影響，以便不破壞任何現有部署。
12. 作為一位系統管理員，我希望 `requirements.txt` 包含 `ncnn` 套件，以便在新機器上一鍵安裝所有相依套件。

---

## Implementation Decisions

### 1. 推論後端選擇策略（零設定切換）

推論引擎根據 `model_path` 的路徑類型自動選擇後端：

- `model_path` 為**檔案**（如 `best.pt`）→ ultralytics PyTorch 後端
- `model_path` 為**資料夾**（如 `best_ncnn_model`）→ ultralytics NCNN 後端

不新增額外的 `model_format` 設定欄位，以保持設定檔的最小複雜度。

### 2. NCNN 後端實作方式

**使用 ultralytics 內建的 NCNN 包裝**，直接以 `YOLO('best_ncnn_model')` 載入並呼叫 `.predict()`，不自行實作前處理（letterbox）、後處理（座標還原）或非極大值抑制（NMS）。ultralytics 的 NCNN wrapper 自動處理 float32 與 int8 兩種量化格式，程式碼層面無需區分。

### 3. `InferenceEngine` 介面保持不變

`InferenceEngine.infer(frame, conf_threshold)` 的簽名與回傳格式（`List[dict]`，含 `cls`、`conf`、`xyxy` 欄位）維持完全相同。`main.py` 的偵測主迴圈不需要任何修改。

新增 `model_type: str` 屬性（值為 `"PyTorch"` 或 `"NCNN"`）與 `model_path: str` 屬性，供 Web UI API 讀取。

### 4. 執行緒數（num_threads）

NCNN 推論執行緒數使用現有 `config.yaml` 中的 `cpu_cores` 欄位，不新增獨立設定欄位。

### 5. 熱重載條件擴充

`main.py` 的熱重載邏輯新增偵測 `cpu_cores` 變更，與 `model_path` 變更同等觸發 `InferenceEngine` 重建。原有 `model_path` 變更觸發條件保留。

### 6. 模型狀態資訊共享

使用與 `LATEST_FRAME` 相同的共享全域變數模式（`web_ui.MODEL_INFO`）在主執行緒與 Flask 執行緒間傳遞模型資訊。`MODEL_INFO` 為一個 `dict`，包含：

```
{
  "type":      "PyTorch" | "NCNN",
  "path":      <model_path 字串>,
  "cpu_cores": <整數>
}
```

### 7. `/model_info` API 端點

在 Flask 應用新增 `GET /model_info` 端點，回傳 `MODEL_INFO` dict 的 JSON 序列化結果。

### 8. Web UI 狀態列

在 `index.html` 標頭下方新增一條模型狀態列（`model-status-bar`），每 5 秒透過 `fetch('/model_info')` 查詢並更新顯示。樣式與現有終端機綠色設計系統一致。

### 9. 相依套件

在 `requirements.txt` 新增 `ncnn`，並移除重複的 `pyyaml` 條目。

---

## Testing Decisions

### 好測試的定義

測試應針對**外部行為**，而非實作細節。對本功能而言，應測試 `InferenceEngine` 的公開介面（`model_type` 屬性、`infer()` 回傳格式），以及 `/model_info` 端點的回應結構，而不是測試內部使用哪個 class 或哪個函式。

### 測試模組

由於本專案目前**無自動化測試框架**，本 PRD 的測試策略以手動驗證為主：

1. **PyTorch 迴歸測試**：修改前後，`model_path: best.pt` 的推論結果應一致，`/model_info` 回傳 `"type": "PyTorch"`。
2. **NCNN 後端切換測試**：`model_path: best_ncnn_model` 啟動後，`/model_info` 回傳 `"type": "NCNN"`，偵測輸出格式與 PyTorch 後端相同。
3. **熱重載測試**：執行中修改 `model_path` 與 `cpu_cores`，確認引擎自動重建且 Web UI 狀態列於 5 秒內更新。
4. **效能基準測試**：在 Raspberry Pi 5 上比較 `performance.log` 中 PT 與 NCNN 的平均推論時間，確認達到預期加速倍率。

---

## Out of Scope

- **NCNN 模型轉換腳本**：使用者自行在 ARM64 環境（Raspberry Pi 5）上執行 `yolo export model=best.pt format=ncnn` 完成轉換，此工具不納入本專案。
- **int8 量化流程**：int8 模型的產生（ncnn2table / ncnn2int8）由使用者自行完成，本 PRD 僅確保系統能載入已量化的 int8 模型。
- **Vulkan GPU 加速**：Raspberry Pi 5 無 Vulkan 支援，不在考慮範圍。
- **ONNX / OpenVINO / TensorRT 等其他格式**：本 PRD 僅聚焦 NCNN 格式。
- **自動化測試框架建置**：本專案目前無測試框架，引入測試框架超出本 PRD 範圍。
- **Web UI `/model_info` 以外的 API 新增**：本次僅新增此單一端點。

---

## Further Notes

- **NCNN 套件在 x86 開發機上可安裝但無 ARM NEON 加速**，效能優勢僅在 ARM64 平台（如 RPi 5）上完全體現。
- ultralytics 對 NCNN 的支援是透過 PNNX 工具鏈匯出，建議使用與 ultralytics 版本匹配的 NCNN 套件版本以避免相容性問題。
- **預期效能改善**（RPi 5 ARM64，yolov8n 640×640 估算）：

  | 後端 | 推論時間 | 相對改善 |
  |------|---------| --------|
  | PyTorch `.pt` | ~350ms | baseline |
  | NCNN float32 | ~100ms | ~3.5× |
  | NCNN int8 | ~50ms | ~7× |
