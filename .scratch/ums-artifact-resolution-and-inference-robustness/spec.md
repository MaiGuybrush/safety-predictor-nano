Status: ready-for-agent

# Spec: UMS Artifact 模型落地智慧解析與推論引擎目錄容錯 (UMS Artifact Resolution and Inference Robustness)

> 針對真實 UMS 平台下載 Zip 解壓縮後的目錄結構（包含 `best.pt`、`result.json`、`result.CSV` 等檔案），解決直接將目錄寫入 `config.yaml` 導致 `ultralytics.YOLO` 拋出 `TypeError` 崩潰之問題，並建立智慧格式自動優先級（ONNX > PyTorch > NCNN）與雙層防護機制。

## Problem Statement

在先前的系統中，當透過 UMS API 下載模型版本時：
1. **目錄寫入導致推論執行緒崩潰**：UMS 下載的 Zip 壓縮檔解壓至 `models/<model_name>/v<version_number>/` 後，`model_sync.py::_land_artifact()` 誤將資料夾路徑寫入 `config.yaml` 的 `model_path` 或 `streams[].model`。當系統觸發熱重載時，`InferenceEngine` 將資料夾路徑傳給 `ultralytics.YOLO()`，由於該目錄並非 NCNN 專用目錄而是存放 PyTorch 權重（`best.pt`），導致 YOLO 拋出 `TypeError: model='models\yolo8n\v2' is not a supported model format`，推論執行緒異常中斷。
2. **多格式並存時缺少智慧優先級決策**：UMS 平台或未來匯出之模型壓縮包中可能同時包含 `.onnx`、`.pt` 或 NCNN 檔案，系統缺乏明確且自動化的格式挑選機制，無法在 edge/CPU 環境下自動挑選推論效能最佳的權重檔案。

## Solution

建立 **智慧格式自動優先級解析** 與 **雙層防護機制**：
1. **模型同步層 (Model Sync Layer) 智慧落地解析**：
   - 下載解壓縮後，深入目錄內部檢查檔案：
     - **優先順序 1：ONNX (`.onnx`)** ➔ 若目錄內含 `best.onnx` 或任何 `*.onnx`，回傳具體檔案路徑（如 `models/yolo8n/v2/best.onnx`）。
     - **優先順序 2：PyTorch (`.pt`)** ➔ 若目錄內含 `best.pt` 或任何 `*.pt`，回傳具體檔案路徑（如 `models/yolo8n/v2/best.pt`）。
     - **優先順序 3：NCNN (專用目錄)** ➔ 若目錄內含 `model.ncnn.param` / `*.ncnn.bin`，回傳該目錄路徑。
     - **單一檔案處理**：若非 Zip 且副檔名非 `.pt`/`.onnx`（例如 `model.bin`），自動更名為 `<model_name>.pt` 並回傳檔案路徑。
   - 確保寫回 `config.yaml` 的永遠是可直接載入的精確檔案路徑或合法 NCNN 目錄。
2. **推論引擎層 (Inference Engine Layer) 容錯增強**：
   - 在 `InferenceEngine` 初始化時，若傳入的 `model_path` 為目錄且非 NCNN 結構，自動搜尋並轉向目錄內部的 `best.onnx` / `best.pt` 進行載入，作為第二層防禦，徹底防止任何路徑異常或手動設定錯誤造成推論執行緒中斷。
