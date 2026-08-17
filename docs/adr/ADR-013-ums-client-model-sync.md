# ADR-013：採用 `ums-client` 從 UMS 平台同步模型（UMS Client Model Sync）

| 欄位 | 內容 |
|------|------|
| **狀態** | 已接受 (Accepted) |
| **日期** | 2026-08-16 |
| **決策者** | 開發團隊 |
| **相關 ADR** | [ADR-006](ADR-006-per-stream-model-assignment.md)、[ADR-007](ADR-007-engine-instance-cache.md) |
| **相關 Spec** | [ums-client-integration/spec.md](../../.scratch/ums-client-integration/spec.md) |

---

## 情境與問題

safety-predictor-nano 是常駐在 Raspberry Pi 5 上的 headless 服務，`model_path` / `streams[].model` 只能指向裝置本機已存在的模型檔案。要換模型，得先用其他方式把檔案手動搬到裝置上再改 `config.yaml`，沒有辦法直接從 UMS 平台的模型清單挑一個版本、讓裝置自己抓下來用。裝置沒有桌面 GUI，也沒有人現場盯著看下載進度。

---

## 決策選項與決策

### 1. 是否採用 `ums-client`

**決策：採用。** `ums-client` 是零依賴（僅用標準函式庫）、無 Qt 依賴的獨立 package，已在另一個 repo 完成並測試，供多個專案共用同一份 UMS API 呼叫邏輯。若不採用，safety-predictor-nano 需自行重刻一份 `urllib` 呼叫與 chunk 下載/解壓邏輯，重複造輪子且無法與其他專案（如 AIVision_GUI）共用維護成本。

### 2. Config schema：新增 `ums_model` 欄位

**決策：全域與 per-stream 皆新增可選欄位 `ums_model: {name, version}`**（`version` 省略時預設 `"latest"`），與 [ADR-006](ADR-006-per-stream-model-assignment.md) 的 optional field + fallback 風格並列：

```yaml
model_path: best.pt
ums_model:
  name: safety-helmet-detector
  version: latest
streams:
  - url: rtsp://192.168.1.100:554/cam1
    model: model_a.pt
    ums_model:
      name: cam1-model
      version: 3
```

未宣告 `ums_model` 的 stream（或全域）完全不受同步邏輯影響，沿用既有 `model`/`model_path` 純本機路徑用法。理由：讓「要不要用 UMS 同步」成為逐 stream 的顯式選擇，向下相容，不強迫既有部署遷移。

### 3. 同步觸發時機

**決策：開機自動 + Web UI 手動端點，兩者都要。** 理由：裝置是 headless 環境，無桌面 GUI，開機自動同步確保「重開機/更新後模型自動保持最新」；但重開機成本高，手動端點讓維運人員能在 UMS 平台上傳新版本後立即套用，不用等下次重開機。兩個觸發點呼叫同一個 `model_sync.sync_all()`，不各自實作一份同步邏輯。

### 4. `config.yaml` 寫回機制

**決策：同步完成後自動把下載後的實際路徑寫回 `config.yaml`（`model_path`/`streams[i].model`），沿用 [ADR-007](ADR-007-engine-instance-cache.md) 既有的 `check_for_updates()` mtime 輪詢機制觸發熱重載，不新增跨執行緒通知或訊號路徑。** 理由：mtime 輪詢機制已存在且運作良好，寫回檔案後自然觸發既有熱重載流程，避免重複造一條通知管線。寫回時只更新目標欄位（`ConfigManager.update_model_paths()`），不像 `web_ui.py::save_config()` 那樣重建整份 config dict，避免遺失未涉及欄位（例如 `ums_model` 宣告本身）。

---

## 理由（總結）

1. **重用既有基礎設施**：熱重載（ADR-007）、per-stream 覆蓋（ADR-006）機制不需改動即可支援模型同步的結果套用。
2. **失敗隔離**：任何單一同步目標失敗不中斷其他目標，也不影響裝置既有正在運作的模型（`sync_all()` 本身不拋例外中止呼叫端）。
3. **可測試性**：同步邏輯集中在單一模組 `model_sync.py`，以可注入的 client 呼叫 UMS API，測試時不需打真實網路。

---

## 取捨與風險

- **開機同步為阻塞式呼叫**：若 UMS 平台無回應，需在合理 timeout 內失敗並讓開機流程繼續（`UmsApiClient` 建構子預設 `timeout=30` 秒）。
- **Artifact 格式判斷規則已由真實憑證驗證**：已實測確認 UMS 回傳 Zip 壓縮包解壓後包含 `best.pt`、`result.json`、`result.CSV` 等檔案。`model_sync.py` 的落地規則更新為依 `ONNX > PyTorch > NCNN` 智慧優先級深度尋找具體模型檔案路徑並寫回 `config.yaml`，同時 `InferenceEngine` 加入目錄解析容錯。
- **`ums-client` 尚未發布成遠端 repo**：目前仍是 `pip install -e <本機路徑>`，PyInstaller 打包時本機依賴能否正確收進單一執行檔尚待部署階段驗證，非本 ADR 範圍。
