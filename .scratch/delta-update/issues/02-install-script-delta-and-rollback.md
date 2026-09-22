## Parent

#82 ([DeltaUpdate] 輕量增量更新機制藍圖)

## What to build

在邊緣端安裝與維護層實作 Delta 增量補丁的就地安全替換與回滾：
1. **`scripts/install.sh` 支援 `--delta` 模式**：
   - 識別輸入封包為 Delta 增量包（檢驗 `manifest.json` 與結構）。
   - **局域原子置換**：嚴格保留底層 `_internal/` 中的所有重型動態函式庫（PyTorch、OpenCV、NumPy 等）不動，僅將當前運作的 `_internal/argus.zip`、Web 模板與手冊備份至 `_internal/.patch_bak/`。
   - 將新版 `payload/` 解壓覆蓋至對應路徑，並更新版本標記。
2. **輕量級快速回滾機制**：
   - 當呼叫 `install.sh --rollback` 時，若偵測到存在 `.patch_bak/`，自動執行局部秒級還原（避免搬移 1GB 的全量目錄），並產出回滾警示標記。
3. **測試覆蓋**：
   - 撰寫測試（如 `tests/integration/test_install_delta.py` 或 shell 測試），驗證：
     - Delta 替換前後龐大動態庫未被變更或刪除。
     - 業務邏輯 `argus.zip` 成功更新至新版本。
     - 觸發回滾後正確復原舊版代碼。

## Acceptance criteria

- [ ] `scripts/install.sh --delta <delta_tar_gz>` 能正確識別並僅覆蓋 `argus.zip` 與前端資產。
- [ ] 既有底層依賴庫（如 `_internal/torch/`、`_internal/cv2/`）與本機配置（`config.yaml`、`models/`、`logs/`）完全不受影響。
- [ ] 更新前自動完成 `.patch_bak/` 備份，升級耗時在樹莓派 5 上小於 1 秒。
- [ ] `scripts/install.sh --rollback` 能在秒級內精確還原舊版 `argus.zip` 與靜態檔案。
- [ ] 整合測試驗證 Delta 升級與回滾流程 100% 通過。

## Blocked by

- #83 ([DeltaUpdate] 01 — 打包端業務模組解耦與 Delta 增量包建置流程)
