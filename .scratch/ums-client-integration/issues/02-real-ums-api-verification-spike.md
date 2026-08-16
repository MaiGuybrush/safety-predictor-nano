# 02 — 真實 UMS API 手動驗證（spike）

**What to build:** 用真實 `UMS_API_KEY` 手動跑一次 `ums_client.UmsApiClient.fetch_my_models()` + `download_version()`，確認 UMS 伺服器實際回傳的 artifact 長什麼樣子（資料夾 / zip / 副檔名不明的單一檔案），把結論記錄下來供 04 的「Artifact 格式判斷規則」對照調整。這是探索性質、需要真實憑證的手動步驟，不是可自動化的程式碼改動。

**Blocked by:** None — can start immediately

**Status:** ready-for-human（需要真實 `UMS_BASE_URL` / `UMS_API_KEY`，agent 無法自行取得憑證）

- [ ] 設定真實 `UMS_BASE_URL` / `UMS_API_KEY` 環境變數
- [ ] 執行 `UmsApiClient.from_env().fetch_my_models()`，確認回傳的 `ModelInfo`/`ModelVersionInfo` 欄位符合 `ums-client/README.md` 文件描述
- [ ] 選一個模型版本執行 `download_version()`，記錄實際回傳形態：是資料夾（zip 已解壓）還是單一檔案；若為單一檔案，記錄副檔名/檔案內容特徵（是否為 PyTorch pickle）
- [ ] 把驗證結論寫成本 ticket 的 `## Comments`，並標註是否與 spec「Artifact 格式判斷規則」的假設一致
- [ ] 若結論與假設不符，於 comments 註明應如何調整 04 的落地規則（04 的判斷邏輯集中在單一模組，屆時修正不影響其他部分）
