## Parent

#90 (自動更新功能需求)

## What to build

校正狀態機生命週期。`UpdateManager._do_download` 於解壓驗證至 `updates/staging/` 後直接停在 `READY_TO_INSTALL`，嚴格不提前置換運行中檔案；`trigger_restart` 寫入包含完整中繼資料的 `.update_in_progress` 並呼叫 `sys.exit(42)`；徹底拔除 `src/argus/updates/delta_updater.py` 中的 `release_file_handles`、`gc.get_objects()` 與 `copyfile` 降級，清理所有裸吞例外並通過單元測試。

## Acceptance criteria

- [ ] `UpdateManager._do_download` 解壓與驗證完畢後僅切換為 `READY_TO_INSTALL`，不調用 `run_install_delta`
- [ ] `UpdateManager.trigger_restart` 寫入包含 `target_version`, `is_delta`, `staging_dir`, `package_type` 之 `.update_in_progress`，並呼叫 `sys.exit(42)`
- [ ] 拔除 `delta_updater.py` 中的 `release_file_handles`、`gc.get_objects()` 遍歷與 `shutil.copyfile` 就地覆寫降級，全面回歸標準 `os.replace`
- [ ] 清理所有裸吞例外 (`except Exception: pass`)，規範補齊 logger 輸出
- [ ] 更新 `tests/unit/test_update_manager.py` 與 `tests/unit/test_delta_updater.py`，單元測試全數通過

## Blocked by

- #91 (05 — 建立跨平台獨立安裝與回滾執行器 scripts/install.py)
- #92 (06 — 實作 Windows 守護腳本 run.bat、同步修訂 run.sh 與 main.py 自動委派防呆)
