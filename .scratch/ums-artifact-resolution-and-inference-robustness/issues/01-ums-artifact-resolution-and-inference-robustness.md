# 01 — UMS Artifact 模型落地智慧解析與推論引擎目錄容錯 (UMS Artifact Resolution and Inference Robustness)

**What to build:** 
重構 UMS 模型落地路徑判定邏輯與推論引擎目錄解析，解決 UMS 下載 Zip 解壓縮後為資料夾導致 `ultralytics.YOLO` 拋出 `TypeError` 崩潰之問題：
1. `model_sync.py::_land_artifact()` 在解壓縮至目錄後深入掃描，依 `ONNX > PyTorch > NCNN` 智慧優先級取得具體模型檔案路徑（如 `models/yolo8n/v2/best.pt`）寫回 `config.yaml`。
2. `InferenceEngine` 增強容錯：若傳入為目錄且非 NCNN 結構，自動搜尋內部之 `*.onnx` 或 `*.pt` 權重檔案載入，徹底杜絕執行緒崩潰。
3. 撰寫單元測試覆蓋多格式目錄、單檔與推論引擎目錄解析，並驗證全套測試套件。

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] 改造 `model_sync.py::_land_artifact()`：若目標為資料夾，依序搜尋 `*.onnx` ➔ `*.pt` ➔ NCNN 目錄 ➔ `model.bin`（更名為 `.pt`），回傳精確之可用檔案/目錄字串路徑。
- [ ] 改造 `inference_engine.py::InferenceEngine.__init__()`：若傳入目錄且非 NCNN 格式，自動定位內部之 `*.onnx` 或 `*.pt` 檔案路徑載入，並正確標註 `self.model_type`。
- [ ] 更新 `test_model_sync.py`：新增測試案例驗證解壓目錄內含 `best.pt`、`best.onnx`、NCNN 與單一檔案時的落地路徑。
- [ ] 更新 `test_inference_engine.py` / `test_engine_cache.py`：驗證傳入包含 `best.pt` 的資料夾時引擎能成功初始化與推論。
- [ ] 執行全套單元測試套件（67+ 項測試），確認無任何回歸。
