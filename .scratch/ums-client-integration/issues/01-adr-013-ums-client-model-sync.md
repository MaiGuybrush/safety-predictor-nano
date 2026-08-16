# 01 — 補 ADR-013：ums-client 模型同步架構決策

**What to build:** 一篇新的 ADR，記錄本次 spec 已定案的架構決策，讓後續實作 ticket（03~06）能像既有 ADR-006/007 一樣「respect the ADR」。純文件產出，不涉及程式碼。

**Blocked by:** None — can start immediately

- [ ] 新增 `docs/adr/ADR-013-ums-client-model-sync.md`，格式比照 `docs/adr/ADR-006-per-stream-model-assignment.md` / `ADR-007-engine-instance-cache.md`（狀態/日期/決策者/相關 ADR/PRD 表格 + 情境與問題 + 決策選項 + 決策 + 理由 + 取捨與風險）
- [ ] 內容涵蓋：是否採用 `ums-client`（決策：採用，理由——零依賴、無 Qt，避免重刻 UMS API 呼叫邏輯）
- [ ] 內容涵蓋：`ums_model` config schema 設計（全域 + per-stream optional field + fallback，與 ADR-006 並列參照）
- [ ] 內容涵蓋：同步觸發時機決策（開機自動 + Web UI 手動端點，兩者都要，理由——headless 裝置無桌面 GUI）
- [ ] 內容涵蓋：`config.yaml` 寫回機制決策（自動寫回 + 沿用 ADR-007 既有 mtime 輪詢熱重載，不新增通知路徑）
- [ ] 更新 `docs/adr/README.md` 索引表，新增 ADR-013 一列
- [ ] `.scratch/ums-client-integration/spec.md`「Further Notes」段落的文件更新結論已反映在 ADR 內容裡（無需另外改動 spec.md 本身）
