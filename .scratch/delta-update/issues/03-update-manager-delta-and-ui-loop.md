## Parent

#82 ([DeltaUpdate] 輕量增量更新機制藍圖)

## What to build

在應用層完整串接 App Management API、UpdateManager 狀態機與 Web UI 前端展示，完成端到端增量更新閉環：
1. **AppUpdateClient 增量封包優先選取**：
   - 擴充 `AppUpdateClient.get_download_info()`，於 `filesInfo` 清單中優先配對 `argus_delta-*.tar.gz`，若伺服器未提供增量包則自動安全降級（Fallback）使用全量包。
2. **UpdateManager 增量狀態流與解壓套用**：
   - 識別當前下載為 Delta Package，動態調整磁碟預檢空間需求（由 2.5 倍全量 650MB 降至僅需 20MB）。
   - Staging 解壓完成後，呼叫 `install.sh --delta` 執行局部原子替換。
   - 觸發重啟時發出 `sys.exit(42)`，與既有 `run.sh` 守護迴圈、30 秒健康狀態評估窗口無縫閉環。
3. **Web UI 更新彈窗與 SSE 通道增強**：
   - 更新彈窗呈現「📦 增量更新 (Delta Patch)」標籤、實際下載大小（如 2.4 MB）與傳輸速率。
   - SSE 實時進度條即時反映 2.4MB 的下載與 Staging 狀態。
4. **端到端 E2E 測試驗證**：
   - 撰寫端到端自動化測試（`tests/e2e/test_delta_update_flow.py`），覆蓋從版本輪詢、Delta 下載、局部套用到重啟健康檢查確認的全生命週期。

## Acceptance criteria

- [ ] `AppUpdateClient` 能優先解析並下載 `argus_delta` 封包，下載總量約 2.4 MB。
- [ ] 若無增量包時，自動無縫回退至全量 `argus_predictor` 封包。
- [ ] Web UI 更新彈窗與 SSE 通道正確顯示「增量更新」標籤與真實大小。
- [ ] 升級套用透過 `install.sh --delta` 執行，完成後觸發 Exit Code 42 並通過 30 秒健康檢查 Commit。
- [ ] E2E 自動化測試（`tests/e2e/test_delta_update_flow.py`）執行全數通過（遵循 CI 模式）。

## Blocked by

- #84 ([DeltaUpdate] 02 — install.sh 與更新引擎支援 Delta 局部替換與原子回滾)