3. **相關文件與 ADR 同步更新**：
   - 於 [ADR-013](file:///D:/Projects/argus/safty-predictor-nano/docs/adr/ADR-013-ums-client-model-sync.md) 中補充實測驗證結論（UMS 回傳 Zip 內含 `best.pt` 與指標檔案），更新 Artifact 落地規則決策紀錄。

## User Stories

1. As a 系統維運人員, I want 在 Web UI 上選定 UMS 模型與版本儲存後, so that 系統自動下載解壓縮並正確載入 `best.pt` 或 `best.onnx` 權重檔開始即時推論，背景執行緒不發生崩潰。
2. As a 系統維運人員, I want 當 UMS 提供的模型壓縮包內同時存在 `.onnx` 與 `.pt` 檔案時, so that 系統自動挑選推論效能較佳的 `.onnx` 檔案進行推論，無須人工手動干預。
3. As a 系統維運人員, I want 當 UMS 提供的模型壓縮包內僅有 PyTorch `.pt`（如目前的 `best.pt`）時, so that 系統自動定位並正確載入該 `.pt` 檔案。
4. As a 系統維運人員, I want 在 `config.yaml` 中看到清楚且可追蹤的實際模型路徑（如 `models/yolo8n/v2/best.pt`）, so that 我能一目了然得知當前生效的具體檔案。
5. As a 系統維運人員, I want 即使我不小心在 `config.yaml` 中將 `model_path` 寫成資料夾路徑 `models/yolo8n/v2`, so that `InferenceEngine` 也能自動在該目錄內找到可用的 `best.pt` / `best.onnx` 載入，不發生例外拋錯。
6. As a 系統開發者, I want `model_sync.py` 的單元測試能完整覆蓋目錄內含 `best.pt`、內含 `best.onnx`、內含 NCNN 與單一檔案等所有情況, so that 未來任何重構都能確保落地邏輯 100% 穩定。

## Implementation Decisions

### 1. Artifact 智慧落地解析模組 (`model_sync.py`)

- 重構 `_land_artifact(downloaded_path, model_name)`：
  - 若 `path.is_dir()`：
    - 檢查是否有 `*.onnx`（如 `best.onnx`），若有回傳該 `.onnx` 檔案字串路徑。
    - 檢查是否有 `*.pt`（如 `best.pt`），若有回傳該 `.pt` 檔案字串路徑。
    - 檢查是否有 `model.ncnn.param` 或 `*.ncnn.bin`，若有回傳目錄字串路徑。
    - 若無上述檔案但有 `model.bin`，將其更名為 `<model_name>.pt` 並回傳。
  - 若 `path` 為檔案：
    - 若副檔名為 `.pt` 或 `.onnx`，原樣回傳。
    - 若非上述副檔名，更名為 `<model_name>.pt` 並回傳。

### 2. 推論引擎目錄解析強化 (`inference_engine.py`)

- 在 `InferenceEngine.__init__(model_path, num_threads)` 中：
  - 若 `os.path.isdir(model_path)`：
    - 檢查目錄是否為 NCNN（含有 `.param` 或 `.bin`）：`self.model_type = "NCNN"`, `actual_path = model_path`。
    - 否則檢查目錄內是否存在 `.onnx` 檔案：`self.model_type = "ONNX"`, `actual_path = onnx_file_path`。
    - 否則檢查目錄內是否存在 `.pt` 檔案：`self.model_type = "PyTorch"`, `actual_path = pt_file_path`。
    - 否則保持 `actual_path = model_path`。
  - 呼叫 `self.model = YOLO(actual_path)`。

### 3. 文件與 ADR 狀態更新

- 更新 [ADR-013](file:///D:/Projects/argus/safty-predictor-nano/docs/adr/ADR-013-ums-client-model-sync.md)：記錄 UMS 實測壓縮包結構與落地規則修正。

## Testing Decisions

- **測試原則**：以單元測試注入 Mock 物件驗證外部行為，不發起真實網路請求。
- **測試範圍**：
  1. `test_model_sync.py`：
     - 測試下載解壓目錄內含 `best.pt` 時，寫回路徑為 `.../best.pt`。
     - 測試下載解壓目錄內含 `best.onnx` 時，優先選用 `.onnx`。
     - 測試下載解壓目錄內含 NCNN 檔案時，維持資料夾路徑。
     - 測試單檔非 `.pt`（`model.bin`）自動更名為 `.pt`。
  2. `test_inference_engine.py` / `test_engine_cache.py`：
     - 測試傳入包含 `best.pt` 的資料夾路徑時，`InferenceEngine` 能正確解析並成功載入。
  3. 全套單元測試回歸驗證（確保 67+ 項測試皆 PASS）。

## Out of Scope

- 在 Web UI 上新增格式手動選擇下拉選單（維持目前純自動判定，降低介面複雜度）。
- 模型格式線上轉換（如在 Raspberry Pi 上將 `.pt` 動態轉換為 ONNX 或 NCNN）。

## Further Notes

- 本次修改解決了 UMS 模型整合過程中真實環境對接的最後一個關鍵 Seam，完成後系統即可穩定無痛地在本地模型與 UMS 雲端模型之間任意切換。
