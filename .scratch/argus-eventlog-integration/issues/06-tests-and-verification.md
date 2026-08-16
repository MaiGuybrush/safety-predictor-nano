Status: done (partial — 第 4 項需要真實 model weight，留給裝置端驗證)

# 06 — 測試收尾與 e2e 語法檢查

**What to build:** 補齊 01～05 各自留下的測試缺口，跑一輪全專案 import/語法檢查（比照前例 `.scratch/fps-decoupling/issues/04-e2e-verification-and-syntax-check.md` 的做法）。

**Blocked by:** 01, 02, 03, 04, 05

- [x] `pytest -q` 跑過本 repo 所有 `test_*.py`：49 passed, 1 failed。失敗的是 `test_model_sync.py::test_concurrent_sync_all_calls_do_not_lose_updates`（`NameError: threading` 未 import），跟這次改動無關，屬於平行進行中的 ums-client 整合留下的既有問題，不在本次範圍內修
- [x] `argus-eventlog` repo 的 `pytest` 跑過，2 passed（含新增的多鏡頭路由回歸測試）
- [x] `python -c "import main"` 實際 import（非只 AST 檢查）成功，`argus_eventlog`/`event_producer` 無循環 import 或路徑問題
- [ ] 手動檢查 `recordings/<camera_id>/events/` 底下實際產生的 `.jsonl`：**未執行**，因為 `best.pt` 被 gitignore、開發機上沒有真實模型權重，`mode=video` 也讀不到真實推論結果。需要在有模型權重的機器（樹莓派或有 `best.pt` 的開發環境）實際跑一次 `main.py` 確認輸出

## Comments

- 實作於本次 `/grill-me` session。
