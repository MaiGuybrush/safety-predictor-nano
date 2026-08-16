# 05 — 開機自動同步整合

**What to build:** 裝置開機時自動跑一次模型同步，同步完成（或失敗維持舊模型）後才建立 `stream_units`，讓「開機即拿到 UMS 上最新模型」這個使用情境完整可用，不用等 Web UI 觸發。

**Blocked by:** 04（需要 `model_sync.sync_all()`）

- [ ] `main.py` 啟動流程中、建立 `stream_units`/`engine_cache` 之前，呼叫一次 `model_sync.sync_all(config_manager)`
- [ ] 同步完成後沿用既有「讀取 config → `get_stream_configs()` → 建立 stream_units」流程，不需特殊分支（因為同步已把結果寫回 config.yaml）
- [ ] 同步失敗（例如網路不通）時開機流程仍繼續、沿用舊有 `model_path`/`streams[].model`，服務正常啟動，不因單次同步失敗而卡住開機
- [ ] 測試比照 `test_engine_cache.py` 對 `main.py` 的 mock 手法，驗證「開機呼叫一次 sync_all」「同步失敗時仍走既有路徑建立 stream_units」
