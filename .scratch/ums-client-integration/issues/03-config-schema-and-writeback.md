# 03 — Config schema `ums_model` 解析 + ConfigManager 寫回

**What to build:** `config.yaml` 能宣告「這個 stream / 全域要同步哪個 UMS 模型」，且 `ConfigManager` 能在同步完成後把下載出來的實際路徑寫回對應欄位，不破壞既有其他欄位。這張 ticket 只做 config 層，尚未接上真正的 UMS 呼叫（那是 04 的事），可用假路徑字串完整測試這一層的讀寫行為。

**Blocked by:** None — can start immediately

- [ ] 全域新增可選欄位 `ums_model: {name, version}`（`version` 省略時預設 `"latest"`），`get_stream_configs()` 或同層方法能讀出這個宣告
- [ ] `streams[]` 每個元素新增可選欄位 `ums_model`，格式同上，覆蓋該 stream 的同步目標；不存在時該 stream 完全不受影響（既有 `model` 欄位用法照舊）
- [ ] `ConfigManager` 新增寫回方法（例如 `update_model_paths(updates)`），可針對單一 `model_path` 或指定 index 的 `streams[i].model` 寫入新路徑，且不重建整份 config dict（對照 `web_ui.py::save_config()` 現有「整份重建」寫法，本方法必須保留未涉及的既有欄位，包含 `ums_model` 本身）
- [ ] 寫回後檔案 mtime 有變動（沿用現有 `os.path.getmtime` 熱重載機制，不需額外程式碼）
- [ ] 單元測試延續 `test_config_manager.py` 的 tempfile 模式：涵蓋「舊 `rtsp_streams` 格式不受影響」「`streams[].ums_model` 解析」「`update_model_paths()` 寫回後保留其他既有欄位」三類案例
