# Handoff: Delta 增量更新 Windows [WinError 5] 修復與 Code Review 結果

## 1. 任務背景與當前狀態 (Context & Current State)

- **原始問題**：
  在 Windows 執行環境下，點擊「下載更新包」進度條推進至 100% 後報錯：
  `更新失敗: [WinError 5] 存取被拒。: '.../_internal/argus.zip.tmp' -> '.../_internal/argus.zip'`。
- **根本原因**：
  1. 系統啟動時透過 `mount_argus_zip()` 將 `_internal/argus.zip` 掛載至 `sys.path`。
  2. 載入 YOLO 推論引擎 (`ultralytics`/`torch`) 時，`importlib.metadata` 掃描 `sys.path`，透過 `zipfile.ZipFile` 開啟 `argus.zip` 並長駐於 `FastPath.lookup` 快取。
  3. Windows NTFS 預設無 `FILE_SHARE_DELETE`，當前運行的 Python 行程持有開啟控制代碼，導致 `os.replace` (MoveFileExW) 因無法 unlink 而拋出 WinError 5。
- **臨時修復變更 (Working Diff)**：
  - [`src/argus/updates/delta_updater.py`](file:///D:/Projects/argus/safety-predictor-nano/src/argus/updates/delta_updater.py)：新增 `release_file_handles` (關閉 GC 中指向該檔案的 ZipFile/IO 物件、清理快取) 與 `safe_replace_file` (重試置換並降級 `shutil.copyfile`)。
  - [`tests/unit/test_delta_updater.py`](file:///D:/Projects/argus/safety-predictor-nano/tests/unit/test_delta_updater.py)：新增鎖定檔案與開啟控制代碼之替換單元測試。
  - [`scripts/mock_app_update_server.py`](file:///D:/Projects/argus/safety-predictor-nano/scripts/mock_app_update_server.py)：補齊檔案 SHA256 動態計算與重用判斷。
  - [`src/argus/__init__.py`](file:///D:/Projects/argus/safety-predictor-nano/src/argus/__init__.py)：基準版本對齊為 `1.0.0`。
  - **實測驗證**：已於 `sandbox/argus_predictor` 重新打包 `argus.zip` 並實測通過，更新狀態順利由 `DOWNLOADING` 推進至 `READY_TO_INSTALL`。

---

## 2. 雙軸 Code Review 結果 (Review Findings)

依據 `/code-review` 執行 Standards 與 Spec 雙軸審查：

### 2.1 Standards 軸 (規範與異味)
1. **CPU 邊緣運算負擔 (硬性違規)**：
   - 參照 [`AGENTS.md`](file:///D:/Projects/argus/safety-predictor-nano/AGENTS.md)。
   - `safe_replace_file` 未限制 `sys.platform == "win32"`，在主力環境 Linux ARM64 (樹莓派 5) 上每次更新無條件遍歷全域 `gc.get_objects()`，增加不必要的 CPU 負擔。
2. **例外處理規範 (硬性違規)**：
   - 參照 [`AGENTS.md`](file:///D:/Projects/argus/safety-predictor-nano/AGENTS.md)。
   - `delta_updater.py` 存在多處無記錄的裸吞例外 (`except Exception: pass`)。
3. **設計異味 (Smells)**：
   - **Duplicated Code**：`compute_sha256` 跨檔重複；`apply_delta` 與 `rollback` 樣式重複。
   - **Feature Envy**：`release_file_handles` 透過 GC 強制關閉外部物件，干預生命週期。
   - **Speculative Generality**：反射清除 `importlib.metadata.FastPath` 屬防禦性過度設計。

### 2.2 Spec 軸 (規格與設計意圖)
1. **違背原子置換原則 (重大)**：
   - 參照 [`docs/adr/ADR-019-auto-update-and-safe-upgrade-mechanism.md`](file:///D:/Projects/argus/safety-predictor-nano/docs/adr/ADR-019-auto-update-and-safe-upgrade-mechanism.md) 第 3 節 與 [Issue 02](file:///D:/Projects/argus/safety-predictor-nano/.scratch/delta-update/issues/02-install-script-delta-and-rollback.md)。
   - `safe_replace_file` 失敗時降級為 `shutil.copyfile` 就地寫入，破壞了「原子目錄/檔案置換」原則。若寫入中途中斷將毀損 `argus.zip`。
2. **提前置換違背狀態機生命週期 (重大)**：
   - 參照 [`ADR-019`](file:///D:/Projects/argus/safety-predictor-nano/docs/adr/ADR-019-auto-update-and-safe-upgrade-mechanism.md) 第 5 節。
   - 在提示模式 (Notify Mode) 下，系統應在「下載並驗證」後進入 `READY_TO_INSTALL`，待使用者確認點擊重啟時才套用更新。目前於下載階段即呼叫 `apply_delta` 覆蓋運行中檔案，違背生命週期設計。
3. **架構根治方案缺失**：
   - 參照 [`ADR-019`](file:///D:/Projects/argus/safety-predictor-nano/docs/adr/ADR-019-auto-update-and-safe-upgrade-mechanism.md) 第 4 節。
   - 應將檔案置換遞延至程序退出 (Exit 42) 後，由外層守護進程 (`run.sh` 或 Windows 守護腳本) 完成目錄/檔案搬移，而非在主行程運作時原地置換。

---

## 3. 接續工作重點與改善建議 (Next Steps)

下一位 Agent 接手時，建議聚焦於下列改進：

1. **短期穩定化 (針對目前 Diff)**：
   - 替 `release_file_handles` 與 Windows 特化降級邏輯加上 `if sys.platform == "win32"` 平台守衛，避免影響 Linux ARM64。
   - 補齊例外日誌紀錄，移除不安全的裸吞 `pass`。
2. **中長期架構修正 (對齊 ADR-019)**：
   - 調整 `UpdateManager._do_download`：下載完成後僅解壓校驗至 `updates/staging/`，進入 `READY_TO_INSTALL`，不直接執行 `apply_delta`。
   - 將 `apply_delta` 移至 `trigger_restart` 或外部啟動腳本執行，從架構層徹底解決 Windows 行程佔用檔案問題，消除對 `gc.get_objects()` 與 `shutil.copyfile` 降級的依賴。
3. **更新藍圖同步**：
   - 更新 [`.scratch/delta-update/map.md`](file:///D:/Projects/argus/safety-predictor-nano/.scratch/delta-update/map.md)，登記本問題與相關規格修正方案。

---

## 4. 建議技能 (Suggested Skills)

接手進行後續重構或測試時，建議呼叫以下技能：
- **`code-review`**：修改後再次進行雙軸審查驗證。
- **`write-user-manual`**：若操作流程或設定畫面有所變更時同步手冊。
