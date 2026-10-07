Status: resolved

## Parent

#90 (自動更新功能需求)

## What to build

提供脫離主程式執行期之獨立 CLI 安裝工具 `scripts/install.py`，支援 `--delta` 局部原子置換（自動建立 `_internal/.patch_bak/` 備份）、`--rollback` 秒級局部還原與 `--full` 全量切換。徹底回歸標準 `os.replace`，具備完整的 Manifest 校驗與專屬單元測試。

## Acceptance criteria

- [x] 提供 `scripts/install.py` 命令列工具，支援 `--delta <path>`、`--rollback` 與 `--full <path>` 參數
- [x] 支援 `manifest.json` 與 sha256 完整性校驗
- [x] 局部置換時自動備份既有檔案至 `_internal/.patch_bak/`，並以標準 `os.replace` 原子置換 `argus.zip`、Web 模板、手冊與 `version.txt`
- [x] 回滾時自 `.patch_bak/` 秒級還原並寫入 `.rollback_alert` 標記檔
- [x] 新增 `tests/unit/test_install_script.py`，驗證安裝與回滾流程 100% 綠燈

## Answer

已成功建立跨平台獨立 CLI 安裝與回滾執行器 `scripts/install.py` 以及專屬單元測試 `tests/unit/test_install_script.py`：
1. **獨立命令列支援**：支援 `--delta [path]`、`--rollback`、`--full [path]`、`--dir <base_dir>` 與非互動選項。
2. **完整性校驗**：支援自動解壓縮 `.tar.gz`/`.zip` 或直接讀取暫存目錄，校驗 `manifest.json` 之 `package_type == "delta"`，並對載荷各檔案進行 SHA-256 與大小校驗。
3. **安全備份與原子置換**：局部增量安裝自動建立 `_internal/.patch_bak/` 備份，使用標準 `os.replace` 原子覆蓋業務模組與靜態資源，保護底層重型動態庫。
4. **雙模秒級回滾**：優先偵測 `.patch_bak/` 執行局部秒級還原；若無局部備份則回退至全量 `argus_predictor_bak/` 還原，並產生 `.rollback_alert` 告警標記檔。
5. **單元測試全數通過**：`pytest tests/unit/test_install_script.py` 驗證 Help 輸出、Delta 安裝與局部回滾、全量切換與回滾、損壞 Manifest 攔截皆 100% 通過。

## Blocked by

- None — can start immediately
