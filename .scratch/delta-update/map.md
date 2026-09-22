# [DeltaUpdate] 輕量增量更新機制藍圖 (Wayfinder Map: Delta Package Support)

## Destination

在現有 ADR-019 自動更新架構與 `--onedir` 發布模式的基礎上，擴充支援「應用層增量補丁（Delta Package）」，達成初次安裝完整環境（~256MB），後續日常更新僅需下載約 2.4MB（純代碼修復約 150KB），節省 99% 傳輸頻寬與等待時間。

## Notes

- 相關規範：[ADR-005](docs/adr/ADR-005-arm64-build-constraint.md)、[ADR-019](docs/adr/ADR-019-auto-update-and-safe-upgrade-mechanism.md)、README.md 方案 C (`--onedir`)。
- 服務生命週期：沿用既有 `run.sh` 監聽 Exit Code 42 重啟、30 秒健康狀態評估與原子回滾。
- 業務解耦策略：利用 PyInstaller 排除業務模組 + Python 內建 `zipimport` 掛載 `_internal/argus.zip`。

## Slices / Issues

1. **[01 — 打包端業務模組解耦與 Delta 增量包建置流程](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/83)** (Gitea [#83](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/83))
2. **[02 — install.sh 與更新引擎支援 Delta 局部替換與原子回滾](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/84)** (Gitea [#84](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/84))
3. **[03 — UpdateManager 整合 Delta 下載、Web UI 標籤與端到端升級閉環](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/85)** (Gitea [#85](http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/85))

