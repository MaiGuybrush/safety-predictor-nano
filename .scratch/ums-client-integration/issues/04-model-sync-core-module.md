# 04 — model_sync 核心模組

**What to build:** 一個可獨立呼叫、可獨立測試的同步入口 `model_sync.sync_all(config_manager, client=None)`：讀取 03 解析出的 `ums_model` 目標、呼叫 `ums-client` 抓清單與下載、依規則把下載結果落地成 `InferenceEngine` 認得的格式、透過 03 的寫回方法更新 `config.yaml`，回傳成功/失敗清單。這是整個功能唯一的整合 seam，04 完成後，開機同步（05）與手動同步端點（06）都只是呼叫這一個函式。

**Blocked by:** 03（需要 `ums_model` 解析與 `update_model_paths()` 寫回方法）

- [ ] `sync_all()` 解析 config 中所有 `ums_model` 宣告（全域 + per-stream），依 `(name, version)` 去重，未宣告任何 `ums_model` 時視為 no-op
- [ ] `client` 參數未提供時預設 `UmsApiClient.from_env()`；測試時可注入假 client，不打真實網路
- [ ] 對每個同步目標：`fetch_my_models()` 找對應模型 → 依 `version`（`"latest"` 或釘住版本號）選 `ModelVersionInfo` → `download_version()` 落地到本機目錄
- [ ] Artifact 格式落地規則：回傳資料夾 → 原樣使用（NCNN）；回傳檔案且副檔名已是 `.pt` → 原樣使用；回傳檔案但副檔名不是 `.pt` → 更名為 `<model_name>.pt`。若 02 的驗證結論與此不符，依 02 的 comments 調整
- [ ] 單一目標失敗（網路錯誤、模型/版本不存在）不中斷其他目標，該目標對應的 `model_path`/`streams[].model` 維持原值不變，失敗訊息收進回傳結果
- [ ] `sync_all()` 成功時透過 03 的 `update_model_paths()` 把下載後路徑寫回 config.yaml
- [ ] 維護「最近一次同步結果」的模組層狀態，供 06 讀取
- [ ] 單元測試：mock `UmsApiClient`（比照 `test_engine_cache.py` 的 `@patch` 注入手法），驗證「單一目標成功寫回」「多目標各自去重下載」「單一目標失敗不影響其他目標與既有 config」「三種 artifact 落地規則各自的分支」
