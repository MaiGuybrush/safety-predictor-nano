# [DeltaUpdate] 輕量增量更新機制藍圖 (Wayfinder Map: Delta Package Support)

## Destination

在現有 ADR-019 自動更新架構與 `--onedir` 發布模式的基礎上，擴充支援「應用層增量補丁（Delta Package）」，達成初次安裝完整環境（~256MB），後續日常更新僅需下載約 2.4MB（純代碼修復約 150KB），節省 99% 傳輸頻寬與等待時間。

## Notes

- 相關規範：[ADR-005](docs/adr/ADR-005-arm64-build-constraint.md)、[ADR-019](docs/adr/ADR-019-auto-update-and-safe-upgrade-mechanism.md)、README.md 方案 C (`--onedir`)。
- 服務生命週期：沿用既有 `run.sh` 監聽 Exit Code 42 重啟、30 秒健康狀態評估與原子回滾。
- 業務解耦策略：利用 PyInstaller 排除業務模組 + Python 內建 `zipimport` 掛載 `_internal/argus.zip`。

## Decisions so far

- [01 — 打包端業務模組解耦與 Delta 增量包建置流程](issues/01-packaging-decoupling-and-delta-builder.md) — 於 `argus_predictor.spec` 將業務代碼抽離為獨立 `argus.zip` 並透過 `zipimport` 動態載入；建立 `scripts/build_delta_package.py` 產出 < 3MB 之 Delta 增量更新包。([Gitea #83](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/83))
- [02 — install.sh 與更新引擎支援 Delta 局部替換與原子回滾](issues/02-install-script-delta-and-rollback.md) — `scripts/install.sh` 擴充支援 `--delta` 模式與 `.patch_bak/` 備份機制，達成秒級局域覆蓋與秒級原子回滾，完整保留底層動態庫與配置檔案。([Gitea #84](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/84))
- [03 — UpdateManager 整合 Delta 下載、Web UI 標籤與端到端升級閉環](issues/03-update-manager-delta-and-ui-loop.md) — `AppUpdateClient` 支援優先選取 `argus_delta-*.tar.gz` 增量包與自動回退；`UpdateManager` 整合增量磁檢（20MB）、`--delta` 套用與 Exit 42 重啟；Web UI 提供 Delta 標籤與 SSE 實時進度，並通過 E2E 全流程驗證。([Gitea #85](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/85))
- [05 — 建立跨平台獨立安裝與回滾執行器 (scripts/install.py)](issues/05-install-script-python-core.md) — 實作跨平台 Python 獨立安裝與回滾工具 `scripts/install.py`，支援 `--delta`、`--rollback` 與 `--full`，具備 Manifest SHA-256 完整性校驗與標準原子置換，通過專屬單元測試。([Gitea #91](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/91))

## Slices / Issues

- [x] 1. **[01 — 打包端業務模組解耦與 Delta 增量包建置流程](issues/01-packaging-decoupling-and-delta-builder.md)** (Gitea [#83](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/83))
- [x] 2. **[02 — install.sh 與更新引擎支援 Delta 局部替換與原子回滾](issues/02-install-script-delta-and-rollback.md)** (Gitea [#84](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/84))
- [x] 3. **[03 — UpdateManager 整合 Delta 下載、Web UI 標籤與端到端升級閉環](issues/03-update-manager-delta-and-ui-loop.md)** (Gitea [#85](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/85))
- [x] 4. **[04 — 修復 Delta 更新版本不同步：build_delta_package 注入版號至 argus.zip 且執行端優先載入 version.txt](issues/04-fix-delta-version-desync-and-runtime-fallback.md)** (Gitea [#88](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/88))
- [x] 5. **[05 — 建立跨平台獨立安裝與回滾執行器 (scripts/install.py)](issues/05-install-script-python-core.md)** (Gitea [#91](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/91))
- [x] 6. **[06 — 實作 Windows 守護腳本 (run.bat)、同步修訂 run.sh 與 main.py 自動委派防呆](issues/06-runner-scripts-and-auto-relaunch.md)** (Gitea [#92](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/92))
- [x] 7. **[07 — 重構 UpdateManager 狀態機生命週期 (遞延置換至 Exit 42) 並拔除 delta_updater 程式碼異味](issues/07-update-manager-deferred-swap-and-cleanup.md)** (Gitea [#93](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/93))
- [ ] 8. **[08 — 端到端增量更新生命週期與回滾閉環驗證 (test_delta_update_flow.py)](issues/08-e2e-deferred-update-lifecycle.md)** (Gitea [#94](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/94))


