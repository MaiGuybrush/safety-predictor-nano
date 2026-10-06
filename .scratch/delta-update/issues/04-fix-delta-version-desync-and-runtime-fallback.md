## Parent

#82 ([DeltaUpdate] 輕量增量更新機制藍圖)

## What to build

解決 Delta 增量更新套用重啟後，系統版本仍為舊版（1.0.0）並陷入重複提示「有新版本可用」的死迴圈問題。

### 問題背景與根本原因：
1. **打包端**：`scripts/build_delta_package.py` 在建置 `argus.zip` 時，直接壓縮 `src/argus`，未將指定的 `--version` 動態寫入 `argus.zip` 內之 `argus/__init__.py`，導致 zip 內部 `__version__` 仍硬編碼為舊版。
2. **執行端**：`install.sh --delta` 雖成功更新了檔案系統的 `version.txt`，但 Python 模組與 `UpdateManager` 開機時僅讀取 `argus.__version__`，從未探測 `version.txt`。
3. **連鎖反應**：重啟後 `UpdateManager.current_version` 仍為 1.0.0，開機版本檢查向 API 比對（API 提供 1.1.0），誤判有更高版本可用，導致 Web UI 右上角再次亮起「新版本可用」呼吸徽章。

### 交付內容：
1. **打包工具修復**：`build_delta_package.py` 建置時，動態將 `--version` 注入 `argus.zip` 內的 `argus/__init__.py`。
2. **打包端版本一致性防呆**：當指定之 `--version` 與原始碼 `src/argus/__init__.py` 不一致時拋錯中斷，確保 Git 倉庫與補丁包版本嚴格對齊，未指定時預設採用原始碼版本。
3. **執行端雙保險解析**：`src/argus/__init__.py` 與 `UpdateManager` 增加本機 `version.txt` 探測機制，啟動與重啟時優先採用 `version.txt` 中的版本號。
4. **消除重複提示**：更新重啟後，`UpdateManager.current_version` 正確更新為目標版本（如 1.1.0），API 版本檢查判定已是最新版本，Web UI 不再跳出更新提示。
5. **自動化測試**：補充打包版本注入、原始碼版本一致性校驗與 `version.txt` 解析之單元測試。

## Acceptance criteria

- [x] `build_delta_package.py --version <ver>` 產出的 `argus.zip` 內部 `argus/__init__.py` 包含 `__version__ = "<ver>"`。
- [x] `build_delta_package.py` 檢查指定之 `--version` 是否與 `src/argus/__init__.py` 一致，若不一致則拒絕建置並提示先更新原始碼版本號。
- [x] 執行端開機時若環境目錄存在 `version.txt`，`argus.__version__` 與 `UpdateManager.current_version` 正確優先採用該版本。
- [x] 執行 TC-04 / TC-05 流程後，重啟之 Web UI 導覽列與 `/api/health` 正確顯示新版本號（如 `v1.1.0`）。
- [x] 重啟後開機版本檢查判定為最新版本，Web UI 不再出現「新版本可用」呼吸徽章。
- [x] 單元測試覆蓋打包版本注入與執行端 `version.txt` 優先級判定，測試全數 PASS。

## Blocked by

- None — can start immediately.
