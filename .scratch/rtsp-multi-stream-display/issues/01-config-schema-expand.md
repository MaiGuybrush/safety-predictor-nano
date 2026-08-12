# 01 — Config Schema Expand：`get_stream_configs()`

**What to build:** 讓系統能夠讀取新版 `streams` 物件列表格式的設定，同時維持對舊版 `rtsp_streams` 字串列表格式的完整向下相容。完成後，任何使用舊設定格式的既有部署無需修改 `config.yaml` 即可繼續運作；使用新格式的部署則可為每路串流指定獨立的 `url`、`model`（可選）與 `label`（可選）。

**Blocked by:** None — 可立即開始。

**Status:** ready-for-agent

- [ ] `config_manager` 新增 `get_stream_configs()` 方法，回傳 `list[dict]`，每個元素包含 `url`、`model`、`label` 三個欄位。
- [ ] 當 `config.yaml` 含 `streams` 欄位（物件列表）時，正確解析每個物件，`model` 缺失時 fallback 至全域 `model_path`，`label` 缺失時回傳空字串。
- [ ] 當 `config.yaml` 不含 `streams` 但含舊版 `rtsp_streams`（字串列表）時，自動相容，每條 URL 使用全域 `model_path`，`label` 為空字串。
- [ ] 當 `streams` 和 `rtsp_streams` 同時存在時，`streams` 優先，`rtsp_streams` 被忽略。
- [ ] URL 為空字串的項目自動過濾不納入結果。
- [ ] 更新 `config.yaml` 範例，新增含 `streams` 格式的示範設定（保留舊格式的向下相容說明）。
