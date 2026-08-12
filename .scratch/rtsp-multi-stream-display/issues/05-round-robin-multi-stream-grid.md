# 05 — Round-Robin 排程 + 多路 Grid 合圖

**What to build:** 讓系統在有多路 RTSP 串流時，以 Round-Robin 方式輪流對每路推論，確保每路串流都能以穩定的有效 FPS 獲得推論資源，不因串流數增加而被其他路拖慢。所有路的最新標注幀合成 Grid 後推入 Web UI，讓瀏覽器在同一個視訊區塊內一眼看到所有攝影機的即時畫面與偵測框。

**Blocked by:** 04（需要 `stream_units` 含完整的串流與引擎配對）。

**Status:** ready-for-agent

- [ ] 主推論迴圈改為 Round-Robin 模式：維護 `rr_index` 整數，每輪只對 `stream_units[rr_index % len(stream_units)]` 的一路執行取幀與推論，完成後 `rr_index += 1`。
- [ ] 每路推論完成後，將標注幀以串流 URL 為 key 存入 `latest_frames` dict（持久保留至被新幀覆蓋）。
- [ ] 每輪推論後，將 `latest_frames` 中所有路的最新幀合成 Grid（2 欄為上限），JPEG 編碼後寫入 `web_ui.LATEST_FRAME`。
- [ ] Grid 合成：所有幀縮放至統一寬度（target_w=640），不足格位以純黑填補，`np.hstack` + `np.vstack` 實作。
- [ ] 設定 2 路串流，瀏覽器顯示左右並排的 Grid 畫面，每路各自顯示偵測框與自訂標籤。
- [ ] 設定 3–4 路串流，Grid 排列正確（3 路：2+1，4 路：2×2）。
- [ ] 某路串流斷線（`get_latest_frame()` 回傳 `None`）時，其對應格位保持最後一幀靜止，整體不崩潰。
- [ ] 只有 1 路串流時，退化為單路顯示（無多餘黑框），行為與 ticket 03 完成後相同。
