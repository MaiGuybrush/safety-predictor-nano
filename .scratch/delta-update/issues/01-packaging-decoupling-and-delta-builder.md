## Parent

#82 ([DeltaUpdate] 輕量增量更新機制藍圖)

## What to build

在 PyInstaller `--onedir` 打包架構中實作「業務模組外置解耦」與「Delta 增量包自動化建置工具」：
1. **Spec 業務代碼解耦**：在 `argus_predictor.spec` 中剔除 `argus` 業務模組（防止舊代碼被焊死於 ELF 內建 PYZ 中），並在主入口點（`main.py`）透過 Python 內建 `zipimport` 優先掛載 `_internal/argus.zip`。
2. **Delta 建置腳本**：建立跨平台自動化腳本 `scripts/build_delta_package.py`，負責編譯 `src/argus` 為 bytecode zip 檔，並收錄 Web templates、mdBook 手冊與 `manifest.json`，輸出 `argus_delta-v{VERSION}-arm64.tar.gz`（體積小於 3MB）。
3. **驗證與測試**：建立單元測試驗證模組在 `zipimport` 掛載下的正確匯入，以及驗證 delta 打包腳本輸出物之完整性與 SHA256 校驗碼。

## Acceptance criteria

- [x] `argus_predictor.spec` 成功將 `argus` 自 PYZ 抽離，且主程式可透過 `_internal/argus.zip` 正常啟動並載入所有領域模組。
- [x] `scripts/build_delta_package.py` 能成功產出 `dist/argus_delta-v{VERSION}-arm64.tar.gz` 及其 `.sha256` 檔。
- [x] 增量更新包體積小於 3.5 MB（含完整離線手冊與模板），純代碼修復時小於 250 KB。
- [x] 增量包內含 `manifest.json`（標註 target_version、min_compatible_base 與檔案校驗雜湊）。
- [x] 自動化測試（`tests/unit/test_delta_packaging.py`）全部通過。

## Implementation Summary

- **`main.py`**: 實作 `mount_argus_zip()`，支援在 PyInstaller `--onedir` 環境或測試環境中動態掛載 `_internal/argus.zip`，優先級高於系統預設載入路徑。
- **`argus_predictor.spec`**: 從 `hiddenimports` 中移除所有 `argus.*` 模組，配置 `excludes=['argus']` 並在 `Analysis` 後過濾 `a.pure` 剔除所有 `argus` 前綴模組，改由 `COLLECT` 將編譯好的 `argus.zip` 輸出至 `_internal/`。
- **`scripts/build_delta_package.py`**:
  - `build_argus_zip`: 自動遞迴編譯 `src/argus` 為最高壓縮等級之 bytecode zip 檔。
  - `build_delta_package`: 整合 `argus.zip`、Web templates、mdBook 手冊與 `manifest.json`，產出 `argus_delta-v{VERSION}-{ARCH}.tar.gz` 與 `.sha256`。
  - 支援 `--code-only` 模式，產出 < 250 KB 的純代碼修復增量包。
- **`src/argus/web/web_ui.py`**: 升級模板目錄路徑解析策略，支援 zipimport 封裝環境下的模板載入回退。
- **`tests/unit/test_delta_packaging.py`**: 涵蓋 bytecode zip 編譯、zipimport 動態載入、Spec 解耦規則、全量與純代碼 Delta 打包、SHA256 校驗與 CLI 執行。

## Blocked by

- None — can start immediately.
